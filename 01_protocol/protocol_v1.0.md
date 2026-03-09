# SLR Protocol v1.0

## 0) Title and registration

**Title:** Gate-Based Quantum Computing in Finance: A Two-Stage Systematic
Literature Review and Practical Advantage Assessment

**Registration:** Not pre-registered. Protocol versioned in this repository
with amendments tracked in `amendments_log.csv`.

**Protocol version:** 1.0 (updated v1.2, 2026-03-09)

---

## 1) Review type

Two-stage systematic literature review:

- **Stage A — Mapping Review:** Broad survey of gate-based quantum computing
  applications in finance. Produces a structured evidence map (taxonomy of
  problem families, quantum methods, evaluation approaches, and maturity).
- **Stage B — Focused SLR:** Deep assessment of practical quantum advantage
  claims, applying the Hoefler et al. (2023) framework to evaluate crossover
  viability, end-to-end overhead accounting, and classical baseline quality.

---

## 2) Review question(s)

**Stage A (mapping):**
- RQ1: What gate-based quantum computing applications have been proposed or
  demonstrated for financial use cases?
- RQ2: What quantum algorithms and methods are used, and for which finance
  problem families?
- RQ3: What is the distribution of evaluation approaches (real hardware,
  simulation, analytical) and hardware regimes (NISQ, fault-tolerant)?

**Stage B (focused):**
- RQ4: For which financial workloads does the existing literature provide
  credible evidence of practical quantum advantage (Tier-1 crossover
  within ≤ 2 weeks wall-clock time)?
- RQ5: What are the dominant gaps in advantage claims — missing end-to-end
  overhead, weak classical baselines, unaccounted I/O bottleneck, or
  absent crossover estimates?

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
  (i.e., they meet Stage A inclusion criteria in §9).
- Workshop papers and extended abstracts — included at Stage A if they contain
  a workload definition or method description; excluded at Stage B unless they
  provide quantitative evaluation.

Excluded:
- Theses and dissertations (risk of duplicating published work; captured
  via snowballing if the published version exists).
- Blog posts, news articles, slide decks without accompanying papers.
- Patents (different evidence standard; not peer-reviewed or preprint-equivalent).

When a preprint and a peer-reviewed version of the same work both appear,
the peer-reviewed version is the canonical record. The preprint is linked
via version_group_id and retained for provenance but excluded from synthesis
counts to avoid double-counting.

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

### Core databases (7 sources)

1. **Scopus** — multidisciplinary, strong CS and engineering coverage
2. **Web of Science (WoS)** — multidisciplinary, strong journal coverage
3. **IEEE Xplore** — primary venue for quantum computing conference papers
4. **ACM Digital Library** — computer science, algorithms, and systems
5. **arXiv** — physics and CS preprints (primary channel for quantum computing)
6. **SSRN** — finance and economics preprints
7. **Semantic Scholar** (supplementary coverage extension — cross-disciplinary
   grey literature and workshop papers)

Seven sources were selected to maximise coverage across the publication venues
where quantum finance research appears: physics (arXiv), computer science
(IEEE, ACM), multidisciplinary (Scopus, WoS), finance preprints (SSRN), and
cross-disciplinary discovery (Semantic Scholar).

### Supplementary methods

- **Backward snowballing:** Reference lists of included studies.
- **Forward snowballing:** Citing articles via Semantic Scholar / Google Scholar.
- **Expert consultation:** Domain experts may suggest additional relevant papers.

---

## 7) Search strategy

### Block structure

Two-block Boolean strategy: **Quantum** AND **Finance**.

**Block 1 — Quantum (technology):**
```
"quantum computing" OR "quantum algorithm" OR "quantum circuit"
OR "quantum gate" OR "variational quantum" OR QAOA OR VQE OR "quantum
amplitude estimation" OR QAE OR "Grover" OR HHL OR "quantum walk"
OR "quantum machine learning" OR "quantum annealing" OR "quantum
error correction" OR "fault-tolerant quantum" OR "quantum speedup"
OR "quantum advantage"
```

**Block 2 — Finance (domain):**
```
"finance" OR "financial" OR "portfolio optimization" OR "option pricing"
OR "risk analysis" OR "credit scoring" OR "fraud detection" OR "Monte
Carlo" OR "derivative" OR "asset allocation" OR "quantitative finance"
OR "Black-Scholes" OR "value at risk" OR VaR OR "market risk" OR
"credit risk" OR "algorithmic trading"
```

### Combined template

```
(Block 1) AND (Block 2)
```

Design rationale: We use a two-block strategy (Quantum AND Finance) without
a third methods/evaluation block at the search stage. Rationale: Stage A is
a mapping review requiring broad capture; filtering for evaluation depth is
applied at screening (Stage B eligibility criteria in §9), not at search.
Adding evaluation terms to the search string risks excluding papers that
contain relevant resource estimates or benchmarks but do not use standard
evaluation vocabulary in their titles/abstracts. This decision is consistent
with Okoli (2015, §4.2) who recommends erring toward recall at the search
stage and precision at the screening stage.

### Adaptation per database

Each database requires syntax adaptation (e.g., Scopus uses TITLE-ABS-KEY,
IEEE uses metadata fields, arXiv uses ti/abs prefixes). Exact search strings
executed per database are logged in `02_search_logs/search_log.xlsx` per
PRISMA-S requirements.

### Date and language limits

- **Date filter:** 2016-01-01 to present (applied at search stage).
- **Language filter:** English only (applied at screening stage via EX-NOTEN).

---

## 8) Screening and selection

### Process

Two-phase screening by two independent reviewers:

1. **Title/abstract screening:** Each record assessed against inclusion
   criteria (§9). Decisions recorded in
   `05_screening/title_abstract_decisions.csv`.
2. **Full-text screening:** Records passing title/abstract screening are
   assessed at full-text level. Decisions recorded in
   `05_screening/full_text_decisions.csv`, with mandatory exclusion reason
   codes for excluded records (see `05_screening/exclusion_reason_codes.md`).

### Conflict resolution

Where reviewers disagree, records are discussed and a consensus decision
reached. If consensus cannot be reached, a third reviewer adjudicates.
All conflicts and resolutions are documented in the decision files.

### Inter-rater reliability

We report Cohen's κ (kappa) at two checkpoints:

1. Calibration round: Both reviewers independently screen the same ~50 records.
   Target: κ ≥ 0.70 before proceeding to main screening.
   If κ < 0.70, reviewers discuss disagreements, clarify criteria, log any
   criteria clarifications as minor protocol amendments, and repeat calibration
   on a fresh 50-record sample.

2. Main screening: Reported on the full title/abstract overlap set.
   κ < 0.60 triggers a review of screening criteria and partial re-screening.

Calibration results (agreement rate, κ value, disagreements resolved,
criteria clarifications) are documented in 05_screening/calibration_log.md.

### Pilot screening documentation

The calibration round serves a dual purpose: reliability testing and
criteria refinement. All calibration artefacts are retained:

- Calibration screening decisions: stored in
  05_screening/calibration_decisions.csv (same format as
  title_abstract_decisions.csv)
- Calibration log: 05_screening/calibration_log.md (created above)
  documents agreement metrics, resolved disagreements, and any criteria
  clarifications
- Criteria clarifications arising from calibration are logged as minor
  amendments in 01_protocol/amendments_log.csv with type "calibration_refinement"

This creates a complete audit trail from initial criteria interpretation
through to final screening reliability.

---

## 9) Eligibility criteria

### Stage A — Mapping inclusion

A record is included at Stage A if ALL of the following hold:
- Uses or proposes a gate-based quantum computing approach
- Addresses a financial application or use case
- Contains sufficient methodological detail to extract at least: problem
  family, quantum method, and evaluation type

### Stage B — Focused SLR inclusion

A Stage A–included record is further included at Stage B if it:
- Contains a quantitative evaluation (empirical, simulation, or analytical)
  of performance or resource requirements
- Makes or enables assessment of a quantum advantage claim (explicit or
  implicit via resource estimates)

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
- **Hoefler framework (Stage B):** input_data_size, output_type,
  io_bottleneck_discussed, speedup_type_detailed,
  oracle_stateprep_cost_included, end_to_end_overhead,
  crossover_time_estimated, crossover_size_estimated,
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
(scored 0 / 1 / 2):

- **q_methodology:** Methodological rigour (algorithm description,
  mathematical correctness, implementation detail)
- **q_reproducibility:** Reproducibility (code availability, parameter
  reporting, data accessibility)
- **q_baseline:** Classical baseline quality (state-of-art = 2,
  reasonable = 1, weak/none = 0)
- **q_scalability:** Scalability analysis (asymptotic + concrete = 2,
  one of these = 1, neither = 0)
- **q_justification:** Advantage justification (end-to-end with overhead = 2,
  partial = 1, asymptotic-only or none = 0)
- **q_io_bottleneck:** I/O limitations acknowledged and addressed
- **q_crossover_framing:** Tier-1/Tier-2 crossover analysis present
- **q_end_to_end:** End-to-end overhead included

Studies are not excluded based on quality scores, but scores are used to
weight findings in synthesis and reported transparently.

---

## 11b) Certainty of evidence across studies

Per PRISMA 2020 (Item 13d), we assess the certainty of the body of evidence
for each synthesis finding using the following approach:

For Stage A (mapping): We do not apply a formal certainty-of-evidence
framework, as the mapping outputs are descriptive (frequency counts,
taxonomy, evidence map). Instead, we report the distribution of rubric
scores across the included set and flag clusters where evidence quality
is uniformly low.

For Stage B (focused synthesis): We adapt a simplified GRADE-like approach
for computational benchmarking studies. Each synthesis finding (e.g.,
"Workload X shows plausible Tier-1 crossover") is rated on a three-level
certainty scale:

- HIGH: ≥3 independent studies with rubric scores averaging ≥1.5/2.0,
  consistent findings, credible baselines, and end-to-end overhead accounting.
- MODERATE: 2+ studies with partial agreement, or rubric scores averaging
  1.0–1.5, or missing one key evaluation dimension.
- LOW: Single study, conflicting findings, rubric scores averaging <1.0,
  or fundamental evaluation gaps (no baseline, no overhead accounting).

Certainty ratings are reported alongside each synthesis finding in the
results tables and discussion. We explicitly state when a finding rests
on low-certainty evidence and flag it as requiring future work.

Rationale for simplified approach: Standard GRADE was designed for clinical
intervention studies. Computational benchmarking studies lack randomisation,
blinding, and clinical outcomes. Our adapted framework preserves the core
GRADE logic (consistency, directness, precision, risk of bias) while using
domain-appropriate indicators.

---

## 12) Synthesis plan

### Stage A synthesis

- Descriptive statistics: counts by problem family, quantum method,
  evaluation type, hardware regime, year.
- Evidence map: matrix of problem family × quantum method, annotated
  with evaluation maturity.
- Trend analysis: publication volume over time, method adoption curves.

### Stage B synthesis

- Per-workload advantage assessment table: for each problem family,
  summarise the best available evidence on crossover viability.
- Gap analysis: identify which advantage claims lack end-to-end overhead,
  credible baselines, or crossover estimates.
- Narrative synthesis organised by Hoefler-framework dimensions.

Meta-analysis (statistical pooling) is not planned due to heterogeneity
of methods, metrics, and problem instances across studies.

---

## 13) Reporting

This review follows:
- **PRISMA 2020** (Page et al., 2021) for reporting structure
- **PRISMA-S** (Rethlefsen et al., 2021) for search documentation
- **Okoli (2015)** for SLR methodology in information systems
- **vom Brocke et al. (2015)** for rigour in literature search

The PRISMA flow diagram is generated programmatically via
`python -m tools.slr_toolkit.cli prisma`.

---

## 14) Timeline and team

| Phase | Target |
|-------|--------|
| Protocol finalisation | Complete |
| Database searches | In progress |
| Screening (title/abstract) | — |
| Screening (full-text) | — |
| Data extraction | — |
| Quality appraisal | — |
| Synthesis and writing | — |

---

## 15) Amendments

All protocol amendments are logged in `01_protocol/amendments_log.csv` and
`01_protocol/amendments_log.md` with date, version, affected section(s),
description, rationale, and expected impact on results.

Minor amendments (e.g., search string refinements, criteria clarifications
from calibration) are logged with type "minor" or "calibration_refinement".
Major amendments (e.g., scope changes, new databases) are logged with type
"major" and require explicit justification.
