# Reproducibility Guide

How to reproduce the SLR pipeline from search through synthesis. Written for thesis examiners, collaborators, and future maintainers.

## Environment Setup

```bash
git clone <repo-url>
cd quantum-finance-slr
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Python 3.11+ required.

## Pipeline Steps

### 1. API Search

```bash
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum computing" AND "finance"' \
    --from-year 2016
```

For Scopus, add `--sources scopus --api-key YOUR_KEY`.

### 2. Build Master Library

```bash
python -m tools.slr_toolkit.cli build-master
```

Produces `04_deduped_library/master_records.csv` and `master_library.bib`.

### 3. Human Screening

```bash
python -m tools.slr_toolkit.cli generate-screening --seed 42 --validation-size 100
python -m tools.slr_toolkit.cli compute-kappa
```

Proceed once Cohen's κ ≥ 0.70.

### 4. LLM-Assisted Screening

```bash
python -m tools.slr_toolkit.cli llm-screen
```

Production run used `gpt-5-mini` via Azure OpenAI Responses API. Audit log: `05_screening/llm_screening_prompt_log.jsonl`.

### 5. Discrepancy Resolution

```bash
python -m tools.slr_toolkit.cli merge-screening
python -m tools.slr_toolkit.cli ai-discrepancies
python -m tools.slr_toolkit.cli ai-validation
python -m tools.slr_toolkit.cli fn-audit
```

### 6. PRISMA Counts & Figures

```bash
python -m tools.slr_toolkit.cli prisma
python generate_figures.py
```

## Tests

```bash
pytest tools/tests -v
```

## File Provenance

| Category | Location | Generated? |
|----------|----------|------------|
| Raw API responses | `03_raw_exports/*/api_search_*.json` | Yes |
| Normalized records | `03_raw_exports/*/normalized_records.csv` | Yes |
| Master library | `04_deduped_library/` | Yes |
| PRISMA counts | `02_search_logs/prisma_counts.xlsx` | Yes |
| Search log | `02_search_logs/search_log.xlsx` | Yes |
| Figures | `06_figures/` | Yes |
| Protocol and amendments | `01_protocol/` | No |
| Screening decisions | `05_screening/` | Mixed |

## Reproducibility Notes

- Raw exports and screening artifacts are kept for auditability.
- LLM prompt log (`05_screening/llm_screening_prompt_log.jsonl`) provides a full audit trail.
- Earlier search iterations (v1–v4) were discarded to keep the repo clean; only v5 (final) is retained.

## Azure OpenAI Configuration

See [.env.example](.env.example) for required environment variables:

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure resource URL |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (e.g. `gpt-5-mini`) |
| `AZURE_OPENAI_API_KEY` | API key (or use `az login` for keyless auth) |

See [.env.example](.env.example) for a template.

## Current Study Numbers

| Metric | Value |
|--------|-------|
| Total ingested | 6,232 |
| Duplicates removed | 3,222 |
| Unique records screened | 3,010 |
| AI include decisions | 651 (21.6%) |
| AI exclude decisions | 2,359 (78.4%) |
| Calibration kappa | 0.849 (PASS) |
| Screening model | gpt-5-mini (Responses API) |
| Screening workbooks | Cal: 50, Val: 100, A: 1,475, B: 1,499 |
