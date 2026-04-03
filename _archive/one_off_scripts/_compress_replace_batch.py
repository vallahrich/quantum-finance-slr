"""Batch compress large PDFs and replace them on Zotero.

Strategy (respects 2 GB quota):
  Phase 1 – Inventory: fetch all Zotero attachments, match to local PDFs > 0.8 MB.
  Phase 2 – Delete:    batch-delete the Zotero attachment items to free storage.
  Phase 3 – Compress:  shrink local PDFs with pikepdf.
  Phase 4 – Upload:    re-upload compressed PDFs as new attachments.
"""

import csv
import hashlib
import json
import logging
import os
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
REPORT_PATH = ROOT / "08_full_texts" / "_compress_replace_report.json"

SIZE_THRESHOLD = 0.8 * 1024 * 1024  # 0.8 MB in bytes

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY}
WRITE_DELAY = 1.1  # seconds between write calls


# ── helpers ──────────────────────────────────────────────────────────────
def _pid_from_filename(fn: str) -> str | None:
    """Extract paper_id (12-char hex prefix) from attachment filename."""
    if "_" in fn and len(fn.split("_")[0]) == 12:
        return fn.split("_")[0]
    return None


def _zotero_get(endpoint: str, params: dict | None = None):
    """GET with automatic pagination."""
    results = []
    params = params or {}
    params.setdefault("limit", 100)
    params.setdefault("start", 0)
    while True:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS,
                         params=params, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        results.extend(batch)
        total = int(r.headers.get("Total-Results", 0))
        params["start"] += len(batch)
        if params["start"] >= total:
            break
    return results


def _zotero_delete(keys: list[str], last_version: int) -> int:
    """Batch-delete up to 50 items. Returns new library version."""
    chunk = keys[:50]
    h = {**HEADERS, "If-Unmodified-Since-Version": str(last_version)}
    time.sleep(WRITE_DELAY)
    r = requests.delete(
        f"{BASE_URL}/items",
        headers=h,
        params={"itemKey": ",".join(chunk)},
        timeout=60,
    )
    r.raise_for_status()
    return int(r.headers.get("Last-Modified-Version", last_version))


def compress_pdf(src: Path, dst: Path) -> bool:
    """Rewrite PDF with pikepdf for smaller file size."""
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


def upload_pdf(parent_key: str, pdf_path: Path) -> bool:
    """Upload a PDF as a child attachment (3-step Zotero file upload)."""
    file_bytes = pdf_path.read_bytes()
    file_size = len(file_bytes)
    md5 = hashlib.md5(file_bytes).hexdigest()
    filename = pdf_path.name
    mtime = int(pdf_path.stat().st_mtime * 1000)

    # Step 1: create attachment item
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
        f"{BASE_URL}/items",
        headers={**HEADERS, "Content-Type": "application/json"},
        json=attach_data,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    successful = result.get("successful", result.get("success", {}))
    if "0" not in successful:
        log.warning("  Create attachment failed: %s", result.get("failed", {}))
        return False
    obj = successful["0"]
    attach_key = obj["key"] if isinstance(obj, dict) else obj

    # Step 2: authorize upload
    url = f"{BASE_URL}/items/{attach_key}/file"
    auth_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "If-None-Match": "*",
    }
    auth_body = f"md5={md5}&filename={filename}&filesize={file_size}&mtime={mtime}"
    time.sleep(WRITE_DELAY)
    auth_resp = requests.post(url, headers=auth_headers, data=auth_body, timeout=30)
    if auth_resp.status_code != 200:
        log.warning("  Auth failed (%d): %s", auth_resp.status_code, auth_resp.text[:200])
        return False
    auth_data = auth_resp.json()

    if auth_data.get("exists"):
        log.info("  File already on server (deduped): %s", filename)
        return True

    # Step 3: upload to S3
    s3_url = auth_data["url"]
    s3_prefix = auth_data.get("prefix", "")
    s3_suffix = auth_data.get("suffix", "")
    s3_ct = auth_data.get("contentType", "application/pdf")
    upload_body = s3_prefix.encode("latin-1") + file_bytes + s3_suffix.encode("latin-1")

    s3_resp = requests.post(s3_url, headers={"Content-Type": s3_ct},
                            data=upload_body, timeout=120)
    if s3_resp.status_code not in (200, 201, 204):
        log.warning("  S3 upload failed (%d)", s3_resp.status_code)
        return False

    # Step 4: register
    upload_key = auth_data["uploadKey"]
    reg_headers = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                   "If-None-Match": "*"}
    time.sleep(WRITE_DELAY)
    reg_resp = requests.post(url, headers=reg_headers,
                             data=f"upload={upload_key}", timeout=30)
    if reg_resp.status_code == 204:
        return True
    log.warning("  Register failed (%d): %s", reg_resp.status_code, reg_resp.text[:200])
    return False


# ── main pipeline ────────────────────────────────────────────────────────
def main():
    if not API_KEY or not GROUP_ID:
        raise SystemExit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID env vars")

    COMPRESSED_DIR.mkdir(exist_ok=True)

    # ── Phase 1: Inventory ───────────────────────────────────────────────
    log.info("Phase 1: building inventory...")

    # Build map of local large PDFs: paper_id → Path
    large_local: dict[str, Path] = {}
    for pdf in PDFS_DIR.glob("*.pdf"):
        if pdf.stat().st_size > SIZE_THRESHOLD:
            pid = _pid_from_filename(pdf.name)
            if pid:
                large_local[pid] = pdf

    log.info("Local PDFs > %.1f MB: %d", SIZE_THRESHOLD / (1024 * 1024), len(large_local))

    # Fetch all Zotero attachments
    attachments = _zotero_get("/items", {"itemType": "attachment", "format": "json"})
    log.info("Zotero attachments fetched: %d", len(attachments))

    # Match: find attachments whose filename maps to a large local PDF
    to_replace: list[dict] = []  # { pid, attach_key, parent_key, local_path, version }
    for att in attachments:
        d = att["data"]
        if d.get("contentType") != "application/pdf" or not d.get("md5"):
            continue
        pid = _pid_from_filename(d.get("filename", ""))
        if pid and pid in large_local:
            to_replace.append({
                "pid": pid,
                "attach_key": d["key"],
                "parent_key": d["parentItem"],
                "local_path": str(large_local[pid]),
                "version": d["version"],
            })

    log.info("Attachments to replace: %d", len(to_replace))
    if not to_replace:
        log.info("Nothing to do!")
        return

    original_bytes = sum(Path(r["local_path"]).stat().st_size for r in to_replace)
    log.info("Original total size: %.1f MB", original_bytes / (1024 * 1024))

    # ── Phase 2: Compress locally ────────────────────────────────────────
    log.info("Phase 2: compressing PDFs...")
    compressed_map: dict[str, Path] = {}  # pid → compressed path
    saved_bytes = 0

    for i, item in enumerate(to_replace, 1):
        src = Path(item["local_path"])
        dst = COMPRESSED_DIR / src.name
        src_size = src.stat().st_size
        log.info("  [%d/%d] %s (%.1f MB)...", i, len(to_replace), src.name[:50], src_size / (1024 * 1024))

        if compress_pdf(src, dst):
            dst_size = dst.stat().st_size
            if dst_size < src_size:
                saved = src_size - dst_size
                saved_bytes += saved
                compressed_map[item["pid"]] = dst
                log.info("    -> %.1f MB (saved %.1f MB, %.0f%%)",
                         dst_size / (1024 * 1024), saved / (1024 * 1024),
                         (saved / src_size) * 100)
            else:
                log.info("    -> no savings, keeping original")
                compressed_map[item["pid"]] = src
        else:
            compressed_map[item["pid"]] = src

    log.info("Compression complete. Total savings: %.1f MB", saved_bytes / (1024 * 1024))

    # ── Phase 3: Delete old attachments from Zotero ──────────────────────
    log.info("Phase 3: deleting %d old attachments from Zotero...", len(to_replace))

    # Get current library version
    r = requests.get(f"{BASE_URL}/items", headers=HEADERS,
                     params={"limit": 1, "format": "json"}, timeout=30)
    lib_version = int(r.headers.get("Last-Modified-Version", 0))

    keys_to_delete = [item["attach_key"] for item in to_replace]
    deleted = 0
    for start in range(0, len(keys_to_delete), 50):
        chunk = keys_to_delete[start:start + 50]
        try:
            lib_version = _zotero_delete(chunk, lib_version)
            deleted += len(chunk)
            log.info("  Deleted %d/%d", deleted, len(keys_to_delete))
        except requests.HTTPError as e:
            log.error("  Delete batch failed: %s", e)
            break

    log.info("Deleted %d attachments", deleted)

    # Wait a moment for storage to be freed
    log.info("Waiting 5s for storage to synchronize...")
    time.sleep(5)

    # ── Phase 4: Upload compressed PDFs ──────────────────────────────────
    log.info("Phase 4: uploading %d compressed PDFs...", len(to_replace))
    success = 0
    failed = 0
    fail_list = []

    for i, item in enumerate(to_replace, 1):
        pid = item["pid"]
        parent_key = item["parent_key"]
        pdf_path = compressed_map.get(pid, Path(item["local_path"]))
        size_mb = pdf_path.stat().st_size / (1024 * 1024)

        log.info("  [%d/%d] %s (%.1f MB) → %s", i, len(to_replace), pid, size_mb, parent_key)
        try:
            if upload_pdf(parent_key, pdf_path):
                success += 1
            else:
                failed += 1
                fail_list.append(pid)
        except Exception as e:
            failed += 1
            fail_list.append(pid)
            log.warning("    Error: %s", str(e)[:120])

        # Progress checkpoint every 50
        if i % 50 == 0:
            log.info("  Progress: %d ok, %d failed out of %d", success, failed, i)

    # ── Phase 5: Replace originals with compressed versions ──────────────
    replaced_on_disk = 0
    for pid, comp_path in compressed_map.items():
        if comp_path.parent == COMPRESSED_DIR:
            orig = large_local[pid]
            if comp_path.stat().st_size < orig.stat().st_size:
                import shutil
                shutil.copy2(comp_path, orig)
                replaced_on_disk += 1

    # ── Report ───────────────────────────────────────────────────────────
    new_bytes = sum(Path(r["local_path"]).stat().st_size for r in to_replace)
    report = {
        "total_candidates": len(to_replace),
        "deleted_from_zotero": deleted,
        "uploaded_compressed": success,
        "upload_failed": failed,
        "failed_pids": fail_list,
        "original_total_mb": round(original_bytes / (1024 * 1024), 1),
        "compressed_total_mb": round(new_bytes / (1024 * 1024), 1),
        "savings_mb": round(saved_bytes / (1024 * 1024), 1),
        "replaced_on_disk": replaced_on_disk,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Report saved to %s", REPORT_PATH.name)

    log.info("=" * 60)
    log.info("DONE: %d deleted, %d uploaded, %d failed", deleted, success, failed)
    log.info("Space saved: %.1f MB", saved_bytes / (1024 * 1024))
    if fail_list:
        log.info("Failed PIDs: %s", ", ".join(fail_list[:10]))


if __name__ == "__main__":
    main()
