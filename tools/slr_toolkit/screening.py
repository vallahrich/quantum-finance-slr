"""Generate screening Excel workbooks and compute inter-rater reliability."""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import config

log = logging.getLogger(__name__)

# ── Styles ────────────────────────────────────────────────────────────────

_HEADER_FONT = Font(name="Segoe UI", bold=True, size=11, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="0078D4", end_color="0078D4", fill_type="solid")
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
_CELL_FONT = Font(name="Segoe UI", size=10)
_CELL_ALIGN = Alignment(vertical="top", wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)

_FILL_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
_FILL_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
_FILL_YELLOW = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
_FILL_LIGHT_BLUE = PatternFill(start_color="DEEAF6", end_color="DEEAF6", fill_type="solid")

_INSTR_FONT = Font(name="Segoe UI", size=11)
_INSTR_BOLD = Font(name="Segoe UI", size=11, bold=True)
_INSTR_TITLE = Font(name="Segoe UI", size=14, bold=True, color="0078D4")


# ── Helpers ───────────────────────────────────────────────────────────────

def _load_unique_records() -> list[dict[str, str]]:
    """Load non-duplicate records from master_records.csv."""
    records = []
    with open(config.MASTER_RECORDS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("duplicate_of", "").strip():
                records.append(row)
    return records


def _add_instructions_sheet(wb: Workbook, sheet_type: str) -> None:
    """Add an Instructions sheet to the workbook."""
    ws = wb.create_sheet("Instructions", 0)
    ws.sheet_properties.tabColor = "0078D4"

    lines = [
        ("Title/Abstract Screening — Instructions", _INSTR_TITLE),
        ("", _INSTR_FONT),
        ("GOAL", _INSTR_BOLD),
        (
            "Decide whether each paper should be INCLUDED or EXCLUDED based on "
            "its title and abstract. This is Stage A (broad mapping) — when in "
            "doubt, INCLUDE.",
            _INSTR_FONT,
        ),
        ("", _INSTR_FONT),
        ("INCLUSION CRITERIA (all must hold):", _INSTR_BOLD),
        ("  1. Uses or proposes a gate-based quantum computing approach", _INSTR_FONT),
        ("  2. Addresses a financial application or use case", _INSTR_FONT),
        (
            "  3. Contains enough detail to extract: problem family, quantum method, "
            "evaluation type",
            _INSTR_FONT,
        ),
        ("", _INSTR_FONT),
        ("QUICK EXCLUSION RULES:", _INSTR_BOLD),
        ("  - Quantum annealing ONLY (no gate-based component) -> exclude", _INSTR_FONT),
        ("  - Quantum-inspired classical algorithms -> exclude", _INSTR_FONT),
        ("  - Not finance (chemistry, logistics, etc.) -> exclude", _INSTR_FONT),
        ("  - Pure hardware, no application -> exclude", _INSTR_FONT),
        ("  - Survey/review papers -> exclude (used for snowballing only)", _INSTR_FONT),
        ("  - Non-English -> exclude", _INSTR_FONT),
        ("", _INSTR_FONT),
        ("HOW TO SCREEN:", _INSTR_BOLD),
        ("  1. Go to the 'Screening' sheet", _INSTR_FONT),
        ("  2. Read the Title and Abstract for each row", _INSTR_FONT),
        (
            "  3. Click the Decision column and select: include / exclude / maybe",
            _INSTR_FONT,
        ),
        ("  4. Add notes if helpful (especially for 'maybe' decisions)", _INSTR_FONT),
        ("  5. The row will auto-colour: green=include, red=exclude, yellow=maybe", _INSTR_FONT),
        ("", _INSTR_FONT),
        ("WHEN IN DOUBT -> choose 'maybe' (will be discussed jointly)", _INSTR_BOLD),
        ("", _INSTR_FONT),
        ("PROGRESS:", _INSTR_BOLD),
        ("  Check the 'Progress' sheet to see how many you have left.", _INSTR_FONT),
    ]

    if sheet_type == "calibration":
        lines.insert(2, ("This is the CALIBRATION file — both reviewers screen the same 50 records.", _INSTR_BOLD))
        lines.insert(3, ("Fill YOUR column only (Reviewer A Decision or Reviewer B Decision).", _INSTR_FONT))
        lines.insert(4, ("", _INSTR_FONT))

    for i, (text, font) in enumerate(lines, start=1):
        cell = ws.cell(row=i, column=1, value=text)
        cell.font = font
    ws.column_dimensions["A"].width = 90


def _style_header(ws, col_count: int) -> None:
    """Apply header styling to row 1."""
    for col in range(1, col_count + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN
        cell.border = _THIN_BORDER


def _add_conditional_formatting(ws, decision_col_letter: str, max_row: int) -> None:
    """Add green/red/yellow conditional formatting on the decision column."""
    rng = f"{decision_col_letter}2:{decision_col_letter}{max_row}"
    ws.conditional_formatting.add(
        rng, CellIsRule(operator="equal", formula=['"include"'], fill=_FILL_GREEN)
    )
    ws.conditional_formatting.add(
        rng, CellIsRule(operator="equal", formula=['"exclude"'], fill=_FILL_RED)
    )
    ws.conditional_formatting.add(
        rng, CellIsRule(operator="equal", formula=['"maybe"'], fill=_FILL_YELLOW)
    )


def _add_row_formatting(ws, decision_col_idx: int, max_row: int, col_count: int) -> None:
    """Add row-level conditional formatting so entire rows colour."""
    decision_col = get_column_letter(decision_col_idx)
    for col in range(1, col_count + 1):
        col_letter = get_column_letter(col)
        rng = f"{col_letter}2:{col_letter}{max_row}"
        ws.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="equal",
                formula=[f'"include"'],
                fill=_FILL_GREEN,
            ),
        )
        # Only apply row colouring based on decision column
        # Use formula-based rule instead
    # Simpler: just colour the decision column
    _add_conditional_formatting(ws, decision_col, max_row)


def _add_progress_sheet(wb: Workbook, screening_sheet_name: str,
                        decision_col_letter: str, total: int) -> None:
    """Add a Progress tracking sheet with live formulas."""
    ws = wb.create_sheet("Progress")
    ws.sheet_properties.tabColor = "00B050"

    headers = ["Metric", "Count", "Percentage"]
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=i, value=h)
        cell.font = _HEADER_FONT
        cell.fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
        cell.alignment = _HEADER_ALIGN

    sn = screening_sheet_name
    col = decision_col_letter
    rng = f"'{sn}'.{col}2:{col}{total + 1}"

    metrics = [
        ("Total records", str(total), ""),
        ("Screened", f'=COUNTA({rng})', f'=B3/B2'),
        ("Remaining", f'=B2-B3', f'=B4/B2'),
        ("", "", ""),
        ("Include", f'=COUNTIF({rng},"include")', f'=IF(B3>0,B7/B3,"")'),
        ("Exclude", f'=COUNTIF({rng},"exclude")', f'=IF(B3>0,B8/B3,"")'),
        ("Maybe", f'=COUNTIF({rng},"maybe")', f'=IF(B3>0,B9/B3,"")'),
    ]

    for i, (label, formula, pct) in enumerate(metrics, 2):
        ws.cell(row=i, column=1, value=label).font = Font(name="Segoe UI", size=11, bold=bool(label))
        cell_b = ws.cell(row=i, column=2, value=formula if not formula.startswith("=") else None)
        if formula.startswith("="):
            cell_b.value = formula
        cell_b.font = Font(name="Segoe UI", size=14, bold=True)
        cell_b.alignment = Alignment(horizontal="center")

        cell_c = ws.cell(row=i, column=3, value=pct if not pct.startswith("=") else None)
        if pct.startswith("="):
            cell_c.value = pct
        cell_c.number_format = "0.0%"
        cell_c.font = Font(name="Segoe UI", size=11)
        cell_c.alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14


# ── Main generators ──────────────────────────────────────────────────────

def generate_calibration_workbook(
    records: list[dict[str, str]],
    sample_size: int = 50,
    seed: int = 42,
    output_path: Path | None = None,
) -> Path:
    """Generate the calibration screening Excel (both reviewers)."""
    if output_path is None:
        output_path = config.SCREENING_DIR / "calibration_screening.xlsx"

    random.seed(seed)
    sample = random.sample(records, min(sample_size, len(records)))

    wb = Workbook()
    _add_instructions_sheet(wb, "calibration")

    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    ws = wb.create_sheet("Screening")
    ws.sheet_properties.tabColor = "FFC000"

    headers = [
        "#", "Paper ID", "Title", "Authors", "Year", "DOI",
        "Abstract", "Source", "Reviewer A Decision",
        "Reviewer B Decision", "Final Decision", "Notes",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(row=1, column=i, value=h)
    _style_header(ws, len(headers))

    # Data validation for decision columns
    dv = DataValidation(
        type="list", formula1='"include,exclude,maybe"', allow_blank=True
    )
    dv.error = "Please select: include, exclude, or maybe"
    dv.errorTitle = "Invalid decision"
    dv.prompt = "Select your screening decision"
    dv.promptTitle = "Decision"
    ws.add_data_validation(dv)

    for row_idx, rec in enumerate(sample, start=2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1)
        ws.cell(row=row_idx, column=2, value=rec.get("paper_id", ""))
        ws.cell(row=row_idx, column=3, value=rec.get("title", ""))
        ws.cell(row=row_idx, column=4, value=rec.get("authors", ""))
        ws.cell(row=row_idx, column=5, value=rec.get("year", ""))
        ws.cell(row=row_idx, column=6, value=rec.get("doi", ""))
        ws.cell(row=row_idx, column=7, value=rec.get("abstract", ""))
        ws.cell(row=row_idx, column=8, value=rec.get("source_db", ""))

        for col in (9, 10, 11):
            dv.add(ws.cell(row=row_idx, column=col))

        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.font = _CELL_FONT
            cell.alignment = _CELL_ALIGN
            cell.border = _THIN_BORDER

    max_row = len(sample) + 1

    # Conditional formatting on all three decision columns
    for col_letter in ("I", "J", "K"):
        _add_conditional_formatting(ws, col_letter, max_row)

    # Column widths
    widths = {"A": 5, "B": 14, "C": 50, "D": 30, "E": 7, "F": 22,
              "G": 70, "H": 12, "I": 18, "J": 18, "K": 16, "L": 30}
    for col_letter, w in widths.items():
        ws.column_dimensions[col_letter].width = w

    # Freeze panes
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:L{max_row}"

    # Progress sheet
    _add_progress_sheet(wb, "Screening", "I", len(sample))

    wb.save(output_path)
    log.info("Calibration workbook: %s (%d records)", output_path, len(sample))
    return output_path


def generate_split_workbooks(
    records: list[dict[str, str]],
    calibration_ids: set[str],
    seed: int = 42,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Generate Reviewer A and B screening Excels (split)."""
    if output_dir is None:
        output_dir = config.SCREENING_DIR

    # Exclude calibration records
    remaining = [r for r in records if r.get("paper_id", "") not in calibration_ids]

    # Shuffle deterministically then split
    random.seed(seed)
    random.shuffle(remaining)
    mid = len(remaining) // 2
    split_a = remaining[:mid]
    split_b = remaining[mid:]

    path_a = output_dir / "screening_reviewer_A.xlsx"
    path_b = output_dir / "screening_reviewer_B.xlsx"

    for label, subset, path in [("A", split_a, path_a), ("B", split_b, path_b)]:
        wb = Workbook()
        _add_instructions_sheet(wb, "split")
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        ws = wb.create_sheet("Screening")
        ws.sheet_properties.tabColor = "FFC000"

        headers = [
            "#", "Paper ID", "Title", "Authors", "Year", "DOI",
            "Abstract", "Source", "Decision", "Notes",
        ]
        for i, h in enumerate(headers, 1):
            ws.cell(row=1, column=i, value=h)
        _style_header(ws, len(headers))

        dv = DataValidation(
            type="list", formula1='"include,exclude,maybe"', allow_blank=True
        )
        dv.error = "Please select: include, exclude, or maybe"
        dv.errorTitle = "Invalid decision"
        dv.prompt = "Select your screening decision"
        dv.promptTitle = "Decision"
        ws.add_data_validation(dv)

        for row_idx, rec in enumerate(subset, start=2):
            ws.cell(row=row_idx, column=1, value=row_idx - 1)
            ws.cell(row=row_idx, column=2, value=rec.get("paper_id", ""))
            ws.cell(row=row_idx, column=3, value=rec.get("title", ""))
            ws.cell(row=row_idx, column=4, value=rec.get("authors", ""))
            ws.cell(row=row_idx, column=5, value=rec.get("year", ""))
            ws.cell(row=row_idx, column=6, value=rec.get("doi", ""))
            ws.cell(row=row_idx, column=7, value=rec.get("abstract", ""))
            ws.cell(row=row_idx, column=8, value=rec.get("source_db", ""))
            dv.add(ws.cell(row=row_idx, column=9))

            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=col)
                cell.font = _CELL_FONT
                cell.alignment = _CELL_ALIGN
                cell.border = _THIN_BORDER

        max_row = len(subset) + 1
        _add_conditional_formatting(ws, "I", max_row)

        widths = {"A": 5, "B": 14, "C": 50, "D": 30, "E": 7, "F": 22,
                  "G": 70, "H": 12, "I": 14, "J": 30}
        for col_letter, w in widths.items():
            ws.column_dimensions[col_letter].width = w

        ws.freeze_panes = "C2"
        ws.auto_filter.ref = f"A1:J{max_row}"

        _add_progress_sheet(wb, "Screening", "I", len(subset))
        wb.save(path)
        log.info("Reviewer %s workbook: %s (%d records)", label, path, len(subset))

    return path_a, path_b


def generate_screening_excels(seed: int = 42) -> dict[str, Path]:
    """Generate all screening workbooks (calibration + split)."""
    records = _load_unique_records()
    log.info("Loaded %d unique records for screening", len(records))

    cal_path = generate_calibration_workbook(records, seed=seed)

    # Get calibration paper IDs
    cal_wb = load_workbook(cal_path, read_only=True)
    cal_ws = cal_wb["Screening"]
    cal_ids: set[str] = set()
    for row in cal_ws.iter_rows(min_row=2, max_col=2, values_only=True):
        if row[1]:
            cal_ids.add(str(row[1]))
    cal_wb.close()

    path_a, path_b = generate_split_workbooks(records, cal_ids, seed=seed)

    return {
        "calibration": cal_path,
        "reviewer_a": path_a,
        "reviewer_b": path_b,
    }


# ── Kappa computation ────────────────────────────────────────────────────

def compute_kappa(calibration_path: Path | None = None) -> dict:
    """Compute Cohen's kappa from the calibration workbook.

    Returns dict with: n, agreement, kappa, details.
    """
    if calibration_path is None:
        calibration_path = config.SCREENING_DIR / "calibration_screening.xlsx"

    wb = load_workbook(calibration_path, read_only=True)
    ws = wb["Screening"]

    pairs: list[tuple[str, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[2] is None:  # no title = empty row
            continue
        a = str(row[8] or "").strip().lower()
        b = str(row[9] or "").strip().lower()
        if a and b:
            pairs.append((a, b))
    wb.close()

    if not pairs:
        return {"n": 0, "agreement": 0, "kappa": 0, "error": "No paired decisions found"}

    # Cohen's kappa
    n = len(pairs)
    categories = sorted(set(a for a, _ in pairs) | set(b for _, b in pairs))
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n  # observed agreement

    # Expected agreement
    pe = 0.0
    for cat in categories:
        pa = sum(1 for a, _ in pairs if a == cat) / n
        pb = sum(1 for _, b in pairs if b == cat) / n
        pe += pa * pb

    kappa = (po - pe) / (1 - pe) if pe < 1.0 else 1.0

    # Confusion details
    confusion: dict[tuple[str, str], int] = {}
    for a, b in pairs:
        key = (a, b)
        confusion[key] = confusion.get(key, 0) + 1

    disagreements = [(a, b) for a, b in pairs if a != b]

    return {
        "n": n,
        "agreement": po,
        "kappa": round(kappa, 3),
        "screened_total": n,
        "agreed": agree,
        "disagreed": len(disagreements),
        "confusion": confusion,
        "pass": kappa >= 0.70,
    }


# ── Merge results ────────────────────────────────────────────────────────

def merge_screening_results(
    calibration_path: Path | None = None,
    reviewer_a_path: Path | None = None,
    reviewer_b_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Merge calibration + split screening results into one decisions CSV."""
    if calibration_path is None:
        calibration_path = config.SCREENING_DIR / "calibration_screening.xlsx"
    if reviewer_a_path is None:
        reviewer_a_path = config.SCREENING_DIR / "screening_reviewer_A.xlsx"
    if reviewer_b_path is None:
        reviewer_b_path = config.SCREENING_DIR / "screening_reviewer_B.xlsx"
    if output_path is None:
        output_path = config.TA_DECISIONS_FILE

    rows: list[dict[str, str]] = []

    # Calibration: use final_decision column
    wb = load_workbook(calibration_path, read_only=True)
    ws = wb["Screening"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[2] is None:
            continue
        decision = str(row[10] or row[8] or "").strip().lower()  # final > reviewer_a
        rows.append({
            "paper_id": str(row[1] or ""),
            "title": str(row[2] or ""),
            "decision": decision,
            "reviewer": "calibration",
            "notes": str(row[11] or ""),
        })
    wb.close()

    # Reviewer A and B
    for label, path in [("A", reviewer_a_path), ("B", reviewer_b_path)]:
        if not path.exists():
            log.warning("Reviewer %s file not found: %s", label, path)
            continue
        wb = load_workbook(path, read_only=True)
        ws = wb["Screening"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[2] is None:
                continue
            decision = str(row[8] or "").strip().lower()
            rows.append({
                "paper_id": str(row[1] or ""),
                "title": str(row[2] or ""),
                "decision": decision,
                "reviewer": f"reviewer_{label}",
                "notes": str(row[9] or ""),
            })
        wb.close()

    fieldnames = ["paper_id", "title", "decision", "reviewer", "notes"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Merged %d decisions -> %s", len(rows), output_path)
    return output_path
