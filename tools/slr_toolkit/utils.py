"""Shared utilities — hashing, safe file writes, logging setup."""

from __future__ import annotations

import csv
import hashlib
import logging
import sys
import time
from pathlib import Path

from . import config


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


def _replace_with_retries(tmp_path: Path, path: Path, *, attempts: int = 10) -> None:
    """Replace ``path`` with ``tmp_path``, retrying on transient Windows/OneDrive locks."""
    log = logging.getLogger("slr_toolkit")
    for attempt in range(attempts):
        try:
            tmp_path.replace(path)
            return
        except PermissionError:
            time.sleep(0.5 * (attempt + 1))

    # All atomic retries exhausted — fall back to direct overwrite
    log.warning("Atomic rename failed after %d retries for %s; falling back to direct write", attempts, path)
    try:
        content = tmp_path.read_bytes()
        path.write_bytes(content)
        tmp_path.unlink(missing_ok=True)
    except PermissionError:
        log.error("Direct write also failed for %s — skipping this checkpoint save", path)
        tmp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically where possible, with lock retries for Windows sync tools."""
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    _replace_with_retries(tmp_path, path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Binary variant of :func:`atomic_write_text`."""
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_bytes(data)
    _replace_with_retries(tmp_path, path)


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
    atomic_write_text(path, content)
    log.info("Wrote: %s", path)
    return True


def cohens_kappa(decisions_a: list[str], decisions_b: list[str]) -> float:
    """Compute Cohen's kappa for two lists of categorical decisions.

    κ = (p_o - p_e) / (1 - p_e)
    where p_o = observed agreement, p_e = expected agreement by chance.
    Returns 1.0 for perfect agreement, 0.0 for chance-level, negative for
    worse-than-chance. Returns 1.0 if both lists are empty.
    """
    n = len(decisions_a)
    if n == 0:
        return 1.0
    if n != len(decisions_b):
        raise ValueError(
            f"Decision lists must have equal length (got {n} vs {len(decisions_b)})"
        )

    # Collect all unique categories
    categories = sorted(set(decisions_a) | set(decisions_b))

    # Observed agreement
    agree = sum(1 for a, b in zip(decisions_a, decisions_b) if a == b)
    p_o = agree / n

    # Expected agreement by chance
    p_e = 0.0
    for cat in categories:
        count_a = sum(1 for d in decisions_a if d == cat)
        count_b = sum(1 for d in decisions_b if d == cat)
        p_e += (count_a / n) * (count_b / n)

    if p_e == 1.0:
        return 1.0

    return (p_o - p_e) / (1 - p_e)


def percent_agreement(decisions_a: list[str], decisions_b: list[str]) -> float:
    """Compute percent agreement between two lists of decisions."""
    n = len(decisions_a)
    if n == 0:
        return 100.0
    if n != len(decisions_b):
        raise ValueError(
            f"Decision lists must have equal length (got {n} vs {len(decisions_b)})"
        )
    agree = sum(1 for a, b in zip(decisions_a, decisions_b) if a == b)
    return 100.0 * agree / n


def safe_write_bytes(path: Path, data: bytes, *, force: bool = False) -> bool:
    """Binary variant of :func:`safe_write_text`."""
    log = logging.getLogger("slr_toolkit")
    if path.exists() and not force:
        log.info("Skipping (exists): %s", path)
        return False
    atomic_write_bytes(path, data)
    log.info("Wrote: %s", path)
    return True


def load_master_records(*, unique_only: bool = False) -> list[dict[str, str]]:
    """Load records from ``master_records.csv``.

    Parameters
    ----------
    unique_only:
        When ``True``, exclude rows already marked as duplicates.
    """
    path = config.MASTER_RECORDS_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"Master records file not found: {path}. Run build-master first."
        )

    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if unique_only:
        return [row for row in rows if not row.get("duplicate_of", "").strip()]
    return rows
