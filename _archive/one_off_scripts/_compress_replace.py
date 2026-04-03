"""Compress PDFs > 0.8 MB and replace existing Zotero attachments with smaller versions.

This replaces files in-place on existing attachment items (If-Match: old_md5),
which frees storage rather than consuming more.
"""
import csv
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import pikepdf
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
PDFS_DIR = ROOT / "08_full_texts" / "pdfs"
COMPRESSED_DIR = ROOT / "08_full_texts" / "_compressed"
REPORT_PATH = ROOT / "08_full_texts" / "compression_report.json"
MIN_SIZE_BYTES = int(0.8 * 1024 * 1024)  # 0.8 MB
WRITE_DELAY = 1.1  # Zotero write rate limit

# ── Zotero helpers ──────────────────────────────────────────────────

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}


def _get_json(path: str, params: dict | None = None) -> list | dict:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_attachments() -> list[dict]:
    """Fetch every attachment item that has an uploaded file (md5 set)."""
    items = []
    start = 0
    while True:
        batch = _get_json("/items", {
            "itemType": "attachment",
            "start": start,
            "limit": 100,
            "format": "json",
        })
        if not batch:
            break
        for it in batch:
            d = it["data"]
            if d.get("md5") and d.get("contentType") == "application/pdf":
                items.append({
                    "key": d["key"],
                    "parentItem": d.get("parentItem"),
                    "filename": d.get("filename", ""),
                    "md5": d["md5"],
                })
        start += 100
        log.info("  Fetched %d attachments so far...", start)
    log.info("Total attachments with files: %d", len(items))
    return items


# ── Compression ─────────────────────────────────────────────────────

def compress_pdf(src: Path, dst: Path) -> bool:
    """Rewrite PDF with pikepdf to reduce size."""
    try:
        with pikepdf.open(src) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(
                dst,
                linearize=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                compress_streams=True,
                recompress_flate=True,
            )
        return True
    except Exception as e:
        log.warning("Compression failed for %s: %s", src.name, e)
        return False


# ── File replacement upload ─────────────────────────────────────────

def replace_file(attach_key: str, old_md5: str, pdf_path: Path) -> bool:
    """Replace the file on an existing Zotero attachment item.

    Uses If-Match: <old_md5> to do an in-place replacement.
    """
    file_bytes = pdf_path.read_bytes()
    file_size = len(file_bytes)
    new_md5 = hashlib.md5(file_bytes).hexdigest()
    filename = pdf_path.name
    mtime = int(pdf_path.stat().st_mtime * 1000)

    url = f"{BASE_URL}/items/{attach_key}/file"

    # Step 1: Authorize upload (replace mode: If-Match instead of If-None-Match)
    auth_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-Match": old_md5,
    }
    auth_body = f"md5={new_md5}&filename={filename}&filesize={file_size}&mtime={mtime}"

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        auth_resp = requests.post(url, headers=auth_headers, data=auth_body, timeout=30)
        if auth_resp.status_code == 429:
            time.sleep(int(auth_resp.headers.get("Retry-After", 5)))
            continue
        if auth_resp.status_code == 200:
            break
        if auth_resp.status_code == 412:
            log.warning("Precondition failed for %s — md5 mismatch, skip", attach_key)
            return False
        auth_resp.raise_for_status()
    else:
        log.warning("Auth failed after 3 retries for %s", attach_key)
        return False

    auth_data = auth_resp.json()

    if auth_data.get("exists"):
        log.info("  File already matches on server: %s", filename)
        return True

    # Step 2: Upload to S3
    s3_url = auth_data["url"]
    s3_prefix = auth_data.get("prefix", "")
    s3_suffix = auth_data.get("suffix", "")
    s3_content_type = auth_data.get("contentType", "application/pdf")

    upload_body = s3_prefix.encode("latin-1") + file_bytes + s3_suffix.encode("latin-1")

    for attempt in range(3):
        s3_resp = requests.post(
            s3_url,
            headers={"Content-Type": s3_content_type},
            data=upload_body,
            timeout=120,
        )
        if s3_resp.status_code in (200, 201, 204):
            break
        if attempt < 2:
            time.sleep(5)
    else:
        log.warning("S3 upload failed for %s: %d", attach_key, s3_resp.status_code)
        return False

    # Step 3: Register upload
    upload_key = auth_data["uploadKey"]
    reg_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-Match": old_md5,
    }
    reg_body = f"upload={upload_key}"

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        reg_resp = requests.post(url, headers=reg_headers, data=reg_body, timeout=30)
        if reg_resp.status_code == 429:
            time.sleep(int(reg_resp.headers.get("Retry-After", 5)))
            continue
        if reg_resp.status_code == 204:
            return True
        reg_resp.raise_for_status()

    log.warning("Registration failed for %s", attach_key)
    return False


# ── Main ────────────────────────────────────────────────────────────

def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID env vars")

    COMPRESSED_DIR.mkdir(exist_ok=True)

    # 1) Find local PDFs > 0.8 MB
    local_big = {}
    for pdf in PDFS_DIR.glob("*.pdf"):
        if pdf.stat().st_size > MIN_SIZE_BYTES:
            # paper_id is the prefix before the first underscore
            pid = pdf.name.split("_")[0]
            local_big[pdf.name] = {"path": pdf, "pid": pid, "orig_bytes": pdf.stat().st_size}

    log.info("Local PDFs > 0.8 MB: %d", len(local_big))

    # 2) Fetch Zotero attachments
    log.info("Fetching Zotero attachment items...")
    attachments = fetch_all_attachments()

    # Build filename → attachment map
    zot_by_filename: dict[str, dict] = {}
    for att in attachments:
        zot_by_filename[att["filename"]] = att

    # 3) Match: local big PDFs that have a Zotero attachment with a file
    to_process = []
    for fname, info in local_big.items():
        if fname in zot_by_filename:
            att = zot_by_filename[fname]
            to_process.append({
                "filename": fname,
                "local_path": info["path"],
                "orig_bytes": info["orig_bytes"],
                "attach_key": att["key"],
                "old_md5": att["md5"],
            })

    log.info("Matched for replacement: %d (of %d big, %d on Zotero)",
             len(to_process), len(local_big), len(attachments))

    if not to_process:
        log.info("Nothing to process!")
        return

    # Sort largest first for maximum space savings
    to_process.sort(key=lambda x: x["orig_bytes"], reverse=True)

    # 4) Compress and upload
    results = {"replaced": [], "skipped_no_savings": [], "compress_failed": [], "upload_failed": []}
    total_saved = 0

    for i, item in enumerate(to_process, 1):
        fname = item["filename"]
        src = item["local_path"]
        orig_mb = item["orig_bytes"] / (1024 * 1024)
        dst = COMPRESSED_DIR / fname

        log.info("[%d/%d] Compressing %s (%.1f MB)...", i, len(to_process), fname[:60], orig_mb)

        if not compress_pdf(src, dst):
            results["compress_failed"].append(fname)
            continue

        new_bytes = dst.stat().st_size
        new_mb = new_bytes / (1024 * 1024)
        savings = item["orig_bytes"] - new_bytes
        savings_pct = savings / item["orig_bytes"] * 100

        if savings < 50_000:  # less than 50 KB savings — not worth it
            log.info("  Skipping: %.1f MB → %.1f MB (only %.0f KB saved)", orig_mb, new_mb, savings / 1024)
            results["skipped_no_savings"].append(fname)
            dst.unlink(missing_ok=True)
            continue

        log.info("  Compressed: %.1f MB → %.1f MB (%.0f%% reduction)", orig_mb, new_mb, savings_pct)

        # Upload replacement
        if replace_file(item["attach_key"], item["old_md5"], dst):
            total_saved += savings
            results["replaced"].append({
                "filename": fname,
                "orig_mb": round(orig_mb, 2),
                "new_mb": round(new_mb, 2),
                "saved_mb": round(savings / (1024 * 1024), 2),
            })
            log.info("  ✓ Replaced on Zotero (saved %.1f MB)", savings / (1024 * 1024))
            # Also replace local copy with compressed version
            dst.replace(src)
        else:
            results["upload_failed"].append(fname)
            log.warning("  ✗ Upload failed")

        # Clean up compressed file if still there
        dst.unlink(missing_ok=True)

    # 5) Summary
    log.info("=" * 60)
    log.info("DONE: %d replaced, %d skipped (no savings), %d compress fail, %d upload fail",
             len(results["replaced"]), len(results["skipped_no_savings"]),
             len(results["compress_failed"]), len(results["upload_failed"]))
    log.info("Total storage saved: %.1f MB", total_saved / (1024 * 1024))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    log.info("Report saved to %s", REPORT_PATH)


if __name__ == "__main__":
    main()
