"""Tests for query_builder module."""

from __future__ import annotations

from tools.slr_toolkit.query_builder import (
    build_arxiv_query,
    build_openalex_query,
    build_semantic_scholar_query,
)


class TestBuildOpenAlexQuery:
    """OpenAlex query builder."""

    def test_basic_search_key(self) -> None:
        result = build_openalex_query("quantum finance")
        assert result["search_key"] == "search"
        assert result["search_value"] == "quantum finance"
        assert "extra_filter" not in result

    def test_exact_mode(self) -> None:
        result = build_openalex_query("quantum finance", use_exact=True)
        assert result["search_key"] == "search.exact"

    def test_concept_ids_filter(self) -> None:
        result = build_openalex_query(
            "quantum",
            concept_ids=["C41008148", "C162324750"],
        )
        assert result["extra_filter"] == "concept.id:C41008148|C162324750"

    def test_concept_ids_single(self) -> None:
        result = build_openalex_query("quantum", concept_ids=["C41008148"])
        assert result["extra_filter"] == "concept.id:C41008148"

    def test_concept_ids_with_exact(self) -> None:
        result = build_openalex_query(
            "quantum",
            concept_ids=["C41008148"],
            use_exact=True,
        )
        assert result["search_key"] == "search.exact"
        assert "concept.id:C41008148" in result["extra_filter"]

    def test_no_concept_ids_no_extra_filter(self) -> None:
        result = build_openalex_query("test", concept_ids=None)
        assert "extra_filter" not in result

        result2 = build_openalex_query("test", concept_ids=[])
        assert "extra_filter" not in result2


class TestBuildArxivQuery:
    """arXiv query builder."""

    def test_single_term_wrapped(self) -> None:
        result = build_arxiv_query("quantum")
        assert "ti:quantum" in result
        assert "abs:quantum" in result

    def test_boolean_and_preserved(self) -> None:
        result = build_arxiv_query('"quantum computing" AND "finance"')
        assert "AND" in result
        assert 'ti:"quantum computing"' in result
        assert 'abs:"quantum computing"' in result
        assert 'ti:"finance"' in result
        assert 'abs:"finance"' in result

    def test_boolean_or_preserved(self) -> None:
        result = build_arxiv_query("portfolio OR pricing")
        assert "OR" in result
        assert "ti:portfolio" in result
        assert "ti:pricing" in result

    def test_quoted_phrase_preserved(self) -> None:
        result = build_arxiv_query('"quantum computing"')
        assert '"quantum computing"' in result

    def test_categories_added(self) -> None:
        result = build_arxiv_query("quantum", categories=["q-fin*", "quant-ph"])
        assert "cat:q-fin*" in result
        assert "cat:quant-ph" in result
        assert "AND" in result

    def test_categories_only(self) -> None:
        result = build_arxiv_query("", categories=["q-fin*"])
        assert "cat:q-fin*" in result

    def test_no_categories(self) -> None:
        result = build_arxiv_query("quantum", categories=None)
        assert "cat:" not in result


class TestBuildSemanticScholarQuery:
    """Semantic Scholar query builder (passthrough)."""

    def test_passthrough(self) -> None:
        raw = '"quantum computing" AND finance'
        assert build_semantic_scholar_query(raw) == raw

    def test_empty(self) -> None:
        assert build_semantic_scholar_query("") == ""
