"""LLM-assisted tier classification for included papers.

Reads topic_coding.csv (or an interim file) and classifies each paper into
one or more tiers and groups using the tier definitions from the parent
quantum-finance project.

Output: 06_extraction/tier_classification.csv

Follows the same patterns as topic_coding.py: Azure OpenAI client,
checkpoint/resume, cost estimation, prompt logging.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from collections import Counter
from json import JSONDecodeError
from pathlib import Path

from . import config
from .azure_client import (
    AzureAPIError,
    AzureOpenAIClient,
    chat_completion,
    create_client,
)
from .llm_screening import (
    INPUT_COST_PER_1K,
    OUTPUT_COST_PER_1K,
    _estimate_tokens,
    _load_checkpoint,
    _save_checkpoint,
    _append_prompt_log,
)
from .utils import atomic_write_text, ensure_dir, safe_float

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier & group definitions
# ---------------------------------------------------------------------------

TIER1_GROUPS: list[str] = [
    "qc-industry",
    "computational-finance",
    "qc-in-finance-overview",
]

# Tier 2 groups = topic tags from unified taxonomy
TIER2_GROUPS: list[str] = [
    "portfolio-optimization",
    "derivative-pricing",
    "risk-management",
    "fraud-detection",
    "forecasting-prediction",
    "trading-execution",
    "insurance-actuarial",
    "credit-lending",
    "quantum-ml-finance",
    "optimization-methods",
    "simulation-monte-carlo",
    "benchmarking-advantage",
    "asset-pricing",
    "quantum-cryptography",
    "regulatory-compliance",
]

# Tier 3 groups = methodology tags from unified taxonomy
TIER3_GROUPS: list[str] = [
    "qaoa",
    "vqe",
    "amplitude-estimation",
    "quantum-ml",
    "quantum-walk",
    "hhl",
    "hybrid",
    "grover",
    "quantum-annealing",
    "quantum-svm",
    "qubo",
    "quantum-simulation",
    "classical-simulation",
    "other-gate-based",
]

REVIEW_STATUS_DEFAULT = "draft_llm"

TIER_FIELDNAMES = [
    "paper_id",
    "title",
    "tier1_groups",
    "tier2_groups",
    "tier3_groups",
    "llm_confidence",
    "llm_rationale",
    "review_status",
    "review_notes",
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are classifying papers for a systematic literature review on "
    "gate-based quantum computing in finance. Given a paper's title, abstract, "
    "existing topic codes, method family, and evaluation type, assign it to "
    "one or more tiers and groups.\n\n"
    "A paper CAN belong to MULTIPLE tiers and MULTIPLE groups within each tier. "
    "Tier membership is NOT mutually exclusive — a paper can be in Tier 1 AND "
    "Tier 2 AND Tier 3 simultaneously.\n\n"
    "## Tier 1 — General & Contextual\n"
    "Papers that provide overview, theoretical context, or foundational framing "
    "for quantum computing in finance.\n"
    "Classify here if ANY of the following apply:\n"
    "(1) The paper is a review, survey, tutorial, or position paper.\n"
    "(2) It discusses the QC industry, hardware roadmaps, or quantum advantage "
    "across multiple domains.\n"
    "(3) Its evaluation_type is conceptual_only.\n"
    "(4) Its evaluation_type is analytical — it provides theoretical proofs, "
    "complexity analyses, or analytical derivations (even if focused on one "
    "problem). These papers contribute foundational theory.\n"
    "Do NOT classify a paper in Tier 1 merely because it compares its quantum "
    "method against a classical baseline — that is standard experimental "
    "practice (Tier 2 + Tier 3). Tier 1 is for papers whose contribution is "
    "the overview, theory, or framing itself.\n"
    "Group guidance:\n"
    "- qc-industry: QC hardware, industry landscape, roadmaps, general QC surveys.\n"
    "- computational-finance: Computational/quantitative finance foundations, "
    "classical methods overviews, mathematical finance theory.\n"
    "- qc-in-finance-overview: QC-in-finance surveys, tutorials, analytical "
    "speedup proofs, theoretical complexity results.\n"
    f"Groups: {', '.join(TIER1_GROUPS)}\n\n"
    "## Tier 2 — Problem-Specific\n"
    "Papers focused on a specific financial problem domain.\n"
    "Classify here if the paper is framed around a specific financial problem, "
    "regardless of whether it includes an experiment.\n"
    f"Groups: {', '.join(TIER2_GROUPS)}\n\n"
    "## Tier 3 — Algorithm & Experiment\n"
    "Papers that implement and test quantum algorithms on finance problems with "
    "quantitative results (simulation or real QPU).\n"
    "Classify here if the paper runs experiments and reports quantitative results. "
    "Papers with only theoretical proofs (no experiments) do NOT belong here.\n"
    f"Groups: {', '.join(TIER3_GROUPS)}\n\n"
    "Return ONLY a JSON object with this schema:\n"
    "{\n"
    '  "tier1_groups": ["group_id", ...],\n'
    '  "tier2_groups": ["group_id", ...],\n'
    '  "tier3_groups": ["group_id", ...],\n'
    '  "confidence": <float 0.0-1.0>,\n'
    '  "rationale": "one concise sentence"\n'
    "}\n\n"
    "Use empty arrays [] for tiers that do not apply. "
    "Use only the exact group IDs listed above."
)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _build_user_prompt(record: dict[str, str]) -> str:
    return (
        f"Paper ID: {record.get('paper_id', '')}\n"
        f"Title: {record.get('title', '')}\n"
        f"Abstract: {record.get('abstract', '') or '(no abstract available)'}\n"
        f"Primary topics: {record.get('primary_topics', '')}\n"
        f"Secondary topics: {record.get('secondary_topics', '')}\n"
        f"Method family: {record.get('method_family', '')}\n"
        f"Evaluation type: {record.get('evaluation_type', '')}"
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _normalize_groups(values: object, valid_groups: list[str]) -> list[str]:
    """Normalize and validate group assignments."""
    if values is None:
        return []
    if isinstance(values, str):
        parsed = [values]
    elif isinstance(values, list):
        parsed = [str(v) for v in values]
    else:
        parsed = [str(values)]

    cleaned = []
    for value in parsed:
        normalized = value.strip().lower().replace(" ", "-").replace("_", "-")
        if normalized in valid_groups:
            cleaned.append(normalized)
    return list(dict.fromkeys(cleaned))


def _parse_tier_response(raw_response: dict) -> dict[str, object]:
    choices = raw_response.get("choices", [])
    if not choices:
        raise ValueError("No choices in API response")

    content = str(choices[0].get("message", {}).get("content") or "").strip()
    usage = raw_response.get("usage", {})

    try:
        payload = json.loads(content)
    except JSONDecodeError as exc:
        raise ValueError(f"Cannot parse JSON from model output: {content!r}") from exc

    tier1 = _normalize_groups(payload.get("tier1_groups"), TIER1_GROUPS)
    tier2 = _normalize_groups(payload.get("tier2_groups"), TIER2_GROUPS)
    tier3 = _normalize_groups(payload.get("tier3_groups"), TIER3_GROUPS)

    try:
        confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    rationale = str(payload.get("rationale", "")).strip()

    return {
        "tier1_groups": tier1,
        "tier2_groups": tier2,
        "tier3_groups": tier3,
        "confidence": confidence,
        "rationale": rationale,
        "_usage": usage,
    }


def _fallback_tier_decision(reason: str) -> dict[str, object]:
    return {
        "tier1_groups": [],
        "tier2_groups": [],
        "tier3_groups": [],
        "confidence": 0.0,
        "rationale": reason,
        "_usage": {},
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _read_json_array(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def load_topic_coded_papers(
    topic_csv: Path | None = None,
    master_csv: Path | None = None,
) -> list[dict[str, str]]:
    """Load topic-coded papers with metadata for tier classification.

    Reads topic_coding.csv for topic codes and method families.
    Joins with master_records.csv (if available) for abstracts,
    or falls back to title-only if master data is not available.
    """
    if topic_csv is None:
        topic_csv = config.TOPIC_CODING_CSV
    if master_csv is None:
        master_csv = config.MASTER_RECORDS_CSV

    if not topic_csv.exists():
        raise FileNotFoundError(
            f"Topic coding file not found: {topic_csv}. "
            "Run 'topic-code' before 'classify-tiers'."
        )

    with open(topic_csv, encoding="utf-8", newline="") as f:
        topic_rows = list(csv.DictReader(f))

    # Try to load abstracts from master records
    abstract_map: dict[str, str] = {}
    if master_csv.exists():
        with open(master_csv, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                pid = row.get("paper_id", "")
                if pid:
                    abstract_map[pid] = row.get("abstract", "")
        log.info("Loaded abstracts from %s (%d records)", master_csv, len(abstract_map))
    else:
        log.warning(
            "Master records not found at %s. "
            "Tier classification will proceed without abstracts.",
            master_csv,
        )

    records: list[dict[str, str]] = []
    for row in topic_rows:
        pid = row.get("paper_id", "")
        if not pid:
            continue
        records.append({
            "paper_id": pid,
            "title": row.get("title", ""),
            "abstract": abstract_map.get(pid, ""),
            "primary_topics": row.get("primary_topics", "[]"),
            "secondary_topics": row.get("secondary_topics", "[]"),
            "method_family": row.get("method_family", ""),
            "evaluation_type": row.get("evaluation_type", ""),
        })

    return records


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def _serialize_tier_row(record: dict[str, str], decision: dict[str, object]) -> dict[str, str]:
    return {
        "paper_id": record.get("paper_id", ""),
        "title": record.get("title", ""),
        "tier1_groups": json.dumps(decision["tier1_groups"], ensure_ascii=False),
        "tier2_groups": json.dumps(decision["tier2_groups"], ensure_ascii=False),
        "tier3_groups": json.dumps(decision["tier3_groups"], ensure_ascii=False),
        "llm_confidence": f"{float(decision.get('confidence', 0.0)):.4f}",
        "llm_rationale": str(decision.get("rationale", "")),
        "review_status": REVIEW_STATUS_DEFAULT,
        "review_notes": "",
    }


def write_tier_classification_csv(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    sorted_rows = sorted(
        rows,
        key=lambda row: safe_float(row.get("llm_confidence", "0"), 0.0),
        reverse=True,
    )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TIER_FIELDNAMES)
        writer.writeheader()
        writer.writerows(sorted_rows)


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def generate_tier_summary(
    csv_path: Path | None = None,
    summary_path: Path | None = None,
) -> Path:
    if csv_path is None:
        csv_path = config.TIER_CLASSIFICATION_CSV
    if summary_path is None:
        summary_path = config.TIER_CLASSIFICATION_SUMMARY

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    tier1_counts: Counter[str] = Counter()
    tier2_counts: Counter[str] = Counter()
    tier3_counts: Counter[str] = Counter()
    tier_assignment: Counter[str] = Counter()

    for row in rows:
        t1 = _read_json_array(row.get("tier1_groups", ""))
        t2 = _read_json_array(row.get("tier2_groups", ""))
        t3 = _read_json_array(row.get("tier3_groups", ""))

        for g in t1:
            tier1_counts[g] += 1
        for g in t2:
            tier2_counts[g] += 1
        for g in t3:
            tier3_counts[g] += 1

        tiers_present = []
        if t1:
            tiers_present.append("T1")
        if t2:
            tiers_present.append("T2")
        if t3:
            tiers_present.append("T3")
        tier_assignment["+".join(tiers_present) or "none"] += 1

    report = [
        "# Tier Classification Summary",
        "",
        "Draft LLM-assisted tier classification. Review before using for Zotero sync.",
        "",
        f"- Papers classified: {len(rows)}",
        "",
        "## Tier Assignment Distribution",
        "",
        "| Tier Combination | Count |",
        "|------------------|-------|",
    ]
    for combo, count in tier_assignment.most_common():
        report.append(f"| {combo} | {count} |")

    report.extend([
        "",
        "## Tier 1 — General Overview",
        "",
        "| Group | Count |",
        "|-------|-------|",
    ])
    for group, count in tier1_counts.most_common():
        report.append(f"| {group} | {count} |")
    if not tier1_counts:
        report.append("| (none) | 0 |")

    report.extend([
        "",
        "## Tier 2 — Problem-Specific",
        "",
        "| Group | Count |",
        "|-------|-------|",
    ])
    for group, count in tier2_counts.most_common():
        report.append(f"| {group} | {count} |")

    report.extend([
        "",
        "## Tier 3 — Algorithm & Experiment",
        "",
        "| Group | Count |",
        "|-------|-------|",
    ])
    for group, count in tier3_counts.most_common():
        report.append(f"| {group} | {count} |")

    atomic_write_text(summary_path, "\n".join(report) + "\n")
    return summary_path


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def estimate_tier_classification_cost(
    records: list[dict[str, str]],
    *,
    input_cost_per_1k: float = INPUT_COST_PER_1K,
    output_cost_per_1k: float = OUTPUT_COST_PER_1K,
) -> dict[str, float | int]:
    system_tokens = _estimate_tokens(SYSTEM_PROMPT)
    total_in = 0
    total_out = 0

    for rec in records:
        total_in += system_tokens + _estimate_tokens(_build_user_prompt(rec))
        total_out += 150  # tier response ~100-200 tokens

    input_cost = (total_in / 1000) * input_cost_per_1k
    output_cost = (total_out / 1000) * output_cost_per_1k
    return {
        "n_records": len(records),
        "est_input_tokens": total_in,
        "est_output_tokens": total_out,
        "est_total_tokens": total_in + total_out,
        "est_input_cost_usd": round(input_cost, 4),
        "est_output_cost_usd": round(output_cost, 4),
        "est_total_cost_usd": round(input_cost + output_cost, 4),
        "input_cost_per_1k": input_cost_per_1k,
        "output_cost_per_1k": output_cost_per_1k,
    }


# ---------------------------------------------------------------------------
# Single-record classification
# ---------------------------------------------------------------------------

def _classify_one_record(
    client: AzureOpenAIClient,
    record: dict[str, str],
) -> dict[str, object]:
    user_prompt = _build_user_prompt(record)
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            raw = chat_completion(
                client,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=512,
            )
            return _parse_tier_response(raw)
        except (ValueError, JSONDecodeError) as exc:
            last_error = exc
            log.warning(
                "Tier parse error for %s (attempt %d/3): %s",
                record.get("paper_id", ""), attempt + 1, exc,
            )
            time.sleep(2)
        except AzureAPIError as exc:
            last_error = exc
            code = exc.status_code or 0
            if code == 429:
                wait = min(60, 2 ** (attempt + 2))
                time.sleep(wait)
            elif 500 <= code < 600:
                wait = min(30, 2 ** (attempt + 1))
                time.sleep(wait)
            else:
                raise

    return _fallback_tier_decision(
        f"Tier classification failed after 3 attempts: {last_error}"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _load_existing_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run_tier_classification(
    *,
    api_key: str | None = None,
    endpoint: str | None = None,
    deployment: str | None = None,
    batch_size: int = 10,
    delay: float = 1.0,
    max_records: int | None = None,
    dry_run: bool = False,
    estimate_only: bool = False,
    input_file: Path | None = None,
    output_path: Path | None = None,
    summary_path: Path | None = None,
    checkpoint_path: Path | None = None,
    prompt_log_path: Path | None = None,
) -> Path | dict[str, float | int]:
    """Run tier classification on topic-coded papers.

    Returns the output CSV path on success, or a cost estimate dict
    if ``dry_run`` or ``estimate_only`` is set.
    """
    api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
    endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")

    if batch_size <= 0:
        raise ValueError("batch_size must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    if output_path is None:
        output_path = config.TIER_CLASSIFICATION_CSV
    if summary_path is None:
        summary_path = config.TIER_CLASSIFICATION_SUMMARY
    if checkpoint_path is None:
        checkpoint_path = config.TIER_CLASSIFICATION_CHECKPOINT
    if prompt_log_path is None:
        prompt_log_path = config.TIER_CLASSIFICATION_PROMPT_LOG

    records = load_topic_coded_papers(input_file)
    if max_records is not None:
        records = records[:max_records]
    if not records:
        raise ValueError("No topic-coded papers found for tier classification.")

    if estimate_only or dry_run:
        return estimate_tier_classification_cost(records)

    # Create SDK client
    client = create_client(endpoint=endpoint, api_key=api_key, deployment=deployment)

    checkpoint = _load_checkpoint(checkpoint_path)
    screened_set = set(checkpoint.get("screened_ids", []))
    results = [
        row for row in _load_existing_rows(output_path)
        if row.get("paper_id") in screened_set
    ]
    pending = [row for row in records if row.get("paper_id") not in screened_set]

    log.info(
        "Tier classification: %d already done, %d pending",
        len(results), len(pending),
    )

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start: batch_start + batch_size]
        for record in batch:
            decision = _classify_one_record(client, record)
            usage = decision.pop("_usage", {})
            row = _serialize_tier_row(record, decision)
            results.append(row)

            _append_prompt_log(prompt_log_path, {
                "paper_id": record.get("paper_id", ""),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "user_prompt": _build_user_prompt(record),
                "tier1_groups": json.loads(row["tier1_groups"]),
                "tier2_groups": json.loads(row["tier2_groups"]),
                "tier3_groups": json.loads(row["tier3_groups"]),
                "llm_confidence": row["llm_confidence"],
                "llm_rationale": row["llm_rationale"],
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            })

            screened_set.add(record.get("paper_id", ""))
            checkpoint["screened_ids"] = sorted(screened_set)
            _save_checkpoint(checkpoint_path, checkpoint)

        if batch_start + batch_size < len(pending):
            time.sleep(delay)

    write_tier_classification_csv(output_path, results)
    generate_tier_summary(output_path, summary_path)
    return output_path
