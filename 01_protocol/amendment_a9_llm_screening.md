# Protocol Amendment A9 - LLM-Based Screening

| Field | Value |
|-------|-------|
| Amendment ID | A9 |
| Date | 2026-03-13 |
| Protocol version | v3.5 |
| Sections affected | 8, 8c |
| Author | TVW |

## Summary

The AI-assisted screening tool was changed from ASReview active learning to LLM-based title and abstract classification via Azure OpenAI.

## Rationale

ASReview active learning did not discriminate effectively with the available calibration and validation labels. In practice, unlabeled records collapsed toward broad "include" predictions and did not provide a useful ranking or exclusion signal.

LLM-based classification does not require a training set. Each record is independently evaluated against the inclusion and exclusion criteria through a structured prompt that returns:

- a binary decision
- a confidence score
- a reason code aligned with the exclusion taxonomy
- a brief reasoning trace

## Current Implementation Notes

- The screening was run with `o4-mini` (OpenAI reasoning model) after evaluating
  `gpt-4.1-mini`, `DeepSeek-V3.2`, and `o4-mini`.
- `gpt-4.1-mini` was the first successful run (572 include, 17.7%).
- `DeepSeek-V3.2` failed due to rate limiting and token auth issues (94% ERR-LLM).
- `o4-mini` produced the final run (600 include, 18.6%, 0 errors).
- `llm-screen` supports either `AZURE_OPENAI_API_KEY` or keyless Azure AD auth via `az login`.
- Screening runs are resumable through `05_screening/llm_screening_checkpoint.json`.
- Per-record prompt and response metadata are logged to `05_screening/llm_screening_prompt_log.jsonl`.

## Changes

1. Added `tools/slr_toolkit/llm_screening.py` as a stdlib-only Azure OpenAI client.
2. Added the `llm-screen` CLI command as the primary LLM screening step.
3. Preserved downstream compatibility by continuing to write `ai_screening_decisions.csv`.
4. Added checkpoint and prompt-log artifacts for auditability and resumability.

## Unchanged Procedures

| Procedure | Status |
|-----------|--------|
| Human calibration (kappa >= 0.70) | Unchanged |
| Calibrate-then-split design | Unchanged |
| Held-out validation subset | Unchanged |
| AI validation (recall >= 0.95) | Unchanged |
| Discrepancy review | Unchanged |
| False-negative audit (10%) | Unchanged |
| Full-text screening (human) | Unchanged |

## Configuration

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment / model name |

## Transparency and Reporting

All LLM interactions are logged with timestamps, prompts, decisions, confidence scores, reason codes, and token counts. This supports reproducibility audits and AI-assisted review traceability.
