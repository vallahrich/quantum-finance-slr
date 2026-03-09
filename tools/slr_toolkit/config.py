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

ALL_DIRS: list[Path] = [
    PROTOCOL_DIR,
    SEARCH_LOGS_DIR,
    RAW_EXPORTS_DIR,
    DEDUPED_DIR,
    SCREENING_DIR,
    EXTRACTION_DIR,
    FIGURES_DIR,
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

EXTRACTION_TEMPLATE   = EXTRACTION_DIR / "extraction_template.xlsx"
CODEBOOK_MD           = EXTRACTION_DIR / "codebook.md"
PROTOCOL_MD           = PROTOCOL_DIR / "protocol_v1.0.md"
AMENDMENTS_CSV        = PROTOCOL_DIR / "amendments_log.csv"

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
