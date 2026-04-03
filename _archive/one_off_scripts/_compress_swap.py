"""Compress PDFs > 0.8 MB and swap Zotero attachments (delete old → upload compressed).

Strategy: delete existing large attachment → upload compressed version.
Each swap frees net storage (compressed < original).
Processes largest files first for maximum early savings.
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
CHECKPOINT_PATH = ROOT / "08_full_texts" / "_compress_checkpoint.json"
MIN_SIZE_BYTES = int(0.8 * 1024 * 1024)  # 0.8 MB
WRITE_DELAY = 1.1  # Zotero write rate limit

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}


def _get_json(path: str, params: dict | None = None) -> list | dict:
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_attachments() -> list[dict]:
    """Fetch attachment items that have an uploaded file."""
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
                    "version": it.get("version", d.get("version")),
                })
        start += 100
        if start % 500 == 0:
            log.info("  Fetched %d attachments...", start)
    log.info("Total attachments with files: %d", len(items))
    return items


def compress_pdf(src: Path, dst: Path) -> bool:
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


def delete_attachment(key: str, version: int) -> bool:
    """Delete an attachment item from Zotero."""
    url = f"{BASE_URL}/items/{key}"
    hdrs = {**HEADERS, "If-Unmodified-Since-Version": str(version)}
    time.sleep(WRITE_DELAY)
    r = requests.delete(url, headers=hdrs, timeout=30)
    if r.status_code == 204:
        return True
    log.warning("Delete failed for %s: %d %s", key, r.status_code, r.text[:200])
    return False


def upload_new_attachment(parent_key: str, pdf_path: Path) -> bool:
    """Create new attachment and upload file (same as ZoteroWriter.upload_pdf)."""
    file_bytes = pdf_path.read_bytes()
    file_size = len(file_bytes)
    md5 = hashlib.md5(file_bytes).hexdigest()
    filename = pdf_path.name
    mtime = int(pdf_path.stat().st_mtime * 1000)

    # Step 1: Create attachment item
    attach_data = [{
        "itemType": "attachment",
        "parentItem": parent_key,
        "linkMode": "imported_file",
        "title": filename,
        "contentType": "application/pdf",
        "filename": filename,
        "tags": [],
    }]

    time.sleep(WRITE_DELAY)
    resp = requests.post(
        f"{BASE_URL}/items", headers={**HEADERS, "Content-Type": "application/json"},
        json=attach_data, timeout=30,
    )
    result = resp.json()
    successful = result.get("successful", result.get("success", {}))
    if "0" not in successful:
        log.warning("  Create attachment failed: %s", result.get("failed", {}))
        return False

    obj = successful["0"]
    attach_key = obj["key"] if isinstance(obj, dict) else obj

    # Step 2: Authorize upload
    url = f"{BASE_URL}/items/{attach_key}/file"
    auth_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-None-Match": "*",
    }
    auth_body = f"md5={md5}&filename={filename}&filesize={file_size}&mtime={mtime}"

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        auth_resp = requests.post(url, headers=auth_headers, data=auth_body, timeout=30)
        if auth_resp.status_code == 429:
            time.sleep(int(auth_resp.headers.get("Retry-After", 5)))
            continue
        if auth_resp.status_code == 200:
            break
        if auth_resp.status_code == 413:
            log.warning("  413 — storage quota full, aborting")
            # Clean up orphaned attachment
            _try_delete(attach_key)
            return False
        auth_resp.raise_for_status()
    else:
        _try_delete(attach_key)
        return False

    auth_data = auth_resp.json()

    if auth_data.get("exists"):
        log.info("  File already on server")
        return True

    # Step 3: S3 upload
    s3_url = auth_data["url"]
    s3_prefix = auth_data.get("prefix", "")
    s3_suffix = auth_data.get("suffix", "")
    s3_ct = auth_data.get("contentType", "application/pdf")
    upload_body = s3_prefix.encode("latin-1") + file_bytes + s3_suffix.encode("latin-1")

    for attempt in range(3):
        s3_resp = requests.post(s3_url, headers={"Content-Type": s3_ct}, data=upload_body, timeout=120)
        if s3_resp.status_code in (200, 201, 204):
            break
        if attempt < 2:
            time.sleep(5)
    else:
        log.warning("  S3 upload failed: %d", s3_resp.status_code)
        _try_delete(attach_key)
        return False

    # Step 4: Register
    upload_key = auth_data["uploadKey"]
    reg_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-None-Match": "*",
    }
    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        reg_resp = requests.post(url, headers=reg_headers, data=f"upload={upload_key}", timeout=30)
        if reg_resp.status_code == 429:
            time.sleep(int(reg_resp.headers.get("Retry-After", 5)))
            continue
        if reg_resp.status_code == 204:
            return True
        reg_resp.raise_for_status()

    _try_delete(attach_key)
    return False


def _try_delete(key: str):
    """Best-effort delete of an orphaned attachment."""
    try:
        r = requests.get(f"{BASE_URL}/items/{key}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            ver = r.json().get("version", 0)
            delete_attachment(key, ver)
    except Exception:
        pass


def load_checkpoint() -> set:
    if CHECKPOINT_PATH.exists():
        return set(json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8")))
    return set()


def save_checkpoint(done: set):
    CHECKPOINT_PATH.write_text(json.dumps(sorted(done)), encoding="utf-8")


def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID env vars")

    COMPRESSED_DIR.mkdir(exist_ok=True)

    # 1) Find local big PDFs
    local_big = {}
    for pdf in PDFS_DIR.glob("*.pdf"):
        if pdf.stat().st_size > MIN_SIZE_BYTES:
            local_big[pdf.name] = pdf

    log.info("Local PDFs > 0.8 MB: %d", len(local_big))

    # 2) Fetch Zotero attachments
    log.info("Fetching Zotero attachments...")
    attachments = fetch_all_attachments()
    zot_by_filename = {a["filename"]: a for a in attachments}

    # 3) Match
    to_process = []
    for fname, pdf_path in local_big.items():
        if fname in zot_by_filename:
            att = zot_by_filename[fname]
            to_process.append({
                "filename": fname,
                "local_path": pdf_path,
                "orig_bytes": pdf_path.stat().st_size,
                "attach_key": att["key"],
                "parent_key": att["parentItem"],
                "old_md5": att["md5"],
                "version": att["version"],
            })

    to_process.sort(key=lambda x: x["orig_bytes"], reverse=True)
    log.info("Matched for swap: %d", len(to_process))

    # 4) Load checkpoint (resume support)
    done = load_checkpoint()
    remaining = [t for t in to_process if t["filename"] not in done]
    log.info("Already done: %d, remaining: %d", len(done), len(remaining))

    results = {"replaced": [], "skipped_no_savings": [], "compress_failed": [],
               "delete_failed": [], "upload_failed": []}
    total_saved = 0

    for i, item in enumerate(remaining, 1):
        fname = item["filename"]
        src = item["local_path"]
        orig_mb = item["orig_bytes"] / (1024 * 1024)
        dst = COMPRESSED_DIR / fname

        log.info("[%d/%d] %s (%.1f MB)", i, len(remaining), fname[:55], orig_mb)

        # Compress
        if not compress_pdf(src, dst):
            results["compress_failed"].append(fname)
            done.add(fname)
            save_checkpoint(done)
            continue

        new_bytes = dst.stat().st_size
        new_mb = new_bytes / (1024 * 1024)
        savings = item["orig_bytes"] - new_bytes

        if savings < 50_000:  # < 50 KB savings
            log.info("  Skip: %.1f→%.1f MB (%.0fKB saved)", orig_mb, new_mb, savings / 1024)
            results["skipped_no_savings"].append(fname)
            dst.unlink(missing_ok=True)
            done.add(fname)
            save_checkpoint(done)
            continue

        log.info("  Compressed: %.1f→%.1f MB (%.0f%% / %.1f MB saved)",
                 orig_mb, new_mb, savings / item["orig_bytes"] * 100, savings / (1024 * 1024))

        # Delete old attachment
        if not delete_attachment(item["attach_key"], item["version"]):
            results["delete_failed"].append(fname)
            dst.unlink(missing_ok=True)
            done.add(fname)
            save_checkpoint(done)
            continue

        log.info("  Deleted old attachment %s", item["attach_key"])
        time.sleep(2)  # give server a moment to free storage

        # Upload compressed
        if upload_new_attachment(item["parent_key"], dst):
            total_saved += savings
            results["replaced"].append({
                "filename": fname,
                "orig_mb": round(orig_mb, 2),
                "new_mb": round(new_mb, 2),
                "saved_mb": round(savings / (1024 * 1024), 2),
            })
            log.info("  ✓ Replaced (saved %.1f MB, cumulative: %.0f MB)",
                     savings / (1024 * 1024), total_saved / (1024 * 1024))
            # Replace local file with compressed version
            dst.replace(src)
        else:
            results["upload_failed"].append(fname)
            log.warning("  ✗ Upload failed — attachment deleted but not replaced!")
            dst.unlink(missing_ok=True)

        done.add(fname)
        save_checkpoint(done)

    # 5) Summary
    log.info("=" * 60)
    log.info("DONE: %d replaced, %d skipped, %d compress-fail, %d delete-fail, %d upload-fail",
             len(results["replaced"]), len(results["skipped_no_savings"]),
             len(results["compress_failed"]), len(results["delete_failed"]),
             len(results["upload_failed"]))
    log.info("Total storage saved: %.1f MB", total_saved / (1024 * 1024))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    log.info("Report: %s", REPORT_PATH)


if __name__ == "__main__":
    main()
