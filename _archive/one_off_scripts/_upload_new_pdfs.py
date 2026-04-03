"""Find new PDFs (not yet uploaded to Zotero) and upload them."""
import csv
import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def main():
    pdfs_dir = ROOT / "08_full_texts" / "pdfs"

    # 1. All PDFs on disk
    all_pdfs = {f.name: f for f in pdfs_dir.glob("*.pdf")}
    log.info("Total PDFs on disk: %d", len(all_pdfs))

    # 2. Load download_log to know which paper_ids already had successful downloads
    dl_log_path = ROOT / "08_full_texts" / "download_log.csv"
    pid_to_file: dict[str, str] = {}
    previously_success: set[str] = set()
    with open(dl_log_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pid_to_file[row["paper_id"]] = row.get("filename", "")
            if row.get("status") == "success":
                previously_success.add(row["paper_id"])

    known_filenames = set(pid_to_file.values())

    # 3. Find new PDFs: on disk but filename not in download_log
    new_files = sorted(set(all_pdfs.keys()) - known_filenames)
    log.info("New PDFs (not in download_log): %d", len(new_files))

    # 4. Also find PDFs where download_log had a failure but PDF now exists
    recovered = []
    for pid, fname in pid_to_file.items():
        if pid not in previously_success and fname and (pdfs_dir / fname).is_file():
            recovered.append(pid)
    log.info("Recovered PDFs (were failed, now on disk): %d", len(recovered))

    # 5. Match new PDFs to paper_ids via filename prefix
    # Filenames follow: {paper_id}_{title_slug}.pdf
    new_pid_to_path: dict[str, Path] = {}
    unmatched = []
    for fname in new_files:
        pid_part = fname.split("_", 1)[0]
        new_pid_to_path[pid_part] = all_pdfs[fname]

    # Also add recovered ones
    for pid in recovered:
        fname = pid_to_file[pid]
        path = pdfs_dir / fname
        if path.is_file():
            new_pid_to_path[pid] = path

    log.info("Total new PDFs to upload: %d", len(new_pid_to_path))

    if not new_pid_to_path:
        log.info("Nothing to upload!")
        return

    # 6. Load sync report to get paper_id -> zotero_key mapping
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

    # If the report was overwritten (only 30 items), we need to look up keys via API
    if len(key_map) < 100:
        log.info("Sync report has only %d keys, will look up via Zotero API...", len(key_map))
        from tools.slr_toolkit.zotero_sync import ZoteroWriter
        writer = ZoteroWriter()
        doi_idx, arxiv_idx, title_idx, ay_idx = writer._build_zotero_index()

        # Load master records for these papers
        from tools.slr_toolkit import config
        master: dict[str, dict] = {}
        with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["paper_id"] in new_pid_to_path:
                    master[row["paper_id"]] = row

        for pid in new_pid_to_path:
            if pid in key_map:
                continue
            paper = master.get(pid)
            if not paper:
                continue
            existing, _ = writer._find_existing_item(paper, doi_idx, arxiv_idx, title_idx, ay_idx)
            if existing:
                key_map[pid] = existing["key"]

    log.info("Zotero keys available for %d / %d new PDFs", 
             sum(1 for pid in new_pid_to_path if pid in key_map), len(new_pid_to_path))

    # 7. Upload
    from tools.slr_toolkit.zotero_sync import ZoteroWriter
    writer = ZoteroWriter()

    success = 0
    failed = 0
    no_key = 0
    failed_papers = []

    for i, (pid, pdf_path) in enumerate(sorted(new_pid_to_path.items()), 1):
        zkey = key_map.get(pid)
        if not zkey:
            no_key += 1
            log.warning("[%d/%d] No Zotero key for %s — skipping", i, len(new_pid_to_path), pid)
            continue

        try:
            result = writer.upload_pdf(zkey, pdf_path)
            if result:
                success += 1
                if i % 10 == 0 or i == len(new_pid_to_path):
                    log.info("[%d/%d] Progress: %d uploaded, %d failed, %d no key",
                             i, len(new_pid_to_path), success, failed, no_key)
            else:
                failed += 1
                failed_papers.append(pid)
        except Exception as e:
            failed += 1
            failed_papers.append(pid)
            log.warning("[%d/%d] ERROR %s: %s", i, len(new_pid_to_path), pid, str(e)[:100])

    # 8. Update download_log for new PDFs
    log.info("Updating download_log.csv for new PDFs...")
    from datetime import datetime
    rows_to_update = {}
    with open(dl_log_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)

    row_by_pid = {r["paper_id"]: r for r in all_rows}
    updated_count = 0
    for pid, pdf_path in new_pid_to_path.items():
        if pid in row_by_pid and row_by_pid[pid].get("status") != "success":
            row_by_pid[pid]["status"] = "success"
            row_by_pid[pid]["filename"] = pdf_path.name
            row_by_pid[pid]["source"] = row_by_pid[pid].get("source", "") or "zotero"
            row_by_pid[pid]["timestamp"] = datetime.now().isoformat(timespec="seconds")
            updated_count += 1

    if updated_count:
        with open(dl_log_path, "w", encoding="utf-8", newline="") as f:
            writer_csv = csv.DictWriter(f, fieldnames=fieldnames)
            writer_csv.writeheader()
            writer_csv.writerows(all_rows)
        log.info("Updated %d rows in download_log.csv", updated_count)

    log.info("=== Upload Complete ===")
    log.info("  Uploaded: %d", success)
    log.info("  Failed:   %d", failed)
    log.info("  No key:   %d", no_key)
    log.info("  Total:    %d", len(new_pid_to_path))

    if failed_papers:
        log.info("  Failed: %s", ", ".join(failed_papers[:20]))

    # Save report
    out = ROOT / "08_full_texts" / "pdf_upload_report.json"
    out.write_text(json.dumps({
        "uploaded": success, "failed": failed, "no_key": no_key,
        "total": len(new_pid_to_path), "failed_papers": failed_papers,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
