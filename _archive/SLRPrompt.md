You are Claude Code acting as a senior Python engineer + research ops assistant.

GOAL
Create a clean, reproducible Git repository for a two-stage SLR (Stage A mapping + Stage B focused SLR) with a “search run” workflow. The repo must help us:
1) initialize a standard folder structure,
2) create new search runs (date-stamped),
3) log search metadata (PRISMA-S style),
4) ingest/export bibliographic exports (RIS/BibTeX/CSV) into a master dataset,
5) deduplicate records (basic DOI/title logic),
6) generate PRISMA counts from screening decision files.

CONSTRAINTS
- Use Python (preferred). Assume Python 3.11+.
- No network calls. Everything is local file-based.
- Output must be reproducible, with clear README instructions and command examples.
- Keep it simple and robust; don’t over-engineer.
- Use standard libs + these dependencies only if needed: pandas, openpyxl, rispy, bibtexparser, rapidfuzz (optional), python-dotenv (optional).
- Provide unit tests where reasonable (pytest), but keep them minimal.

REPO NAME
quantum-finance-slr

STRUCTURE (create exactly this top-level layout)
/
  README.md
  pyproject.toml (or requirements.txt if you prefer)
  .gitignore
  /01_protocol/
    protocol_v1.0.md
    amendments_log.csv
  /02_search_logs/
    search_log.xlsx
    prisma_counts.xlsx (auto-generated)
  /03_raw_exports/
    (empty; raw exports go here)
  /04_deduped_library/
    master_records.csv (auto-generated)
    master_library.bib (auto-generated)
    master_library.ris (auto-generated if feasible)
  /05_screening/
    title_abstract_decisions_template.csv
    full_text_decisions_template.csv
    (user exports decisions here)
  /06_extraction/
    extraction_template.xlsx
    codebook.md
  /07_figures/
    (generated figures; optional)
  /tools/
    slr_toolkit/
      __init__.py
      cli.py
      config.py
      utils.py
      search_run.py
      ingest.py
      dedup.py
      prisma.py
      templates.py
    tests/
      test_dedup.py
      test_ingest_smoke.py

SLR CONTEXT (put in README + protocol template)
- Two-stage design (Stage A mapping, Stage B focused SLR).
- Scope: gate-based QC in finance; include preprints; NISQ + fault-tolerant projections.
- Time window: 2016-01-01 to present.
- We assess “practical advantage” using a Tier-1 crossover target (≤2 weeks) + Tier-2 finance SLA reality check.
(You don’t need to implement scientific evaluation; just store fields and workflow.)

CLI REQUIREMENTS (must implement)
1) Init (idempotent)
   python -m tools.slr_toolkit.cli init
   - Creates any missing folders/templates.
   - Does not overwrite existing files unless --force is passed.

2) Create search run
   python -m tools.slr_toolkit.cli new-search-run --source scopus --date 2026-03-08
   - Creates a folder: /03_raw_exports/2026-03-08_scopus/
   - Places a README.txt inside explaining what to export and where to put files.
   - Appends a new row to /02_search_logs/search_log.xlsx with:
     SearchRunID, Date, Database, Query, Fields, Filters, ResultsN, ExportFormat, ExportFiles, Notes
   - If the xlsx doesn’t exist, create it with correct columns and nice formatting.

3) Ingest exports
   python -m tools.slr_toolkit.cli ingest --run-folder /03_raw_exports/2026-03-08_scopus
   - Reads any of: .ris, .bib, .csv.
   - Normalizes into a standard dataframe with columns at minimum:
     paper_id (stable hash), title, authors, year, venue, doi, abstract, keywords, source_db, export_file
   - Writes a run-level normalized CSV into the run folder (e.g., normalized_records.csv).

4) Build master library
   python -m tools.slr_toolkit.cli build-master
   - Scans all run folders under /03_raw_exports/*/
   - Loads each normalized_records.csv (or ingests on the fly if missing)
   - Deduplicates across runs:
     Primary key: DOI exact match (case-insensitive)
     Secondary: fuzzy title match (rapidfuzz optional) + year within ±1 + first author initial
     Keep a “duplicate_of” column.
   - Outputs:
     /04_deduped_library/master_records.csv
     /04_deduped_library/master_library.bib (minimum fields; skip if bibtex not available)
   - Prints summary counts: total ingested, deduped unique, duplicates.

5) PRISMA counts
   python -m tools.slr_toolkit.cli prisma
   - Reads screening decision files in /05_screening/:
     title_abstract_decisions.csv (user copies from template)
     full_text_decisions.csv (user copies from template)
   - Generates /02_search_logs/prisma_counts.xlsx with:
     Identified, DuplicatesRemoved, ScreenedTitleAbstract, ExcludedTitleAbstract,
     FullTextAssessed, ExcludedFullText, IncludedStageA, IncludedStageB
   - If some files are missing, generate partial counts and clearly mark missing inputs.

TEMPLATES TO CREATE (must implement via templates.py)
A) /05_screening/title_abstract_decisions_template.csv with columns:
   paper_id, decision_A, decision_B, conflict, final_decision, reason_code, notes
   - final_decision values: include/exclude/maybe
B) /05_screening/full_text_decisions_template.csv with columns:
   paper_id, decision_A, decision_B, conflict, final_decision, exclusion_reason, notes
C) /06_extraction/extraction_template.xlsx with sheets:
   - Codebook (column name, definition, allowed values)
   - Extraction (one row per paper_id; include key fields like problem_family, quantum_method, evaluation_type, NISQ_vs_FT, baseline_strength, etc.)
   - Rubric (0–2 scoring columns; free-text justification)
D) /01_protocol/protocol_v1.0.md containing a concise protocol skeleton (scope, RQs, databases, search logging, screening, extraction, synthesis plan, amendment log pointer).

QUALITY
- Add clear README with:
  - setup instructions
  - example commands
  - where to put exports
  - how to update screening files
  - how PRISMA counts are computed
- Ensure scripts handle missing fields gracefully (e.g., missing DOI).
- Use type hints and logging.
- Provide minimal pytest tests for dedup and ingest parsing.

DELIVERABLE
Generate all files in the repo as described. Provide a short summary at the end listing created commands and paths. Do not ask me questions; make reasonable assumptions and implement.

Start now by creating the full repo structure and the Python package + CLI.