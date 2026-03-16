"""LLM-based title/abstract screening via Azure OpenAI.

Replaces ASReview active-learning step (Protocol Amendment A9).
Uses only stdlib (urllib + json) — no additional dependencies.

Output is backward-compatible with the existing downstream pipeline:
``ai_screening_decisions.csv`` with columns ``paper_id``, ``ai_decision``,
``ai_rank``, ``ai_confidence`` (plus ``reason_code`` and ``reasoning``).
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from json import JSONDecodeError
from pathlib import Path

from . import config
from .utils import atomic_write_text, ensure_dir, load_master_records, safe_float

log = logging.getLogger(__name__)

# ── Azure OpenAI pricing (USD per 1 K tokens) ───────────────────────────
# Default: gpt-5-mini pricing as of 2026-03-14. Adjust these for your deployment.
INPUT_COST_PER_1K: float = 0.00025  # $0.25 / 1M input tokens
OUTPUT_COST_PER_1K: float = 0.002   # $2.00 / 1M output tokens

# ── File paths ───────────────────────────────────────────────────────────
CHECKPOINT_FILE = config.SCREENING_DIR / "llm_screening_checkpoint.json"
PROMPT_LOG_FILE = config.SCREENING_DIR / "llm_screening_prompt_log.jsonl"
_DEFAULT_CHECKPOINT_STATE = {"screened_ids": [], "version": 1}
_VALID_REASON_CODES = {
    "INCLUDE", "EX-PARADIGM", "EX-NONFIN", "EX-NOMETHOD",
    "EX-TOOSHORT", "EX-NOTEN", "EX-OTHER", "ERR-LLM",
}

# ── Screening system prompt ──────────────────────────────────────────────
SYSTEM_PROMPT: str = (
    "You are an expert systematic-literature-review screener. "
    "Classify the paper below for a review on gate-based quantum computing "
    "applications in finance.\n\n"
    "INCLUSION CRITERIA (ALL must hold):\n"
    "1. Uses or proposes a gate-based quantum computing approach "
    "(QAOA, VQE, QAE, Grover, HHL, quantum walks, QML/QNN, "
    "hybrid quantum-classical, etc.)\n"
    "2. Addresses a financial application or use case "
    "(portfolio optimisation, option pricing, risk analysis, credit scoring, "
    "fraud detection, algorithmic trading, etc.)\n"
    "3. Contains enough methodological detail to extract: problem family, "
    "quantum method, evaluation type\n\n"
    "EXCLUSION RULES:\n"
    "- Quantum annealing ONLY (no gate-based component) -> EX-PARADIGM\n"
    "- Quantum-inspired classical algorithms -> EX-PARADIGM\n"
    "- Not finance (chemistry, logistics, biology, etc.) -> EX-NONFIN\n"
    "- Pure hardware / no financial application -> EX-NONFIN\n"
    "- Survey/review with no original method contribution -> EX-NOMETHOD\n"
    "- Poster / extended abstract with insufficient detail -> EX-TOOSHORT\n"
    "- Non-English -> EX-NOTEN\n\n"
    "WHEN IN DOUBT -> include (systematic reviews err toward recall).\n\n"
    "Respond with ONLY a JSON object (no markdown fences, no extra text):\n"
    "{\n"
    '  "decision": "include" or "exclude",\n'
    '  "confidence": <float 0.0-1.0>,\n'
    '  "reason_code": "INCLUDE | EX-PARADIGM | EX-NONFIN | EX-NOMETHOD '
    '| EX-TOOSHORT | EX-NOTEN | EX-OTHER",\n'
    '  "reasoning": "<one concise sentence>"\n'
    "}"
)


# ── Helpers ──────────────────────────────────────────────────────────────

class _AzureAPIError(Exception):
    """Azure OpenAI API error carrying the HTTP status code."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _build_user_prompt(title: str, abstract: str, paper_id: str) -> str:
    abstract_text = abstract.strip() if abstract.strip() else "(no abstract available)"
    return f"Paper ID: {paper_id}\nTitle: {title}\nAbstract: {abstract_text}"


def _build_url(endpoint: str, deployment: str) -> str:
    """Build the Azure OpenAI / AI Services chat completions URL.

    Supports three endpoint styles:
    - ``https://RESOURCE.openai.azure.com/openai/v1/``  (OpenAI-compatible)
    - ``https://RESOURCE.openai.azure.com``              (standard Azure OpenAI)
    - ``https://RESOURCE.cognitiveservices.azure.com``   (AI Services / MaaS)
    """
    endpoint = endpoint.rstrip("/")
    if "/openai/v1" in endpoint:
        return f"{endpoint}/chat/completions"
    return (
        f"{endpoint}/openai/deployments/{deployment}"
        f"/chat/completions?api-version=2025-01-01-preview"
    )


def _extract_message_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text", "")))
        return "".join(text_parts)
    return str(content or "")


# Re-export for backward compatibility (topic_coding imports this)
_safe_float = safe_float


def _normalize_reason_code(value: object, decision: str) -> str:
    raw = str(value or "").strip().upper()
    if raw in _VALID_REASON_CODES:
        return raw
    return "INCLUDE" if decision == "include" else "EX-OTHER"


# ── Azure AD token helper ────────────────────────────────────────────────

_cached_ad_token: dict | None = None  # {"token": str, "expires_on": float}


def _get_azure_ad_token() -> str:
    """Obtain a bearer token via ``az account get-access-token``.

    Uses the caller's existing ``az login`` session — no stored secrets.
    Tokens are cached until 2 minutes before expiry.
    """
    global _cached_ad_token  # noqa: PLW0603
    now = time.time()
    if _cached_ad_token and _cached_ad_token["expires_on"] - now > 120:
        return _cached_ad_token["token"]

    import shutil
    az_cmd = shutil.which("az") or shutil.which("az.cmd") or "az"

    try:
        result = subprocess.run(  # noqa: S603
            [az_cmd, "account", "get-access-token",
             "--resource", "https://cognitiveservices.azure.com",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Azure CLI ('az') not found. Install it or provide --api-key."
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"'az account get-access-token' failed.\n"
            f"Run 'az login' first.\n{exc.stderr.strip()}"
        )

    try:
        token_data = json.loads(result.stdout)
        token = token_data["accessToken"]
        # expires_on is a Unix timestamp (int/float)
        expires_on = float(token_data.get("expires_on", now + 3300))
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(
            f"Failed to parse 'az account get-access-token' output: {exc}"
        )
    if not token:
        raise RuntimeError(
            "Azure CLI returned an empty token.  Run 'az login' and retry."
        )

    # Cache with real expiry from az CLI
    _cached_ad_token = {"token": token, "expires_on": expires_on}
    log.info("Acquired Azure AD token via 'az account get-access-token'")
    return token


# ── Azure OpenAI client (stdlib only) ────────────────────────────────────

def _call_azure_openai(
    url: str,
    api_key: str,
    deployment: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 256,
    timeout: int = 120,
    use_ad_token: bool = False,
) -> dict:
    """Send a chat-completion request and return the parsed JSON response."""
    is_reasoning = "o1" in deployment or "o3" in deployment or "o4" in deployment
    
    if is_reasoning:
        body: dict = {
            "messages": [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_completion_tokens": max_tokens * 4,
        }
    else:
        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
    if "/openai/v1" in url:
        body["model"] = deployment

    data = json.dumps(body).encode("utf-8")
    if use_ad_token:
        token = _get_azure_ad_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    else:
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key,
        }

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise _AzureAPIError(
            f"HTTP {exc.code}: {exc.reason}\n{body_text}",
            status_code=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise _AzureAPIError(f"Connection error: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise _AzureAPIError(f"Timeout/connection error: {exc}") from exc


# ── Response parsing ─────────────────────────────────────────────────────

def _parse_llm_response(raw_response: dict) -> dict:
    """Extract and validate the structured screening decision."""
    choices = raw_response.get("choices", [])
    if not choices:
        raise ValueError("No choices in API response")

    content = _extract_message_content(choices[0].get("message", {}).get("content", ""))
    usage = raw_response.get("usage", {})

    try:
        decision = json.loads(content)
    except JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
        if match:
            decision = json.loads(match.group())
        else:
            raise ValueError(f"Cannot parse JSON from model output: {content!r}")

    if "decision" not in decision:
        raise ValueError(f"Missing 'decision' field: {decision}")

    dec = str(decision["decision"]).strip().lower()
    if dec == "borderline":
        dec = "include"
        decision["reasoning"] = (
            f"(borderline→include) {decision.get('reasoning', '')}"
        )
    elif dec not in ("include", "exclude"):
        raise ValueError(f"Invalid decision value: {dec!r}")
    decision["decision"] = dec

    confidence = decision.get("confidence", 0.5)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5
    decision["confidence"] = confidence

    decision["reason_code"] = _normalize_reason_code(
        decision.get("reason_code"), dec,
    )
    decision.setdefault("reasoning", "")
    decision["_usage"] = usage
    return decision


# ── Token / cost estimation ──────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """Approximate token count (~4 chars per token for English)."""
    return max(1, len(text) // 4)


def estimate_cost(
    records: list[dict[str, str]],
    *,
    input_cost_per_1k: float = INPUT_COST_PER_1K,
    output_cost_per_1k: float = OUTPUT_COST_PER_1K,
) -> dict:
    """Estimate screening cost without calling the API."""
    system_tokens = _estimate_tokens(SYSTEM_PROMPT)
    total_in = 0
    total_out = 0

    for rec in records:
        user_prompt = _build_user_prompt(
            rec.get("title", ""), rec.get("abstract", ""), rec.get("paper_id", ""),
        )
        total_in += system_tokens + _estimate_tokens(user_prompt)
        total_out += 80  # structured JSON response is ~60-100 tokens

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


# ── Checkpoint management ───────────────────────────────────────────────

def _load_checkpoint(path: Path) -> dict:
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
            if isinstance(state, dict):
                return {
                    "screened_ids": list(state.get("screened_ids", [])),
                    "version": state.get("version", 1),
                }
        except (OSError, JSONDecodeError) as exc:
            log.warning("Ignoring unreadable checkpoint %s: %s", path, exc)
    return dict(_DEFAULT_CHECKPOINT_STATE)


def _save_checkpoint(path: Path, state: dict) -> None:
    atomic_write_text(path, json.dumps(state, indent=2))


# ── Audit log ────────────────────────────────────────────────────────────

def _append_prompt_log(path: Path, entry: dict) -> None:
    ensure_dir(path.parent)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    for attempt in range(5):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            return
        except PermissionError:
            time.sleep(0.3 * (attempt + 1))
    # Last resort — skip this log entry rather than crash
    log.warning("Could not write prompt log entry for %s (OneDrive lock)", entry.get("paper_id", "?"))


# ── I/O helpers ──────────────────────────────────────────────────────────

def _load_records_for_screening() -> list[dict[str, str]]:
    """Load non-duplicate records from master_records.csv."""
    return load_master_records(unique_only=True)


def _load_existing_decisions(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def _rebuild_results_from_log(
    log_path: Path, screened_ids: set[str],
) -> list[dict[str, str]]:
    """Rebuild screening results from the prompt log (latest entry per paper)."""
    decisions: dict[str, dict[str, str]] = {}
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            pid = entry.get("paper_id", "")
            if pid in screened_ids:
                decisions[pid] = {
                    "paper_id": pid,
                    "ai_decision": entry.get("decision", ""),
                    "ai_confidence": f"{float(entry.get('confidence', 0)):.4f}",
                    "reason_code": entry.get("reason_code", ""),
                    "reasoning": entry.get("reasoning", ""),
                }
    log.info("Rebuilt %d results from prompt log", len(decisions))
    return list(decisions.values())


def _write_decisions_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write ai_screening_decisions.csv ranked by confidence descending."""
    ensure_dir(path.parent)
    sorted_rows = sorted(
        rows,
        key=lambda r: _safe_float(r.get("ai_confidence", "0"), 0.0),
        reverse=True,
    )
    fieldnames = [
        "paper_id", "ai_decision", "ai_rank", "ai_confidence",
        "reason_code", "reasoning",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rank, row in enumerate(sorted_rows, 1):
            writer.writerow({
                "paper_id": row.get("paper_id", ""),
                "ai_decision": row.get("ai_decision", ""),
                "ai_rank": rank,
                "ai_confidence": row.get("ai_confidence", ""),
                "reason_code": row.get("reason_code", ""),
                "reasoning": row.get("reasoning", ""),
            })


# ── Main entry point ────────────────────────────────────────────────────

def run_llm_screening(
    *,
    api_key: str | None = None,
    endpoint: str | None = None,
    deployment: str | None = None,
    batch_size: int = 10,
    delay: float = 1.0,
    max_records: int | None = None,
    dry_run: bool = False,
    estimate_only: bool = False,
    output_path: Path | None = None,
    checkpoint_path: Path | None = None,
    prompt_log_path: Path | None = None,
) -> Path | dict:
    """Screen title/abstract records via Azure OpenAI LLM classification.

    Writes ``ai_screening_decisions.csv`` compatible with downstream commands
    (``ai-validation``, ``ai-discrepancies``, ``fn-audit``).

    Returns
    -------
    Path
        Output CSV path (normal run).
    dict
        Cost-estimation dict (``estimate_only=True`` or ``dry_run=True``).
    """
    api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
    endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")

    if output_path is None:
        output_path = config.AI_SCREENING_DECISIONS
    if checkpoint_path is None:
        checkpoint_path = CHECKPOINT_FILE
    if prompt_log_path is None:
        prompt_log_path = PROMPT_LOG_FILE

    if batch_size <= 0:
        raise ValueError("batch_size must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    # ── Load records ─────────────────────────────────────────────────────
    records = _load_records_for_screening()
    if not records:
        log.warning("No records to screen (master_records.csv empty or missing)")
        print("[WARN] No records found in master library.")
        return output_path

    # ── Resume: determine already-screened IDs ───────────────────────────
    checkpoint = _load_checkpoint(checkpoint_path)
    screened_set: set[str] = set(checkpoint.get("screened_ids", []))

    # On resume, rebuild results from the prompt log (ground truth)
    # rather than the CSV which may have been truncated by a crash.
    if screened_set and prompt_log_path.exists():
        results = _rebuild_results_from_log(prompt_log_path, screened_set)
    elif screened_set:
        existing = _load_existing_decisions(output_path)
        results = [r for r in existing if r.get("paper_id") in screened_set]
    else:
        results = []

    pending = [r for r in records if r["paper_id"] not in screened_set]
    if max_records is not None:
        pending = pending[:max_records]

    log.info(
        "LLM screening: %d total, %d already done, %d pending",
        len(records), len(screened_set), len(pending),
    )

    # ── Cost estimation / dry-run ────────────────────────────────────────
    if estimate_only or dry_run:
        return estimate_cost(pending)

    # ── Validate credentials ─────────────────────────────────────────────
    use_ad_token = False
    if not api_key:
        # Try Azure AD auth via 'az login' session (keyless)
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
    if not endpoint:
        raise RuntimeError(
            "Azure OpenAI endpoint not set. "
            "Set AZURE_OPENAI_ENDPOINT or pass --endpoint."
        )
    if not deployment:
        raise RuntimeError(
            "Azure OpenAI deployment not set. "
            "Set AZURE_OPENAI_DEPLOYMENT or pass --deployment."
        )

    url = _build_url(endpoint, deployment)
    log.info("Azure OpenAI URL: %s", url)

    # ── Screen in batches ────────────────────────────────────────────────
    total_prompt_tokens = 0
    total_completion_tokens = 0
    processed = 0

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start : batch_start + batch_size]

        for rec in batch:
            pid = rec["paper_id"]
            user_prompt = _build_user_prompt(
                rec.get("title", ""), rec.get("abstract", ""), pid,
            )

            decision = _screen_one_record(
                url, api_key, deployment, user_prompt, pid,
                use_ad_token=use_ad_token,
            )

            usage = decision.pop("_usage", {})
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)

            # Audit log
            _append_prompt_log(prompt_log_path, {
                "paper_id": pid,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "user_prompt": user_prompt,
                "decision": decision["decision"],
                "confidence": decision["confidence"],
                "reason_code": decision.get("reason_code", ""),
                "reasoning": decision.get("reasoning", ""),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            })

            results.append({
                "paper_id": pid,
                "ai_decision": decision["decision"],
                "ai_confidence": f"{decision['confidence']:.4f}",
                "reason_code": decision.get("reason_code", ""),
                "reasoning": decision.get("reasoning", ""),
            })

            # Checkpoint after every record
            screened_set.add(pid)
            checkpoint["screened_ids"] = sorted(screened_set)
            _save_checkpoint(checkpoint_path, checkpoint)

            processed += 1
            if processed % 10 == 0:
                log.info("Progress: %d / %d", processed, len(pending))

        # Inter-batch delay
        if batch_start + batch_size < len(pending):
            time.sleep(delay)

    # ── Write final CSV ──────────────────────────────────────────────────
    _write_decisions_csv(output_path, results)

    n_incl = sum(1 for r in results if r.get("ai_decision") == "include")
    n_excl = len(results) - n_incl
    log.info(
        "LLM screening complete: %d processed (%d include, %d exclude). "
        "Tokens: %d prompt / %d completion -> %s",
        len(results), n_incl, n_excl,
        total_prompt_tokens, total_completion_tokens, output_path,
    )
    return output_path


def _screen_one_record(
    url: str, api_key: str, deployment: str, user_prompt: str, paper_id: str,
    *, use_ad_token: bool = False,
) -> dict:
    """Call the API with retries and return a parsed decision dict."""
    last_error: Exception | None = None

    for attempt in range(5):
        try:
            raw = _call_azure_openai(
                url, api_key, deployment, SYSTEM_PROMPT, user_prompt,
                use_ad_token=use_ad_token,
            )
            return _parse_llm_response(raw)

        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            log.warning("Parse error for %s (attempt %d/5): %s", paper_id, attempt + 1, exc)
            time.sleep(2)

        except _AzureAPIError as exc:
            last_error = exc
            code = exc.status_code or 0
            if code == 401 and use_ad_token:
                # Token expired — force refresh and retry
                global _cached_ad_token  # noqa: PLW0603
                _cached_ad_token = None
                log.warning("Token expired for %s, refreshing and retrying", paper_id)
                time.sleep(1)
            elif code == 429:
                wait = min(60, 2 ** (attempt + 2))
                log.warning("Rate-limited on %s, waiting %ds", paper_id, wait)
                time.sleep(wait)
            elif 500 <= code < 600:
                wait = min(30, 2 ** (attempt + 1))
                log.warning("Server error %d on %s, retrying in %ds", code, paper_id, wait)
                time.sleep(wait)
            elif code == 0:  # timeout / connection error
                wait = min(30, 2 ** (attempt + 1))
                log.warning("Timeout/connection on %s, retrying in %ds", paper_id, wait)
                time.sleep(wait)
            else:
                raise

    # All retries exhausted — err toward recall
    log.error("Failed to screen %s after 5 attempts: %s", paper_id, last_error)
    return {
        "decision": "include",
        "confidence": 0.0,
        "reason_code": "ERR-LLM",
        "reasoning": f"LLM screening failed after 5 attempts: {last_error}",
        "_usage": {},
    }
