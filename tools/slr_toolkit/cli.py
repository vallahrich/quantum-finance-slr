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

    paths = generate_screening_excels(
        seed=args.seed, validation_size=args.validation_size,
    )
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


def _cmd_export_asreview(args: argparse.Namespace) -> None:
    """Export records and prior labels for ASReview."""
    from .screening import export_asreview_dataset, export_asreview_labels

    labels_path = export_asreview_labels()

    # Count labels by source
    import csv as _csv
    cal_ids: set[str] = set()
    total_labels = 0
    if labels_path.exists():
        with open(labels_path, encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                cal_ids.add(row.get("paper_id", ""))
                total_labels += 1

    print(f"[ok] Prior labels exported: {labels_path.name} ({total_labels} labels)")

    dataset_path = export_asreview_dataset(exclude_ids=cal_ids)
    print(f"[ok] ASReview dataset exported: {dataset_path.name}")
    print(f"     {len(cal_ids)} labelled records excluded from dataset")
    print()
    print("Next steps:")
    print("  1. Import both files into ASReview LAB v2")
    print("  2. Use prior labels as training data (prior knowledge)")
    print("  3. Run active-learning screening")
    print("  4. Export results and run: slr_toolkit import-ai-decisions --file <export.csv>")


def _cmd_import_ai_decisions(args: argparse.Namespace) -> None:
    """Import AI screening results into the pipeline."""
    from .screening import import_ai_decisions

    output = import_ai_decisions(Path(args.file))
    print(f"[ok] AI decisions imported -> {output.name}")


def _cmd_ai_discrepancies(args: argparse.Namespace) -> None:
    """Compare human vs AI decisions and flag discrepancies."""
    from .screening import find_discrepancies

    human_path = Path(args.human_decisions) if args.human_decisions else None
    counts = find_discrepancies(human_decisions_path=human_path)
    print("[ok] Discrepancy analysis complete:")
    for dtype, n in sorted(counts.items()):
        print(f"  {dtype:20s}: {n}")

    ai_rescue = counts.get("ai_rescue", 0)
    if ai_rescue > 0:
        print(f"\n  ** {ai_rescue} records flagged for human re-review (AI=include, Human=exclude)")
        print("  Edit 05_screening/ai_discrepancy_review.csv to resolve these.")
    else:
        print("\n  No AI rescue cases found — human and AI screening are aligned.")


def _cmd_fn_audit(args: argparse.Namespace) -> None:
    """Generate false-negative audit sample."""
    from .screening import generate_fn_audit

    output = generate_fn_audit(audit_fraction=args.fraction, seed=args.seed)
    print(f"[ok] FN audit sample -> {output.name}")
    print("  Second reviewer should re-screen these records.")
    print("  If >=5% should have been included, re-screen all double-excluded records.")


def _cmd_run_asreview(args: argparse.Namespace) -> None:
    """Run ASReview active-learning simulation in-pipeline."""
    from .screening import run_asreview_simulate

    output = run_asreview_simulate(
        model=args.model,
        seed=args.seed,
        threshold=args.threshold,
    )
    print(f"[ok] ASReview simulation complete -> {output.name}")
    print("Next: slr-toolkit ai-discrepancies")


def _cmd_llm_screen(args: argparse.Namespace) -> None:
    """Run LLM-based title/abstract screening via Azure OpenAI."""
    from .llm_screening import run_llm_screening

    result = run_llm_screening(
        api_key=args.api_key,
        endpoint=args.endpoint,
        deployment=args.deployment,
        batch_size=args.batch_size,
        delay=args.delay,
        max_records=args.max_records,
        dry_run=args.dry_run,
        estimate_only=args.estimate_cost,
    )

    if isinstance(result, dict):
        # Cost estimation or dry-run output
        print("LLM Screening Cost Estimate:")
        print(f"  Records to screen:  {result['n_records']}")
        print(f"  Est. input tokens:  {result['est_input_tokens']:,}")
        print(f"  Est. output tokens: {result['est_output_tokens']:,}")
        print(f"  Est. total tokens:  {result['est_total_tokens']:,}")
        print(f"  Est. input cost:    ${result['est_input_cost_usd']:.4f}")
        print(f"  Est. output cost:   ${result['est_output_cost_usd']:.4f}")
        print(f"  Est. total cost:    ${result['est_total_cost_usd']:.4f}")
        print(f"  Pricing: ${result['input_cost_per_1k']}/1K in, "
              f"${result['output_cost_per_1k']}/1K out")
        if args.dry_run:
            print("\n  [dry-run] No API calls made.")
    else:
        print(f"[ok] LLM screening complete -> {result.name}")
        print("Next: slr-toolkit ai-validation")


def _cmd_ai_validation(args: argparse.Namespace) -> None:
    """Compute AI performance on the validation subset."""
    from .screening import compute_ai_validation

    metrics = compute_ai_validation()
    if metrics.get("error"):
        print(f"[FAIL] {metrics['error']}")
        return

    print("AI Validation Results (held-out subset):")
    print(f"  Records:    {metrics['n']}")
    print(f"  TP: {metrics['tp']}  FN: {metrics['fn']}  FP: {metrics['fp']}  TN: {metrics['tn']}")
    print(f"  Recall:     {metrics['recall']:.4f}")
    print(f"  Specificity:{metrics['specificity']:.4f}")
    print(f"  Precision:  {metrics['precision']:.4f}")
    print(f"  F1:         {metrics['f1']:.4f}")
    print(f"  Cohen's κ:  {metrics['kappa']:.4f}")
    print()
    if metrics["pass"]:
        print(f"  [ok] Recall = {metrics['recall']:.4f} >= 0.95 -- PASS")
        print("  Proceed with AI-as-safety-net workflow.")
    else:
        print(f"  [FAIL] Recall = {metrics['recall']:.4f} < 0.95 -- BELOW THRESHOLD")
        print("  Options: refine AI model or abandon AI layer.")
    print(f"\n  Full report: 05_screening/ai_validation_report.md")


def _cmd_topic_code(args: argparse.Namespace) -> None:
    """Run LLM-assisted thematic coding on final included papers."""
    from .topic_coding import generate_topic_summary, run_topic_coding

    result = run_topic_coding(
        api_key=args.api_key,
        endpoint=args.endpoint,
        deployment=args.deployment,
        batch_size=args.batch_size,
        delay=args.delay,
        max_records=args.max_records,
        dry_run=args.dry_run,
        estimate_only=args.estimate_cost,
        input_file=Path(args.input_file) if args.input_file else None,
    )

    if isinstance(result, dict):
        print("Topic Coding Cost Estimate:")
        print(f"  Records to code:    {result['n_records']}")
        print(f"  Est. input tokens:  {result['est_input_tokens']:,}")
        print(f"  Est. output tokens: {result['est_output_tokens']:,}")
        print(f"  Est. total tokens:  {result['est_total_tokens']:,}")
        print(f"  Est. input cost:    ${result['est_input_cost_usd']:.4f}")
        print(f"  Est. output cost:   ${result['est_output_cost_usd']:.4f}")
        print(f"  Est. total cost:    ${result['est_total_cost_usd']:.4f}")
        if args.dry_run:
            print("\n  [dry-run] No API calls made.")
        return

    summary_path = generate_topic_summary(result)
    print(f"[ok] Topic coding complete -> {result.name}")
    print(f"[ok] Topic summary generated -> {summary_path.name}")
    print("  Draft LLM coding only: review topic labels before using them in synthesis.")


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
        if dest.exists():
            raise FileExistsError(
                f"Cannot move {folder.name}: destination already exists at {dest}"
            )
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
    p_gs.add_argument(
        "--validation-size", type=int, default=100,
        help="Number of records for the held-out AI validation subset (default: 100).",
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

    # -- export-asreview -----------------------------------------------------
    p_ea = sub.add_parser(
        "export-asreview",
        help="Export records as ASReview-compatible CSV + prior labels.",
    )
    p_ea.set_defaults(func=_cmd_export_asreview)

    # -- run-asreview --------------------------------------------------------
    p_ra = sub.add_parser(
        "run-asreview",
        help="Run ASReview active-learning simulation and export AI decisions.",
    )
    p_ra.add_argument(
        "--model", default="elas_u4",
        help="ASReview model config name (default: elas_u4).",
    )
    p_ra.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    p_ra.add_argument(
        "--threshold", type=float, default=0.5,
        help="Probability threshold for AI include decision (default: 0.5).",
    )
    p_ra.set_defaults(func=_cmd_run_asreview)

    # -- import-ai-decisions -------------------------------------------------
    p_ia = sub.add_parser(
        "import-ai-decisions",
        help="Import AI screening results (e.g. ASReview export) into the pipeline.",
    )
    p_ia.add_argument(
        "--file", required=True,
        help="Path to AI decision export CSV (must have paper_id + label column).",
    )
    p_ia.set_defaults(func=_cmd_import_ai_decisions)

    # -- ai-discrepancies ----------------------------------------------------
    p_ad = sub.add_parser(
        "ai-discrepancies",
        help="Compare human vs AI screening decisions and flag discrepancies.",
    )
    p_ad.add_argument(
        "--human-decisions", default=None,
        help="Path to human decisions CSV (default: title_abstract_decisions.csv from merge-screening).",
    )
    p_ad.set_defaults(func=_cmd_ai_discrepancies)

    # -- fn-audit ------------------------------------------------------------
    p_fn = sub.add_parser(
        "fn-audit",
        help="Sample 10%% of double-excluded records for false-negative audit.",
    )
    p_fn.add_argument(
        "--fraction", type=float, default=0.10,
        help="Fraction of double-excluded records to sample (default: 0.10).",
    )
    p_fn.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducible sampling (default: 42).",
    )
    p_fn.set_defaults(func=_cmd_fn_audit)

    # -- ai-validation -------------------------------------------------------
    p_av = sub.add_parser(
        "ai-validation",
        help="Compute AI performance on the held-out validation subset.",
    )
    p_av.set_defaults(func=_cmd_ai_validation)

    # -- llm-screen ----------------------------------------------------------
    p_ls = sub.add_parser(
        "llm-screen",
        help="Run LLM-based title/abstract screening via Azure OpenAI.",
    )
    p_ls.add_argument(
        "--api-key", default=None,
        help="Azure OpenAI API key (default: AZURE_OPENAI_API_KEY env var).",
    )
    p_ls.add_argument(
        "--endpoint", default=None,
        help="Azure OpenAI endpoint URL (default: AZURE_OPENAI_ENDPOINT env var).",
    )
    p_ls.add_argument(
        "--deployment", default=None,
        help="Azure OpenAI deployment/model name (default: AZURE_OPENAI_DEPLOYMENT env var; recommended: gpt-5-mini).",
    )
    p_ls.add_argument(
        "--batch-size", type=int, default=10,
        help="Number of records per batch (default: 10).",
    )
    p_ls.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between batches (default: 1.0).",
    )
    p_ls.add_argument(
        "--max-records", type=int, default=None,
        help="Maximum number of records to screen (default: all pending).",
    )
    p_ls.add_argument(
        "--dry-run", action="store_true",
        help="Show cost estimate without calling the API.",
    )
    p_ls.add_argument(
        "--estimate-cost", action="store_true",
        help="Print token/cost estimate and exit.",
    )
    p_ls.set_defaults(func=_cmd_llm_screen)

    # -- topic-code ---------------------------------------------------------
    p_tc = sub.add_parser(
        "topic-code",
        help="Run LLM-assisted thematic coding on final included papers.",
    )
    p_tc.add_argument(
        "--input-file", default=None,
        help="Optional input CSV override. Default: 05_screening/full_text_decisions.csv.",
    )
    p_tc.add_argument(
        "--api-key", default=None,
        help="Azure OpenAI API key (default: AZURE_OPENAI_API_KEY env var).",
    )
    p_tc.add_argument(
        "--endpoint", default=None,
        help="Azure OpenAI endpoint URL (default: AZURE_OPENAI_ENDPOINT env var).",
    )
    p_tc.add_argument(
        "--deployment", default=None,
        help="Azure OpenAI deployment/model name (default: AZURE_OPENAI_DEPLOYMENT env var; recommended: gpt-5-mini).",
    )
    p_tc.add_argument(
        "--batch-size", type=int, default=10,
        help="Number of records per batch (default: 10).",
    )
    p_tc.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds to wait between batches (default: 1.0).",
    )
    p_tc.add_argument(
        "--max-records", type=int, default=None,
        help="Maximum number of included papers to code (default: all).",
    )
    p_tc.add_argument(
        "--dry-run", action="store_true",
        help="Show cost estimate without calling the API.",
    )
    p_tc.add_argument(
        "--estimate-cost", action="store_true",
        help="Print token/cost estimate and exit.",
    )
    p_tc.set_defaults(func=_cmd_topic_code)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    args.func(args)


if __name__ == "__main__":
    main()
