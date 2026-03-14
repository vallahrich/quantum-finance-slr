"""Tests for LLM-based screening module (Protocol Amendment A9)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.slr_toolkit import config


# ── Fixtures ──────────────────────────────────────────────────────────────

SAMPLE_RECORDS = [
    {"paper_id": f"p{i:03d}", "title": f"Paper {i}", "authors": f"Author {i}",
     "year": "2023", "abstract": f"Abstract for paper {i}", "source_db": "test"}
    for i in range(5)
]


def _make_master_csv(path: Path, records: list[dict]) -> Path:
    cols = config.NORMALIZED_COLUMNS + ["duplicate_of"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for rec in records:
            row = {c: rec.get(c, "") for c in cols}
            writer.writerow(row)
    return path


# ── Tests: _build_url ─────────────────────────────────────────────────────


class TestBuildUrl:
    def test_standard_azure_endpoint(self):
        from tools.slr_toolkit.llm_screening import _build_url

        url = _build_url("https://myresource.openai.azure.com", "gpt-4o")
        assert "deployments/gpt-4o" in url
        assert "api-version=" in url

    def test_v1_compatible_endpoint(self):
        from tools.slr_toolkit.llm_screening import _build_url

        url = _build_url(
            "https://myresource.openai.azure.com/openai/v1/", "gpt-4o",
        )
        assert url.endswith("/chat/completions")
        assert "deployments" not in url

    def test_trailing_slash_stripped(self):
        from tools.slr_toolkit.llm_screening import _build_url

        url = _build_url("https://myresource.openai.azure.com/", "gpt-4o")
        assert "deployments/gpt-4o" in url


# ── Tests: _parse_llm_response ───────────────────────────────────────────


class TestParseLLMResponse:
    def test_valid_json(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        raw = {
            "choices": [{"message": {"content": json.dumps({
                "decision": "include",
                "confidence": 0.85,
                "reason_code": "INCLUDE",
                "reasoning": "Gate-based quantum for portfolio optimization.",
            })}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        result = _parse_llm_response(raw)
        assert result["decision"] == "include"
        assert result["confidence"] == 0.85
        assert result["reason_code"] == "INCLUDE"

    def test_borderline_mapped_to_include(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        raw = {
            "choices": [{"message": {"content": json.dumps({
                "decision": "borderline",
                "confidence": 0.5,
                "reason_code": "INCLUDE",
                "reasoning": "Unclear scope.",
            })}}],
            "usage": {},
        }
        result = _parse_llm_response(raw)
        assert result["decision"] == "include"
        assert "(borderline→include)" in result["reasoning"]

    def test_json_in_markdown_fence(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        raw = {
            "choices": [{"message": {"content":
                '```json\n{"decision": "exclude", "confidence": 0.9, '
                '"reason_code": "EX-PARADIGM", "reasoning": "Annealing only."}\n```'
            }}],
            "usage": {},
        }
        result = _parse_llm_response(raw)
        assert result["decision"] == "exclude"
        assert result["reason_code"] == "EX-PARADIGM"

    def test_missing_decision_raises(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        raw = {
            "choices": [{"message": {"content": '{"confidence": 0.5}'}}],
            "usage": {},
        }
        with pytest.raises(ValueError, match="Missing 'decision'"):
            _parse_llm_response(raw)

    def test_no_choices_raises(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        with pytest.raises(ValueError, match="No choices"):
            _parse_llm_response({"choices": [], "usage": {}})

    def test_confidence_clamped(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        raw = {
            "choices": [{"message": {"content": json.dumps({
                "decision": "include", "confidence": 1.5,
            })}}],
            "usage": {},
        }
        result = _parse_llm_response(raw)
        assert result["confidence"] == 1.0

    def test_defaults_for_missing_fields(self):
        from tools.slr_toolkit.llm_screening import _parse_llm_response

        raw = {
            "choices": [{"message": {"content": json.dumps({
                "decision": "exclude",
            })}}],
            "usage": {},
        }
        result = _parse_llm_response(raw)
        assert result["reason_code"] == "EX-OTHER"
        assert result["confidence"] == 0.5


# ── Tests: estimate_cost ─────────────────────────────────────────────────


class TestEstimateCost:
    def test_returns_cost_breakdown(self):
        from tools.slr_toolkit.llm_screening import estimate_cost

        records = [
            {"paper_id": "p001", "title": "Quantum finance", "abstract": "Text"},
            {"paper_id": "p002", "title": "Another paper", "abstract": "More text"},
        ]
        result = estimate_cost(records)
        assert result["n_records"] == 2
        assert result["est_total_tokens"] > 0
        assert result["est_total_cost_usd"] > 0

    def test_empty_records(self):
        from tools.slr_toolkit.llm_screening import estimate_cost

        result = estimate_cost([])
        assert result["n_records"] == 0
        assert result["est_total_cost_usd"] == 0


# ── Tests: checkpoint ────────────────────────────────────────────────────


class TestCheckpoint:
    def test_save_and_load(self, tmp_path):
        from tools.slr_toolkit.llm_screening import _load_checkpoint, _save_checkpoint

        cp = tmp_path / "checkpoint.json"
        state = {"screened_ids": ["p001", "p002"], "version": 1}
        _save_checkpoint(cp, state)

        loaded = _load_checkpoint(cp)
        assert loaded["screened_ids"] == ["p001", "p002"]

    def test_load_nonexistent(self, tmp_path):
        from tools.slr_toolkit.llm_screening import _load_checkpoint

        loaded = _load_checkpoint(tmp_path / "nonexistent.json")
        assert loaded["screened_ids"] == []


# ── Tests: _write_decisions_csv ──────────────────────────────────────────


class TestWriteDecisions:
    def test_ranks_by_confidence_descending(self, tmp_path):
        from tools.slr_toolkit.llm_screening import _write_decisions_csv

        rows = [
            {"paper_id": "p001", "ai_decision": "include", "ai_confidence": "0.5",
             "reason_code": "INCLUDE", "reasoning": "test"},
            {"paper_id": "p002", "ai_decision": "exclude", "ai_confidence": "0.9",
             "reason_code": "EX-PARADIGM", "reasoning": "test"},
        ]
        out = tmp_path / "decisions.csv"
        _write_decisions_csv(out, rows)

        with open(out, encoding="utf-8") as f:
            result = list(csv.DictReader(f))
        assert result[0]["paper_id"] == "p002"
        assert result[0]["ai_rank"] == "1"
        assert result[1]["paper_id"] == "p001"
        assert result[1]["ai_rank"] == "2"

    def test_output_has_all_required_columns(self, tmp_path):
        from tools.slr_toolkit.llm_screening import _write_decisions_csv

        rows = [{"paper_id": "p001", "ai_decision": "include", "ai_confidence": "0.8"}]
        out = tmp_path / "decisions.csv"
        _write_decisions_csv(out, rows)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
        assert "paper_id" in cols
        assert "ai_decision" in cols
        assert "ai_rank" in cols
        assert "ai_confidence" in cols


# ── Tests: downstream compatibility ──────────────────────────────────────


class TestDownstreamCompatibility:
    """Verify the LLM output CSV is consumable by find_discrepancies and
    compute_ai_validation exactly like the ASReview output."""

    def _write_llm_decisions(self, path: Path) -> None:
        from tools.slr_toolkit.llm_screening import _write_decisions_csv
        _write_decisions_csv(path, [
            {"paper_id": "p001", "ai_decision": "include", "ai_confidence": "0.9",
             "reason_code": "INCLUDE", "reasoning": "quantum finance paper"},
            {"paper_id": "p002", "ai_decision": "include", "ai_confidence": "0.8",
             "reason_code": "INCLUDE", "reasoning": "portfolio optimization"},
            {"paper_id": "p003", "ai_decision": "exclude", "ai_confidence": "0.4",
             "reason_code": "EX-PARADIGM", "reasoning": "annealing only"},
            {"paper_id": "p004", "ai_decision": "exclude", "ai_confidence": "0.2",
             "reason_code": "EX-NONFIN", "reasoning": "chemistry application"},
        ])

    def test_find_discrepancies_accepts_llm_output(self, tmp_path, monkeypatch):
        from tools.slr_toolkit.screening import find_discrepancies

        ai_csv = tmp_path / "ai_decisions.csv"
        self._write_llm_decisions(ai_csv)

        human_csv = tmp_path / "human.csv"
        human_csv.write_text(
            "paper_id,decision\n"
            "p001,include\np002,exclude\np003,include\np004,exclude\n"
        )

        master = _make_master_csv(
            tmp_path / "master.csv",
            [{"paper_id": f"p{i:03d}", "title": f"T{i}"} for i in range(1, 5)],
        )
        monkeypatch.setattr(config, "MASTER_RECORDS_CSV", master)

        counts = find_discrepancies(human_csv, ai_csv, tmp_path / "disc.csv")

        assert counts["agree_include"] == 1
        assert counts["ai_rescue"] == 1
        assert counts["human_only"] == 1
        assert counts["agree_exclude"] == 1

    def test_compute_ai_validation_accepts_llm_output(self, tmp_path):
        from tools.slr_toolkit.screening import compute_ai_validation
        from openpyxl import Workbook

        # Validation workbook with known decisions
        val_path = tmp_path / "val.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Screening"
        for i, h in enumerate(["#", "Paper ID", "Title", "Authors", "Year",
                                "DOI", "Abstract", "Source",
                                "Rev A", "Rev B", "Final", "Notes"], 1):
            ws.cell(row=1, column=i, value=h)
        for idx, (pid, dec) in enumerate([
            ("p001", "include"), ("p002", "include"),
            ("p003", "exclude"), ("p004", "exclude"),
        ], start=2):
            ws.cell(row=idx, column=1, value=idx - 1)
            ws.cell(row=idx, column=2, value=pid)
            ws.cell(row=idx, column=3, value=f"Title {pid}")
            ws.cell(row=idx, column=9, value=dec)
            ws.cell(row=idx, column=11, value=dec)
        wb.save(val_path)

        # LLM decisions CSV
        ai_csv = tmp_path / "ai.csv"
        self._write_llm_decisions(ai_csv)

        metrics = compute_ai_validation(val_path, ai_csv, tmp_path / "report.md")

        assert metrics["n"] == 4
        assert "recall" in metrics
        assert "pass" in metrics
