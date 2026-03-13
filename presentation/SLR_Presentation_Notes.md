# Gate-Based Quantum Computing in Finance
## A Systematic Literature Review Within a Mixed-Methods Research Design
### Presentation for Research Colleague

---

## Slide 1 — Title

**Gate-Based Quantum Computing in Finance:**
**A Systematic Literature Review Within a Mixed-Methods Research Design**

- Presenter: [Your Name]
- Date: March 2026
- Protocol: OSF registered, version 3.0

---

## Slide 2 — Why This Review?

### The Problem
- Quantum computing in finance is generating huge interest (portfolio optimisation, option pricing, risk analysis…)
- But: **how close are we to practical quantum advantage?**
- Many papers claim "quantum speedup" — but do they account for the **full pipeline cost**?

### Gap in Existing Literature
| Prior Review | Limitation |
|---|---|
| **Bunescu & Vârtei (2024)** | Only formal SLR so far; WoS + Scopus only; no advantage assessment |
| **Herman et al. (2022/2023)** | Comprehensive survey (~300 refs) but **not systematic** — no formal search methodology |
| **Orús et al. (2019)** | Pre-NISQ era; heavily annealing-focused |
| **Egger et al. (2020)** | IBM-centric; selective references |

### This Review Is the First To:
1. Apply the **Hoefler et al. (2023) practical-advantage framework** systematically to quantum finance literature
2. Assess **crossover viability** and **speedup sufficiency** for each problem family
3. Combine comprehensive **evidence mapping** with a focused **practical-advantage assessment** using tiered extraction within a single SLR
4. Situate the SLR within a **mixed-methods design** that triangulates theoretical evidence with practitioner perspectives

---

## Slide 2.5 — Overarching Research Design

This SLR is **Phase 1a** of a larger mixed-methods study:

| Phase | What | Output |
|-------|------|--------|
| **1a — SLR** (this presentation) | Evidence map + advantage assessment | Taxonomy, Hoefler evaluation, evidence gaps |
| **1b — Interviews** | Semi-structured interviews with finance practitioners | Practitioner priorities, constraints, tacit knowledge |
| **2 — Synthesis** | Triangulate SLR + interviews | Convergence/divergence matrix, prioritised workload shortlist |
| **3 — Experiments** | Quantum experiments on prioritised workloads | Empirical validation of advantage claims |

Why mixed-methods? SLR alone = comprehensive but potentially disconnected from practice. Interviews alone = rich but unsystematic. Combined = experiments grounded in both theory and practice.

---

## Slide 3 — SLR Design — Tiered Extraction

### Single SLR with Two Extraction Tiers

**Tier 1 — Evidence Mapping (all included papers)**
- **Goal:** Comprehensive evidence map of gate-based QC in finance
- **Outputs:** Taxonomy of problem families, quantum methods, evaluation approaches, maturity levels
- **RQs:**
  - RQ1: What gate-based QC applications exist for finance?
  - RQ2: What algorithms are used, for which problem families?
  - RQ3: Distribution of evaluation approaches (real HW, simulation, analytical)?

**Tier 2 — Advantage Assessment (papers with quantitative evaluation)**
- **Goal:** Critically assess practical quantum advantage claims using Hoefler framework
- **Outputs:** Per-workload advantage assessment, gap analysis
- **RQs:**
  - RQ4: Which financial workloads have credible evidence of practical quantum advantage?
  - RQ5: What are the dominant gaps? (missing overhead, weak baselines, no crossover estimates)

Papers without quantitative evaluation are coded `tier2_applicable = no` — they still contribute to the evidence map (Tier 1) but not to the advantage assessment (Tier 2).

---

## Slide 4 — Scope & Boundaries

### Included
- **Gate-based** (circuit-model) quantum computing — including hybrid quantum-classical
- Both **NISQ** and **fault-tolerant** regimes
- Empirical, analytical, simulation, algorithm proposals, resource estimation
- **Preprints** (arXiv, SSRN) — tagged as `is_preprint=1`
- Industry technical reports (IBM, JPMorgan, Goldman Sachs, QC Ware…) if sufficient detail
- **Time window:** 2016–present

### Excluded
- Quantum annealing–only (D-Wave without gate-based component)
- Quantum-inspired classical algorithms (unless compared to gate-based)
- Non-finance applications
- Pure hardware papers
- Surveys/reviews (used for snowballing only)
- Non-English publications
- Theses/dissertations

---

## Slide 5 — The Advantage Framework (Hoefler et al. 2023)

This is the **core analytical lens** for Tier 2 extraction:

### Tier-1 Crossover Target
> The quantum solution must complete within **≤ 2 weeks wall-clock time** on projected/available hardware, AND **outperform** the best available classical solution on equivalent hardware budget.

### Tier-2 Finance SLA Reality Check
> Even if Tier-1 is met, the result must be deliverable within **finance-specific operational windows** (overnight batch, intraday risk, real-time pricing).

### End-to-End Overhead
> Claims must account for **full pipeline costs**: state preparation, oracle construction, measurement, classical pre/post-processing, I/O bandwidth — not just asymptotic query complexity.

### Classical Baseline Quality
> The classical comparator must be **state-of-the-art**, not a strawman.

---

## Slide 6 — Information Sources (4 Databases)

| Database | Why? | Access |
|----------|------|--------|
| **Scopus** | Strong CS + engineering; indexes most IEEE/ACM | API (key required) |
| **OpenAlex** | Open graph ~250M works; captures nearly all WoS content | Free API |
| **arXiv** | Primary channel for QC preprints | Free API |
| **Semantic Scholar** | Citation graph for forward snowballing | Free API |

### Why Not WoS / IEEE / ACM Directly?
- OpenAlex captures nearly all WoS-indexed publications via Crossref metadata (Culbert et al. 2025)
- Scopus indexes the majority of IEEE and ACM content
- Validated by **benchmark sensitivity check** (§7b)
- Bramer et al. (2017): 4 databases achieve **98.3% recall** in systematic reviews

---

## Slide 7 — Search Strategy

### Two-Block Boolean Design

```
(Block 1: Quantum terms) AND (Block 2: Finance terms)
```

**Block 1 — Quantum:** "quantum computing", "quantum algorithm\*", "quantum circuit\*", "gate-based quantum", "hybrid quantum-classical", "variational quantum", QAOA, VQE, QAE, "quantum amplitude estimation", "quantum phase estimation", "Grover's algorithm", "Grover search", "HHL algorithm", "Harrow-Hassidim-Lloyd", "quantum linear system\*", "quantum walk\*", "quantum machine learning", "quantum neural network\*", "quantum error correction", "fault-tolerant quantum", "fault tolerant quantum", NISQ, "quantum speedup", "quantum advantage", "quantum annealing", QMCI

**Block 2 — Finance:** finance, financial, "computational finance", "quantitative finance", "portfolio optim\*", "portfolio selection", "portfolio management", "portfolio risk", "asset allocation", "asset management", "option pricing", "derivative pricing", "financial derivative\*", "structured product\*", "fixed income", "bond pricing", "interest rate", "interest rate derivative\*", "credit risk", "market risk", "counterparty risk", "liquidity risk", "value at risk", VaR, "expected shortfall", CVaR, "credit valuation adjustment", CVA, xVA, "potential future exposure", PFE, "Black-Scholes", Greeks, "credit scoring", "default prediction", "fraud detection", "anti-money laundering", "algorithmic trading", "trade execution", "market microstructure", "stock market", "stock price\*", "hedge fund", "financial hedging", "financial engineering", "financial forecasting"

### Design Rationale
- **No third evaluation block** at search stage
- Evidence mapping needs **broad capture** (recall > precision)
- Evaluation depth filtering applied at **extraction** (Tier 2 applicability)
- Consistent with Okoli (2015, §4.2)

### Benchmark Sensitivity Check
- 10 known-relevant papers from Herman et al., Egger et al., Stamatopoulos et al., etc.
- **Target: ≥ 95% recall** on benchmark set
- Validates that 4-database search doesn't miss key papers

---

## Slide 8 — Current Progress (as of March 10, 2026)

### Final Search Results (tightened query, 2026-03-10-v2)
| Source | Records |
|--------|---------|
| OpenAlex | 2,692 |
| arXiv | 496 |
| Semantic Scholar | 1,497 |
| Scopus | 1,090 |
| **Total raw** | **5,775** |

### After Deduplication
- **2,672 unique records** in master library
- 3,103 duplicates removed (2,270 DOI-exact + 833 fuzzy title match)
- 1,800 preprint-published version groups identified
- Multiple search iterations refined query (amendments A1–A5: tightened noisy terms, removed QMC-noise "Monte Carlo" and generic "risk analysis", replaced bare Grover/HHL, added QPE/QNN/fixed-income terms; all sources fetch complete result sets)

### Next Steps
- Run benchmark sensitivity check
- Begin title/abstract screening
- Calibration round (both reviewers screen 50 records, target κ ≥ 0.70)

---

## Slide 9 — Screening & Quality Control

### Two-Reviewer Calibrate-Then-Split Design
1. **Calibration round:** Both reviewers independently screen same 50 records; compute Cohen's κ; target κ ≥ 0.70; discuss disagreements and clarify criteria
2. **Split screening:** Remaining ~2,620 records split equally between reviewers; each screens their half independently
3. **Borderline escalation:** `maybe` decisions resolved jointly by both reviewers
4. **Re-screening after time gap:** Each reviewer re-screens their excluded full-texts after 2–4 weeks

### Screening Phases
1. **Title/Abstract** — broad inclusion against eligibility criteria (§9)
2. **Full-Text** — same criteria; Tier 2 applicability flag assigned during extraction, not screening

### Exclusion Reason Codes (PRISMA 2020 §13b)
- EX-PARADIGM (not gate-based), EX-NONFIN (not finance), EX-NOMETHOD, EX-NOEVAL, EX-DUP, etc.

---

## Slide 10 — Data Extraction & Quality Appraisal

### Extraction Codebook (Key Fields)
| Group | Example Fields |
|-------|---------------|
| Bibliographic | paper_id, title, authors, year, DOI |
| Classification | problem_family, quantum_method, evaluation_type, NISQ_vs_FT |
| Technical | qubit_count, gate_depth, hardware_or_sim |
| Tier 2 flag | tier2_applicable (yes/no) |
| Hoefler Framework (Tier 2) | crossover_time, end_to_end_overhead, classical_baseline_detail, tier1_achievable, tier2_finance_sla |

### Quality Rubric (0/1/2 scoring per SEGRESS)
- **q_methodology** — Methodological rigour
- **q_reproducibility** — Code/data availability
- **q_classical_baseline_risk** — Weak baseline risk
- **q_scalability** — Asymptotic + concrete analysis
- **q_advantage_evidence_risk** — Insufficient evidence risk
- **q_io_bottleneck** — I/O limitations acknowledged
- **q_crossover_framing** — Tier-1/Tier-2 analysis present
- **q_end_to_end** — Full overhead included

---

## Slide 11 — Synthesis Plan

### Tier 1 Outputs (Evidence Mapping)
- **Descriptive stats:** Counts by problem family, quantum method, evaluation type, year
- **Evidence map:** Problem family × quantum method matrix (annotated with maturity)
- **Trend analysis:** Publication volume over time, method adoption curves

### Tier 2 Outputs (Advantage Assessment)
- **Per-workload advantage table:** Best evidence on crossover viability per problem family
- **Gap analysis:** Which claims lack end-to-end overhead, credible baselines, crossover estimates
- **Narrative synthesis** organised by Hoefler-framework dimensions

### Certainty of Evidence (Domain-Adapted)
- **HIGH:** ≥3 studies, consistent findings, SOTA baselines, full overhead, rubric avg ≥ 1.5
- **MODERATE:** 2+ studies, partial agreement, or one key dimension missing
- **LOW:** Single study, conflicts, rubric avg < 1.0, or fundamental gaps

---

## Slide 12 — Reproducibility & Tooling

### Fully Automated Pipeline
- Custom **Python toolkit** (`slr_toolkit`) for end-to-end reproducibility
- API-driven search (OpenAlex, arXiv, Scopus, Semantic Scholar)
- Automated ingestion, normalisation, deduplication
- PRISMA count generation
- All raw JSON preserved for provenance

### Key Commands
```bash
python -m tools.slr_toolkit.cli auto-search ...   # Search APIs
python -m tools.slr_toolkit.cli build-master       # Deduplicate
python -m tools.slr_toolkit.cli prisma             # PRISMA counts
```

### Standards Compliance
- **PRISMA 2020** — Reporting structure
- **PRISMA-S** — Search documentation
- **Okoli (2015)** — SLR methodology in IS
- **vom Brocke et al. (2015)** — Rigour in literature search
- **OSF registration** — Protocol pre-registration

---

## Slide 13 — Expected Contributions

1. **First systematic application** of the Hoefler et al. (2023) practical-advantage framework to quantum finance literature
2. **Comprehensive evidence map** of gate-based QC in finance (2016–present)
3. **Honest assessment** of how far we are from practical quantum advantage in finance
4. **Prioritised research agenda** identifying the most promising problem families and the biggest evidence gaps
5. **Reproducible, open toolkit** for conducting SLRs with API-driven search
6. **Structured SLR outputs** designed to feed into cross-method synthesis with practitioner interviews and experimental validation

---

## Slide 14 — Discussion Points for Colleague

- **Scope refinement:** Is the 2016 start date appropriate? Should we go earlier?
- **Search coverage:** 5,775 raw → 2,672 unique across 4 databases. Is coverage sufficient?
- **Advantage framework:** Is Hoefler et al. (2023) the right lens? Any alternatives?
- **Missing databases:** Are 4 sources sufficient, or should we add IEEE Xplore directly?
- **Tier 2 depth:** How many papers will realistically qualify for Tier 2 advantage assessment?
- **Practical value:** What would make this review most useful for the quantum computing community?
- **Mixed-methods integration:** How should we weight SLR vs interview findings when they diverge?

---

## Appendix A — PRISMA Flow (Expected Shape)

```
Identification:
  Database search → 5,775 raw records (4 sources)
  Other methods (snowballing) → TBD

Deduplication:
  → 2,672 unique records (3,103 duplicates removed)

Screening (Title/Abstract):
  → TBD excluded / TBD included

Screening (Full-Text):
  → TBD excluded (with reason codes) / TBD included total

Tier 2 Applicability:
  → TBD with tier2_applicable = yes (Hoefler advantage assessment)
```

## Appendix B — Key References

- Hoefler et al. (2023) — "Disentangling Hype from Practicality: On Realistically Achieving Quantum Advantage"
- Herman et al. (2022/2023) — "A Survey of Quantum Computing for Finance"
- Bunescu & Vârtei (2024) — Only prior formal SLR in this space
- Egger et al. (2020) — "Quantum computing for finance: Overview and prospects"
- Creswell & Creswell (2018) — Research design for mixed-methods studies
- Page et al. (2021) — PRISMA 2020 guidelines
- Rethlefsen et al. (2021) — PRISMA-S search reporting
- Wohlin (2014) — Snowballing guidelines
- Okoli (2015) — SLR methodology in IS
- Kitchenham et al. (2023) — SEGRESS quality appraisal
