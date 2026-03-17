# SLR Protocol v1.0

## 0) Title and registration

**Title:** Gate-Based Quantum Computing in Finance: A Systematic Literature
Review and Practical Advantage Assessment Within a Mixed-Methods Research
Design

**Registration:** OSF registration pending update. Until the registration
record is finalized, the repository version history and amendments log are
the authoritative audit trail.
Protocol versioned in this repository with amendments tracked in the
authoritative log `amendments_log.csv`.

**Protocol version:** 3.7 (2026-03-17)

This SLR constitutes Phase 1a of a larger exploratory sequential
mixed-methods study (Creswell & Creswell, 2018). The full study also
includes semi-structured practitioner interviews (Phase 1b), cross-method
synthesis (Phase 2), and experimental validation (Phase 3). This protocol
governs only the SLR component.

---

## 0b) Position within overarching research design

This study follows an exploratory sequential mixed-methods design
(Creswell & Creswell, 2018), comprising four phases:

| Phase | Component | Scope |
|-------|-----------|-------|
| **1a** | Systematic literature review (this protocol) | Theoretical evidence mapping and advantage assessment |
| **1b** | Semi-structured practitioner interviews | Practitioner perspectives on quantum readiness in finance |
| **2** | Cross-method synthesis / triangulation | Convergence/divergence analysis of Phases 1a and 1b |
| **3** | Experimental validation | Quantum computing experiments on prioritised workloads |

Phases 1a and 1b run in parallel; their outputs feed jointly into Phase 2.

**Rationale:** The SLR provides systematic theoretical coverage but may
miss practical constraints and tacit industry knowledge that do not appear
in published literature. Semi-structured interviews capture practitioner
perspectives the literature may not reflect. Combining both before
experimental design ensures that experiments are both theoretically
grounded and practically relevant.

The remaining sections of this protocol govern only the SLR (Phase 1a).
Interview protocol, synthesis methodology, and experimental design are
documented separately.

**Reference:** Creswell, J. W., & Creswell, J. D. (2018). *Research
design: Qualitative, quantitative, and mixed methods approaches* (5th
ed.). Sage.

---

## 1) Review type

This protocol governs the systematic literature review component (Phase 1a)
of a larger mixed-methods study (see §0b). The SLR's design is independent
of the other study phases.

Systematic literature review with **tiered extraction**:

- **Scope:** Comprehensive survey of gate-based quantum computing
  applications in finance, combined with critical assessment of practical
  quantum advantage claims using the Hoefler et al. (2023) framework.
- **Tier 1 extraction (all included papers):** Structured evidence mapping —
  classification by problem family, quantum method, evaluation approach,
  hardware regime, and basic technical details. Produces a taxonomy and
  evidence map.
- **Tier 2 extraction (papers with quantitative evaluation):** Deep
  assessment of practical quantum advantage using the Hoefler et al. (2023)
  framework — crossover viability, end-to-end overhead accounting, classical
  baseline quality, I/O bottleneck analysis, and speedup characterisation.
  Produces a per-workload advantage assessment and gap analysis.

Papers without sufficient quantitative evaluation are not excluded but are
coded as `tier2_applicable = no`. They contribute to the evidence map
(Tier 1) but not to the advantage assessment (Tier 2).

---

## 1b) Positioning against prior reviews

Several prior reviews cover quantum computing in finance. This review
addresses gaps left by each:

- **Bunescu & Vârtei (2024)** — The only prior formal SLR; searched WoS +
  Scopus only; focused on bibliometric mapping without practical-advantage
  assessment; found 89% of papers focus on algorithm creation but only
  21/94 test on real financial data.
- **Herman et al. (2022/2023)** — Comprehensive expert survey (~300
  references); no formal search methodology (not a systematic review); no
  crossover feasibility analysis.
- **Orús et al. (2019)** — Heavily annealing-focused; published before the
  NISQ era matured; limited gate-based coverage.
- **Egger et al. (2020)** — IBM-centric industry perspective; not systematic;
  selective reference coverage.

This review is the first to (1) apply the Hoefler et al. (2023)
practical-advantage framework systematically to quantum finance literature,
(2) assess crossover viability and speedup sufficiency for each problem
family, and (3) combine comprehensive evidence mapping with a focused
practical-advantage assessment using tiered extraction within a single SLR.

Beyond methodological gaps in prior reviews, no prior study in this domain
has situated a systematic review within a mixed-methods design that
triangulates theoretical evidence with practitioner perspectives. By
combining the SLR with semi-structured interviews (Phase 1b), this study
can identify where academic findings converge with or diverge from industry
priorities — a gap that purely literature-based reviews cannot address.

---

## 2) Review questions

### PICO(S) framing

Following Kitchenham & Charters (2007, §2.4) adaptation of the PICO
framework for software engineering, the review scope is structured as:

| Element | Definition | This review |
|---------|-----------|-------------|
| **P** — Population | Studies under review | Primary studies of gate-based quantum computing applied to financial problems (2016–present) |
| **I** — Intervention | Technology/method evaluated | Gate-based quantum algorithms (QAOA, VQE, QAE, Grover, HHL, quantum walks, QML, etc.) and hybrid quantum-classical approaches |
| **C** — Comparison | Baseline/alternative | Classical algorithms and heuristics for the same financial workloads (assessed via Hoefler et al. 2023 baseline-quality criteria) |
| **O** — Outcome | Measured effect | Practical quantum advantage: Tier-1 crossover viability (≤ 2 weeks wall-clock), Tier-2 finance SLA feasibility, end-to-end speedup, resource cost |
| **S** — Study design | Eligible study types | Empirical evaluations, simulation studies, analytical proofs, algorithm proposals with complexity analysis, resource estimation studies |

**Evidence mapping:**
- RQ1: What gate-based quantum computing applications have been proposed or
  demonstrated for financial use cases?
- RQ2: What quantum algorithms and methods are used, and for which finance
  problem families?
- RQ3: What is the distribution of evaluation approaches (real hardware,
  simulation, analytical) and hardware regimes (NISQ, fault-tolerant)?

**Practical advantage assessment:**
- RQ4: For which financial workloads does the existing literature provide
  credible evidence of practical quantum advantage (Tier-1 crossover
  within ≤ 2 weeks wall-clock time)?
- RQ5: What are the dominant gaps in advantage claims — missing end-to-end
  overhead, weak classical baselines, unaccounted I/O bottleneck, or
  absent crossover estimates?

**Cross-cutting (answered in Phase 2 synthesis, not by the SLR alone):**
- RQ6: Where do the theoretical findings from the SLR converge with or
  diverge from practitioner assessments of quantum readiness and practical
  viability in finance?

*Note: RQ6 requires input from both the SLR and practitioner interviews.
It is listed here for completeness of the overarching research questions
but is not answerable from the SLR data alone.*

---

## 3) Objectives

1. Produce a comprehensive, reproducible evidence map of gate-based quantum
   computing research in finance (2016–present).
2. Classify and taxonomise the literature by problem family, quantum method,
   evaluation type, and hardware regime.
3. Critically assess quantum advantage claims using the Hoefler et al. (2023)
   practical advantage framework, focusing on Tier-1 crossover feasibility
   and Tier-2 finance-specific operational windows.
4. Identify evidence gaps and formulate a prioritised research agenda.
5. Provide structured SLR outputs (evidence map, advantage assessment, gap
   analysis) as inputs to the cross-method synthesis with practitioner
   interview findings (Phase 2) and subsequent experimental validation
   (Phase 3).

---

## 4) Scope boundaries

### Included

- **Topic:** Gate-based (circuit-model) quantum computing applied to financial
  problems, including hybrid quantum-classical approaches where the quantum
  component uses gate-based circuits.
- **Hardware regimes:** Both NISQ and fault-tolerant.
- **Study types:** Empirical evaluations, analytical proofs, simulation studies,
  algorithm proposals with complexity analysis, and resource estimation studies.
- **Time window:** 2016-01-01 to present. Rationale: meaningful gate-based
  quantum computing research in finance begins around 2016; earlier work is
  predominantly quantum annealing or purely theoretical.

### Grey literature policy

Included:
- Preprints (arXiv, SSRN) — tagged as is_preprint=1 throughout the pipeline.
- Technical reports and white papers from industry quantum computing groups
  (e.g., IBM Quantum, Google AI Quantum, JPMorgan, Goldman Sachs, QC Ware)
  when they contain sufficient methodological detail to be extractable
  (i.e., they meet inclusion criteria in §9).
- Workshop papers and extended abstracts — included if they contain a workload
  definition or method description; coded as `tier2_applicable = no` if they
  lack quantitative evaluation.

Excluded:
- Theses and dissertations (risk of duplicating published work; PhD
  theses are excluded because thesis-derived published papers are captured
  via snowballing).
- Blog posts, news articles, slide decks without accompanying papers.
- Patents (different evidence standard; not peer-reviewed or preprint-equivalent).

When a preprint and a peer-reviewed version of the same work both appear,
the peer-reviewed version is the canonical record. The preprint is linked
via `version_group_id` and retained for provenance but excluded from
synthesis counts to avoid double-counting.

Sensitivity analysis: synthesis findings will be re-computed excluding
preprint-only records to test robustness.

**Conference papers:** In computer science, conference proceedings
constitute primary publication venues (unlike health sciences where they
are considered grey literature). Conference papers indexed in Scopus,
IEEE Xplore, or ACM DL are treated as formal peer-reviewed literature
in this review.

### Excluded

- **Quantum annealing–only** studies (e.g., D-Wave without gate-based component).
- **Quantum-inspired classical algorithms** (e.g., tensor network methods)
  unless compared against a gate-based quantum implementation.
- **Non-finance applications** of quantum computing (e.g., chemistry, logistics)
  unless explicitly mapped to a financial use case.
- **Pure hardware** papers with no application context.
- **Surveys and review papers** — used for snowballing only, not included in
  synthesis.
- Non-English publications. Rationale: The quantum computing and quantitative
  finance research communities publish overwhelmingly in English. Non-English
  exclusion is applied at title/abstract screening using code EX-NOTEN.
  This restriction is reported per PRISMA-S (Rethlefsen et al., 2021).

---

## 5) Advantage framework

We adopt the practical quantum advantage framework of Hoefler et al. (2023):

- **Tier-1 crossover target:** The quantum solution must complete within
  ≤ 2 weeks wall-clock time on projected/available hardware, AND outperform
  the best available classical solution on equivalent hardware budget.
- **Tier-2 finance SLA reality check:** Even if Tier-1 is met, the result
  must be deliverable within finance-specific operational windows (overnight
  batch, intraday risk, real-time pricing).
- **End-to-end overhead:** Advantage claims must account for full pipeline
  costs — state preparation, oracle construction, measurement, classical
  pre/post-processing, I/O bandwidth — not just asymptotic query complexity.
- **Classical baseline quality:** The classical comparator must be
  state-of-the-art or at minimum a reasonable production-grade implementation,
  not a strawman.

---

## 6) Information sources

### Core databases (4 sources)

1. **Scopus** — multidisciplinary, strong CS and engineering coverage;
   indexes the majority of IEEE and ACM content.
2. **OpenAlex** — open scholarly graph (~250M works); captures nearly all
   WoS-indexed publications via Crossref metadata (Culbert et al. 2025).
3. **arXiv** — physics and CS preprints (primary channel for quantum
   computing research).
4. **Semantic Scholar** — cross-disciplinary discovery, citation graph for
   forward snowballing.

Four sources were selected to maximise coverage while using databases with
confirmed programmatic access. Scopus indexes the majority of IEEE and ACM
content; OpenAlex captures nearly all WoS-indexed publications via Crossref
metadata (Culbert et al. 2025). Direct searching of IEEE Xplore, ACM DL,
and Web of Science was therefore omitted without expected recall loss,
supported by the benchmark sensitivity check (§7b) and mandatory
snowballing (§7c).

**Coverage justification citations:**
- Alperin et al. (2024) — OpenAlex as superset of Scopus
- Culbert et al. (2025) — OpenAlex reference coverage vs WoS/Scopus
- Stansfield et al. (2025) — 98% recall in OpenAlex for evidence synthesis
- Bramer et al. (2017) — 4 databases achieving 98.3% recall in systematic
  reviews

**OpenAlex limitations:** Missing abstracts for some Springer Nature
content (since Nov 2022) and Elsevier content (since Nov 2024); imperfect
author disambiguation; no predatory journal filtering. These limitations
are partially mitigated by Scopus coverage (which includes Elsevier
abstracts) and arXiv (which provides full-text access for preprints).

### Supplementary methods

- **Backward snowballing:** Reference lists of all included studies (see §7c).
- **Forward snowballing:** Papers citing included studies via Semantic
  Scholar / OpenAlex citation data (see §7c).
- **Expert consultation:** Domain experts may suggest additional relevant papers.

---

## 7) Search strategy

### Block structure

Two-block Boolean strategy: **Quantum** AND **Finance**.

**Block 1 — Quantum (technology):**
```
"quantum computing" OR "quantum algorithm*" OR "quantum circuit*"
OR "gate-based quantum" OR "hybrid quantum-classical"
OR "variational quantum" OR QAOA OR VQE OR QAE
OR "quantum amplitude estimation"
OR "quantum phase estimation"
OR "Grover's algorithm" OR "Grover search"
OR "HHL algorithm" OR "Harrow-Hassidim-Lloyd"
OR "quantum linear system*"
OR "quantum walk*"
OR "quantum machine learning" OR "quantum neural network*"
OR "quantum error correction"
OR "fault-tolerant quantum" OR "fault tolerant quantum" OR NISQ
OR "quantum speedup" OR "quantum advantage"
OR "quantum annealing"
OR QMCI
```

**Block 2 — Finance (domain):**
```
finance OR financial OR "computational finance" OR "quantitative finance"
OR "portfolio optim*" OR "portfolio selection"
OR "portfolio management" OR "portfolio risk"
OR "asset allocation" OR "asset management"
OR "option pricing" OR "derivative pricing"
OR "financial derivative*" OR "structured product*"
OR "fixed income" OR "bond pricing"
OR "interest rate" OR "interest rate derivative*"
OR "credit risk" OR "market risk"
OR "counterparty risk" OR "liquidity risk"
OR "value at risk" OR VaR
OR "expected shortfall" OR CVaR
OR "credit valuation adjustment" OR CVA OR xVA
OR "potential future exposure" OR PFE
OR "Black-Scholes" OR Greeks
OR "credit scoring" OR "default prediction"
OR "fraud detection" OR "anti-money laundering"
OR "algorithmic trading" OR "trade execution"
OR "market microstructure"
OR "stock market" OR "stock price*"
OR "hedge fund" OR "financial hedging"
OR "financial engineering" OR "financial forecasting"
```

### Combined template

```
(Block 1) AND (Block 2)
```

Design rationale: We use a two-block strategy (Quantum AND Finance) without
a third methods/evaluation block at the search stage. Rationale: the SLR
requires broad capture for evidence mapping; filtering for evaluation depth
is applied at extraction (Tier 2 applicability), not at search. Adding
evaluation terms to the search string risks excluding papers that contain
relevant resource estimates or benchmarks but do not use standard evaluation
vocabulary in their titles/abstracts. This decision is consistent with
Okoli (2015, §4.2) who recommends erring toward recall at the search stage
and precision at the screening stage.

### Adaptation per database

Each database requires syntax adaptation (e.g., Scopus uses TITLE-ABS-KEY,
arXiv uses ti/abs prefixes, OpenAlex uses full-text search + concept
filters). Exact search strings executed per database are logged in
`02_search_logs/search_log.xlsx` per PRISMA-S requirements (Rethlefsen
et al. 2021).

### Date and language limits

- **Date filter:** 2016-01-01 to present (applied at search stage).
- **Language filter:** English only (applied at screening stage via EX-NOTEN).

---

## 7b) Benchmark sensitivity check

Before committing to full screening, we verify that the 4-database search
retrieves a set of known-relevant papers. A benchmark set of 20
known-relevant papers is compiled from prior surveys and the authors' own
reading (see `02_search_logs/benchmark_sensitivity_check.csv`). The 20
papers are selected to cover all 10 problem families, all listed quantum
methods, both hardware regimes (NISQ and fault-tolerant), and all
evaluation types.

**Target:** ≥ 95% recall on the benchmark set.

**Procedure:**
1. Compile the benchmark set from established references including:
   Herman et al. (2022/2023), Egger et al. (2020; 2021), Stamatopoulos
   et al. (2020), Stamatopoulos & Zeng (2024), Woerner & Egger (2019),
   Brandhofer et al. (2022), Orús et al. (2019), Chakrabarti et al.
   (2021), Barkoutsos et al. (2020), Rebentrost et al. (2018), Grossi
   et al. (2022), Alcazar et al. (2022), Slate et al. (2021), Yalovetzky
   et al. (2024), Emmanoulopoulos & Dimoska (2022), Matsakos & Nield
   (2024), Zoufal et al. (2019), and Ciceri et al. (2025).
2. Run all search queries against each database.
3. Check retrieval of each benchmark paper across all databases.
4. For any missed paper, determine whether snowballing (§7c) would catch it.
5. If recall < 95% and snowballing would not compensate, add targeted
   search terms or an additional database.
6. Report benchmark sensitivity results in the thesis methods chapter.

---

## 7c) Snowballing procedure

Snowballing follows the guidelines of Wohlin (2014).

**Start set:** All included papers after full-text screening.

**Backward snowballing:** Examine reference lists of all included papers.
For each reference, apply eligibility criteria (§9) at title/abstract
level, then full-text level for candidates.

**Forward snowballing:** Identify papers citing each included paper using
Semantic Scholar and/or OpenAlex citation data. Apply the same eligibility
criteria.

**Iteration stopping rule:** Continue snowball iterations until an
iteration yields 0 new included papers. Wohlin (2014) reports convergence
typically within 2–3 iterations.

**Screening criteria:** Snowballed candidates are screened using the same
inclusion/exclusion criteria as database-identified records (§9).

**PRISMA reporting:** Snowballed papers are reported separately in the
flow diagram under "Records identified from other methods" per PRISMA 2020
Figure 1. Tracking is documented in
`02_search_logs/snowball_log.csv`.

---

## 8) Screening and selection

### Process

Title/abstract screening is conducted by two independent human reviewers
(Reviewer A and Reviewer B) using a calibration-then-split design,
supplemented by an AI-assisted recall-safety-net layer. Full-text
screening remains exclusively human-led.

The AI-assisted layer is designed as a supplementary safety mechanism,
not a replacement for human screening. Its sole function is to identify
potential false negatives — records that human reviewers may have
excluded but that warrant re-examination. This asymmetric design is
consistent with current guidance from the joint position statement of
Cochrane, the Campbell Collaboration, JBI, and the Collaboration for
Environmental Evidence, which states that "evidence synthesists are
ultimately responsible for their evidence synthesis, including the
decision to use artificial intelligence (AI) and automation, and to
ensure adherence to legal and ethical standards" (Flemyng et al. 2025).
The design is further supported by the AHRQ evidence map on machine
learning tools for evidence synthesis (Adam et al. 2024; 2025 update),
which found that semi-automated abstract screening tools achieve a
median recall of 97% with a median 51% reduction in screening burden,
and recommended human oversight for all AI-assisted screening decisions.

**Step 1 — Human calibration round:** Both reviewers independently
screen the same random sample of 50 records. Cohen's κ is computed.
Target: κ ≥ 0.70 before proceeding. Disagreements are discussed,
borderline cases resolved, and criteria clarifications documented in
`05_screening/calibration_log.md`. If κ < 0.70, criteria are refined and
calibration is repeated on a fresh 50-record sample.

**Step 2 — AI configuration and prompt freeze:** After calibration, the
AI-assisted layer is configured as an LLM-based title/abstract
classifier via Azure OpenAI (see §8c). The screening prompt is frozen
before the main AI run begins. Unlike the earlier ASReview design, this
LLM workflow does **not** require training labels from the calibration
set; the calibration round is used to align the human reviewers, not to
train the AI.

**Step 3 — Held-out validation subset:** Before split screening begins,
a further random sample of ≥100 records (drawn from the non-calibration
pool) is set aside as a held-out validation subset. Both human reviewers
independently screen this subset using standard dual-screening. The LLM
also classifies this subset independently. Performance metrics are
computed on this subset (see §8c). Because the LLM workflow does not use
supervised training labels, the validation subset is reserved for
prospective performance evaluation rather than model training.

**Step 4 — Human split screening:** Once calibrated (κ ≥ 0.70), the
remaining records (excluding the calibration and validation sets) are
split equally between the two reviewers. Each reviewer screens their
assigned half independently.

**Step 5 — AI parallel screening:** The AI layer independently screens
the unique non-duplicate record set in parallel with human screening and
does not influence human decisions in real time. Because no training set
is required, the AI layer can also classify calibration and validation
records independently for audit and validation purposes. Each record
receives an AI inclusion/exclusion decision, a confidence score, an
exclusion reason code where applicable, and a brief rationale.

**Step 6 — Discrepancy resolution (AI-as-safety-net):** After both
human and AI screening are complete, discrepancies are reviewed as
follows:

- **AI = "include", Human = "exclude":** These records are manually
  re-examined by both human reviewers jointly. This is the primary
  function of the AI layer — catching potential false negatives.
- **AI = "include", Human = "include":** No action required (agreement).
- **AI = "exclude", Human = "include":** No action required; the human
  inclusion decision stands.
- **AI = "exclude", Human = "exclude":** No immediate action, but a
  random 10% sample of these records is audited (Step 7).

The human reviewers make the final inclusion/exclusion decision for all
records. The AI does not have autonomous decision-making authority at
any point.

**Step 7 — False-negative audit:** A random 10% sample of records
excluded by both the human reviewer and the AI is independently
re-screened by the second reviewer. The purpose is to estimate the
false-negative rate in the double-excluded set. If the audit reveals
≥5% of re-screened records should have been included, the full
double-excluded set is re-screened by both reviewers. Audit results are
reported in the thesis.

**Step 8 — Borderline escalation:** Uncertain cases (decision = `maybe`)
from any source — human or AI-flagged — are resolved jointly by both
reviewers. Resolutions are documented in the decision CSV `notes` column.

**Step 9 — Re-screening after time gap:** Each reviewer re-screens all
their *excluded* full-text papers after 2–4 weeks. Intra-rater
concordance rate is reported.

### Screening phases

1. **Title/abstract screening (AI-assisted):** Each record assessed
   against inclusion criteria (§9). Human decisions recorded in
   `05_screening/title_abstract_decisions.csv`. AI decisions recorded
   separately in `05_screening/ai_screening_decisions.csv`. Final
   decisions are always the human reviewers' decisions, potentially
   modified by the discrepancy resolution process (Step 6).

2. **Full-text screening (human only):** Records passing title/abstract
   screening are assessed at full-text level against the same inclusion
   criteria (§9). Full-text screening is conducted exclusively by human
   reviewers without AI assistance. This design choice follows current
   best practice, which is considerably more supportive of AI-assisted
   title/abstract triage than fully automated full-text assessment
   (Siemens et al. 2025; Flemyng et al. 2025). Decisions recorded in
   `05_screening/full_text_decisions.csv`, with mandatory exclusion
   reason codes for excluded records (see
   `05_screening/exclusion_reason_codes.md`). The tier distinction
   (`tier2_applicable`) is assigned during extraction, not during
   screening.

### Inter-rater reliability

We report Cohen's κ at the calibration checkpoint and human-AI agreement
metrics:

1. **Human calibration round:** Both reviewers independently screen the
   same ~50 records. Target: κ ≥ 0.70 before proceeding to split
   screening. If κ < 0.70, disagreements are discussed, criteria
   clarified, any clarifications logged as minor protocol amendments,
   and calibration repeated on a fresh 50-record sample.

2. **Human-AI agreement on validation subset:** On the held-out
   validation subset (≥100 records), we report: recall (sensitivity) of
   the AI model for human-included records, specificity, positive
   predictive value, and Cohen's κ between AI and human consensus
   decisions. Recall ≥ 0.95 on the validation subset is the minimum
   threshold for proceeding with the AI-as-safety-net workflow. If
   recall < 0.95, the AI prompt/model configuration is refined and
   re-evaluated, or the AI layer is abandoned and screening proceeds as
   purely human.

Calibration results (agreement rate, κ value, disagreements resolved,
criteria clarifications) are recorded in
`05_screening/calibration_log.md` when the finalized calibration log is
completed. AI validation results are recorded in
`05_screening/ai_validation_report.md` when the validation report is
generated.

### Pilot screening documentation

The calibration round serves a dual purpose: reliability testing and
criteria refinement. All calibration artefacts are retained:

- Calibration screening decisions: stored in
  `05_screening/calibration_decisions.csv`
- Calibration log: `05_screening/calibration_log.md` records agreement
  metrics, resolved disagreements, and any criteria clarifications once
  the finalized log is completed
- AI validation report: `05_screening/ai_validation_report.md` records
  model performance on the held-out validation subset once generated
- Criteria clarifications arising from calibration are logged as minor
  amendments in `01_protocol/amendments_log.csv` with type
  `calibration_refinement`

This creates a complete audit trail from initial criteria interpretation
through to final screening reliability, for both human and AI
components.

---

## 8b) Limitations of AI-assisted split-screening design

Split screening after calibration is more efficient than full dual
screening but means that each record (outside the calibration and
validation sets) is assessed by only one human reviewer. This is
mitigated by: (1) the calibration round establishing high inter-rater
agreement (κ ≥ 0.70) before splitting; (2) the AI recall-safety-net
independently flagging potential false negatives for human
re-examination; (3) borderline escalation ensuring uncertain cases are
resolved jointly; (4) the false-negative audit estimating the miss rate
in the double-excluded set; (5) re-screening after a time gap catching
inconsistencies.

The AI-assisted layer introduces its own limitations. LLM and
active-learning performance varies substantially by dataset, prompt
design, and review context (Delgado-Chaves et al. 2025; Adam et al.
2024). The AI model may exhibit systematic blind spots — for example,
consistently misclassifying records that use non-standard terminology
for quantum computing or finance concepts. The held-out validation
subset and the false-negative audit are designed to detect such
systematic errors, but cannot guarantee their complete absence. Human
reviewers remain the final decision-makers for all records, and the AI
layer is explicitly designed to add recall (catch missed papers), never
to subtract it (exclude papers without human review).

This design trades some complexity for substantially reduced
false-negative risk while maintaining human authority over all
inclusion/exclusion decisions. The limitation is reported transparently
in the thesis discussion chapter.

---

## 8c) AI tool specification and reporting commitments

### Tool specification

| Parameter | Value |
|-----------|-------|
| **Tool** | Custom `llm-screen` workflow implemented in `tools/slr_toolkit/llm_screening.py`, using the official `openai` SDK against the Azure OpenAI Responses API |
| **Model / deployment** | Azure OpenAI deployment specified at runtime via `AZURE_OPENAI_DEPLOYMENT` or `--deployment`; the current completed repository screening run used `gpt-5-mini` |
| **Input to AI** | Title, abstract, and `paper_id` for each record |
| **Output schema** | `decision` (include/exclude), `confidence` (0–1), `reason_code`, and one-sentence `reasoning` |
| **Prompting approach** | Single-record criterion-based classification against the protocol eligibility rules; prompt text frozen before the main run |
| **Training data** | None required |
| **Stopping rule** | Screen all pending unique records; interrupted runs resume from `05_screening/llm_screening_checkpoint.json` |
| **Authentication** | Azure OpenAI API key or keyless Azure AD authentication via `az login` |
| **Date of completed screening run in current repository artifacts** | 2026-03-16 (`ai_screening_decisions.csv` and prompt-log timestamps) |
| **Current completed run size** | 3,010 AI-classified unique records in `05_screening/ai_screening_decisions.csv` |
| **Reproducibility artifacts** | `05_screening/ai_screening_decisions.csv`, `05_screening/llm_screening_checkpoint.json`, and `05_screening/llm_screening_prompt_log.jsonl` |

The exact Azure OpenAI deployment name, endpoint family, and any
pricing assumptions are operational settings rather than methodological
design choices. They must therefore be reported with the executed run,
but the workflow itself remains deployment-agnostic as long as the same
screening prompt and output schema are preserved.

Models trialed during implementation included `gpt-4.1-mini`,
`DeepSeek-V3.2`, `o4-mini`, and `gpt-5-mini`. The current completed
repository screening run uses `gpt-5-mini`; prior trial runs are retained
only for provenance.

### Validation design

1. **Held-out validation subset:** ≥100 records randomly sampled from
   the non-calibration pool, dual-screened by both human reviewers and
   independently classified by the AI. Performance metrics computed:
   recall (primary metric), specificity, precision, F1, Cohen's κ
   (human-AI).

2. **Recall threshold:** AI recall ≥ 0.95 on the validation subset is
   required to proceed. This threshold is informed by the AHRQ evidence
   map finding that semi-automated screening tools achieve a median
   recall of 97% (Adam et al. 2024), and by the Delgado-Chaves et al.
   (2025) finding that well-calibrated LLMs can achieve recall between
   85% and 98% depending on domain and prompt design.

3. **False-negative audit:** 10% random sample of double-excluded
   records (both human and AI excluded) re-screened by the second
   reviewer. Estimated false-negative rate reported.

4. **Sensitivity analysis:** Synthesis findings are re-computed
   excluding records rescued by the AI safety net (i.e., records
   initially excluded by the human reviewer but re-included after AI
   flagging) to assess the AI layer's impact on the final included set.

### Reporting commitments (per PRISMA-trAIce)

The following items are reported in the thesis methods and results
chapters, following the PRISMA-trAIce checklist (Holst et al. 2025):

- **Title/abstract:** The use of AI-assisted screening is indicated in
  the methods chapter title and described in the abstract.
- **AI tool identification:** Tool name, version, model configuration,
  and all parameters documented (see table above).
- **Human-AI interaction:** The specific role of the AI (recall safety
  net only, not autonomous decision-maker) is described. The workflow
  diagram distinguishes human-screened from AI-flagged records.
- **Performance evaluation:** Recall, specificity, precision, F1, and
  Cohen's κ on the held-out validation subset are reported. The number
  of records flagged by the AI for human re-examination, and the
  outcome of that re-examination, are reported.
- **PRISMA flow:** The PRISMA flow diagram distinguishes between records
  excluded by human decision and records rescued by AI flagging,
  following the PRISMA-trAIce flow diagram template (Holst et al. 2025).
- **Limitations:** AI-specific limitations are discussed, including
  model blind spots, reproducibility constraints, and the scope of the
  validation design.
- **Data availability:** The AI decisions file, checkpoint, prompt log,
  frozen prompt text, and the validation subset results are archived in
  the repository.

### Ethical and data-handling considerations

Before uploading any bibliographic records (titles, abstracts, metadata)
to any AI tool, the following are confirmed:

- University AI/data policy compliance is confirmed before any external
  AI screening run is executed and should be documented in the thesis
  compliance notes
- No full-text PDFs or copyrighted content are uploaded to external AI
  services
- Only bibliographic metadata (title, abstract, authors, DOI) is
  processed
- If using a cloud-based LLM API, data processing agreements and terms
  of service are reviewed
- For Azure OpenAI screening, bibliographic metadata is transmitted to
  the configured Azure service; no full-text PDFs are uploaded

---

## 9) Eligibility criteria

### Inclusion criteria

A record is included if ALL of the following hold:
- Uses or proposes a gate-based quantum computing approach
- Addresses a financial application or use case
- Contains sufficient methodological detail to extract at least: problem
  family, quantum method, and evaluation type

### Tier 2 applicability

An included record is additionally flagged as `tier2_applicable = yes`
if it:
- Contains a quantitative evaluation (empirical, simulation, or analytical)
  of performance or resource requirements
- Makes or enables assessment of a quantum advantage claim (explicit or
  implicit via resource estimates)

Records not meeting Tier 2 criteria remain included and receive Tier 1
extraction. They are coded `tier2_applicable = no` and contribute to the
evidence map but not to the per-workload advantage assessment.

### Exclusion codes

Exclusion reasons are coded per `05_screening/exclusion_reason_codes.md`.
Mandatory for all full-text exclusions (PRISMA 2020 §13b).

---

## 10) Data extraction

### Codebook

Extraction fields are defined in the codebook
(`06_extraction/extraction_template.xlsx`, Codebook sheet). Key field groups:

- **Bibliographic:** paper_id, title, authors, year, venue, doi
- **Classification:** problem_family, quantum_method, evaluation_type,
  NISQ_vs_FT
- **Technical detail:** qubit_count, gate_depth, hardware_or_sim,
  dataset_description
- **Advantage assessment:** baseline_strength, advantage_claim,
  advantage_evidence
- **Hoefler framework (Tier 2 — papers with `tier2_applicable = yes`):**
  input_data_size, output_type, io_bottleneck_discussed,
  speedup_type_detailed, oracle_stateprep_cost_included,
  end_to_end_overhead, crossover_time_estimated, crossover_size_estimated,
  classical_baseline_detail, qubit_type, error_correction_model,
  t_count_or_gate_cost, shots_or_samples, tier1_achievable,
  tier2_finance_sla

### Extraction process

1. One reviewer extracts data for each included paper.
2. A second reviewer verifies a random 20% sample.
3. Discrepancies > 10% trigger full double-extraction.

---

## 11) Quality appraisal

Each included study is assessed on a rubric with the following dimensions
(scored 0 / 1 / 2), using risk-of-bias language per SEGRESS (Kitchenham
et al. 2023):

- **q_methodology:** Methodological rigour (algorithm description,
  mathematical correctness, implementation detail)
- **q_reproducibility:** Reproducibility (code availability, parameter
  reporting, data accessibility)
- **q_classical_baseline_risk:** Risk that a weak classical baseline
  inflates perceived quantum advantage (state-of-art baseline = 0
  [low risk], reasonable = 1, weak/none = 2 [high risk])
- **q_scalability:** Scalability analysis (asymptotic + concrete = 2,
  one of these = 1, neither = 0)
- **q_advantage_evidence_risk:** Risk that advantage claims lack
  sufficient evidence (end-to-end with overhead = 0 [low risk],
  partial = 1, asymptotic-only or none = 2 [high risk])
- **q_io_bottleneck:** I/O limitations acknowledged and addressed
- **q_crossover_framing:** Tier-1/Tier-2 crossover analysis present
- **q_end_to_end:** End-to-end overhead included

Studies are not excluded based on quality scores, but scores are used to
weight findings in synthesis and reported transparently.

---

## 11b) Domain-specific certainty-of-evidence framework

Per PRISMA 2020 (Item 13d), we assess the certainty of the body of evidence
for each synthesis finding using the following approach:

For evidence mapping outputs (Tier 1): We do not apply a formal
certainty-of-evidence framework, as the mapping outputs are descriptive
(frequency counts, taxonomy, evidence map). Instead, we report the
distribution of rubric scores across the included set and flag clusters
where evidence quality is uniformly low.

For advantage assessment outputs (Tier 2): Each synthesis finding (e.g.,
"Workload X shows plausible Tier-1 crossover") is rated on a three-level
certainty scale grounded in computational benchmarking criteria:

- **HIGH:** ≥3 independent studies, consistent findings, credible classical
  baselines (state-of-the-art), end-to-end overhead accounting, rubric
  average ≥ 1.5/2.0.
- **MODERATE:** 2+ studies with partial agreement, or rubric average
  1.0–1.5, or one key evaluation dimension missing.
- **LOW:** Single study, conflicting findings, rubric average < 1.0, or
  fundamental evaluation gaps (no baseline, no overhead).

Certainty ratings are reported alongside each synthesis finding in the
results tables and discussion. We explicitly state when a finding rests
on low-certainty evidence and flag it as requiring future work.

**Rationale:** Standard GRADE (Guyatt et al., 2008) was designed for
randomised clinical trials and lacks domain-appropriate indicators for
computational benchmarking. Our framework preserves GRADE's core logic —
consistency, directness, precision, risk of bias — while substituting
domain-relevant criteria following Kitchenham & Charters (2007) and Dybå &
Dingsøyr (2008).

---

## 11c) Reporting bias assessment

Publication bias is partially mitigated by the inclusion of preprints
(arXiv, SSRN) which capture negative or null results that may not reach
peer-reviewed venues. We assess reporting bias qualitatively by examining
whether included studies selectively report favourable metrics (e.g.,
reporting only best-case speedups, omitting overhead costs, using weak
classical baselines). Selective reporting indicators are captured in the
extraction codebook fields `end_to_end_overhead`,
`classical_baseline_detail`, and `speedup_constant_reported`.

---

## 12) Synthesis plan

### Evidence mapping synthesis (Tier 1)

- Descriptive statistics: counts by problem family, quantum method,
  evaluation type, hardware regime, year.
- Evidence map: matrix of problem family × quantum method, annotated
  with evaluation maturity.
- Trend analysis: publication volume over time, method adoption curves.

### Advantage assessment synthesis (Tier 2)

- Per-workload advantage assessment table: for each problem family,
  summarise the best available evidence on crossover viability.
- Gap analysis: identify which advantage claims lack end-to-end overhead,
  credible baselines, or crossover estimates.
- Narrative synthesis organised by Hoefler-framework dimensions.

Meta-analysis (statistical pooling) is not planned due to heterogeneity
of methods, metrics, and problem instances across studies.

### Outputs for cross-method synthesis

The SLR synthesis outputs — specifically the evidence map (problem family ×
quantum method matrix), the per-workload advantage assessment table, and the
gap analysis — serve as structured inputs to the Phase 2 cross-method
synthesis. In Phase 2, these outputs are compared against practitioner
interview themes in a convergence/divergence matrix to identify:
(a) workloads where theory and practice agree on viability,
(b) workloads where practitioners identify constraints not reflected in the
literature, (c) theoretically promising workloads that practitioners
consider impractical, and (d) practitioner-identified priorities
underrepresented in the literature. The Phase 2 synthesis methodology is
documented separately.

---

## 13) Reporting

This review follows:
- **PRISMA 2020** (Page et al., 2021) for reporting structure
- **PRISMA-S** (Rethlefsen et al., 2021) for search documentation
- **PRISMA-trAIce** (Holst et al., 2025) for transparent reporting of
  AI use in evidence synthesis
- **Okoli (2015)** for SLR methodology in information systems
- **vom Brocke et al. (2015)** for rigour in literature search

The PRISMA flow diagram is generated programmatically via
`python -m tools.slr_toolkit.cli prisma` and includes separate counts
for AI-flagged records per the PRISMA-trAIce flow diagram template.

---

## 14) Timeline and team

| Phase | Target |
|-------|--------|
| Protocol finalisation | Complete |
| Database searches | Complete for the current active runs (6,232 raw records in the 2026-03-14-v5 source exports; current master library contains 3,010 canonical records and 3,222 duplicates) |
| Screening (title/abstract) | — |
| Screening (full-text) | — |
| Data extraction | — |
| Quality appraisal | — |
| Synthesis and writing | — |
| Cross-method synthesis and experimental phases | Documented separately |

---

## 15) Amendments

All protocol amendments are logged in the authoritative file
`01_protocol/amendments_log.csv`.

Legacy narrative amendment notes are archived under `01_protocol/archive/`
for provenance only; they are supplementary and not the source of record.

Minor amendments (e.g., search string refinements, criteria clarifications
from calibration) should be added directly to `amendments_log.csv`.
Major amendments (e.g., scope changes, new databases, screening design
changes) should also be recorded in `amendments_log.csv`, with an optional
supplementary narrative note in `01_protocol/archive/` only if a longer
explanation is genuinely useful.
