# Quantum-Finance SLR Toolkit

A reproducible, local-first toolkit for running a **two-stage systematic literature review** (SLR) on gate-based quantum computing in finance.

- **Stage A — Mapping Review:** Broad survey of QC applications in finance.
- **Stage B — Focused SLR:** Deep assessment of practical quantum advantage claims.

## Scope

| Dimension | Value |
|-----------|-------|
| Domain | Gate-based quantum computing in finance |
| Databases | Scopus, OpenAlex, arXiv, Semantic Scholar (4 sources) |
| Includes | Preprints (arXiv, SSRN), NISQ + fault-tolerant |
| Time window | 2016-01-01 → present |
| Advantage framework | Tier-1 crossover target (≤2 weeks) + Tier-2 finance SLA reality check |
| Protocol registration | OSF <https://osf.io/XXXXX> |

---

## Setup

```bash
# Clone and enter the repo
cd quantum-finance-slr

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -e ".[dev]"
```

**Python 3.11+ required.** Core dependencies: `pandas`, `openpyxl`, `rispy`, `bibtexparser`. Optional: `rapidfuzz` (fuzzy deduplication).

---

## Quick Start

### 1. Initialise the repo structure

```bash
python -m tools.slr_toolkit.cli init
```

Creates all numbered folders and template files. Idempotent — won't overwrite existing files. Use `--force` to regenerate templates.

### 2. Create a search run

```bash
python -m tools.slr_toolkit.cli new-search-run --source scopus --date 2026-03-08
```

This:
- Creates `03_raw_exports/2026-03-08_scopus/` with a README.txt
- Appends a metadata row to `02_search_logs/search_log.xlsx`

After creating the run, execute your search in the database and **export results** (RIS, BibTeX, or CSV) into the run folder.

> **PRISMA-S required:** After running your search, update `02_search_logs/search_log.xlsx` with:
> `Interface` (e.g. "Scopus web"), `FullSearchString` (exact copy-paste),
> `Fields` (e.g. TITLE-ABS-KEY), `DateLimits`, `LanguageLimits`, `ResultsN`.

### 3. Ingest exports

```bash
python -m tools.slr_toolkit.cli ingest --run-folder 03_raw_exports/2026-03-08_scopus
```

Reads all `.ris`, `.bib`, `.csv` files in the folder, normalises them into a standard schema, and writes `normalized_records.csv` inside the run folder.

### 4. Build the master library

```bash
python -m tools.slr_toolkit.cli build-master
```

Scans all run folders, concatenates normalised records, deduplicates (DOI exact + fuzzy title match), and outputs:
- `04_deduped_library/master_records.csv`
- `04_deduped_library/master_library.bib`

Dedup also assigns `version_group_id` to link preprint↔peer-reviewed versions of the same work (see *Preprint Versioning* below).

### 5. Automated API search (NEW)

```bash
# Search all free sources (OpenAlex + arXiv + Semantic Scholar)
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum computing" AND "finance"' \
    --from-year 2016 \
    --max-results 500

# Search specific sources only
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum circuit" AND ("portfolio" OR "option pricing")' \
    --sources openalex,arxiv

# With email for faster OpenAlex rate limits
python -m tools.slr_toolkit.cli auto-search \
    --query '"quantum advantage" AND "finance"' \
    --email your.email@example.com

# Scopus (requires API key + pybliometrics)
python -m tools.slr_toolkit.cli auto-search \
    --query 'TITLE-ABS-KEY("quantum computing" AND "finance")' \
    --sources scopus --api-key YOUR_KEY
```

This automatically:
- Queries each API with your search string
- Creates a dated run folder per source (e.g. `2026-03-08_openalex/`)
- Saves raw JSON for provenance + normalised CSV for the pipeline
- Logs each run in `search_log.xlsx`

**Available sources:**

| Source | Auth | Rate limit | Notes |
|--------|------|-----------|-------|
| `openalex` | None (free) | ~10 req/s with email | Best single source, ~250M works |
| `arxiv` | None (free) | 1 req/3s | Preprints only |
| `semantic_scholar` | None (free) | 100 req/5min | Good for citations & forward snowballing |
| `scopus` | API key | Per key | `pip install pybliometrics` |

> **Note:** Web of Science, IEEE Xplore, and ACM DL are not searched
> directly. Scopus indexes the majority of IEEE and ACM content; OpenAlex
> captures nearly all WoS-indexed publications via Crossref metadata.
> See protocol §6 for full justification.

> **PRISMA-S compliance:** All search queries are logged per PRISMA-S
> (Rethlefsen et al. 2021) requirements in
> `02_search_logs/search_log.xlsx` with exact API query strings.

### 6. Generate PRISMA counts

```bash
python -m tools.slr_toolkit.cli prisma
```

Reads screening decision files and master records to compute PRISMA flow-diagram counts. Outputs `02_search_logs/prisma_counts.xlsx` with:
- Main PRISMA flow counts (Identified → Included)
- Full-text exclusion reason breakdown (per PRISMA 2020 §13b)
- Calibration metrics (Cohen's κ, percent agreement) if `calibration_decisions.csv` is populated

---

## Folder Structure

```
quantum-finance-slr/
├── 01_protocol/                 # SLR protocol and amendments
│   ├── protocol_v1.0.md
│   └── amendments_log.csv
├── 02_search_logs/              # Search metadata + PRISMA counts
│   ├── search_log.xlsx          # Auto-managed by new-search-run
│   └── prisma_counts.xlsx       # Auto-generated by prisma
├── 03_raw_exports/              # Bibliographic exports (one folder per run)
│   └── YYYY-MM-DD_source/
│       ├── README.txt
│       ├── export.ris           # ← you place files here
│       └── normalized_records.csv  # ← generated by ingest
├── 04_deduped_library/          # Deduplicated master outputs
│   ├── master_records.csv
│   └── master_library.bib
├── 05_screening/                # Screening decisions
│   ├── title_abstract_decisions_template.csv
│   ├── full_text_decisions_template.csv
│   ├── exclusion_reason_codes.md    # Exclusion reason code definitions
│   ├── calibration_log.md           # Inter-rater reliability log (§8)
│   ├── calibration_decisions.csv    # Calibration round decisions
│   ├── title_abstract_decisions.csv  # ← copy from template, fill in
│   └── full_text_decisions.csv       # ← copy from template, fill in
├── 06_extraction/               # Data extraction
│   ├── extraction_template.xlsx
│   └── codebook.md
├── 07_figures/                  # Generated figures (optional)
└── tools/
    ├── slr_toolkit/             # Python package
    │   ├── __init__.py
    │   ├── cli.py
    │   ├── config.py
    │   ├── utils.py
    │   ├── search_run.py
    │   ├── ingest.py
    │   ├── dedup.py
    │   ├── prisma.py
    │   └── templates.py
    └── tests/
        ├── test_dedup.py
        └── test_ingest_smoke.py
```

---

## Where to Put Exports

1. Run `new-search-run --source <db>` to create the dated folder.
2. Export results from the database in **RIS**, **BibTeX**, or **CSV** format.
3. Place the exported file(s) into `03_raw_exports/YYYY-MM-DD_source/`.
4. Run `ingest --run-folder 03_raw_exports/YYYY-MM-DD_source`.

**Supported formats:**
- `.ris` — parsed via `rispy`
- `.bib` — parsed via `bibtexparser` (v2 API)
- `.csv` — parsed via `pandas` with automatic column-name mapping

---

## Screening Workflow

0. Run calibration round (see §8 of protocol) — target Cohen's κ ≥ 0.70 before main screening.
1. Run `build-master` to get `04_deduped_library/master_records.csv`.
2. Copy `05_screening/title_abstract_decisions_template.csv` → `title_abstract_decisions.csv`.
3. Fill in screening decisions (`include` / `exclude` / `maybe`) for each `paper_id`.
4. For included papers, copy `full_text_decisions_template.csv` → `full_text_decisions.csv` and fill in full-text screening decisions.
5. Run `prisma` to generate counts.

### Decision columns

| Column | Description |
|--------|-------------|
| `decision_A` | Reviewer A's decision |
| `decision_B` | Reviewer B's decision |
| `conflict` | Flag if A ≠ B |
| `final_decision` | Resolved decision: `include` / `exclude` / `maybe` |
| `reason_code` / `exclusion_reason` | Code from `exclusion_reason_codes.md` — **mandatory** for excluded full-text records |
| `stage` | `A` or `B` (full-text template only) — for Stage A/B split in PRISMA |
| `notes` | Free-text notes |

---

## How PRISMA Counts Are Computed

| Metric | Source |
|--------|--------|
| `Identified` | Total rows in `master_records.csv` |
| `DuplicatesRemoved` | Rows where `duplicate_of` is non-empty |
| `ScreenedTitleAbstract` | Rows in `title_abstract_decisions.csv` |
| `ExcludedTitleAbstract` | Rows with `final_decision == 'exclude'` |
| `FullTextAssessed` | Rows in `full_text_decisions.csv` |
| `ExcludedFullText` | Rows with `final_decision == 'exclude'` |
| `IncludedStageA` | Included count (or split by `stage` column if present) |
| `IncludedStageB` | Split by `stage` column, or `N/A` |

The `prisma_counts.xlsx` also includes an **Exclusion Reasons** sheet with per-code counts (e.g. EX-PARADIGM: 5, EX-NONFIN: 3). If excluded records are missing an `exclusion_reason`, a warning is logged.

If input files are missing, counts show `MISSING_INPUT`.

---

## Preprint Versioning

During ingest, records from preprint sources (arXiv, SSRN, etc.) are auto-tagged with `is_preprint=1`.

During `build-master`, dedup assigns a `version_group_id` to link preprint↔peer-reviewed versions:
- Records matched as duplicates share a `version_group_id`.
- This lets you track preprint→journal publication provenance.
- Use `version_group_id` for sensitivity analysis (e.g. exclude preprints where a journal version exists).

---

## Running Tests

```bash
pytest tools/tests/ -v
```

Tests cover:
- DOI-exact deduplication (same DOI → marked duplicate)
- Fuzzy-title deduplication (similar titles + same year + same author initial)
- No false-positive dedup (different titles/authors)
- RIS, BibTeX, and CSV ingest parsing

---

## Notes

- **RIS export** of the master library is not supported (`rispy` has no writer). Use `.bib` or `.csv`.
- **Fuzzy dedup** gracefully degrades to DOI-only if `rapidfuzz` is not installed.
- All CLI commands are idempotent where applicable.
- No network calls — everything is local file-based.

---

## Methodological Frameworks

This review is guided by the following methodological frameworks:

- **PRISMA 2020** (Page et al. 2021) — reporting structure for systematic
  reviews.
- **PRISMA-S** (Rethlefsen et al. 2021) — search documentation extension.
- **Kitchenham & Charters (2007)** — guidelines for performing systematic
  literature reviews in software engineering.
- **Okoli (2015)** — guide to conducting a standalone systematic literature
  review in information systems research.
- **vom Brocke et al. (2015)** — standing on the shoulders of giants:
  challenges and recommendations for rigour in literature searches.
- **Hoefler et al. (2023)** — disentangling hype from practicality: a
  framework for assessing practical quantum advantage.
- **Wohlin (2014)** — guidelines for snowballing in systematic literature
  studies.

---

## Citing This Work

```bibtex
@mastersthesis{wallerich2026quantum,
  author  = {Wallerich, [First Name]},
  title   = {Gate-Based Quantum Computing in Finance: A Two-Stage
             Systematic Literature Review and Practical Advantage
             Assessment},
  school  = {[University Name]},
  year    = {2026},
}
```

---

## Acknowledgements

- Thesis supervisor: [Name]
- [Any additional acknowledgements]

