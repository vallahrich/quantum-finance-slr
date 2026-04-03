"""Retry the 19 papers that failed during initial Zotero sync."""
import csv
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from tools.slr_toolkit.zotero_sync import ZoteroWriter
from tools.slr_toolkit import config

FAILED_IDS = [
    "9b3837c81545", "9b55a2fa0cd5", "9bc9b29fc6af", "9bd4d4752519",
    "aa5b834c3a1d", "aa6714606396", "aa8d930f4f4f", "aa910c409f87",
    "ab43aaeed4af", "ab8ec0885239", "ac9a031452bb", "acc55c7d6a2a",
    "ad0844abb348", "ad79bfb0cfd8", "add09b8c5e11", "ae4cc7b70669",
    "ae6ef4dd0465", "ae8a2fcc480d", "aeba35e547c4",
]

# Load master records
with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
    master = {r["paper_id"]: r for r in csv.DictReader(f) if r["paper_id"] in FAILED_IDS}

# Load PDF index
pdfs_dir = config.FULL_TEXTS_DIR / "pdfs"
pdf_map: dict[str, Path] = {}
with open(config.DOWNLOAD_LOG_CSV, encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row.get("status") == "success" and row.get("filename"):
            p = pdfs_dir / row["filename"]
            if p.is_file():
                pdf_map[row["paper_id"]] = p

writer = ZoteroWriter()
doi_idx, arxiv_idx, title_idx, ay_idx = writer._build_zotero_index()
collection_key = writer.ensure_collection("SLR Results")

created = updated = failed = 0

for pid in FAILED_IDS:
    paper = master.get(pid)
    if not paper:
        print(f"  SKIP {pid}: not in master_records")
        continue

    title = (paper.get("title", pid) or pid)[:60]
    existing, match_method = writer._find_existing_item(paper, doi_idx, arxiv_idx, title_idx, ay_idx)

    if existing:
        zkey = existing["key"]
        print(f"  UPDATE ({match_method}): {pid} - {title}")
        data = existing.get("data", existing)
        version = data.get("version", existing.get("version"))
        existing_cols = set(data.get("collections", []))
        if collection_key not in existing_cols:
            writer._patch(f"/items/{zkey}", {"collections": sorted(existing_cols | {collection_key})}, version)
        updated += 1

        # Upload PDF if available
        if pid in pdf_map:
            print(f"    Uploading PDF...")
            writer.upload_pdf(zkey, pdf_map[pid])
    else:
        print(f"  CREATE: {pid} - {title}")
        item_data = writer._map_paper_to_zotero_data(paper)
        tags = item_data.get("tags", [])
        for t in writer._SLR_TAGS:
            if not any(tag["tag"] == t for tag in tags):
                tags.append({"tag": t})
        item_data["tags"] = tags
        item_data["collections"] = [collection_key]

        try:
            resp = writer._post("/items", [item_data])
            result = resp.json()
            successful = result.get("successful", result.get("success", {}))
            if "0" in successful:
                obj = successful["0"]
                new_key = obj["key"] if isinstance(obj, dict) else obj
                created += 1
                print(f"    Created -> {new_key}")

                # Add child note
                note = writer._create_slr_note(paper, match_method="new")
                note["parentItem"] = new_key
                note["collections"] = [collection_key]
                writer._post("/items", [note])

                # Upload PDF
                if pid in pdf_map:
                    print(f"    Uploading PDF...")
                    writer.upload_pdf(new_key, pdf_map[pid])
            else:
                print(f"    FAILED: {result.get('failed', {})}")
                failed += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            failed += 1

print(f"\nDone: created={created}, updated={updated}, failed={failed}")
