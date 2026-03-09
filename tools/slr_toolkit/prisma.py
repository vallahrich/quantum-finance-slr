"""PRISMA flow-diagram counts from screening decision files."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from . import config
from .utils import ensure_dir

log = logging.getLogger("slr_toolkit.prisma")

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

_MISSING = "MISSING_INPUT"


def _read_csv_safe(path: Path) -> pd.DataFrame | None:
    """Return DataFrame or None if file missing."""
    if not path.exists():
        log.warning("File not found: %s", path)
        return None
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        log.error("Error reading %s: %s", path, exc)
        return None


def generate_prisma_counts() -> dict[str, str | int]:
    """Compute PRISMA counts and write to prisma_counts.xlsx.

    Returns the counts dict.
    """
    counts: dict[str, str | int] = {}

    # --- Identification / deduplication -------------------------------------
    master_path = config.MASTER_RECORDS_CSV
    if master_path.exists():
        master = pd.read_csv(master_path, dtype=str).fillna("")
        total_identified = len(master)
        duplicates_removed = (master["duplicate_of"] != "").sum()
        after_dedup = total_identified - duplicates_removed
    else:
        log.warning("master_records.csv not found — run build-master first.")
        total_identified = _MISSING
        duplicates_removed = _MISSING
        after_dedup = _MISSING

    counts["Identified"] = total_identified
    counts["DuplicatesRemoved"] = duplicates_removed

    # --- Title / abstract screening -----------------------------------------
    ta_df = _read_csv_safe(config.TA_DECISIONS_FILE)
    if ta_df is not None and "final_decision" in ta_df.columns:
        screened_ta = len(ta_df)
        excluded_ta = (ta_df["final_decision"].str.strip().str.lower() == "exclude").sum()
    else:
        screened_ta = after_dedup if isinstance(after_dedup, int) else _MISSING
        excluded_ta = _MISSING

    counts["ScreenedTitleAbstract"] = screened_ta
    counts["ExcludedTitleAbstract"] = excluded_ta

    # --- Full-text screening ------------------------------------------------
    ft_df = _read_csv_safe(config.FT_DECISIONS_FILE)
    if ft_df is not None and "final_decision" in ft_df.columns:
        assessed_ft = len(ft_df)
        excluded_ft = (ft_df["final_decision"].str.strip().str.lower() == "exclude").sum()
        included_total = (ft_df["final_decision"].str.strip().str.lower() == "include").sum()

        # Stage A / B split — look for a 'stage' column or derive from
        # decision_A / decision_B
        if "stage" in ft_df.columns:
            included_a = (
                (ft_df["final_decision"].str.lower() == "include")
                & (ft_df["stage"].str.upper() == "A")
            ).sum()
            included_b = (
                (ft_df["final_decision"].str.lower() == "include")
                & (ft_df["stage"].str.upper() == "B")
            ).sum()
        else:
            # Default: all included count as Stage A; Stage B = subset
            included_a = included_total
            included_b = "N/A (add 'stage' column to full_text_decisions.csv)"
    else:
        assessed_ft = _MISSING
        excluded_ft = _MISSING
        included_a = _MISSING
        included_b = _MISSING

    counts["FullTextAssessed"] = assessed_ft
    counts["ExcludedFullText"] = excluded_ft
    counts["IncludedStageA"] = included_a
    counts["IncludedStageB"] = included_b

    # --- Full-text exclusion reason breakdown (PRISMA 2020 §13b) ------------
    reason_counts: dict[str, int] = {}
    if ft_df is not None and "exclusion_reason" in ft_df.columns:
        excluded_rows = ft_df[ft_df["final_decision"].str.strip().str.lower() == "exclude"]
        missing_reason = (excluded_rows["exclusion_reason"].str.strip() == "").sum()
        if missing_reason > 0:
            log.warning(
                "%d excluded full-text records have NO exclusion_reason — "
                "please fill in using codes from 05_screening/exclusion_reason_codes.md",
                missing_reason,
            )
        for reason, grp in excluded_rows.groupby(
            excluded_rows["exclusion_reason"].str.strip().str.upper()
        ):
            if reason:
                reason_counts[reason] = len(grp)
        if missing_reason > 0:
            reason_counts["(MISSING REASON)"] = int(missing_reason)

    # --- Write XLSX ---------------------------------------------------------
    _write_prisma_xlsx(counts, reason_counts)

    # Print summary
    print("\nPRISMA Counts:")
    for k, v in counts.items():
        print(f"  {k:30s} : {v}")
    if reason_counts:
        print("\nFull-Text Exclusion Reasons:")
        for reason, n in sorted(reason_counts.items()):
            print(f"  {reason:30s} : {n}")
    print()

    return counts


def _write_prisma_xlsx(
    counts: dict[str, str | int],
    reason_counts: dict[str, int] | None = None,
) -> None:
    """Write counts to a neatly formatted Excel file."""
    path = config.PRISMA_COUNTS_XLSX
    ensure_dir(path.parent)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "PRISMA Counts"

    ws.append(["Metric", "Count"])
    for col in range(1, 3):
        cell = ws.cell(row=1, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    for metric, value in counts.items():
        ws.append([metric, value if not isinstance(value, str) else str(value)])

    # Exclusion reason breakdown sheet
    if reason_counts:
        ws_reasons = wb.create_sheet("Exclusion Reasons")
        ws_reasons.append(["Exclusion Reason Code", "Count"])
        for col in range(1, 3):
            cell = ws_reasons.cell(row=1, column=col)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws_reasons.freeze_panes = "A2"
        for reason, n in sorted(reason_counts.items()):
            ws_reasons.append([reason, n])
        ws_reasons.column_dimensions["A"].width = 35
        ws_reasons.column_dimensions["B"].width = 12

    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 18

    wb.save(path)
    log.info("Wrote PRISMA counts → %s", path)
