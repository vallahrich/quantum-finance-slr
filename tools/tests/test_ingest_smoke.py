"""Smoke tests for ingest parsing."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.slr_toolkit.ingest import ingest_run


@pytest.fixture()
def tmp_run_folder(tmp_path: Path) -> Path:
    """Create a temporary run folder."""
    run = tmp_path / "2026-01-01_test"
    run.mkdir()
    return run


class TestRISIngest:
    """Ingest a minimal RIS file."""

    def test_parse_ris(self, tmp_run_folder: Path) -> None:
        pytest.importorskip("rispy")

        ris_content = textwrap.dedent("""\
            TY  - JOUR
            TI  - Quantum Option Pricing with Amplitude Estimation
            AU  - Stamatopoulos, Nikitas
            AU  - Egger, Daniel
            PY  - 2020
            DO  - 10.1038/s41534-019-0130-6
            AB  - We study quantum speedups for Monte Carlo.
            KW  - quantum computing
            KW  - option pricing
            T2  - npj Quantum Information
            ER  -

            TY  - JOUR
            TI  - Variational Quantum Eigensolver for Portfolio
            AU  - Brandhofer, Sebastian
            PY  - 2022
            AB  - VQE applied to portfolio optimization.
            T2  - IEEE Access
            ER  -
        """)
        (tmp_run_folder / "export.ris").write_text(ris_content, encoding="utf-8")

        df = ingest_run(tmp_run_folder)
        assert len(df) == 2
        assert "paper_id" in df.columns
        assert df.iloc[0]["title"] == "Quantum Option Pricing with Amplitude Estimation"
        assert (tmp_run_folder / "normalized_records.csv").exists()


class TestBibTeXIngest:
    """Ingest a minimal BibTeX file."""

    def test_parse_bib(self, tmp_run_folder: Path) -> None:
        pytest.importorskip("bibtexparser")

        bib_content = textwrap.dedent("""\
            @article{stam2020,
              title = {Quantum Option Pricing},
              author = {Stamatopoulos, Nikitas},
              year = {2020},
              journal = {npj Quantum Information},
              doi = {10.1038/example}
            }
        """)
        (tmp_run_folder / "refs.bib").write_text(bib_content, encoding="utf-8")

        df = ingest_run(tmp_run_folder)
        assert len(df) == 1
        assert df.iloc[0]["doi"] == "10.1038/example"
        assert (tmp_run_folder / "normalized_records.csv").exists()


class TestCSVIngest:
    """Ingest a minimal CSV file."""

    def test_parse_csv(self, tmp_run_folder: Path) -> None:
        csv_content = (
            "Title,Authors,Year,DOI,Abstract,Keywords,Source Title\n"
            "Paper One,Auth A; Auth B,2021,10.1000/x,,kw1; kw2,Journal X\n"
            "Paper Two,Auth C,2022,,,kw3,Conference Y\n"
        )
        (tmp_run_folder / "data.csv").write_text(csv_content, encoding="utf-8")

        df = ingest_run(tmp_run_folder)
        assert len(df) == 2
        assert df.iloc[0]["venue"] == "Journal X"
