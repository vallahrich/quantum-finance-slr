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

```bash
# 4. (Optional) Install AI-assisted screening dependencies
pip install -e ".[ai]"
# Required for: export-asreview, run-asreview, import-ai-decisions,
# ai-discrepancies, ai-validation, fn-audit commands
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

1. Generate screening workbooks (calibration + validation + split):

```bash
python -m tools.slr_toolkit.cli generate-screening --seed 42 --validation-size 100
```

This produces:
- `calibration_screening.xlsx` — 50 records, dual-reviewer
- `validation_screening.xlsx` — 100 records, dual-reviewer (held-out for AI validation)
- `screening_reviewer_A.xlsx` — half of remaining records
- `screening_reviewer_B.xlsx` — other half

2. Both reviewers independently screen calibration set. Compute kappa:

```bash
python -m tools.slr_toolkit.cli compute-kappa
```

3. Once κ ≥ 0.70, proceed to split screening.

### Step 3b — AI-assisted screening (optional, per Protocol §8)

After calibration, set up ASReview as a recall safety net:

```bash
# Export prior labels (from calibration consensus) + dataset for ASReview
python -m tools.slr_toolkit.cli export-asreview

# → asreview_prior_labels.csv (training data)
# → asreview_dataset.csv (records to screen)
```

Run ASReview simulation directly in the pipeline:

```bash
# Run ASReview active-learning simulation (uses ELAS-u4 model by default)
python -m tools.slr_toolkit.cli run-asreview
```

Or, if you used ASReview LAB externally, import results:

```bash
# Import AI decisions from ASReview export
python -m tools.slr_toolkit.cli import-ai-decisions --file <asreview_export.csv>
```

After human screening is complete, merge results then compare with AI:

```bash
# Merge calibration + reviewer A/B decisions into one CSV
python -m tools.slr_toolkit.cli merge-screening

# Compare human vs AI decisions (requires merge-screening output)
python -m tools.slr_toolkit.cli ai-discrepancies

# Validate AI on held-out subset
python -m tools.slr_toolkit.cli ai-validation

# Generate false-negative audit sample (10% of double-excluded)
python -m tools.slr_toolkit.cli fn-audit
```

Then fill in `full_text_decisions.csv` with exclusion reasons + `tier2_applicable` flag.

> **Protocol §8 ↔ CLI mapping:**
>
> | Protocol Step | CLI Command |
> |---|---|
> | §8.1 Human calibration | `generate-screening` + manual review |
> | §8.2 AI initialisation | `export-asreview` |
> | §8.3 Held-out validation | `generate-screening --validation-size 100` |
> | §8.4 Human split screening | Manual review of split workbooks |
> | §8.5 AI parallel screening | `run-asreview` |
> | §8.6 Discrepancy resolution | `merge-screening` → `ai-discrepancies` → manual |
> | §8.7 False-negative audit | `fn-audit` |
> | §8.8 Borderline escalation | Manual (during discrepancy review) |
> | §8.9 Re-screening check | Manual (intra-rater concordance) |

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
