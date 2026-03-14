"""One-off script: run full search pipeline across all sources."""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

from tools.slr_toolkit.api_search import auto_search  # noqa: E402
from tools.slr_toolkit.config import SLR_QUERY  # noqa: E402

print(f"Query: {SLR_QUERY}", flush=True)
print("Sources: openalex, arxiv, semantic_scholar, scopus", flush=True)
print("Max results: no limit (fetch all)", flush=True)
print("Starting...\n", flush=True)

folders = auto_search(
    SLR_QUERY,
    sources=["openalex", "arxiv", "semantic_scholar", "scopus"],
    from_year=2016,
    max_results=None,
    run_date="2026-03-14-v5",
)

print(f"\n=== Done. {len(folders)} source(s) ingested ===", flush=True)
for src, path in folders.items():
    print(f"  {src} -> {path}", flush=True)
