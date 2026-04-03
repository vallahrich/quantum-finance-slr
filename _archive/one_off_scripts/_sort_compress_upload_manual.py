"""Sort manually downloaded PDFs, compress them, and upload to Zotero.

Reads PDFs from 08_full_texts/downloadedpdf/, matches them to papers in
master_records.csv using multiple strategies (arXiv ID, SSRN ID, DOI patterns,
title matching, CrossRef PII lookup), copies them to 08_full_texts/pdfs/ with
the standard naming convention, compresses them, and uploads to Zotero.
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

# Compression settings (same as _upload_all_pdfs.py)
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


# ── Helpers ─────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _slugify(title: str, max_len: int = 80) -> str:
    s = unicodedata.normalize("NFKD", title)
    s = re.sub(r"[^\w\s-]", "", s.lower())
    s = re.sub(r"[\s-]+", "_", s).strip("_")
    return s[:max_len]


# ── Matching ────────────────────────────────────────────────────────

def build_indices(master_csv: Path):
    """Build lookup indices from master_records.csv."""
    arxiv_idx = {}   # arxiv_id (without version) -> paper record
    ssrn_idx = {}    # ssrn_number -> paper record
    doi_idx = {}     # normalized doi -> paper record
    title_idx = {}   # normalized title -> paper record
    all_records = {}

    with open(master_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pid = row["paper_id"]
            doi = row.get("doi", "")
            title = row.get("title", "")
            all_records[pid] = row

            # arXiv index
            m = re.search(r"arxiv[./:](\d{4}\.\d{4,5})", doi, re.I)
            if m:
                arxiv_idx[m.group(1)] = row

            # SSRN index
            m = re.search(r"ssrn\.(\d+)", doi, re.I)
            if m:
                ssrn_idx[m.group(1)] = row

            # DOI index
            if doi:
                doi_idx[doi.lower().strip()] = row

            # Title index
            nt = _normalize(title)
            if len(nt) > 10:
                title_idx[nt] = row

    return arxiv_idx, ssrn_idx, doi_idx, title_idx, all_records


def _crossref_pii_lookup(pii: str) -> str | None:
    """Look up a ScienceDirect PII via CrossRef to get DOI."""
    # Format PII with hyphens for CrossRef: S0950705126003990 -> S0950-7051(26)00399-0
    # Actually easier to search CrossRef by filter
    url = "https://api.crossref.org/works"
    # Try searching with the PII directly
    params = {"query": pii, "rows": 3, "filter": "type:journal-article"}
    try:
        resp = requests.get(url, params=params, timeout=15,
                            headers={"User-Agent": "QuantumFinanceSLR/0.1"})
        if resp.status_code == 200:
            items = resp.json().get("message", {}).get("items", [])
            for item in items:
                doi = item.get("DOI", "")
                if doi:
                    return doi
    except Exception:
        pass
    return None


def match_pdf(filename: str, arxiv_idx, ssrn_idx, doi_idx, title_idx) -> tuple[dict | None, str]:
    """Try to match a PDF filename to a paper record. Returns (record, method)."""
    stem = Path(filename).stem

    # 1. arXiv ID from filename (e.g. 2304.08793v1.pdf)
    m = re.match(r"(\d{4}\.\d{4,5})", stem)
    if m:
        aid = m.group(1)
        if aid in arxiv_idx:
            return arxiv_idx[aid], "arxiv"

    # 2. SSRN ID from filename (e.g. ssrn-4130879.pdf)
    m = re.search(r"ssrn-?(\d+)", stem, re.I)
    if m:
        sid = m.group(1)
        if sid in ssrn_idx:
            return ssrn_idx[sid], "ssrn"

    # 3. DOI pattern in filename (e.g. WJARR-2025-1767 -> wjarr.2025.26.2.1767)
    m = re.match(r"WJARR-(\d{4})-(\d+)", stem, re.I)
    if m:
        suffix = m.group(2)
        for doi, rec in doi_idx.items():
            if "wjarr" in doi and doi.endswith(suffix):
                return rec, "doi-wjarr"

    # 4. IJEAS pattern (e.g. IJEAS0510017 -> ijeas.5.10.17)
    m = re.match(r"IJEAS(\d{2})(\d{2})(\d+)", stem, re.I)
    if m:
        for doi, rec in doi_idx.items():
            if "ijeas" in doi:
                # Extract numbers from DOI and compare
                parts = doi.split("ijeas.")[-1] if "ijeas." in doi else ""
                if parts and m.group(3) in parts:
                    return rec, "doi-ijeas"

    # 5. PeerJ pattern (e.g. peerj-cs-3014 -> 10.7717/peerj-cs.3014)
    m = re.search(r"peerj-cs-(\d+)", stem, re.I)
    if m:
        target_doi = f"10.7717/peerj-cs.{m.group(1)}"
        if target_doi in doi_idx:
            return doi_idx[target_doi], "doi-peerj"

    # 6. ScienceDirect PII (e.g. 1-s2.0-S0950705126003990-main)
    m = re.search(r"1-s2\.0-(S\d+)", stem)
    if m:
        pii = m.group(1)
        doi = _crossref_pii_lookup(pii)
        if doi and doi.lower() in doi_idx:
            return doi_idx[doi.lower()], "pii-crossref"

    # 7. Exact title match (e.g. "Classical and quantum computing methods...")
    clean = stem.replace("+", " ").replace("-", " ").replace("_", " ")
    nstem = _normalize(clean)
    if nstem in title_idx:
        return title_idx[nstem], "title-exact"

    # 8. Partial title match (for long enough stems)
    if len(nstem) > 25:
        for nt, rec in title_idx.items():
            if nstem in nt or nt in nstem:
                return rec, "title-partial"

    # 9. Fuzzy word-based title match
    words = [w for w in re.split(r"[\s_+\-]+", clean) if len(w) > 3]
    if len(words) >= 4:
        for nt, rec in title_idx.items():
            matched_words = sum(1 for w in words if _normalize(w) in nt)
            if matched_words >= len(words) * 0.7 and matched_words >= 3:
                return rec, "title-fuzzy"

    return None, ""


# ── Compression (from _upload_all_pdfs.py) ──────────────────────────

def _get_jpeg_quality(file_size_bytes):
    mb = file_size_bytes / (1024 * 1024)
    if mb > 30:
        return JPEG_QUALITY_XLARGE
    if mb > 10:
        return JPEG_QUALITY_LARGE
    return JPEG_QUALITY_DEFAULT


def compress_pdf(src: Path, dst: Path) -> tuple[bool, int]:
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


# ── Zotero upload (from _upload_all_pdfs.py) ────────────────────────

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


def find_zotero_parent(paper: dict, zotero_items: dict, ztitle_idx: dict) -> str | None:
    """Find Zotero parent item key for a paper."""
    # By DOI
    doi = paper.get("doi", "").strip()
    if doi:
        doi_lower = doi.lower()
        for key, info in zotero_items.items():
            if info.get("doi", "").lower() == doi_lower:
                return key

    # By title
    nt = _normalize(paper.get("title", ""))
    if nt and nt in ztitle_idx:
        return ztitle_idx[nt]

    return None


def fetch_zotero_state():
    """Fetch all Zotero items and attachments."""
    # Items
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

    # Attachments
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


def upload_pdf_to_zotero(parent_key: str, pdf_path: Path, att_with_file: dict, att_no_file: dict) -> bool:
    """Upload a PDF to Zotero, handling existing attachments."""
    fname = pdf_path.name

    # Check if attachment already exists with file
    if fname in att_with_file:
        return _replace_file(att_with_file[fname]["key"], att_with_file[fname]["md5"], pdf_path)

    # Check if attachment exists without file
    if fname in att_no_file:
        return _upload_new_file(att_no_file[fname]["key"], pdf_path)

    # Create new attachment and upload
    return _create_attachment_and_upload(parent_key, pdf_path)


def _upload_new_file(attach_key: str, pdf_path: Path) -> bool:
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
        log.warning("  Auth %d: %s", resp.status_code, resp.text[:200])
        return False
    else:
        return False

    auth_data = resp.json()
    if auth_data.get("exists"):
        return True
    return _s3_upload_and_register(url, auth_data, file_bytes, "If-None-Match", "*")


def _replace_file(attach_key: str, old_md5: str, pdf_path: Path) -> bool:
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


def _create_attachment_and_upload(parent_key: str, pdf_path: Path) -> bool:
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


# ── Download log update ────────────────────────────────────────────

def update_download_log(pid: str, paper: dict, filename: str):
    """Append entry to download_log.csv."""
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


# ── Main ────────────────────────────────────────────────────────────

def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID environment variables")

    COMPRESSED_DIR.mkdir(exist_ok=True)

    # Load included papers
    included = set()
    inc_path = ROOT / "05_screening" / "included_for_coding.csv"
    with open(inc_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            included.add(row["paper_id"])

    # Build matching indices
    master_csv = ROOT / "04_deduped_library" / "master_records.csv"
    log.info("Building matching indices from master_records.csv...")
    arxiv_idx, ssrn_idx, doi_idx, title_idx, all_records = build_indices(master_csv)
    log.info("  arXiv: %d, SSRN: %d, DOI: %d, Title: %d",
             len(arxiv_idx), len(ssrn_idx), len(doi_idx), len(title_idx))

    # Check which PDFs already exist
    existing_pids = set()
    for f in PDFS_DIR.glob("*.pdf"):
        existing_pids.add(f.name.split("_")[0])

    # Scan downloaded PDFs
    downloaded = sorted(DOWNLOADED_DIR.iterdir())
    pdf_files = [f for f in downloaded if f.suffix.lower() == ".pdf"]
    log.info("Found %d PDFs in downloadedpdf/", len(pdf_files))

    # Phase 1: Match
    matched = []
    unmatched = []
    skipped_not_included = []

    for pdf in pdf_files:
        record, method = match_pdf(pdf.name, arxiv_idx, ssrn_idx, doi_idx, title_idx)
        if record:
            pid = record["paper_id"]
            # Prefer included papers; skip duplicates
            if pid in existing_pids:
                log.info("  SKIP (already exists): %s -> %s", pdf.name[:50], pid)
                continue
            if pid not in included:
                # Check if a duplicate_of version is included
                dup = record.get("duplicate_of", "")
                if dup and dup in included:
                    pid = dup
                    record = all_records.get(dup, record)
                else:
                    skipped_not_included.append((pdf.name, pid, record.get("title", "")[:50], method))
                    continue
            matched.append((pdf, record, method))
        else:
            unmatched.append(pdf.name)

    log.info("")
    log.info("=== MATCHING RESULTS ===")
    log.info("Matched (included): %d", len(matched))
    for pdf, rec, method in matched:
        log.info("  [%s] %s -> %s %s", method, pdf.name[:45], rec["paper_id"], rec.get("title","")[:40])

    if skipped_not_included:
        log.info("")
        log.info("Skipped (not in included set): %d", len(skipped_not_included))
        for fn, pid, title, method in skipped_not_included:
            log.info("  [%s] %s -> %s %s", method, fn[:45], pid, title)

    if unmatched:
        log.info("")
        log.info("Unmatched: %d", len(unmatched))
        for fn in unmatched:
            log.info("  %s", fn)

    if not matched:
        log.info("Nothing to process!")
        return

    # Phase 2: Copy, compress, upload
    log.info("")
    log.info("=== PROCESSING %d PDFs ===", len(matched))

    # Fetch Zotero state
    log.info("Fetching Zotero state...")
    zotero_items, ztitle_idx, att_with_file, att_no_file = fetch_zotero_state()
    log.info("  Items: %d, Attachments with file: %d, without file: %d",
             len(zotero_items), len(att_with_file), len(att_no_file))

    success_count = 0
    fail_count = 0
    bytes_saved = 0

    for i, (pdf, record, method) in enumerate(matched, 1):
        pid = record["paper_id"]
        title = record.get("title", "unknown")
        slug = _slugify(title)
        new_name = f"{pid}_{slug}.pdf"
        dst_path = PDFS_DIR / new_name
        orig_size = pdf.stat().st_size
        orig_mb = orig_size / (1024 * 1024)

        log.info("[%d/%d] %s (%.1f MB)", i, len(matched), new_name[:55], orig_mb)

        # Copy to pdfs/
        import shutil
        shutil.copy2(pdf, dst_path)

        # Compress
        compressed_path = COMPRESSED_DIR / new_name
        ok, img_count = compress_pdf(dst_path, compressed_path)
        if ok:
            new_size = compressed_path.stat().st_size
            savings = orig_size - new_size
            if savings > MIN_FILE_SAVINGS:
                pct = savings / orig_size * 100
                log.info("  Compressed: %.1f -> %.1f MB (%.0f%% reduction, %d images)",
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
            fail_count += 1
            update_download_log(pid, record, new_name)
            continue

        # Upload
        upload_ok = upload_pdf_to_zotero(parent_key, dst_path, att_with_file, att_no_file)
        if upload_ok:
            log.info("  Uploaded to Zotero (parent: %s)", parent_key)
            success_count += 1
        else:
            log.warning("  Upload FAILED")
            fail_count += 1

        # Update download log
        update_download_log(pid, record, new_name)

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("COMPLETE:")
    log.info("  Uploaded: %d", success_count)
    log.info("  Failed: %d", fail_count)
    log.info("  Compression savings: %.1f MB", bytes_saved / (1024 * 1024))
    log.info("  Unmatched files: %d", len(unmatched))
    log.info("  Skipped (not included): %d", len(skipped_not_included))


if __name__ == "__main__":
    main()
