"""Match unmatched PDFs to master records by extracting titles from the PDFs."""
import csv
import re

def normalize(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

# Titles extracted from the PDFs via PyMuPDF
pdf_titles = {
    '1-s2.0-S2352711023002558-mainext.pdf': 'Omnisolver: An extensible interface to Ising spin-glass and QUBO solvers',
    '1370562.pdf': 'Antifragile Quantum-Semantic Systems via CVaR-POVM Riemannian Memory Manifolds',
    '1887_4290771-Chapter 2.pdf': 'Capturing dynamics with noisy quantum computers',
    '2110.05653v1.pdf': 'Efficient Evaluation of Exponential and Gaussian Functions on a Quantum Computer',
    '2503.12121v2.pdf': 'A Comparative Study of Quantum Optimization Techniques for Solving Combinatorial Optimization Benchmark Problems',
    '2508.06441v3.pdf': 'Accelerating Quantum Monte Carlo Calculations with Set-Equivariant Architectures and Transfer Learning',
    '485.pdf': 'Application of Quantum Computing in Optimization Problems',
    '67dc35e21d25e.pdf': 'Advancing Financial Decision-Making through Quantum Computing and Cloud-Based AI Models A Comparative Analysis of Predictive Algorithms',
    'AIQuantumComputingFinal.pdf': 'AI and Quantum Computing for Finance and Technology',
    'IJEAS0510017.pdf': 'A time-Series Model Based on Quantum Walk in terms of Quantum Bernoulli Noise',
    'out.pdf': 'Discrete-Time Quantum Walk of a Bose-Einstein Condensate in Momentum Space',
}

pdf_dois = {
    '1-s2.0-S2352711023002558-mainext.pdf': '10.1016/j.softx.2023.101559',
    '1370562.pdf': '10.22541/au.176599457.78410478/v1',
    '485.pdf': '10.31713/MCIT.2024.033',
}

# Load master records
title_idx = {}
doi_idx = {}
with open('04_deduped_library/master_records.csv', encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        nt = normalize(row['title'])
        if nt:
            title_idx[nt] = row
        doi = row.get('doi', '').lower().strip()
        if doi:
            doi_idx[doi] = row

# Load included set
included = set()
with open('05_screening/included_for_coding.csv', encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        included.add(row['paper_id'])

print('Searching for matches...\n')

for fn, title in pdf_titles.items():
    print(f'=== {fn} ===')
    print(f'  Title: {title[:80]}')

    found = None
    method = ''

    # Try DOI
    if fn in pdf_dois:
        doi = pdf_dois[fn].lower()
        if doi in doi_idx:
            found = doi_idx[doi]
            method = 'doi'
        else:
            for d, rec in doi_idx.items():
                if doi in d or d in doi:
                    found = rec
                    method = 'doi-partial'
                    break

    # Try exact title
    if not found:
        nt = normalize(title)
        if nt in title_idx:
            found = title_idx[nt]
            method = 'title-exact'

    # Try partial title
    if not found:
        nt = normalize(title)
        for t, rec in title_idx.items():
            if len(nt) > 30 and (nt in t or t in nt):
                found = rec
                method = 'title-partial'
                break

    # Try fuzzy word match
    if not found:
        words = [normalize(w) for w in title.split() if len(w) > 3]
        best_match = None
        best_score = 0
        for t, rec in title_idx.items():
            score = sum(1 for w in words if w in t)
            if score > best_score and score >= len(words) * 0.6:
                best_score = score
                best_match = rec
        if best_match and best_score >= 4:
            found = best_match
            method = f'title-fuzzy({best_score}/{len(words)})'

    if found:
        pid = found['paper_id']
        inc = 'INCLUDED' if pid in included else 'NOT INCLUDED'
        master_title = found['title'][:80]
        master_doi = found.get('doi', '')
        print(f'  MATCH [{method}]: {pid} ({inc})')
        print(f'  Master title: {master_title}')
        print(f'  DOI: {master_doi}')
    else:
        print('  NO MATCH FOUND')
    print()
