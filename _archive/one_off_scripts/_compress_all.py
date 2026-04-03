"""Compress ALL PDFs and replace existing Zotero attachments with smaller versions.

Uses If-Match: <old_md5> for in-place file replacement (frees storage immediately).
Has checkpoint support so it can be interrupted and resumed.
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
CHECKPOINT_PATH = ROOT / "08_full_texts" / "_compress_checkpoint.json"
REPORT_PATH = ROOT / "08_full_texts" / "compression_report.json"
WRITE_DELAY = 1.1

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}


def _get_json(path: str, params: dict | None = None) -> list | dict:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_attachments() -> dict[str, dict]:
    """Fetch every attachment item with an uploaded file. Returns {filename: info}."""
    result = {}
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
                result[d.get("filename", "")] = {
                    "key": d["key"],
                    "md5": d["md5"],
                }
        start += 100
    log.info("Zotero attachments with files: %d", len(result))
    return result


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


def replace_file(attach_key: str, old_md5: str, pdf_path: Path) -> bool:
    """Replace file on existing Zotero attachment using If-Match."""
    file_bytes = pdf_path.read_bytes()
    file_size = len(file_bytes)
    new_md5 = hashlib.md5(file_bytes).hexdigest()
    filename = pdf_path.name
    mtime = int(pdf_path.stat().st_mtime * 1000)

    url = f"{BASE_URL}/items/{attach_key}/file"

    # Step 1: Authorize replacement
    auth_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-Match": old_md5,
    }
    auth_body = f"md5={new_md5}&filename={filename}&filesize={file_size}&mtime={mtime}"

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            auth_resp = requests.post(url, headers=auth_headers, data=auth_body, timeout=30)
        except requests.exceptions.Timeout:
            log.warning("  Auth timeout (attempt %d)", attempt + 1)
            continue
        if auth_resp.status_code == 429:
            time.sleep(int(auth_resp.headers.get("Retry-After", 5)))
            continue
        if auth_resp.status_code == 412:
            log.warning("  Precondition failed (md5 mismatch) for %s", attach_key)
            return False
        if auth_resp.status_code == 413:
            log.warning("  413 Too Large for %s", attach_key)
            return False
        if auth_resp.status_code == 200:
            break
        log.warning("  Auth returned %d: %s", auth_resp.status_code, auth_resp.text[:200])
        return False
    else:
        return False

    auth_data = auth_resp.json()

    if auth_data.get("exists"):
        return True  # already same file

    # Step 2: Upload to S3
    s3_url = auth_data["url"]
    s3_prefix = auth_data.get("prefix", "")
    s3_suffix = auth_data.get("suffix", "")
    s3_ct = auth_data.get("contentType", "application/pdf")
    upload_body = s3_prefix.encode("latin-1") + file_bytes + s3_suffix.encode("latin-1")

    for attempt in range(3):
        try:
            s3_resp = requests.post(s3_url, headers={"Content-Type": s3_ct},
                                     data=upload_body, timeout=180)
            if s3_resp.status_code in (200, 201, 204):
                break
        except requests.exceptions.Timeout:
            log.warning("  S3 timeout (attempt %d)", attempt + 1)
        if attempt < 2:
            time.sleep(5)
    else:
        log.warning("  S3 upload failed for %s", attach_key)
        return False

    # Step 3: Register upload
    upload_key = auth_data["uploadKey"]
    reg_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-Match": old_md5,
    }

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            reg_resp = requests.post(url, headers=reg_headers,
                                      data=f"upload={upload_key}", timeout=30)
        except requests.exceptions.Timeout:
            continue
        if reg_resp.status_code == 429:
            time.sleep(int(reg_resp.headers.get("Retry-After", 5)))
            continue
        if reg_resp.status_code == 204:
            return True
        log.warning("  Register returned %d: %s", reg_resp.status_code, reg_resp.text[:200])
        return False

    return False


def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {"done": [], "replaced": [], "skipped": [], "failed": [], "bytes_saved": 0}


def save_checkpoint(ckpt: dict):
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, indent=2))


def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID env vars")

    COMPRESSED_DIR.mkdir(exist_ok=True)
    ckpt = load_checkpoint()
    done_set = set(ckpt["done"])

    # 1) All local PDFs
    all_pdfs = sorted(PDFS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_size, reverse=True)
    log.info("Total local PDFs: %d", len(all_pdfs))
    log.info("Already processed: %d", len(done_set))

    # 2) Fetch Zotero attachment index
    log.info("Fetching Zotero attachments...")
    zot_idx = fetch_all_attachments()

    # 3) Build work list: PDFs not yet processed that have a Zotero attachment
    work = []
    no_zotero = 0
    for pdf in all_pdfs:
        if pdf.name in done_set:
            continue
        if pdf.name in zot_idx:
            work.append(pdf)
        else:
            no_zotero += 1

    log.info("To process: %d  |  No Zotero attachment: %d  |  Already done: %d",
             len(work), no_zotero, len(done_set))

    if not work:
        log.info("Nothing to process!")
        return

    # 4) Compress and replace
    for i, pdf in enumerate(work, 1):
        fname = pdf.name
        orig_bytes = pdf.stat().st_size
        orig_mb = orig_bytes / (1024 * 1024)
        att = zot_idx[fname]
        dst = COMPRESSED_DIR / fname

        log.info("[%d/%d] %s (%.2f MB)", i, len(work), fname[:60], orig_mb)

        # Compress
        if not compress_pdf(pdf, dst):
            ckpt["done"].append(fname)
            ckpt["failed"].append(fname)
            save_checkpoint(ckpt)
            continue

        new_bytes = dst.stat().st_size
        new_mb = new_bytes / (1024 * 1024)
        savings = orig_bytes - new_bytes

        if savings < 10_000:  # less than 10 KB savings
            log.info("  Skip: %.2f → %.2f MB (%.0f B saved)", orig_mb, new_mb, savings)
            ckpt["done"].append(fname)
            ckpt["skipped"].append(fname)
            dst.unlink(missing_ok=True)
            save_checkpoint(ckpt)
            continue

        log.info("  Compressed: %.2f → %.2f MB (%.0f%% reduction, %.1f MB saved)",
                 orig_mb, new_mb, savings / orig_bytes * 100, savings / (1024 * 1024))

        # Upload replacement
        if replace_file(att["key"], att["md5"], dst):
            ckpt["bytes_saved"] += savings
            ckpt["replaced"].append(fname)
            log.info("  ✓ Replaced on Zotero")
            # Replace local copy too
            dst.replace(pdf)
        else:
            ckpt["failed"].append(fname)
            log.warning("  ✗ Upload failed — keeping original")
            dst.unlink(missing_ok=True)

        ckpt["done"].append(fname)
        save_checkpoint(ckpt)

    # 5) Summary
    total_saved_mb = ckpt["bytes_saved"] / (1024 * 1024)
    log.info("=" * 60)
    log.info("COMPLETE: %d replaced, %d skipped, %d failed",
             len(ckpt["replaced"]), len(ckpt["skipped"]), len(ckpt["failed"]))
    log.info("Total storage saved: %.1f MB", total_saved_mb)

    # Save final report
    with open(REPORT_PATH, "w") as f:
        json.dump({
            "replaced": len(ckpt["replaced"]),
            "skipped": len(ckpt["skipped"]),
            "failed": len(ckpt["failed"]),
            "bytes_saved": ckpt["bytes_saved"],
            "mb_saved": round(total_saved_mb, 1),
        }, f, indent=2)


if __name__ == "__main__":
    main()
