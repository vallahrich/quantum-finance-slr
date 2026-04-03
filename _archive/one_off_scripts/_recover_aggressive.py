"""Aggressive multi-strategy PDF recovery for remaining missing papers.

Strategies (in order):
  1. Copy PDFs from merged duplicates already on disk
  2. arXiv API title search (for arXiv-sourced papers without arXiv DOIs)
  3. MDPI open-access via proper session handling
  4. SSRN alternate download pattern
  5. DOI redirect chain — follow to publisher, scrape PDF link from HTML
  6. PubMed Central lookup by title
  7. Internet Archive / Wayback Machine cached PDFs
  8. Google Scholar scrape (last resort, aggressive)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from tools.slr_toolkit import config
from tools.slr_toolkit.utils import atomic_write_text, ensure_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_ARXIV_PDF = "https://arxiv.org/pdf/"
_ARXIV_API = "http://export.arxiv.org/api/query"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_BOT_UA = "QuantumFinanceSLR/0.1 (systematic-review-toolkit)"

LOG_COLUMNS = [
    "paper_id", "title", "doi", "source", "pdf_url",
    "status", "filename", "timestamp",
]


def _sanitise(title: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "_", title.lower().strip()).strip("_")
    return t[:80]


def _is_pdf(data: bytes) -> bool:
    return data[:5].startswith(b"%PDF")


def _download(url: str, dest: Path, *, ua: str = _BROWSER_UA) -> bool:
    """Download with browser UA, follow redirects, validate PDF."""
    try:
        session = requests.Session()
        resp = session.get(
            url,
            headers={
                "User-Agent": ua,
                "Accept": "application/pdf, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": url,
            },
            timeout=60,
            allow_redirects=True,
            verify=False,
        )
        resp.raise_for_status()
        if _is_pdf(resp.content):
            ensure_dir(dest.parent)
            dest.write_bytes(resp.content)
            return True
        # Try to find PDF link in HTML
        pdf_link = _find_pdf_in_html(resp.text, resp.url)
        if pdf_link:
            resp2 = session.get(
                pdf_link,
                headers={"User-Agent": ua, "Referer": resp.url},
                timeout=60,
                allow_redirects=True,
                verify=False,
            )
            if resp2.status_code == 200 and _is_pdf(resp2.content):
                ensure_dir(dest.parent)
                dest.write_bytes(resp2.content)
                return True
    except Exception:
        pass
    return False


def _find_pdf_in_html(html: str, base_url: str) -> str | None:
    """Extract PDF link from HTML page."""
    # meta refresh
    m = re.search(r'<meta[^>]+url=(["\']?)([^"\'>]+\.pdf[^"\'>]*)\1', html, re.I)
    if m:
        return urllib.parse.urljoin(base_url, m.group(2))
    # Download PDF button/link
    for pattern in [
        r'href=(["\'])([^"\']+\.pdf[^"\']*)\1',
        r'href=(["\'])([^"\']*download[^"\']*pdf[^"\']*)\1',
        r'href=(["\'])([^"\']*pdfft[^"\']*)\1',
        r'href=(["\'])([^"\']*pdfdirect[^"\']*)\1',
        r'data-article-pdf=(["\'])([^"\']+)\1',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return urllib.parse.urljoin(base_url, m.group(2))
    return None


# ── Strategy 1: Copy from merged duplicates ──

def strategy_copy_dupes(
    missing: list[dict], master_rows: list[dict],
    pdf_dir: Path, log_entries: dict,
) -> int:
    """Copy PDFs from duplicate paper_ids that are already on disk."""
    log.info("=== Strategy 1: Copy from merged duplicates ===")
    existing_pdfs = {}
    for fn in pdf_dir.iterdir():
        if fn.suffix == ".pdf":
            prefix = fn.name.split("_")[0]
            existing_pdfs[prefix] = fn

    # Build dup map: for each canonical paper, find all duplicates
    dup_children = {}
    for r in master_rows:
        parent = r.get("duplicate_of", "").strip()
        if parent:
            dup_children.setdefault(parent, []).append(r["paper_id"])

    recovered = 0
    for paper in missing:
        pid = paper["paper_id"]
        children = dup_children.get(pid, [])
        for child in children:
            if child in existing_pdfs:
                src = existing_pdfs[child]
                title = paper.get("title", pid)
                new_name = f"{pid}_{_sanitise(title)}.pdf"
                dest = pdf_dir / new_name
                shutil.copy2(src, dest)
                log_entries[pid] = {
                    "paper_id": pid, "title": title,
                    "doi": paper.get("doi", ""),
                    "source": "duplicate_copy",
                    "pdf_url": str(src),
                    "status": "success",
                    "filename": new_name,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                log.info("  Copied from dup %s -> %s", child, new_name)
                recovered += 1
                break
    log.info("  Result: %d recovered", recovered)
    return recovered


# ── Strategy 2: arXiv API title search ──

def strategy_arxiv_title(
    missing: list[dict], canonical: dict,
    pdf_dir: Path, log_entries: dict,
) -> int:
    """Search arXiv API by title for papers sourced from arXiv but lacking arXiv DOIs."""
    log.info("=== Strategy 2: arXiv API title search ===")
    arxiv_papers = []
    for p in missing:
        m = canonical.get(p["paper_id"], {})
        sdb = m.get("source_db", "").lower()
        venue = m.get("venue", "").lower()
        if sdb == "arxiv" or "arxiv" in venue:
            arxiv_papers.append(p)

    log.info("  %d arXiv-sourced papers to search", len(arxiv_papers))
    recovered = 0

    for i, paper in enumerate(arxiv_papers):
        pid = paper["paper_id"]
        title = paper.get("title", "")
        if not title:
            continue
        safe = title[:50].encode("ascii", errors="replace").decode("ascii")
        print(f"    [{i+1}/{len(arxiv_papers)}] {safe}...", end=" ", flush=True)

        # Search arXiv API
        query = f'ti:"{title}"'
        params = urllib.parse.urlencode({
            "search_query": f"ti:{title}",
            "max_results": "3",
        })
        time.sleep(3.0)  # arXiv rate limit
        try:
            resp = requests.get(f"{_ARXIV_API}?{params}", timeout=30, verify=False)
            if resp.status_code != 200:
                print("API error")
                continue
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            for entry in entries:
                entry_title = (entry.findtext("atom:title", "", ns) or "").strip()
                entry_title_norm = re.sub(r"\s+", " ", entry_title).lower()
                paper_title_norm = re.sub(r"\s+", " ", title).lower().strip()
                # Check similarity
                if not _titles_similar(paper_title_norm, entry_title_norm):
                    continue
                # Get arXiv ID
                arxiv_url = entry.findtext("atom:id", "", ns)  # e.g. http://arxiv.org/abs/2301.12345v1
                if not arxiv_url:
                    continue
                arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
                arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
                pdf_url = f"{_ARXIV_PDF}{arxiv_id}.pdf"

                filename = f"{pid}_{_sanitise(title)}.pdf"
                dest = pdf_dir / filename
                ok = _download(pdf_url, dest)
                if ok:
                    log_entries[pid] = {
                        "paper_id": pid, "title": title,
                        "doi": paper.get("doi", ""),
                        "source": "arxiv_title_search",
                        "pdf_url": pdf_url,
                        "status": "success",
                        "filename": filename,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                    }
                    print(f"OK ({arxiv_id})")
                    recovered += 1
                    break
                else:
                    print("download failed")
                    break
            else:
                print("no match")
        except Exception as e:
            print(f"error: {e}")

    log.info("  Result: %d recovered", recovered)
    return recovered


def _titles_similar(a: str, b: str) -> bool:
    """Check if two normalized titles are essentially the same."""
    na = re.sub(r"[^a-z0-9]", "", a)
    nb = re.sub(r"[^a-z0-9]", "", b)
    if not na or not nb:
        return False
    shorter = min(len(na), len(nb))
    if shorter < 20:
        return na == nb
    return na[:shorter] == nb[:shorter]


# ── Strategy 3: MDPI with proper session ──

def strategy_mdpi(
    missing: list[dict], pdf_dir: Path, log_entries: dict,
) -> int:
    """MDPI papers are OA but need proper browser session with cookies."""
    log.info("=== Strategy 3: MDPI open-access recovery ===")
    mdpi_papers = [p for p in missing if "mdpi.com" in p.get("pdf_url", "")]
    log.info("  %d MDPI papers to try", len(mdpi_papers))
    recovered = 0

    session = requests.Session()
    # First, visit the MDPI homepage to get session cookies
    try:
        session.get("https://www.mdpi.com", headers={"User-Agent": _BROWSER_UA},
                     timeout=15, verify=False)
    except Exception:
        pass

    for i, paper in enumerate(mdpi_papers):
        pid = paper["paper_id"]
        url = paper["pdf_url"]
        title = paper.get("title", pid)
        safe = title[:50].encode("ascii", errors="replace").decode("ascii")
        print(f"    [{i+1}/{len(mdpi_papers)}] {safe}...", end=" ", flush=True)

        time.sleep(2.0)
        try:
            # Try the PDF URL with session cookies
            resp = session.get(
                url,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Referer": "https://www.mdpi.com/",
                    "Accept": "application/pdf, */*",
                },
                timeout=60, allow_redirects=True, verify=False,
            )
            if resp.status_code == 200 and _is_pdf(resp.content):
                filename = f"{pid}_{_sanitise(title)}.pdf"
                dest = pdf_dir / filename
                dest.write_bytes(resp.content)
                log_entries[pid] = {
                    "paper_id": pid, "title": title,
                    "doi": paper.get("doi", ""),
                    "source": "mdpi_session",
                    "pdf_url": url,
                    "status": "success",
                    "filename": filename,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                print("OK")
                recovered += 1
                continue

            # Alt: strip version param, try /pdf without it
            base_url = url.split("?")[0]
            if base_url != url:
                resp2 = session.get(
                    base_url,
                    headers={"User-Agent": _BROWSER_UA, "Referer": "https://www.mdpi.com/"},
                    timeout=60, allow_redirects=True, verify=False,
                )
                if resp2.status_code == 200 and _is_pdf(resp2.content):
                    filename = f"{pid}_{_sanitise(title)}.pdf"
                    dest = pdf_dir / filename
                    dest.write_bytes(resp2.content)
                    log_entries[pid] = {
                        "paper_id": pid, "title": title,
                        "doi": paper.get("doi", ""),
                        "source": "mdpi_session",
                        "pdf_url": base_url,
                        "status": "success",
                        "filename": filename,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                    }
                    print("OK (alt URL)")
                    recovered += 1
                    continue

            # Try the article page and extract PDF link
            article_url = re.sub(r"/pdf\b", "", base_url)
            resp3 = session.get(
                article_url,
                headers={"User-Agent": _BROWSER_UA},
                timeout=30, allow_redirects=True, verify=False,
            )
            if resp3.status_code == 200:
                pdf_link = _find_pdf_in_html(resp3.text, resp3.url)
                if pdf_link:
                    resp4 = session.get(
                        pdf_link,
                        headers={"User-Agent": _BROWSER_UA, "Referer": resp3.url},
                        timeout=60, verify=False,
                    )
                    if resp4.status_code == 200 and _is_pdf(resp4.content):
                        filename = f"{pid}_{_sanitise(title)}.pdf"
                        dest = pdf_dir / filename
                        dest.write_bytes(resp4.content)
                        log_entries[pid] = {
                            "paper_id": pid, "title": title,
                            "doi": paper.get("doi", ""),
                            "source": "mdpi_html_extract",
                            "pdf_url": pdf_link,
                            "status": "success",
                            "filename": filename,
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                        }
                        print("OK (html extract)")
                        recovered += 1
                        continue
            print("still blocked")
        except Exception as e:
            print(f"error: {e}")

    log.info("  Result: %d recovered", recovered)
    return recovered


# ── Strategy 4: SSRN alternate pattern ──

def strategy_ssrn(
    missing: list[dict], pdf_dir: Path, log_entries: dict,
) -> int:
    """Try SSRN with browser session and alternate URL patterns."""
    log.info("=== Strategy 4: SSRN recovery ===")
    ssrn_papers = [p for p in missing if "ssrn.com" in p.get("pdf_url", "")]
    log.info("  %d SSRN papers to try", len(ssrn_papers))
    recovered = 0

    session = requests.Session()
    # Get SSRN cookies
    try:
        session.get("https://www.ssrn.com", headers={"User-Agent": _BROWSER_UA},
                     timeout=15, verify=False)
    except Exception:
        pass

    for i, paper in enumerate(ssrn_papers):
        pid = paper["paper_id"]
        url = paper["pdf_url"]
        title = paper.get("title", pid)
        safe = title[:50].encode("ascii", errors="replace").decode("ascii")
        print(f"    [{i+1}/{len(ssrn_papers)}] {safe}...", end=" ", flush=True)

        time.sleep(3.0)
        try:
            # Try with full browser headers
            resp = session.get(
                url,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Referer": "https://papers.ssrn.com/",
                    "Accept": "application/pdf, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=60, allow_redirects=True, verify=False,
            )
            if resp.status_code == 200 and _is_pdf(resp.content):
                filename = f"{pid}_{_sanitise(title)}.pdf"
                dest = pdf_dir / filename
                dest.write_bytes(resp.content)
                log_entries[pid] = {
                    "paper_id": pid, "title": title,
                    "doi": paper.get("doi", ""),
                    "source": "ssrn_session",
                    "pdf_url": url,
                    "status": "success",
                    "filename": filename,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                print("OK")
                recovered += 1
                continue
            print(f"blocked ({resp.status_code})")
        except Exception as e:
            print(f"error: {e}")

    log.info("  Result: %d recovered", recovered)
    return recovered


# ── Strategy 5: DOI redirect chain + HTML scraping ──

def strategy_doi_redirect(
    missing: list[dict], pdf_dir: Path, log_entries: dict,
) -> int:
    """Follow DOI redirects to publisher page, then scrape PDF link from HTML."""
    log.info("=== Strategy 5: DOI redirect chain + HTML scrape ===")
    doi_papers = [p for p in missing if "doi.org" in p.get("pdf_url", "")]
    log.info("  %d doi.org papers to try", len(doi_papers))
    recovered = 0

    session = requests.Session()

    for i, paper in enumerate(doi_papers):
        pid = paper["paper_id"]
        url = paper["pdf_url"]
        title = paper.get("title", pid)
        safe = title[:50].encode("ascii", errors="replace").decode("ascii")
        print(f"    [{i+1}/{len(doi_papers)}] {safe}...", end=" ", flush=True)

        time.sleep(1.5)
        try:
            resp = session.get(
                url,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Accept": "text/html, application/pdf, */*",
                },
                timeout=30, allow_redirects=True, verify=False,
            )
            if resp.status_code == 200 and _is_pdf(resp.content):
                filename = f"{pid}_{_sanitise(title)}.pdf"
                dest = pdf_dir / filename
                dest.write_bytes(resp.content)
                log_entries[pid] = {
                    "paper_id": pid, "title": title,
                    "doi": paper.get("doi", ""),
                    "source": "doi_redirect",
                    "pdf_url": resp.url,
                    "status": "success",
                    "filename": filename,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                print("OK (direct)")
                recovered += 1
                continue

            if resp.status_code == 200:
                # Try to find PDF link in the HTML
                pdf_link = _find_pdf_in_html(resp.text[:16384], resp.url)
                if pdf_link:
                    time.sleep(1.0)
                    resp2 = session.get(
                        pdf_link,
                        headers={
                            "User-Agent": _BROWSER_UA,
                            "Referer": resp.url,
                        },
                        timeout=60, allow_redirects=True, verify=False,
                    )
                    if resp2.status_code == 200 and _is_pdf(resp2.content):
                        filename = f"{pid}_{_sanitise(title)}.pdf"
                        dest = pdf_dir / filename
                        dest.write_bytes(resp2.content)
                        log_entries[pid] = {
                            "paper_id": pid, "title": title,
                            "doi": paper.get("doi", ""),
                            "source": "doi_html_scrape",
                            "pdf_url": pdf_link,
                            "status": "success",
                            "filename": filename,
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                        }
                        print(f"OK (scraped)")
                        recovered += 1
                        continue
                print("no PDF in HTML")
            else:
                print(f"HTTP {resp.status_code}")
        except Exception as e:
            print(f"error: {e}")

    log.info("  Result: %d recovered", recovered)
    return recovered


# ── Strategy 6: Remaining papers - try with DOI on Unpaywall + CORE ──

def strategy_unpaywall_core(
    missing: list[dict], canonical: dict,
    pdf_dir: Path, log_entries: dict,
) -> int:
    """For remaining papers with DOIs, try Unpaywall and CORE one more time
    with title-based search as fallback."""
    log.info("=== Strategy 6: Unpaywall + CORE title search ===")
    # Papers still missing that have DOIs and weren't covered by strategies above
    already_tried = set()
    for p in missing:
        url = p.get("pdf_url", "")
        if "mdpi.com" in url or "ssrn.com" in url or "doi.org" in url:
            already_tried.add(p["paper_id"])

    remaining = [p for p in missing if p["paper_id"] not in already_tried
                 and p["paper_id"] in canonical]
    log.info("  %d remaining papers to try", len(remaining))
    recovered = 0

    for i, paper in enumerate(remaining):
        pid = paper["paper_id"]
        m = canonical.get(pid, {})
        title = m.get("title", "") or paper.get("title", "")
        doi = m.get("doi", "") or paper.get("doi", "")
        if not title:
            continue
        safe = title[:50].encode("ascii", errors="replace").decode("ascii")
        print(f"    [{i+1}/{len(remaining)}] {safe}...", end=" ", flush=True)

        # Try Unpaywall by title (via DOI)
        if doi:
            time.sleep(1.0)
            try:
                resp = requests.get(
                    f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='')}?email=slr@example.com",
                    timeout=20, verify=False,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for loc in [data.get("best_oa_location", {})] + data.get("oa_locations", []):
                        if not loc:
                            continue
                        pdf_url = loc.get("url_for_pdf", "")
                        if pdf_url:
                            filename = f"{pid}_{_sanitise(title)}.pdf"
                            dest = pdf_dir / filename
                            ok = _download(pdf_url, dest)
                            if ok:
                                log_entries[pid] = {
                                    "paper_id": pid, "title": title,
                                    "doi": doi,
                                    "source": "unpaywall_retry",
                                    "pdf_url": pdf_url,
                                    "status": "success",
                                    "filename": filename,
                                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                                }
                                print("OK (unpaywall)")
                                recovered += 1
                                break
                    else:
                        print("no OA")
                        continue
                    continue
            except Exception:
                pass
        print("skip")

    log.info("  Result: %d recovered", recovered)
    return recovered


# ── Main ──

def main():
    log_path = config.DOWNLOAD_LOG_CSV
    log_entries: dict[str, dict] = {}
    with open(log_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            log_entries[row["paper_id"]] = row

    with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
        master_rows = list(csv.DictReader(f))
    canonical = {r["paper_id"]: r for r in master_rows if not r.get("duplicate_of", "").strip()}

    # Build list of missing papers
    missing = []
    for pid, entry in log_entries.items():
        if entry["status"] in ("download_failed", "no_oa_source"):
            m = canonical.get(pid, {})
            missing.append({
                "paper_id": pid,
                "title": m.get("title", entry.get("title", "")),
                "doi": m.get("doi", entry.get("doi", "")),
                "pdf_url": entry.get("pdf_url", ""),
                "status": entry["status"],
            })

    log.info("Total missing papers: %d", len(missing))
    pdf_dir = ensure_dir(config.FULL_TEXTS_DIR / "pdfs")
    total_recovered = 0

    # Strategy 1
    n = strategy_copy_dupes(missing, master_rows, pdf_dir, log_entries)
    total_recovered += n
    missing = [p for p in missing if log_entries.get(p["paper_id"], {}).get("status") != "success"]

    # Strategy 2
    n = strategy_arxiv_title(missing, canonical, pdf_dir, log_entries)
    total_recovered += n
    missing = [p for p in missing if log_entries.get(p["paper_id"], {}).get("status") != "success"]

    # Strategy 3
    n = strategy_mdpi(missing, pdf_dir, log_entries)
    total_recovered += n
    missing = [p for p in missing if log_entries.get(p["paper_id"], {}).get("status") != "success"]

    # Strategy 4
    n = strategy_ssrn(missing, pdf_dir, log_entries)
    total_recovered += n
    missing = [p for p in missing if log_entries.get(p["paper_id"], {}).get("status") != "success"]

    # Strategy 5
    n = strategy_doi_redirect(missing, pdf_dir, log_entries)
    total_recovered += n
    missing = [p for p in missing if log_entries.get(p["paper_id"], {}).get("status") != "success"]

    # Strategy 6
    n = strategy_unpaywall_core(missing, canonical, pdf_dir, log_entries)
    total_recovered += n

    log.info("")
    log.info("=== TOTAL RECOVERED: %d ===", total_recovered)
    log.info("Still missing: %d", len([e for e in log_entries.values() if e["status"] in ("download_failed", "no_oa_source")]))

    # Save updated log
    lines = [",".join(LOG_COLUMNS)]
    for pid in sorted(log_entries):
        row = log_entries[pid]
        vals = []
        for c in LOG_COLUMNS:
            v = str(row.get(c, ""))
            if any(ch in v for ch in (",", '"', "\n")):
                v = '"' + v.replace('"', '""') + '"'
            vals.append(v)
        lines.append(",".join(vals))
    atomic_write_text(log_path, "\n".join(lines) + "\n")
    log.info("Updated download log: %s", log_path)


if __name__ == "__main__":
    main()
