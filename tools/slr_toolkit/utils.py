"""Shared utilities — hashing, safe file writes, logging setup."""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path


def configure_logging(level: int = logging.INFO) -> None:
    """Set up root logger with a consistent format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_paper_id(
    title: str | None,
    authors: str | None,
    year: str | int | None,
) -> str:
    """Return a stable 12-char hex digest from title + first author + year.

    Handles missing fields by substituting empty strings.
    """
    t = (title or "").strip().lower()
    # Take first author (before first semicolon / comma) and lowercase
    a = ""
    if authors:
        first_author = authors.split(";")[0].split(",")[0].strip().lower()
        a = first_author
    y = str(year or "").strip()
    payload = f"{t}|{a}|{y}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def safe_write_text(path: Path, content: str, *, force: bool = False) -> bool:
    """Write *content* to *path* only if file does not exist or *force* is True.

    Returns True if the file was written, False if skipped.
    """
    log = logging.getLogger("slr_toolkit")
    if path.exists() and not force:
        log.info("Skipping (exists): %s", path)
        return False
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    log.info("Wrote: %s", path)
    return True


def safe_write_bytes(path: Path, data: bytes, *, force: bool = False) -> bool:
    """Binary variant of :func:`safe_write_text`."""
    log = logging.getLogger("slr_toolkit")
    if path.exists() and not force:
        log.info("Skipping (exists): %s", path)
        return False
    ensure_dir(path.parent)
    path.write_bytes(data)
    log.info("Wrote: %s", path)
    return True
