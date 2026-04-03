"""Targeted recovery of failed/missing PDFs via Semantic Scholar title search.

For papers that the main cascade couldn't find (no arXiv DOI, paywalled OA URL),
this does a S2 title search to discover arXiv preprint versions.
"""

import csv
import json
import logging
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

from tools.slr_toolkit import config
from tools.slr_toolkit.utils import atomic_write_text, ensure_dir

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

_ARXIV_PDF_BASE = "https://arxiv.org/pdf/"
_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_PAPER = "https://api.semanticscholar.org/graph/v1/paper"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DELAY = 3.5  # S2 free-tier


def _s2_find_arxiv(title: str, doi: str = "") -> str | None:
    """Search Semantic Scholar for arXiv version of a paper."""
    headers = {"User-Agent": "QuantumFinanceSLR/0.1 (recovery)"}
    fields = "externalIds,openAccessPdf,title"

    # Try DOI first
    if doi:
        url = f"{_S2_PAPER}/DOI:{urllib.parse.quote(doi, safe='')}?fields={fields}"
        time.sleep(DELAY)
        try:
            resp = requests.get(url, headers=headers, timeout=30, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                ext = data.get("externalIds") or {}
                arxiv_id = ext.get("ArXiv")
                if arxiv_id:
                    return f"{_ARXIV_PDF_BASE}{arxiv_id}.pdf"
                oa = data.get("openAccessPdf") or {}
                if oa.get("url"):
                    return oa["url"]
        except Exception as e:
            log.debug("S2 DOI lookup failed: %s", e)

    # Title search
    if title:
        params = urllib.parse.urlencode({
            "query": title[:200],
            "limit": "3",
            "fields": fields,
        })
        url = f"{_S2_SEARCH}?{params}"
        time.sleep(DELAY)
        try:
            resp = requests.get(url, headers=headers, timeout=30, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get("data", []):
                    # Verify title similarity
                    r_title = (result.get("title") or "").lower().strip()
                    q_title = title.lower().strip()
                    if _title_match(q_title, r_title):
                        ext = result.get("externalIds") or {}
                        arxiv_id = ext.get("ArXiv")
                        if arxiv_id:
                            return f"{_ARXIV_PDF_BASE}{arxiv_id}.pdf"
                        oa = result.get("openAccessPdf") or {}
                        if oa.get("url"):
                            return oa["url"]
        except Exception as e:
            log.debug("S2 title search failed: %s", e)

    return None


def _title_match(a: str, b: str) -> bool:
    """Check if two titles are similar enough to be the same paper."""
    def norm(t):
        return re.sub(r"[^a-z0-9]", "", t.lower())
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    # Check if one is a prefix of the other (truncated titles)
    shorter = min(len(na), len(nb))
    return na[:shorter] == nb[:shorter] and shorter > 30


def _download_pdf(url: str, dest: Path) -> bool:
    """Download PDF with validation."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _BROWSER_UA, "Accept": "application/pdf, */*"},
            timeout=60, allow_redirects=True, verify=False,
        )
        if resp.status_code == 403:
            resp = requests.get(
                url,
                headers={"User-Agent": _BROWSER_UA},
                timeout=60, allow_redirects=True, verify=False,
            )
        resp.raise_for_status()
        if not resp.content[:5].startswith(b"%PDF"):
            return False
        ensure_dir(dest.parent)
        dest.write_bytes(resp.content)
        return True
    except Exception:
        return False


def _sanitise(title: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "_", title.lower().strip()).strip("_")
    return t[:80]


def main():
    # Load download log
    log_path = config.DOWNLOAD_LOG_CSV
    log_entries: dict[str, dict] = {}
    with open(log_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            log_entries[row["paper_id"]] = row

    # Load master records
    with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
        master = list(csv.DictReader(f))
    canonical = {r["paper_id"]: r for r in master if not r.get("duplicate_of", "").strip()}

    # Find papers to recover: download_failed + no_oa_source
    to_recover = []
    for pid, entry in log_entries.items():
        if entry["status"] in ("download_failed", "no_oa_source"):
            m = canonical.get(pid, {})
            to_recover.append({
                "paper_id": pid,
                "title": m.get("title", entry.get("title", "")),
                "doi": m.get("doi", entry.get("doi", "")),
            })

    log.info("Found %d papers to attempt recovery (failed + no_oa)", len(to_recover))

    pdf_dir = ensure_dir(config.FULL_TEXTS_DIR / "pdfs")
    recovered = 0
    still_failed = 0

    for i, paper in enumerate(to_recover, 1):
        pid = paper["paper_id"]
        title = paper["title"] or pid
        safe_title = title[:55].encode("ascii", errors="replace").decode("ascii")
        print(f"  [{i}/{len(to_recover)}] {safe_title}...", end=" ", flush=True)

        pdf_url = _s2_find_arxiv(title, paper.get("doi", ""))

        if not pdf_url:
            print("no alt source")
            still_failed += 1
            continue

        filename = f"{pid}_{_sanitise(title)}.pdf"
        dest = pdf_dir / filename

        if dest.exists():
            print("already on disk!")
            log_entries[pid] = {
                "paper_id": pid, "title": title,
                "doi": paper.get("doi", ""),
                "source": "recovery_cached", "pdf_url": pdf_url,
                "status": "success", "filename": filename,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            recovered += 1
            continue

        ok = _download_pdf(pdf_url, dest)
        if ok:
            print(f"OK ({pdf_url[:50]}...)")
            log_entries[pid] = {
                "paper_id": pid, "title": title,
                "doi": paper.get("doi", ""),
                "source": "recovery_s2", "pdf_url": pdf_url,
                "status": "success", "filename": filename,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            recovered += 1
        else:
            print(f"download failed ({pdf_url[:50]}...)")
            still_failed += 1

    log.info("")
    log.info("Recovery complete: %d recovered, %d still missing", recovered, still_failed)

    # Save updated log
    cols = ["paper_id", "title", "doi", "source", "pdf_url", "status", "filename", "timestamp"]
    lines = [",".join(cols)]
    for pid in sorted(log_entries):
        row = log_entries[pid]
        vals = []
        for c in cols:
            v = str(row.get(c, ""))
            if any(ch in v for ch in (",", '"', "\n")):
                v = '"' + v.replace('"', '""') + '"'
            vals.append(v)
        lines.append(",".join(vals))
    atomic_write_text(log_path, "\n".join(lines) + "\n")
    log.info("Updated download log: %s", log_path)


if __name__ == "__main__":
    main()
