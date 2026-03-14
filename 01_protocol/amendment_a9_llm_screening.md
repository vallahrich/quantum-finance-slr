# Protocol Amendment A9 — LLM-Based Screening

| Field               | Value                                      |
|---------------------|--------------------------------------------|
| **Amendment ID**    | A9                                         |
| **Date**            | 2026-03-13                                 |
| **Protocol version**| v3.5                                       |
| **Sections affected** | §8, §8c                                  |
| **Author**          | TVW                                        |

## Summary

The AI-assisted screening tool is changed from ASReview active-learning
classification to LLM-based classification via Azure OpenAI.

## Rationale

ASReview active learning failed to discriminate effectively with the
available 50 calibration + 100 validation labels.  All unlabelled records
were predicted as "include" with approximately 0.67 confidence, providing
no useful ranking or exclusion signal.  The active-learning approach
requires a substantially larger training set to converge, which conflicts
with the resource constraints of this review.

LLM-based classification via Azure OpenAI does not require a training set.
Each record is independently classified against the review's
inclusion/exclusion criteria through a structured prompt, returning a
binary decision (include/exclude), a confidence score (0–1), a reason code
matching the protocol's exclusion taxonomy, and a one-sentence reasoning
trace.

## Changes

1. **New module**: `tools/slr_toolkit/llm_screening.py` — stdlib-only
   Azure OpenAI client for title/abstract screening.
2. **New CLI command**: `llm-screen` — replaces `run-asreview` as the
   primary AI screening step.
3. **Output format**: identical `ai_screening_decisions.csv` with columns
   `paper_id`, `ai_decision`, `ai_rank`, `ai_confidence`, `reason_code`,
   `reasoning`.  The first four columns match the existing ASReview output
   schema exactly; the last two are additive and do not affect downstream
   consumers.
4. **Audit artefacts**:
   - `05_screening/llm_screening_checkpoint.json` — resume state.
   - `05_screening/llm_screening_prompt_log.jsonl` — per-record
     prompt/response log for PRISMA-trAIce compliance.

## Unchanged procedures

| Procedure                   | Status      |
|-----------------------------|-------------|
| Human calibration (κ ≥ 0.70)| Unchanged   |
| Calibrate-then-split design | Unchanged   |
| Held-out validation subset  | Unchanged   |
| AI validation (recall ≥ 0.95)| Unchanged  |
| Discrepancy review          | Unchanged   |
| False-negative audit (10%)  | Unchanged   |
| Full-text screening (human) | Unchanged   |

## Configuration

| Variable                    | Description                         |
|-----------------------------|-------------------------------------|
| `AZURE_OPENAI_API_KEY`      | Azure OpenAI API key                |
| `AZURE_OPENAI_ENDPOINT`     | Resource endpoint URL               |
| `AZURE_OPENAI_DEPLOYMENT`   | Deployment (model) name             |

## Transparency and reporting

All LLM interactions are logged to
`05_screening/llm_screening_prompt_log.jsonl` with timestamps, prompts,
decisions, confidence scores, reason codes, and token counts.  This
supports reproducibility auditing and PRISMA-trAIce compliance
(Holst et al. 2025).
