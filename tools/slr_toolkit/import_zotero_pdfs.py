"""Import PDFs downloaded via Zotero into the SLR pipeline.

Scans a user-specified directory for PDFs, matches them to paper_ids
via DOI or fuzzy title matching, copies them to ``07_full_texts/pdfs/``
with the correct naming convention, and updates ``download_log.csv``.
"""

from __future__ import annotations

import csv
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import config
from .utils import atomic_write_text, ensure_dir

log = logging.getLogger("slr_toolkit.import_zotero_pdfs")

_MAX_FILENAME_LEN = 80


def _sanitise_filename(title: str) -> str:
    """Convert a paper title to a safe, short filename fragment."""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = t.strip("_")
    return t[:_MAX_FILENAME_LEN]


def _load_download_log(log_path: Path) -> dict[str, dict]:
    if not log_path.exists():
        return {}
    with open(log_path, encoding="utf-8", newline="") as f:
        return {row["paper_id"]: row for row in csv.DictReader(f)}


_LOG_COLUMNS = [
    "paper_id", "title", "doi", "source", "pdf_url",
    "status", "filename", "timestamp",
]


def _csv_escape(val: str) -> str:
    if any(c in val for c in (",", '"', "\n")):
        return '"' + val.replace('"', '""') + '"'
    return val


def _save_download_log(log_path: Path, entries: dict[str, dict]) -> None:
    lines = [",".join(_LOG_COLUMNS)]
    for pid in sorted(entries):
        row = entries[pid]
        vals = [_csv_escape(str(row.get(c, ""))) for c in _LOG_COLUMNS]
        lines.append(",".join(vals))
    atomic_write_text(log_path, "\n".join(lines) + "\n")


def _build_paper_index(
    included_path: Path,
    master_path: Path,
) -> dict[str, dict]:
    """Build lookup structures for matching: {paper_id: metadata}."""
    included_ids: set[str] = set()
    with open(included_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("final_decision", "").strip().lower() == "include":
                included_ids.add(row["paper_id"])

    papers: dict[str, dict] = {}
    with open(master_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["paper_id"] in included_ids:
                papers[row["paper_id"]] = row
    return papers


def _normalise_title(title: str) -> str:
    """Normalise title for fuzzy matching."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def import_zotero_pdfs(
    zotero_dir: Path,
    *,
    match_threshold: float = 0.85,
) -> Path:
    """Import PDFs from *zotero_dir* into the SLR PDF directory.

    Matches PDFs to papers by:
    1. DOI embedded in filename (Zotero sometimes includes DOI)
    2. Fuzzy title matching against master records

    Returns the download log path.
    """
    pdf_dir = ensure_dir(config.FULL_TEXTS_DIR / "pdfs")
    log_path = config.DOWNLOAD_LOG_CSV
    download_log = _load_download_log(log_path)

    papers = _build_paper_index(config.INCLUDED_FOR_CODING, config.MASTER_RECORDS_CSV)

    # Build reverse lookups
    doi_to_pid: dict[str, str] = {}
    title_to_pid: dict[str, str] = {}
    for pid, meta in papers.items():
        doi = meta.get("doi", "").strip().lower()
        if doi:
            doi_to_pid[doi] = pid
        title = _normalise_title(meta.get("title", ""))
        if title:
            title_to_pid[title] = pid

    # Try to use rapidfuzz for fuzzy matching if available
    try:
        from rapidfuzz import fuzz as _fuzz
        has_fuzz = True
    except ImportError:
        has_fuzz = False

    source_pdfs = sorted(zotero_dir.glob("*.pdf"))
    if not source_pdfs:
        print(f"No PDF files found in {zotero_dir}")
        return log_path

    print(f"Found {len(source_pdfs)} PDFs in {zotero_dir}")

    stats = {"matched": 0, "already_have": 0, "unmatched": 0}
    unmatched_files: list[str] = []

    for pdf_path in source_pdfs:
        stem = pdf_path.stem
        norm_stem = _normalise_title(stem)

        matched_pid: str | None = None

        # Strategy 1: Check if filename contains a DOI
        for doi, pid in doi_to_pid.items():
            doi_fragment = doi.replace("/", "_").replace(".", "_").lower()
            if doi_fragment in norm_stem.replace(" ", "_"):
                matched_pid = pid
                break

        # Strategy 2: Exact title match
        if not matched_pid:
            matched_pid = title_to_pid.get(norm_stem)

        # Strategy 3: Fuzzy title match
        if not matched_pid and has_fuzz:
            best_score = 0.0
            for title, pid in title_to_pid.items():
                score = _fuzz.token_sort_ratio(norm_stem, title) / 100.0
                if score > best_score:
                    best_score = score
                    if score >= match_threshold:
                        matched_pid = pid

        if not matched_pid:
            stats["unmatched"] += 1
            unmatched_files.append(pdf_path.name)
            continue

        # Check if we already have this PDF
        if download_log.get(matched_pid, {}).get("status") == "success":
            stats["already_have"] += 1
            continue

        # Copy PDF with correct naming
        meta = papers[matched_pid]
        title = meta.get("title", "") or matched_pid
        pdf_filename = f"{matched_pid}_{_sanitise_filename(title)}.pdf"
        dest = pdf_dir / pdf_filename

        shutil.copy2(pdf_path, dest)

        download_log[matched_pid] = {
            "paper_id": matched_pid,
            "title": title,
            "doi": meta.get("doi", ""),
            "source": "zotero",
            "pdf_url": "",
            "status": "success",
            "filename": pdf_filename,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        stats["matched"] += 1
        print(f"  Imported: {pdf_path.name} -> {pdf_filename}")

        _save_download_log(log_path, download_log)

    print(f"\nImport complete:")
    print(f"  Matched & imported: {stats['matched']}")
    print(f"  Already had PDF:    {stats['already_have']}")
    print(f"  Unmatched:          {stats['unmatched']}")

    if unmatched_files:
        print(f"\nUnmatched files (review manually):")
        for name in unmatched_files[:20]:
            print(f"  - {name}")
        if len(unmatched_files) > 20:
            print(f"  ... and {len(unmatched_files) - 20} more")

    return log_path
