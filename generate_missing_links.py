"""Generate an HTML file with DOI links for manual/browser-based download.

Papers with DOIs that failed OA download can be accessed via CBS institutional
access. Open the HTML file in a browser while on CBS network or VPN.
"""
import csv
from pathlib import Path
from html import escape

LOG_CSV = Path("08_full_texts/download_log.csv")
MASTER_CSV = Path("04_deduped_library/master_records.csv")
OUTPUT_HTML = Path("08_full_texts/missing_pdfs_doi_links.html")
OUTPUT_CSV = Path("08_full_texts/missing_pdfs.csv")

# Get latest status per paper
log = list(csv.DictReader(open(LOG_CSV, encoding="utf-8")))
latest = {}
for r in log:
    latest[r["paper_id"]] = r
failed_ids = {pid for pid, r in latest.items() if r["status"] != "success"}

# Load master for metadata
master = {}
with open(MASTER_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        master[row["paper_id"].strip()] = row

# Build list of papers with DOIs
papers_with_doi = []
papers_no_doi = []
for pid in sorted(failed_ids):
    m = master.get(pid, {})
    doi = m.get("doi", "").strip()
    title = m.get("title", "Unknown")
    year = m.get("year", "")
    venue = m.get("venue", "")
    if doi:
        papers_with_doi.append({"pid": pid, "doi": doi, "title": title, "year": year, "venue": venue})
    else:
        papers_no_doi.append({"pid": pid, "title": title, "year": year, "venue": venue})

# ── Generate HTML ──
style_block = (
    "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;"
    " max-width: 1100px; margin: 0 auto; padding: 20px; }\n"
    "  h1 { color: #1a365d; }\n"
    "  .stats { background: #f0f4f8; padding: 15px; border-radius: 8px; margin: 20px 0; }\n"
    "  table { border-collapse: collapse; width: 100%%; margin-top: 20px; }\n"
    "  th { background: #2d3748; color: white; padding: 10px; text-align: left; position: sticky; top: 0; }\n"
    "  td { padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }\n"
    "  tr:hover { background: #edf2f7; }\n"
    "  a { color: #2b6cb0; text-decoration: none; }\n"
    "  a:hover { text-decoration: underline; }\n"
    "  .checkbox { width: 20px; }\n"
    "  .instructions { background: #fffbeb; border-left: 4px solid #d69e2e; padding: 15px; margin: 20px 0; }\n"
    "  .no-doi { background: #fff5f5; border-left: 4px solid #e53e3e; padding: 15px; margin: 20px 0; }\n"
)
html_parts = [
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
    '<title>Missing PDFs - CBS Library Access</title>\n'
    '<style>\n  %s</style>\n</head>\n<body>\n' % style_block,
    '<h1>Missing PDFs for Full-Text Screening</h1>\n',
    '<div class="stats">\n'
    '  <strong>Summary:</strong> %d papers with DOI links | %d papers without DOI (need title search)<br>\n'
    '  <strong>Total missing:</strong> %d / 875 included papers\n'
    '</div>\n' % (len(papers_with_doi), len(papers_no_doi), len(failed_ids)),
    '<div class="instructions">\n'
    '  <strong>How to use:</strong><br>\n'
    '  1. Connect to CBS network or VPN<br>\n'
    '  2. Click each DOI link — it will resolve to the publisher with your institutional access<br>\n'
    '  3. Download the PDF and save to <code>08_full_texts/pdfs/</code> with filename: <code>{paper_id}_{short_title}.pdf</code><br>\n'
    '  4. Check the box when done<br><br>\n'
    '  <strong>Tip:</strong> If a DOI link doesn\'t give you access, try searching the title in '
    '<a href="https://libsearch.cbs.dk" target="_blank">CBS Libsearch</a>\n'
    '</div>\n',
    '<h2>Papers with DOI (%d)</h2>\n' % len(papers_with_doi),
    '<table>\n<tr><th class="checkbox">Done</th><th>#</th><th>Paper ID</th><th>Year</th>'
    '<th>Title</th><th>DOI Link</th></tr>\n',
]

for i, p in enumerate(papers_with_doi, 1):
    doi_url = "https://doi.org/" + p["doi"] if not p["doi"].startswith("http") else p["doi"]
    html_parts.append(
        '<tr><td><input type="checkbox"></td><td>%d</td><td>%s</td><td>%s</td>'
        '<td>%s</td><td><a href="%s" target="_blank">%s</a></td></tr>\n'
        % (i, escape(p["pid"][:12]), escape(p["year"]),
           escape(p["title"][:100]), escape(doi_url), escape(p["doi"][:50]))
    )

html_parts.append("</table>\n")

if papers_no_doi:
    html_parts.append("""
<div class="no-doi">
<h2>Papers WITHOUT DOI (%d) — search by title in <a href="https://libsearch.cbs.dk" target="_blank">Libsearch</a></h2>
</div>
<table>
<tr><th class="checkbox">✓</th><th>#</th><th>Paper ID</th><th>Year</th><th>Title</th><th>Search</th></tr>
""" % len(papers_no_doi))
    for i, p in enumerate(papers_no_doi, 1):
        search_url = "https://libsearch.cbs.dk/discovery/search?query=any,contains,%s&vid=45KBDK_CBS:CBS" % escape(p["title"][:60].replace(" ", "+"))
        html_parts.append(
            '<tr><td><input type="checkbox"></td><td>%d</td><td>%s</td><td>%s</td>'
            '<td>%s</td><td><a href="%s" target="_blank">Search</a></td></tr>\n'
            % (i, escape(p["pid"][:12]), escape(p["year"]),
               escape(p["title"][:100]), escape(search_url))
        )
    html_parts.append("</table>\n")

html_parts.append("</body></html>")

OUTPUT_HTML.write_text("".join(html_parts), encoding="utf-8")
print("Wrote: %s" % OUTPUT_HTML)

# ── Also write CSV for reference ──
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["paper_id", "title", "year", "venue", "doi", "doi_url", "has_doi"])
    for p in papers_with_doi:
        doi_url = "https://doi.org/" + p["doi"] if not p["doi"].startswith("http") else p["doi"]
        writer.writerow([p["pid"], p["title"], p["year"], p["venue"], p["doi"], doi_url, "yes"])
    for p in papers_no_doi:
        writer.writerow([p["pid"], p["title"], p["year"], p["venue"], "", "", "no"])

print("Wrote: %s" % OUTPUT_CSV)
print()
print("With DOI: %d" % len(papers_with_doi))
print("No DOI:   %d" % len(papers_no_doi))
print("Total:    %d" % len(failed_ids))
