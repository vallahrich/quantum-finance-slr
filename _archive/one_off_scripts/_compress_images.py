"""Compress ALL PDFs via image recompression and replace on Zotero.

Uses pikepdf + Pillow to re-encode embedded images at JPEG quality 50,
achieving 30-70% file size reduction. Then replaces the file on Zotero
using If-Match to free storage immediately.

Has checkpoint support — safe to interrupt and resume.
"""
import hashlib
import json
import logging
import os
import io
import sys
import time
from pathlib import Path

import pikepdf
from pikepdf import PdfImage
from PIL import Image
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
PDFS_DIR = ROOT / "08_full_texts" / "pdfs"
COMPRESSED_DIR = ROOT / "08_full_texts" / "_compressed"
CHECKPOINT_PATH = ROOT / "08_full_texts" / "_imgcompress_checkpoint.json"
REPORT_PATH = ROOT / "08_full_texts" / "compression_report.json"

JPEG_QUALITY = 60
MIN_IMG_DIM = 100       # skip images smaller than 100x100
MIN_SAVINGS_FRAC = 0.15 # only replace image if >15% savings
MIN_FILE_SAVINGS = 10_000  # skip if file savings < 10 KB
WRITE_DELAY = 1.1

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}


# ── Zotero helpers ──────────────────────────────────────────────────

def fetch_all_attachments() -> dict[str, dict]:
    """Returns {filename: {key, md5}}."""
    result = {}
    start = 0
    while True:
        r = requests.get(f"{BASE_URL}/items",
                         headers=HEADERS,
                         params={"itemType": "attachment", "start": start,
                                 "limit": 100, "format": "json"},
                         timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for it in batch:
            d = it["data"]
            if d.get("md5") and d.get("contentType") == "application/pdf":
                result[d.get("filename", "")] = {"key": d["key"], "md5": d["md5"]}
        start += 100
    log.info("Zotero attachments with files: %d", len(result))
    return result


def replace_file(attach_key: str, old_md5: str, pdf_path: Path) -> bool:
    """Replace file on existing Zotero attachment using If-Match."""
    file_bytes = pdf_path.read_bytes()
    file_size = len(file_bytes)
    new_md5 = hashlib.md5(file_bytes).hexdigest()
    filename = pdf_path.name
    mtime = int(pdf_path.stat().st_mtime * 1000)

    url = f"{BASE_URL}/items/{attach_key}/file"

    # Step 1: Authorize
    auth_headers = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                    "If-Match": old_md5}
    auth_body = f"md5={new_md5}&filename={filename}&filesize={file_size}&mtime={mtime}"

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            resp = requests.post(url, headers=auth_headers, data=auth_body, timeout=30)
        except requests.exceptions.Timeout:
            continue
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            continue
        if resp.status_code in (412, 413):
            log.warning("  Auth %d for %s", resp.status_code, attach_key)
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

    # Step 2: S3 upload
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
        log.warning("  S3 upload failed for %s", attach_key)
        return False

    # Step 3: Register
    reg_headers = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                   "If-Match": old_md5}

    for attempt in range(3):
        time.sleep(WRITE_DELAY)
        try:
            reg = requests.post(url, headers=reg_headers,
                                data=f"upload={auth_data['uploadKey']}", timeout=30)
        except requests.exceptions.Timeout:
            continue
        if reg.status_code == 429:
            time.sleep(int(reg.headers.get("Retry-After", 5)))
            continue
        if reg.status_code == 204:
            return True
        log.warning("  Register %d: %s", reg.status_code, reg.text[:200])
        return False
    return False


# ── PDF compression ─────────────────────────────────────────────────

def compress_pdf_images(src: Path, dst: Path) -> tuple[bool, int]:
    """Compress PDF by re-encoding images at lower JPEG quality.
    
    Returns (success, num_images_recompressed).
    """
    try:
        with pikepdf.open(src) as pdf:
            count = 0
            for page in pdf.pages:
                try:
                    images = list(page.images.items())
                except Exception:
                    continue
                for name, raw_img in images:
                    try:
                        pdfimg = PdfImage(raw_img)
                        if pdfimg.width < MIN_IMG_DIM and pdfimg.height < MIN_IMG_DIM:
                            continue
                        old_bytes = raw_img.read_raw_bytes()
                        old_size = len(old_bytes)
                        
                        pil_img = pdfimg.as_pil_image()
                        if pil_img.mode not in ("RGB", "L"):
                            pil_img = pil_img.convert("RGB")
                        
                        buf = io.BytesIO()
                        pil_img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
                        new_bytes = buf.getvalue()
                        
                        if len(new_bytes) < old_size * (1 - MIN_SAVINGS_FRAC):
                            raw_img.write(new_bytes, filter=pikepdf.Name("/DCTDecode"))
                            raw_img["/Width"] = pdfimg.width
                            raw_img["/Height"] = pdfimg.height
                            cs = "/DeviceGray" if pil_img.mode == "L" else "/DeviceRGB"
                            raw_img["/ColorSpace"] = pikepdf.Name(cs)
                            raw_img["/BitsPerComponent"] = 8
                            for k in ("/DecodeParms", "/Decode", "/SMask", "/Mask"):
                                if k in raw_img:
                                    del raw_img[k]
                            count += 1
                    except Exception:
                        pass

            pdf.remove_unreferenced_resources()
            pdf.save(dst, linearize=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate,
                     compress_streams=True)
        return True, count
    except Exception as e:
        log.warning("Compress failed %s: %s", src.name[:50], e)
        return False, 0


# ── Checkpoint ──────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {"done": [], "replaced": [], "skipped": [], "failed": [],
            "compress_failed": [], "bytes_saved": 0}


def save_checkpoint(ckpt: dict):
    CHECKPOINT_PATH.write_text(json.dumps(ckpt))


# ── Main ────────────────────────────────────────────────────────────

def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID env vars")

    COMPRESSED_DIR.mkdir(exist_ok=True)
    ckpt = load_checkpoint()
    done_set = set(ckpt["done"])

    # Only compress the 150 biggest PDFs
    MAX_PDFS = 150
    all_pdfs = sorted(PDFS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_size, reverse=True)[:MAX_PDFS]
    log.info("Top %d largest PDFs selected (of %d total)", MAX_PDFS, len(list(PDFS_DIR.glob("*.pdf"))))
    log.info("Already processed: %d", len(done_set))

    log.info("Fetching Zotero attachments...")
    zot_idx = fetch_all_attachments()

    work = []
    no_zotero = 0
    for pdf in all_pdfs:
        if pdf.name in done_set:
            continue
        if pdf.name in zot_idx:
            work.append(pdf)
        else:
            no_zotero += 1

    log.info("To process: %d  |  No Zotero match: %d  |  Already done: %d",
             len(work), no_zotero, len(done_set))

    if not work:
        log.info("Nothing to process!")
        return

    for i, pdf in enumerate(work, 1):
        fname = pdf.name
        orig_bytes = pdf.stat().st_size
        orig_mb = orig_bytes / (1024 * 1024)
        att = zot_idx[fname]
        dst = COMPRESSED_DIR / fname

        log.info("[%d/%d] %s (%.2f MB)", i, len(work), fname[:60], orig_mb)

        ok, img_count = compress_pdf_images(pdf, dst)
        if not ok:
            ckpt["done"].append(fname)
            ckpt["compress_failed"].append(fname)
            save_checkpoint(ckpt)
            continue

        new_bytes = dst.stat().st_size
        new_mb = new_bytes / (1024 * 1024)
        savings = orig_bytes - new_bytes

        if savings < MIN_FILE_SAVINGS:
            log.info("  Skip: %.2f -> %.2f MB (%d imgs, %.0f KB saved)",
                     orig_mb, new_mb, img_count, savings / 1024)
            ckpt["done"].append(fname)
            ckpt["skipped"].append(fname)
            dst.unlink(missing_ok=True)
            save_checkpoint(ckpt)
            continue

        pct = savings / orig_bytes * 100
        log.info("  Compressed: %.2f -> %.2f MB (%.0f%% reduction, %d imgs)",
                 orig_mb, new_mb, pct, img_count)

        if replace_file(att["key"], att["md5"], dst):
            ckpt["bytes_saved"] += savings
            ckpt["replaced"].append(fname)
            log.info("  Replaced on Zotero (%.1f MB saved)", savings / (1024 * 1024))
            # Also replace local copy
            dst.replace(pdf)
        else:
            ckpt["failed"].append(fname)
            log.warning("  Upload failed — keeping original")
            dst.unlink(missing_ok=True)

        ckpt["done"].append(fname)
        save_checkpoint(ckpt)

        # Progress summary every 50
        if i % 50 == 0:
            log.info("--- Progress: %d/%d done, %.1f MB saved so far ---",
                     i, len(work), ckpt["bytes_saved"] / (1024 * 1024))

    # Summary
    total_saved_mb = ckpt["bytes_saved"] / (1024 * 1024)
    log.info("=" * 60)
    log.info("COMPLETE: %d replaced, %d skipped, %d failed, %d compress_failed",
             len(ckpt["replaced"]), len(ckpt["skipped"]),
             len(ckpt["failed"]), len(ckpt["compress_failed"]))
    log.info("Total storage saved: %.1f MB", total_saved_mb)

    with open(REPORT_PATH, "w") as f:
        json.dump({
            "replaced": len(ckpt["replaced"]),
            "skipped": len(ckpt["skipped"]),
            "failed": len(ckpt["failed"]),
            "compress_failed": len(ckpt["compress_failed"]),
            "bytes_saved": ckpt["bytes_saved"],
            "mb_saved": round(total_saved_mb, 1),
        }, f, indent=2)


if __name__ == "__main__":
    main()
