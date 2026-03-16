"""Shared test fixtures for slr_toolkit tests."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.slr_toolkit import config


def make_master_csv(path: Path, records: list[dict]) -> Path:
    """Write a minimal master_records.csv for testing."""
    cols = config.NORMALIZED_COLUMNS + ["duplicate_of"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for rec in records:
            row = {c: rec.get(c, "") for c in cols}
            writer.writerow(row)
    return path


SAMPLE_RECORDS = [
    {
        "paper_id": f"p{i:03d}",
        "title": f"Paper {i}",
        "authors": f"Author {i}",
        "year": "2023",
        "abstract": f"Abstract for paper {i}",
        "source_db": "test",
    }
    for i in range(20)
]
