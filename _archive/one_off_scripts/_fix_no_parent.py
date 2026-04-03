"""Find Zotero parents for the 3 no-parent PDFs and upload them."""
import csv
import re
import os
import sys
import time
import hashlib
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_KEY = os.environ.get("ZOTERO_API_KEY", "")
GROUP_ID = os.environ.get("ZOTERO_GROUP_ID", "")
BASE_URL = f"https://api.zotero.org/groups/{GROUP_ID}"
HEADERS = {"Zotero-API-Key": API_KEY, "Zotero-API-Version": "3"}

NO_PARENT_FILES = [
    "c945ded90aa0_efficient_option_pricing_with_unary_based_photonic_computing_chip_and_generative.pdf",
    "1c4934de7d9a_the_application_of_quantum_approximation_optimization_algorithm_in_portfolio_opt.pdf",
    "c07bf2c04ef9_corrections_to_enhancing_knapsack_based_financial_portfolio_optimization_using_q.pdf",
]


def find_parent_fuzzy(title):
    """Search Zotero by title keywords with multiple search strategies."""
    # Try progressively broader searches
    for num_words in [6, 4, 3]:
        words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", "", title).split() if len(w) > 2][:num_words]
        q = " ".join(words)
        r = requests.get(f"{BASE_URL}/items", headers=HEADERS,
                         params={"q": q, "limit": 10, "format": "json"}, timeout=30)
        for it in r.json():
            d = it["data"]
            if d.get("itemType") != "attachment":
                t1 = re.sub(r"[^a-z0-9]", "", title.lower())
                t2 = re.sub(r"[^a-z0-9]", "", d.get("title", "").lower())
                # Accept if first 30 chars match or significant overlap
                if (t1[:30] == t2[:30] or t2[:30] in t1 or t1[:30] in t2
                        or len(set(t1.split()) & set(t2.split())) > 3):
                    return d["key"], d.get("title", "")
    return None, None


def create_attachment_and_upload(parent_key, pdf_path):
    """Create attachment and upload PDF."""
    filename = pdf_path.name
    attach_data = [{
        "itemType": "attachment",
        "parentItem": parent_key,
        "linkMode": "imported_file",
        "title": filename,
        "contentType": "application/pdf",
        "filename": filename,
        "tags": [],
    }]
    time.sleep(1.1)
    resp = requests.post(f"{BASE_URL}/items", headers=HEADERS, json=attach_data, timeout=30)
    result = resp.json()
    successful = result.get("successful", result.get("success", {}))
    if "0" not in successful:
        print(f"  Failed to create attachment: {result.get('failed', {})}")
        return False
    obj = successful["0"]
    attach_key = obj["key"] if isinstance(obj, dict) else obj

    # Upload file
    file_bytes = pdf_path.read_bytes()
    md5 = hashlib.md5(file_bytes).hexdigest()
    mtime = int(pdf_path.stat().st_mtime * 1000)
    url = f"{BASE_URL}/items/{attach_key}/file"
    auth_body = f"md5={md5}&filename={filename}&filesize={len(file_bytes)}&mtime={mtime}"
    time.sleep(1.1)
    resp = requests.post(url, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                                       "If-None-Match": "*"}, data=auth_body, timeout=30)
    if resp.status_code != 200:
        print(f"  Auth failed: {resp.status_code}")
        return False
    auth_data = resp.json()
    if auth_data.get("exists"):
        return True

    upload_body = (auth_data.get("prefix", "").encode("latin-1") +
                   file_bytes + auth_data.get("suffix", "").encode("latin-1"))
    s3 = requests.post(auth_data["url"],
                       headers={"Content-Type": auth_data.get("contentType", "application/pdf")},
                       data=upload_body, timeout=180)
    if s3.status_code not in (200, 201, 204):
        print(f"  S3 failed: {s3.status_code}")
        return False

    time.sleep(1.1)
    reg = requests.post(url, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                                      "If-None-Match": "*"},
                        data=f"upload={auth_data['uploadKey']}", timeout=30)
    return reg.status_code == 204


def main():
    if not API_KEY or not GROUP_ID:
        sys.exit("Set ZOTERO_API_KEY and ZOTERO_GROUP_ID")

    records = {}
    with open(ROOT / "04_deduped_library" / "master_records.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            records[row["paper_id"]] = row

    for fn in NO_PARENT_FILES:
        pid = fn.split("_")[0]
        rec = records.get(pid)
        pdf_path = ROOT / "08_full_texts" / "pdfs" / fn
        if not pdf_path.exists():
            print(f"SKIP {fn} - file not found")
            continue

        title = rec.get("title", "") if rec else ""
        print(f"\n{fn}")
        print(f"  Title: {title}")

        parent_key, matched_title = find_parent_fuzzy(title)
        if parent_key:
            print(f"  Found parent: {parent_key} - {matched_title[:60]}")
            ok = create_attachment_and_upload(parent_key, pdf_path)
            print(f"  Upload: {'OK' if ok else 'FAILED'}")
        else:
            print(f"  No parent found via fuzzy search either")
            # Try broader search with fewer words
            words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", "", title).split() if len(w) > 3][:3]
            q = " ".join(words)
            print(f"  Trying broader search: {q}")
            r = requests.get(f"{BASE_URL}/items", headers=HEADERS,
                             params={"q": q, "limit": 5, "format": "json"}, timeout=30)
            for it in r.json():
                d = it["data"]
                if d.get("itemType") != "attachment":
                    print(f"    Candidate: {d['key']} - {d.get('title', '')[:80]}")


if __name__ == "__main__":
    main()
