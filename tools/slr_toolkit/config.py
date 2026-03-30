"""Central configuration — paths, column definitions, constants."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root  (two levels up from tools/slr_toolkit/)
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Numbered directory paths
# ---------------------------------------------------------------------------
PROTOCOL_DIR      = ROOT_DIR / "01_protocol"
SEARCH_LOGS_DIR   = ROOT_DIR / "02_search_logs"
RAW_EXPORTS_DIR   = ROOT_DIR / "03_raw_exports"
DEDUPED_DIR       = ROOT_DIR / "04_deduped_library"
SCREENING_DIR     = ROOT_DIR / "05_screening"
EXTRACTION_DIR    = ROOT_DIR / "06_extraction"
FIGURES_DIR       = ROOT_DIR / "07_figures"
FULL_TEXTS_DIR    = ROOT_DIR / "08_full_texts"

ALL_DIRS: list[Path] = [
    PROTOCOL_DIR,
    SEARCH_LOGS_DIR,
    RAW_EXPORTS_DIR,
    DEDUPED_DIR,
    SCREENING_DIR,
    EXTRACTION_DIR,
    FIGURES_DIR,
    FULL_TEXTS_DIR,
]

# ---------------------------------------------------------------------------
# Key file paths
# ---------------------------------------------------------------------------
SEARCH_LOG_XLSX       = SEARCH_LOGS_DIR / "search_log.xlsx"
PRISMA_COUNTS_XLSX    = SEARCH_LOGS_DIR / "prisma_counts.xlsx"
MASTER_RECORDS_CSV    = DEDUPED_DIR / "master_records.csv"
MASTER_LIBRARY_BIB    = DEDUPED_DIR / "master_library.bib"
MASTER_LIBRARY_RIS    = DEDUPED_DIR / "master_library.ris"

TA_DECISIONS_TEMPLATE = SCREENING_DIR / "title_abstract_decisions_template.csv"
FT_DECISIONS_TEMPLATE = SCREENING_DIR / "full_text_decisions_template.csv"
TA_DECISIONS_FILE     = SCREENING_DIR / "title_abstract_decisions.csv"
FT_DECISIONS_FILE     = SCREENING_DIR / "full_text_decisions.csv"

CALIBRATION_DECISIONS_CSV = SCREENING_DIR / "calibration_decisions.csv"
CALIBRATION_LOG_MD       = SCREENING_DIR / "calibration_log.md"

# Screening workbook paths
CALIBRATION_SCREENING_XLSX = SCREENING_DIR / "calibration_screening.xlsx"
VALIDATION_SCREENING_XLSX  = SCREENING_DIR / "validation_screening.xlsx"
REVIEWER_A_SCREENING_XLSX  = SCREENING_DIR / "screening_reviewer_A.xlsx"
REVIEWER_B_SCREENING_XLSX  = SCREENING_DIR / "screening_reviewer_B.xlsx"

# ASReview data files
ASREVIEW_DATASET_CSV      = SCREENING_DIR / "asreview_dataset.csv"
ASREVIEW_PRIOR_LABELS_CSV = SCREENING_DIR / "asreview_prior_labels.csv"

# AI-assisted screening (Protocol §8, Amendment A8)
AI_SCREENING_DECISIONS  = SCREENING_DIR / "ai_screening_decisions.csv"
AI_DISCREPANCY_REVIEW   = SCREENING_DIR / "ai_discrepancy_review.csv"
AI_VALIDATION_REPORT    = SCREENING_DIR / "ai_validation_report.md"
VALIDATION_DECISIONS    = SCREENING_DIR / "validation_decisions.csv"
FN_AUDIT_SAMPLE         = SCREENING_DIR / "fn_audit_sample.csv"

EXTRACTION_TEMPLATE   = EXTRACTION_DIR / "extraction_template.xlsx"
CODEBOOK_MD           = EXTRACTION_DIR / "codebook.md"
TOPIC_TAXONOMY_MD     = EXTRACTION_DIR / "topic_taxonomy.md"
TOPIC_CODING_CSV      = EXTRACTION_DIR / "topic_coding.csv"
TOPIC_CODING_SUMMARY  = EXTRACTION_DIR / "topic_coding_summary.md"
TOPIC_CODING_CHECKPOINT = EXTRACTION_DIR / "topic_coding_checkpoint.json"
TOPIC_CODING_PROMPT_LOG = EXTRACTION_DIR / "topic_coding_prompt_log.jsonl"

# Tier classification (Phase B — cross-repo integration)
TIER_CLASSIFICATION_CSV        = EXTRACTION_DIR / "tier_classification.csv"
TIER_CLASSIFICATION_SUMMARY    = EXTRACTION_DIR / "tier_classification_summary.md"
TIER_CLASSIFICATION_CHECKPOINT = EXTRACTION_DIR / "tier_classification_checkpoint.json"
TIER_CLASSIFICATION_PROMPT_LOG = EXTRACTION_DIR / "tier_classification_prompt_log.jsonl"

PROTOCOL_MD           = PROTOCOL_DIR / "protocol.md"
AMENDMENTS_CSV        = PROTOCOL_DIR / "amendments_log.csv"

# Full-text PDFs (§ post-screening download)
INCLUDED_FOR_CODING   = SCREENING_DIR / "included_for_coding.csv"
DOWNLOAD_LOG_CSV      = FULL_TEXTS_DIR / "download_log.csv"

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------
NORMALIZED_COLUMNS: list[str] = [
    "paper_id",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "abstract",
    "keywords",
    "source_db",
    "export_file",
    "is_preprint",
    "version_group_id",
]

SEARCH_LOG_COLUMNS: list[str] = [
    "SearchRunID",
    "Date",
    "Database",
    "Interface",
    "FullSearchString",
    "Fields",
    "DateLimits",
    "LanguageLimits",
    "OtherLimits",
    "ResultsN",
    "ExportFormat",
    "ExportFiles",
    "Notes",
]

# Preprint venue patterns (case-insensitive substring match)
PREPRINT_VENUES: list[str] = [
    "arxiv", "ssrn", "preprint", "biorxiv", "medrxiv",
    "chemrxiv", "techrxiv", "engrxiv", "hal-",
]

# ---------------------------------------------------------------------------
# Dedup settings
# ---------------------------------------------------------------------------
FUZZY_TITLE_THRESHOLD: int = 90   # rapidfuzz token_sort_ratio threshold
YEAR_TOLERANCE: int = 1           # ±years for fuzzy matching

# ---------------------------------------------------------------------------
# OpenAlex API
# ---------------------------------------------------------------------------
OPENALEX_API_URL: str = "https://api.openalex.org/works"

# ---------------------------------------------------------------------------
# Recommended arXiv categories for quantum finance SLR.
# Apply via --arxiv-categories if arXiv results are unmanageably large.
# NOT applied by default — SLR methodology requires erring toward recall.
# ---------------------------------------------------------------------------
RECOMMENDED_ARXIV_CATEGORIES: list[str] = [
    "q-fin.*", "quant-ph", "cs.CE", "cs.AI", "cs.LG", "cs.CC", "cs.DS",
]

# ---------------------------------------------------------------------------
# Canonical SLR query — API-neutral, used by run_search.py and auto-search.
# Each query builder adapts this per-source (wildcard expansion, field
# prefixes, TITLE-ABS-KEY wrapping, etc.).
# ---------------------------------------------------------------------------
SLR_QUERY: str = (
    '("quantum computing" OR "quantum algorithm*" OR "quantum circuit*"'
    ' OR "gate-based quantum" OR "hybrid quantum-classical"'
    ' OR "variational quantum" OR QAOA OR VQE OR QAE'
    ' OR "quantum amplitude estimation"'
    ' OR "quantum phase estimation"'
    ' OR "Grover\'s algorithm" OR "Grover search"'
    ' OR "HHL algorithm" OR "Harrow-Hassidim-Lloyd"'
    ' OR "quantum linear system*"'
    ' OR "quantum walk*"'
    ' OR "quantum machine learning" OR "quantum neural network*"'
    ' OR "quantum error correction"'
    ' OR "fault-tolerant quantum" OR "fault tolerant quantum" OR NISQ'
    ' OR "quantum speedup" OR "quantum advantage"'
    ' OR "quantum annealing"'
    ' OR QMCI)'
    ' AND '
    '(finance OR financial OR "computational finance" OR "quantitative finance"'
    ' OR "portfolio optim*" OR "portfolio selection"'
    ' OR "portfolio management" OR "portfolio risk"'
    ' OR "asset allocation" OR "asset management"'
    ' OR "option pricing" OR "derivative pricing"'
    ' OR "financial derivative*" OR "structured product*"'
    ' OR "fixed income" OR "bond pricing"'
    ' OR "interest rate" OR "interest rate derivative*"'
    ' OR "credit risk" OR "market risk"'
    ' OR "counterparty risk" OR "liquidity risk"'
    ' OR "value at risk" OR VaR'
    ' OR "expected shortfall" OR CVaR'
    ' OR "credit valuation adjustment" OR CVA OR xVA'
    ' OR "potential future exposure" OR PFE'
    ' OR "Black-Scholes" OR Greeks'
    ' OR "credit scoring" OR "default prediction"'
    ' OR "fraud detection" OR "anti-money laundering"'
    ' OR "algorithmic trading" OR "trade execution"'
    ' OR "market microstructure"'
    ' OR "stock market" OR "stock price*"'
    ' OR "hedge fund" OR "financial hedging"'
    ' OR "financial engineering" OR "financial forecasting")'
)

# Scopus-formatted version of SLR_QUERY (for manual Scopus advanced search).
SCOPUS_QUERY_TEMPLATE: str = (
    f"TITLE-ABS-KEY({SLR_QUERY}) AND PUBYEAR > 2015"
)
