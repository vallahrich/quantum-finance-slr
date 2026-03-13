---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', sans-serif;
  }
  h1 {
    color: #0078d4;
  }
  h2 {
    color: #106ebe;
  }
  table {
    font-size: 0.75em;
  }
  .highlight {
    background-color: #fff3cd;
    padding: 0.5em;
    border-left: 4px solid #ffc107;
  }
---

# Gate-Based Quantum Computing in Finance

## A Systematic Literature Review Within a Mixed-Methods Research Design

**Presenter:** [Your Name]
**Date:** March 2026

---

# Motivation

**Quantum computing + finance** = one of the most-hyped application areas

- Portfolio optimisation, option pricing, risk analysis, fraud detection…
- Many claims of "quantum speedup" — but **are they realistic?**

### The key question:

> **For which financial workloads does credible evidence of practical quantum advantage actually exist?**

---

# Gap in Existing Reviews

| Review | Coverage | Limitation |
|--------|----------|------------|
| Bunescu & Vârtei (2024) | 94 papers; WoS + Scopus | No advantage assessment |
| Herman et al. (2022) | ~300 refs | Not systematic (no formal search) |
| Orús et al. (2019) | Broad survey | Annealing-focused; pre-NISQ era |
| Egger et al. (2020) | IBM perspective | Selective; not systematic |

### **No prior review** applies a practical-advantage framework systematically

---

# Our Contribution

### First to combine:

1. **Hoefler et al. (2023) practical-advantage framework** applied systematically to QC-finance literature

2. Comprehensive **evidence mapping** + focused **practical-advantage assessment** via tiered extraction

3. **Crossover viability assessment** per problem family

4. **Mixed-methods design** triangulating SLR with practitioner interviews

5. **Reproducible, API-driven** search pipeline (open toolkit)

---

# Overarching Research Design

This SLR is **Phase 1a** of a larger mixed-methods study:

| Phase | What | Output |
|-------|------|--------|
| **1a — SLR** | Evidence map + advantage assessment | Taxonomy, Hoefler evaluation, gaps |
| **1b — Interviews** | Practitioner interviews | Priorities, constraints, tacit knowledge |
| **2 — Synthesis** | Triangulate SLR + interviews | Convergence/divergence matrix |
| **3 — Experiments** | Quantum experiments | Empirical validation |

**Why?** SLR = systematic but potentially disconnected from practice. Interviews = rich but unsystematic. **Combined** = experiments grounded in both.

---

# SLR Design — Tiered Extraction

## Tier 1 — Evidence Mapping (all included papers)
- *What's out there?*
- Evidence map: problem families × quantum methods × maturity
- Papers without quantitative evaluation coded `tier2_applicable = no`

## Tier 2 — Advantage Assessment (quantitative papers)
- *Where is practical advantage credible?*
- Hoefler framework assessment per workload
- Only papers with `tier2_applicable = yes`

---

# Scope

| Dimension | Decision |
|-----------|----------|
| **Paradigm** | Gate-based (circuit-model) only |
| **Includes** | NISQ + fault-tolerant; preprints; industry reports |
| **Excludes** | Annealing-only; quantum-inspired; non-finance |
| **Time window** | 2016 – present |
| **Language** | English only |
| **Grey lit** | arXiv/SSRN preprints ✓ &nbsp; Theses/patents ✗ |
| **Research context** | Phase 1a of mixed-methods design |

---

# The Advantage Framework
## Hoefler et al. (2023)

### Tier-1 Crossover
Quantum must complete within **≤ 2 weeks** wall-clock AND **beat** best classical on equivalent budget

### Tier-2 Finance SLA
Must fit **real operational windows**: overnight batch, intraday risk, real-time pricing

### End-to-End Overhead
State prep + oracle + measurement + classical pre/post + I/O — **not just query complexity**

### Classical Baseline
Must compare against **state-of-the-art** — not a strawman

---

# Information Sources

| Database | Role | Access |
|----------|------|--------|
| **Scopus** | Core CS/engineering index | API (key) |
| **OpenAlex** | ~250M works; covers WoS content | Free |
| **arXiv** | QC preprints (primary channel) | Free |
| **Semantic Scholar** | Citation graph (snowballing) | Free |

**Why not WoS/IEEE/ACM directly?**
- OpenAlex ⊃ WoS (Culbert et al. 2025)
- Scopus ⊃ most IEEE + ACM
- 4 databases → **98.3% expected recall** (Bramer et al. 2017)
- Validated by benchmark sensitivity check

---

# Search Strategy

## Two-block Boolean: Quantum AND Finance

**Block 1 (Quantum):** `"quantum computing"`, `"quantum algorithm*"`, `"quantum circuit*"`, `"gate-based quantum"`, `"hybrid quantum-classical"`, `"variational quantum"`, `QAOA`, `VQE`, `QAE`, `"quantum amplitude estimation"`, `"quantum phase estimation"`, `"Grover's algorithm"`, `"Grover search"`, `"HHL algorithm"`, `"Harrow-Hassidim-Lloyd"`, `"quantum linear system*"`, `"quantum walk*"`, `"quantum machine learning"`, `"quantum neural network*"`, `"quantum error correction"`, `"fault-tolerant quantum"`, `"fault tolerant quantum"`, `NISQ`, `"quantum speedup"`, `"quantum advantage"`, `"quantum annealing"`, `QMCI`

**Block 2 (Finance):** `finance`, `financial`, `"computational finance"`, `"quantitative finance"`, `"portfolio optim*"`, `"portfolio selection"`, `"portfolio management"`, `"portfolio risk"`, `"asset allocation"`, `"asset management"`, `"option pricing"`, `"derivative pricing"`, `"financial derivative*"`, `"structured product*"`, `"fixed income"`, `"bond pricing"`, `"interest rate"`, `"interest rate derivative*"`, `"credit risk"`, `"market risk"`, `"counterparty risk"`, `"liquidity risk"`, `"value at risk"`, `VaR`, `"expected shortfall"`, `CVaR`, `"credit valuation adjustment"`, `CVA`, `xVA`, `"potential future exposure"`, `PFE`, `"Black-Scholes"`, `Greeks`, `"credit scoring"`, `"default prediction"`, `"fraud detection"`, `"anti-money laundering"`, `"algorithmic trading"`, `"trade execution"`, `"market microstructure"`, `"stock market"`, `"stock price*"`, `"hedge fund"`, `"financial hedging"`, `"financial engineering"`, `"financial forecasting"`

### Design choice: no third block
- Evidence mapping needs broad capture → **maximise recall** at search, **precision** at screening
- Per Okoli (2015, §4.2)

---

# Current Numbers

| Source | Records |
|--------|---------|
| OpenAlex | 2,692 |
| arXiv | 496 |
| Semantic Scholar | 1,497 |
| Scopus | 1,090 |
| **Total raw** | **5,775** |
| **After deduplication** | **2,672** |
| Duplicates (DOI + fuzzy) | 3,103 |

### Query refinement (Amendments A1–A5)
- Tightened noisy bare terms (e.g. `derivative*` → `"derivative pricing"`, `trading` → `"algorithmic trading"`)
- A5: Removed `"Monte Carlo"` (QMC noise), `"risk analysis"` (generic); replaced bare `Grover`/`HHL` with quoted phrases; added QPE, QNN, fixed-income terms
- Uncapped result sets per SLR completeness (Kitchenham & Charters 2007)
- All sources fetched completely — no API-cap truncation

---

# Screening Process

### Two reviewers — calibrate then split

1. **Calibration round** — both screen same 50 records; target Cohen's κ ≥ 0.70
2. **Split screening** — remaining ~2,620 records split equally between reviewers
3. **Borderline escalation** — `maybe` cases resolved jointly
4. **Re-screening** — excluded full-texts re-screened after 2–4 weeks

### Screening phases
- **Title/Abstract** → inclusion against eligibility criteria (§9)
- **Full-Text** → same criteria; Tier 2 flag assigned at extraction

### Exclusion codes (PRISMA 2020 §13b)
`EX-PARADIGM` · `EX-NONFIN` · `EX-NOMETHOD` · `EX-NOEVAL` · `EX-DUP` · …

---

# Extraction & Quality

## Extraction Codebook
- **Bibliographic:** title, authors, year, DOI
- **Classification:** problem family, quantum method, NISQ vs FT
- **Tier 2 flag:** `tier2_applicable` (yes/no)
- **Hoefler fields (Tier 2):** crossover time, end-to-end overhead, classical baseline, tier-1/tier-2 achievability

## Quality Rubric (0/1/2 per SEGRESS)

| Dimension | What it captures |
|-----------|-----------------|
| q_classical_baseline_risk | Weak baseline inflates advantage? |
| q_advantage_evidence_risk | Claims lack evidence? |
| q_end_to_end | Full overhead included? |
| q_crossover_framing | Tier-1/Tier-2 analysis present? |
| q_reproducibility | Code + data available? |

---

# Expected Outputs

## Tier 1 (Evidence Mapping)
- **Evidence map:** problem family × quantum method (annotated with maturity)
- **Trend analysis:** publication volume, method adoption curves
- **Taxonomy:** problem families, algorithms, evaluation approaches

## Tier 2 (Advantage Assessment)
- **Per-workload advantage table:** best evidence on crossover viability
- **Gap analysis:** missing overhead, weak baselines, no crossover estimates
- **Certainty ratings:** HIGH / MODERATE / LOW per synthesis finding

---

# Reproducibility & Tooling

### Custom Python toolkit: `slr_toolkit`
```bash
auto-search    # API-driven search across all 4 databases
build-master   # Deduplicate (DOI exact + fuzzy title)
prisma         # Generate PRISMA flow counts
```

### All artefacts versioned
- Raw JSON preserved for provenance
- PRISMA-S compliant search logging
- OSF protocol pre-registration

### Standards
PRISMA 2020 · PRISMA-S · Okoli (2015) · vom Brocke et al. (2015) · SEGRESS

---

# Timeline

| Phase | Status |
|-------|--------|
| Protocol finalisation | ✅ Complete (v3.0) |
| Database searches | ✅ Complete (5,775 raw → 2,672 unique) |
| Benchmark sensitivity check | 🟡 Next |
| Screening (title/abstract) | ⬜ Planned |
| Screening (full-text) | ⬜ Planned |
| Data extraction | ⬜ Planned |
| Synthesis & writing | ⬜ Planned |
| Cross-method synthesis & experiments | ⬜ Documented separately |

---

# Discussion Points

1. **Query breadth:** 5,775 raw → 2,672 unique — is coverage sufficient?
2. **Database coverage:** 4 sources sufficient?
3. **Advantage lens:** Hoefler framework the right choice?
4. **Tier 2 depth:** How many papers will realistically qualify?
5. **Preprint handling:** Include or sensitivity-analyse only?
6. **Mixed-methods integration:** How should we weight SLR vs interview findings when they diverge?
7. **What would make this most valuable** for the QC community?

---

# Key References

- **Hoefler et al. (2023)** — Practical quantum advantage framework
- **Herman et al. (2022)** — Survey of QC for finance
- **Bunescu & Vârtei (2024)** — Prior formal SLR
- **Creswell & Creswell (2018)** — Mixed-methods research design
- **Page et al. (2021)** — PRISMA 2020
- **Rethlefsen et al. (2021)** — PRISMA-S
- **Wohlin (2014)** — Snowballing guidelines
- **Kitchenham et al. (2023)** — SEGRESS quality appraisal

---

# Thank You

### Questions?
