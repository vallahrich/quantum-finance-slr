"""Tests for LLM-assisted topic coding."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.slr_toolkit import config


def _make_master_csv(path: Path, records: list[dict]) -> Path:
    cols = config.NORMALIZED_COLUMNS + ["duplicate_of"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for rec in records:
            row = {c: rec.get(c, "") for c in cols}
            writer.writerow(row)
    return path


def _make_full_text_csv(path: Path, rows: list[dict]) -> Path:
    cols = [
        "paper_id", "decision_reviewer_A", "decision_reviewer_B", "conflict",
        "final_decision", "exclusion_reason", "tier2_applicable", "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in cols})
    return path


class TestLoadIncludedPapers:
    def test_selects_only_included_and_joins_master(self, tmp_path, monkeypatch):
        from tools.slr_toolkit.topic_coding import load_included_papers

        ft = _make_full_text_csv(
            tmp_path / "full_text.csv",
            [
                {"paper_id": "p001", "final_decision": "include"},
                {"paper_id": "p002", "final_decision": "exclude"},
                {"paper_id": "p003", "final_decision": "include"},
            ],
        )
        master = _make_master_csv(
            tmp_path / "master.csv",
            [
                {"paper_id": "p001", "title": "Paper 1", "abstract": "A1", "venue": "V1", "year": "2024"},
                {"paper_id": "p002", "title": "Paper 2", "abstract": "A2", "venue": "V2", "year": "2023"},
                {"paper_id": "p003", "title": "Paper 3", "abstract": "A3", "venue": "V3", "year": "2022"},
            ],
        )
        monkeypatch.setattr(config, "MASTER_RECORDS_CSV", master)

        rows = load_included_papers(ft, master)
        assert [row["paper_id"] for row in rows] == ["p001", "p003"]
        assert rows[0]["title"] == "Paper 1"
        assert rows[1]["abstract"] == "A3"


class TestParseTopicResponse:
    def test_parses_valid_multi_label_response(self):
        from tools.slr_toolkit.topic_coding import _parse_topic_response

        raw = {
            "choices": [{
                "message": {"content": json.dumps({
                    "primary_topics": ["portfolio_optimization"],
                    "secondary_topics": ["benchmarking_and_advantage", "optimization_methods"],
                    "emergent_topics": [],
                    "application_area": "portfolio allocation",
                    "method_family": "qaoa_or_optimization",
                    "evaluation_type": "benchmark_comparison",
                    "confidence": 0.92,
                    "rationale": "Finance optimization paper with explicit benchmarking.",
                })}
            }],
            "usage": {"prompt_tokens": 123},
        }

        parsed = _parse_topic_response(raw)
        assert parsed["primary_topics"] == ["portfolio_optimization"]
        assert "optimization_methods" in parsed["secondary_topics"]
        assert parsed["method_family"] == "qaoa_or_optimization"
        assert parsed["evaluation_type"] == "benchmark_comparison"

    def test_malformed_json_raises(self):
        from tools.slr_toolkit.topic_coding import _parse_topic_response

        raw = {
            "choices": [{"message": {"content": "not json"}}],
            "usage": {},
        }
        with pytest.raises(ValueError, match="Cannot parse JSON"):
            _parse_topic_response(raw)

    def test_invalid_method_and_eval_fall_back(self):
        from tools.slr_toolkit.topic_coding import _parse_topic_response

        raw = {
            "choices": [{
                "message": {"content": json.dumps({
                    "primary_topics": ["portfolio_optimization"],
                    "secondary_topics": [],
                    "emergent_topics": ["novel_theme"],
                    "application_area": "portfolio",
                    "method_family": "weird",
                    "evaluation_type": "odd",
                    "confidence": "oops",
                    "rationale": "x",
                })}
            }],
            "usage": {},
        }
        parsed = _parse_topic_response(raw)
        assert parsed["method_family"] == "other_gate_based"
        assert parsed["evaluation_type"] == "conceptual_only"
        assert parsed["confidence"] == 0.5
        assert parsed["emergent_topics"] == ["novel_theme"]


class TestTopicSummary:
    def test_generates_summary_from_csv(self, tmp_path):
        from tools.slr_toolkit.topic_coding import generate_topic_summary

        csv_path = tmp_path / "topic_coding.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "paper_id", "title", "final_decision", "primary_topics",
                "secondary_topics", "emergent_topics", "application_area",
                "method_family", "evaluation_type", "llm_confidence",
                "llm_rationale", "review_status", "review_notes",
            ])
            writer.writeheader()
            writer.writerow({
                "paper_id": "p001",
                "title": "Paper 1",
                "final_decision": "include",
                "primary_topics": json.dumps(["portfolio_optimization"]),
                "secondary_topics": json.dumps(["benchmarking_and_advantage"]),
                "emergent_topics": json.dumps([]),
                "application_area": "portfolio allocation",
                "method_family": "qaoa_or_optimization",
                "evaluation_type": "benchmark_comparison",
                "llm_confidence": "0.90",
                "llm_rationale": "x",
                "review_status": "draft_llm",
                "review_notes": "",
            })
            writer.writerow({
                "paper_id": "p002",
                "title": "Paper 2",
                "final_decision": "include",
                "primary_topics": json.dumps(["portfolio_optimization"]),
                "secondary_topics": json.dumps([]),
                "emergent_topics": json.dumps(["quantum_insurance_products"]),
                "application_area": "portfolio allocation",
                "method_family": "quantum_ml",
                "evaluation_type": "simulator",
                "llm_confidence": "0.75",
                "llm_rationale": "y",
                "review_status": "draft_llm",
                "review_notes": "",
            })

        out = generate_topic_summary(csv_path, tmp_path / "summary.md")
        text = out.read_text(encoding="utf-8")
        assert "Topic Coding Summary" in text
        assert "portfolio_optimization" in text
        assert "quantum_insurance_products" in text


class TestRunTopicCoding:
    def test_dry_run_cost_estimate(self, tmp_path, monkeypatch):
        from tools.slr_toolkit.topic_coding import run_topic_coding

        ft = _make_full_text_csv(
            tmp_path / "full_text.csv",
            [{"paper_id": "p001", "final_decision": "include"}],
        )
        master = _make_master_csv(
            tmp_path / "master.csv",
            [{"paper_id": "p001", "title": "Paper 1", "abstract": "A1", "venue": "V1", "year": "2024"}],
        )
        monkeypatch.setattr(config, "MASTER_RECORDS_CSV", master)

        result = run_topic_coding(input_file=ft, dry_run=True)
        assert result["n_records"] == 1
        assert result["est_total_tokens"] > 0

    def test_empty_included_set_raises(self, tmp_path):
        from tools.slr_toolkit.topic_coding import run_topic_coding

        ft = _make_full_text_csv(
            tmp_path / "full_text.csv",
            [{"paper_id": "p001", "final_decision": "exclude"}],
        )
        with pytest.raises(ValueError, match="No included papers"):
            run_topic_coding(input_file=ft, dry_run=True)

    def test_missing_credentials_raise_for_real_run(self, tmp_path, monkeypatch):
        from tools.slr_toolkit.topic_coding import run_topic_coding

        ft = _make_full_text_csv(
            tmp_path / "full_text.csv",
            [{"paper_id": "p001", "final_decision": "include"}],
        )
        master = _make_master_csv(
            tmp_path / "master.csv",
            [{"paper_id": "p001", "title": "Paper 1", "abstract": "A1", "venue": "V1", "year": "2024"}],
        )
        monkeypatch.setattr(config, "MASTER_RECORDS_CSV", master)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

        with pytest.raises(RuntimeError, match="endpoint not set"):
            run_topic_coding(input_file=ft)

    def test_checkpoint_resume_keeps_existing_rows(self, tmp_path, monkeypatch):
        from tools.slr_toolkit.topic_coding import run_topic_coding, write_topic_coding_csv

        ft = _make_full_text_csv(
            tmp_path / "full_text.csv",
            [
                {"paper_id": "p001", "final_decision": "include"},
                {"paper_id": "p002", "final_decision": "include"},
            ],
        )
        master = _make_master_csv(
            tmp_path / "master.csv",
            [
                {"paper_id": "p001", "title": "Paper 1", "abstract": "A1", "venue": "V1", "year": "2024"},
                {"paper_id": "p002", "title": "Paper 2", "abstract": "A2", "venue": "V2", "year": "2024"},
            ],
        )
        monkeypatch.setattr(config, "MASTER_RECORDS_CSV", master)

        output = tmp_path / "topic_coding.csv"
        checkpoint = tmp_path / "checkpoint.json"
        prompt_log = tmp_path / "prompt_log.jsonl"
        summary = tmp_path / "summary.md"

        write_topic_coding_csv(output, [{
            "paper_id": "p001",
            "title": "Paper 1",
            "final_decision": "include",
            "primary_topics": json.dumps(["portfolio_optimization"]),
            "secondary_topics": json.dumps([]),
            "emergent_topics": json.dumps([]),
            "application_area": "portfolio",
            "method_family": "qaoa_or_optimization",
            "evaluation_type": "simulator",
            "llm_confidence": "0.8000",
            "llm_rationale": "x",
            "review_status": "draft_llm",
            "review_notes": "",
        }])
        checkpoint.write_text(json.dumps({"screened_ids": ["p001"], "version": 1}), encoding="utf-8")

        def fake_screen(*args, **kwargs):
            return {
                "primary_topics": ["risk_management"],
                "secondary_topics": [],
                "emergent_topics": [],
                "application_area": "risk",
                "method_family": "other_gate_based",
                "evaluation_type": "simulator",
                "confidence": 0.7,
                "rationale": "x",
                "_usage": {},
            }

        monkeypatch.setattr("tools.slr_toolkit.topic_coding._screen_one_record", fake_screen)
        result = run_topic_coding(
            input_file=ft,
            api_key="key",
            endpoint="https://example.openai.azure.com",
            deployment="gpt",
            output_path=output,
            summary_path=summary,
            checkpoint_path=checkpoint,
            prompt_log_path=prompt_log,
        )
        assert result == output
        with open(output, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert {row["paper_id"] for row in rows} == {"p001", "p002"}
