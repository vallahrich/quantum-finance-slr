"""Generate missing_pdfs_report.md grouped by publisher with clickable links."""
import csv, re, html
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).parent
LOG_PATH      = ROOT / "07_full_texts/download_log.csv"
INCLUDED_PATH = ROOT / "05_screening/included_for_coding.csv"
MASTER_PATH   = ROOT / "04_deduped_library/master_records.csv"
PDF_DIR       = ROOT / "07_full_texts/pdfs"
REPORT_PATH   = ROOT / "07_full_texts/missing_pdfs_report.md"

def safe(s):
    return html.unescape(str(s)).encode("ascii", "replace").decode()

included_ids = set()
with open(INCLUDED_PATH, encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row.get("final_decision", "").strip().lower() == "include":
            included_ids.add(row["paper_id"])

all_rows: dict[str, list] = defaultdict(list)
with open(MASTER_PATH, encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        all_rows[row["paper_id"]].append(row)

download_log = {}
with open(LOG_PATH, encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        download_log[row["paper_id"]] = row

def file_exists(row):
    fname = row.get("filename", "")
    return bool(fname) and (PDF_DIR / fname).exists()

have_on_disk = {
    pid for pid, row in download_log.items()
    if row.get("status") == "success" and pid in included_ids and file_exists(row)
}
# Also count PDFs on disk whose paper_id matches an included paper
# (covers manually added PDFs not in download_log)
for pdf_path in PDF_DIR.glob("*.pdf"):
    pid = pdf_path.name.split("_")[0]
    if pid in included_ids:
        have_on_disk.add(pid)

# Zenodo records are code repos / datasets / PREreviews — not scientific papers needing a PDF
ZENODO_EXCLUDE = {
    "115e509ec529",  # Hybrid Quantum Market State Inference (Zenodo code/data)
    "89a54b4268bd",  # qaoa_portfolio_optimization.py — QAOA Benchmark code
    "8d58112a9617",  # portfolio_optimizer.py — Disruptive Quantum-Inspired Portfolio Optimizer code
    "251a3166cf94",  # hgribeirogeo/qaoa-carbon-cerrado v1.0 — code repo
    "32f23740c07f",  # hgribeirogeo/qaoa-carbon-cerrado v2.0 — code repo
    "3bd0da5c69ac",  # PREreview of "The Inverse Born Rule Fallacy" — review note
    "9a4ba980a229",  # Quantum Approaches to NP-Hard Combinatorial Optimization — Zenodo preprint
    "b2cc85a6587a",  # QCC Echo: Redacted Results-Only Verification — Zenodo report
    "1dc251ce8c53",  # Extrapolation method to optimize linear-ramp QAOA (Zenodo)
}

missing_pids = sorted(
    pid for pid in included_ids
    if pid not in have_on_disk and pid not in ZENODO_EXCLUDE
)


def classify_publisher(doi):
    if not doi:
        return ("No DOI / Preprint", "none")
    d = doi.lower()
    if "10.48550" in d or "arxiv" in d:  return ("arXiv", "oa")
    if "10.2139/ssrn" in d:              return ("SSRN", "oa")
    if "10.5281/zenodo" in d:            return ("Zenodo", "oa")
    if "10.20944" in d:                  return ("Preprints.org", "oa")
    if "10.36227/techrxiv" in d:         return ("TechRxiv", "oa")
    if "10.13140" in d:                  return ("ResearchGate", "oa")
    if "10.64206" in d:                  return ("Open Access (DOI)", "oa")
    if "10.70088" in d:                  return ("Open Access (DOI)", "oa")
    if "10.25397" in d:                  return ("Open Access (DOI)", "oa")
    if "10.30574" in d:                  return ("WJARR/WJAETS", "oa")
    if "10.32996" in d:                  return ("Open Access (DOI)", "oa")
    if "10.33545" in d:                  return ("Open Access (DOI)", "oa")
    if "10.1103" in d:                   return ("APS (Phys Rev)", "paywalled")
    if "10.1016" in d:                   return ("Elsevier", "paywalled")
    if "10.1007" in d:                   return ("Springer", "paywalled")
    if "10.1109" in d:                   return ("IEEE", "paywalled")
    if "10.1002" in d:                   return ("Wiley", "paywalled")
    if "10.1080" in d:                   return ("Taylor & Francis", "paywalled")
    if "10.1201" in d:                   return ("CRC Press", "paywalled")
    if "10.4324" in d:                   return ("Routledge", "paywalled")
    if "10.4018" in d:                   return ("IGI Global", "paywalled")
    if "10.1142" in d:                   return ("World Scientific", "paywalled")
    if "10.1515" in d:                   return ("De Gruyter", "paywalled")
    if "10.1088" in d:                   return ("IOP Publishing", "paywalled")
    if "10.1364" in d:                   return ("Optica/OSA", "paywalled")
    if "10.2523" in d:                   return ("SPE/IPTC", "paywalled")
    if "10.54946" in d:                  return ("Wilmott", "paywalled")
    if "10.5220" in d:                   return ("SCITEPRESS", "paywalled")
    if "10.17771" in d:                  return ("PUC-Rio", "paywalled")
    if "10.5573" in d:                   return ("IEIE", "paywalled")
    if "10.1504" in d:                   return ("Inderscience", "paywalled")
    if "10.1117" in d:                   return ("SPIE", "paywalled")
    if "10.53759" in d:                  return ("TowardsAI", "paywalled")
    if "10.6914" in d:                   return ("QSS", "paywalled")
    if "10.36676" in d:                  return ("Open Access (DOI)", "oa")
    if "10.15408" in d:                  return ("Open Access (DOI)", "oa")
    if "10.22541" in d:                  return ("Authorea", "oa")
    return ("Other", "unknown")


def make_primary_link(doi):
    if not doi:
        return ""
    d = doi.lower()
    if "10.48550" in d or "arxiv" in d:
        m = re.search(r"(\d{4}\.\d{4,5})", doi)
        if m:
            return f"[arXiv:{m.group(1)}](https://arxiv.org/abs/{m.group(1)})"
    if "10.2139/ssrn" in d:
        sid = doi.split("ssrn.")[-1].strip()
        return f"[SSRN:{sid}](https://papers.ssrn.com/sol3/papers.cfm?abstract_id={sid})"
    if "10.5281/zenodo" in d:
        zid = re.search(r"zenodo\.(\d+)", d)
        zid_str = zid.group(1) if zid else ""
        return f"[Zenodo:{zid_str}](https://zenodo.org/record/{zid_str})"
    return f"[{doi}](https://doi.org/{doi})"


def alt_links(pid, primary_doi):
    links = []
    seen = {primary_doi.lower()} if primary_doi else set()
    for r in all_rows[pid]:
        d = r.get("doi", "").strip()
        if not d or d.lower() in seen:
            continue
        seen.add(d.lower())
        dl = d.lower()
        if "10.48550" in dl or "arxiv" in dl:
            m = re.search(r"(\d{4}\.\d{4,5})", d)
            if m:
                links.append(f"[arXiv:{m.group(1)}](https://arxiv.org/abs/{m.group(1)})")
        elif "10.2139/ssrn" in dl:
            sid = d.split("ssrn.")[-1].strip()
            links.append(f"[SSRN:{sid}](https://papers.ssrn.com/sol3/papers.cfm?abstract_id={sid})")
        elif "10.5281/zenodo" in dl:
            zid = re.search(r"zenodo\.(\d+)", dl)
            if zid:
                links.append(f"[Zenodo:{zid.group(1)}](https://zenodo.org/record/{zid.group(1)})")
        elif "10.20944" in dl:
            links.append(f"[Preprints.org](https://doi.org/{d})")
        elif "10.13140" in dl:
            links.append(f"[ResearchGate](https://doi.org/{d})")
    return links


# Known arXiv alternatives — verified via web search
KNOWN_ALT_ARXIV = {
    "0067a26ce270": "2111.15332",  # Quantum algorithm for stochastic optimal stopping
    "0608ad48d5b8": "2101.04023",  # Pricing financial derivatives with exponential quantum speedup
    "1312e9d3c55e": "2511.14786",  # Hybrid Quantum-Classical Machine Learning with PennyLane
    "1d16f793a68b": "2212.04209",  # Quantum neural network for continuous variable prediction
    "4dc6746d80a2": "1906.08108",  # Uncertainty and symmetry bound for quantum walks
    "4de005c12725": "2304.08793",  # Automated Function Implementation via Conditional Parameterized QC (Wolf)
    "3f4c5ad6749d": "1912.01618",  # Quantum unary approach to option pricing (APS, Phys Rev A)
    "86891f250a78": "2307.00908",  # QML on near-term quantum devices (APS, Phys Rev Applied)
    "cde1c896dc3c": "2109.04298",  # Quantum Machine Learning for Finance (primary IS arXiv)
    # Not confirmed open access — no preprint found:
    # 3a3ba897009d  QAOA applied to portfolio optimization
    # 8bb680c2fb8b  Quantum computing: Challenges and opportunities (IEEE conference)
    # fa9e2c7101b8  QAOA Applications in Finance (APS abstract only)
    # e505ff143d95  QML and Optimisation in Finance (Packt book)
    # ba5afbcce6b8  QML and Optimisation in Finance T&F (book review, no preprint)
    # 7e22c616ae62  Portfolio Optimization: Applications in QC (Wiley 2016 chapter)
    # 46e6281cc0ea  A quantum feature selection framework (IOP, no preprint)
}

# Build per-paper data
papers_data = []
for pid in missing_pids:
    rows = all_rows[pid]
    meta = rows[0]
    title = safe(meta.get("title", ""))
    year  = meta.get("year", "")
    log_status = download_log.get(pid, {}).get("status", "never_attempted")

    all_dois = []
    seen_d: set = set()
    for r in rows:
        d = r.get("doi", "").strip()
        if d and d.lower() not in seen_d:
            all_dois.append(d)
            seen_d.add(d.lower())

    primary_doi = all_dois[0] if all_dois else ""
    pub, pub_type = classify_publisher(primary_doi)
    primary_link = make_primary_link(primary_doi)
    alts = alt_links(pid, primary_doi)

    # Inject known arXiv alternative
    if pid in KNOWN_ALT_ARXIV:
        arxiv_id = KNOWN_ALT_ARXIV[pid]
        arxiv_link = f"[arXiv:{arxiv_id}](https://arxiv.org/abs/{arxiv_id})"
        # If primary is already arXiv, skip; else add as alt
        if "arxiv" not in primary_doi.lower() and "10.48550" not in primary_doi.lower():
            if arxiv_link not in alts:
                alts.insert(0, arxiv_link)
        else:
            primary_link = arxiv_link  # make it the primary link

    papers_data.append({
        "pid": pid, "title": title, "year": year,
        "pub": pub, "pub_type": pub_type,
        "primary_doi": primary_doi,
        "primary_link": primary_link,
        "alts": alts,
        "status": log_status,
    })

by_pub: dict[str, list] = defaultdict(list)
for p in papers_data:
    by_pub[p["pub"]].append(p)

pub_order_oa    = sorted([k for k in by_pub if by_pub[k][0]["pub_type"] == "oa"],        key=lambda k: -len(by_pub[k]))
pub_order_pw    = sorted([k for k in by_pub if by_pub[k][0]["pub_type"] == "paywalled"],  key=lambda k: -len(by_pub[k]))
pub_order_other = sorted([k for k in by_pub if by_pub[k][0]["pub_type"] not in ("oa","paywalled")], key=lambda k: -len(by_pub[k]))
pub_order = pub_order_oa + pub_order_pw + pub_order_other

lines = []
lines.append("# Missing PDFs Report")
lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
lines.append("")
lines.append("## Summary")
lines.append(f"- Included papers: **{len(included_ids)}**")
lines.append(f"- PDFs on disk: **{len(have_on_disk)}**")
lines.append(f"- Zenodo code/data records excluded (not scientific papers): **{len(ZENODO_EXCLUDE)}**")
lines.append(f"- Still missing: **{len(missing_pids)}**")
lines.append("")
lines.append("### Missing by publisher")
lines.append("")
lines.append("| Publisher | Count | Access |")
lines.append("|-----------|-------|--------|")
for pub in pub_order:
    count = len(by_pub[pub])
    pts = by_pub[pub][0]["pub_type"]
    access = "Open Access" if pts == "oa" else ("Paywalled" if pts == "paywalled" else "Unknown")
    lines.append(f"| {pub} | {count} | {access} |")
lines.append("")
lines.append("---")
lines.append("")

for pub in pub_order:
    papers = sorted(by_pub[pub], key=lambda p: p["year"])
    pts = papers[0]["pub_type"]
    access_label = "Open Access" if pts == "oa" else ("Paywalled" if pts == "paywalled" else "")
    lines.append(f"## {pub} ({len(papers)}) — {access_label}")
    lines.append("")
    for p in papers:
        lines.append(f"### {p['title']}")
        lines.append(f"- **paper_id:** `{p['pid']}`")
        lines.append(f"- **year:** {p['year']}")
        lines.append(f"- **status:** `{p['status']}`")
        if p["primary_link"]:
            lines.append(f"- **link:** {p['primary_link']}")
        if p["alts"]:
            lines.append(f"- **alternatives:** {' · '.join(p['alts'])}")
        lines.append("")

REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Report written: {len(missing_pids)} missing, {len(pub_order)} publisher groups")
for pub in pub_order:
    print(f"  [{by_pub[pub][0]['pub_type']:10s}] {pub}: {len(by_pub[pub])}")
