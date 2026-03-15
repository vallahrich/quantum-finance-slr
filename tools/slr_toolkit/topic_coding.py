"""LLM-assisted thematic coding for included papers."""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from collections import Counter
from itertools import combinations
from json import JSONDecodeError
from pathlib import Path

from . import config
from .llm_screening import (
    INPUT_COST_PER_1K,
    OUTPUT_COST_PER_1K,
    _AzureAPIError,
    _build_url,
    _call_azure_openai,
    _estimate_tokens,
    _extract_message_content,
    _load_checkpoint,
    _save_checkpoint,
    _append_prompt_log,
    _safe_float,
)
from .utils import atomic_write_text, ensure_dir

log = logging.getLogger(__name__)

CONTROLLED_TOPICS: list[str] = [
    "portfolio_optimization",
    "derivative_pricing",
    "risk_management",
    "fraud_and_detection",
    "forecasting_and_prediction",
    "trading_and_execution",
    "insurance_and_actuarial",
    "credit_and_lending",
    "quantum_ml_for_finance",
    "optimization_methods",
    "simulation_and_monte_carlo",
    "benchmarking_and_advantage",
]

METHOD_FAMILIES: list[str] = [
    "qaoa_or_optimization",
    "variational_or_vqe",
    "amplitude_estimation",
    "quantum_ml",
    "quantum_walk_or_search",
    "linear_systems_or_hhl",
    "hybrid_unspecified",
    "other_gate_based",
]

EVALUATION_TYPES: list[str] = [
    "simulator",
    "real_hardware",
    "analytical",
    "benchmark_comparison",
    "conceptual_only",
]

REVIEW_STATUS_DEFAULT = "draft_llm"
TOPIC_FIELDNAMES = [
    "paper_id",
    "title",
    "final_decision",
    "primary_topics",
    "secondary_topics",
    "emergent_topics",
    "application_area",
    "method_family",
    "evaluation_type",
    "llm_confidence",
    "llm_rationale",
    "review_status",
    "review_notes",
]

SYSTEM_PROMPT = (
    "You are assisting with thematic coding for a systematic literature review on "
    "gate-based quantum computing in finance. You must assign structured multi-label "
    "topic codes to already-included papers.\n\n"
    "Use the controlled topics first. A paper may belong to multiple controlled topics. "
    "Only use emergent topics if the controlled topics do not capture the main theme. "
    "Do not invent near-duplicates of controlled topics.\n\n"
    f"Controlled topics: {', '.join(CONTROLLED_TOPICS)}\n"
    f"Method families: {', '.join(METHOD_FAMILIES)}\n"
    f"Evaluation types: {', '.join(EVALUATION_TYPES)}\n\n"
    "Return ONLY a JSON object with this schema:\n"
    "{\n"
    '  "primary_topics": ["topic_a"],\n'
    '  "secondary_topics": ["topic_b"],\n'
    '  "emergent_topics": ["new_topic_if_needed"],\n'
    '  "application_area": "short free-text area",\n'
    '  "method_family": "one of the controlled method families",\n'
    '  "evaluation_type": "one of the controlled evaluation types",\n'
    '  "confidence": <float 0.0-1.0>,\n'
    '  "rationale": "one concise sentence"\n'
    "}"
)


def _build_user_prompt(record: dict[str, str]) -> str:
    return (
        f"Paper ID: {record.get('paper_id', '')}\n"
        f"Title: {record.get('title', '')}\n"
        f"Abstract: {record.get('abstract', '') or '(no abstract available)'}\n"
        f"Venue: {record.get('venue', '')}\n"
        f"Year: {record.get('year', '')}"
    )


def _normalize_topic_list(values: object, *, allow_emergent: bool = False) -> list[str]:
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
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        if not normalized:
            continue
        if allow_emergent or normalized in CONTROLLED_TOPICS:
            cleaned.append(normalized)
    return list(dict.fromkeys(cleaned))


def _parse_topic_response(raw_response: dict) -> dict[str, object]:
    choices = raw_response.get("choices", [])
    if not choices:
        raise ValueError("No choices in API response")

    content = _extract_message_content(choices[0].get("message", {}).get("content", ""))
    usage = raw_response.get("usage", {})

    try:
        payload = json.loads(content)
    except JSONDecodeError as exc:
        raise ValueError(f"Cannot parse JSON from model output: {content!r}") from exc

    primary_topics = _normalize_topic_list(payload.get("primary_topics"))
    secondary_topics = _normalize_topic_list(payload.get("secondary_topics"))
    emergent_topics = _normalize_topic_list(payload.get("emergent_topics"), allow_emergent=True)

    if not primary_topics and secondary_topics:
        primary_topics = [secondary_topics[0]]
        secondary_topics = secondary_topics[1:]

    method_family = str(payload.get("method_family", "")).strip().lower().replace(" ", "_")
    if method_family not in METHOD_FAMILIES:
        method_family = "other_gate_based"

    evaluation_type = str(payload.get("evaluation_type", "")).strip().lower().replace(" ", "_")
    if evaluation_type not in EVALUATION_TYPES:
        evaluation_type = "conceptual_only"

    try:
        confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    rationale = str(payload.get("rationale", "")).strip()

    return {
        "primary_topics": primary_topics,
        "secondary_topics": [t for t in secondary_topics if t not in primary_topics],
        "emergent_topics": emergent_topics,
        "application_area": str(payload.get("application_area", "")).strip(),
        "method_family": method_family,
        "evaluation_type": evaluation_type,
        "confidence": confidence,
        "rationale": rationale,
        "_usage": usage,
    }


def _fallback_topic_decision(reason: str) -> dict[str, object]:
    return {
        "primary_topics": [],
        "secondary_topics": [],
        "emergent_topics": ["needs_manual_review"],
        "application_area": "",
        "method_family": "other_gate_based",
        "evaluation_type": "conceptual_only",
        "confidence": 0.0,
        "rationale": reason,
        "_usage": {},
    }


def load_included_papers(
    input_path: Path | None = None,
    master_path: Path | None = None,
) -> list[dict[str, str]]:
    """Load final included papers and join them to master metadata."""
    if input_path is None:
        input_path = config.FT_DECISIONS_FILE
    if master_path is None:
        master_path = config.MASTER_RECORDS_CSV

    if not input_path.exists():
        raise FileNotFoundError(
            f"Full-text decisions file not found: {input_path}. "
            "Create it before running topic coding."
        )

    with open(input_path, encoding="utf-8", newline="") as f:
        included_ids = [
            row.get("paper_id", "")
            for row in csv.DictReader(f)
            if row.get("final_decision", "").strip().lower() == "include"
        ]

    if not included_ids:
        return []

    if not master_path.exists():
        raise FileNotFoundError(
            f"Master records file not found: {master_path}. Run build-master first."
        )
    with open(master_path, encoding="utf-8", newline="") as f:
        master_rows = list(csv.DictReader(f))
    master_map = {row.get("paper_id", ""): row for row in master_rows}

    joined: list[dict[str, str]] = []
    for paper_id in included_ids:
        row = master_map.get(paper_id, {})
        joined.append({
            "paper_id": paper_id,
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "venue": row.get("venue", ""),
            "year": row.get("year", ""),
            "final_decision": "include",
        })
    return joined


def estimate_topic_coding_cost(
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
        total_out += 120

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


def _load_existing_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _serialize_topic_row(record: dict[str, str], decision: dict[str, object]) -> dict[str, str]:
    return {
        "paper_id": record.get("paper_id", ""),
        "title": record.get("title", ""),
        "final_decision": "include",
        "primary_topics": json.dumps(decision["primary_topics"], ensure_ascii=False),
        "secondary_topics": json.dumps(decision["secondary_topics"], ensure_ascii=False),
        "emergent_topics": json.dumps(decision["emergent_topics"], ensure_ascii=False),
        "application_area": str(decision.get("application_area", "")),
        "method_family": str(decision.get("method_family", "")),
        "evaluation_type": str(decision.get("evaluation_type", "")),
        "llm_confidence": f"{float(decision.get('confidence', 0.0)):.4f}",
        "llm_rationale": str(decision.get("rationale", "")),
        "review_status": REVIEW_STATUS_DEFAULT,
        "review_notes": "",
    }


def write_topic_coding_csv(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    sorted_rows = sorted(rows, key=lambda row: _safe_float(row.get("llm_confidence", "0"), 0.0), reverse=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TOPIC_FIELDNAMES)
        writer.writeheader()
        writer.writerows(sorted_rows)


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


def generate_topic_summary(
    csv_path: Path | None = None,
    summary_path: Path | None = None,
) -> Path:
    if csv_path is None:
        csv_path = config.TOPIC_CODING_CSV
    if summary_path is None:
        summary_path = config.TOPIC_CODING_SUMMARY

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    topic_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    application_counts: Counter[str] = Counter()
    emergent_counts: Counter[str] = Counter()
    topic_pairs: Counter[tuple[str, str]] = Counter()
    topic_examples: dict[str, list[str]] = {}

    for row in rows:
        topics = _read_json_array(row.get("primary_topics", "")) + _read_json_array(row.get("secondary_topics", ""))
        topics = list(dict.fromkeys(topics))
        for topic in topics:
            topic_counts[topic] += 1
            topic_examples.setdefault(topic, [])
            if len(topic_examples[topic]) < 3 and row.get("title", ""):
                topic_examples[topic].append(row["title"])
        for pair in combinations(sorted(topics), 2):
            topic_pairs[pair] += 1

        for topic in _read_json_array(row.get("emergent_topics", "")):
            emergent_counts[topic] += 1

        method = row.get("method_family", "").strip()
        if method:
            method_counts[method] += 1

        app = row.get("application_area", "").strip()
        if app:
            application_counts[app] += 1

    report = [
        "# Topic Coding Summary",
        "",
        "Draft LLM-assisted thematic coding for included papers. Review before using in synthesis.",
        "",
        f"- Papers coded: {len(rows)}",
        "",
        "## Topic Frequency",
        "",
        "| Topic | Count | Example Titles |",
        "|-------|-------|----------------|",
    ]
    for topic, count in topic_counts.most_common():
        report.append(f"| {topic} | {count} | {'; '.join(topic_examples.get(topic, []))} |")

    report.extend([
        "",
        "## Method Family Frequency",
        "",
        "| Method Family | Count |",
        "|---------------|-------|",
    ])
    for method, count in method_counts.most_common():
        report.append(f"| {method} | {count} |")

    report.extend([
        "",
        "## Application Area Frequency",
        "",
        "| Application Area | Count |",
        "|------------------|-------|",
    ])
    for app, count in application_counts.most_common():
        report.append(f"| {app} | {count} |")

    report.extend([
        "",
        "## Topic Co-occurrence",
        "",
        "| Topic Pair | Count |",
        "|------------|-------|",
    ])
    for pair, count in topic_pairs.most_common(10):
        report.append(f"| {' + '.join(pair)} | {count} |")

    report.extend([
        "",
        "## Emergent Topics Needing Consolidation",
        "",
        "| Emergent Topic | Count |",
        "|----------------|-------|",
    ])
    for topic, count in emergent_counts.most_common():
        report.append(f"| {topic} | {count} |")

    atomic_write_text(summary_path, "\n".join(report) + "\n")
    return summary_path


def _screen_one_record(
    url: str,
    api_key: str,
    deployment: str,
    record: dict[str, str],
    *,
    use_ad_token: bool = False,
) -> dict[str, object]:
    user_prompt = _build_user_prompt(record)
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            raw = _call_azure_openai(
                url,
                api_key,
                deployment,
                SYSTEM_PROMPT,
                user_prompt,
                use_ad_token=use_ad_token,
            )
            return _parse_topic_response(raw)
        except (ValueError, JSONDecodeError) as exc:
            last_error = exc
            log.warning("Topic parse error for %s (attempt %d/3): %s", record.get("paper_id", ""), attempt + 1, exc)
            time.sleep(2)
        except _AzureAPIError as exc:
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

    return _fallback_topic_decision(f"Topic coding failed after 3 attempts: {last_error}")


def run_topic_coding(
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
    api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
    endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")

    if batch_size <= 0:
        raise ValueError("batch_size must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    if output_path is None:
        output_path = config.TOPIC_CODING_CSV
    if summary_path is None:
        summary_path = config.TOPIC_CODING_SUMMARY
    if checkpoint_path is None:
        checkpoint_path = config.TOPIC_CODING_CHECKPOINT
    if prompt_log_path is None:
        prompt_log_path = config.TOPIC_CODING_PROMPT_LOG

    records = load_included_papers(input_file)
    if max_records is not None:
        records = records[:max_records]
    if not records:
        raise ValueError("No included papers found for topic coding.")

    if estimate_only or dry_run:
        return estimate_topic_coding_cost(records)

    if not endpoint:
        raise RuntimeError("Azure OpenAI endpoint not set. Set AZURE_OPENAI_ENDPOINT or pass --endpoint.")
    if not deployment:
        raise RuntimeError("Azure OpenAI deployment not set. Set AZURE_OPENAI_DEPLOYMENT or pass --deployment.")

    use_ad_token = False
    if not api_key:
        from .llm_screening import _get_azure_ad_token
        try:
            _get_azure_ad_token()
            use_ad_token = True
            log.info("Using Azure AD token auth (no API key needed)")
        except RuntimeError:
            raise RuntimeError(
                "No API key and Azure AD auth unavailable. "
                "Either set AZURE_OPENAI_API_KEY / pass --api-key, "
                "or run 'az login' for keyless auth."
            )

    url = _build_url(endpoint, deployment)
    checkpoint = _load_checkpoint(checkpoint_path)
    screened_set = set(checkpoint.get("screened_ids", []))
    results = [row for row in _load_existing_rows(output_path) if row.get("paper_id") in screened_set]
    pending = [row for row in records if row.get("paper_id") not in screened_set]

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start : batch_start + batch_size]
        for record in batch:
            decision = _screen_one_record(url, api_key, deployment, record, use_ad_token=use_ad_token)
            usage = decision.pop("_usage", {})
            row = _serialize_topic_row(record, decision)
            results.append(row)
            _append_prompt_log(prompt_log_path, {
                "paper_id": record.get("paper_id", ""),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "user_prompt": _build_user_prompt(record),
                "primary_topics": json.loads(row["primary_topics"]),
                "secondary_topics": json.loads(row["secondary_topics"]),
                "emergent_topics": json.loads(row["emergent_topics"]),
                "application_area": row["application_area"],
                "method_family": row["method_family"],
                "evaluation_type": row["evaluation_type"],
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

    write_topic_coding_csv(output_path, results)
    generate_topic_summary(output_path, summary_path)
    return output_path
