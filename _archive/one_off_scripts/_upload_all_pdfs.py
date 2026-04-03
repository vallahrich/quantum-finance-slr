"""Compress ALL local PDFs and ensure every one is uploaded to Zotero.

Three categories:
1. Already uploaded with file → compress locally, replace on Zotero (If-Match)
2. Has orphaned attachment (no file) → upload file to existing attachment
3. No attachment at all → find parent item, create new attachment + upload

Checkpoint support for safe interruption/resume.
"""
import csv
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import pikepdf
from pikepdf import PdfImage
from PIL import Image
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
PDFS_DIR = ROOT / "08_full_texts" / "pdfs"
COMPRESSED_DIR = ROOT / "08_full_texts" / "_compressed"
CHECKPOINT_PATH = ROOT / "08_full_texts" / "_upload_all_checkpoint.json"

# Tiered compression: bigger files get more aggressive quality
JPEG_QUALITY_DEFAULT = 50
JPEG_QUALITY_LARGE = 40      # files > 10 MB
JPEG_QUALITY_XLARGE = 35     # files > 30 MB
MAX_IMG_DIM = 1800           # downscale images with any dimension > this
MIN_IMG_DIM = 80
MIN_SAVINGS_FRAC = 0.10      # lowered: accept 10% savings per image
MIN_FILE_SAVINGS = 5_000     # lowered minimum file savings
WRITE_DELAY = 1.1

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}


# ── Zotero helpers ──────────────────────────────────────────────────

def _get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path, json_data=None, data=None, extra_headers=None):
    hdrs = {**HEADERS}
    if extra_headers:
        hdrs.update(extra_headers)
    if json_data is not None:
        r = requests.post(f"{BASE_URL}{path}", headers=hdrs, json=json_data, timeout=30)
    else:
        r = requests.post(f"{BASE_URL}{path}", headers=hdrs, data=data, timeout=30)
    return r


def fetch_attachments():
    """Returns (with_file: {filename: {key, md5, parent}}, no_file: {filename: {key, parent}})."""
    with_file = {}
    no_file = {}
    start = 0
    while True:
        batch = _get("/items", {"itemType": "attachment", "start": start, "limit": 100, "format": "json"})
        if not batch:
            break
        for it in batch:
            d = it["data"]
            if d.get("contentType") == "application/pdf":
                fn = d.get("filename", "")
                info = {"key": d["key"], "parent": d.get("parentItem", "")}
                if d.get("md5"):
                    info["md5"] = d["md5"]
                    with_file[fn] = info
                else:
                    no_file[fn] = info
        start += 100
    return with_file, no_file


def fetch_all_items():
    """Returns {key: {title, doi, ...}} for all non-attachment items."""
    items = {}
    start = 0
    while True:
        batch = _get("/items", {"itemType": "-attachment", "start": start, "limit": 100, "format": "json"})
        if not batch:
            break
        for it in batch:
            d = it["data"]
            items[d["key"]] = {
                "title": d.get("title", ""),
                "doi": d.get("DOI", ""),
                "key": d["key"],
            }
        start += 100
    return items


def _normalize(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def build_title_index(items):
    """Returns {normalized_title: key}."""
    idx = {}
    for key, info in items.items():
        t = _normalize(info["title"])
        if t:
            idx[t] = key
    return idx


def find_parent_for_pdf(pdf_name, master_records, title_idx):
    """Try to find the Zotero parent item key for a local PDF.
    
    Match via paper_id → master_records → title → Zotero title index.
    """
    pid = pdf_name.split("_")[0]
    rec = master_records.get(pid)
    if not rec:
        return None
    
    # Try DOI match could be added but title is reliable enough
    title_norm = _normalize(rec.get("title", ""))
    if title_norm and title_norm in title_idx:
        return title_idx[title_norm]
    return None


# ── Upload functions ────────────────────────────────────────────────

def upload_new_file(attach_key, pdf_path):
    """Upload file to an existing attachment item that has no file (If-None-Match: *)."""
    file_bytes = pdf_path.read_bytes()
    md5 = hashlib.md5(file_bytes).hexdigest()
    mtime = int(pdf_path.stat().st_mtime * 1000)
    
    url = f"{BASE_URL}/items/{attach_key}/file"
    auth_body = f"md5={md5}&filename={pdf_path.name}&filesize={len(file_bytes)}&mtime={mtime}"
    
    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                                                "If-None-Match": "*"}, data=auth_body, timeout=30)
        except requests.exceptions.Timeout:
            continue
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            continue
        if resp.status_code == 200:
            break
        if resp.status_code == 413:
            log.warning("  413 Too Large")
            return False
        log.warning("  Auth %d: %s", resp.status_code, resp.text[:200])
        return False
    else:
        return False
    
    auth_data = resp.json()
    if auth_data.get("exists"):
        return True
    
    return _s3_upload_and_register(url, auth_data, file_bytes, "If-None-Match", "*")


def replace_file(attach_key, old_md5, pdf_path):
    """Replace file on existing attachment (If-Match: old_md5)."""
    file_bytes = pdf_path.read_bytes()
    new_md5 = hashlib.md5(file_bytes).hexdigest()
    mtime = int(pdf_path.stat().st_mtime * 1000)
    
    url = f"{BASE_URL}/items/{attach_key}/file"
    auth_body = f"md5={new_md5}&filename={pdf_path.name}&filesize={len(file_bytes)}&mtime={mtime}"
    
    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                                                "If-Match": old_md5}, data=auth_body, timeout=30)
        except requests.exceptions.Timeout:
            continue
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            continue
        if resp.status_code in (412, 413):
            log.warning("  Auth %d", resp.status_code)
            return False
        if resp.status_code == 200:
            break
        log.warning("  Auth %d: %s", resp.status_code, resp.text[:200])
        return False
    else:
        return False
    
    auth_data = resp.json()
    if auth_data.get("exists"):
        return True
    
    return _s3_upload_and_register(url, auth_data, file_bytes, "If-Match", old_md5)


def create_attachment_and_upload(parent_key, pdf_path):
    """Create a new attachment item and upload the PDF file."""
    filename = pdf_path.name
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
    resp = _post("/items", json_data=attach_data)
    result = resp.json()
    successful = result.get("successful", result.get("success", {}))
    if "0" not in successful:
        log.warning("  Failed to create attachment: %s", result.get("failed", {}))
        return False
    
    obj = successful["0"]
    attach_key = obj["key"] if isinstance(obj, dict) else obj
    
    return upload_new_file(attach_key, pdf_path)


def _s3_upload_and_register(url, auth_data, file_bytes, match_header, match_value):
    """Upload to S3 and register with Zotero."""
    upload_body = (auth_data.get("prefix", "").encode("latin-1") +
                   file_bytes +
                   auth_data.get("suffix", "").encode("latin-1"))
    
    for attempt in range(3):
        try:
            s3 = requests.post(auth_data["url"],
                               headers={"Content-Type": auth_data.get("contentType", "application/pdf")},
                               data=upload_body, timeout=180)
            if s3.status_code in (200, 201, 204):
                break
        except requests.exceptions.Timeout:
            pass
        if attempt < 2:
            time.sleep(5)
    else:
        log.warning("  S3 upload failed")
        return False
    
    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            reg = requests.post(url, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                                               match_header: match_value},
                                data=f"upload={auth_data['uploadKey']}", timeout=30)
        except requests.exceptions.Timeout:
            continue
        if reg.status_code == 429:
            time.sleep(int(reg.headers.get("Retry-After", 5)))
            continue
        if reg.status_code == 204:
            return True
        log.warning("  Register %d", reg.status_code)
        return False
    return False


# ── Compression ─────────────────────────────────────────────────────

def _get_jpeg_quality(file_size_bytes):
    """Return JPEG quality based on file size."""
    mb = file_size_bytes / (1024 * 1024)
    if mb > 30:
        return JPEG_QUALITY_XLARGE
    if mb > 10:
        return JPEG_QUALITY_LARGE
    return JPEG_QUALITY_DEFAULT


def compress_pdf(src, dst):
    """Compress PDF by re-encoding images with tiered quality + downscaling."""
    jpeg_q = _get_jpeg_quality(src.stat().st_size)
    try:
        with pikepdf.open(src) as pdf:
            count = 0
            for page in pdf.pages:
                try:
                    for name, raw_img in page.images.items():
                        try:
                            pdfimg = PdfImage(raw_img)
                            if pdfimg.width < MIN_IMG_DIM and pdfimg.height < MIN_IMG_DIM:
                                continue
                            old_size = len(raw_img.read_raw_bytes())
                            pil_img = pdfimg.as_pil_image()
                            if pil_img.mode not in ("RGB", "L"):
                                pil_img = pil_img.convert("RGB")
                            # Downscale large images
                            w, h = pil_img.size
                            if max(w, h) > MAX_IMG_DIM:
                                ratio = MAX_IMG_DIM / max(w, h)
                                new_w, new_h = int(w * ratio), int(h * ratio)
                                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                            buf = io.BytesIO()
                            pil_img.save(buf, "JPEG", quality=jpeg_q, optimize=True)
                            if len(buf.getvalue()) < old_size * (1 - MIN_SAVINGS_FRAC):
                                raw_img.write(buf.getvalue(), filter=pikepdf.Name("/DCTDecode"))
                                raw_img["/Width"] = pil_img.size[0]
                                raw_img["/Height"] = pil_img.size[1]
                                cs = "/DeviceGray" if pil_img.mode == "L" else "/DeviceRGB"
                                raw_img["/ColorSpace"] = pikepdf.Name(cs)
                                raw_img["/BitsPerComponent"] = 8
                                for k in ("/DecodeParms", "/Decode", "/SMask", "/Mask"):
                                    if k in raw_img:
                                        del raw_img[k]
                                count += 1
                        except Exception:
                            pass
                except Exception:
                    pass
            pdf.remove_unreferenced_resources()
            pdf.save(dst, linearize=True, object_stream_mode=pikepdf.ObjectStreamMode.generate,
                     compress_streams=True)
        return True, count
    except Exception as e:
        log.warning("  Compress failed: %s", str(e)[:100])
        return False, 0


# ── Checkpoint ──────────────────────────────────────────────────────

def load_checkpoint():
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {"done": [], "replaced": [], "uploaded_existing": [], "uploaded_new": [],
            "skipped": [], "failed": [], "no_parent": [], "bytes_saved": 0}


def save_checkpoint(ckpt):
    CHECKPOINT_PATH.write_text(json.dumps(ckpt))


# ── Main ────────────────────────────────────────────────────────────

def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID env vars")

    COMPRESSED_DIR.mkdir(exist_ok=True)
    ckpt = load_checkpoint()
    done_set = set(ckpt["done"])

    # Load master records for paper_id → title mapping
    from tools.slr_toolkit import config
    master_records = {}
    with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            master_records[row["paper_id"]] = row

    # Fetch Zotero state
    log.info("Fetching Zotero attachments...")
    att_with_file, att_no_file = fetch_attachments()
    log.info("  With file: %d, Without file: %d", len(att_with_file), len(att_no_file))

    log.info("Fetching Zotero items...")
    all_items = fetch_all_items()
    title_idx = build_title_index(all_items)
    log.info("  Items: %d, Title index: %d", len(all_items), len(title_idx))

    # Build work list
    all_pdfs = sorted(PDFS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_size, reverse=True)
    log.info("Local PDFs: %d, Already done: %d", len(all_pdfs), len(done_set))

    work = []
    for pdf in all_pdfs:
        if pdf.name in done_set:
            continue
        if pdf.name in att_with_file:
            work.append(("replace", pdf, att_with_file[pdf.name]))
        elif pdf.name in att_no_file:
            work.append(("upload_existing", pdf, att_no_file[pdf.name]))
        else:
            work.append(("upload_new", pdf, None))

    replace_count = sum(1 for t, _, _ in work if t == "replace")
    upload_existing_count = sum(1 for t, _, _ in work if t == "upload_existing")
    upload_new_count = sum(1 for t, _, _ in work if t == "upload_new")
    log.info("Work: %d replace, %d upload-existing, %d upload-new",
             replace_count, upload_existing_count, upload_new_count)

    if not work:
        log.info("Nothing to process!")
        return

    for i, (task_type, pdf, att_info) in enumerate(work, 1):
        fname = pdf.name
        orig_bytes = pdf.stat().st_size
        orig_mb = orig_bytes / (1024 * 1024)

        log.info("[%d/%d] %s %s (%.2f MB)", i, len(work), task_type.upper(), fname[:55], orig_mb)

        # Step 1: Compress
        dst = COMPRESSED_DIR / fname
        ok, img_count = compress_pdf(pdf, dst)

        if ok:
            new_bytes = dst.stat().st_size
            savings = orig_bytes - new_bytes
            if savings > MIN_FILE_SAVINGS:
                log.info("  Compressed: %.2f -> %.2f MB (%.0f%%, q=%d)",
                         orig_mb, new_bytes / (1024 * 1024), savings / orig_bytes * 100,
                         _get_jpeg_quality(orig_bytes))
                # Replace local copy with compressed
                dst.replace(pdf)
                ckpt["bytes_saved"] += savings
            else:
                log.info("  No meaningful savings, using original")
                dst.unlink(missing_ok=True)
        else:
            dst.unlink(missing_ok=True)

        # Step 2: Upload
        upload_ok = False
        if task_type == "replace":
            upload_ok = replace_file(att_info["key"], att_info["md5"], pdf)
            if upload_ok:
                ckpt["replaced"].append(fname)
        elif task_type == "upload_existing":
            upload_ok = upload_new_file(att_info["key"], pdf)
            if upload_ok:
                ckpt["uploaded_existing"].append(fname)
        else:  # upload_new
            parent_key = find_parent_for_pdf(fname, master_records, title_idx)
            if parent_key:
                upload_ok = create_attachment_and_upload(parent_key, pdf)
                if upload_ok:
                    ckpt["uploaded_new"].append(fname)
            else:
                log.warning("  No Zotero parent found for %s", fname[:50])
                ckpt["no_parent"].append(fname)

        if not upload_ok and task_type != "upload_new":
            ckpt["failed"].append(fname)
            log.warning("  Upload FAILED")
        elif not upload_ok and task_type == "upload_new" and fname not in ckpt["no_parent"]:
            ckpt["failed"].append(fname)

        if upload_ok:
            log.info("  Uploaded")

        ckpt["done"].append(fname)
        save_checkpoint(ckpt)

        if i % 25 == 0:
            log.info("--- Progress: %d/%d | replaced=%d uploaded_existing=%d uploaded_new=%d failed=%d no_parent=%d | saved=%.0f MB ---",
                     i, len(work), len(ckpt["replaced"]), len(ckpt["uploaded_existing"]),
                     len(ckpt["uploaded_new"]), len(ckpt["failed"]), len(ckpt["no_parent"]),
                     ckpt["bytes_saved"] / (1024 * 1024))

    # Summary
    log.info("=" * 60)
    log.info("COMPLETE:")
    log.info("  Replaced: %d", len(ckpt["replaced"]))
    log.info("  Uploaded (existing att): %d", len(ckpt["uploaded_existing"]))
    log.info("  Uploaded (new att): %d", len(ckpt["uploaded_new"]))
    log.info("  Failed: %d", len(ckpt["failed"]))
    log.info("  No parent found: %d", len(ckpt["no_parent"]))
    log.info("  Compression savings: %.1f MB", ckpt["bytes_saved"] / (1024 * 1024))


if __name__ == "__main__":
    main()
