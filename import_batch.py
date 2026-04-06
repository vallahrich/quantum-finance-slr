"""Import batch of manually downloaded PDFs from downloadedpdf/ into pdfs/."""
import csv, re, shutil
from pathlib import Path
from datetime import datetime
import pypdf
from rapidfuzz import fuzz

ROOT = Path(".")
PDF_DIR = ROOT / "07_full_texts/pdfs"
DL_DIR = ROOT / "07_full_texts/downloadedpdf"
LOG_PATH = ROOT / "07_full_texts/download_log.csv"
INCLUDED_PATH = ROOT / "05_screening/included_for_coding.csv"
MASTER_PATH = ROOT / "04_deduped_library/master_records.csv"
LOG_COLUMNS = ["paper_id","title","doi","source","pdf_url","status","filename","timestamp"]

def sanitise(t):
    return re.sub(r'[^a-z0-9]+','_',t.lower()).strip('_')[:80]

def norm(t):
    return re.sub(r'[^a-z0-9 ]+', ' ', t.lower()).strip()

def safe(s):
    return str(s).encode('ascii','replace').decode()

def csv_escape(v):
    v = str(v)
    return ('"'+v.replace('"','""')+'"') if any(c in v for c in (',','"','\n')) else v

# Load included IDs
included_ids = set()
with open(INCLUDED_PATH, encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        if row.get('final_decision','').strip().lower() == 'include':
            included_ids.add(row['paper_id'])

# Load ALL master records (multiple rows per pid possible - collect ALL DOIs)
papers = {}
doi_to_pid = {}
with open(MASTER_PATH, encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        pid = row['paper_id']
        if pid not in included_ids:
            continue
        papers[pid] = row  # last row wins for metadata
        doi = row.get('doi','').strip().lower()
        if doi:
            doi_to_pid[doi] = pid

# Load download log
download_log = {}
with open(LOG_PATH, encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        download_log[row['paper_id']] = row

have_success = {pid for pid,r in download_log.items() if r.get('status')=='success'}
missing_pids = {pid for pid in included_ids if pid not in have_success}

# Title lookup (missing only)
title_to_pid = {}
for pid in missing_pids:
    t = norm(papers[pid].get('title',''))
    if t:
        title_to_pid[t] = pid

DOI_PAT = re.compile(r'10\.\d{4,}/\S{3,60}')

def extract_text(pdf_path, pages=8):
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        text = ''
        for page in reader.pages[:pages]:
            text += (page.extract_text() or '') + '\n'
        return text
    except Exception:
        return ''

def extract_dois(text):
    return [d.rstrip('.,);/>') for d in DOI_PAT.findall(text)]

# Hard-coded matches from manual text analysis
MANUAL_MATCHES = {
    "2304.08793v1": "afa84e1d94cf",
    "1-24-Comparative-Study-of-Classical-and-Quantum-Machine": "0d70169cb87f",
    "5-25-Reinforcement-Learning": "ef9db5fc8faa",
    "4-Quantum-Enhanced-Graph-Analytics": "cf9049abcad1",
    "AutonomousQuantumAgentsforPortfolioOptimization-OrchestratingQAOAWorkflowsonCloudQuantumSimulators": "1858371f4c44",
    "Quantum_Algorithms_for_Stochastic_Differ": "2b4dc3c2ba75",
}

# Files confirmed NOT in SLR (skip silently)
NOT_IN_SLR = {
    "TESIS JAVIER GONZALEZ CONDE",
    "Designing_PSS_and_SVC_Parameters_simulta",
    "QSS010104 (1)",
    "rf_aiinassetmanagement_practitioner-briefs_09_quantumcomputingforfinance_online",
    "The_Potential_of_Quantum_Techniques_for_Stock_Price_Prediction",
    "2-25-AI-Data-Science-and-Quantum-Neural-Networks (1)",
    "2302.12291v1",  # different paper (QUBO for Sharpe Ratio - different arxiv ID than included one)
}

pdfs = sorted(DL_DIR.glob('*.pdf'))
print(f"Processing {len(pdfs)} PDFs in downloadedpdf/")
print(f"Missing papers: {len(missing_pids)}")

results = []
for pdf_path in pdfs:
    stem = pdf_path.stem
    matched_pid = None
    match_method = ''

    if stem in NOT_IN_SLR:
        print(f"  NOT-IN-SLR: {safe(pdf_path.name)}")
        results.append({'pdf': pdf_path, 'matched_pid': None, 'method': 'not-in-slr'})
        continue

    if stem in MANUAL_MATCHES:
        matched_pid = MANUAL_MATCHES[stem]
        match_method = 'manual'

    # S1: SSRN filename
    if not matched_pid:
        m = re.match(r'ssrn[_-]?(\d+)', stem.lower())
        if m:
            ssrn_id = m.group(1)
            for doi, pid in doi_to_pid.items():
                if ssrn_id in doi and pid in missing_pids:
                    matched_pid = pid; match_method = f'SSRN({ssrn_id})'; break

    # S2: arXiv filename
    if not matched_pid:
        m = re.match(r'(\d{4}\.\d{4,5})v?\d*', stem)
        if m:
            arxiv_id = m.group(1)
            for doi, pid in doi_to_pid.items():
                if arxiv_id in doi and pid in missing_pids:
                    matched_pid = pid; match_method = f'arXiv({arxiv_id})'; break

    # S3: DOI from PDF content
    text = ''
    if not matched_pid:
        text = extract_text(pdf_path)
        for doi in extract_dois(text):
            dlower = doi.lower()
            if dlower in doi_to_pid and doi_to_pid[dlower] in missing_pids:
                matched_pid = doi_to_pid[dlower]
                match_method = f'DOI({doi[:40]})'; break

    # S4: Fuzzy on first text lines
    if not matched_pid:
        if not text:
            text = extract_text(pdf_path)
        lines = [l.strip() for l in text[:1000].split('\n') if len(l.strip()) > 20][:5]
        for line in lines:
            line_norm = norm(line)
            for title, pid in title_to_pid.items():
                score = fuzz.token_sort_ratio(line_norm, title) / 100.0
                if score >= 0.88:
                    matched_pid = pid
                    match_method = f'fuzzy-text({score:.2f})'
                    break
            if matched_pid:
                break

    # S5: Fuzzy on stem
    if not matched_pid:
        stem_norm = norm(stem.replace('-',' ').replace('_',' '))
        best_score = 0.0; best_pid = None
        for title, pid in title_to_pid.items():
            score = fuzz.token_sort_ratio(stem_norm, title) / 100.0
            if score > best_score:
                best_score = score; best_pid = pid
        if best_score >= 0.82:
            matched_pid = best_pid; match_method = f'fuzzy-stem({best_score:.2f})'

    results.append({'pdf': pdf_path, 'matched_pid': matched_pid, 'method': match_method})
    if matched_pid:
        title = safe(papers[matched_pid]['title'])[:55]
        print(f"  MATCH [{match_method}]: {safe(pdf_path.name)[:45]:45s} -> {matched_pid} | {title}")
    else:
        print(f"  UNMATCHED: {safe(pdf_path.name)}")

matched = [r for r in results if r['matched_pid']]
unmatched = [r for r in results if not r['matched_pid'] and r['method'] not in ('not-in-slr',)]
print(f"\nMatched: {len(matched)}, Unmatched: {len(unmatched)}")

# Import matched PDFs
print("\n--- IMPORTING ---")
imported = 0
already_have = 0
for r in matched:
    pid = r['matched_pid']
    if download_log.get(pid, {}).get('status') == 'success':
        already_have += 1
        print(f"  ALREADY HAVE: {pid}")
        continue
    meta = papers[pid]
    title = meta.get('title','') or pid
    doi = meta.get('doi','') or ''
    pdf_filename = f"{pid}_{sanitise(title)}.pdf"
    dest = PDF_DIR / pdf_filename
    shutil.copy2(r['pdf'], dest)
    download_log[pid] = {
        'paper_id': pid, 'title': title, 'doi': doi,
        'source': 'manual_import', 'pdf_url': '',
        'status': 'success', 'filename': pdf_filename,
        'timestamp': datetime.now().isoformat(timespec='seconds'),
    }
    print(f"  IMPORTED: {safe(pdf_filename)[:72]}")
    imported += 1

print(f"\nImported: {imported}, already had: {already_have}")

# Save log
lines = [','.join(LOG_COLUMNS)]
for pid in sorted(download_log):
    row = download_log[pid]
    lines.append(','.join(csv_escape(row.get(c,'')) for c in LOG_COLUMNS))
LOG_PATH.write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(f"Saved download log ({len(download_log)} entries)")

# Delete imported files from downloadedpdf
print("\n--- CLEANING downloadedpdf ---")
deleted = 0
for r in matched:
    if r['pdf'].exists():
        r['pdf'].unlink()
        deleted += 1
        print(f"  DELETED: {safe(r['pdf'].name)}")

print(f"\nDeleted {deleted} from downloadedpdf")
remaining = list(DL_DIR.glob('*.pdf'))
print(f"\nRemaining in downloadedpdf ({len(remaining)} files - not-in-SLR or unmatched):")
for f in sorted(remaining):
    print(f"  {safe(f.name)}")
