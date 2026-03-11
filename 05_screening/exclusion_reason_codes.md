# Exclusion Reason Codes (Full-Text Stage)

Use these codes in `full_text_decisions.csv` under `exclusion_reason`.

## Scope / paradigm
- **EX-PARADIGM** — Not gate-based (e.g., annealing-only, analog-only, quantum-inspired only)
- **EX-NONFIN** — Not finance and no explicit finance mapping

## Content / evidence
- **EX-NOMETHOD** — Insufficient method detail (cannot code)
- **EX-NOEVAL** — No evaluation/claim relevant to performance/advantage
- **EX-NOWORKLOAD** — No workload definition or finance task specification
- **EX-TOOSHORT** — Poster/extended abstract/slide deck with insufficient detail

## Duplicates / accessibility
- **EX-DUP** — Duplicate of another record (record `duplicate_of`)
- **EX-NOACCESS** — Full text unavailable after reasonable attempts (log attempt)

## Other
- **EX-NOTEN** — Non-English (if applied)
- **EX-OTHER** — Other (must explain in notes)

---

# Quick rule of thumb
- Screening is broad: only exclude for scope/paradigm/non-finance/insufficient to code.
- Papers without quantitative evaluation are NOT excluded — they are included
  and coded as `tier2_applicable = no`. They contribute to the evidence map
  but not to the advantage assessment.
- The Tier 2 flag is assigned during extraction, not during screening.
