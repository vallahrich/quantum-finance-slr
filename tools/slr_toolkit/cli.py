"""CLI entry-point — ``python -m tools.slr_toolkit.cli <command>``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config
from .utils import configure_logging, ensure_dir


def _cmd_init(args: argparse.Namespace) -> None:
    """Create missing folders and template files."""
    from .templates import create_all_templates

    force: bool = args.force
    log = logging.getLogger("slr_toolkit.cli")

    for d in config.ALL_DIRS:
        ensure_dir(d)
        log.info("Ensured directory: %s", d)

    create_all_templates(force=force)
    print("✓ Repository structure initialised.")


def _cmd_new_search_run(args: argparse.Namespace) -> None:
    """Create a new date-stamped search-run folder."""
    from .search_run import create_search_run

    run_folder = create_search_run(source=args.source, run_date=args.date)
    print(f"✓ Created search run: {run_folder}")


def _cmd_ingest(args: argparse.Namespace) -> None:
    """Ingest bibliographic exports from a run folder."""
    from .ingest import ingest_run

    run_folder = Path(args.run_folder).resolve()
    df = ingest_run(run_folder)
    print(f"✓ Ingested {len(df)} records from {run_folder.name}")


def _cmd_build_master(args: argparse.Namespace) -> None:
    """Build deduplicated master library."""
    from .dedup import build_master

    build_master()
    print("✓ Master library built.")


def _cmd_prisma(args: argparse.Namespace) -> None:
    """Generate PRISMA flow counts."""
    from .prisma import generate_prisma_counts

    generate_prisma_counts()
    print("✓ PRISMA counts generated.")


def _cmd_auto_search(args: argparse.Namespace) -> None:
    """Run automated API search across selected databases."""
    from .api_search import auto_search

    sources = [s.strip() for s in args.sources.split(",")]
    print(f"Searching: {', '.join(sources)}")
    print(f"Query: {args.query}")
    print(f"Year range: {args.from_year}–present")
    print(f"Max results per source: {args.max_results}")
    print()

    folders = auto_search(
        query=args.query,
        sources=sources,
        from_year=args.from_year,
        max_results=args.max_results,
        run_date=args.date,
        email=args.email,
        api_key=args.api_key,
    )

    if folders:
        print(f"\n✓ Auto-search complete. {len(folders)} source(s) ingested.")
        for source, folder in folders.items():
            print(f"  {source} → {folder.name}")
    else:
        print("\n✗ No results retrieved from any source.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slr_toolkit",
        description="Quantum-Finance SLR Toolkit — manage search runs, "
                    "ingest exports, deduplicate, and generate PRISMA counts.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # -- init ----------------------------------------------------------------
    p_init = sub.add_parser("init", help="Initialise folder structure and templates.")
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing template files.",
    )
    p_init.set_defaults(func=_cmd_init)

    # -- new-search-run ------------------------------------------------------
    p_nsr = sub.add_parser("new-search-run", help="Create a new search-run folder.")
    p_nsr.add_argument(
        "--source",
        required=True,
        help="Database name (e.g. scopus, wos, ieee, arxiv).",
    )
    p_nsr.add_argument(
        "--date",
        default=None,
        help="Run date in YYYY-MM-DD format (default: today).",
    )
    p_nsr.set_defaults(func=_cmd_new_search_run)

    # -- ingest --------------------------------------------------------------
    p_ing = sub.add_parser("ingest", help="Ingest exports from a run folder.")
    p_ing.add_argument(
        "--run-folder",
        required=True,
        help="Path to the run folder (e.g. 03_raw_exports/2026-03-08_scopus).",
    )
    p_ing.set_defaults(func=_cmd_ingest)

    # -- build-master --------------------------------------------------------
    p_bm = sub.add_parser("build-master", help="Build deduplicated master library.")
    p_bm.set_defaults(func=_cmd_build_master)

    # -- prisma --------------------------------------------------------------
    p_pr = sub.add_parser("prisma", help="Generate PRISMA flow counts.")
    p_pr.set_defaults(func=_cmd_prisma)

    # -- auto-search ---------------------------------------------------------
    p_as = sub.add_parser(
        "auto-search",
        help="Automatically search APIs and ingest results.",
    )
    p_as.add_argument(
        "--query", "-q",
        required=True,
        help='Search query, e.g. \'"quantum computing" AND "finance"\'.'
    )
    p_as.add_argument(
        "--sources", "-s",
        default="openalex,arxiv,semantic_scholar",
        help="Comma-separated API sources: openalex, arxiv, semantic_scholar, "
             "scopus, wos. Default: openalex,arxiv,semantic_scholar.",
    )
    p_as.add_argument(
        "--from-year",
        type=int,
        default=2016,
        help="Start year for publication filter (default: 2016).",
    )
    p_as.add_argument(
        "--max-results",
        type=int,
        default=500,
        help="Max results per source (default: 500).",
    )
    p_as.add_argument(
        "--date",
        default=None,
        help="Run date in YYYY-MM-DD format (default: today).",
    )
    p_as.add_argument(
        "--email",
        default=None,
        help="Contact email for polite API access (OpenAlex).",
    )
    p_as.add_argument(
        "--api-key",
        default=None,
        help="API key for Scopus or WoS (if using those sources).",
    )
    p_as.set_defaults(func=_cmd_auto_search)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    args.func(args)


if __name__ == "__main__":
    main()
