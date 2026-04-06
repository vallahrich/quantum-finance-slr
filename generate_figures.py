"""Generate SLR figures for 06_figures/ (Step 1: search & screening)."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

REPO = Path(__file__).resolve().parent
FIGURES = REPO / "06_figures"
FIGURES.mkdir(exist_ok=True)

# Styling
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

PALETTE = [
    "#2171b5", "#6baed6", "#bdd7e7",  # blues
    "#238b45", "#74c476", "#bae4b3",  # greens
    "#d94801", "#fd8d3c", "#fdd0a2",  # oranges
    "#756bb1", "#bcbddc", "#dadaeb",  # purples
]


def _load_master() -> pd.DataFrame:
    df = pd.read_csv(REPO / "04_deduped_library" / "master_records.csv", dtype=str).fillna("")
    return df[df["duplicate_of"] == ""]


def _load_ai_screening() -> pd.DataFrame:
    return pd.read_csv(REPO / "05_screening" / "ai_screening_decisions.csv", dtype=str).fillna("")


# ── Figure 1: PRISMA flow diagram ─────────────────────────────────────────
def fig_prisma_flow():
    """Generate a PRISMA 2020 flow diagram."""
    master_full = pd.read_csv(REPO / "04_deduped_library" / "master_records.csv", dtype=str).fillna("")

    n_identified = len(master_full)
    n_duplicates = int((master_full["duplicate_of"] != "").sum())
    n_screened = n_identified - n_duplicates

    # Full-text decisions (includes both included and excluded at full-text)
    ft_path = REPO / "05_screening" / "full_text_decisions.csv"
    if ft_path.exists():
        ft = pd.read_csv(ft_path, dtype=str).fillna("")
        n_assessed_ft = len(ft)
        n_excluded_ft = int((ft["final_decision"].str.strip().str.lower() == "exclude").sum())
        n_included_ft = int((ft["final_decision"].str.strip().str.lower() == "include").sum())
    else:
        inc_path = REPO / "05_screening" / "included_for_coding.csv"
        if inc_path.exists():
            inc = pd.read_csv(inc_path, dtype=str)
            n_included_ft = len(inc)
        else:
            n_included_ft = 0
        n_assessed_ft = n_included_ft
        n_excluded_ft = 0

    n_excluded_ta = n_screened - n_assessed_ft

    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")

    box_style = dict(boxstyle="round,pad=0.4", facecolor="#e8f0fe", edgecolor="#2171b5", linewidth=1.5)
    excl_style = dict(boxstyle="round,pad=0.4", facecolor="#fce4e4", edgecolor="#d94801", linewidth=1.5)
    final_style = dict(boxstyle="round,pad=0.4", facecolor="#e6f4ea", edgecolor="#238b45", linewidth=1.5)

    # Identification
    ax.text(5, 11.2, "Identification", fontsize=14, fontweight="bold", ha="center")
    ax.text(5, 10.5, f"Records identified through\ndatabase searching\n(n = {n_identified:,})",
            ha="center", va="center", fontsize=10, bbox=box_style)

    # Sources breakdown
    sources = master_full["source_db"].value_counts()
    src_text = "  ".join(f"{s}: {c:,}" for s, c in sources.items())
    ax.text(5, 9.6, src_text, ha="center", va="center", fontsize=8, style="italic", color="#555")

    # Arrow
    ax.annotate("", xy=(5, 9.1), xytext=(5, 9.4), arrowprops=dict(arrowstyle="->", lw=1.5))

    # Duplicates removed
    ax.text(8, 9.1, f"Duplicates removed\n(n = {n_duplicates:,})", ha="center", va="center",
            fontsize=10, bbox=excl_style)
    ax.annotate("", xy=(6.5, 9.1), xytext=(5.3, 8.8), arrowprops=dict(arrowstyle="->", lw=1))

    # Screening
    ax.text(5, 8.5, "Screening", fontsize=14, fontweight="bold", ha="center")
    ax.text(5, 7.8, f"Records screened\n(title/abstract)\n(n = {n_screened:,})",
            ha="center", va="center", fontsize=10, bbox=box_style)

    ax.annotate("", xy=(5, 7.1), xytext=(5, 7.4), arrowprops=dict(arrowstyle="->", lw=1.5))

    # Excluded at T/A
    ax.text(8, 7.1, f"Records excluded\n(n = {n_excluded_ta:,})", ha="center", va="center",
            fontsize=10, bbox=excl_style)
    ax.annotate("", xy=(6.5, 7.1), xytext=(5.5, 7.1), arrowprops=dict(arrowstyle="->", lw=1))

    # Eligibility
    ax.text(5, 6.2, "Eligibility", fontsize=14, fontweight="bold", ha="center")
    ax.text(5, 5.5, f"Full-text articles assessed\nfor eligibility\n(n = {n_assessed_ft:,})",
            ha="center", va="center", fontsize=10, bbox=box_style)

    # Excluded at full-text
    if n_excluded_ft > 0:
        ax.text(8, 5.5, f"Full-text articles excluded\n(n = {n_excluded_ft:,})\nReason: no paper found",
                ha="center", va="center", fontsize=10, bbox=excl_style)
        ax.annotate("", xy=(6.5, 5.5), xytext=(5.5, 5.5), arrowprops=dict(arrowstyle="->", lw=1))

    ax.annotate("", xy=(5, 4.7), xytext=(5, 5.0), arrowprops=dict(arrowstyle="->", lw=1.5))

    # Included
    ax.text(5, 3.8, "Included", fontsize=14, fontweight="bold", ha="center")
    ax.text(5, 3.1, f"Studies included in\nsystematic review\n(n = {n_included_ft:,})",
            ha="center", va="center", fontsize=10, bbox=final_style)

    # Note about PDFs
    import os
    n_pdfs = len([f for f in os.listdir(REPO / "07_full_texts" / "pdfs") if f.endswith(".pdf")])
    ax.text(5, 2.2,
            f"Full-text PDFs retrieved: {n_pdfs:,} / {n_included_ft:,}",
            ha="center", va="center", fontsize=9, style="italic", color="#555")

    fig.savefig(FIGURES / "fig1_prisma_flow.png")
    fig.savefig(FIGURES / "fig1_prisma_flow.pdf")
    plt.close(fig)
    print("  fig1_prisma_flow")


# ── Figure 2: Publication year distribution ───────────────────────────────
def fig_year_distribution():
    """Bar chart of publications by year."""
    master = _load_master()
    master["year_int"] = pd.to_numeric(master["year"], errors="coerce")
    master = master.dropna(subset=["year_int"])
    master["year_int"] = master["year_int"].astype(int)

    # Focus on 2016+ (SLR scope)
    recent = master[master["year_int"] >= 2016]
    year_counts = recent["year_int"].value_counts().sort_index()

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(year_counts.index, year_counts.values, color="#2171b5", edgecolor="white", width=0.8)

    # Add count labels
    for bar, count in zip(bars, year_counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 8,
                str(count), ha="center", va="bottom", fontsize=9)

    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Number of Records")
    ax.set_title("Records Identified by Publication Year (2016–2026)")
    ax.set_xticks(year_counts.index)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(FIGURES / "fig2_year_distribution.png")
    fig.savefig(FIGURES / "fig2_year_distribution.pdf")
    plt.close(fig)
    print("  fig2_year_distribution")


# ── Figure 3: Source database contribution ────────────────────────────────
def fig_source_distribution():
    """Horizontal bar chart of records by source database."""
    master = _load_master()
    src = master["source_db"].value_counts()

    fig, ax = plt.subplots(figsize=(7, 4))
    colors = ["#2171b5", "#6baed6", "#bdd7e7", "#d4e4f3"]
    bars = ax.barh(src.index, src.values, color=colors[:len(src)], edgecolor="white")

    for bar, count in zip(bars, src.values):
        ax.text(bar.get_width() + 10, bar.get_y() + bar.get_height() / 2,
                f"{count:,}", ha="left", va="center", fontsize=10)

    ax.set_xlabel("Number of Unique Records")
    ax.set_title("Records by Source Database")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(FIGURES / "fig3_source_distribution.png")
    fig.savefig(FIGURES / "fig3_source_distribution.pdf")
    plt.close(fig)
    print("  fig3_source_distribution")


# ── Figure 4: Screening exclusion reasons ─────────────────────────────────
def fig_exclusion_reasons():
    """Horizontal bar chart of final exclusion reasons for all excluded papers."""
    from collections import Counter

    master = pd.read_csv(REPO / "04_deduped_library" / "master_records.csv", dtype=str).fillna("")
    unique_ids = set(master[master["duplicate_of"] == ""]["paper_id"])
    inc = pd.read_csv(REPO / "05_screening" / "included_for_coding.csv", dtype=str).fillna("")
    inc_ids = set(inc["paper_id"])
    exc_ids = unique_ids - inc_ids

    ai = _load_ai_screening()
    ai_reason = dict(zip(ai["paper_id"], ai["reason_code"]))

    # Compute final exclusion reasons
    reasons_counter = Counter()
    for pid in exc_ids:
        r = ai_reason.get(pid, "EX-OTHER")
        if r in ("INCLUDE", "ERR-LLM"):
            reasons_counter["EX-REVERSED"] += 1
        else:
            reasons_counter[r] += 1

    # Sort by count descending
    ordered = reasons_counter.most_common()
    codes = [r for r, _ in ordered]
    counts = [c for _, c in ordered]

    labels_map = {
        "EX-NONFIN": "Not finance\napplication",
        "EX-NOMETHOD": "Survey/review,\nno original method",
        "EX-TOOSHORT": "Insufficient\nmethodological detail",
        "EX-PARADIGM": "Annealing only /\nquantum-inspired",
        "EX-REVERSED": "Excluded after\ndiscrepancy review",
        "EX-OTHER": "Other",
        "EX-NOTEN": "Non-English",
    }

    labels = [labels_map.get(r, r) for r in codes]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#d94801", "#fd8d3c", "#fdd0a2", "#fee6ce", "#fff5eb", "#f0f0f0", "#e0e0e0"]
    bars = ax.barh(range(len(counts)), counts, color=colors[:len(counts)], edgecolor="white")

    ax.set_yticks(range(len(counts)))
    ax.set_yticklabels(labels, fontsize=9)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                f"{count:,}", ha="left", va="center", fontsize=10)

    ax.set_xlabel("Number of Records Excluded")
    ax.set_title("Title/Abstract Screening Exclusion Reasons")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(FIGURES / "fig4_exclusion_reasons.png")
    fig.savefig(FIGURES / "fig4_exclusion_reasons.pdf")
    plt.close(fig)
    print("  fig4_exclusion_reasons")


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print("Generating figures in 06_figures/...")
    fig_prisma_flow()
    fig_year_distribution()
    fig_source_distribution()
    fig_exclusion_reasons()
    print(f"\nDone. {len(list(FIGURES.glob('*.png')))} PNG + {len(list(FIGURES.glob('*.pdf')))} PDF files generated.")


if __name__ == "__main__":
    main()
