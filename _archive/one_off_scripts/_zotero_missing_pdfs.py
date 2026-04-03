"""Find Zotero items in 'SLR Results' that have no PDF attachment."""
import csv
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def main():
    from tools.slr_toolkit.zotero_sync import ZoteroWriter

    writer = ZoteroWriter()

    # 1. Find the SLR Results collection
    colls = writer.list_collections()
    slr_key = None
    for c in colls:
        if c.get("data", {}).get("name") == "SLR Results":
            slr_key = c["key"]
            break

    if not slr_key:
        print("ERROR: 'SLR Results' collection not found!")
        return

    # 2. Fetch ALL items in the collection (including attachments)
    log.info("Fetching all items from 'SLR Results' collection...")
    all_items = []
    start = 0
    while True:
        resp = writer._get(f"/collections/{slr_key}/items", params={
            "format": "json", "limit": 100, "start": start,
        })
        batch = resp.json()
        if not batch:
            break
        all_items.extend(batch)
        start += len(batch)
        if len(batch) < 100:
            break

    # 3. Separate parent items from attachments
    parent_items = {}
    attachments_by_parent = {}

    for item in all_items:
        data = item.get("data", {})
        itype = data.get("itemType", "")

        if itype == "attachment":
            parent_key = data.get("parentItem", "")
            if parent_key:
                if parent_key not in attachments_by_parent:
                    attachments_by_parent[parent_key] = []
                attachments_by_parent[parent_key].append(data)
        elif itype == "note":
            continue  # skip notes
        else:
            parent_items[item["key"]] = item

    log.info("Parent items: %d, Attachment items: %d", 
             len(parent_items), sum(len(v) for v in attachments_by_parent.values()))

    # 4. Find items with no PDF attachment
    has_pdf = set()
    for parent_key, atts in attachments_by_parent.items():
        for att in atts:
            if att.get("contentType") == "application/pdf":
                has_pdf.add(parent_key)
                break

    no_pdf_items = []
    for key, item in parent_items.items():
        if key not in has_pdf:
            data = item.get("data", {})
            no_pdf_items.append({
                "zotero_key": key,
                "title": data.get("title", ""),
                "doi": data.get("DOI", ""),
                "year": data.get("date", "")[:4],
                "item_type": data.get("itemType", ""),
            })

    no_pdf_items.sort(key=lambda x: x["title"])

    log.info("Items WITH PDF: %d", len(has_pdf))
    log.info("Items WITHOUT PDF: %d", len(no_pdf_items))

    # 5. Write CSV
    out = ROOT / "08_full_texts" / "zotero_missing_pdfs.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["zotero_key", "title", "doi", "year", "item_type", "doi_url"])
        w.writeheader()
        for item in no_pdf_items:
            item["doi_url"] = f"https://doi.org/{item['doi']}" if item["doi"] else ""
            w.writerow(item)

    # 6. Write HTML
    html_path = ROOT / "08_full_texts" / "zotero_missing_pdfs.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write('<html><head><meta charset="utf-8"><title>Zotero Items Missing PDFs</title></head><body>\n')
        f.write(f"<h1>{len(no_pdf_items)} Zotero Items Missing PDFs</h1>\n")
        f.write(f"<p>Items with PDF: {len(has_pdf)} | Without PDF: {len(no_pdf_items)}</p>\n<ol>\n")
        for item in no_pdf_items:
            doi = item["doi"]
            title = item["title"]
            year = item["year"]
            if doi:
                f.write(f'<li><a href="https://doi.org/{doi}" target="_blank">{title}</a> ({year})</li>\n')
            else:
                f.write(f"<li>{title} ({year}) — no DOI</li>\n")
        f.write("</ol></body></html>\n")

    print(f"\n=== Zotero PDF Status ===")
    print(f"  Total items in SLR Results: {len(parent_items)}")
    print(f"  With PDF attachment: {len(has_pdf)}")
    print(f"  Missing PDF: {len(no_pdf_items)}")
    print(f"\n  CSV:  {out}")
    print(f"  HTML: {html_path}")


if __name__ == "__main__":
    main()
