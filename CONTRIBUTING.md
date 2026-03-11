# Contributing & Reproducibility Guide

This document explains how to reproduce the full SLR pipeline from search
through PRISMA flow-diagram generation. It is intended for thesis examiners
and any researcher wishing to verify or extend the work.

---

## Environment setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd quantum-finance-slr

# 2. Create a virtual environment (Python 3.11+)
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

# 3. Install the toolkit in editable mode with dev dependencies
pip install -e ".[dev]"
```

---

## Running the full pipeline

### Step 1 — API search (retrieve records)

```bash
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum computing" AND "finance"' \
    --from-year 2016 \
    --max-results 500
```

This queries OpenAlex, arXiv, and Semantic Scholar. For Scopus, add
`--sources scopus --api-key YOUR_KEY`.

Each run creates a dated folder under `03_raw_exports/` with raw JSON and
normalised CSV. Query details are auto-logged to
`02_search_logs/search_log.xlsx`.

### Step 2 — Build master library (deduplicate)

```bash
python -m tools.slr_toolkit.cli build-master
```

Produces `04_deduped_library/master_records.csv` and `master_library.bib`.

### Step 3 — Screen records

1. Copy `05_screening/title_abstract_decisions_template.csv` →
   `title_abstract_decisions.csv`
2. Fill in screening decisions (`include` / `exclude` / `maybe`).
3. For included papers, copy `full_text_decisions_template.csv` →
   `full_text_decisions.csv` and complete full-text screening
   (include `tier2_applicable` flag for each included paper).

### Step 4 — Generate PRISMA counts

```bash
python -m tools.slr_toolkit.cli prisma
```

Outputs `02_search_logs/prisma_counts.xlsx`.

---

## Running the test suite

```bash
pytest tools/tests/ -v
```

Tests cover deduplication (DOI-exact and fuzzy-title), ingest parsing (RIS,
BibTeX, CSV), and query builder logic.

---

## File provenance

| Category | Location | Generated? |
|----------|----------|-----------|
| Raw API responses | `03_raw_exports/*/api_search_*.json` | Yes (by auto-search) |
| Normalised records | `03_raw_exports/*/normalized_records.csv` | Yes (by ingest) |
| Master library | `04_deduped_library/` | Yes (by build-master) |
| PRISMA counts | `02_search_logs/prisma_counts.xlsx` | Yes (by prisma) |
| Search log | `02_search_logs/search_log.xlsx` | Yes (by new-search-run / auto-search) |
| Protocol & amendments | `01_protocol/` | No (hand-authored) |
| Screening decisions | `05_screening/` | No (hand-authored) |
| Extraction data | `06_extraction/` | No (hand-authored) |

---

## `.gitignore` conventions

Auto-generated files that can be reproduced from raw data are listed in
`.gitignore`:
- `__pycache__/`, `*.pyc`
- `.venv/`
- `*.egg-info/`

Raw exports and screening decisions are **committed** to ensure full
reproducibility.
