"""Generate list of papers still missing PDFs."""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
pdfs_dir = ROOT / "08_full_texts" / "pdfs"

# Papers with PDFs
pdf_pids = {f.stem.split("_", 1)[0] for f in pdfs_dir.glob("*.pdf")}
dl_success = set()
with open(ROOT / "08_full_texts/download_log.csv", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row.get("status") == "success":
            dl_success.add(row["paper_id"])
have_pdf = pdf_pids | dl_success

# Included papers
included = set()
with open(ROOT / "05_screening/included_for_coding.csv", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row.get("final_decision") == "include":
            included.add(row["paper_id"])

missing_pids = sorted(included - have_pdf)

# Load metadata
master = {}
with open(ROOT / "04_deduped_library/master_records.csv", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row["paper_id"] in missing_pids:
            master[row["paper_id"]] = row

print(f"Included: {len(included)}, Have PDF: {len(included & have_pdf)}, Missing: {len(missing_pids)}")

# Write CSV
out = ROOT / "08_full_texts" / "missing_pdfs.csv"
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["paper_id", "title", "doi", "doi_url", "venue", "year"])
    for pid in missing_pids:
        r = master.get(pid, {})
        doi = r.get("doi", "")
        doi_url = f"https://doi.org/{doi}" if doi else ""
        w.writerow([pid, r.get("title", ""), doi, doi_url, r.get("venue", ""), r.get("year", "")])
print(f"CSV: {out}")

# Write HTML
html_path = ROOT / "08_full_texts" / "missing_pdfs_doi_links.html"
with open(html_path, "w", encoding="utf-8") as f:
    f.write('<html><head><meta charset="utf-8"><title>Missing PDFs</title></head><body>\n')
    f.write(f"<h1>{len(missing_pids)} Papers Missing PDFs</h1><ol>\n")
    for pid in missing_pids:
        r = master.get(pid, {})
        doi = r.get("doi", "")
        title = r.get("title", pid)
        year = r.get("year", "")
        if doi:
            f.write(f'<li><a href="https://doi.org/{doi}" target="_blank">{title}</a> ({year})</li>\n')
        else:
            f.write(f"<li>{title} ({year}) — no DOI</li>\n")
    f.write("</ol></body></html>\n")
print(f"HTML: {html_path}")

# Write RIS
ris_path = ROOT / "08_full_texts" / "missing_pdfs_zotero.ris"
with open(ris_path, "w", encoding="utf-8") as f:
    for pid in missing_pids:
        r = master.get(pid, {})
        f.write("TY  - JOUR\n")
        f.write(f"TI  - {r.get('title', '')}\n")
        for author in r.get("authors", "").split(";"):
            author = author.strip()
            if author:
                f.write(f"AU  - {author}\n")
        f.write(f"PY  - {r.get('year', '')}\n")
        if r.get("venue"):
            f.write(f"JO  - {r.get('venue', '')}\n")
        if r.get("doi"):
            f.write(f"DO  - {r.get('doi', '')}\n")
        f.write(f"N1  - paper_id:{pid}\n")
        f.write("ER  - \n\n")
print(f"RIS: {ris_path}")

# Summary
venues = Counter()
for pid in missing_pids:
    r = master.get(pid, {})
    v = (r.get("venue", "") or "unknown").split("(")[0].strip()[:40]
    venues[v] += 1

has_doi = sum(1 for pid in missing_pids if master.get(pid, {}).get("doi"))
print(f"\nHave DOI: {has_doi}/{len(missing_pids)}")
print("\nMissing by venue (top 15):")
for v, c in venues.most_common(15):
    print(f"  {c:3d}  {v}")
