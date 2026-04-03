"""Process the 11 previously-unmatched manual PDFs.

Uses titles extracted via PyMuPDF to build a hardcoded mapping, then
copies, compresses, and uploads each to Zotero.
"""
import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import pikepdf
import requests
from pikepdf import PdfImage
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DOWNLOADED_DIR = ROOT / "08_full_texts" / "downloadedpdf"
PDFS_DIR = ROOT / "08_full_texts" / "pdfs"
COMPRESSED_DIR = ROOT / "08_full_texts" / "_compressed"
DOWNLOAD_LOG = ROOT / "08_full_texts" / "download_log.csv"

# Verified mapping: filename -> paper_id (all INCLUDED)
MANUAL_MATCHES = {
    # ScienceDirect paper (the original, not the corrigendum dfd464e83103)
    "1-s2.0-S2352711023002558-mainext.pdf": "dfd464e83103",
    # Authorea preprint
    "1370562.pdf": "aa5b834c3a1d",
    # Leiden thesis chapter
    "1887_4290771-Chapter 2.pdf": "17bf34700dca",
    # arXiv: Efficient Evaluation of Exponential and Gaussian Functions
    "2110.05653v1.pdf": "aeba35e547c4",
    # arXiv: A Comparative Study of Quantum Optimization Techniques
    "2503.12121v2.pdf": "1b63c3136291",
    # arXiv: Accelerating Quantum Monte Carlo Calculations
    "2508.06441v3.pdf": "6e0380dce3b2",
    # IEEE: Application of Quantum Computing in Optimization Problems
    "485.pdf": "311bac170c43",
    # JAIBDD: Advancing Financial Decision-Making through QC
    "67dc35e21d25e.pdf": "d3580aed27bb",
    # Book: AI & Quantum Computing for Finance & Insurance (Schulte)
    "AIQuantumComputingFinal.pdf": "64111b3b5d61",
    # IJEAS: A time-Series Model Based on Quantum Walk
    "IJEAS0510017.pdf": "8d9fbaf6510b",
    # Thesis: Discrete-Time Quantum Walk of a BEC
    "out.pdf": "1bc4675bdbc6",
}

# Compression settings
JPEG_QUALITY_DEFAULT = 50
JPEG_QUALITY_LARGE = 40
JPEG_QUALITY_XLARGE = 35
MAX_IMG_DIM = 1800
MIN_IMG_DIM = 80
MIN_SAVINGS_FRAC = 0.10
MIN_FILE_SAVINGS = 5_000
WRITE_DELAY = 1.1

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _slugify(title: str, max_len: int = 80) -> str:
    s = unicodedata.normalize("NFKD", title)
    s = re.sub(r"[^\w\s-]", "", s.lower())
    s = re.sub(r"[\s-]+", "_", s).strip("_")
    return s[:max_len]


# ── Compression ─────────────────────────────────────────────────────

def _get_jpeg_quality(file_size_bytes):
    mb = file_size_bytes / (1024 * 1024)
    if mb > 30:
        return JPEG_QUALITY_XLARGE
    if mb > 10:
        return JPEG_QUALITY_LARGE
    return JPEG_QUALITY_DEFAULT


def compress_pdf(src: Path, dst: Path) -> tuple[bool, int]:
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
            pdf.save(dst, linearize=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate,
                     compress_streams=True)
        return True, count
    except Exception as e:
        log.warning("  Compress failed: %s", str(e)[:100])
        return False, 0


# ── Zotero helpers ──────────────────────────────────────────────────

def _zotero_get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _zotero_post(path, json_data=None, data=None, extra_headers=None):
    hdrs = {**HEADERS}
    if extra_headers:
        hdrs.update(extra_headers)
    if json_data is not None:
        r = requests.post(f"{BASE_URL}{path}", headers=hdrs, json=json_data, timeout=30)
    else:
        r = requests.post(f"{BASE_URL}{path}", headers=hdrs, data=data, timeout=30)
    return r


def _s3_upload_and_register(url, auth_data, file_bytes, match_header, match_value):
    upload_body = (auth_data.get("prefix", "").encode("latin-1") +
                   file_bytes +
                   auth_data.get("suffix", "").encode("latin-1"))
    for attempt in range(3):
        try:
            s3 = requests.post(auth_data["url"],
                               headers={"Content-Type": auth_data.get("contentType", "application/pdf")},
                               data=upload_body, timeout=300)
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


def _upload_new_file(attach_key, pdf_path):
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
            log.warning("  413 Too Large (%d bytes)", len(file_bytes))
            return False
        log.warning("  Auth %d: %s", resp.status_code, resp.text[:200])
        return False
    else:
        return False
    auth_data = resp.json()
    if auth_data.get("exists"):
        return True
    return _s3_upload_and_register(url, auth_data, file_bytes, "If-None-Match", "*")


def _create_attachment_and_upload(parent_key, pdf_path):
    attach_data = [{
        "itemType": "attachment",
        "parentItem": parent_key,
        "linkMode": "imported_file",
        "title": pdf_path.name,
        "contentType": "application/pdf",
        "filename": pdf_path.name,
        "tags": [],
    }]
    time.sleep(WRITE_DELAY)
    resp = _zotero_post("/items", json_data=attach_data)
    result = resp.json()
    successful = result.get("successful", result.get("success", {}))
    if "0" not in successful:
        log.warning("  Failed to create attachment: %s", result.get("failed", {}))
        return False
    obj = successful["0"]
    attach_key = obj["key"] if isinstance(obj, dict) else obj
    return _upload_new_file(attach_key, pdf_path)


def find_zotero_parent(paper, zotero_items, ztitle_idx):
    doi = paper.get("doi", "").strip()
    if doi:
        doi_lower = doi.lower()
        for key, info in zotero_items.items():
            if info.get("doi", "").lower() == doi_lower:
                return key
    nt = _normalize(paper.get("title", ""))
    if nt and nt in ztitle_idx:
        return ztitle_idx[nt]
    # Partial title match  
    if len(nt) > 30:
        for t, key in ztitle_idx.items():
            if nt in t or t in nt:
                return key
    return None


def fetch_zotero_state():
    items = {}
    start = 0
    while True:
        batch = _zotero_get("/items", {"itemType": "-attachment", "start": start, "limit": 100})
        if not batch:
            break
        for it in batch:
            d = it["data"]
            items[d["key"]] = {"title": d.get("title", ""), "doi": d.get("DOI", ""), "key": d["key"]}
        start += 100

    att_with_file = {}
    att_no_file = {}
    start = 0
    while True:
        batch = _zotero_get("/items", {"itemType": "attachment", "start": start, "limit": 100})
        if not batch:
            break
        for it in batch:
            d = it["data"]
            if d.get("contentType") == "application/pdf":
                fn = d.get("filename", "")
                info = {"key": d["key"], "parent": d.get("parentItem", "")}
                if d.get("md5"):
                    info["md5"] = d["md5"]
                    att_with_file[fn] = info
                else:
                    att_no_file[fn] = info
        start += 100

    title_idx = {}
    for key, info in items.items():
        nt = _normalize(info["title"])
        if nt:
            title_idx[nt] = key

    return items, title_idx, att_with_file, att_no_file


def update_download_log(pid, paper, filename):
    row = {
        "paper_id": pid,
        "title": paper.get("title", ""),
        "doi": paper.get("doi", ""),
        "source": "manual",
        "pdf_url": "",
        "status": "success",
        "filename": filename,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    with open(DOWNLOAD_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["paper_id", "title", "doi", "source",
                                                "pdf_url", "status", "filename", "timestamp"])
        writer.writerow(row)


def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID environment variables")

    COMPRESSED_DIR.mkdir(exist_ok=True)

    # Load master records
    master = {}
    with open(ROOT / "04_deduped_library" / "master_records.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            master[row["paper_id"]] = row

    # Check which already have PDFs
    existing_pids = set()
    for f in PDFS_DIR.glob("*.pdf"):
        existing_pids.add(f.name.split("_")[0])

    # Build work list
    work = []
    for fn, pid in MANUAL_MATCHES.items():
        src = DOWNLOADED_DIR / fn
        if not src.exists():
            log.warning("File not found: %s", fn)
            continue
        if pid in existing_pids:
            log.info("SKIP (already exists): %s -> %s", fn, pid)
            continue
        if pid not in master:
            log.warning("Paper ID not in master records: %s", pid)
            continue
        work.append((src, pid, master[pid]))

    if not work:
        log.info("Nothing to process!")
        return

    log.info("=== %d PDFs to process ===", len(work))
    for src, pid, rec in work:
        title = rec.get("title", "")[:60]
        log.info("  %s -> %s (%s)", src.name[:45], pid, title)

    # Fetch Zotero state
    log.info("\nFetching Zotero state...")
    zotero_items, ztitle_idx, att_with_file, att_no_file = fetch_zotero_state()
    log.info("  Items: %d, Attachments: %d", len(zotero_items), len(att_with_file) + len(att_no_file))

    success = 0
    failed = 0
    bytes_saved = 0

    for i, (src, pid, record) in enumerate(work, 1):
        title = record.get("title", "unknown")
        slug = _slugify(title)
        new_name = f"{pid}_{slug}.pdf"
        dst_path = PDFS_DIR / new_name
        orig_size = src.stat().st_size
        orig_mb = orig_size / (1024 * 1024)

        log.info("\n[%d/%d] %s (%.1f MB)", i, len(work), new_name[:55], orig_mb)

        # Copy
        shutil.copy2(src, dst_path)

        # Compress
        compressed_path = COMPRESSED_DIR / new_name
        ok, img_count = compress_pdf(dst_path, compressed_path)
        if ok:
            new_size = compressed_path.stat().st_size
            savings = orig_size - new_size
            if savings > MIN_FILE_SAVINGS:
                pct = savings / orig_size * 100
                log.info("  Compressed: %.1f -> %.1f MB (%.0f%%, %d images)",
                         orig_mb, new_size / (1024 * 1024), pct, img_count)
                compressed_path.replace(dst_path)
                bytes_saved += savings
            else:
                log.info("  No meaningful compression savings")
                compressed_path.unlink(missing_ok=True)
        else:
            compressed_path.unlink(missing_ok=True)

        # Find Zotero parent
        parent_key = find_zotero_parent(record, zotero_items, ztitle_idx)
        if not parent_key:
            log.warning("  No Zotero parent item found - skipping upload")
            update_download_log(pid, record, new_name)
            failed += 1
            continue

        # Upload
        final_size = dst_path.stat().st_size / (1024 * 1024)
        log.info("  Uploading (%.1f MB) to parent %s...", final_size, parent_key)
        upload_ok = _create_attachment_and_upload(parent_key, dst_path)
        if upload_ok:
            log.info("  Uploaded OK")
            success += 1
        else:
            log.warning("  Upload FAILED")
            failed += 1

        update_download_log(pid, record, new_name)

    log.info("\n" + "=" * 60)
    log.info("COMPLETE:")
    log.info("  Uploaded: %d", success)
    log.info("  Failed: %d", failed)
    log.info("  Compression savings: %.1f MB", bytes_saved / (1024 * 1024))


if __name__ == "__main__":
    main()
