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
    """Generate a PRISMA 2020 flow diagram (thesis-quality)."""
    master_full = pd.read_csv(REPO / "04_deduped_library" / "master_records.csv", dtype=str).fillna("")

    n_identified = len(master_full)
    n_duplicates = int((master_full["duplicate_of"] != "").sum())
    n_screened = n_identified - n_duplicates

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

    # Source breakdown
    sources = master_full["source_db"].value_counts()

    # ── Layout constants ──────────────────────────────────────────────────
    fig_w, fig_h = 11, 11.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    # Coordinates
    cx = 4.2            # centre of main flow boxes
    rx = 8.5            # centre of right-side exclusion boxes
    bw_main = 3.2       # main box width
    bw_excl = 3.0       # exclusion box width
    bh = 0.85           # box height
    sidebar_w = 1.3     # phase sidebar width

    # Phase y-bands (top of band, bottom of band)
    y_id_top, y_id_bot = 11.0, 8.3
    y_sc_top, y_sc_bot = 8.3, 5.8
    y_el_top, y_el_bot = 5.8, 3.4
    y_in_top, y_in_bot = 3.4, 0.8

    # Box y-centres
    y_ident = 10.2
    y_src = 9.35
    y_dup = 9.35
    y_screen = 7.2
    y_excl_ta = 7.2
    y_assess = 4.8
    y_excl_ft = 4.8
    y_incl = 2.2

    # ── Colours (PRISMA 2020 standard: muted, professional) ───────────────
    c_sidebar = "#e8e8e8"
    c_sidebar_text = "#444444"
    c_box_fill = "#ffffff"
    c_box_edge = "#333333"
    c_excl_fill = "#fafafa"
    c_excl_edge = "#888888"
    c_incl_fill = "#f0f7f0"
    c_incl_edge = "#333333"
    c_arrow = "#333333"
    lw_box = 1.2
    lw_arrow = 1.0
    fs_box = 9.5
    fs_phase = 11

    # ── Helper: draw a box with centred text ──────────────────────────────
    def _box(x, y, w, h, text, fill, edge, lw=lw_box, fontsize=fs_box,
             fontweight="normal"):
        rect = mpatches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.08",
            facecolor=fill, edgecolor=edge, linewidth=lw,
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                fontweight=fontweight, linespacing=1.35)

    def _arrow_down(x, y_from, y_to):
        ax.annotate("", xy=(x, y_to), xytext=(x, y_from),
                    arrowprops=dict(arrowstyle="-|>", color=c_arrow,
                                    lw=lw_arrow, mutation_scale=12))

    def _arrow_right(x_from, x_to, y):
        ax.annotate("", xy=(x_to, y), xytext=(x_from, y),
                    arrowprops=dict(arrowstyle="-|>", color=c_arrow,
                                    lw=lw_arrow, mutation_scale=12))

    # ── Phase sidebar bands ───────────────────────────────────────────────
    for top, bot, label in [
        (y_id_top, y_id_bot, "Identification"),
        (y_sc_top, y_sc_bot, "Screening"),
        (y_el_top, y_el_bot, "Eligibility"),
        (y_in_top, y_in_bot, "Included"),
    ]:
        rect = mpatches.FancyBboxPatch(
            (0.15, bot), sidebar_w, top - bot,
            boxstyle="round,pad=0.06",
            facecolor=c_sidebar, edgecolor="#cccccc", linewidth=0.8,
        )
        ax.add_patch(rect)
        ax.text(0.15 + sidebar_w / 2, (top + bot) / 2, label,
                ha="center", va="center", fontsize=fs_phase,
                fontweight="bold", color=c_sidebar_text, rotation=90)

    # ── Identification ────────────────────────────────────────────────────
    # Source breakdown embedded in the box
    src_parts = [f"{s.replace('_', ' ').title()}: {c:,}" for s, c in sources.items()]
    src_line = "\n".join(src_parts)

    id_box_h = 1.8
    _box(cx, y_ident, bw_main, id_box_h,
         f"Records identified through\ndatabase searching\n(n = {n_identified:,})",
         c_box_fill, c_box_edge)
    ax.text(cx, y_ident - 0.55, src_line,
            ha="center", va="center", fontsize=5.5, color="#666666",
            linespacing=1.3)

    # Duplicates removed (right side) — positioned between ident and screening
    y_junct = y_ident - id_box_h / 2 - 0.45  # junction point on the vertical line
    _box(rx, y_junct, bw_excl, 0.65,
         f"Duplicates removed\n(n = {n_duplicates:,})",
         c_excl_fill, c_excl_edge)

    # Vertical arrow: ident box → junction → screening box
    # Segment 1: ident bottom to junction
    ax.plot([cx, cx], [y_ident - id_box_h / 2, y_junct], color=c_arrow, lw=lw_arrow,
            solid_capstyle="butt")
    # Horizontal arrow: junction → duplicates box
    _arrow_right(cx, rx - bw_excl / 2, y_junct)
    # Segment 2: junction to screening box (with arrowhead)
    _arrow_down(cx, y_junct, y_screen + bh / 2)

    # ── Screening ─────────────────────────────────────────────────────────
    _box(cx, y_screen, bw_main, bh,
         f"Records screened\n(title/abstract)\n(n = {n_screened:,})",
         c_box_fill, c_box_edge)

    # Records excluded at T/A (right side)
    _box(rx, y_excl_ta, bw_excl, 0.65,
         f"Records excluded\n(n = {n_excluded_ta:,})",
         c_excl_fill, c_excl_edge)

    # Arrow down to eligibility
    _arrow_down(cx, y_screen - bh / 2, y_assess + bh / 2)
    # Arrow right to exclusion
    _arrow_right(cx + bw_main / 2, rx - bw_excl / 2, y_excl_ta)

    # ── Eligibility ───────────────────────────────────────────────────────
    _box(cx, y_assess, bw_main, bh,
         f"Full-text articles assessed\nfor eligibility\n(n = {n_assessed_ft:,})",
         c_box_fill, c_box_edge)

    # Full-text exclusion (right side) — count from actual PDFs on disk
    pdf_dir = REPO / "07_full_texts" / "pdfs"
    n_pdfs_on_disk = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0
    n_zenodo = 9  # Zenodo code/data records (not scientific papers)
    n_not_retrieved = n_included_ft - n_pdfs_on_disk - n_zenodo
    n_ft_excluded_total = n_excluded_ft + n_zenodo + max(n_not_retrieved, 0)
    n_final_included = n_assessed_ft - n_ft_excluded_total

    if n_ft_excluded_total > 0:
        n_no_paper = n_excluded_ft + max(n_not_retrieved, 0)
        excl_text = f"Full-text articles excluded\n(n = {n_ft_excluded_total})"
        excl_text += f"\nNo paper found / no access: {n_no_paper}"
        excl_text += f"\nNot a paper (Zenodo records): {n_zenodo}"
        _box(rx, y_excl_ft, bw_excl, 1.25,
             excl_text,
             c_excl_fill, c_excl_edge, fontsize=8.5)
        _arrow_right(cx + bw_main / 2, rx - bw_excl / 2, y_excl_ft)

    # Arrow down to included
    _arrow_down(cx, y_assess - bh / 2, y_incl + bh / 2)

    # ── Included ──────────────────────────────────────────────────────────
    _box(cx, y_incl, bw_main, bh,
         f"Studies included in\nsystematic review\n(n = {n_final_included:,})",
         c_incl_fill, c_incl_edge, fontweight="bold")

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
