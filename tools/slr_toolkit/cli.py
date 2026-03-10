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
    print("[ok] Repository structure initialised.")


def _cmd_new_search_run(args: argparse.Namespace) -> None:
    """Create a new date-stamped search-run folder."""
    from .search_run import create_search_run

    run_folder = create_search_run(source=args.source, run_date=args.date)
    print(f"[ok] Created search run: {run_folder}")


def _cmd_ingest(args: argparse.Namespace) -> None:
    """Ingest bibliographic exports from a run folder."""
    from .ingest import ingest_run

    run_folder = Path(args.run_folder).resolve()
    df = ingest_run(run_folder)
    print(f"[ok] Ingested {len(df)} records from {run_folder.name}")


def _cmd_build_master(args: argparse.Namespace) -> None:
    """Build deduplicated master library."""
    from .dedup import build_master

    build_master()
    print("[ok] Master library built.")


def _cmd_prisma(args: argparse.Namespace) -> None:
    """Generate PRISMA flow counts."""
    from .prisma import generate_prisma_counts

    generate_prisma_counts()
    print("[ok] PRISMA counts generated.")


def _cmd_auto_search(args: argparse.Namespace) -> None:
    """Run automated API search across selected databases."""
    from .api_search import auto_search, resolve_openalex_concepts

    sources = [s.strip() for s in args.sources.split(",")]
    print(f"Searching: {', '.join(sources)}")
    print(f"Query: {args.query}")
    print(f"Year range: {args.from_year}--present")
    cap_str = str(args.max_results) if args.max_results is not None else "all (no limit)"
    print(f"Max results per source: {cap_str}")

    # Resolve concept filters to OpenAlex IDs
    concept_ids: list[str] | None = None
    if args.concept_filter:
        concept_ids = []
        terms = [t.strip() for t in args.concept_filter.split(",")]
        print(f"\nResolving concept filters: {terms}")
        for term in terms:
            matches = resolve_openalex_concepts(term)
            if matches:
                best = matches[0]
                concept_ids.append(best["id"])
                print(f"  {term!r} -> {best['id']} ({best['display_name']})")
                if len(matches) > 1:
                    for m in matches[1:]:
                        print(f"    also: {m['id']} ({m['display_name']})")
            else:
                print(f"  {term!r} -> no matches found")

    arxiv_categories: list[str] | None = None
    if args.arxiv_categories:
        arxiv_categories = [c.strip() for c in args.arxiv_categories.split(",")]
        print(f"arXiv categories: {arxiv_categories}")

    if args.exact:
        print("OpenAlex exact matching: enabled")

    print()

    folders = auto_search(
        query=args.query,
        sources=sources,
        from_year=args.from_year,
        max_results=args.max_results,
        run_date=args.date,
        email=args.email,
        api_key=args.api_key,
        openalex_api_key=args.openalex_api_key,
        concept_ids=concept_ids if concept_ids else None,
        use_exact=args.exact,
        arxiv_categories=arxiv_categories,
    )

    if folders:
        print(f"\n[ok] Auto-search complete. {len(folders)} source(s) ingested.")
        for source, folder in folders.items():
            print(f"  {source} -> {folder.name}")
    else:
        print("\n[FAIL] No results retrieved from any source.")


def _cmd_generate_screening(args: argparse.Namespace) -> None:
    """Generate screening Excel workbooks."""
    from .screening import generate_screening_excels

    paths = generate_screening_excels(seed=args.seed)
    print("[ok] Screening workbooks generated:")
    for label, path in paths.items():
        print(f"  {label}: {path.name}")


def _cmd_compute_kappa(args: argparse.Namespace) -> None:
    """Compute Cohen's kappa from calibration workbook."""
    from pathlib import Path
    from .screening import compute_kappa

    cal_path = Path(args.file) if args.file else None
    result = compute_kappa(cal_path)

    if result.get("error"):
        print(f"[FAIL] {result['error']}")
        return

    print(f"Calibration Results:")
    print(f"  Records screened by both: {result['n']}")
    print(f"  Agreed:                   {result['agreed']}")
    print(f"  Disagreed:                {result['disagreed']}")
    print(f"  Agreement rate:           {result['agreement']:.1%}")
    print(f"  Cohen's kappa:            {result['kappa']:.3f}")
    print()

    if result["pass"]:
        print(f"  [ok] kappa = {result['kappa']:.3f} >= 0.70 -- PASS")
        print("  You can proceed to split screening.")
    else:
        print(f"  [FAIL] kappa = {result['kappa']:.3f} < 0.70 -- BELOW THRESHOLD")
        print("  Discuss disagreements, clarify criteria, and recalibrate.")

    if result.get("confusion"):
        print("\n  Confusion matrix:")
        for (a, b), count in sorted(result["confusion"].items()):
            if a != b:
                print(f"    Reviewer A={a}, Reviewer B={b}: {count}")


def _cmd_merge_screening(args: argparse.Namespace) -> None:
    """Merge screening results into decisions CSV."""
    from .screening import merge_screening_results

    output = merge_screening_results()
    print(f"[ok] Merged screening decisions -> {output.name}")


def _cmd_rerun_clean(args: argparse.Namespace) -> None:
    """Move noisy run folders to a deprecated directory and log the amendment."""
    import csv
    from datetime import date

    log = logging.getLogger("slr_toolkit.cli")
    pattern = args.pattern
    rationale = args.rationale or "Noisy results deprecated via rerun-clean"

    deprecated_dir = config.RAW_EXPORTS_DIR / "_deprecated_noisy"
    ensure_dir(deprecated_dir)

    # Find matching run folders
    matched: list[Path] = []
    if config.RAW_EXPORTS_DIR.exists():
        for child in sorted(config.RAW_EXPORTS_DIR.iterdir()):
            if child.is_dir() and child.name != "_deprecated_noisy" and pattern in child.name:
                matched.append(child)

    if not matched:
        print(f"No run folders matching {pattern!r} found in {config.RAW_EXPORTS_DIR}")
        return

    print(f"Moving {len(matched)} folder(s) to _deprecated_noisy/:")
    for folder in matched:
        dest = deprecated_dir / folder.name
        folder.rename(dest)
        print(f"  {folder.name} -> _deprecated_noisy/{folder.name}")
        log.info("Moved %s to %s", folder, dest)

    # Write README in deprecated folder
    readme_path = deprecated_dir / "README.txt"
    if not readme_path.exists():
        readme_path.write_text(
            "Deprecated search-run folders\n"
            "=============================\n\n"
            "Folders in this directory were moved here by the `rerun-clean` command\n"
            "because their search results were deemed too noisy or imprecise.\n"
            "They are kept for provenance but excluded from the active pipeline.\n",
            encoding="utf-8",
        )

    # Append to amendments_log.csv
    today = date.today().isoformat()
    description = f"Deprecated run folders matching {pattern!r} via rerun-clean"
    amendments_path = config.AMENDMENTS_CSV
    ensure_dir(amendments_path.parent)

    file_exists = amendments_path.exists() and amendments_path.stat().st_size > 0
    with open(amendments_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["date", "version", "section", "change_description", "author"])
        writer.writerow([today, "", "03_raw_exports", f"{description}. Rationale: {rationale}", "slr_toolkit"])

    print(f"[ok] Amendment logged to {amendments_path.name}")


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
        help='Search query, e.g. \'"quantum computing" AND "finance"\'. '
             "For Scopus, see config.SCOPUS_QUERY_TEMPLATE for the recommended query.",
    )
    p_as.add_argument(
        "--sources", "-s",
        default="openalex,arxiv,scopus",
        help="Comma-separated API sources: openalex, arxiv, scopus, "
             "semantic_scholar, wos. Default: openalex,arxiv,scopus.",
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
        default=None,
        help="Max results per source. Default: all (no limit). "
             "Pass a number to cap results.",
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
    p_as.add_argument(
        "--openalex-api-key",
        default=None,
        help="OpenAlex API key (free, required since Feb 2026). "
             "Also checks OPENALEX_API_KEY env var. "
             "Get a key at https://openalex.org/settings/api",
    )
    p_as.add_argument(
        "--concept-filter",
        default=None,
        help="Comma-separated concept search terms for OpenAlex filtering "
             '(e.g. "quantum computing,finance"). Auto-resolves to concept IDs.',
    )
    p_as.add_argument(
        "--arxiv-categories",
        default=None,
        help="Comma-separated arXiv category filters. NOT applied by default. "
             "Recommended if arXiv results are unmanageably large: "
             "q-fin.*,quant-ph,cs.CE,cs.AI,cs.LG",
    )
    p_as.add_argument(
        "--exact",
        action="store_true",
        help="Use OpenAlex exact matching for unstemmed results.",
    )
    p_as.set_defaults(func=_cmd_auto_search)

    # -- rerun-clean ---------------------------------------------------------
    p_rc = sub.add_parser(
        "rerun-clean",
        help="Move noisy run folders to _deprecated_noisy/ and log the amendment.",
    )
    p_rc.add_argument(
        "--pattern",
        required=True,
        help="Substring pattern to match run folder names (e.g. '2026-03-08' or 'openalex').",
    )
    p_rc.add_argument(
        "--rationale",
        default=None,
        help="Reason for deprecating these runs (logged to amendments_log.csv).",
    )
    p_rc.set_defaults(func=_cmd_rerun_clean)

    # -- generate-screening --------------------------------------------------
    p_gs = sub.add_parser(
        "generate-screening",
        help="Generate calibration + split screening Excel workbooks.",
    )
    p_gs.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducible sampling/splitting (default: 42).",
    )
    p_gs.set_defaults(func=_cmd_generate_screening)

    # -- compute-kappa -------------------------------------------------------
    p_ck = sub.add_parser(
        "compute-kappa",
        help="Compute Cohen's kappa from the calibration screening workbook.",
    )
    p_ck.add_argument(
        "--file", default=None,
        help="Path to calibration Excel (default: 05_screening/calibration_screening.xlsx).",
    )
    p_ck.set_defaults(func=_cmd_compute_kappa)

    # -- merge-screening -----------------------------------------------------
    p_ms = sub.add_parser(
        "merge-screening",
        help="Merge calibration + reviewer A/B screening into one decisions CSV.",
    )
    p_ms.set_defaults(func=_cmd_merge_screening)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    args.func(args)


if __name__ == "__main__":
    main()
