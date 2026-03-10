Search Run Export Folder
========================
Source database : arxiv
Date            : 2026-03-10

Instructions
------------
1. Run your search query in arxiv.
2. Export results in one of these formats:
   - RIS  (.ris)
   - BibTeX (.bib)
   - CSV  (.csv)
3. Place the exported file(s) in THIS folder.
4. Then ingest them:
   python -m tools.slr_toolkit.cli ingest --run-folder "C:\Users\t-vwallerich\OneDrive - Microsoft\Quantum\SLR\quantum-finance-slr\03_raw_exports\2026-03-10_arxiv"
5. **PRISMA-S mandatory:** update 02_search_logs/search_log.xlsx with:
   - Interface: e.g. "Scopus web", "WoS Basic Search", "IEEE Xplore"
   - FullSearchString: exact copy-paste of the query as executed
   - Fields: e.g. TITLE-ABS-KEY, ALL
   - DateLimits: e.g. 2016-01-01 to 2026-03-10
   - LanguageLimits: e.g. English (or blank if none)
   - ResultsN: number of hits returned
