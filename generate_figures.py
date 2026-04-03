"""Generate all SLR figures for 07_figures/."""

from __future__ import annotations

import ast
import textwrap
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

REPO = Path(__file__).resolve().parent
FIGURES = REPO / "07_figures"
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


def _load_topic_coding() -> pd.DataFrame:
    return pd.read_csv(REPO / "06_extraction" / "topic_coding.csv").fillna("")


# ── Figure 1: PRISMA flow diagram ─────────────────────────────────────────
def fig_prisma_flow():
    """Generate a PRISMA 2020 flow diagram."""
    master = _load_master()
    master_full = pd.read_csv(REPO / "04_deduped_library" / "master_records.csv", dtype=str).fillna("")
    ai = _load_ai_screening()

    n_identified = len(master_full)
    n_duplicates = (master_full["duplicate_of"] != "").sum()
    n_screened = len(ai)
    n_included_ta = (ai["ai_decision"] == "include").sum()
    n_excluded_ta = (ai["ai_decision"] == "exclude").sum()

    # Full-text from included_for_coding
    inc_path = REPO / "05_screening" / "included_for_coding.csv"
    if inc_path.exists():
        inc = pd.read_csv(inc_path, dtype=str)
        n_included_ft = len(inc)
    else:
        n_included_ft = n_included_ta

    # Topic coding completed
    tc = _load_topic_coding()
    n_coded = len(tc)

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
    ax.text(5, 5.5, f"Full-text articles assessed\nfor eligibility\n(n = {n_included_ft:,})",
            ha="center", va="center", fontsize=10, bbox=box_style)

    ax.annotate("", xy=(5, 4.7), xytext=(5, 5.0), arrowprops=dict(arrowstyle="->", lw=1.5))

    # Included
    ax.text(5, 3.8, "Included", fontsize=14, fontweight="bold", ha="center")
    ax.text(5, 3.1, f"Studies included in\nquantitative synthesis\n(n = {n_coded:,})",
            ha="center", va="center", fontsize=10, bbox=final_style)

    # Dual pathway note
    ax.text(5, 2.2,
            f"Tier 1 (evidence mapping): all {n_coded} papers\n"
            "Tier 2 (advantage assessment): quantitative subset",
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
    """Horizontal bar chart of AI screening exclusion reason codes."""
    ai = _load_ai_screening()
    excluded = ai[ai["ai_decision"] == "exclude"]
    reasons = excluded["reason_code"].value_counts()

    labels_map = {
        "EX-NONFIN": "Not finance\napplication",
        "EX-NOMETHOD": "Survey/review,\nno original method",
        "EX-TOOSHORT": "Insufficient\nmethodological detail",
        "EX-PARADIGM": "Annealing only /\nquantum-inspired",
        "EX-OTHER": "Other",
        "EX-NOTEN": "Non-English",
    }

    labels = [labels_map.get(r, r) for r in reasons.index]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#d94801", "#fd8d3c", "#fdd0a2", "#fee6ce", "#fff5eb", "#f0f0f0"]
    bars = ax.barh(range(len(reasons)), reasons.values, color=colors[:len(reasons)], edgecolor="white")

    ax.set_yticks(range(len(reasons)))
    ax.set_yticklabels(labels, fontsize=9)

    for bar, count in zip(bars, reasons.values):
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


# ── Figure 5: Topic distribution ──────────────────────────────────────────
def fig_topic_distribution():
    """Horizontal bar chart of primary topic assignments."""
    tc = _load_topic_coding()
    topics_all = []
    for _, row in tc.iterrows():
        try:
            pts = ast.literal_eval(row["primary_topics"])
            topics_all.extend(pts)
        except (ValueError, SyntaxError):
            pass

    topic_counts = Counter(topics_all)
    # Sort by count
    labels_raw = [t for t, _ in topic_counts.most_common()]
    counts = [c for _, c in topic_counts.most_common()]

    # Prettify labels
    def pretty(s: str) -> str:
        return s.replace("_", " ").replace("and ", "& ").title()

    labels = [pretty(l) for l in labels_raw]

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = PALETTE[:len(labels)]
    bars = ax.barh(range(len(labels)), counts, color=colors, edgecolor="white")

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                str(count), ha="left", va="center", fontsize=10)

    ax.set_xlabel("Number of Papers")
    ax.set_title("Primary Application Topics (n = 585 coded papers)")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(FIGURES / "fig5_topic_distribution.png")
    fig.savefig(FIGURES / "fig5_topic_distribution.pdf")
    plt.close(fig)
    print("  fig5_topic_distribution")


# ── Figure 6: Method family distribution ──────────────────────────────────
def fig_method_families():
    """Horizontal bar chart of quantum method families."""
    tc = _load_topic_coding()
    methods = tc["method_family"].dropna().value_counts()

    def pretty(s: str) -> str:
        mapping = {
            "quantum_ml": "Quantum ML",
            "variational_or_vqe": "Variational / VQE",
            "amplitude_estimation": "Amplitude Estimation",
            "qaoa_or_optimization": "QAOA / Optimization",
            "other_gate_based": "Other Gate-Based",
            "hybrid_unspecified": "Hybrid (Unspecified)",
            "quantum_walk_or_search": "Quantum Walk / Search",
            "linear_systems_or_hhl": "Linear Systems / HHL",
        }
        return mapping.get(s, s.replace("_", " ").title())

    labels = [pretty(m) for m in methods.index]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#238b45", "#74c476", "#bae4b3", "#d5efcf",
              "#756bb1", "#bcbddc", "#dadaeb", "#ededed"]
    bars = ax.barh(range(len(labels)), methods.values, color=colors[:len(labels)], edgecolor="white")

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)

    for bar, count in zip(bars, methods.values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                str(count), ha="left", va="center", fontsize=10)

    ax.set_xlabel("Number of Papers")
    ax.set_title("Quantum Method Families (n = 585 coded papers)")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(FIGURES / "fig6_method_families.png")
    fig.savefig(FIGURES / "fig6_method_families.pdf")
    plt.close(fig)
    print("  fig6_method_families")


# ── Figure 7: Evaluation type distribution ────────────────────────────────
def fig_evaluation_types():
    """Pie chart of evaluation types."""
    tc = _load_topic_coding()
    evals = tc["evaluation_type"].dropna().value_counts()

    def pretty(s: str) -> str:
        mapping = {
            "simulator": "Simulator",
            "real_hardware": "Real Hardware",
            "benchmark_comparison": "Benchmark Comparison",
            "analytical": "Analytical",
            "conceptual_only": "Conceptual Only",
        }
        return mapping.get(s, s.replace("_", " ").title())

    labels = [pretty(e) for e in evals.index]
    colors = ["#2171b5", "#238b45", "#d94801", "#756bb1", "#969696"]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        evals.values, labels=labels, autopct="%1.1f%%",
        colors=colors[:len(labels)], startangle=90,
        pctdistance=0.75, textprops={"fontsize": 10}
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_color("white")
        t.set_fontweight("bold")

    ax.set_title("Evaluation Approach Distribution (n = 585)")

    fig.savefig(FIGURES / "fig7_evaluation_types.png")
    fig.savefig(FIGURES / "fig7_evaluation_types.pdf")
    plt.close(fig)
    print("  fig7_evaluation_types")


# ── Figure 8: Year × topic heatmap ────────────────────────────────────────
def fig_year_topic_heatmap():
    """Heatmap of topics over time for included papers."""
    tc = _load_topic_coding()
    master = pd.read_csv(REPO / "04_deduped_library" / "master_records.csv", dtype=str).fillna("")
    merged = tc.merge(master[["paper_id", "year"]], on="paper_id", how="left")
    merged["year_int"] = pd.to_numeric(merged["year"], errors="coerce")
    merged = merged.dropna(subset=["year_int"])
    merged["year_int"] = merged["year_int"].astype(int)
    merged = merged[merged["year_int"] >= 2016]

    # Build topic × year matrix
    rows = []
    for _, row in merged.iterrows():
        try:
            pts = ast.literal_eval(row["primary_topics"])
        except (ValueError, SyntaxError):
            continue
        for t in pts:
            rows.append({"topic": t, "year": row["year_int"]})

    if not rows:
        return
    cross = pd.DataFrame(rows)
    pivot = cross.pivot_table(index="topic", columns="year", aggfunc="size", fill_value=0)

    def pretty(s: str) -> str:
        return s.replace("_", " ").replace("and ", "& ").title()

    # Sort by total
    pivot["_total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("_total", ascending=True).drop(columns="_total")
    pivot.index = [pretty(t) for t in pivot.index]

    fig, ax = plt.subplots(figsize=(12, 7))
    im = ax.imshow(pivot.values, aspect="auto", cmap="Blues")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if val > 0:
                color = "white" if val > pivot.values.max() * 0.6 else "black"
                ax.text(j, i, str(int(val)), ha="center", va="center", fontsize=8, color=color)

    ax.set_title("Application Topics by Publication Year (2016–2026)")
    ax.set_xlabel("Year")
    fig.colorbar(im, ax=ax, label="Paper Count", shrink=0.7)

    fig.savefig(FIGURES / "fig8_year_topic_heatmap.png")
    fig.savefig(FIGURES / "fig8_year_topic_heatmap.pdf")
    plt.close(fig)
    print("  fig8_year_topic_heatmap")


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print("Generating figures in 07_figures/...")
    fig_prisma_flow()
    fig_year_distribution()
    fig_source_distribution()
    fig_exclusion_reasons()
    fig_topic_distribution()
    fig_method_families()
    fig_evaluation_types()
    fig_year_topic_heatmap()
    print(f"\nDone. {len(list(FIGURES.glob('*.png')))} PNG + {len(list(FIGURES.glob('*.pdf')))} PDF files generated.")


if __name__ == "__main__":
    main()
