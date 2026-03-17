"""Deduplication logic and master-library builder."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pandas as pd

from . import config
from .ingest import ingest_run
from .utils import ensure_dir

log = logging.getLogger("slr_toolkit.dedup")


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _first_author_initial(authors: str) -> str:
    """Return the lowercased first character of the first author's last name."""
    if not authors:
        return ""
    first = authors.split(";")[0].split(",")[0].strip()
    return first[0].lower() if first else ""


def deduplicate(df: pd.DataFrame, *, fuzzy: bool = True) -> pd.DataFrame:
    """Mark duplicate records in-place and return the DataFrame.

    Adds a ``duplicate_of`` column.  Pass 1 uses DOI exact match; Pass 2
    uses fuzzy title matching (requires *rapidfuzz*).
    """
    df = df.copy()
    df["duplicate_of"] = ""

    # --- Pass 0: exact paper_id collisions ---------------------------------
    # `paper_id` is the frozen screening key used by downstream manual review.
    # If multiple rows share the same generated paper_id, they must collapse to
    # a single canonical record before screening outputs can be joined safely.
    df["_paper_id"] = df["paper_id"].astype(str).str.strip()
    pid_groups = df[df["_paper_id"] != ""].groupby("_paper_id", sort=False)

    pid_dupes = 0
    for _paper_id, grp in pid_groups:
        if len(grp) < 2:
            continue
        canonical = grp.index[0]
        for idx in grp.index[1:]:
            if df.at[idx, "duplicate_of"] == "":
                df.at[idx, "duplicate_of"] = df.at[canonical, "paper_id"]
                pid_dupes += 1

    log.info("Pass 0 (paper_id): %d duplicate rows collapsed", pid_dupes)

    # --- Pass 1: DOI exact match (case-insensitive) -------------------------
    df["_doi_lower"] = df["doi"].astype(str).str.strip().str.lower()
    doi_groups = df[df["_doi_lower"] != ""].groupby("_doi_lower")

    for _doi, grp in doi_groups:
        if len(grp) < 2:
            continue
        canonical = grp.index[0]
        for idx in grp.index[1:]:
            if df.at[idx, "duplicate_of"] == "":
                df.at[idx, "duplicate_of"] = df.at[canonical, "paper_id"]

    log.info(
        "Pass 1 (DOI): %d duplicates found",
        (df["duplicate_of"] != "").sum(),
    )

    # --- Pass 2: Fuzzy title match ------------------------------------------
    if fuzzy:
        try:
            from rapidfuzz import fuzz  # type: ignore[import-untyped]
        except ImportError:
            log.info("rapidfuzz not installed — skipping fuzzy dedup pass")
            fuzzy = False

    if fuzzy:
        from rapidfuzz import fuzz  # type: ignore[import-untyped]
        from collections import defaultdict

        remaining_mask = df["duplicate_of"] == ""
        remaining_idx = df.index[remaining_mask].tolist()

        # Pre-compute lookup dicts for O(1) access
        titles: dict[int, str] = {}
        years: dict[int, float] = {}
        fa_initials: dict[int, str] = {}
        paper_ids: dict[int, str] = {}

        for idx in remaining_idx:
            titles[idx] = str(df.at[idx, "title"]).strip().lower()
            try:
                years[idx] = float(df.at[idx, "year"])
            except (ValueError, TypeError):
                years[idx] = float("nan")
            fa_initials[idx] = _first_author_initial(str(df.at[idx, "authors"]))
            paper_ids[idx] = df.at[idx, "paper_id"]

        # Blocking: group by (first_author_initial, year) to avoid O(n²)
        blocks: dict[tuple[str, int], list[int]] = defaultdict(list)
        for idx in remaining_idx:
            fa = fa_initials[idx]
            yr = years[idx]
            if fa and not pd.isna(yr):
                yr_int = int(yr)
                for y in range(yr_int - config.YEAR_TOLERANCE, yr_int + config.YEAR_TOLERANCE + 1):
                    blocks[(fa, y)].append(idx)

        fuzzy_dupes = 0
        seen_pairs: set[tuple[int, int]] = set()

        for block_indices in blocks.values():
            if len(block_indices) < 2:
                continue
            for i, idx_a in enumerate(block_indices):
                if df.at[idx_a, "duplicate_of"] != "":
                    continue
                for idx_b in block_indices[i + 1:]:
                    if df.at[idx_b, "duplicate_of"] != "":
                        continue
                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)

                    score = fuzz.token_sort_ratio(titles[idx_a], titles[idx_b])
                    if score < config.FUZZY_TITLE_THRESHOLD:
                        continue

                    df.at[idx_b, "duplicate_of"] = paper_ids[idx_a]
                    fuzzy_dupes += 1

        log.info("Pass 2 (fuzzy): %d additional duplicates found", fuzzy_dupes)

    # Clean up temp columns
    df.drop(columns=[c for c in df.columns if c.startswith("_")], inplace=True)

    # --- Pass 3: Preprint↔published version grouping -----------------------
    df = _assign_version_groups(df)

    return df


def _assign_version_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Link preprint↔peer-reviewed versions via version_group_id.

    For each duplicate pair, if one is a preprint and the other is not,
    assign the same version_group_id (the canonical paper_id).  Also
    assign standalone version_group_ids to non-grouped records.
    """
    if "version_group_id" not in df.columns:
        df["version_group_id"] = ""
    if "is_preprint" not in df.columns:
        df["is_preprint"] = "0"

    # Build groups from duplicate_of chains
    groups: dict[str, str] = {}  # paper_id → group_leader
    for idx, row in df.iterrows():
        pid = row["paper_id"]
        dup_of = row["duplicate_of"]
        if dup_of:
            leader = groups.get(dup_of, dup_of)
            groups[pid] = leader
            groups[dup_of] = leader
        else:
            groups.setdefault(pid, pid)

    # Resolve transitive groups
    def _resolve(pid: str) -> str:
        seen: set[str] = set()
        while groups.get(pid, pid) != pid and pid not in seen:
            seen.add(pid)
            pid = groups[pid]
        return pid

    df["version_group_id"] = df["paper_id"].apply(_resolve)

    n_groups = df["version_group_id"].nunique()
    n_multi = (df.groupby("version_group_id").size() > 1).sum()
    log.info(
        "Version groups: %d total, %d multi-version (preprint↔published)",
        n_groups, n_multi,
    )
    return df


# ---------------------------------------------------------------------------
# Master-library builder
# ---------------------------------------------------------------------------

def build_master() -> pd.DataFrame:
    """Scan all run folders, deduplicate, and write master outputs.

    Returns the full (including duplicates) master DataFrame.
    """
    run_dirs = sorted(config.RAW_EXPORTS_DIR.glob("*/"))
    if not run_dirs:
        log.warning("No run folders found under %s", config.RAW_EXPORTS_DIR)
        return pd.DataFrame(columns=config.NORMALIZED_COLUMNS + ["duplicate_of"])

    frames: list[pd.DataFrame] = []
    for rd in run_dirs:
        if not rd.is_dir():
            continue
        if rd.name.startswith("_"):
            log.info("Skipping inactive run directory: %s", rd)
            continue
        norm_csv = rd / "normalized_records.csv"
        if norm_csv.exists():
            log.info("Loading %s", norm_csv)
            frames.append(pd.read_csv(norm_csv, dtype=str).fillna(""))
        else:
            log.info("No normalized CSV in %s — ingesting on the fly", rd)
            frames.append(ingest_run(rd))

    if not frames:
        log.warning("No records to build master from.")
        return pd.DataFrame(columns=config.NORMALIZED_COLUMNS + ["duplicate_of"])

    master = pd.concat(frames, ignore_index=True).fillna("")
    total_ingested = len(master)
    log.info("Total ingested records: %d", total_ingested)

    master = deduplicate(master)

    n_dupes = (master["duplicate_of"] != "").sum()
    n_unique = total_ingested - n_dupes

    # Write master CSV
    ensure_dir(config.DEDUPED_DIR)
    master.to_csv(config.MASTER_RECORDS_CSV, index=False, encoding="utf-8")
    log.info("Wrote %s", config.MASTER_RECORDS_CSV)

    # Write minimal BibTeX
    _write_master_bib(master[master["duplicate_of"] == ""])

    # Summary
    print(f"\n{'='*50}")
    print(f"  Total ingested : {total_ingested}")
    print(f"  Unique records : {n_unique}")
    print(f"  Duplicates     : {n_dupes}")
    print(f"{'='*50}\n")

    return master


def _write_master_bib(df: pd.DataFrame) -> None:
    """Write a minimal BibTeX file from the unique records."""
    lines: list[str] = []
    for _, row in df.iterrows():
        key = row.get("paper_id", "unknown")
        fields: list[str] = []
        if row.get("title"):
            fields.append(f"  title = {{{row['title']}}}")
        if row.get("authors"):
            fields.append(f"  author = {{{row['authors']}}}")
        if row.get("year"):
            fields.append(f"  year = {{{row['year']}}}")
        if row.get("doi"):
            fields.append(f"  doi = {{{row['doi']}}}")
        if row.get("venue"):
            fields.append(f"  journal = {{{row['venue']}}}")
        if row.get("abstract"):
            fields.append(f"  abstract = {{{row['abstract']}}}")
        entry = "@article{" + key + ",\n" + ",\n".join(fields) + "\n}\n"
        lines.append(entry)

    content = "\n".join(lines)
    config.MASTER_LIBRARY_BIB.write_text(content, encoding="utf-8")
    log.info("Wrote %d entries → %s", len(df), config.MASTER_LIBRARY_BIB)
