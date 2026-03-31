"""Download PDFs via institutional (CBS EZProxy) access using Playwright.

Automates browser-based PDF download through CBS's EZProxy, handling
publisher-specific login flows and PDF download buttons.

Requires: ``pip install playwright && playwright install chromium``
"""

from __future__ import annotations

import csv
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config
from .utils import atomic_write_text, ensure_dir

log = logging.getLogger("slr_toolkit.institutional_download")

_MAX_FILENAME_LEN = 80


def _sanitise_filename(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = t.strip("_")
    return t[:_MAX_FILENAME_LEN]


# ── Download log I/O (shared format with pdf_download.py) ────────────────

_LOG_COLUMNS = [
    "paper_id", "title", "doi", "source", "pdf_url",
    "status", "filename", "timestamp",
]


def _csv_escape(val: str) -> str:
    if any(c in val for c in (",", '"', "\n")):
        return '"' + val.replace('"', '""') + '"'
    return val


def _load_download_log(log_path: Path) -> dict[str, dict]:
    if not log_path.exists():
        return {}
    with open(log_path, encoding="utf-8", newline="") as f:
        return {row["paper_id"]: row for row in csv.DictReader(f)}


def _save_download_log(log_path: Path, entries: dict[str, dict]) -> None:
    lines = [",".join(_LOG_COLUMNS)]
    for pid in sorted(entries):
        row = entries[pid]
        vals = [_csv_escape(str(row.get(c, ""))) for c in _LOG_COLUMNS]
        lines.append(",".join(vals))
    atomic_write_text(log_path, "\n".join(lines) + "\n")


# ── Publisher-specific PDF extraction ────────────────────────────────────

def _find_pdf_link_ieee(page: Any) -> str | None:
    """Find PDF download link on IEEE Xplore."""
    # IEEE has a "PDF" button that triggers a download
    try:
        btn = page.locator("a.pdf-btn-link, a[href*='stamp.jsp']").first
        if btn.count():
            href = btn.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://ieeexplore.ieee.org{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_springer(page: Any) -> str | None:
    """Find PDF link on Springer/Nature."""
    try:
        link = page.locator("a[data-article-pdf], a[href*='/content/pdf/']").first
        if link.count():
            href = link.get_attribute("href")
            if href:
                base = page.url.split("/")[0] + "//" + page.url.split("/")[2]
                return href if href.startswith("http") else f"{base}{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_elsevier(page: Any) -> str | None:
    """Find PDF link on ScienceDirect (Elsevier)."""
    try:
        link = page.locator("a.pdf-download, a[href*='pdfft']").first
        if link.count():
            href = link.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://www.sciencedirect.com{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_wiley(page: Any) -> str | None:
    """Find PDF link on Wiley Online Library."""
    try:
        link = page.locator("a[href*='/doi/pdfdirect/'], a[href*='/doi/pdf/']").first
        if link.count():
            href = link.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://onlinelibrary.wiley.com{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_generic(page: Any) -> str | None:
    """Generic fallback: look for any PDF link on the page."""
    try:
        # Look for links with .pdf in href or 'download pdf' text
        for selector in [
            "a[href$='.pdf']",
            "a[href*='pdf']",
            "a:has-text('Download PDF')",
            "a:has-text('Full Text PDF')",
            "a:has-text('View PDF')",
        ]:
            link = page.locator(selector).first
            if link.count():
                href = link.get_attribute("href")
                if href:
                    base = page.url.split("/")[0] + "//" + page.url.split("/")[2]
                    return href if href.startswith("http") else f"{base}{href}"
    except Exception:
        pass
    return None


_PUBLISHER_HANDLERS = [
    ("ieeexplore.ieee.org", _find_pdf_link_ieee),
    ("link.springer.com", _find_pdf_link_springer),
    ("nature.com", _find_pdf_link_springer),
    ("sciencedirect.com", _find_pdf_link_elsevier),
    ("onlinelibrary.wiley.com", _find_pdf_link_wiley),
]


def _find_pdf_on_page(page: Any) -> str | None:
    """Try publisher-specific handlers then generic fallback."""
    current_url = page.url.lower()
    for domain, handler in _PUBLISHER_HANDLERS:
        if domain in current_url:
            result = handler(page)
            if result:
                return result
    return _find_pdf_link_generic(page)


# ── Main entry point ─────────────────────────────────────────────────────

def institutional_download(
    *,
    proxy_base: str,
    delay: float = 7.0,
    max_papers: int | None = None,
    headless: bool = True,
    input_file: Path | None = None,
) -> Path:
    """Download PDFs via CBS institutional proxy using Playwright.

    Parameters
    ----------
    proxy_base : str
        CBS EZProxy base URL for DOI resolution, e.g.
        ``https://www-doi-org.esc-web.lib.cbs.dk``.
    delay : float
        Seconds between requests (default 7 — respectful institutional use).
    max_papers : int | None
        Cap on papers to attempt.
    headless : bool
        Run browser in headless mode (default True). Set False for debugging.
    input_file : Path | None
        Override the included-papers CSV.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright is required for institutional downloads.\n"
            "Install with: pip install playwright && playwright install chromium"
        )

    # Load papers that need downloading
    included_path = input_file or config.INCLUDED_FOR_CODING
    included_ids: set[str] = set()
    with open(included_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("final_decision", "").strip().lower() == "include":
                included_ids.add(row["paper_id"])

    master: dict[str, dict] = {}
    if config.MASTER_RECORDS_CSV.exists():
        with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["paper_id"] in included_ids:
                    master[row["paper_id"]] = row

    log_path = config.DOWNLOAD_LOG_CSV
    download_log = _load_download_log(log_path)
    pdf_dir = ensure_dir(config.FULL_TEXTS_DIR / "pdfs")

    # Filter to papers that still need PDFs and have DOIs
    papers_to_try = []
    for pid in sorted(included_ids):
        if download_log.get(pid, {}).get("status") == "success":
            continue
        paper = master.get(pid, {"paper_id": pid, "title": "", "doi": ""})
        doi = paper.get("doi", "").strip()
        if doi:
            papers_to_try.append(paper)

    if max_papers is not None:
        papers_to_try = papers_to_try[:max_papers]

    if not papers_to_try:
        print("No papers need institutional download (all have PDFs or no DOIs).")
        return log_path

    print(f"Attempting institutional download for {len(papers_to_try)} papers...")
    print(f"  Proxy: {proxy_base}")
    print(f"  Delay: {delay}s between requests")
    print(f"  Mode:  {'headless' if headless else 'visible browser'}")
    print()

    stats = {"success": 0, "failed": 0, "login_needed": False}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        for i, paper in enumerate(papers_to_try, 1):
            pid = paper["paper_id"]
            doi = paper.get("doi", "").strip()
            title = paper.get("title", "") or pid
            short_title = title[:60] + "..." if len(title) > 60 else title
            print(f"  [{i}/{len(papers_to_try)}] {short_title}")

            # Construct proxied DOI URL
            # e.g. https://www-doi-org.esc-web.lib.cbs.dk/10.1007/s10479-023-05444-y
            proxy_url = f"{proxy_base.rstrip('/')}/{doi}"

            try:
                page.goto(proxy_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)  # Let page fully render

                # Check if we hit a login page
                if "login" in page.url.lower() or "auth" in page.url.lower():
                    if not stats["login_needed"]:
                        print("\n  *** CBS login page detected! ***")
                        print("  Please log in manually in the browser window.")
                        print("  Waiting 60 seconds for login...")
                        stats["login_needed"] = True
                        page.wait_for_url("**/doi/**", timeout=60000)
                        time.sleep(2)

                # Try to find PDF link on the publisher page
                pdf_link = _find_pdf_on_page(page)

                if pdf_link:
                    # Download the PDF
                    pdf_filename = f"{pid}_{_sanitise_filename(title)}.pdf"
                    dest = pdf_dir / pdf_filename

                    with page.expect_download(timeout=60000) as download_info:
                        page.goto(pdf_link, timeout=30000)
                    download = download_info.value
                    download.save_as(str(dest))

                    # Validate
                    if dest.exists() and dest.read_bytes()[:5].startswith(b"%PDF"):
                        download_log[pid] = {
                            "paper_id": pid,
                            "title": title,
                            "doi": doi,
                            "source": "institutional",
                            "pdf_url": pdf_link,
                            "status": "success",
                            "filename": pdf_filename,
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                        }
                        stats["success"] += 1
                        print(f"           -> OK (institutional)")
                    else:
                        # Download didn't produce valid PDF, try direct navigation
                        if dest.exists():
                            dest.unlink()
                        raise ValueError("Downloaded file is not a valid PDF")
                else:
                    raise ValueError("No PDF link found on publisher page")

            except Exception as exc:
                log.debug("Institutional download failed for %s: %s", pid, exc)
                download_log[pid] = {
                    "paper_id": pid,
                    "title": title,
                    "doi": doi,
                    "source": "institutional",
                    "pdf_url": proxy_url,
                    "status": "download_failed",
                    "filename": "",
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                stats["failed"] += 1
                print(f"           -> FAILED ({exc})")

            _save_download_log(log_path, download_log)
            time.sleep(delay)

        browser.close()

    print(f"\nInstitutional download complete:")
    print(f"  Success: {stats['success']}")
    print(f"  Failed:  {stats['failed']}")
    print(f"  Log:     {log_path.name}")

    return log_path
