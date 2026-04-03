import json

d = json.loads(open("08_full_texts/_upload_all_checkpoint.json").read())
print("=== FINAL RESULTS ===")
print(f"Total processed: {len(d['done'])} / 690")
print(f"Replaced (already had file on Zotero): {len(d['replaced'])}")
print(f"Uploaded to existing attachment: {len(d['uploaded_existing'])}")
print(f"Uploaded as new attachment: {len(d['uploaded_new'])}")
print(f"Failed: {len(d['failed'])}")
print(f"No parent found: {len(d['no_parent'])}")
print(f"Skipped: {len(d['skipped'])}")
print(f"Compression savings: {d['bytes_saved']/1024/1024:.0f} MB")
print()
total_uploaded = len(d["replaced"]) + len(d["uploaded_existing"]) + len(d["uploaded_new"])
print(f"TOTAL UPLOADED: {total_uploaded}")
print(f"NOT UPLOADED: {len(d['no_parent'])} (no Zotero parent item)")
if d.get("no_parent"):
    print("No-parent files:")
    for f in d["no_parent"]:
        print(f"  {f}")
