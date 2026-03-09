"""Benchmark sensitivity check — verify known-relevant papers appear in master library."""
import pandas as pd
from rapidfuzz import fuzz

# Benchmark papers (DOI + title for matching)
BENCHMARK = [
    {"title": "A Survey of Quantum Computing for Finance", "doi": "10.1038/s42254-023-00603-1", "authors": "Herman et al.", "year": "2023"},
    {"title": "Quantum Computing for Finance: State-of-the-Art and Future Prospects", "doi": "10.1109/TQE.2022.3220738", "authors": "Herman et al.", "year": "2022"},
    {"title": "Quantum computational finance: Monte Carlo pricing of financial derivatives", "doi": "10.1103/PhysRevA.98.022321", "authors": "Rebentrost et al.", "year": "2018"},
    {"title": "Quantum Risk Analysis", "doi": "10.1038/s41534-019-0130-6", "authors": "Woerner & Egger", "year": "2019"},
    {"title": "Option Pricing using Quantum Computers", "doi": "10.22331/q-2020-07-06-291", "authors": "Stamatopoulos et al.", "year": "2020"},
    {"title": "Quantum computing for finance: Overview and prospects", "doi": "10.1109/TQE.2021.3030823", "authors": "Egger et al.", "year": "2020"},
    {"title": "Quantum computing for finance: state of the art and future prospects", "doi": "10.1103/RevModPhys.91.045001", "authors": "Orús et al.", "year": "2019"},
    {"title": "Quantum Monte Carlo Integration: The Full Advantage in Minimal Circuit Depth", "doi": "10.22331/q-2021-06-24-481", "authors": "Chakrabarti et al.", "year": "2021"},
    {"title": "Improving Variational Quantum Optimization using CVaR", "doi": "10.22331/q-2020-04-20-256", "authors": "Barkoutsos et al.", "year": "2020"},
    {"title": "Benchmarking the performance of portfolio optimization with QAOA", "doi": "10.1007/s11128-022-03766-5", "authors": "Brandhofer et al.", "year": "2022"},
]

master = pd.read_csv("04_deduped_library/master_records.csv", dtype=str).fillna("")

found = 0
missed = []

for bp in BENCHMARK:
    # Try DOI match first
    doi_match = master[master["doi"].str.lower() == bp["doi"].lower()]
    if len(doi_match) > 0:
        src = doi_match.iloc[0]["source_db"]
        print(f"  ✓ FOUND (DOI)  [{bp['year']}] {bp['title'][:80]}  [source: {src}]")
        found += 1
        continue

    # Try fuzzy title match
    best_score = 0
    best_row = None
    for _, row in master.iterrows():
        score = fuzz.token_sort_ratio(bp["title"].lower(), row["title"].lower())
        if score > best_score:
            best_score = score
            best_row = row
        if score >= 90:
            break

    if best_score >= 85:
        print(f"  ✓ FOUND (fuzzy {best_score}%)  [{bp['year']}] {bp['title'][:80]}  [source: {best_row['source_db']}]")
        found += 1
    else:
        print(f"  ✗ MISSED  [{bp['year']}] {bp['title'][:80]}  (best match: {best_score}%)")
        missed.append(bp)

total = len(BENCHMARK)
recall = found / total * 100
print(f"\n{'='*60}")
print(f"Benchmark recall: {found}/{total} = {recall:.1f}%")
print(f"Target: ≥ 95%")
print(f"Result: {'PASS ✓' if recall >= 95 else 'FAIL ✗'}")
if missed:
    print(f"\nMissed papers:")
    for m in missed:
        print(f"  - [{m['year']}] {m['title']} (DOI: {m['doi']})")
