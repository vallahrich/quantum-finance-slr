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

## A Two-Stage SLR & Practical Advantage Assessment

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

2. **Mapping review** (Stage A) + **focused advantage analysis** (Stage B)

3. **Crossover viability assessment** per problem family

4. **Reproducible, API-driven** search pipeline (open toolkit)

---

# Two-Stage Design

## Stage A — Mapping Review
- Broad survey: *What's out there?*
- Evidence map: problem families × quantum methods × maturity

## Stage B — Focused SLR
- Deep dive: *Where is practical advantage credible?*
- Hoefler framework assessment per workload

![bg right:35% w:350](https://mermaid.ink/img/pako:eNptkE1uwzAMha9CcJUc4AJddNFFF-2iFkWBkmlb-JEBkk4QBLl7acdJ3XYEID7ye-QL3JmkgCeXiizZFnIbonuOhC7s72IXWDQ5sYYB0eCKPxA1x4E88H8pu3RMPqsaVPCqGn0NR3ag7LVj6cqDFyXFYx27Ey14dvMa5tdQ6sCv_1Tqb3T-cLt4g7uETxxAEy_4bBRvZgcDZ_3hfPjm0Q)

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

**Block 1 (Quantum):** `"quantum computing"`, `"quantum algorithm*"`, `"quantum circuit*"`, `"variational quantum"`, `QAOA`, `VQE`, `QAE`, `Grover`, `HHL`, `"quantum walk*"`, `"quantum machine learning"`, `"quantum error correction"`, `"fault-tolerant quantum"`, `"quantum speedup"`, `"quantum advantage"`, `"quantum annealing"`

**Block 2 (Finance):** `finance`, `financial`, `"quantitative finance"`, `"portfolio optim*"`, `"portfolio selection"`, `"option pricing"`, `"derivative pricing"`, `"financial derivative*"`, `"risk analysis"`, `"credit risk"`, `"market risk"`, `VaR`, `"Black-Scholes"`, `CVA`, `xVA`, `"Monte Carlo"`, `"credit scoring"`, `"fraud detection"`, `"algorithmic trading"`, `"asset allocation"`, `"stock market"`, `"stock price*"`, `"hedge fund"`, `"financial hedging"`, `"financial engineering"`

### Design choice: no third block
- Stage A = broad capture → **maximise recall** at search, **precision** at screening
- Per Okoli (2015, §4.2)

---

# Current Numbers

| Source | Records |
|--------|---------|
| OpenAlex | 4,709 |
| arXiv | 1,196 |
| Semantic Scholar | 874 |
| Scopus | 1,685 |
| **Total raw** | **8,464** |
| **After deduplication** | **4,750** |
| Duplicates (DOI + fuzzy) | 3,714 |

### Query refinement (Amendments A1–A2)
- Tightened noisy bare terms (e.g. `derivative*` → `"derivative pricing"`, `trading` → `"algorithmic trading"`)
- Uncapped result sets per SLR completeness (Kitchenham & Charters 2007)
- All sources fetched completely — no API-cap truncation

---

# Screening Process

### Two reviewers — calibrate then split

1. **Calibration round** — both screen same 50 records; target Cohen's κ ≥ 0.70
2. **Split screening** — remaining ~4,700 records split equally between reviewers
3. **Borderline escalation** — `maybe` cases resolved jointly
4. **Re-screening** — excluded full-texts re-screened after 2–4 weeks

### Two phases
- **Title/Abstract** → broad Stage A inclusion
- **Full-Text** → deeper Stage B filter (must have quantitative evaluation)

### Exclusion codes (PRISMA 2020 §13b)
`EX-PARADIGM` · `EX-NONFIN` · `EX-NOMETHOD` · `EX-NOEVAL` · `EX-DUP` · …

---

# Extraction & Quality

## Extraction Codebook
- **Bibliographic:** title, authors, year, DOI
- **Classification:** problem family, quantum method, NISQ vs FT
- **Hoefler fields:** crossover time, end-to-end overhead, classical baseline, tier-1/tier-2 achievability

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

## Stage A
- **Evidence map:** problem family × quantum method (annotated with maturity)
- **Trend analysis:** publication volume, method adoption curves
- **Taxonomy:** problem families, algorithms, evaluation approaches

## Stage B
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
| Protocol finalisation | ✅ Complete (v2.0) |
| Database searches | ✅ Complete (8,464 raw → 4,750 unique) |
| Benchmark sensitivity check | 🟡 Next |
| Screening (title/abstract) | ⬜ Planned |
| Screening (full-text) | ⬜ Planned |
| Data extraction | ⬜ Planned |
| Synthesis & writing | ⬜ Planned |

---

# Discussion Points

1. **Query breadth:** 8,464 raw → 4,750 unique — is coverage sufficient?
2. **Database coverage:** 4 sources sufficient?
3. **Advantage lens:** Hoefler framework the right choice?
4. **Stage B depth:** How many papers will realistically qualify?
5. **Preprint handling:** Include or sensitivity-analyse only?
6. **What would make this most valuable** for the QC community?

---

# Key References

- **Hoefler et al. (2023)** — Practical quantum advantage framework
- **Herman et al. (2022)** — Survey of QC for finance
- **Bunescu & Vârtei (2024)** — Prior formal SLR
- **Page et al. (2021)** — PRISMA 2020
- **Rethlefsen et al. (2021)** — PRISMA-S
- **Wohlin (2014)** — Snowballing guidelines
- **Kitchenham et al. (2023)** — SEGRESS quality appraisal

---

# Thank You

### Questions?
