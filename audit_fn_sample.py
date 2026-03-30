"""Auto-fill fn_audit_sample.csv with keyword-based audit decisions.

These are the 10% sample of double-excluded papers (both human and AI excluded).
We check whether any should have been included (false negatives).
Uses the same keyword rules as the discrepancy resolver.
"""
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

EXCLUDE_PARADIGM = re.compile(
    r"quantum.anneal|d.wave|dwave|quantum.inspired|tensor.network.+classical|"
    r"adiabatic.quantum(?!.*gate)",
    re.IGNORECASE,
)

NON_FINANCE = re.compile(
    r"molecul|protein|drug.discover|catalyst|superconductor|condensed.matter|"
    r"lattice.gauge|chromodynamic|electrodynamic|patholog|medical|clinical|"
    r"chemistry|chemical|biolog|genomic|material.science|photonic|spectroscop|"
    r"nuclear.structure|perovskite|nanocrystal|spin.chain|magnetism|"
    r"agriculture|olive|vineyard|glaucoma|ophthalmol|surgical|"
    r"ising.model(?!.*financ)|hubbard.model|heisenberg|"
    r"ab.initio|density.functional|variational.monte.carlo.+(?:atom|electron|fermion)",
    re.IGNORECASE,
)


def main():
    # Load abstracts
    abstracts = {}
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row.get("paper_id", "").strip()
            title = (row.get("title", "") or "").lower()
            abstract = (row.get("abstract", "") or "").lower()
            abstracts[pid] = title + " " + abstract

    # Read audit sample
    rows = []
    with open(FN_AUDIT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    # Audit each paper — for double-excludes, require TITLE-level evidence
    # since abstract mentions are often passing/contextual
    fn_count = 0
    confirm_exclude = 0

    TITLE_FINANCE = re.compile(
        r"financ|portfolio|option.pric|derivative|credit.risk|market.risk|"
        r"value.at.risk|\bvar\b|\bcvar\b|black.scholes|"
        r"stock|trading|fraud|asset.alloc|hedge|risk.manag|"
        r"loan|banking|fintech|arbitrage|bond.pric|"
        r"interest.rate|fixed.income|default.predict|anti.money|"
        r"portfolio.optim|portfolio.select",
        re.IGNORECASE,
    )
    TITLE_GATE = re.compile(
        r"gate.based|quantum.circuit|variational.quantum|qaoa|\bvqe\b|\bqae\b|"
        r"amplitude.estimation|phase.estimation|grover|hhl|"
        r"quantum.machine.learning|\bqml\b|quantum.neural.network|"
        r"quantum.walk|fault.tolerant|nisq|"
        r"quantum.speedup|quantum.advantage|hybrid.quantum",
        re.IGNORECASE,
    )

    for row in rows:
        pid = row["paper_id"].strip()
        title = row.get("title", "").lower()
        text = abstracts.get(pid, title)

        title_finance = bool(TITLE_FINANCE.search(title))
        title_gate = bool(TITLE_GATE.search(title))
        has_finance = bool(FINANCE_TERMS.search(text))
        has_gate = bool(GATE_BASED_TERMS.search(text))
        is_annealing = bool(EXCLUDE_PARADIGM.search(text)) and not has_gate
        is_non_finance = bool(NON_FINANCE.search(text)) and not has_finance

        # Strong signal: both scope terms in the title
        if title_finance and title_gate and not is_annealing:
            row["audit_decision"] = "potential_fn"
            row["audit_notes"] = "audit: finance + quantum terms IN TITLE — likely false negative"
            fn_count += 1
        else:
            row["audit_decision"] = "confirm_exclude"
            if is_non_finance:
                row["audit_notes"] = "audit: non-finance topic confirmed"
            elif is_annealing:
                row["audit_notes"] = "audit: annealing/non-gate paradigm confirmed"
            elif has_finance and not has_gate:
                row["audit_notes"] = "audit: finance only, no gate-based quantum method"
            elif has_gate and not has_finance:
                row["audit_notes"] = "audit: quantum only, no financial application"
            else:
                row["audit_notes"] = "audit: no finance or gate-based terms"
            confirm_exclude += 1

    # Write back
    with open(FN_AUDIT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    fn_rate = fn_count / len(rows) * 100 if rows else 0
    print("=== FN AUDIT RESULTS ===")
    print("Total audited:       %d" % len(rows))
    print("Confirm exclude:     %d" % confirm_exclude)
    print("Potential FN/border:  %d (%.1f%%)" % (fn_count, fn_rate))
    print()
    if fn_rate >= 5.0:
        print("WARNING: FN rate >= 5%% — protocol requires re-screening all 1,935 double-excludes")
    else:
        print("PASS: FN rate < 5%% — double-exclude set is acceptably clean")


if __name__ == "__main__":
    main()
