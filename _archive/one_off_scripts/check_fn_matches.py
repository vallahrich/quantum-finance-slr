"""Quick diagnostic: why are so many FN audit papers flagged?"""
import csv
import re
from pathlib import Path

FN_AUDIT_CSV = Path("05_screening/fn_audit_sample.csv")
MASTER_CSV = Path("04_deduped_library/master_records.csv")

FINANCE_TERMS = re.compile(
    r"financ|portfolio|option.pric|derivative.pric|credit.risk|market.risk|"
    r"value.at.risk|\bvar\b|\bcvar\b|black.scholes|monte.carlo.+pric|"
    r"stock.market|stock.price|trading|fraud.detect|credit.scor|"
    r"asset.alloc|hedge|risk.manag|insurance|actuarial|"
    r"loan|banking|fintech|algorithmic.trad|arbitrage|"
    r"financial.forecast|quantitative.finance|computational.finance|"
    r"expected.shortfall|counterparty|liquidity.risk|bond.pric|"
    r"interest.rate|fixed.income|default.predict|anti.money|"
    r"market.microstructure|portfolio.optim|portfolio.select|"
    r"option.valuat|structured.product",
    re.IGNORECASE,
)

GATE_BASED_TERMS = re.compile(
    r"gate.based|quantum.circuit|variational.quantum|qaoa|\bvqe\b|\bqae\b|"
    r"amplitude.estimation|phase.estimation|grover|hhl|"
    r"quantum.machine.learning|\bqml\b|quantum.neural.network|"
    r"quantum.walk|quantum.error.correct|fault.tolerant|nisq|"
    r"quantum.speedup|quantum.advantage|hybrid.quantum.classical|"
    r"qubit|quantum.comput|quantum.algorithm",
    re.IGNORECASE,
)

abstracts = {}
with open(MASTER_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        pid = row.get("paper_id", "").strip()
        title = (row.get("title", "") or "").lower()
        abstract = (row.get("abstract", "") or "").lower()
        abstracts[pid] = title + " " + abstract

rows = list(csv.DictReader(open(FN_AUDIT_CSV, newline="", encoding="utf-8")))

flagged = [r for r in rows if r.get("audit_decision") == "potential_fn"]
print("Flagged potential_fn: %d" % len(flagged))
print()

# Show first 15 with the matching terms
for r in flagged[:15]:
    pid = r["paper_id"]
    text = abstracts.get(pid, "")
    fin_matches = FINANCE_TERMS.findall(text)[:3]
    gate_matches = GATE_BASED_TERMS.findall(text)[:3]
    print("---")
    print("TITLE: %s" % r["title"][:100])
    print("  Finance matches: %s" % fin_matches)
    print("  Gate matches: %s" % gate_matches)
    print("  AI confidence: %s" % r.get("ai_confidence", "?"))
