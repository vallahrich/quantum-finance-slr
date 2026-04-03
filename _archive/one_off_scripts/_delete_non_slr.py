"""Delete all Zotero items NOT in the 'SLR Results' collection.

Fetches all items in the group library, fetches all items in the
'SLR Results' collection, computes the difference, and batch-deletes
(including child attachments) any item not in SLR Results.
"""

import logging
import os
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    from pathlib import Path

    d = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = d / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break
        d = d.parent
except ImportError:
    pass

API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "6475432")

if not API_KEY:
    raise SystemExit("ZOTERO_API_KEY not set")

BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {
    "Zotero-API-Key": API_KEY,
    "Zotero-API-Version": "3",
}
READ_DELAY = 0.2
WRITE_DELAY = 1.0


def _paginated_get(path, params=None):
    """Fetch all items from a paginated Zotero endpoint."""
    params = dict(params or {})
    params.setdefault("format", "json")
    params.setdefault("limit", 100)
    params["start"] = 0
    items = []
    last_version = None
    while True:
        time.sleep(READ_DELAY)
        for attempt in range(5):
            try:
                r = requests.get(
                    f"{BASE_URL}{path}", headers=HEADERS,
                    params=params, timeout=60,
                )
                if r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", 10))
                    log.warning("Rate limited, waiting %ds...", wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt < 4:
                    log.warning("Request failed (attempt %d): %s", attempt + 1, e)
                    time.sleep(5 * (attempt + 1))
                else:
                    raise
        batch = r.json()
        if not batch:
            break
        items.extend(batch)
        last_version = int(r.headers.get("Last-Modified-Version", 0))
        total = int(r.headers.get("Total-Results", 0))
        params["start"] += len(batch)
        log.info("  fetched %d / %d from %s", params["start"], total, path)
        if params["start"] >= total:
            break
    return items, last_version


def _batch_delete(keys, last_version):
    """Delete items in batches of 50. Returns updated library version."""
    for i in range(0, len(keys), 50):
        chunk = keys[i : i + 50]
        h = {**HEADERS, "If-Unmodified-Since-Version": str(last_version)}
        time.sleep(WRITE_DELAY)
        r = requests.delete(
            f"{BASE_URL}/items",
            headers=h,
            params={"itemKey": ",".join(chunk)},
            timeout=60,
        )
        if r.status_code == 412:
            log.error("Version conflict deleting batch %d–%d. Re-run script.", i, i + len(chunk))
            raise SystemExit(1)
        r.raise_for_status()
        last_version = int(r.headers.get("Last-Modified-Version", last_version))
        log.info("Deleted batch %d–%d (%d items)", i, i + len(chunk), len(chunk))
    return last_version


def main():
    # 1. Find 'SLR Results' collection
    colls, _ = _paginated_get("/collections")
    slr_key = None
    for c in colls:
        if c.get("data", {}).get("name") == "SLR Results":
            slr_key = c["key"]
            break
    if not slr_key:
        raise SystemExit("Could not find 'SLR Results' collection!")
    log.info("SLR Results collection key: %s", slr_key)

    # 2. Fetch ALL items in SLR Results collection (including attachments)
    slr_items, _ = _paginated_get(f"/collections/{slr_key}/items")
    slr_keys = {item["key"] for item in slr_items}
    log.info("Items in SLR Results: %d", len(slr_keys))

    # 3. Fetch ALL items in the entire library (all types)
    all_items, lib_version = _paginated_get("/items")
    log.info("Total items in library: %d", len(all_items))

    # 4. Build parent→children map so we keep children of SLR parents
    parent_of = {}  # child_key -> parent_key
    for item in all_items:
        parent_key = item.get("data", {}).get("parentItem")
        if parent_key:
            parent_of[item["key"]] = parent_key

    # 5. Determine which items to keep:
    #    - Any item directly in SLR Results collection
    #    - Any child (attachment/note) whose parent is in SLR Results
    keep_keys = set(slr_keys)
    for item in all_items:
        parent_key = parent_of.get(item["key"])
        if parent_key and parent_key in keep_keys:
            keep_keys.add(item["key"])

    # 6. Items to delete = all minus keep
    delete_keys = [item["key"] for item in all_items if item["key"] not in keep_keys]
    log.info("Items to DELETE: %d", len(delete_keys))

    if not delete_keys:
        log.info("Nothing to delete — all items are in SLR Results.")
        return

    # 7. Confirm before proceeding
    print(f"\n{'='*60}")
    print(f"  WILL DELETE {len(delete_keys)} items from Zotero group {GROUP_ID}")
    print(f"  KEEPING {len(keep_keys)} items (SLR Results + their attachments)")
    print(f"{'='*60}")
    answer = input("\nType 'yes' to confirm deletion: ").strip().lower()
    if answer != "yes":
        print("Aborted.")
        return

    # 8. Delete children first (attachments/notes), then parents
    children_to_delete = [k for k in delete_keys if k in parent_of]
    parents_to_delete = [k for k in delete_keys if k not in parent_of]

    if children_to_delete:
        log.info("Deleting %d child items (attachments/notes)...", len(children_to_delete))
        lib_version = _batch_delete(children_to_delete, lib_version)

    if parents_to_delete:
        log.info("Deleting %d parent items...", len(parents_to_delete))
        lib_version = _batch_delete(parents_to_delete, lib_version)

    log.info("Done! Deleted %d items total.", len(delete_keys))


if __name__ == "__main__":
    main()
