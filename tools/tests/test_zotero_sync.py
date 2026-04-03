"""Tests for zotero_sync module — normalization, mapping, dedup, and dry-run."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.slr_toolkit.zotero_sync import ZoteroWriter


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeDoi:
    def test_strips_url_prefix(self):
        assert ZoteroWriter._normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"

    def test_strips_dx_prefix(self):
        assert ZoteroWriter._normalize_doi("http://dx.doi.org/10.1234/ABC") == "10.1234/abc"

    def test_lowercases(self):
        assert ZoteroWriter._normalize_doi("10.1234/ABC") == "10.1234/abc"

    def test_strips_whitespace(self):
        assert ZoteroWriter._normalize_doi("  10.1234/abc  ") == "10.1234/abc"

    def test_empty(self):
        assert ZoteroWriter._normalize_doi("") == ""


class TestNormalizeTitle:
    def test_basic(self):
        assert ZoteroWriter.normalize_title("Hello, World!") == "hello world"

    def test_unicode(self):
        assert ZoteroWriter.normalize_title("Über quantum—finance") == "ber quantum finance"

    def test_multiple_spaces(self):
        assert ZoteroWriter.normalize_title("  too   many   spaces  ") == "too many spaces"

    def test_empty(self):
        assert ZoteroWriter.normalize_title("") == ""


class TestExtractArxivId:
    def test_valid(self):
        assert ZoteroWriter._extract_arxiv_id("10.48550/arXiv.2301.12345") == "2301.12345"

    def test_case_insensitive(self):
        assert ZoteroWriter._extract_arxiv_id("10.48550/ARXIV.2301.12345") == "2301.12345"

    def test_non_arxiv(self):
        assert ZoteroWriter._extract_arxiv_id("10.1007/s10479-023-05444-y") == ""

    def test_empty(self):
        assert ZoteroWriter._extract_arxiv_id("") == ""


class TestFirstAuthorYear:
    def test_basic(self):
        assert ZoteroWriter._first_author_year("Smith, John; Doe, Jane", "2023") == "smith|2023"

    def test_semicolon_split(self):
        assert ZoteroWriter._first_author_year("Alice; Bob", "2024") == "alice|2024"

    def test_empty_authors(self):
        assert ZoteroWriter._first_author_year("", "2023") == ""

    def test_empty_year(self):
        assert ZoteroWriter._first_author_year("Smith", "") == ""


# ---------------------------------------------------------------------------
# Mapping tests
# ---------------------------------------------------------------------------


class TestMapPaperToZoteroData:
    def test_journal_article(self):
        paper = {
            "paper_id": "abc123",
            "title": "Quantum Portfolio Optimization",
            "authors": "Smith, John; Doe, Jane",
            "year": "2023",
            "venue": "Journal of Finance",
            "doi": "10.1234/jf.2023.001",
            "abstract": "We study quantum algorithms.",
            "keywords": "quantum; finance",
            "source_db": "scopus",
            "is_preprint": "0",
        }
        data = ZoteroWriter._map_paper_to_zotero_data(paper)
        assert data["itemType"] == "journalArticle"
        assert data["title"] == "Quantum Portfolio Optimization"
        assert data["DOI"] == "10.1234/jf.2023.001"
        assert data["publicationTitle"] == "Journal of Finance"
        assert len(data["creators"]) == 2
        assert data["creators"][0]["lastName"] == "Smith"
        assert data["creators"][0]["firstName"] == "John"

    def test_arxiv_preprint(self):
        paper = {
            "paper_id": "def456",
            "title": "QML for Finance",
            "authors": "Alice",
            "year": "2024",
            "venue": "arXiv",
            "doi": "10.48550/arXiv.2401.00001",
            "abstract": "",
            "keywords": "",
            "source_db": "arxiv",
            "is_preprint": "1",
        }
        data = ZoteroWriter._map_paper_to_zotero_data(paper)
        assert data["itemType"] == "preprint"
        assert "arXiv" in data.get("extra", "")
        assert data["url"] == "https://arxiv.org/abs/2401.00001"

    def test_conference_paper(self):
        paper = {
            "paper_id": "ghi789",
            "title": "Test Paper",
            "authors": "Bob",
            "year": "2023",
            "venue": "IEEE Conference on Quantum",
            "doi": "",
            "abstract": "",
            "keywords": "",
            "source_db": "scopus",
            "is_preprint": "0",
        }
        data = ZoteroWriter._map_paper_to_zotero_data(paper)
        assert data["itemType"] == "conferencePaper"
        assert data["proceedingsTitle"] == "IEEE Conference on Quantum"

    def test_tags_from_keywords(self):
        paper = {
            "paper_id": "x",
            "title": "Test",
            "authors": "",
            "year": "2023",
            "venue": "",
            "doi": "",
            "abstract": "",
            "keywords": "quantum computing; portfolio optimization",
            "source_db": "",
            "is_preprint": "",
        }
        data = ZoteroWriter._map_paper_to_zotero_data(paper)
        tag_names = [t["tag"] for t in data.get("tags", [])]
        assert "quantum computing" in tag_names
        assert "portfolio optimization" in tag_names


# ---------------------------------------------------------------------------
# Dedup tests
# ---------------------------------------------------------------------------


class TestFindExistingItem:
    """Test dedup logic without actually calling the API."""

    def setup_method(self):
        # We don't want __init__ to validate API key
        self.writer = ZoteroWriter.__new__(ZoteroWriter)

    def test_match_by_doi(self):
        item = {"key": "Z1", "data": {"DOI": "10.1234/abc"}}
        doi_idx = {"10.1234/abc": item}
        paper = {"doi": "10.1234/abc", "title": "X", "authors": "", "year": ""}

        found, method = self.writer._find_existing_item(paper, doi_idx, {}, {}, {})
        assert found == item
        assert method == "doi"

    def test_match_by_arxiv_id(self):
        item = {"key": "Z2", "data": {}}
        arxiv_idx = {"2301.12345": item}
        paper = {"doi": "10.48550/arXiv.2301.12345", "title": "", "authors": "", "year": ""}

        found, method = self.writer._find_existing_item(paper, {}, arxiv_idx, {}, {})
        assert found == item
        assert method == "arxiv_id"

    def test_match_by_title(self):
        item = {"key": "Z3", "data": {}}
        title_idx = {"quantum portfolio optimization": item}
        paper = {"doi": "", "title": "Quantum Portfolio Optimization!", "authors": "", "year": ""}

        found, method = self.writer._find_existing_item(paper, {}, {}, title_idx, {})
        assert found == item
        assert method == "title"

    def test_match_by_author_year(self):
        item = {"key": "Z4", "data": {}}
        ay_idx = {"smith|2023": item}
        paper = {"doi": "", "title": "Unknown", "authors": "Smith, John", "year": "2023"}

        found, method = self.writer._find_existing_item(paper, {}, {}, {}, ay_idx)
        assert found == item
        assert method == "author_year"

    def test_no_match(self):
        paper = {"doi": "", "title": "Unique Paper", "authors": "Nobody", "year": "2099"}
        found, method = self.writer._find_existing_item(paper, {}, {}, {}, {})
        assert found is None
        assert method == ""

    def test_doi_takes_priority(self):
        doi_item = {"key": "DOI", "data": {"DOI": "10.1234/abc"}}
        title_item = {"key": "TITLE", "data": {}}
        paper = {"doi": "10.1234/abc", "title": "Some Title", "authors": "", "year": ""}

        found, method = self.writer._find_existing_item(
            paper,
            {"10.1234/abc": doi_item},
            {},
            {"some title": title_item},
            {},
        )
        assert found["key"] == "DOI"
        assert method == "doi"


# ---------------------------------------------------------------------------
# Collection creation test
# ---------------------------------------------------------------------------


class TestEnsureCollection:
    def test_finds_existing(self):
        writer = ZoteroWriter.__new__(ZoteroWriter)
        writer.list_collections = MagicMock(return_value=[
            {"key": "ABC", "data": {"name": "SLR Results", "parentCollection": False}},
        ])
        writer.create_collection = MagicMock()

        key = writer.ensure_collection("SLR Results")
        assert key == "ABC"
        writer.create_collection.assert_not_called()

    def test_creates_new(self):
        writer = ZoteroWriter.__new__(ZoteroWriter)
        writer.list_collections = MagicMock(return_value=[])
        writer.create_collection = MagicMock(return_value="NEW_KEY")

        key = writer.ensure_collection("SLR Results")
        assert key == "NEW_KEY"
        writer.create_collection.assert_called_once_with("SLR Results", parent_key=None)


# ---------------------------------------------------------------------------
# Dry-run test
# ---------------------------------------------------------------------------


class TestSyncDryRun:
    """Test that dry-run does not make any API write calls."""

    def test_dry_run_no_writes(self, tmp_path):
        """Dry-run should not call _post or _patch."""
        # Create minimal included_for_coding.csv
        included_csv = tmp_path / "included.csv"
        included_csv.write_text("paper_id,final_decision\np001,include\n")

        # Create minimal master_records.csv
        master_csv = tmp_path / "master.csv"
        master_csv.write_text(
            "paper_id,title,authors,year,venue,doi,abstract,keywords,source_db,export_file,is_preprint,version_group_id\n"
            "p001,Test Paper,Author A,2023,Test Venue,10.1234/test,,quantum,test,,0,\n"
        )

        writer = ZoteroWriter.__new__(ZoteroWriter)
        writer._group_id = "6475432"
        writer._api_key = "fake"
        writer._base = "https://api.zotero.org/groups/6475432"
        writer._headers = {}
        writer._library_version = None

        # Mock the API calls
        writer.get_all_items = MagicMock(return_value=[])
        writer._post = MagicMock()
        writer._patch = MagicMock()
        writer.list_collections = MagicMock(return_value=[])
        writer.create_collection = MagicMock()

        # Patch config paths
        with patch.object(type(writer), '_build_zotero_index',
                          return_value=({}, {}, {}, {})):
            with patch("tools.slr_toolkit.config.INCLUDED_FOR_CODING", included_csv), \
                 patch("tools.slr_toolkit.config.MASTER_RECORDS_CSV", master_csv):

                report = writer.sync_slr_results(dry_run=True, max_items=5)

        # Verify no write calls
        writer._post.assert_not_called()
        writer._patch.assert_not_called()
        writer.create_collection.assert_not_called()

        # Verify report
        assert report["dry_run"] is True
        assert report["summary"]["created"] == 1
        assert report["summary"]["updated"] == 0
        assert report["summary"]["failed"] == 0
