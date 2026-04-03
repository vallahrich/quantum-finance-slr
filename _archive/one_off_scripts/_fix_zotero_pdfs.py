"""Upload local PDFs to Zotero items that are missing PDF attachments."""
import csv
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def main():
    from tools.slr_toolkit.zotero_sync import ZoteroWriter
    from tools.slr_toolkit import config

    writer = ZoteroWriter()

    # 1. Load the Zotero missing PDFs list we just generated
    missing_csv = ROOT / "08_full_texts" / "zotero_missing_pdfs.csv"
    missing_items: dict[str, dict] = {}  # zotero_key -> {title, doi, ...}
    with open(missing_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            missing_items[row["zotero_key"]] = row

    log.info("Zotero items missing PDFs: %d", len(missing_items))

    # 2. Build a mapping: zotero_key -> paper_id
    # We need to match Zotero items to our local paper_ids
    # Strategy: normalize titles and DOIs from both sides

    # Load master records
    master: dict[str, dict] = {}
    with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            master[row["paper_id"]] = row

    # Build local indices
    doi_to_pid: dict[str, str] = {}
    title_to_pid: dict[str, str] = {}
    for pid, rec in master.items():
        doi = rec.get("doi", "").strip().lower()
        if doi:
            doi_to_pid[doi] = pid
        title = rec.get("title", "").strip().lower()
        if title:
            # Simple normalization
            import re
            norm = re.sub(r"[^a-z0-9]+", " ", title).strip()
            title_to_pid[norm] = pid

    # 3. Build local PDF index
    pdfs_dir = config.FULL_TEXTS_DIR / "pdfs"
    pid_to_pdf: dict[str, Path] = {}

    # From download_log
    with open(config.DOWNLOAD_LOG_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "success" and row.get("filename"):
                p = pdfs_dir / row["filename"]
                if p.is_file():
                    pid_to_pdf[row["paper_id"]] = p

    # Also scan directory
    for pdf_file in pdfs_dir.glob("*.pdf"):
        pid_part = pdf_file.stem.split("_", 1)[0]
        if pid_part not in pid_to_pdf:
            pid_to_pdf[pid_part] = pdf_file

    log.info("Local PDFs available: %d", len(pid_to_pdf))

    # 4. Match Zotero missing items to local paper_ids with PDFs
    import re
    zkey_to_pid: dict[str, str] = {}
    for zkey, item in missing_items.items():
        # Try DOI match
        zdoi = item.get("doi", "").strip().lower()
        if zdoi and zdoi in doi_to_pid:
            zkey_to_pid[zkey] = doi_to_pid[zdoi]
            continue

        # Try title match
        ztitle = item.get("title", "").strip().lower()
        if ztitle:
            norm = re.sub(r"[^a-z0-9]+", " ", ztitle).strip()
            if norm in title_to_pid:
                zkey_to_pid[zkey] = title_to_pid[norm]
                continue

    matched_with_pdf = {zkey: pid for zkey, pid in zkey_to_pid.items() if pid in pid_to_pdf}
    matched_no_pdf = {zkey: pid for zkey, pid in zkey_to_pid.items() if pid not in pid_to_pdf}
    unmatched = set(missing_items.keys()) - set(zkey_to_pid.keys())

    log.info("Matched to paper_id WITH local PDF: %d", len(matched_with_pdf))
    log.info("Matched to paper_id but NO local PDF: %d", len(matched_no_pdf))
    log.info("Could not match to any paper_id: %d", len(unmatched))

    if not matched_with_pdf:
        log.info("No PDFs to upload!")
        return

    # 5. Upload PDFs
    success = 0
    failed = 0
    failed_list = []

    total = len(matched_with_pdf)
    for i, (zkey, pid) in enumerate(sorted(matched_with_pdf.items()), 1):
        pdf_path = pid_to_pdf[pid]
        try:
            result = writer.upload_pdf(zkey, pdf_path)
            if result:
                success += 1
            else:
                failed += 1
                failed_list.append(pid)
        except Exception as e:
            failed += 1
            failed_list.append(pid)
            log.warning("[%d/%d] ERROR %s: %s", i, total, pid, str(e)[:100])

        if i % 20 == 0 or i == total:
            log.info("[%d/%d] Progress: %d uploaded, %d failed", i, total, success, failed)

    log.info("=== Upload Complete ===")
    log.info("  Uploaded: %d", success)
    log.info("  Failed:   %d", failed)
    log.info("  Still missing (no local PDF): %d", len(matched_no_pdf) + len(unmatched))

    # Save report
    out = ROOT / "08_full_texts" / "zotero_pdf_fix_report.json"
    out.write_text(json.dumps({
        "uploaded": success,
        "failed": failed,
        "still_missing_no_local_pdf": len(matched_no_pdf),
        "unmatched": len(unmatched),
        "failed_papers": failed_list,
    }, indent=2) + "\n", encoding="utf-8")
    log.info("Report: %s", out)


if __name__ == "__main__":
    main()
