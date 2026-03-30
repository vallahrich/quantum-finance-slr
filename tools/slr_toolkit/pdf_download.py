"""Download open-access PDFs for included papers.

Resolution order per paper:
  1. arXiv  — if DOI matches ``10.48550/arXiv.*`` or source_db == "arxiv"
  2. Semantic Scholar — ``openAccessPdf`` field via paper lookup
  3. Unpaywall — free OA copy lookup by DOI (requires email for polite pool)

Results are written to ``08_full_texts/pdfs/`` with a CSV log tracking
every attempt so the process is fully resumable.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config
from .utils import atomic_write_text, ensure_dir, load_master_records

log = logging.getLogger("slr_toolkit.pdf_download")

# ── Constants ──────────────────────────────────────────────────────────────

_ARXIV_PDF_BASE = "https://arxiv.org/pdf/"
_S2_PAPER_API = "https://api.semanticscholar.org/graph/v1/paper"
_UNPAYWALL_API = "https://api.unpaywall.org/v2"

_USER_AGENT = "QuantumFinanceSLR/0.1 (systematic-review-toolkit; mailto:{email})"
_PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}

# Maximum filename length (stem) to avoid OS limits
_MAX_FILENAME_LEN = 80


# ── Helpers ────────────────────────────────────────────────────────────────

def _sanitise_filename(title: str) -> str:
    """Convert a paper title to a safe, short filename fragment."""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = t.strip("_")
    return t[:_MAX_FILENAME_LEN]


def _extract_arxiv_id(doi: str, source_db: str, title: str) -> str | None:
    """Try to extract an arXiv ID from DOI or source metadata.

    arXiv DOIs look like ``10.48550/arXiv.2301.12345``.
    """
    if doi:
        m = re.match(r"10\.48550/arXiv\.(.+)", doi, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _fetch_url(url: str, *, timeout: int = 30, headers: dict | None = None) -> bytes:
    """Fetch raw bytes from *url*, raising on HTTP errors."""
    hdrs = {"User-Agent": _USER_AGENT.format(email="slr@example.com")}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_json(url: str, *, timeout: int = 30, headers: dict | None = None) -> dict:
    """Fetch and parse JSON from *url*."""
    data = _fetch_url(url, timeout=timeout, headers=headers)
    return json.loads(data)


def _download_pdf(url: str, dest: Path, *, timeout: int = 60) -> bool:
    """Download a PDF from *url* to *dest*. Returns True on success."""
    try:
        # Encode spaces and other unsafe chars in the URL path/query
        url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=-._~%")
        req = urllib.request.Request(url, headers={
            "User-Agent": _USER_AGENT.format(email="slr@example.com"),
            "Accept": "application/pdf",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()

        # Basic validation: PDF files start with %PDF
        if not data[:5].startswith(b"%PDF"):
            log.warning("Response from %s does not look like a PDF (first bytes: %r)", url, data[:20])
            return False

        ensure_dir(dest.parent)
        dest.write_bytes(data)
        log.info("Downloaded PDF: %s (%d bytes)", dest.name, len(data))
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        log.warning("PDF download failed from %s: %s", url, exc)
        return False


# ── Source resolvers ───────────────────────────────────────────────────────

def _try_arxiv(paper: dict) -> str | None:
    """Return arXiv PDF URL if paper has an arXiv ID."""
    arxiv_id = _extract_arxiv_id(
        paper.get("doi", ""),
        paper.get("source_db", ""),
        paper.get("title", ""),
    )
    if arxiv_id:
        return f"{_ARXIV_PDF_BASE}{arxiv_id}.pdf"
    return None


def _try_semantic_scholar(
    paper: dict,
    *,
    s2_key: str = "",
    delay: float = 3.5,
) -> str | None:
    """Look up paper on Semantic Scholar and return openAccessPdf URL if available."""
    doi = paper.get("doi", "").strip()

    # Prefer DOI-based lookup (exact match), fall back to title search
    if doi:
        url = f"{_S2_PAPER_API}/DOI:{urllib.parse.quote(doi, safe='')}?fields=openAccessPdf,externalIds"
    else:
        title = paper.get("title", "").strip()
        if not title:
            return None
        params = urllib.parse.urlencode({
            "query": title,
            "limit": "1",
            "fields": "openAccessPdf,externalIds,title",
        })
        url = f"{_S2_PAPER_API}/search?{params}"

    headers: dict[str, str] = {}
    if s2_key:
        headers["x-api-key"] = s2_key

    time.sleep(delay)  # Respect S2 rate limits

    try:
        data = _fetch_json(url, headers=headers)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        log.debug("S2 lookup failed for %s: %s", paper.get("paper_id"), exc)
        return None

    # If we used search, unwrap the first result
    if "data" in data:
        results = data.get("data", [])
        if not results:
            return None
        data = results[0]

    oa_pdf = data.get("openAccessPdf")
    if oa_pdf and isinstance(oa_pdf, dict):
        pdf_url = oa_pdf.get("url", "")
        if pdf_url:
            # If S2 also gave us an arXiv ID we missed, prefer the arXiv URL
            ext_ids = data.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv")
            if arxiv_id:
                return f"{_ARXIV_PDF_BASE}{arxiv_id}.pdf"
            return pdf_url

    # Even if no openAccessPdf, check for arXiv ID
    ext_ids = data.get("externalIds") or {}
    arxiv_id = ext_ids.get("ArXiv")
    if arxiv_id:
        return f"{_ARXIV_PDF_BASE}{arxiv_id}.pdf"

    return None


def _try_unpaywall(paper: dict, *, email: str) -> str | None:
    """Look up paper on Unpaywall (free OA discovery by DOI)."""
    doi = paper.get("doi", "").strip()
    if not doi or not email:
        return None

    url = f"{_UNPAYWALL_API}/{urllib.parse.quote(doi, safe='')}?email={urllib.parse.quote(email, safe='')}"
    time.sleep(1.0)

    try:
        data = _fetch_json(url)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        log.debug("Unpaywall lookup failed for DOI %s: %s", doi, exc)
        return None

    # Best OA location
    best_oa = data.get("best_oa_location") or {}
    pdf_url = best_oa.get("url_for_pdf", "")
    if pdf_url:
        return pdf_url

    # Fall back to any OA location with a PDF
    for loc in data.get("oa_locations", []):
        pdf_url = loc.get("url_for_pdf", "")
        if pdf_url:
            return pdf_url

    return None


# ── Download log I/O ──────────────────────────────────────────────────────

_LOG_COLUMNS = [
    "paper_id", "title", "doi", "source", "pdf_url",
    "status", "filename", "timestamp",
]


def _load_download_log(log_path: Path) -> dict[str, dict]:
    """Load download log CSV. Returns {paper_id: row_dict}."""
    if not log_path.exists():
        return {}
    with open(log_path, encoding="utf-8", newline="") as f:
        return {row["paper_id"]: row for row in csv.DictReader(f)}


def _save_download_log(log_path: Path, entries: dict[str, dict]) -> None:
    """Write download log CSV atomically."""
    lines = [",".join(_LOG_COLUMNS)]
    for pid in sorted(entries):
        row = entries[pid]
        vals = [_csv_escape(str(row.get(c, ""))) for c in _LOG_COLUMNS]
        lines.append(",".join(vals))
    atomic_write_text(log_path, "\n".join(lines) + "\n")


def _csv_escape(val: str) -> str:
    """Escape a value for CSV output."""
    if any(c in val for c in (",", '"', "\n")):
        return '"' + val.replace('"', '""') + '"'
    return val


# ── Main entry point ──────────────────────────────────────────────────────

def download_pdfs(
    *,
    email: str | None = None,
    s2_key: str | None = None,
    max_papers: int | None = None,
    delay: float = 3.5,
    skip_existing: bool = True,
    input_file: Path | None = None,
) -> Path:
    """Download open-access PDFs for all papers in the final included list.

    Parameters
    ----------
    email : str | None
        Contact email for Unpaywall polite pool. Also checked via
        ``UNPAYWALL_EMAIL`` env var. If not provided, Unpaywall is skipped.
    s2_key : str | None
        Semantic Scholar API key for higher rate limits. Also checked via
        ``S2_API_KEY`` env var.
    max_papers : int | None
        Cap on how many papers to attempt (useful for testing).
    delay : float
        Seconds between API requests (default 3.5 — S2 free-tier limit).
    skip_existing : bool
        Skip papers that already have a successful download in the log.
    input_file : Path | None
        Override the default included-papers file.

    Returns
    -------
    Path
        Path to the download log CSV.
    """
    email = email or os.environ.get("UNPAYWALL_EMAIL", "")
    s2_key = s2_key or os.environ.get("S2_API_KEY", "")

    # 1. Load final included paper IDs
    included_path = input_file or config.INCLUDED_FOR_CODING
    if not included_path.exists():
        raise FileNotFoundError(
            f"Included papers file not found: {included_path}\n"
            "Run screening reconciliation first."
        )

    included_ids: set[str] = set()
    with open(included_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("final_decision", "").strip().lower() == "include":
                included_ids.add(row["paper_id"])

    if not included_ids:
        log.warning("No included papers found in %s", included_path)
        return config.DOWNLOAD_LOG_CSV

    log.info("Found %d included papers", len(included_ids))

    # 2. Load master records for metadata
    master: dict[str, dict] = {}
    if config.MASTER_RECORDS_CSV.exists():
        with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["paper_id"] in included_ids:
                    master[row["paper_id"]] = row

    log.info("Matched %d / %d papers in master records", len(master), len(included_ids))

    # 3. Load existing download log (for resume support)
    log_path = config.DOWNLOAD_LOG_CSV
    download_log = _load_download_log(log_path)

    # 4. Determine which papers still need downloading
    papers_to_try = []
    for pid in sorted(included_ids):
        if skip_existing and pid in download_log and download_log[pid].get("status") == "success":
            continue
        if pid in master:
            papers_to_try.append(master[pid])
        else:
            # Paper is in included list but not in master — create minimal record
            papers_to_try.append({"paper_id": pid, "title": "", "doi": "", "source_db": ""})

    if max_papers is not None:
        papers_to_try = papers_to_try[:max_papers]

    if not papers_to_try:
        print("All included papers already downloaded (or no papers to process).")
        return log_path

    print(f"Attempting PDF download for {len(papers_to_try)} papers...")
    print(f"  Output: {config.FULL_TEXTS_DIR / 'pdfs'}")
    if email:
        print(f"  Unpaywall email: {email}")
    else:
        print("  Unpaywall: disabled (set --email or UNPAYWALL_EMAIL env var)")
    print()

    pdf_dir = ensure_dir(config.FULL_TEXTS_DIR / "pdfs")
    stats = {"success": 0, "failed": 0, "skipped": 0}

    for i, paper in enumerate(papers_to_try, 1):
        pid = paper["paper_id"]
        title = paper.get("title", "") or pid
        short_title = title[:60] + "..." if len(title) > 60 else title
        print(f"  [{i}/{len(papers_to_try)}] {short_title}")

        pdf_filename = f"{pid}_{_sanitise_filename(title)}.pdf"
        dest = pdf_dir / pdf_filename

        # If the file already exists on disk, skip
        if dest.exists() and skip_existing:
            log.info("  Already on disk: %s", pdf_filename)
            download_log[pid] = {
                "paper_id": pid,
                "title": title,
                "doi": paper.get("doi", ""),
                "source": "cached",
                "pdf_url": "",
                "status": "success",
                "filename": pdf_filename,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            stats["skipped"] += 1
            print(f"           -> cached (already on disk)")
            continue

        # Try sources in priority order
        pdf_url: str | None = None
        source_used = ""

        # 1. arXiv (fast, no API call needed if DOI contains arXiv ID)
        pdf_url = _try_arxiv(paper)
        if pdf_url:
            source_used = "arxiv"
            log.info("  arXiv URL found: %s", pdf_url)

        # 2. Semantic Scholar
        if not pdf_url:
            pdf_url = _try_semantic_scholar(paper, s2_key=s2_key, delay=delay)
            if pdf_url:
                source_used = "semantic_scholar"
                log.info("  S2 open-access URL found: %s", pdf_url)

        # 3. Unpaywall
        if not pdf_url and email:
            pdf_url = _try_unpaywall(paper, email=email)
            if pdf_url:
                source_used = "unpaywall"
                log.info("  Unpaywall URL found: %s", pdf_url)

        # Attempt download
        if pdf_url:
            success = _download_pdf(pdf_url, dest)
            status = "success" if success else "download_failed"
        else:
            success = False
            status = "no_oa_source"
            source_used = "none"

        download_log[pid] = {
            "paper_id": pid,
            "title": title,
            "doi": paper.get("doi", ""),
            "source": source_used,
            "pdf_url": pdf_url or "",
            "status": status,
            "filename": pdf_filename if success else "",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        if success:
            stats["success"] += 1
            print(f"           -> OK ({source_used})")
        else:
            stats["failed"] += 1
            print(f"           -> FAILED ({status})")

        # Save log after each paper (checkpoint for resume)
        _save_download_log(log_path, download_log)

    # Final summary
    total = stats["success"] + stats["failed"] + stats["skipped"]
    print(f"\nDownload complete:")
    print(f"  Success:  {stats['success']}")
    print(f"  Cached:   {stats['skipped']}")
    print(f"  Failed:   {stats['failed']}")
    print(f"  Total:    {total}")
    print(f"  Log:      {log_path.name}")

    success_rate = (stats["success"] + stats["skipped"]) / total * 100 if total else 0
    print(f"  OA rate:  {success_rate:.0f}%")

    return log_path
