"""One-off script: run full search pipeline across all sources."""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

from tools.slr_toolkit.api_search import auto_search  # noqa: E402

QUERY = (
    '("quantum computing" OR "quantum algorithm" OR "quantum circuit" '
    'OR qubit OR "variational quantum" OR QAOA OR VQE OR QAE '
    'OR "quantum amplitude estimation" OR Grover OR HHL '
    'OR "quantum walk" OR "quantum machine learning" OR QML '
    'OR "quantum annealing" OR "quantum error correction" '
    'OR "fault-tolerant quantum" OR NISQ OR "quantum speedup" '
    'OR "quantum advantage" OR "quantum Monte Carlo") '
    "AND "
    '(finance OR financial OR portfolio OR "risk management" '
    'OR "option pricing" OR derivative OR "credit risk" '
    'OR "market risk" OR "stock market" OR trading '
    'OR "asset allocation" OR "Monte Carlo" OR "Black-Scholes" '
    'OR VaR OR "value at risk" OR "quantitative finance" '
    'OR "credit scoring" OR "fraud detection" OR CVA OR xVA '
    'OR "algorithmic trading" OR hedging OR banking)'
)

print(f"Query: {QUERY}", flush=True)
print("Sources: openalex, arxiv, scopus", flush=True)
print("Max results: 10000 per source", flush=True)
print("Starting...\n", flush=True)

folders = auto_search(
    QUERY,
    sources=["openalex", "arxiv", "scopus"],
    from_year=2016,
    max_results=10000,
    run_date="2026-03-09",
)

print(f"\n=== Done. {len(folders)} source(s) ingested ===", flush=True)
for src, path in folders.items():
    print(f"  {src} -> {path}", flush=True)
