"""Auto-resolve clear-cut screening discrepancies.

Applies protocol inclusion criteria (§4, §9) via keyword matching against
titles and abstracts. Errs toward inclusion per SLR methodology.

- agree_include / agree_exclude → auto-confirmed
- human_only (human=include, AI=exclude) → confirm human UNLESS clearly off-scope
- ai_rescue  (AI=include, human=exclude) → include if finance + gate-based; exclude if off-scope

Leaves ambiguous cases with notes='MANUAL REVIEW NEEDED' for human resolution.
"""
import csv
import re
import shutil
from datetime import datetime
from pathlib import Path

SCREENING_DIR = Path("05_screening")
MASTER_CSV = Path("04_deduped_library/master_records.csv")
DISCREPANCY_CSV = SCREENING_DIR / "ai_discrepancy_review.csv"
AI_DECISIONS_CSV = SCREENING_DIR / "ai_screening_decisions.csv"

# ── Keyword patterns based on protocol §4 and §9 ──

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

NON_ENGLISH = re.compile(
    r"\u0430\u043d\u0430\u043b\u0438\u0437|\u0438\u0441\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d|"
    r"\u0440\u043e\u0437\u0440\u043e\u0431\u043a|PREDIKSI|ANALISIS|"
    r"Acci\u00f3n|MENGGUNAKAN|Bursa.Efek|\u0412\u0415\u041a\u0422\u041e\u0420",
    re.IGNORECASE,
)

SURVEY_ONLY = re.compile(
    r"^(a )?review of|^survey of|literature review|systematic review|"
    r"comprehensive review|state.of.the.art|tutorial|overview|handbook|"
    r"beginner.s guide|textbook|book chapter",
    re.IGNORECASE,
)


def auto_resolve(pid, discrepancy_type, ai_confidence, title, abstracts, ai_reasons):
    """Return (decision, note) or (None, None) if manual review needed."""
    text = abstracts.get(pid, title.lower())
    reason = ai_reasons.get(pid, "")
    conf = float(ai_confidence) if ai_confidence else 0.5

    has_finance = bool(FINANCE_TERMS.search(text))
    has_gate = bool(GATE_BASED_TERMS.search(text))
    is_annealing_only = bool(EXCLUDE_PARADIGM.search(text)) and not has_gate
    is_non_finance = bool(NON_FINANCE.search(text)) and not has_finance
    is_non_english = bool(NON_ENGLISH.search(text))
    is_survey = bool(SURVEY_ONLY.search(text))

    if discrepancy_type == "agree_include":
        return "include", "auto: both agree include"

    if discrepancy_type == "agree_exclude":
        return "exclude", "auto: both agree exclude"

    if discrepancy_type == "human_only":
        # Human included, AI excluded. SLR errs toward inclusion.
        if is_non_english:
            return "exclude", "auto: non-English detected (overrides human)"
        if is_non_finance and not has_finance:
            return "exclude", "auto: non-finance topic, no finance terms (%s)" % reason
        if is_annealing_only:
            return "exclude", "auto: annealing-only, not gate-based (%s)" % reason
        # Trust the human
        return "include", "auto: human include confirmed (AI conf=%.2f, reason=%s)" % (conf, reason)

    if discrepancy_type == "ai_rescue":
        # AI included, human excluded. Check if AI caught a real miss.
        if is_non_english:
            return "exclude", "auto: non-English - human exclude confirmed"
        if is_non_finance and not has_finance:
            return "exclude", "auto: non-finance - human exclude confirmed"
        if is_annealing_only:
            return "exclude", "auto: annealing-only - human exclude confirmed"
        if is_survey:
            return "exclude", "auto: survey/review - excluded per protocol S4"
        if has_finance and has_gate:
            return "include", "auto: AI rescue accepted - finance + gate-based (conf=%.2f)" % conf
        if has_finance and conf >= 0.80:
            return "include", "auto: AI rescue accepted - finance terms + high conf (%.2f)" % conf
        if has_gate and conf >= 0.80:
            # Has quantum but no finance - ambiguous
            return None, None
        # Low confidence, no clear scope match
        return "exclude", "auto: low scope match - human exclude confirmed (conf=%.2f)" % conf

    return None, None


def main():
    # ── Load data ──
    abstracts = {}
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row.get("paper_id", "").strip()
            title = (row.get("title", "") or "").lower()
            abstract = (row.get("abstract", "") or "").lower()
            abstracts[pid] = title + " " + abstract

    ai_reasons = {}
    with open(AI_DECISIONS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row.get("paper_id", "").strip()
            ai_reasons[pid] = row.get("reason_code", "").strip()

    print("Loaded %d abstracts, %d AI reasons" % (len(abstracts), len(ai_reasons)))

    # ── Backup ──
    backup_dir = SCREENING_DIR / "_backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / ("ai_discrepancy_review_backup_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(DISCREPANCY_CSV, backup)
    print("Backup: %s" % backup)

    # ── Read discrepancies ──
    rows = []
    with open(DISCREPANCY_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    # ── Resolve ──
    stats = {"auto_include": 0, "auto_exclude": 0, "manual_needed": 0}
    by_type = {}

    for row in rows:
        dt = row.get("discrepancy_type", "").strip()
        pid = row.get("paper_id", "").strip()
        conf = row.get("ai_confidence", "0.5")
        title = row.get("title", "")

        decision, note = auto_resolve(pid, dt, conf, title, abstracts, ai_reasons)

        if decision:
            row["re_review_decision"] = decision
            row["notes"] = note
            if decision == "include":
                stats["auto_include"] += 1
            else:
                stats["auto_exclude"] += 1
        else:
            stats["manual_needed"] += 1
            row["notes"] = "MANUAL REVIEW NEEDED"

        by_type.setdefault(dt, {"include": 0, "exclude": 0, "manual": 0})
        if decision == "include":
            by_type[dt]["include"] += 1
        elif decision == "exclude":
            by_type[dt]["exclude"] += 1
        else:
            by_type[dt]["manual"] += 1

    # ── Write ──
    with open(DISCREPANCY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # ── Report ──
    print()
    print("=== AUTO-RESOLUTION SUMMARY ===")
    print("Total rows:                %d" % len(rows))
    print("Auto-resolved to INCLUDE:  %d" % stats["auto_include"])
    print("Auto-resolved to EXCLUDE:  %d" % stats["auto_exclude"])
    print("MANUAL REVIEW still needed: %d" % stats["manual_needed"])
    print()
    for dt in ["agree_include", "agree_exclude", "human_only", "ai_rescue"]:
        if dt in by_type:
            d = by_type[dt]
            print("  %-20s  include=%4d  exclude=%4d  manual=%4d" % (dt, d["include"], d["exclude"], d["manual"]))


if __name__ == "__main__":
    main()
