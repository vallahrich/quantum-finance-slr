# Quantum-Finance SLR Toolkit

A reproducible, local-first toolkit for running a systematic literature review (SLR) on gate-based quantum computing in finance, with tiered extraction for evidence mapping and practical advantage assessment.

- Tier 1 extraction (all papers): evidence mapping across problem families, quantum methods, evaluation approaches, and maturity.
- Tier 2 extraction (quantitative papers): practical advantage assessment using the Hoefler et al. (2023) framework.

## Scope

| Dimension | Value |
|-----------|-------|
| Domain | Gate-based quantum computing in finance |
| Research context | Phase 1a of an exploratory sequential mixed-methods design |
| Databases | Scopus, OpenAlex, arXiv, Semantic Scholar |
| Includes | Preprints, NISQ, and fault-tolerant studies |
| Time window | 2016-01-01 to present |
| Advantage framework | Tier-1 crossover target plus Tier-2 finance SLA reality check |
| Protocol registration | OSF `<https://osf.io/XXXXX>` |

## Setup

```bash
cd quantum-finance-slr
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Python 3.11+ is required.

## Quick Start

### 1. Initialize the repo structure

```bash
python -m tools.slr_toolkit.cli init
```

Creates the numbered folders and template files. The command is idempotent and will not overwrite templates unless you pass `--force`.

### 2. Create a search run

```bash
python -m tools.slr_toolkit.cli new-search-run --source scopus --date 2026-03-08
```

This creates `03_raw_exports/2026-03-08_scopus/` and appends a metadata row to `02_search_logs/search_log.xlsx`.

### 3. Ingest exports

```bash
python -m tools.slr_toolkit.cli ingest --run-folder 03_raw_exports/2026-03-08_scopus
```

Reads all `.ris`, `.bib`, and `.csv` files in the folder, normalizes them into the project schema, and writes `normalized_records.csv`.

### 4. Build the master library

```bash
python -m tools.slr_toolkit.cli build-master
```

Scans run folders, concatenates normalized records, deduplicates them, and writes:

- `04_deduped_library/master_records.csv`
- `04_deduped_library/master_library.bib`

The dedup step also assigns `version_group_id` values to connect preprint and peer-reviewed versions of the same work.

### 5. Run automated API search

```bash
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum computing" AND "finance"' \
    --from-year 2016 \
    --max-results 500
```

This automatically:

- queries each selected API
- creates a dated run folder per source
- saves raw JSON for provenance
- saves normalized CSV for the ingest pipeline
- logs each run in `02_search_logs/search_log.xlsx`

Available sources:

| Source | Auth | Notes |
|--------|------|-------|
| `openalex` | Free | Best general source, supports concept filters |
| `arxiv` | Free | Preprints only |
| `semantic_scholar` | Free | Good for citations and forward snowballing |
| `scopus` | API key | Requires Elsevier access |

### 6. Generate PRISMA counts

```bash
python -m tools.slr_toolkit.cli prisma
```

Outputs `02_search_logs/prisma_counts.xlsx` with flow counts, exclusion-reason breakdowns, and calibration metrics when available.

## Folder Structure

```text
quantum-finance-slr/
|-- 01_protocol/
|-- 02_search_logs/
|-- 03_raw_exports/
|-- 04_deduped_library/
|-- 05_screening/
|   |-- title_abstract_decisions_template.csv
|   |-- full_text_decisions_template.csv
|   |-- included_for_coding.csv
|   |-- llm_screening_checkpoint.json
|   `-- llm_screening_prompt_log.jsonl
|-- 06_extraction/
|   |-- extraction_template.xlsx
|   |-- codebook.md
|   |-- topic_coding.csv
|   `-- topic_coding_summary.md
|-- 07_figures/
`-- tools/
    |-- slr_toolkit/
    `-- tests/
```

## Screening Workflow

1. Generate screening workbooks:

```bash
python -m tools.slr_toolkit.cli generate-screening --seed 42 --validation-size 100
```

This produces calibration, validation, and split-reviewer Excel files.

2. Compute calibration agreement:

```bash
python -m tools.slr_toolkit.cli compute-kappa
```

3. Complete split human screening.

4. Optionally run the AI safety-net workflow:

- `export-asreview`
- `run-asreview` or `llm-screen`
- `merge-screening`
- `ai-discrepancies`
- `ai-validation`
- `fn-audit`

5. Complete `full_text_decisions.csv` with final decisions, exclusion reasons, and `tier2_applicable`.

6. Run topic coding for included studies:

```bash
python -m tools.slr_toolkit.cli topic-code
python -m tools.slr_toolkit.cli topic-code --dry-run
python -m tools.slr_toolkit.cli topic-code --max-records 25
python -m tools.slr_toolkit.cli topic-code --input-file 05_screening/included_for_coding.csv
```

Use `--input-file 05_screening/included_for_coding.csv` when you have an interim include list but have not finalized `05_screening/full_text_decisions.csv` yet.

## AI / LLM Notes

- `llm-screen` and `topic-code` support either `--api-key` / `AZURE_OPENAI_API_KEY` or keyless Azure AD auth via `az login`.
- The toolkit's current default pricing assumptions are set to `gpt-4.1-mini`.
- `o4-mini` is the recommended deployment for screening and topic coding.
- Models tested: `gpt-4.1-mini`, `DeepSeek-V3.2`, `o4-mini` (o4-mini selected).
- `llm-screen` writes resumable progress to `05_screening/llm_screening_checkpoint.json`.
- `llm-screen` writes a per-record audit log to `05_screening/llm_screening_prompt_log.jsonl`.
- `import-ai-decisions` validates imported labels instead of silently treating unknown values as excludes.

Accepted imported AI labels include:

- `1` / `0`
- `true` / `false`
- `yes` / `no`
- `include` / `exclude`
- `relevant` / `irrelevant`

## How PRISMA Counts Are Computed

| Metric | Source |
|--------|--------|
| `Identified` | Total rows in `master_records.csv` |
| `DuplicatesRemoved` | Rows where `duplicate_of` is non-empty |
| `ScreenedTitleAbstract` | Rows in `title_abstract_decisions.csv` |
| `ExcludedTitleAbstract` | Rows with `final_decision == 'exclude'` |
| `FullTextAssessed` | Rows in `full_text_decisions.csv` |
| `ExcludedFullText` | Rows with `final_decision == 'exclude'` |
| `IncludedTotal` | Rows with `final_decision == 'include'` |
| `Tier2Applicable` | Included rows with `tier2_applicable == 'yes'` |

If required inputs are missing, counts are reported as `MISSING_INPUT`.

## Running Tests

```bash
pytest tools/tests -v
```

Coverage currently includes:

- DOI-exact deduplication
- fuzzy-title deduplication
- ingest parsing for RIS, BibTeX, and CSV
- query-builder logic
- AI-screening and topic-coding flows

## Methodological Frameworks

This review is guided by:

- PRISMA 2020
- PRISMA-S
- Kitchenham and Charters (2007)
- Okoli (2015)
- vom Brocke et al. (2015)
- Hoefler et al. (2023)
- Wohlin (2014)
- Creswell and Creswell (2018)

## Citing This Work

```bibtex
@mastersthesis{wallerich2026quantum,
  author  = {Wallerich, [First Name]},
  title   = {Gate-Based Quantum Computing in Finance: A Systematic
             Literature Review and Practical Advantage Assessment
             Within a Mixed-Methods Research Design},
  school  = {[University Name]},
  year    = {2026},
}
```

## Acknowledgements

- Thesis supervisor: [Name]
- [Any additional acknowledgements]
