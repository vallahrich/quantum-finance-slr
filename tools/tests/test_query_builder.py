"""Tests for query_builder module."""

from __future__ import annotations

from tools.slr_toolkit.query_builder import (
    build_arxiv_query,
    build_openalex_query,
    build_scopus_query,
    build_semantic_scholar_query,
    expand_wildcards_for_openalex,
)


class TestBuildOpenAlexQuery:
    """OpenAlex query builder — uses title_and_abstract.search filter."""

    def test_basic_filter_key(self) -> None:
        result = build_openalex_query("quantum finance")
        assert result["filter_key"] == "title_and_abstract.search"
        assert result["filter_value"] == "quantum finance"
        assert "extra_filter" not in result

    def test_exact_mode(self) -> None:
        result = build_openalex_query("quantum finance", use_exact=True)
        assert result["filter_key"] == "title_and_abstract.search.exact"

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
        assert result["filter_key"] == "title_and_abstract.search.exact"
        assert "concept.id:C41008148" in result["extra_filter"]

    def test_no_concept_ids_no_extra_filter(self) -> None:
        result = build_openalex_query("test", concept_ids=None)
        assert "extra_filter" not in result

        result2 = build_openalex_query("test", concept_ids=[])
        assert "extra_filter" not in result2

    def test_no_search_key(self) -> None:
        """Must NOT use old full-text search= param."""
        result = build_openalex_query("quantum finance")
        assert "search_key" not in result
        assert "search_value" not in result

    def test_wildcard_expansion_applied(self) -> None:
        """Wildcards in the query must be expanded before returning."""
        result = build_openalex_query('"quantum algorithm*" AND finance')
        assert "*" not in result["filter_value"]
        assert "quantum algorithms" in result["filter_value"]


class TestExpandWildcardsForOpenalex:
    """Wildcard expansion for OpenAlex queries."""

    def test_quoted_wildcard_expanded(self) -> None:
        result = expand_wildcards_for_openalex('"quantum algorithm*" AND finance')
        assert "quantum algorithms" in result
        assert "*" not in result

    def test_unquoted_wildcard_expanded(self) -> None:
        result = expand_wildcards_for_openalex("quantum algorithm* AND finance")
        assert "quantum algorithms" in result
        assert "*" not in result

    def test_multiple_wildcards(self) -> None:
        q = '"quantum algorithm*" AND ("portfolio optim*" OR finance)'
        result = expand_wildcards_for_openalex(q)
        assert "*" not in result
        assert "quantum algorithms" in result
        assert "portfolio optimization" in result
        assert "portfolio optimisation" in result

    def test_no_wildcards_unchanged(self) -> None:
        q = '"quantum computing" AND finance'
        assert expand_wildcards_for_openalex(q) == q

    def test_longer_pattern_matches_first(self) -> None:
        """'financial derivative*' should match before 'derivative*'."""
        q = '"financial derivative*"'
        result = expand_wildcards_for_openalex(q)
        assert "financial derivatives" in result
        # Should NOT produce bare "derivatives" from the shorter pattern
        assert result.count("derivative") >= 2  # "financial derivative" + "financial derivatives"

    def test_case_insensitive(self) -> None:
        result = expand_wildcards_for_openalex('"Quantum Algorithm*"')
        assert "quantum algorithms" in result
        assert "*" not in result

    def test_new_amendment_a6_wildcards(self) -> None:
        """Amendment A6 wildcard terms must be expanded."""
        for term in ["quantum linear system*", "interest rate derivative*", "structured product*"]:
            result = expand_wildcards_for_openalex(f'"{term}"')
            assert "*" not in result
            # Check both singular and plural forms are present
            singular = term.rstrip("*")
            assert singular in result


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
        """categories=None must NOT add any cat: clause (opt-in only)."""
        result = build_arxiv_query("quantum", categories=None)
        assert "cat:" not in result

    def test_empty_categories_list(self) -> None:
        """categories=[] must NOT add any cat: clause."""
        result = build_arxiv_query("quantum", categories=[])
        assert "cat:" not in result

    def test_parenthesized_groups(self) -> None:
        """Parenthesized Boolean groups must not mangle ti:/abs: prefixes."""
        result = build_arxiv_query(
            '"quantum algorithm*" AND ("portfolio optim*" OR finance)'
        )
        assert 'ti:"quantum algorithm*"' in result
        assert 'abs:"quantum algorithm*"' in result
        assert 'ti:"portfolio optim*"' in result
        assert 'abs:"portfolio optim*"' in result
        assert "ti:finance" in result
        assert "abs:finance" in result
        # Parentheses preserved for grouping
        assert "(ti:finance OR abs:finance)" in result

    def test_nested_parentheses(self) -> None:
        """Multiple levels of parens should be handled."""
        result = build_arxiv_query("((quantum OR classical) AND finance)")
        assert "ti:quantum" in result
        assert "ti:finance" in result


class TestBuildScopusQuery:
    """Scopus query builder — auto-wraps in TITLE-ABS-KEY."""

    def test_auto_wraps(self) -> None:
        result = build_scopus_query('"quantum computing" AND finance')
        assert result.startswith("TITLE-ABS-KEY(")
        assert "PUBYEAR > 2015" in result

    def test_custom_from_year(self) -> None:
        result = build_scopus_query("quantum", from_year=2020)
        assert "PUBYEAR > 2019" in result

    def test_already_formatted_unchanged(self) -> None:
        raw = 'TITLE-ABS-KEY("quantum computing") AND PUBYEAR > 2015'
        assert build_scopus_query(raw) == raw

    def test_title_abs_variant_unchanged(self) -> None:
        raw = 'TITLE-ABS("quantum") AND PUBYEAR > 2015'
        assert build_scopus_query(raw) == raw


class TestBuildSemanticScholarQuery:
    """Semantic Scholar query builder (passthrough)."""

    def test_passthrough(self) -> None:
        raw = '"quantum computing" AND finance'
        assert build_semantic_scholar_query(raw) == raw

    def test_empty(self) -> None:
        assert build_semantic_scholar_query("") == ""
