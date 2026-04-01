"""Tests for institutional download helpers (no browser needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.slr_toolkit.institutional_download import (
    CBS_PROFILE,
    INSTITUTIONS,
    InstitutionProfile,
    SessionManager,
    build_cbs_proxy_url,
    build_doi_proxy_url,
    build_proxy_url,
    get_institution,
    get_unresolved_papers,
    _sanitise_filename,
    _load_download_log,
    _save_download_log,
)


# ── URL builders ──────────────────────────────────────────────────────────


class TestBuildProxyUrl:
    def test_cbs_login_url(self):
        url = build_cbs_proxy_url("https://doi.org/10.1007/s123")
        assert url == "http://esc-web.lib.cbs.dk/login?url=https://doi.org/10.1007/s123"

    def test_build_proxy_url_generic(self):
        url = build_proxy_url("https://example.com/paper", CBS_PROFILE)
        assert url == "http://esc-web.lib.cbs.dk/login?url=https://example.com/paper"

    def test_doi_proxy_url(self):
        url = build_doi_proxy_url("10.1007/s123", CBS_PROFILE)
        assert url == "https://www-doi-org.esc-web.lib.cbs.dk/10.1007/s123"

    def test_doi_proxy_url_strips_trailing_slash(self):
        profile = InstitutionProfile(
            key="test",
            name="Test",
            login_url_base="http://proxy.test/login?url=",
            doi_proxy_base="https://doi-proxy.test/",
            session_state_filename="test.json",
        )
        url = build_doi_proxy_url("10.1234/abc", profile)
        assert url == "https://doi-proxy.test/10.1234/abc"


# ── Institution registry ─────────────────────────────────────────────────


class TestGetInstitution:
    def test_cbs_exists(self):
        profile = get_institution("cbs")
        assert profile.key == "cbs"
        assert "Copenhagen" in profile.name

    def test_case_insensitive(self):
        profile = get_institution("CBS")
        assert profile.key == "cbs"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown institution"):
            get_institution("nonexistent")


# ── Filename sanitisation ────────────────────────────────────────────────


class TestSanitiseFilename:
    def test_basic(self):
        assert _sanitise_filename("Quantum Finance!") == "quantum_finance"

    def test_truncation(self):
        long_title = "a" * 200
        assert len(_sanitise_filename(long_title)) == 80

    def test_special_chars(self):
        assert _sanitise_filename("Title: A (Review)") == "title_a_review"


# ── Session manager ──────────────────────────────────────────────────────


class TestSessionManager:
    def test_no_saved_session(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "tools.slr_toolkit.config.AUTH_STATE_DIR", tmp_path / ".auth"
        )
        profile = InstitutionProfile(
            key="test", name="Test", login_url_base="", doi_proxy_base="",
            session_state_filename="test_session.json",
        )
        mgr = SessionManager(profile)
        assert not mgr.has_saved_session
        assert mgr.load_state_kwargs() == {}

    def test_clear_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "tools.slr_toolkit.config.AUTH_STATE_DIR", tmp_path / ".auth"
        )
        profile = InstitutionProfile(
            key="test", name="Test", login_url_base="", doi_proxy_base="",
            session_state_filename="test_session.json",
        )
        mgr = SessionManager(profile)
        mgr.clear()  # Should not raise

    def test_has_saved_session(self, tmp_path, monkeypatch):
        auth_dir = tmp_path / ".auth"
        auth_dir.mkdir()
        monkeypatch.setattr(
            "tools.slr_toolkit.config.AUTH_STATE_DIR", auth_dir
        )
        profile = InstitutionProfile(
            key="test", name="Test", login_url_base="", doi_proxy_base="",
            session_state_filename="test_session.json",
        )
        # Write a fake session file
        (auth_dir / "test_session.json").write_text('{"cookies": []}')

        mgr = SessionManager(profile)
        assert mgr.has_saved_session
        kwargs = mgr.load_state_kwargs()
        assert "storage_state" in kwargs

    def test_clear_existing(self, tmp_path, monkeypatch):
        auth_dir = tmp_path / ".auth"
        auth_dir.mkdir()
        monkeypatch.setattr(
            "tools.slr_toolkit.config.AUTH_STATE_DIR", auth_dir
        )
        profile = InstitutionProfile(
            key="test", name="Test", login_url_base="", doi_proxy_base="",
            session_state_filename="test_session.json",
        )
        session_file = auth_dir / "test_session.json"
        session_file.write_text('{"cookies": []}')

        mgr = SessionManager(profile)
        mgr.clear()
        assert not session_file.exists()
        assert not mgr.has_saved_session


# ── Download log I/O ─────────────────────────────────────────────────────


class TestDownloadLogIO:
    def test_roundtrip(self, tmp_path):
        log_path = tmp_path / "download_log.csv"
        entries = {
            "abc123": {
                "paper_id": "abc123",
                "title": "Test Paper",
                "doi": "10.1234/test",
                "source": "arxiv",
                "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
                "status": "success",
                "filename": "abc123_test_paper.pdf",
                "timestamp": "2026-03-31T12:00:00",
            },
        }
        _save_download_log(log_path, entries)
        loaded = _load_download_log(log_path)
        assert "abc123" in loaded
        assert loaded["abc123"]["status"] == "success"
        assert loaded["abc123"]["doi"] == "10.1234/test"

    def test_csv_escaping(self, tmp_path):
        log_path = tmp_path / "download_log.csv"
        entries = {
            "def456": {
                "paper_id": "def456",
                "title": 'Paper with "quotes" and, commas',
                "doi": "10.1234/test",
                "source": "openalex",
                "pdf_url": "",
                "status": "download_failed",
                "filename": "",
                "timestamp": "2026-03-31T12:00:00",
            },
        }
        _save_download_log(log_path, entries)
        loaded = _load_download_log(log_path)
        assert loaded["def456"]["title"] == 'Paper with "quotes" and, commas'
