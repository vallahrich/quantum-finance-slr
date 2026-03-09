"""Ingest bibliographic exports — RIS, BibTeX, CSV → normalized DataFrame."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .utils import generate_paper_id

log = logging.getLogger("slr_toolkit.ingest")


def _detect_preprint(venue: str, source_db: str) -> bool:
    """Return True if the record looks like a preprint."""
    combined = f"{venue} {source_db}".lower()
    return any(p in combined for p in config.PREPRINT_VENUES)

# ---------------------------------------------------------------------------
# RIS ingestion (rispy)
# ---------------------------------------------------------------------------

# Mapping from RIS tags to our normalised column names.
_RIS_TAG_MAP: dict[str, str] = {
    "title": "title",
    "primary_title": "title",
    "authors": "authors",
    "first_authors": "authors",
    "year": "year",
    "publication_year": "year",
    "doi": "doi",
    "abstract": "abstract",
    "keywords": "keywords",
    "secondary_title": "venue",
    "journal_name": "venue",
    "alternate_title3": "venue",
}


def _parse_ris(path: Path) -> list[dict[str, Any]]:
    """Parse a .ris file and return a list of normalised dicts."""
    try:
        import rispy
    except ImportError:
        log.warning("rispy not installed — skipping %s", path)
        return []

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        entries = rispy.load(fh)

    records: list[dict[str, Any]] = []
    for entry in entries:
        rec: dict[str, Any] = {}
        for ris_key, norm_key in _RIS_TAG_MAP.items():
            val = entry.get(ris_key)
            if val is None:
                continue
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            if norm_key not in rec or not rec[norm_key]:
                rec[norm_key] = str(val).strip()
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# BibTeX ingestion (bibtexparser v2)
# ---------------------------------------------------------------------------

_BIB_FIELD_MAP: dict[str, str] = {
    "title": "title",
    "author": "authors",
    "year": "year",
    "doi": "doi",
    "abstract": "abstract",
    "keywords": "keywords",
    "journal": "venue",
    "booktitle": "venue",
}


def _parse_bib(path: Path) -> list[dict[str, Any]]:
    """Parse a .bib file and return a list of normalised dicts.

    Supports both bibtexparser v1 (<=1.x) and v2 (>=2.0) APIs.
    """
    try:
        import bibtexparser
    except ImportError:
        log.warning("bibtexparser not installed — skipping %s", path)
        return []

    bib_text = path.read_text(encoding="utf-8", errors="replace")

    # Detect API version
    if hasattr(bibtexparser, "parse"):
        # v2 API
        library = bibtexparser.parse(bib_text)
        entries_raw: list[dict[str, str]] = []
        for entry in library.entries:
            d: dict[str, str] = {}
            for bib_key in _BIB_FIELD_MAP:
                field = entry.fields_dict.get(bib_key)
                if field is not None:
                    d[bib_key] = str(field.value).strip()
            entries_raw.append(d)
    else:
        # v1 API
        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        library = bibtexparser.loads(bib_text, parser=parser)
        entries_raw = library.entries  # list[dict[str, str]]

    records: list[dict[str, Any]] = []
    for entry in entries_raw:
        rec: dict[str, Any] = {}
        for bib_key, norm_key in _BIB_FIELD_MAP.items():
            val = entry.get(bib_key)
            if val is None:
                continue
            val = str(val).strip()
            if norm_key not in rec or not rec[norm_key]:
                rec[norm_key] = val
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# CSV ingestion (pandas)
# ---------------------------------------------------------------------------

# Common header variants → normalised column name (case-insensitive match).
_CSV_HEADER_MAP: dict[str, str] = {
    "title": "title",
    "document title": "title",
    "article title": "title",
    "author": "authors",
    "authors": "authors",
    "author(s)": "authors",
    "year": "year",
    "publication year": "year",
    "pub year": "year",
    "doi": "doi",
    "abstract": "abstract",
    "author keywords": "keywords",
    "keywords": "keywords",
    "index keywords": "keywords",
    "source title": "venue",
    "journal": "venue",
    "venue": "venue",
    "source": "venue",
}


def _parse_csv(path: Path) -> list[dict[str, Any]]:
    """Parse a CSV and map common column-name variants to normalised names."""
    try:
        df = pd.read_csv(path, encoding="utf-8", dtype=str)
    except Exception:
        try:
            df = pd.read_csv(path, encoding="latin-1", dtype=str)
        except Exception as exc:
            log.error("Failed to read CSV %s: %s", path, exc)
            return []

    rename_map: dict[str, str] = {}
    for col in df.columns:
        lower = col.strip().lower()
        if lower in _CSV_HEADER_MAP:
            norm = _CSV_HEADER_MAP[lower]
            if norm not in rename_map.values():
                rename_map[col] = norm

    df = df.rename(columns=rename_map)
    # Keep only normalised columns that exist
    keep = [c for c in config.NORMALIZED_COLUMNS if c in df.columns]
    df = df[keep] if keep else df
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PARSERS: dict[str, Any] = {
    ".ris": _parse_ris,
    ".bib": _parse_bib,
    ".csv": _parse_csv,
}


def ingest_run(run_folder: Path) -> pd.DataFrame:
    """Ingest all bibliographic exports in *run_folder* and write normalised CSV.

    Returns the normalised DataFrame.
    """
    run_folder = Path(run_folder).resolve()
    if not run_folder.is_dir():
        raise FileNotFoundError(f"Run folder not found: {run_folder}")

    # Determine source_db from folder name (e.g. "2026-03-08_scopus" → "scopus")
    parts = run_folder.name.split("_", maxsplit=1)
    source_db = parts[1] if len(parts) > 1 else run_folder.name

    all_records: list[dict[str, Any]] = []

    for ext, parser_fn in _PARSERS.items():
        for fpath in sorted(run_folder.glob(f"*{ext}")):
            if fpath.name == "normalized_records.csv":
                continue  # don't re-ingest our own output
            log.info("Parsing %s", fpath)
            recs = parser_fn(fpath)
            for r in recs:
                r["source_db"] = source_db
                r["export_file"] = fpath.name
            all_records.extend(recs)
            log.info("  → %d records from %s", len(recs), fpath.name)

    if not all_records:
        log.warning("No records found in %s", run_folder)
        return pd.DataFrame(columns=config.NORMALIZED_COLUMNS)

    df = pd.DataFrame(all_records)

    # Ensure all normalised columns exist
    for col in config.NORMALIZED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Generate stable paper_id
    df["paper_id"] = df.apply(
        lambda row: generate_paper_id(row.get("title"), row.get("authors"), row.get("year")),
        axis=1,
    )

    # Detect preprints
    df["is_preprint"] = df.apply(
        lambda row: "1" if _detect_preprint(
            str(row.get("venue", "")), str(row.get("source_db", ""))
        ) else "0",
        axis=1,
    )
    # version_group_id is populated later during dedup (preprint↔published linking)
    df["version_group_id"] = ""

    df = df[config.NORMALIZED_COLUMNS]  # canonical column order
    df = df.fillna("")

    # Write normalised output
    out_path = run_folder / "normalized_records.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info("Wrote %d normalised records → %s", len(df), out_path)

    return df
