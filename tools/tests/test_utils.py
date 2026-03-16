"""Tests for shared utility functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.slr_toolkit.utils import (
    atomic_write_text,
    cohens_kappa,
    generate_paper_id,
    percent_agreement,
    safe_float,
    safe_write_text,
)


class TestGeneratePaperId:
    def test_stable_hash(self) -> None:
        id1 = generate_paper_id("Quantum Finance", "Smith, J.", "2023")
        id2 = generate_paper_id("Quantum Finance", "Smith, J.", "2023")
        assert id1 == id2
        assert len(id1) == 12

    def test_case_insensitive_title(self) -> None:
        id1 = generate_paper_id("Quantum Finance", "Smith", "2023")
        id2 = generate_paper_id("quantum finance", "Smith", "2023")
        assert id1 == id2

    def test_different_papers_different_ids(self) -> None:
        id1 = generate_paper_id("Paper A", "Smith", "2023")
        id2 = generate_paper_id("Paper B", "Jones", "2024")
        assert id1 != id2

    def test_handles_none_fields(self) -> None:
        pid = generate_paper_id(None, None, None)
        assert len(pid) == 12

    def test_first_author_only(self) -> None:
        id1 = generate_paper_id("X", "Smith, J.; Jones, K.", "2023")
        id2 = generate_paper_id("X", "Smith, J.", "2023")
        assert id1 == id2


class TestCohensKappa:
    def test_perfect_agreement(self) -> None:
        assert cohens_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0

    def test_no_agreement(self) -> None:
        kappa = cohens_kappa(["a", "a", "a"], ["b", "b", "b"])
        assert kappa <= 0

    def test_empty_lists(self) -> None:
        assert cohens_kappa([], []) == 1.0

    def test_unequal_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            cohens_kappa(["a"], ["a", "b"])


class TestPercentAgreement:
    def test_full_agreement(self) -> None:
        assert percent_agreement(["a", "b"], ["a", "b"]) == 100.0

    def test_half_agreement(self) -> None:
        assert percent_agreement(["a", "b"], ["a", "c"]) == 50.0

    def test_empty_lists(self) -> None:
        assert percent_agreement([], []) == 100.0


class TestSafeFloat:
    def test_valid_float(self) -> None:
        assert safe_float("3.14") == 3.14

    def test_invalid_returns_default(self) -> None:
        assert safe_float("not_a_number", 0.0) == 0.0

    def test_none_returns_default(self) -> None:
        assert safe_float(None, -1.0) == -1.0

    def test_int_input(self) -> None:
        assert safe_float(42) == 42.0


class TestAtomicWriteText:
    def test_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        atomic_write_text(path, "hello")
        assert path.read_text(encoding="utf-8") == "hello"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "dir" / "test.txt"
        atomic_write_text(path, "content")
        assert path.read_text(encoding="utf-8") == "content"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("old", encoding="utf-8")
        atomic_write_text(path, "new")
        assert path.read_text(encoding="utf-8") == "new"


class TestSafeWriteText:
    def test_skips_existing_by_default(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("original", encoding="utf-8")
        result = safe_write_text(path, "overwrite")
        assert result is False
        assert path.read_text(encoding="utf-8") == "original"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("original", encoding="utf-8")
        result = safe_write_text(path, "overwrite", force=True)
        assert result is True
        assert path.read_text(encoding="utf-8") == "overwrite"
