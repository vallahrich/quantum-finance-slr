"""Download PDFs via institutional proxy access using Playwright.

Two-stage workflow
------------------
1. **Open-access stage** — handled by :mod:`pdf_download` (7-source cascade).
2. **Institutional stage** — this module.  For every paper that still lacks a
   PDF after stage 1, construct a proxied URL via the configured institution
   (default: CBS / Copenhagen Business School) and attempt browser-based
   retrieval.

Session persistence
-------------------
Playwright's ``storage_state`` is saved after a successful login so that
subsequent runs reuse cookies/sessions without requiring a fresh login.
The state file lives under ``<repo>/.auth/`` (configurable via
:pydata:`config.AUTH_STATE_DIR`).

Adding new institutions
-----------------------
1. Create a new :class:`InstitutionProfile` instance (see ``CBS_PROFILE``).
2. Register it in the ``INSTITUTIONS`` dict.
3. Use ``--institution <key>`` on the CLI.

Requires: ``pip install playwright && playwright install chromium``
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config
from .utils import atomic_write_text, ensure_dir

log = logging.getLogger("slr_toolkit.institutional_download")

_MAX_FILENAME_LEN = 80


# ── Filename helper ───────────────────────────────────────────────────────

def _sanitise_filename(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = t.strip("_")
    return t[:_MAX_FILENAME_LEN]


# ── Download log I/O (shared format with pdf_download.py) ────────────────

_LOG_COLUMNS = [
    "paper_id", "title", "doi", "source", "pdf_url",
    "status", "filename", "timestamp",
]


def _csv_escape(val: str) -> str:
    if any(c in val for c in (",", '"', "\n")):
        return '"' + val.replace('"', '""') + '"'
    return val


def _load_download_log(log_path: Path) -> dict[str, dict]:
    if not log_path.exists():
        return {}
    with open(log_path, encoding="utf-8", newline="") as f:
        return {row["paper_id"]: row for row in csv.DictReader(f)}


def _save_download_log(log_path: Path, entries: dict[str, dict]) -> None:
    lines = [",".join(_LOG_COLUMNS)]
    for pid in sorted(entries):
        row = entries[pid]
        vals = [_csv_escape(str(row.get(c, ""))) for c in _LOG_COLUMNS]
        lines.append(",".join(vals))
    atomic_write_text(log_path, "\n".join(lines) + "\n")


# ── Institution profiles ─────────────────────────────────────────────────

@dataclass
class InstitutionProfile:
    """Configuration for one institutional proxy."""

    key: str
    name: str
    # Pattern: ``login_url_base + <target_url>`` — the ``login?url=`` style.
    login_url_base: str
    # Pattern: ``doi_proxy_base + "/" + <doi>`` — DOI-rewriting proxy.
    doi_proxy_base: str
    # Path (relative to AUTH_STATE_DIR) for persisted browser state.
    session_state_filename: str
    # Strings that indicate we've landed on a login / auth page.
    login_page_signals: list[str] = field(default_factory=lambda: [
        "login", "auth", "sso", "idp", "saml", "shibboleth",
    ])
    # Max seconds to wait for the user to complete interactive login.
    login_timeout_s: int = 120

    @property
    def session_state_path(self) -> Path:
        return config.AUTH_STATE_DIR / self.session_state_filename


CBS_PROFILE = InstitutionProfile(
    key="cbs",
    name="Copenhagen Business School",
    login_url_base="http://esc-web.lib.cbs.dk/login?url=",
    doi_proxy_base="https://www-doi-org.esc-web.lib.cbs.dk",
    session_state_filename="cbs_proxy_session.json",
    login_page_signals=["login", "auth", "sso", "idp", "saml",
                        "shibboleth", "wayf.dk"],
    login_timeout_s=300,
)

INSTITUTIONS: dict[str, InstitutionProfile] = {
    "cbs": CBS_PROFILE,
}

# DOI prefixes for publishers whose proxy + direct-PDF workflow is known to work.
# Used by ``--working-only`` to skip publishers that consistently fail.
WORKING_DOI_PREFIXES: set[str] = {
    "10.1109",   # IEEE Xplore
    "10.1007",   # Springer
    "10.1140",   # Springer (EPJ)
    "10.1002",   # Wiley
    "10.1049",   # IET (Wiley)
    "10.1145",   # ACM Digital Library
    "10.1016",   # Elsevier / ScienceDirect
    "10.3905",   # PM Research (Institutional Investor / Wiley)
}


def _doi_has_working_prefix(doi: str) -> bool:
    """Return True if *doi* starts with a prefix in :data:`WORKING_DOI_PREFIXES`."""
    prefix = doi.split("/", 1)[0] if "/" in doi else ""
    return prefix in WORKING_DOI_PREFIXES


def get_institution(key: str) -> InstitutionProfile:
    """Return the :class:`InstitutionProfile` for *key*, or raise."""
    try:
        return INSTITUTIONS[key.lower()]
    except KeyError:
        available = ", ".join(sorted(INSTITUTIONS))
        raise ValueError(
            f"Unknown institution '{key}'. Available: {available}"
        ) from None


# ── Proxy URL builders ────────────────────────────────────────────────────

def build_proxy_url(target_url: str, profile: InstitutionProfile) -> str:
    """Construct a proxied URL using the institution's ``login?url=`` base.

    >>> build_proxy_url("https://doi.org/10.1007/s123", CBS_PROFILE)
    'http://esc-web.lib.cbs.dk/login?url=https://doi.org/10.1007/s123'
    """
    return f"{profile.login_url_base}{target_url}"


def build_cbs_proxy_url(target_url: str) -> str:
    """Convenience wrapper — build a CBS-proxied URL.

    >>> build_cbs_proxy_url("https://doi.org/10.1007/s123")
    'http://esc-web.lib.cbs.dk/login?url=https://doi.org/10.1007/s123'
    """
    return build_proxy_url(target_url, CBS_PROFILE)


def build_doi_proxy_url(doi: str, profile: InstitutionProfile) -> str:
    """Construct a DOI-rewriting proxy URL.

    >>> build_doi_proxy_url("10.1007/s123", CBS_PROFILE)
    'https://www-doi-org.esc-web.lib.cbs.dk/10.1007/s123'
    """
    return f"{profile.doi_proxy_base.rstrip('/')}/{doi}"


# ── Publisher-specific PDF extraction ────────────────────────────────────

def _find_pdf_link_ieee(page: Any) -> str | None:
    """Find PDF download link on IEEE Xplore."""
    try:
        btn = page.locator("a.pdf-btn-link, a[href*='stamp.jsp']").first
        if btn.count():
            href = btn.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://ieeexplore.ieee.org{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_springer(page: Any) -> str | None:
    """Find PDF link on Springer/Nature."""
    try:
        link = page.locator("a[data-article-pdf], a[href*='/content/pdf/']").first
        if link.count():
            href = link.get_attribute("href")
            if href:
                base = page.url.split("/")[0] + "//" + page.url.split("/")[2]
                return href if href.startswith("http") else f"{base}{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_elsevier(page: Any) -> str | None:
    """Find PDF link on ScienceDirect (Elsevier)."""
    try:
        link = page.locator("a.pdf-download, a[href*='pdfft']").first
        if link.count():
            href = link.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://www.sciencedirect.com{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_wiley(page: Any) -> str | None:
    """Find PDF link on Wiley Online Library.

    Prefers ``/doi/pdfdirect/`` > ``/doi/pdf/`` > ``/doi/epdf/``.
    The ``epdf`` variant is an embedded viewer, not a direct download.
    """
    try:
        # Priority order: pdfdirect > pdf > epdf
        for selector in [
            "a[href*='/doi/pdfdirect/']",
            "a[href*='/doi/pdf/']",
            "a:has-text('Download PDF')",
            "a[href*='/doi/epdf/']",
        ]:
            link = page.locator(selector).first
            if link.count():
                href = link.get_attribute("href")
                if href:
                    # Convert epdf to pdf for direct download
                    if "/doi/epdf/" in href:
                        href = href.replace("/doi/epdf/", "/doi/pdf/")
                    base = page.url.split("/")[0] + "//" + page.url.split("/")[2]
                    return href if href.startswith("http") else f"{base}{href}"
    except Exception:
        pass
    return None


def _find_pdf_link_generic(page: Any) -> str | None:
    """Generic fallback: look for any PDF link on the page."""
    try:
        for selector in [
            "a[href$='.pdf']",
            "a[href*='pdf']",
            "a:has-text('Download PDF')",
            "a:has-text('Full Text PDF')",
            "a:has-text('View PDF')",
        ]:
            link = page.locator(selector).first
            if link.count():
                href = link.get_attribute("href")
                if href:
                    base = page.url.split("/")[0] + "//" + page.url.split("/")[2]
                    return href if href.startswith("http") else f"{base}{href}"
    except Exception:
        pass
    return None


_PUBLISHER_HANDLERS = [
    ("ieeexplore.ieee.org", _find_pdf_link_ieee),
    ("link.springer.com", _find_pdf_link_springer),
    ("nature.com", _find_pdf_link_springer),
    ("sciencedirect.com", _find_pdf_link_elsevier),
    ("onlinelibrary.wiley.com", _find_pdf_link_wiley),
]


def _find_pdf_on_page(page: Any) -> str | None:
    """Try publisher-specific handlers then generic fallback."""
    current_url = page.url.lower()
    for domain, handler in _PUBLISHER_HANDLERS:
        if domain in current_url:
            result = handler(page)
            if result:
                return result
    return _find_pdf_link_generic(page)


# ── Login / auth detection ────────────────────────────────────────────────

# Domains that are SSO / identity providers — NOT publisher sites.
_SSO_DOMAINS = [
    "login.microsoftonline.com",
    "adfs.", "fs.", "idp.",
    "wayf.dk",
    "shibboleth",
    "login.cbs.dk",
    "esc-web.lib.cbs.dk/login",
]


def _looks_like_login_page(page: Any, profile: InstitutionProfile) -> bool:
    """Heuristic check: does the current page look like an auth/login wall?

    Only returns True when the URL belongs to a known SSO/identity-provider
    domain **and** the page contains login form elements.  Publisher pages
    (IEEE, Wiley, Springer …) are never treated as login pages even if they
    contain ``<input type="submit">``.
    """
    try:
        url_lower = page.url.lower()

        # Must be on an SSO domain, not a publisher page
        on_sso_domain = any(d in url_lower for d in _SSO_DOMAINS)
        if not on_sso_domain:
            return False

        # Strongest signal: a visible password input
        if page.locator("input[type='password']").count():
            return True
        # Username/email input
        if page.locator("input[type='email'], input[name='loginfmt'], "
                        "input[name='login'], input[name='username']").count():
            return True
    except Exception:
        pass
    return False


def _looks_like_paywall(page: Any) -> bool:
    """Heuristic check: does the page look like a paywall / access-denied?"""
    try:
        text = page.inner_text("body")[:3000].lower()
        paywall_signals = [
            "buy this article",
            "purchase this article",
            "rent this article",
            "subscribe to",
            "access denied",
            "institutional access",
            "sign in to access",
            "full text is not available",
            "you do not currently have access",
        ]
        return any(s in text for s in paywall_signals)
    except Exception:
        return False


# ── Session management ────────────────────────────────────────────────────

class SessionManager:
    """Manage Playwright browser context with persistent session state.

    Saves and loads cookies / localStorage so that institutional SSO
    sessions survive across runs.
    """

    def __init__(self, profile: InstitutionProfile):
        self.profile = profile
        self._state_path = profile.session_state_path

    @property
    def has_saved_session(self) -> bool:
        return self._state_path.exists()

    def load_state_kwargs(self) -> dict:
        """Return kwargs for ``browser.new_context(...)`` to restore session."""
        if self.has_saved_session:
            log.info("Loading saved session from %s", self._state_path.name)
            return {"storage_state": str(self._state_path)}
        return {}

    def save_state(self, context: Any) -> None:
        """Persist the current browser context's storage state."""
        ensure_dir(self._state_path.parent)
        state = context.storage_state()
        self._state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("Session state saved to %s", self._state_path.name)

    def clear(self) -> None:
        """Delete the saved session (force re-login next time)."""
        if self._state_path.exists():
            self._state_path.unlink()
            log.info("Session state cleared: %s", self._state_path.name)


def _handle_login_if_needed(
    page: Any,
    context: Any,
    profile: InstitutionProfile,
    session_mgr: SessionManager,
    *,
    already_prompted: bool = False,
) -> bool:
    """Detect login page and wait for user to authenticate interactively.

    Returns True if login was performed (or already authenticated).
    """
    if not _looks_like_login_page(page, profile):
        return False

    if already_prompted:
        # We already asked the user to log in once this session — if we're
        # still on a login page, the session might have expired mid-run.
        log.warning("Login page detected again — session may have expired.")

    print(flush=True)
    print(f"  *** {profile.name} login required — opening browser ***", flush=True)
    print(f"  URL: {page.url}", flush=True)
    print(f"  Please log in manually in the browser window.", flush=True)
    print(f"  Waiting up to {profile.login_timeout_s}s for authentication...", flush=True)
    print(flush=True)

    try:
        # Wait for the URL to change away from the login page.
        # We poll rather than using wait_for_url with a single pattern,
        # because the post-login destination is unpredictable.
        deadline = time.time() + profile.login_timeout_s
        while time.time() < deadline:
            if not _looks_like_login_page(page, profile):
                break
            time.sleep(2)
        else:
            print("  *** Login timeout — continuing anyway ***")
            return False

        print("  Login completed — continuing downloads")
        # Save session state for reuse
        session_mgr.save_state(context)
        return True

    except Exception as exc:
        log.warning("Error waiting for login: %s", exc)
        return False


# ── Hybrid download: browser auth + requests-based PDF fetch ──────────────

import requests as _requests
import urllib3 as _urllib3

_urllib3.disable_warnings(_urllib3.exceptions.InsecureRequestWarning)


def _build_requests_session(context: Any) -> "_requests.Session":
    """Create a :class:`requests.Session` pre-loaded with browser cookies."""
    session = _requests.Session()
    for c in context.cookies():
        session.cookies.set(
            c["name"], c["value"],
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
        )
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return session


def _resolve_direct_pdf_url(page_url: str, doi: str) -> str | None:
    """Derive the most likely direct-download PDF URL from the publisher page.

    Many publishers have predictable URL patterns for direct PDF access
    that work with ``requests`` once cookies are present.
    """
    url_lower = page_url.lower()

    # IEEE Xplore: /document/{arnumber} -> /stampPDF/getPDF.jsp?arnumber={arnumber}
    m = re.search(r"ieee[^/]*/document/(\d+)", url_lower)
    if m:
        base = page_url.split("/document/")[0]
        return f"{base}/stampPDF/getPDF.jsp?tp=&arnumber={m.group(1)}&ref="

    # Wiley: /doi/{type}/{doi} -> /doi/pdfdirect/{doi}
    if "wiley" in url_lower and "/doi/" in url_lower:
        base = page_url.split("/doi/")[0]
        return f"{base}/doi/pdfdirect/{doi}"

    # Springer / Nature: article page -> /content/pdf/{doi}.pdf
    if ("springer" in url_lower or "nature.com" in url_lower) and doi:
        base = page_url.split("/article/")[0] if "/article/" in url_lower else page_url.rsplit("/", 1)[0]
        return f"{base}/content/pdf/{doi}.pdf"

    # Elsevier / ScienceDirect: /science/article/pii/{id} -> PDF via pdfft
    if "sciencedirect" in url_lower:
        m_pii = re.search(r"/pii/(\w+)", url_lower)
        if m_pii:
            base = page_url.split("/science/")[0]
            return f"{base}/science/article/pii/{m_pii.group(1)}/pdfft"

    return None


def _download_pdf_with_session(
    session: "_requests.Session",
    url: str,
    dest: Path,
    *,
    referer: str = "",
) -> bool:
    """Download a PDF using requests session with browser cookies.

    Returns True if a valid PDF was saved to *dest*.
    """
    headers: dict[str, str] = {"Accept": "application/pdf, */*"}
    if referer:
        headers["Referer"] = referer
    try:
        resp = session.get(
            url, headers=headers, verify=False,
            allow_redirects=True, timeout=60,
        )
        if resp.ok and resp.content[:5].startswith(b"%PDF") and len(resp.content) > 5000:
            ensure_dir(dest.parent)
            dest.write_bytes(resp.content)
            log.info("  Downloaded PDF: %s (%d bytes)", dest.name, len(resp.content))
            return True
        log.debug("  Download from %s: status=%s, size=%d, pdf=%s",
                  url[:60], resp.status_code, len(resp.content),
                  resp.content[:5].startswith(b"%PDF"))
    except _requests.RequestException as exc:
        log.debug("  requests download failed: %s", exc)
    return False


# ── Core download logic ───────────────────────────────────────────────────

def _attempt_institutional_download_for_paper(
    page: Any,
    context: Any,
    paper: dict,
    profile: InstitutionProfile,
    pdf_dir: Path,
    *,
    skip_initial_navigate: bool = False,
) -> tuple[bool, str, str]:
    """Try to download a single paper via institutional proxy.

    Strategy:
    1. Navigate browser to proxied DOI to land on authenticated publisher page.
    2. Derive the direct PDF URL from the publisher-specific URL pattern.
    3. Download the PDF via ``requests`` using browser cookies.
    4. If that fails, fall back to the link found by ``_find_pdf_on_page``.

    Returns (success, pdf_url_or_proxy_url, pdf_filename_or_empty).
    """
    pid = paper["paper_id"]
    doi = paper.get("doi", "").strip()
    title = paper.get("title", "") or pid

    if doi:
        target_url = f"https://doi.org/{doi}"
        proxy_url = build_proxy_url(target_url, profile)
    else:
        return False, "", ""

    pdf_filename = f"{pid}_{_sanitise_filename(title)}.pdf"
    dest = pdf_dir / pdf_filename

    try:
        if not skip_initial_navigate:
            page.goto(proxy_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)

        publisher_url = page.url
        log.info("  Publisher page: %s", publisher_url[:100])

        # Check for paywall
        if _looks_like_paywall(page):
            log.info("  Paywall detected for %s", pid)
            return False, proxy_url, ""

        # Build a requests session with browser cookies
        session = _build_requests_session(context)

        # Strategy 1: derive direct PDF URL from publisher pattern
        direct_url = _resolve_direct_pdf_url(publisher_url, doi)
        if direct_url:
            log.info("  Direct PDF URL: %s", direct_url[:100])
            if _download_pdf_with_session(session, direct_url, dest, referer=publisher_url):
                return True, direct_url, pdf_filename

        # Strategy 2: use the PDF link found on the page
        pdf_link = _find_pdf_on_page(page)
        if pdf_link:
            log.info("  Page PDF link: %s", pdf_link[:100])
            if _download_pdf_with_session(session, pdf_link, dest, referer=publisher_url):
                return True, pdf_link, pdf_filename

        # Strategy 3: try DOI-rewriting proxy and repeat
        doi_proxy = build_doi_proxy_url(doi, profile)
        page.goto(doi_proxy, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        publisher_url2 = page.url
        if publisher_url2 != publisher_url:
            direct_url2 = _resolve_direct_pdf_url(publisher_url2, doi)
            if direct_url2:
                if _download_pdf_with_session(session, direct_url2, dest, referer=publisher_url2):
                    return True, direct_url2, pdf_filename
            pdf_link2 = _find_pdf_on_page(page)
            if pdf_link2:
                if _download_pdf_with_session(session, pdf_link2, dest, referer=publisher_url2):
                    return True, pdf_link2, pdf_filename

        return False, proxy_url, ""

    except Exception as exc:
        log.debug("Institutional download failed for %s: %s", pid, exc)
        return False, proxy_url, ""


# ── Public API: retry unresolved papers ───────────────────────────────────

def get_unresolved_papers(
    input_file: Path | None = None,
    *,
    working_only: bool = False,
) -> list[dict]:
    """Return papers that are included but do not have a successful PDF.

    Reads the download log and master records to find papers with status
    ``download_failed``, ``no_oa_source``, or missing from the log entirely.
    Only papers with a DOI are returned (institutional proxy requires a URL).

    Parameters
    ----------
    working_only : bool
        If True, further filter to papers whose DOI prefix matches a
        publisher known to work via institutional proxy (see
        :data:`WORKING_DOI_PREFIXES`).
    """
    included_path = input_file or config.INCLUDED_FOR_CODING
    included_ids: set[str] = set()
    with open(included_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("final_decision", "").strip().lower() == "include":
                included_ids.add(row["paper_id"])

    master: dict[str, dict] = {}
    if config.MASTER_RECORDS_CSV.exists():
        with open(config.MASTER_RECORDS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["paper_id"] in included_ids:
                    master[row["paper_id"]] = row

    download_log = _load_download_log(config.DOWNLOAD_LOG_CSV)

    unresolved = []
    for pid in sorted(included_ids):
        entry = download_log.get(pid, {})
        status = entry.get("status", "")
        if status == "success":
            continue
        paper = master.get(pid, {"paper_id": pid, "title": "", "doi": ""})
        doi = paper.get("doi", "").strip()
        if not doi:
            continue
        if working_only and not _doi_has_working_prefix(doi):
            continue
        unresolved.append(paper)

    return unresolved


def retry_unresolved_with_institutional_access(
    *,
    institution: str = "cbs",
    delay: float = 7.0,
    max_papers: int | None = None,
    headless: bool = False,
    input_file: Path | None = None,
    working_only: bool = False,
) -> tuple[Path, dict]:
    """Retry unresolved papers via institutional proxy.

    Parameters
    ----------
    institution : str
        Institution key (default ``"cbs"``). See :data:`INSTITUTIONS`.
    delay : float
        Seconds between requests (default 7).
    max_papers : int | None
        Cap on papers to attempt.
    headless : bool
        If True, run browser headless. Default False so login popup is
        visible for interactive SSO.
    input_file : Path | None
        Override the included-papers CSV.
    working_only : bool
        If True, only attempt papers from publishers whose DOI prefix is
        in :data:`WORKING_DOI_PREFIXES`.

    Returns
    -------
    tuple[Path, dict]
        (download_log_path, stats_dict) where stats_dict has keys
        ``success``, ``failed``, ``login_performed``, ``total_attempted``.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright is required for institutional downloads.\n"
            "Install with: pip install playwright && playwright install chromium"
        ) from None

    profile = get_institution(institution)
    session_mgr = SessionManager(profile)

    papers_to_try = get_unresolved_papers(
        input_file=input_file, working_only=working_only,
    )
    if max_papers is not None:
        papers_to_try = papers_to_try[:max_papers]

    if not papers_to_try:
        print("No unresolved papers to retry via institutional access.")
        return config.DOWNLOAD_LOG_CSV, {
            "success": 0, "failed": 0,
            "login_performed": False, "total_attempted": 0,
        }

    print(f"\n{'='*60}")
    print(f"STAGE 2: Institutional access via {profile.name}")
    print(f"{'='*60}")
    print(f"  Unresolved papers with DOIs: {len(papers_to_try)}")
    if working_only:
        print(f"  Filter: working publishers only (IEEE, Springer, Wiley, ACM, Elsevier)")
    print(f"  Proxy (login?url=):  {profile.login_url_base}")
    print(f"  Proxy (DOI rewrite): {profile.doi_proxy_base}")
    print(f"  Session state:       {profile.session_state_path}")
    print(f"  Saved session:       {'yes' if session_mgr.has_saved_session else 'no'}")
    print(f"  Delay: {delay}s between requests")
    print(f"  Mode:  {'headless' if headless else 'visible browser (for login)'}")
    print()

    log_path = config.DOWNLOAD_LOG_CSV
    download_log = _load_download_log(log_path)
    pdf_dir = ensure_dir(config.FULL_TEXTS_DIR / "pdfs")

    stats: dict[str, Any] = {
        "success": 0,
        "failed": 0,
        "login_performed": False,
        "total_attempted": len(papers_to_try),
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)

        # Restore saved session if available
        ctx_kwargs: dict[str, Any] = {
            "accept_downloads": True,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        ctx_kwargs.update(session_mgr.load_state_kwargs())

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        login_done = False

        for i, paper in enumerate(papers_to_try, 1):
            pid = paper["paper_id"]
            title = paper.get("title", "") or pid
            short_title = title[:60] + "..." if len(title) > 60 else title
            safe_title = short_title.encode("ascii", errors="replace").decode("ascii")
            print(f"  [{i}/{len(papers_to_try)}] {safe_title}")

            # Navigate to the proxied URL
            doi = paper.get("doi", "").strip()
            target_url = f"https://doi.org/{doi}"
            proxy_url = build_proxy_url(target_url, profile)

            try:
                page.goto(proxy_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2)
            except Exception as exc:
                log.debug("Navigation failed for %s: %s", pid, exc)
                download_log[pid] = {
                    "paper_id": pid, "title": title, "doi": doi,
                    "source": "institutional",
                    "pdf_url": proxy_url,
                    "status": "download_failed",
                    "filename": "",
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                stats["failed"] += 1
                print(f"           -> FAILED (navigation error)")
                _save_download_log(log_path, download_log)
                time.sleep(delay)
                continue

            # Wait for SAML/SSO redirects to settle before checking login
            time.sleep(2)

            log.debug("  Page URL: %s", page.url)
            try:
                log.debug("  Page title: %s", page.title()[:80] if page.title() else "(empty)")
            except Exception:
                pass

            # Check if login is needed
            if _looks_like_login_page(page, profile):
                performed = _handle_login_if_needed(
                    page, context, profile, session_mgr,
                    already_prompted=login_done,
                )
                if performed:
                    login_done = True
                    stats["login_performed"] = True
                    # Re-navigate after login — the SSO redirect may not
                    # land on the right publisher page.
                    try:
                        page.goto(proxy_url, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(2)
                    except Exception:
                        pass

            # Attempt the actual download — page is already on the
            # publisher site (or close to it), so we pass skip_navigate=True
            # to avoid a redundant proxy navigation.
            success, used_url, filename = _attempt_institutional_download_for_paper(
                page, context, paper, profile, pdf_dir,
                skip_initial_navigate=True,
            )

            if success:
                download_log[pid] = {
                    "paper_id": pid, "title": title, "doi": doi,
                    "source": "institutional",
                    "pdf_url": used_url,
                    "status": "success",
                    "filename": filename,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                stats["success"] += 1
                print(f"           -> OK (institutional)")
            else:
                download_log[pid] = {
                    "paper_id": pid, "title": title, "doi": doi,
                    "source": "institutional",
                    "pdf_url": used_url or proxy_url,
                    "status": "download_failed",
                    "filename": "",
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
                stats["failed"] += 1
                reason = "paywall" if _looks_like_paywall(page) else "no PDF link found"
                print(f"           -> FAILED ({reason})")

            _save_download_log(log_path, download_log)
            time.sleep(delay)

        # Save session state at the end of the run
        if login_done:
            session_mgr.save_state(context)

        browser.close()

    print(f"\nInstitutional download complete ({profile.name}):")
    print(f"  Attempted: {stats['total_attempted']}")
    print(f"  Success:   {stats['success']}")
    print(f"  Failed:    {stats['failed']}")
    print(f"  Login:     {'yes' if stats['login_performed'] else 'no (reused session)'}")
    print(f"  Log:       {log_path.name}")

    return log_path, stats


# ── Legacy entry point (backwards-compatible) ─────────────────────────────

def institutional_download(
    *,
    proxy_base: str,
    delay: float = 7.0,
    max_papers: int | None = None,
    headless: bool = True,
    input_file: Path | None = None,
) -> Path:
    """Download PDFs via CBS institutional proxy using Playwright.

    This is the original entry point, kept for backwards compatibility.
    For the new two-stage workflow, use
    :func:`retry_unresolved_with_institutional_access` instead.

    Parameters
    ----------
    proxy_base : str
        CBS EZProxy base URL for DOI resolution, e.g.
        ``https://www-doi-org.esc-web.lib.cbs.dk``.
    delay : float
        Seconds between requests (default 7 — respectful institutional use).
    max_papers : int | None
        Cap on papers to attempt.
    headless : bool
        Run browser in headless mode (default True). Set False for debugging.
    input_file : Path | None
        Override the included-papers CSV.
    """
    log_path, _stats = retry_unresolved_with_institutional_access(
        institution="cbs",
        delay=delay,
        max_papers=max_papers,
        headless=headless,
        input_file=input_file,
    )
    return log_path
