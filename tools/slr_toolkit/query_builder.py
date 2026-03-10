"""Query adapters — translate a raw Boolean query into API-specific syntax.

Each builder returns a dict with the keys expected by the corresponding
search function (e.g. ``search`` param value, ``filter`` additions).
"""

from __future__ import annotations

import re
import urllib.parse


# ── OpenAlex ──────────────────────────────────────────────────────────────

# Wildcard expansions for OpenAlex (which doesn't support * wildcards).
# OpenAlex silently strips *, ?, ~ characters from queries.
# Only needs to cover terms actually used in our SLR queries.
OPENALEX_WILDCARD_EXPANSIONS: dict[str, str] = {
    "quantum algorithm*": '"quantum algorithm" OR "quantum algorithms"',
    "quantum circuit*": '"quantum circuit" OR "quantum circuits"',
    "quantum walk*": '"quantum walk" OR "quantum walks"',
    "portfolio optim*": '"portfolio optimization" OR "portfolio optimisation"',
    "stock price*": '"stock price" OR "stock prices"',
    "financial derivative*": '"financial derivative" OR "financial derivatives"',
    "derivative*": '"derivative" OR "derivatives"',
}


def expand_wildcards_for_openalex(query: str) -> str:
    """Expand wildcard patterns (``term*``) into OR groups for OpenAlex.

    OpenAlex does not support wildcard characters and silently removes them.
    This function replaces known wildcard patterns with explicit OR expansions
    so that variant forms are matched.

    Parameters
    ----------
    query : str
        Query string potentially containing ``*`` wildcard patterns.

    Returns
    -------
    str with all known wildcard patterns replaced by ``(expansion)`` groups.
    """
    result = query
    # Sort by length descending so longer patterns match first
    # (e.g. "financial derivative*" before "derivative*")
    for pattern, expansion in sorted(
        OPENALEX_WILDCARD_EXPANSIONS.items(), key=lambda x: len(x[0]), reverse=True
    ):
        # Match both quoted and unquoted forms, case-insensitive
        # e.g. "quantum algorithm*" or quantum algorithm*
        quoted = f'"{pattern}"'
        if quoted.lower() in result.lower():
            # Find the actual case-matched substring and replace it
            idx = result.lower().index(quoted.lower())
            result = result[:idx] + f"({expansion})" + result[idx + len(quoted):]
        elif pattern.lower() in result.lower():
            idx = result.lower().index(pattern.lower())
            result = result[:idx] + f"({expansion})" + result[idx + len(pattern):]

    return result


def build_openalex_query(
    raw_query: str,
    *,
    concept_ids: list[str] | None = None,
    use_exact: bool = False,
) -> dict[str, str]:
    """Build OpenAlex API parameters from a raw Boolean query.

    Uses ``filter=title_and_abstract.search:`` instead of the ``search=``
    parameter so that matching is restricted to title and abstract (aligned
    with standard SLR field-restricted searching like Scopus TITLE-ABS-KEY).

    Wildcards (``*``) are expanded to OR groups since OpenAlex silently
    strips wildcard characters.

    Parameters
    ----------
    raw_query : str
        Free-text query with optional Boolean operators (AND / OR).
        OpenAlex expects uppercase AND/OR — this function preserves them.
    concept_ids : list[str] | None
        Optional OpenAlex concept IDs (e.g. ``["C41008148", "C162324750"]``)
        to add as a filter.
    use_exact : bool
        If True, use ``title_and_abstract.search.exact`` for unstemmed
        matching.

    Returns
    -------
    dict with ``"filter_key"`` and ``"filter_value"``,
    plus an optional ``"extra_filter"`` string to append to the filter param.
    """
    filter_key = (
        "title_and_abstract.search.exact" if use_exact
        else "title_and_abstract.search"
    )

    expanded_query = expand_wildcards_for_openalex(raw_query)

    result: dict[str, str] = {
        "filter_key": filter_key,
        "filter_value": expanded_query,
    }

    if concept_ids:
        # OpenAlex filter: concept.id:ID1|ID2  (pipe = OR within field)
        ids_str = "|".join(concept_ids)
        result["extra_filter"] = f"concept.id:{ids_str}"

    return result


# ── arXiv ─────────────────────────────────────────────────────────────────

def _wrap_arxiv_term(term: str) -> str:
    """Wrap a single term/phrase with ``ti:`` and ``abs:`` field prefixes.

    Quoted phrases are preserved; individual terms are left bare within the
    field prefix.  Leading/trailing parentheses from Boolean grouping are
    preserved outside the field-prefix wrapper.

    Returns ``{leading}(ti:{term} OR abs:{term}){trailing}``.
    """
    term = term.strip()
    if not term:
        return ""
    # Strip leading/trailing parentheses (Boolean grouping, not part of term)
    leading = ""
    trailing = ""
    while term.startswith("("):
        leading += "("
        term = term[1:]
    while term.endswith(")"):
        trailing += ")"
        term = term[:-1]
    term = term.strip()
    if not term:
        return leading + trailing
    return f"{leading}(ti:{term} OR abs:{term}){trailing}"


_BOOL_OPS = re.compile(r"\b(AND|OR|ANDNOT)\b")


def build_arxiv_query(
    raw_query: str,
    *,
    categories: list[str] | None = None,
) -> str:
    """Build an arXiv search_query string from a raw Boolean query.

    * Individual terms and quoted phrases are wrapped with ``ti:`` and
      ``abs:`` field prefixes so the search covers title+abstract.
    * Boolean operators (AND / OR / ANDNOT) are preserved.
    * Optional ``categories`` are appended as ``(cat:a OR cat:b)``.

    Parameters
    ----------
    raw_query : str
        Human-readable Boolean query, e.g.
        ``"quantum computing" AND "finance"``.
    categories : list[str] | None
        arXiv category filters (e.g. ``["q-fin*", "quant-ph", "cs.CE"]``).

    Returns
    -------
    str suitable for the ``search_query`` parameter of the arXiv API.
    """
    # Split on Boolean operators, keeping the operators as tokens
    tokens = _BOOL_OPS.split(raw_query)
    parts: list[str] = []

    for token in tokens:
        stripped = token.strip()
        if not stripped:
            continue
        if stripped in ("AND", "OR", "ANDNOT"):
            parts.append(stripped)
        else:
            parts.append(_wrap_arxiv_term(stripped))

    query = " ".join(parts)

    if categories:
        cat_parts = " OR ".join(f"cat:{cat}" for cat in categories)
        cat_clause = f"({cat_parts})"
        if query:
            query = f"({query}) AND {cat_clause}"
        else:
            query = cat_clause

    return query


# ── Scopus ────────────────────────────────────────────────────────────────

def build_scopus_query(raw_query: str, *, from_year: int = 2016) -> str:
    """Build a Scopus search query with TITLE-ABS-KEY field restriction.

    If the query already contains ``TITLE-ABS-KEY`` or ``TITLE-ABS(`` it is
    returned unchanged (user passed a pre-formatted Scopus query).  Otherwise
    the raw Boolean query is wrapped in ``TITLE-ABS-KEY()`` and a
    ``PUBYEAR > {from_year - 1}`` filter is appended.

    Parameters
    ----------
    raw_query : str
        Boolean query string.
    from_year : int
        Earliest publication year to include.
    """
    upper = raw_query.upper()
    if "TITLE-ABS-KEY" in upper or "TITLE-ABS(" in upper:
        return raw_query
    return f"TITLE-ABS-KEY({raw_query}) AND PUBYEAR > {from_year - 1}"


# ── Semantic Scholar ──────────────────────────────────────────────────────

def build_semantic_scholar_query(raw_query: str) -> str:
    """Build a Semantic Scholar query (passthrough).

    Semantic Scholar handles free-text well, so we just return the raw query.
    """
    return raw_query
