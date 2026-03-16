"""Automated API search — OpenAlex, arXiv, Semantic Scholar, Scopus/WoS stubs.

Each searcher returns a list of dicts with normalised column names.
Results are auto-ingested into the pipeline (normalized_records.csv).
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .ingest import _detect_preprint
from .query_builder import build_arxiv_query, build_openalex_query, build_scopus_query
from .search_run import create_search_run
from .utils import ensure_dir, generate_paper_id


# ── PRISMA-S query logger ─────────────────────────────────────────────────

_INTERFACE_MAP: dict[str, str] = {
    "openalex": "OpenAlex REST API v2",
    "arxiv": "arXiv Atom API",
    "semantic_scholar": "Semantic Scholar Graph API v1",
    "scopus": "Scopus Search API (Elsevier)",
    "wos": "Web of Science Starter API v1 (Clarivate)",
}


def _log_search_to_xlsx(
    source: str,
    query: str,
    run_date: str,
    results_n: int,
    *,
    fields: str = "",
    date_limits: str = "",
    notes: str = "",
) -> None:
    """Append a PRISMA-S compliant row to search_log.xlsx."""
    path = config.SEARCH_LOG_XLSX
    ensure_dir(path.parent)

    interface = _INTERFACE_MAP.get(source, source)

    row = {
        "SearchRunID": f"{run_date}_{source}",
        "Date": run_date,
        "Database": source,
        "Interface": interface,
        "FullSearchString": query,
        "Fields": fields or _default_fields(source),
        "DateLimits": date_limits or "2016-01-01 to present",
        "LanguageLimits": "None (applied at screening via EX-NOTEN)",
        "OtherLimits": "",
        "ResultsN": results_n,
        "ExportFormat": "JSON (auto-normalised to CSV)",
        "ExportFiles": f"api_search_{source}.json",
        "Notes": notes,
    }

    if path.exists():
        try:
            existing = pd.read_excel(path, dtype=str).fillna("")
        except Exception:
            existing = pd.DataFrame(columns=config.SEARCH_LOG_COLUMNS)
    else:
        existing = pd.DataFrame(columns=config.SEARCH_LOG_COLUMNS)

    new_row = pd.DataFrame([row])
    updated = pd.concat([existing, new_row], ignore_index=True)
    updated.to_excel(path, index=False, engine="openpyxl")
    log.info("Logged search to %s", path)


def _default_fields(source: str) -> str:
    """Return default field description per source."""
    return {
        "openalex": "title_and_abstract.search filter + concept.id filter",
        "arxiv": "ti: + abs: + cat:",
        "semantic_scholar": "query (title + abstract)",
        "scopus": "TITLE-ABS-KEY",
        "wos": "TS (Topic Search)",
    }.get(source, "")


_SAFETY_LIMIT = 50_000  # warn (but don't stop) if a single source exceeds this

log = logging.getLogger("slr_toolkit.api_search")

# ── Rate-limit helper ──────────────────────────────────────────────────────

def _rate_limited_get(url: str, *, delay: float = 1.0, timeout: int = 30) -> bytes:
    """GET with a polite delay and timeout."""
    time.sleep(delay)
    req = urllib.request.Request(url, headers={
        "User-Agent": "quantum-finance-slr/0.1 (SLR toolkit; mailto:slr@example.com)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ═══════════════════════════════════════════════════════════════════════════
# OpenAlex  (free API key required since Feb 2026)
# Docs: https://docs.openalex.org
# ═══════════════════════════════════════════════════════════════════════════

_OPENALEX_WORKS = "https://api.openalex.org/works"
_OPENALEX_CONCEPTS = "https://api.openalex.org/concepts"


def resolve_openalex_concepts(term: str) -> list[dict]:
    """Look up OpenAlex concept IDs matching *term*.

    Calls ``https://api.openalex.org/concepts?search={term}`` and returns
    the top 3 matches, each as ``{"id": "C...", "display_name": "..."}``
    """
    params = urllib.parse.urlencode({"search": term})
    url = f"{_OPENALEX_CONCEPTS}?{params}"
    try:
        data = json.loads(_rate_limited_get(url, delay=0.2))
    except Exception as exc:
        log.error("OpenAlex concept lookup failed for %r: %s", term, exc)
        return []

    results = data.get("results", [])
    out: list[dict] = []
    for r in results[:3]:
        oa_id = r.get("id", "")
        # Extract the short ID (e.g. "C41008148") from the full URL
        short_id = oa_id.rsplit("/", 1)[-1] if "/" in oa_id else oa_id
        out.append({
            "id": short_id,
            "display_name": r.get("display_name", ""),
        })
    return out


def _openalex_parse_work(w: dict) -> dict[str, Any]:
    """Convert an OpenAlex work object to a normalised record dict."""
    # Authors
    authorships = w.get("authorships", [])
    authors = "; ".join(
        a.get("author", {}).get("display_name", "")
        for a in authorships
    )

    # Venue / primary location
    primary = w.get("primary_location") or {}
    source = primary.get("source") or {}
    venue = source.get("display_name", "")

    # Keywords (concepts in OpenAlex)
    concepts = w.get("concepts", [])
    keywords = "; ".join(c.get("display_name", "") for c in concepts[:10])

    # Abstract — OpenAlex provides inverted index; reconstruct
    abstract = ""
    inv_idx = w.get("abstract_inverted_index")
    if inv_idx:
        try:
            word_positions: list[tuple[int, str]] = []
            for word, positions in inv_idx.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            abstract = " ".join(w for _, w in word_positions)
        except Exception:
            pass

    doi_raw = w.get("doi", "") or ""
    doi = doi_raw.replace("https://doi.org/", "")

    return {
        "title": w.get("title", "") or "",
        "authors": authors,
        "year": str(w.get("publication_year", "")),
        "venue": venue,
        "doi": doi,
        "abstract": abstract,
        "keywords": keywords,
    }


def search_openalex(
    query: str,
    *,
    from_year: int = 2016,
    to_year: int | None = None,
    max_results: int | None = None,
    per_page: int = 100,
    email: str | None = None,
    concept_ids: list[str] | None = None,
    use_exact: bool = False,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Search OpenAlex works API.

    Parameters
    ----------
    query : str
        Free-text search query.
    from_year, to_year : int
        Publication year range.
    max_results : int | None
        Maximum records to retrieve. ``None`` means fetch all (no limit).
    email : str | None
        Optional contact email for polite pool (faster rate limits).
    concept_ids : list[str] | None
        OpenAlex concept IDs to add as a filter (OR-combined).
    use_exact : bool
        Use exact matching for unstemmed results (default: stemmed).
    api_key : str | None
        OpenAlex API key. Required since Feb 2026 for meaningful usage.
        Get a free key at https://openalex.org/settings/api
    """
    import os

    if to_year is None:
        to_year = date.today().year

    oa_key = api_key or os.environ.get("OPENALEX_API_KEY", "")
    if not oa_key:
        log.warning(
            "No OpenAlex API key found. Rate limits will be very restrictive "
            "(100 credits/day). Get a free key at https://openalex.org/settings/api"
        )

    oa_q = build_openalex_query(query, concept_ids=concept_ids, use_exact=use_exact)

    # Build filter string: title_and_abstract search + year + optional concepts
    filter_parts = [
        f"{oa_q['filter_key']}:{oa_q['filter_value']}",
        f"publication_year:{from_year}-{to_year}",
    ]
    if "extra_filter" in oa_q:
        filter_parts.append(oa_q["extra_filter"])

    params: dict[str, str] = {
        "filter": ",".join(filter_parts),
        "per_page": str(min(per_page, 200)),
        "sort": "relevance_score:desc",
    }
    if email:
        params["mailto"] = email
    if oa_key:
        params["api_key"] = oa_key

    all_records: list[dict[str, Any]] = []
    cursor = "*"
    pages = 0
    warned_safety = False

    while True:
        if max_results is not None and len(all_records) >= max_results:
            break

        params["cursor"] = cursor
        url = f"{_OPENALEX_WORKS}?{urllib.parse.urlencode(params)}"
        log.info("OpenAlex page %d — fetching %s", pages + 1, url[:120] + "...")

        try:
            data = json.loads(_rate_limited_get(url, delay=0.2))
        except Exception as exc:
            log.error("OpenAlex request failed: %s", exc)
            break

        results = data.get("results", [])
        if not results:
            break

        for w in results:
            all_records.append(_openalex_parse_work(w))
            if max_results is not None and len(all_records) >= max_results:
                break

        # Progress counter
        if len(all_records) % 100 < len(results):
            print(f"  openalex: fetched {len(all_records)} records so far...")

        # Safety warning
        if not warned_safety and len(all_records) > _SAFETY_LIMIT:
            log.warning(
                "OpenAlex: %d records fetched — query may be too broad. "
                "Continuing to fetch all results.", len(all_records),
            )
            warned_safety = True

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        pages += 1

    log.info("OpenAlex: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# arXiv  (free, OAI-PMH / Atom API)
# Docs: https://info.arxiv.org/help/api/
# ═══════════════════════════════════════════════════════════════════════════

_ARXIV_API = "http://export.arxiv.org/api/query"
_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _arxiv_parse_entry(entry: ET.Element) -> dict[str, Any]:
    """Convert an arXiv Atom entry to a normalised dict."""
    title = (entry.findtext("atom:title", "", _ARXIV_NS) or "").strip().replace("\n", " ")
    abstract = (entry.findtext("atom:summary", "", _ARXIV_NS) or "").strip().replace("\n", " ")

    authors_els = entry.findall("atom:author/atom:name", _ARXIV_NS)
    authors = "; ".join(a.text.strip() for a in authors_els if a.text)

    published = entry.findtext("atom:published", "", _ARXIV_NS) or ""
    year = published[:4] if len(published) >= 4 else ""

    # DOI link (if present)
    doi = ""
    for link in entry.findall("atom:link", _ARXIV_NS):
        if link.get("title") == "doi":
            doi = (link.get("href", "") or "").replace("https://doi.org/", "")

    # Categories as keywords
    cats = entry.findall("atom:category", _ARXIV_NS)
    keywords = "; ".join(c.get("term", "") for c in cats if c.get("term"))

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": "arXiv",
        "doi": doi,
        "abstract": abstract,
        "keywords": keywords,
    }


def search_arxiv(
    query: str,
    *,
    max_results: int | None = None,
    batch_size: int = 100,
    categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search arXiv API.

    Parameters
    ----------
    query : str
        arXiv search query (supports AND/OR/ANDNOT, field prefixes like ti:, au:, abs:).
    max_results : int | None
        Maximum records to retrieve. ``None`` means fetch all (no limit).
    categories : list[str] | None
        arXiv category filters (e.g. ``["q-fin*", "quant-ph"]``).
    """
    # Apply field-prefix wrapping and category filtering via the query builder
    search_query = build_arxiv_query(query, categories=categories)

    all_records: list[dict[str, Any]] = []
    start = 0
    warned_safety = False

    while True:
        if max_results is not None and start >= max_results:
            break

        n = batch_size
        if max_results is not None:
            n = min(batch_size, max_results - start)

        params = urllib.parse.urlencode({
            "search_query": search_query,
            "start": str(start),
            "max_results": str(n),
            "sortBy": "relevance",
            "sortOrder": "descending",
        })
        url = f"{_ARXIV_API}?{params}"
        log.info("arXiv batch start=%d — fetching", start)

        try:
            xml_bytes = _rate_limited_get(url, delay=3.0, timeout=60)
            root = ET.fromstring(xml_bytes)
        except Exception as exc:
            log.error("arXiv request failed: %s", exc)
            break

        entries = root.findall("atom:entry", _ARXIV_NS)
        if not entries:
            break

        for entry in entries:
            all_records.append(_arxiv_parse_entry(entry))

        # Progress counter
        if len(all_records) % 100 < len(entries):
            print(f"  arxiv: fetched {len(all_records)} records so far...")

        # Safety warning
        if not warned_safety and len(all_records) > _SAFETY_LIMIT:
            log.warning(
                "arXiv: %d records fetched — query may be too broad. "
                "Continuing to fetch all results.", len(all_records),
            )
            warned_safety = True

        if len(entries) < n:
            break  # no more results
        start += n

    if len(all_records) >= 50000:
        msg = (
            "arXiv: hit the ~50,000 record hard limit. Results may be incomplete. "
            "Consider splitting by date range using submittedDate, or adding "
            "category restrictions via --arxiv-categories to narrow results."
        )
        log.warning(msg)
        print(f"  WARNING: {msg}")

    log.info("arXiv: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Semantic Scholar  (free tier, 100 requests / 5 min)
# Docs: https://api.semanticscholar.org/
# ═══════════════════════════════════════════════════════════════════════════

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_BULK_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"


def _convert_to_s2_bulk_syntax(query: str) -> str:
    """Convert standard Boolean query to S2 bulk search syntax.

    The bulk endpoint uses ``+`` for AND, ``|`` for OR, ``-`` for NOT,
    instead of the English words.
    """
    result = query
    result = re.sub(r'\bAND\b', '+', result)
    result = re.sub(r'\bOR\b', '|', result)
    result = re.sub(r'\bNOT\b', '-', result)
    return result


def _s2_fetch_with_backoff(url: str, *, max_retries: int = 5) -> dict:
    """Fetch from Semantic Scholar with exponential backoff on 429."""
    for attempt in range(max_retries):
        try:
            return json.loads(_rate_limited_get(url, delay=3.5, timeout=30))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = min(60 * (2 ** attempt), 600)  # 60s, 120s, 240s, 480s, 600s
                log.warning(
                    "Semantic Scholar rate limit (429) — attempt %d/%d, "
                    "waiting %ds before retry",
                    attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Semantic Scholar: still rate-limited after {max_retries} retries")


def _s2_parse_paper(p: dict) -> dict[str, Any]:
    """Convert a Semantic Scholar paper object to a normalised record dict."""
    ext_ids = p.get("externalIds") or {}
    doi = ext_ids.get("DOI", "") or ""
    authors_list = p.get("authors") or []
    authors = "; ".join(a.get("name", "") for a in authors_list)
    fos = p.get("s2FieldsOfStudy") or []
    keywords = "; ".join(f.get("category", "") for f in fos)

    return {
        "title": p.get("title", "") or "",
        "authors": authors,
        "year": str(p.get("year", "") or ""),
        "venue": p.get("venue", "") or "",
        "doi": doi,
        "abstract": p.get("abstract", "") or "",
        "keywords": keywords,
    }


def _s2_search_relevance(
    query: str,
    *,
    from_year: int,
    to_year: int,
    max_results: int,
    s2_key: str,
) -> list[dict[str, Any]]:
    """Fetch from S2 relevance endpoint (capped at 1,000 results)."""
    fields = "title,authors,year,venue,externalIds,abstract,s2FieldsOfStudy"
    all_records: list[dict[str, Any]] = []
    offset = 0
    batch_size = 100

    while offset < max_results:
        n = min(batch_size, max_results - offset)
        params = urllib.parse.urlencode({
            "query": query,
            "offset": str(offset),
            "limit": str(n),
            "fields": fields,
            "year": f"{from_year}-{to_year}",
        })
        url = f"{_S2_SEARCH}?{params}"
        log.info("Semantic Scholar (relevance) offset=%d — fetching", offset)

        try:
            if s2_key:
                req = urllib.request.Request(url, headers={
                    "x-api-key": s2_key,
                    "Accept": "application/json",
                })
                time.sleep(1.0)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
            else:
                data = _s2_fetch_with_backoff(url)
        except Exception as exc:
            log.error("Semantic Scholar request failed: %s", exc)
            break

        papers = data.get("data", [])
        if not papers:
            break

        for p in papers:
            all_records.append(_s2_parse_paper(p))

        if len(all_records) % 100 < len(papers):
            print(f"  semantic_scholar: fetched {len(all_records)} records so far...")

        total = data.get("total", 0)
        offset += n
        log.info("Semantic Scholar: %d / %d (total available: %d)", len(all_records), max_results, total)
        if offset >= total:
            break

    return all_records


def _s2_search_bulk(
    query: str,
    *,
    from_year: int,
    to_year: int,
    max_results: int | None,
    s2_key: str,
) -> list[dict[str, Any]]:
    """Fetch from S2 bulk endpoint (supports >1,000 results via token pagination)."""
    fields = "title,authors,year,venue,externalIds,abstract,s2FieldsOfStudy"
    bulk_query = _convert_to_s2_bulk_syntax(query)
    all_records: list[dict[str, Any]] = []
    warned_safety = False

    base_params = urllib.parse.urlencode({
        "query": bulk_query,
        "fields": fields,
        "year": f"{from_year}-{to_year}",
    })
    token: str | None = None

    while True:
        if max_results is not None and len(all_records) >= max_results:
            break

        url = f"{_S2_BULK_SEARCH}?{base_params}"
        if token:
            url += f"&token={urllib.parse.quote(token, safe='')}"
        log.info("Semantic Scholar (bulk) fetching — %d records so far", len(all_records))

        try:
            if s2_key:
                req = urllib.request.Request(url, headers={
                    "x-api-key": s2_key,
                    "Accept": "application/json",
                })
                time.sleep(1.0)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
            else:
                data = _s2_fetch_with_backoff(url)
        except Exception as exc:
            log.error("Semantic Scholar bulk request failed: %s", exc)
            break

        papers = data.get("data", [])
        if not papers:
            break

        for p in papers:
            all_records.append(_s2_parse_paper(p))
            if max_results is not None and len(all_records) >= max_results:
                break

        if len(all_records) % 100 < len(papers):
            print(f"  semantic_scholar: fetched {len(all_records)} records so far...")

        if not warned_safety and len(all_records) > _SAFETY_LIMIT:
            log.warning(
                "Semantic Scholar: %d records fetched — query may be too broad. "
                "Continuing to fetch all results.", len(all_records),
            )
            warned_safety = True

        token = data.get("token")
        if not token:
            break

    return all_records


def search_semantic_scholar(
    query: str,
    *,
    from_year: int = 2016,
    to_year: int | None = None,
    max_results: int | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Search Semantic Scholar paper search API.

    Uses the relevance endpoint for small result sets (max_results <= 1000)
    and the bulk endpoint for larger or uncapped fetches, since the relevance
    endpoint has a hard cap of 1,000 results.

    Parameters
    ----------
    query : str
        Free-text search query.
    from_year, to_year : int
        Publication year range filter.
    max_results : int | None
        Maximum records to retrieve. ``None`` means fetch all (no limit).
    api_key : str | None
        Optional S2 API key for higher rate limits.
        Get one free at https://www.semanticscholar.org/product/api#api-key
    """
    if to_year is None:
        to_year = date.today().year

    import os
    s2_key = api_key or os.environ.get("S2_API_KEY", "")

    # Relevance endpoint caps at 1,000 total results.
    # Use it only when max_results is explicitly set and <= 1000.
    use_relevance = max_results is not None and max_results <= 1000

    if use_relevance:
        all_records = _s2_search_relevance(
            query,
            from_year=from_year,
            to_year=to_year,
            max_results=max_results,
            s2_key=s2_key,
        )
    else:
        all_records = _s2_search_bulk(
            query,
            from_year=from_year,
            to_year=to_year,
            max_results=max_results,
            s2_key=s2_key,
        )

    log.info("Semantic Scholar: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Scopus stub  (requires pybliometrics + API key)
# ═══════════════════════════════════════════════════════════════════════════

def search_scopus(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int | None = None,
    from_year: int = 2016,
) -> list[dict[str, Any]]:
    """Search Scopus via Elsevier REST API.

    Uses the raw REST API for maximum compatibility with free-tier keys.
    Set api_key or configure ~/.config/pybliometrics/pybliometrics.cfg.

    The query is auto-wrapped in ``TITLE-ABS-KEY()`` with a ``PUBYEAR``
    filter unless it already contains Scopus field syntax.
    """
    import os

    query = build_scopus_query(query, from_year=from_year)

    # Resolve API key: explicit > env > pybliometrics config
    key = api_key or os.environ.get("SCOPUS_API_KEY", "")
    if not key:
        try:
            import configparser
            cfg = configparser.ConfigParser()
            cfg_path = Path.home() / ".config" / "pybliometrics.cfg"
            if cfg_path.exists():
                cfg.read(cfg_path)
                key = cfg.get("Authentication", "APIKey", fallback="").split(",")[0].strip()
        except Exception:
            pass

    if not key:
        log.error(
            "Scopus API key not found. Set SCOPUS_API_KEY env var, "
            "pass --api-key, or configure ~/.config/pybliometrics.cfg"
        )
        return []

    base_url = "https://api.elsevier.com/content/search/scopus"
    all_records: list[dict[str, Any]] = []
    start = 0
    count = 25  # Scopus max per page
    total = 0
    warned_safety = False

    while True:
        if max_results is not None and start >= max_results:
            break

        page_count = count
        if max_results is not None:
            page_count = min(count, max_results - start)

        params = urllib.parse.urlencode({
            "query": query,
            "start": str(start),
            "count": str(page_count),
        })
        url = f"{base_url}?{params}"
        req = urllib.request.Request(url, headers={
            "X-ELS-APIKey": key,
            "Accept": "application/json",
        })

        try:
            time.sleep(0.5)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            log.error("Scopus request failed at start=%d: %s", start, exc)
            break

        results = data.get("search-results", {})
        total = int(results.get("opensearch:totalResults", 0))
        entries = results.get("entry", [])

        if not entries:
            break

        # Check for error entry
        if len(entries) == 1 and entries[0].get("error"):
            log.error("Scopus API error: %s", entries[0]["error"])
            break

        for e in entries:
            all_records.append({
                "title": e.get("dc:title", "") or "",
                "authors": e.get("dc:creator", "") or "",
                "year": (e.get("prism:coverDate", "") or "")[:4],
                "venue": e.get("prism:publicationName", "") or "",
                "doi": e.get("prism:doi", "") or "",
                "abstract": "",  # abstracts not in search results; need AbstractRetrieval
                "keywords": e.get("authkeywords", "") or "",
            })

            if max_results is not None and len(all_records) >= max_results:
                break

        # Progress counter
        if len(all_records) % 100 < len(entries):
            print(f"  scopus: fetched {len(all_records)} records so far...")

        # Safety warning
        if not warned_safety and len(all_records) > _SAFETY_LIMIT:
            log.warning(
                "Scopus: %d records fetched — query may be too broad. "
                "Continuing to fetch all results.", len(all_records),
            )
            warned_safety = True

        cap_str = str(max_results) if max_results is not None else "all"
        log.info("Scopus: fetched %d / %s (total available: %d)", len(all_records), cap_str, total)

        if start + count >= total:
            break
        start += count

    # Scopus web export caps at 20,000 records; API pagination handles more,
    # but warn so the user can cross-check against the web interface.
    if total > 20000:
        log.info(
            "Scopus: %d total results. Note: Scopus web export is limited to "
            "20,000 records. API pagination handles this, but verify completeness "
            "against the web interface count.", total,
        )

    log.info("Scopus: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Web of Science stub  (requires clarivate API key)
# ═══════════════════════════════════════════════════════════════════════════

def search_wos(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """Search Web of Science Starter API (requires API key).

    Apply for a key at: https://developer.clarivate.com/
    Set env var WOS_API_KEY or pass api_key.
    """
    import os
    key = api_key or os.environ.get("WOS_API_KEY", "")
    if not key:
        log.error(
            "WoS API key not found. Set WOS_API_KEY env var or pass --api-key.\n"
            "Apply at: https://developer.clarivate.com/"
        )
        return []

    url = "https://api.clarivate.com/apis/wos-starter/v1/documents"
    all_records: list[dict[str, Any]] = []
    page = 1
    limit = 50
    if max_results is not None:
        limit = min(50, max_results)
    warned_safety = False

    while True:
        if max_results is not None and len(all_records) >= max_results:
            break

        params = urllib.parse.urlencode({
            "q": query,
            "db": "WOS",
            "limit": str(limit),
            "page": str(page),
        })
        req_url = f"{url}?{params}"
        req = urllib.request.Request(req_url, headers={
            "X-ApiKey": key,
            "Accept": "application/json",
        })

        try:
            time.sleep(1.0)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            log.error("WoS request failed: %s", exc)
            break

        hits = data.get("hits", [])
        if not hits:
            break

        for h in hits:
            names = h.get("names", {}).get("authors", [])
            authors = "; ".join(
                n.get("displayName", "") for n in names
            ) if isinstance(names, list) else ""

            src = h.get("source", {})

            all_records.append({
                "title": h.get("title", "") or "",
                "authors": authors,
                "year": str(src.get("publishYear", "")),
                "venue": src.get("sourceTitle", "") or "",
                "doi": h.get("identifiers", {}).get("doi", "") or "",
                "abstract": "",  # WoS starter doesn't return abstracts
                "keywords": "; ".join(h.get("keywords", {}).get("authorKeywords", []) or []),
            })

        # Progress counter
        if len(all_records) % 100 < len(hits):
            print(f"  wos: fetched {len(all_records)} records so far...")

        # Safety warning
        if not warned_safety and len(all_records) > _SAFETY_LIMIT:
            log.warning(
                "WoS: %d records fetched — query may be too broad. "
                "Continuing to fetch all results.", len(all_records),
            )
            warned_safety = True

        if len(hits) < limit:
            break
        page += 1

    log.info("WoS: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Unified search dispatcher
# ═══════════════════════════════════════════════════════════════════════════

_SEARCHERS: dict[str, Any] = {
    "openalex": search_openalex,
    "arxiv": search_arxiv,
    "semantic_scholar": search_semantic_scholar,
    "scopus": search_scopus,
    "wos": search_wos,
}


def auto_search(
    query: str,
    *,
    sources: list[str] | None = None,
    from_year: int = 2016,
    max_results: int | None = None,
    run_date: str | None = None,
    email: str | None = None,
    api_key: str | None = None,
    openalex_api_key: str | None = None,
    concept_ids: list[str] | None = None,
    use_exact: bool = False,
    arxiv_categories: list[str] | None = None,
) -> dict[str, Path]:
    """Run automated search across selected APIs and auto-ingest results.

    Parameters
    ----------
    query : str
        Search query (adapted per-source internally).
    sources : list[str]
        API sources to query. Default: ["openalex", "arxiv", "scopus"].
    from_year : int
        Start year filter.
    max_results : int | None
        Max results per source. ``None`` means fetch all (no limit).
    run_date : str
        Date string (YYYY-MM-DD). Default: today.
    email : str
        Contact email for polite rate limits (OpenAlex).
    api_key : str
        API key for Scopus/WoS (if needed).
    openalex_api_key : str | None
        OpenAlex API key (free, required since Feb 2026).
    concept_ids : list[str] | None
        OpenAlex concept IDs to filter by.
    use_exact : bool
        Use OpenAlex exact matching for unstemmed results.
    arxiv_categories : list[str] | None
        arXiv category filters (e.g. ``["q-fin*", "quant-ph"]``).

    Returns
    -------
    dict mapping source name → run folder path
    """

    if sources is None:
        sources = ["openalex", "arxiv", "scopus"]

    if run_date is None:
        run_date = date.today().isoformat()

    created_folders: dict[str, Path] = {}

    for source in sources:
        searcher = _SEARCHERS.get(source)
        if not searcher:
            log.warning("Unknown source: %s — skipping", source)
            continue

        log.info("═" * 60)
        log.info("Searching %s …", source)
        log.info("═" * 60)

        # Build kwargs per searcher
        kwargs: dict[str, Any] = {"max_results": max_results}
        if source in ("openalex", "semantic_scholar", "scopus"):
            kwargs["from_year"] = from_year
        if source == "openalex" and email:
            kwargs["email"] = email
        if source == "openalex" and openalex_api_key:
            kwargs["api_key"] = openalex_api_key
        if source == "openalex" and concept_ids:
            kwargs["concept_ids"] = concept_ids
        if source == "openalex" and use_exact:
            kwargs["use_exact"] = True
        if source == "arxiv" and arxiv_categories:
            kwargs["categories"] = arxiv_categories
        if source in ("scopus", "wos") and api_key:
            kwargs["api_key"] = api_key

        try:
            records = searcher(query, **kwargs)
        except KeyboardInterrupt:
            log.warning("Search interrupted by user for %s", source)
            break
        except Exception as exc:
            log.error("Search failed for %s: %s", source, exc)
            continue

        if not records:
            log.warning("No results from %s", source)
            continue

        # Create run folder
        run_folder = create_search_run(
            source=source,
            run_date=run_date,
            log_search=False,
        )

        # Normalise and write
        df = pd.DataFrame(records)
        for col in config.NORMALIZED_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        df["source_db"] = source
        df["export_file"] = f"api_search_{source}.json"
        df["paper_id"] = df.apply(
            lambda row: generate_paper_id(
                row.get("title"), row.get("authors"), row.get("year")
            ),
            axis=1,
        )
        df["is_preprint"] = df.apply(
            lambda row: "1" if _detect_preprint(
                str(row.get("venue", "")), str(row.get("source_db", ""))
            ) else "0",
            axis=1,
        )
        df["version_group_id"] = ""
        df = df[config.NORMALIZED_COLUMNS].fillna("")

        # Save raw JSON for provenance
        raw_path = run_folder / f"api_search_{source}.json"
        raw_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Write normalized CSV
        out_path = run_folder / "normalized_records.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")

        log.info(
            "%s: %d records -> %s", source, len(df), out_path,
        )
        print(f"  [ok] {source}: {len(df)} records ingested")

        # Auto-log exact query to search_log.xlsx (PRISMA-S compliance)
        _log_search_to_xlsx(
            source=source,
            query=query,
            run_date=run_date,
            results_n=len(df),
            notes=f"API version: {_INTERFACE_MAP.get(source, source)}; "
                  f"max_results={max_results if max_results is not None else 'all'}",
        )

        created_folders[source] = run_folder

    return created_folders
