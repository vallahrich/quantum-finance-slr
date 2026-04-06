# Quantum-Finance SLR Toolkit

Reproducible, local-first toolkit for conducting a **systematic literature review (SLR)** on gate-based quantum computing in finance. This repository delivers a complete **Step 1** (search, screening, PDF retrieval) for handoff to Step 2 (classification and analysis).

## Scope

| Dimension | Value |
|-----------|-------|
| Domain | Gate-based quantum computing in finance |
| Databases | Scopus, OpenAlex, arXiv, Semantic Scholar |
| Includes | Preprints, NISQ, and fault-tolerant studies |
| Time window | 2016-01-01 – 2026-03-14 |
| Search date | Final run: 2026-03-14 (v5) |

## Results Summary

| Stage | Count |
|-------|-------|
| Records identified | 6,232 |
| Duplicates removed | 3,222 |
| Unique records screened (title/abstract) | 3,010 |
| Excluded at title/abstract | 2,135 |
| Full-text articles assessed | 875 |
| Excluded at full-text (no paper found) | 33 |
| **Included in systematic review** | **842** |

**Calibration**: Cohen’s κ = 0.849 (threshold ≥ 0.70). See [calibration_log.md](05_screening/calibration_log.md).

**AI safety net**: 184 papers flagged by AI screening; 144 rescued (included after re-review).

### Exclusion Reasons (Title/Abstract)

| Code | Count | Description |
|------|-------|-------------|
| EX-NONFIN | 901 | Not a finance application |
| EX-NOMETHOD | 557 | Survey/review, no original method |
| EX-TOOSHORT | 258 | Insufficient methodological detail |
| EX-PARADIGM | 234 | Annealing only / quantum-inspired |
| EX-REVERSED | 106 | Excluded after inter-rater discrepancy review |
| EX-OTHER | 73 | Miscellaneous |
| EX-NOTEN | 6 | Non-English |

### Figures

All figures are in [`06_figures/`](06_figures/) and can be regenerated via `python generate_figures.py`:

| Figure | Description |
|--------|-------------|
| `fig1_prisma_flow` | PRISMA 2020 flow diagram |
| `fig2_year_distribution` | Records by publication year (2016–2026) |
| `fig3_source_distribution` | Records by source database |
| `fig4_exclusion_reasons` | Screening exclusion reason breakdown |

## Folder Structure

```text
quantum-finance-slr/
├── 01_protocol/           Protocol, amendments log, PRISMA checklists
├── 02_search_logs/        PRISMA-S search log, benchmark check, snowball log
├── 03_raw_exports/        Raw API search results per source (v5 = final run)
├── 04_deduped_library/    Deduplicated master_records.csv + master_library.bib
├── 05_screening/          Screening workbooks, AI decisions, calibration
├── 06_figures/            Generated figures (PNG + PDF)
├── 07_full_texts/         PDF storage and download log
├── tools/
│   ├── slr_toolkit/       Core Python package (CLI, search, dedup, screening, LLM)
│   └── tests/             pytest test suite
├── generate_figures.py    Figure generation script
├── run_search.py          Main search runner
├── run_benchmark_check.py Benchmark sensitivity verification
└── pyproject.toml         Package configuration
```

## Setup

```bash
cd quantum-finance-slr
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

Python 3.11+ required.

## Pipeline

### 1. Initialize repo structure

```bash
python -m tools.slr_toolkit.cli init
```

### 2. Automated API search

```bash
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum computing" AND "finance"' \
    --from-year 2016
```

Queries each API, creates dated run folders with raw JSON and normalized CSV, and logs runs in `02_search_logs/search_log.xlsx`.

| Source | Auth | Notes |
|--------|------|-------|
| `openalex` | Free | Best general source, concept filters |
| `arxiv` | Free | Preprints |
| `semantic_scholar` | Free | Citations and forward snowballing |
| `scopus` | API key | Requires Elsevier access |

### 3. Build master library

```bash
python -m tools.slr_toolkit.cli build-master
```

Deduplicates records (DOI-exact → fuzzy-title matching) and writes `master_records.csv` + `master_library.bib`.

### 4. Screen (title/abstract)

```bash
python -m tools.slr_toolkit.cli generate-screening --seed 42 --validation-size 100
python -m tools.slr_toolkit.cli llm-screen
python -m tools.slr_toolkit.cli prisma
```

### 5. Generate figures

```bash
python generate_figures.py
```

## What’s Next (Step 2 — Classification)

This repository delivers Step 1 of the thesis workflow. The handoff to Step 2 includes:

- **842 included papers** in `05_screening/included_for_coding.csv`
- **646 full-text PDFs** in `07_full_texts/pdfs/` (tracked via Git LFS) and Zotero
- **Master library** in `04_deduped_library/master_records.csv` with metadata
- **Screening audit trail** — AI decisions, discrepancy review, calibration log, prompt logs

Step 2 tasks (not in scope for this repository):
- Topic coding and tier classification
- Snowballing (protocol §7c) using included papers as start set
- Tiered extraction (Tier 1 evidence mapping, Tier 2 Hoefler advantage assessment)
- Quality appraisal and synthesis

## AI / LLM Configuration

The toolkit uses Azure OpenAI via the `openai` SDK with structured JSON output (Responses API).

**Required environment variables** (see [.env.example](.env.example)):

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure resource URL |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name |
| `AZURE_OPENAI_API_KEY` | API key (or use `az login` for keyless auth) |

**Screening model**: `gpt-5-mini` (production run). Models evaluated: `gpt-4.1-mini`, `DeepSeek-V3.2`, `o4-mini`, `gpt-5-mini`.

Audit trail: `05_screening/llm_screening_prompt_log.jsonl`.

## Running Tests

```bash
pytest tools/tests -v
```

Covers: Azure OpenAI endpoints, deduplication, ingestion (RIS/BibTeX/CSV), query builders, LLM screening, shared utilities.

## Methodological Frameworks

- PRISMA 2020 · PRISMA-S
- Kitchenham & Charters (2007)
- Okoli (2015)
- vom Brocke et al. (2015)
- Hoefler et al. (2023)
- Wohlin (2014)
- Creswell & Creswell (2018)

## License

MIT — see [LICENSE](LICENSE).
