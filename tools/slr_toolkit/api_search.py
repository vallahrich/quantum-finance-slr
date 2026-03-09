"""Automated API search — OpenAlex, arXiv, Semantic Scholar, Scopus/WoS stubs.

Each searcher returns a list of dicts with normalised column names.
Results are auto-ingested into the pipeline (normalized_records.csv).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any

from . import config
from .ingest import _detect_preprint
from .search_run import create_search_run
from .utils import ensure_dir, generate_paper_id

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
# OpenAlex  (fully free, no auth)
# Docs: https://docs.openalex.org
# ═══════════════════════════════════════════════════════════════════════════

_OPENALEX_WORKS = "https://api.openalex.org/works"


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
    max_results: int = 500,
    per_page: int = 100,
    email: str | None = None,
) -> list[dict[str, Any]]:
    """Search OpenAlex works API.

    Parameters
    ----------
    query : str
        Free-text search query.
    from_year, to_year : int
        Publication year range.
    max_results : int
        Maximum records to retrieve (across pages).
    email : str | None
        Optional contact email for polite pool (faster rate limits).
    """
    if to_year is None:
        to_year = date.today().year

    params: dict[str, str] = {
        "search": query,
        "filter": f"publication_year:{from_year}-{to_year}",
        "per_page": str(min(per_page, 200)),
        "sort": "relevance_score:desc",
    }
    if email:
        params["mailto"] = email

    all_records: list[dict[str, Any]] = []
    cursor = "*"
    pages = 0

    while len(all_records) < max_results:
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
            if len(all_records) >= max_results:
                break

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
    max_results: int = 500,
    batch_size: int = 100,
) -> list[dict[str, Any]]:
    """Search arXiv API.

    Parameters
    ----------
    query : str
        arXiv search query (supports AND/OR/ANDNOT, field prefixes like ti:, au:, abs:).
    max_results : int
        Maximum records to retrieve.
    """
    all_records: list[dict[str, Any]] = []
    start = 0

    while start < max_results:
        n = min(batch_size, max_results - start)
        params = urllib.parse.urlencode({
            "search_query": query,
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

        if len(entries) < n:
            break  # no more results
        start += n

    log.info("arXiv: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Semantic Scholar  (free tier, 100 requests / 5 min)
# Docs: https://api.semanticscholar.org/
# ═══════════════════════════════════════════════════════════════════════════

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


def search_semantic_scholar(
    query: str,
    *,
    from_year: int = 2016,
    to_year: int | None = None,
    max_results: int = 500,
) -> list[dict[str, Any]]:
    """Search Semantic Scholar paper search API.

    Parameters
    ----------
    query : str
        Free-text search query.
    from_year, to_year : int
        Publication year range filter.
    max_results : int
        Maximum records to retrieve.
    """
    if to_year is None:
        to_year = date.today().year

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
        log.info("Semantic Scholar offset=%d — fetching", offset)

        try:
            data = json.loads(_rate_limited_get(url, delay=3.5, timeout=30))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = 300  # 5 minutes — S2 rate window
                log.warning("Semantic Scholar rate limit hit — waiting %ds", wait)
                time.sleep(wait)
                try:
                    data = json.loads(_rate_limited_get(url, delay=1.0, timeout=30))
                except Exception as exc2:
                    log.error("Semantic Scholar retry failed: %s", exc2)
                    break
            else:
                log.error("Semantic Scholar request failed: %s", exc)
                break
        except Exception as exc:
            log.error("Semantic Scholar request failed: %s", exc)
            break

        papers = data.get("data", [])
        if not papers:
            break

        for p in papers:
            ext_ids = p.get("externalIds") or {}
            doi = ext_ids.get("DOI", "") or ""
            authors_list = p.get("authors") or []
            authors = "; ".join(a.get("name", "") for a in authors_list)
            fos = p.get("s2FieldsOfStudy") or []
            keywords = "; ".join(f.get("category", "") for f in fos)

            all_records.append({
                "title": p.get("title", "") or "",
                "authors": authors,
                "year": str(p.get("year", "") or ""),
                "venue": p.get("venue", "") or "",
                "doi": doi,
                "abstract": p.get("abstract", "") or "",
                "keywords": keywords,
            })

        total = data.get("total", 0)
        offset += n
        if offset >= total:
            break

    log.info("Semantic Scholar: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Scopus stub  (requires pybliometrics + API key)
# ═══════════════════════════════════════════════════════════════════════════

def search_scopus(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 500,
) -> list[dict[str, Any]]:
    """Search Scopus via Elsevier REST API.

    Uses the raw REST API for maximum compatibility with free-tier keys.
    Set api_key or configure ~/.config/pybliometrics/pybliometrics.cfg.
    """
    import os

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

    while start < max_results:
        params = urllib.parse.urlencode({
            "query": query,
            "start": str(start),
            "count": str(min(count, max_results - start)),
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

            if len(all_records) >= max_results:
                break

        log.info("Scopus: fetched %d / %d (total available: %d)", len(all_records), max_results, total)

        if start + count >= total:
            break
        start += count

    log.info("Scopus: retrieved %d records", len(all_records))
    return all_records


# ═══════════════════════════════════════════════════════════════════════════
# Web of Science stub  (requires clarivate API key)
# ═══════════════════════════════════════════════════════════════════════════

def search_wos(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 500,
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
    limit = min(50, max_results)

    while len(all_records) < max_results:
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
    max_results: int = 500,
    run_date: str | None = None,
    email: str | None = None,
    api_key: str | None = None,
) -> dict[str, Path]:
    """Run automated search across selected APIs and auto-ingest results.

    Parameters
    ----------
    query : str
        Search query (adapted per-source internally).
    sources : list[str]
        API sources to query. Default: ["openalex", "arxiv", "semantic_scholar"].
    from_year : int
        Start year filter.
    max_results : int
        Max results per source.
    run_date : str
        Date string (YYYY-MM-DD). Default: today.
    email : str
        Contact email for polite rate limits (OpenAlex).
    api_key : str
        API key for Scopus/WoS (if needed).

    Returns
    -------
    dict mapping source name → run folder path
    """
    import pandas as pd

    if sources is None:
        sources = ["openalex", "arxiv", "semantic_scholar"]

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
        if source in ("openalex", "semantic_scholar"):
            kwargs["from_year"] = from_year
        if source == "openalex" and email:
            kwargs["email"] = email
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
        run_folder = create_search_run(source=source, run_date=run_date)

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
            "%s: %d records → %s", source, len(df), out_path,
        )
        print(f"  ✓ {source}: {len(df)} records ingested")

        created_folders[source] = run_folder

    return created_folders
