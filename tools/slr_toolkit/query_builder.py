"""Query adapters — translate a raw Boolean query into API-specific syntax.

Each builder returns a dict with the keys expected by the corresponding
search function (e.g. ``search`` param value, ``filter`` additions).
"""

from __future__ import annotations

import re
import urllib.parse


# ── OpenAlex ──────────────────────────────────────────────────────────────

def build_openalex_query(
    raw_query: str,
    *,
    concept_ids: list[str] | None = None,
    use_exact: bool = False,
) -> dict[str, str]:
    """Build OpenAlex API parameters from a raw Boolean query.

    Parameters
    ----------
    raw_query : str
        Free-text query with optional Boolean operators (AND / OR).
        OpenAlex expects uppercase AND/OR — this function preserves them.
    concept_ids : list[str] | None
        Optional OpenAlex concept IDs (e.g. ``["C41008148", "C162324750"]``)
        to add as a filter.
    use_exact : bool
        If True, use ``search.exact`` instead of ``search`` so OpenAlex
        performs unstemmed matching.

    Returns
    -------
    dict with ``"search_key"`` (the param name) and ``"search_value"``,
    plus an optional ``"extra_filter"`` string to append to the filter param.
    """
    search_key = "search.exact" if use_exact else "search"
    result: dict[str, str] = {
        "search_key": search_key,
        "search_value": raw_query,
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
    field prefix.  Returns ``(ti:{term} OR abs:{term})``.
    """
    term = term.strip()
    if not term:
        return ""
    return f"(ti:{term} OR abs:{term})"


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


# ── Semantic Scholar ──────────────────────────────────────────────────────

def build_semantic_scholar_query(raw_query: str) -> str:
    """Build a Semantic Scholar query (passthrough).

    Semantic Scholar handles free-text well, so we just return the raw query.
    """
    return raw_query
