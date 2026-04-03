"""Compress oversized PDFs and retry Zotero upload."""
import json
import logging
import shutil
from pathlib import Path

import pikepdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
PDFS_DIR = ROOT / "08_full_texts" / "pdfs"

FAILED_PIDS = ["d388ccd2fff8", "f3cb59fe38ac", "24ca4814e7f2", "323683ff9874", "0ab4724fd60f", "dca63675e36a"]


def compress_pdf(src: Path, dst: Path) -> bool:
    """Compress a PDF by rewriting with pikepdf (linearized, object streams)."""
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


def main():
    from tools.slr_toolkit.zotero_sync import ZoteroWriter

    compressed_dir = ROOT / "08_full_texts" / "_compressed"
    compressed_dir.mkdir(exist_ok=True)

    # Find and compress
    to_upload: list[tuple[str, Path]] = []

    for pid in FAILED_PIDS:
        matches = list(PDFS_DIR.glob(f"{pid}_*.pdf"))
        if not matches:
            log.warning("No PDF found for %s", pid)
            continue

        src = matches[0]
        src_mb = src.stat().st_size / (1024 * 1024)
        dst = compressed_dir / src.name

        log.info("Compressing %s (%.1f MB)...", src.name[:50], src_mb)
        if compress_pdf(src, dst):
            dst_mb = dst.stat().st_size / (1024 * 1024)
            ratio = (1 - dst_mb / src_mb) * 100
            log.info("  -> %.1f MB (%.0f%% reduction)", dst_mb, ratio)
            to_upload.append((pid, dst))
        else:
            to_upload.append((pid, src))  # try original anyway

    if not to_upload:
        log.info("Nothing to upload!")
        return

    # Look up Zotero keys
    writer = ZoteroWriter()
    from tools.slr_toolkit import config
    import csv, re

    # Build indices
    master = {}
    with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["paper_id"] in FAILED_PIDS:
                master[row["paper_id"]] = row

    doi_idx, arxiv_idx, title_idx, ay_idx = writer._build_zotero_index()

    success = 0
    failed = 0
    for pid, pdf_path in to_upload:
        paper = master.get(pid)
        if not paper:
            log.warning("No master record for %s", pid)
            failed += 1
            continue

        existing, method = writer._find_existing_item(paper, doi_idx, arxiv_idx, title_idx, ay_idx)
        if not existing:
            log.warning("No Zotero item found for %s", pid)
            failed += 1
            continue

        zkey = existing["key"]
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        log.info("Uploading %s (%.1f MB) to %s...", pid, size_mb, zkey)

        try:
            result = writer.upload_pdf(zkey, pdf_path)
            if result:
                success += 1
                # Replace original with compressed version
                if pdf_path.parent == compressed_dir:
                    orig = list(PDFS_DIR.glob(f"{pid}_*.pdf"))[0]
                    shutil.copy2(pdf_path, orig)
                    log.info("  Replaced original with compressed version")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            log.warning("  Upload failed: %s", str(e)[:100])

    log.info("=== Done: %d uploaded, %d failed ===", success, failed)


if __name__ == "__main__":
    main()
