"""Tests for deduplication logic."""

from __future__ import annotations

import pandas as pd
import pytest

from tools.slr_toolkit.dedup import deduplicate


def _make_df(records: list[dict]) -> pd.DataFrame:
    """Create a DataFrame with all normalised columns filled in."""
    from tools.slr_toolkit.config import NORMALIZED_COLUMNS

    df = pd.DataFrame(records)
    for col in NORMALIZED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


class TestDOIDedup:
    """Pass-1 DOI exact-match deduplication."""

    def test_same_doi_marks_duplicate(self) -> None:
        df = _make_df([
            {"paper_id": "aaa111", "doi": "10.1234/abc", "title": "Paper A", "year": "2023", "authors": "Smith"},
            {"paper_id": "bbb222", "doi": "10.1234/ABC", "title": "Paper A copy", "year": "2023", "authors": "Smith"},
        ])
        result = deduplicate(df, fuzzy=False)
        assert result.at[0, "duplicate_of"] == ""
        assert result.at[1, "duplicate_of"] == "aaa111"

    def test_different_doi_no_duplicate(self) -> None:
        df = _make_df([
            {"paper_id": "aaa111", "doi": "10.1234/abc", "title": "Paper A", "year": "2023", "authors": "Smith"},
            {"paper_id": "bbb222", "doi": "10.1234/xyz", "title": "Paper B", "year": "2024", "authors": "Jones"},
        ])
        result = deduplicate(df, fuzzy=False)
        assert result.at[0, "duplicate_of"] == ""
        assert result.at[1, "duplicate_of"] == ""

    def test_empty_doi_not_matched(self) -> None:
        df = _make_df([
            {"paper_id": "aaa111", "doi": "", "title": "Paper A", "year": "2023", "authors": "Smith"},
            {"paper_id": "bbb222", "doi": "", "title": "Paper B", "year": "2023", "authors": "Jones"},
        ])
        result = deduplicate(df, fuzzy=False)
        assert result.at[0, "duplicate_of"] == ""
        assert result.at[1, "duplicate_of"] == ""


class TestFuzzyDedup:
    """Pass-2 fuzzy title dedup (requires rapidfuzz)."""

    @pytest.fixture(autouse=True)
    def _check_rapidfuzz(self) -> None:
        pytest.importorskip("rapidfuzz")

    def test_similar_title_same_author_year(self) -> None:
        df = _make_df([
            {"paper_id": "aaa111", "doi": "", "title": "Quantum Portfolio Optimization Using QAOA",
             "year": "2023", "authors": "Smith, J."},
            {"paper_id": "bbb222", "doi": "", "title": "Quantum portfolio optimization using QAOA",
             "year": "2023", "authors": "Smith, J.; Jones, K."},
        ])
        result = deduplicate(df, fuzzy=True)
        assert result.at[1, "duplicate_of"] == "aaa111"

    def test_different_titles_not_matched(self) -> None:
        df = _make_df([
            {"paper_id": "aaa111", "doi": "", "title": "Quantum Portfolio Optimization",
             "year": "2023", "authors": "Smith, J."},
            {"paper_id": "bbb222", "doi": "", "title": "Classical Machine Learning for Credit Risk",
             "year": "2023", "authors": "Jones, K."},
        ])
        result = deduplicate(df, fuzzy=True)
        assert result.at[0, "duplicate_of"] == ""
        assert result.at[1, "duplicate_of"] == ""

    def test_same_title_different_author_initial(self) -> None:
        """Different first-author initials should NOT match."""
        df = _make_df([
            {"paper_id": "aaa111", "doi": "", "title": "Quantum Finance Review",
             "year": "2023", "authors": "Smith, J."},
            {"paper_id": "bbb222", "doi": "", "title": "Quantum Finance Review",
             "year": "2023", "authors": "Jones, K."},
        ])
        result = deduplicate(df, fuzzy=True)
        assert result.at[0, "duplicate_of"] == ""
        assert result.at[1, "duplicate_of"] == ""
