"""Quick Zotero stats check."""
from tools.slr_toolkit.zotero_sync import ZoteroWriter

w = ZoteroWriter()
items = w.get_all_items()
print(f"Total Zotero items (non-attachment): {len(items)}")

resp_att = w._get("/items", params={"format": "json", "itemType": "attachment", "limit": 1})
att_total = int(resp_att.headers.get("Total-Results", 0))
print(f"Attachment items: {att_total}")

colls = w.list_collections()
for c in colls:
    if c.get("data", {}).get("name") == "SLR Results":
        key = c["key"]
        resp = w._get(f"/collections/{key}/items", params={"limit": 1})
        total = int(resp.headers.get("Total-Results", 0))
        print(f"Items in 'SLR Results' collection: {total}")
        break
