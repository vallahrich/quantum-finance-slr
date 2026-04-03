"""Upload PDFs to existing Zotero items using keys from sync report."""
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent

def main():
    # Load sync report for paper_id -> zotero_key mapping
    report_path = ROOT / "08_full_texts" / "zotero_sync_report.json"
    with open(report_path) as f:
        report = json.load(f)

    key_map: dict[str, str] = {}
    for p in report.get("created", []):
        if p.get("zotero_key"):
            key_map[p["paper_id"]] = p["zotero_key"]
    for p in report.get("updated", []):
        if p.get("zotero_key"):
            key_map[p["paper_id"]] = p["zotero_key"]

    log.info("Loaded %d Zotero item keys from sync report", len(key_map))

    # Build PDF index from download_log
    pdfs_dir = ROOT / "08_full_texts" / "pdfs"
    pdf_index: dict[str, Path] = {}
    with open(ROOT / "08_full_texts" / "download_log.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "success" and row.get("filename"):
                path = pdfs_dir / row["filename"]
                if path.is_file():
                    pdf_index[row["paper_id"]] = path

    # Also scan directory for paper_id prefix matches
    for pdf_file in pdfs_dir.glob("*.pdf"):
        pid_part = pdf_file.stem.split("_", 1)[0]
        if pid_part not in pdf_index:
            pdf_index[pid_part] = pdf_file

    uploadable = sorted(pid for pid in pdf_index if pid in key_map)
    log.info("PDFs on disk: %d, uploadable: %d", len(pdf_index), len(uploadable))

    # Initialize Zotero writer
    from tools.slr_toolkit.zotero_sync import ZoteroWriter
    writer = ZoteroWriter()

    # First, clean up orphaned attachment items from the failed first run
    log.info("Cleaning up orphaned attachment items from failed uploads...")
    orphan_count = 0
    # Fetch all attachment items in the library
    attachments = []
    start = 0
    while True:
        resp = writer._get("/items", params={
            "format": "json",
            "itemType": "attachment",
            "limit": 100,
            "start": start,
        })
        batch = resp.json()
        if not batch:
            break
        attachments.extend(batch)
        start += len(batch)
        if len(batch) < 100:
            break

    log.info("Found %d attachment items total", len(attachments))

    # Find orphaned ones: attachments with no file (enclosureType missing or no md5)
    # These are the ones we created but failed to upload to
    for att in attachments:
        data = att.get("data", {})
        # Check if this is a PDF attachment with no actual file content
        if (data.get("contentType") == "application/pdf" 
            and data.get("linkMode") == "imported_file"
            and not data.get("md5", "")):
            try:
                writer._delete(
                    f"/items/{att['key']}",
                    version=data.get("version", att.get("version", 0)),
                )
                orphan_count += 1
            except Exception as e:
                log.warning("Failed to delete orphan %s: %s", att["key"], e)

    log.info("Cleaned up %d orphaned attachment items", orphan_count)

    # Now upload PDFs
    success = 0
    failed = 0
    failed_papers = []

    for i, pid in enumerate(uploadable, 1):
        zkey = key_map[pid]
        pdf_path = pdf_index[pid]
        safe_name = pdf_path.name[:50]

        try:
            result = writer.upload_pdf(zkey, pdf_path)
            if result:
                success += 1
                if i % 25 == 0 or i == len(uploadable):
                    log.info("[%d/%d] Uploaded %d, failed %d", i, len(uploadable), success, failed)
            else:
                failed += 1
                failed_papers.append(pid)
                log.warning("[%d/%d] FAILED: %s (%s)", i, len(uploadable), pid, safe_name)
        except Exception as e:
            failed += 1
            failed_papers.append(pid)
            log.warning("[%d/%d] ERROR %s: %s", i, len(uploadable), pid, str(e)[:100])

    log.info("=== PDF Upload Complete ===")
    log.info("  Uploaded: %d", success)
    log.info("  Failed:   %d", failed)
    log.info("  Total:    %d", len(uploadable))

    if failed_papers:
        log.info("  Failed paper IDs: %s", ", ".join(failed_papers[:20]))

    # Save upload results
    upload_report = {
        "uploaded": success,
        "failed": failed,
        "total": len(uploadable),
        "failed_papers": failed_papers,
    }
    out = ROOT / "08_full_texts" / "pdf_upload_report.json"
    out.write_text(json.dumps(upload_report, indent=2) + "\n", encoding="utf-8")
    log.info("Report saved to %s", out)


if __name__ == "__main__":
    main()
