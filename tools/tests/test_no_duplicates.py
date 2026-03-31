"""Tests to verify there are no unwanted duplications in the SLR results.

Checks across multiple levels:
1. download_log.csv — each paper_id appears exactly once
2. included_for_coding.csv — no duplicate paper_ids
3. Master records — canonical rows (duplicate_of empty) have unique paper_ids
4. DOI uniqueness — included canonical papers should not share DOIs across
   different version groups
5. Title near-duplicates — catch papers that slipped through dedup
6. PDF filenames — no two successful downloads to the same file

Note: master_records.csv intentionally contains multiple rows per paper_id
(one per source database). Rows with ``duplicate_of`` set are non-canonical
copies. Tests that check the included set should filter to canonical rows.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

import pytest

from tools.slr_toolkit import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _normalize_doi(doi: str) -> str:
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/",
                    "https://dx.doi.org/", "http://dx.doi.org/"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def _canonical_rows(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return only canonical master records (duplicate_of is empty).

    master_records.csv contains multiple rows per paper_id — one per source
    database.  Rows where ``duplicate_of`` is non-empty are copies that were
    merged into the canonical row during deduplication.
    """
    return [r for r in records if not r.get("duplicate_of", "").strip()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def included_ids() -> set[str]:
    rows = _load_csv(config.INCLUDED_FOR_CODING)
    return {r["paper_id"] for r in rows
            if r.get("final_decision", "").strip().lower() == "include"}


@pytest.fixture(scope="module")
def master_records() -> list[dict[str, str]]:
    return _load_csv(config.MASTER_RECORDS_CSV)


@pytest.fixture(scope="module")
def canonical_master(master_records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Canonical (non-duplicate) master records only."""
    return _canonical_rows(master_records)


@pytest.fixture(scope="module")
def download_log() -> list[dict[str, str]]:
    if not config.DOWNLOAD_LOG_CSV.exists():
        pytest.skip("download_log.csv not found")
    return _load_csv(config.DOWNLOAD_LOG_CSV)


# ---------------------------------------------------------------------------
# 1. Download log — no duplicate paper_ids
# ---------------------------------------------------------------------------

class TestDownloadLogNoDuplicates:

    def test_unique_paper_ids(self, download_log: list[dict]) -> None:
        """Each paper_id must appear exactly once in download_log.csv."""
        pids = [r["paper_id"] for r in download_log]
        counts = Counter(pids)
        duplicates = {pid: n for pid, n in counts.items() if n > 1}
        assert not duplicates, (
            f"Duplicate paper_ids in download_log.csv: {duplicates}"
        )

    def test_entry_count_matches_included(
        self, download_log: list[dict], included_ids: set[str],
    ) -> None:
        """download_log should have at most one entry per included paper."""
        log_pids = {r["paper_id"] for r in download_log}
        extra = log_pids - included_ids
        assert not extra, (
            f"download_log contains {len(extra)} paper_ids not in included set: "
            f"{sorted(extra)[:5]}..."
        )


# ---------------------------------------------------------------------------
# 2. Included-for-coding — no duplicate paper_ids
# ---------------------------------------------------------------------------

class TestIncludedNoDuplicates:

    def test_unique_paper_ids(self, included_ids: set[str]) -> None:
        """included_for_coding.csv should have unique paper_ids among includes."""
        rows = _load_csv(config.INCLUDED_FOR_CODING)
        include_pids = [r["paper_id"] for r in rows
                        if r.get("final_decision", "").strip().lower() == "include"]
        counts = Counter(include_pids)
        duplicates = {pid: n for pid, n in counts.items() if n > 1}
        assert not duplicates, (
            f"Duplicate paper_ids in included_for_coding.csv: {duplicates}"
        )

    def test_nonzero_included(self, included_ids: set[str]) -> None:
        """Sanity check: we should have a reasonable number of included papers."""
        assert len(included_ids) > 100, (
            f"Only {len(included_ids)} included papers — expected > 100"
        )


# ---------------------------------------------------------------------------
# 3. Master records — each included paper_id appears exactly once
# ---------------------------------------------------------------------------

class TestMasterRecordsNoDuplicates:

    def test_unique_paper_ids_among_canonical(
        self, canonical_master: list[dict],
    ) -> None:
        """Each paper_id among canonical (non-duplicate) rows must be unique."""
        pids = [r["paper_id"] for r in canonical_master]
        counts = Counter(pids)
        duplicates = {pid: n for pid, n in counts.items() if n > 1}
        assert not duplicates, (
            f"Duplicate paper_ids among canonical master records: "
            f"{dict(list(duplicates.items())[:5])}..."
        )

    def test_every_included_has_canonical_row(
        self,
        canonical_master: list[dict],
        included_ids: set[str],
    ) -> None:
        """Every included paper_id should have a canonical master record."""
        canonical_pids = {r["paper_id"] for r in canonical_master}
        missing = included_ids - canonical_pids
        assert not missing, (
            f"{len(missing)} included papers have no canonical master record: "
            f"{sorted(missing)[:5]}..."
        )


# ---------------------------------------------------------------------------
# 4. DOI uniqueness among included papers (version-group aware)
# ---------------------------------------------------------------------------

class TestDOIUniqueness:

    def test_no_duplicate_dois_among_canonical_included(
        self,
        canonical_master: list[dict],
        included_ids: set[str],
    ) -> None:
        """No two *different* canonical included papers should share a DOI.

        Each canonical paper_id is a unique work. If two have the same DOI,
        dedup missed a pair.
        """
        doi_pids: dict[str, list[str]] = {}  # norm_doi -> [paper_ids]

        for r in canonical_master:
            pid = r["paper_id"]
            if pid not in included_ids:
                continue
            doi = _normalize_doi(r.get("doi", ""))
            if not doi:
                continue
            doi_pids.setdefault(doi, []).append(pid)

        duplicates = {
            doi: pids
            for doi, pids in doi_pids.items()
            if len(pids) > 1
        }
        assert not duplicates, (
            f"Canonical included papers sharing a DOI (dedup missed these): "
            f"{dict(list(duplicates.items())[:5])}"
        )


# ---------------------------------------------------------------------------
# 5. Title near-duplicates among included papers
# ---------------------------------------------------------------------------

class TestTitleNearDuplicates:

    # Known title-duplicate pairs where dedup didn't link preprint/published
    # versions across sources (different DOIs, different version groups).
    # These are tracked here so the count doesn't silently grow.
    _KNOWN_TITLE_DUP_COUNT = 11  # Update if duplicates are resolved

    def test_title_duplicates_do_not_grow(
        self,
        canonical_master: list[dict],
        included_ids: set[str],
    ) -> None:
        """Track exact-title duplicates among canonical included papers.

        Some duplicates are known (preprint/published pairs the dedup missed
        because they have different DOIs across sources). This test ensures
        the count doesn't grow beyond the known baseline.
        """
        title_pids: dict[str, list[str]] = {}

        for r in canonical_master:
            pid = r["paper_id"]
            if pid not in included_ids:
                continue
            title = _normalize_title(r.get("title", ""))
            if not title or len(title) < 10:
                continue
            title_pids.setdefault(title, []).append(pid)

        duplicates = {
            title: pids
            for title, pids in title_pids.items()
            if len(pids) > 1
        }

        dup_count = len(duplicates)
        if dup_count > 0:
            import warnings
            warnings.warn(
                f"{dup_count} title-duplicate pairs found among canonical "
                f"included papers (known dedup misses). "
                f"Examples: {dict(list(duplicates.items())[:3])}",
                stacklevel=1,
            )

        assert dup_count <= self._KNOWN_TITLE_DUP_COUNT, (
            f"Title duplicates grew from {self._KNOWN_TITLE_DUP_COUNT} to "
            f"{dup_count} — new dedup misses detected: "
            f"{dict(list(duplicates.items())[:5])}"
        )


# ---------------------------------------------------------------------------
# 6. PDF filenames — no two successful downloads to the same file
# ---------------------------------------------------------------------------

class TestPDFFileUniqueness:

    def test_no_duplicate_filenames(self, download_log: list[dict]) -> None:
        """Successful downloads should not have the same filename."""
        filenames = [
            r["filename"]
            for r in download_log
            if r.get("status") == "success" and r.get("filename")
        ]
        counts = Counter(filenames)
        duplicates = {fn: n for fn, n in counts.items() if n > 1}
        assert not duplicates, (
            f"Duplicate PDF filenames in download_log.csv: "
            f"{dict(list(duplicates.items())[:5])}"
        )
