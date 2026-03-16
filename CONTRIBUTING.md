# Contributing and Reproducibility Guide

This document explains how to reproduce the SLR pipeline from search through PRISMA reporting. It is written for thesis examiners, collaborators, and future maintainers.

## Environment Setup

```bash
git clone <repo-url>
cd quantum-finance-slr
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Optional AI / ASReview dependencies for the legacy ASReview path:

```bash
pip install -e ".[ai]"
```

## Running the Pipeline

### Step 1: API Search

```bash
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum computing" AND "finance"' \
    --from-year 2016 \
    --max-results 500
```

For Scopus, add `--sources scopus --api-key YOUR_KEY`.

### Step 2: Build the Master Library

```bash
python -m tools.slr_toolkit.cli build-master
```

This produces `04_deduped_library/master_records.csv` and `04_deduped_library/master_library.bib`.

### Step 3: Human Screening

Generate workbooks:

```bash
python -m tools.slr_toolkit.cli generate-screening --seed 42 --validation-size 100
```

Compute agreement:

```bash
python -m tools.slr_toolkit.cli compute-kappa
```

Proceed once Cohen's kappa is at least `0.70`.

### Step 3b: AI-Assisted Screening

The current production workflow uses Azure OpenAI LLM screening. The
ASReview path remains in the repo as a legacy / experimental option.

ASReview path:

```bash
python -m tools.slr_toolkit.cli export-asreview
python -m tools.slr_toolkit.cli run-asreview
```

LLM path:

```bash
python -m tools.slr_toolkit.cli llm-screen --dry-run
python -m tools.slr_toolkit.cli llm-screen
```

Notes:

- `llm-screen` supports `--api-key` / `AZURE_OPENAI_API_KEY` or keyless Azure AD auth via `az login`.
- The repo's current screening cost assumptions are based on `gpt-5-mini`.
- The completed repository screening run used `o4-mini`.
- `llm-screen` writes resumable state to `05_screening/llm_screening_checkpoint.json`.
- `llm-screen` writes audit logs to `05_screening/llm_screening_prompt_log.jsonl`.

Import AI decisions from an external tool:

```bash
python -m tools.slr_toolkit.cli import-ai-decisions --file <export.csv>
```

Supported imported label formats include:

- `1` / `0`
- `true` / `false`
- `yes` / `no`
- `include` / `exclude`
- `relevant` / `irrelevant`

After human screening, merge and review:

```bash
python -m tools.slr_toolkit.cli merge-screening
python -m tools.slr_toolkit.cli ai-discrepancies
python -m tools.slr_toolkit.cli ai-validation
python -m tools.slr_toolkit.cli fn-audit
```

### Step 4: Full-Text Decisions and Topic Coding

Create and populate `05_screening/full_text_decisions.csv` from the template, then run:

```bash
python -m tools.slr_toolkit.cli topic-code
```

If you are still working from an interim include list, use:

```bash
python -m tools.slr_toolkit.cli topic-code --input-file 05_screening/included_for_coding.csv
```

### Step 5: PRISMA Counts

```bash
python -m tools.slr_toolkit.cli prisma
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
| Protocol and amendments | `01_protocol/` | No |
| Screening decisions | `05_screening/` | Mixed |
| Extraction outputs | `06_extraction/` | Mixed |

## Reproducibility Notes

- Raw exports and screening artifacts are intentionally kept in the repository for auditability.
- Generated AI logs and checkpoints are useful for traceability but may be regenerated if you restart a run.
- Prefer non-destructive updates to screening and extraction outputs so the review trail remains inspectable.
