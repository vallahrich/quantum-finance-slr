# Gate-Based Quantum Computing in Finance
## A Two-Stage Systematic Literature Review & Practical Advantage Assessment
### Presentation for Research Colleague

---

## Slide 1 — Title

**Gate-Based Quantum Computing in Finance:**
**A Two-Stage Systematic Literature Review & Practical Advantage Assessment**

- Presenter: [Your Name]
- Date: March 2026
- Protocol: OSF registered, version 2.0

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
3. Combine a **mapping review** (Stage A) with a **focused advantage analysis** (Stage B)

---

## Slide 3 — Two-Stage Design

### Stage A — Mapping Review (Broad)
- **Goal:** Comprehensive evidence map of gate-based QC in finance
- **Outputs:** Taxonomy of problem families, quantum methods, evaluation approaches, maturity levels
- **RQs:**
  - RQ1: What gate-based QC applications exist for finance?
  - RQ2: What algorithms are used, for which problem families?
  - RQ3: Distribution of evaluation approaches (real HW, simulation, analytical)?

### Stage B — Focused SLR (Deep)
- **Goal:** Critically assess practical quantum advantage claims
- **Outputs:** Per-workload advantage assessment, gap analysis
- **RQs:**
  - RQ4: Which financial workloads have credible evidence of practical quantum advantage?
  - RQ5: What are the dominant gaps? (missing overhead, weak baselines, no crossover estimates)

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

This is the **core analytical lens** for Stage B:

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

**Block 1 — Quantum:** "quantum computing", "quantum algorithm\*", "quantum circuit\*", "variational quantum", QAOA, VQE, QAE, Grover, HHL, "quantum walk\*", "quantum machine learning", "quantum error correction", "fault-tolerant quantum", "quantum speedup", "quantum advantage", "quantum annealing"

**Block 2 — Finance:** finance, financial, "quantitative finance", "portfolio optim\*", "portfolio selection", "option pricing", "derivative pricing", "financial derivative\*", "risk analysis", "credit risk", "market risk", VaR, "Black-Scholes", CVA, xVA, "Monte Carlo", "credit scoring", "fraud detection", "algorithmic trading", "asset allocation", "stock market", "stock price\*", "hedge fund", "financial hedging", "financial engineering"

### Design Rationale
- **No third evaluation block** at search stage
- Stage A = mapping → needs **broad capture** (recall > precision)
- Evaluation filtering applied at **screening** (Stage B criteria)
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
| OpenAlex | 4,709 |
| arXiv | 1,196 |
| Semantic Scholar | 874 |
| Scopus | 1,685 |
| **Total raw** | **8,464** |

### After Deduplication
- **4,750 unique records** in master library
- 3,714 duplicates removed (2,387 DOI-exact + 1,327 fuzzy title match)
- 2,280 preprint-published version groups identified
- Multiple search iterations refined query (amendments A1–A2: tightened noisy terms, all sources fetch complete result sets)

### Next Steps
- Run benchmark sensitivity check
- Begin title/abstract screening
- Calibration round with supervisor (target κ ≥ 0.70)

---

## Slide 9 — Screening & Quality Control

### Two-Reviewer Calibrate-Then-Split Design
1. **Calibration round:** Both reviewers independently screen same 50 records; compute Cohen's κ; target κ ≥ 0.70; discuss disagreements and clarify criteria
2. **Split screening:** Remaining ~4,700 records split equally between reviewers; each screens their half independently
3. **Borderline escalation:** `maybe` decisions resolved jointly by both reviewers
4. **Re-screening after time gap:** Each reviewer re-screens their excluded full-texts after 2–4 weeks

### Two Screening Phases
1. **Title/Abstract** — broad inclusion (Stage A criteria)
2. **Full-Text** — deeper assessment (Stage B criteria for advantage evaluation)

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
| Hoefler Framework | crossover_time, end_to_end_overhead, classical_baseline_detail, tier1_achievable, tier2_finance_sla |

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

### Stage A Outputs
- **Descriptive stats:** Counts by problem family, quantum method, evaluation type, year
- **Evidence map:** Problem family × quantum method matrix (annotated with maturity)
- **Trend analysis:** Publication volume over time, method adoption curves

### Stage B Outputs
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

---

## Slide 14 — Discussion Points for Colleague

- **Scope refinement:** Is the 2016 start date appropriate? Should we go earlier?
- **Search coverage:** 8,464 raw → 4,750 unique across 4 databases. Is coverage sufficient?
- **Advantage framework:** Is Hoefler et al. (2023) the right lens? Any alternatives?
- **Missing databases:** Are 4 sources sufficient, or should we add IEEE Xplore directly?
- **Stage B depth:** How many papers will realistically qualify for Stage B advantage assessment?
- **Practical value:** What would make this review most useful for the quantum computing community?

---

## Appendix A — PRISMA Flow (Expected Shape)

```
Identification:
  Database search → 8,464 raw records (4 sources)
  Other methods (snowballing) → TBD

Deduplication:
  → 4,750 unique records (3,714 duplicates removed)
  
Screening (Title/Abstract):
  → TBD excluded / TBD included
  
Screening (Full-Text):
  → TBD excluded (with reason codes) / TBD included Stage A
  
Stage B Filter:
  → TBD included in Stage B (quantitative advantage evaluation)
```

## Appendix B — Key References

- Hoefler et al. (2023) — "Disentangling Hype from Practicality: On Realistically Achieving Quantum Advantage"
- Herman et al. (2022/2023) — "A Survey of Quantum Computing for Finance"
- Bunescu & Vârtei (2024) — Only prior formal SLR in this space
- Egger et al. (2020) — "Quantum computing for finance: Overview and prospects"
- Page et al. (2021) — PRISMA 2020 guidelines
- Rethlefsen et al. (2021) — PRISMA-S search reporting
- Wohlin (2014) — Snowballing guidelines
- Okoli (2015) — SLR methodology in IS
- Kitchenham et al. (2023) — SEGRESS quality appraisal
