# SLR Presentation — Talking Points Cheat Sheet

## 1-Minute Elevator Pitch
"I'm doing a systematic literature review on quantum computing applied to finance — specifically gate-based approaches. There are hundreds of papers claiming quantum speedups for portfolio optimisation, option pricing, etc., but nobody has systematically checked whether those claims hold up when you account for the full computational pipeline. I'm using the Hoefler et al. practical-advantage framework to do exactly that: Stage A maps everything out, Stage B deep-dives on which claims are actually credible."

---

## Key Numbers to Remember
- **8,464** raw records from 4 search runs across 4 databases (OpenAlex, arXiv, Semantic Scholar, Scopus)
- **4,750** unique records after deduplication (3,714 duplicates removed)
- **10** benchmark papers for sensitivity checking
- **2016–present** time window
- **5 research questions** across 2 stages
- **2 reviewers** with calibrate-then-split design

## The "So What?" for Each Slide

| Slide | Key Takeaway |
|-------|-------------|
| Motivation | QC-finance is hyped — we need rigorous evidence assessment |
| Gap | No prior review combines systematic search + advantage framework |
| Two-stage | Stage A = breadth (what exists?), Stage B = depth (is advantage real?) |
| Scope | Gate-based only, excluding annealing — because that's where the open question is |
| Hoefler | The framework gives us objective criteria: ≤2 weeks crossover, real SLAs, full overhead, SOTA baselines |
| Sources | 4 databases, coverage-justified, API-automated |
| Search | Two-block Boolean, maximise recall, filter at screening |
| Numbers | Large initial set reflects broad search — expect heavy reduction at screening |
| Screening | Two reviewers, calibrated (κ ≥ 0.70), then split — efficient and defensible |
| Extraction | Codebook directly maps to Hoefler dimensions — every paper assessed on same criteria |
| Outputs | Evidence map + advantage table + gap analysis = actionable research agenda |
| Tooling | Fully reproducible, open, API-driven — not just a Word doc |

## Anticipated Questions & Answers

**Q: Why not include quantum annealing?**
A: Annealing and gate-based are fundamentally different paradigms with different advantage arguments. Including both would conflate the analysis. Prior reviews (Orús 2019) already cover annealing well.

**Q: Why start from 2016?**
A: Meaningful gate-based QC research in finance begins ~2016. Earlier work is predominantly annealing or purely theoretical. We capture the entire relevant era.

**Q: Is 4,750 records enough? Could you be missing relevant papers?**
A: We refined the query through multiple iterations (amendments A1–A2) to remove noise while preserving recall. All 4 sources fetched complete result sets with no API-cap truncation. Coverage is validated by a benchmark sensitivity check against known-relevant papers. Mandatory snowballing (§7c) catches anything missed by the database search.

**Q: How do you ensure screening consistency with two reviewers?**
A: We calibrate first — both reviewers independently screen the same 50 records and compute Cohen's kappa. We only proceed to split screening once kappa >= 0.70. Borderline cases are resolved jointly, and each reviewer re-screens their excluded papers after a time gap to catch inconsistencies.

**Q: Why Hoefler et al. specifically?**
A: It's the most rigorous practical-advantage framework available. It requires accounting for end-to-end overhead, credible baselines, and operational feasibility — exactly the dimensions where most QC-finance claims are weakest.

**Q: How is this different from Herman et al. 2022?**
A: Herman et al. is an excellent survey but explicitly not a systematic review — no formal search protocol, no reproducible methodology, no advantage framework applied per-paper. We build on their work with systematic rigour.

**Q: What do you expect to find?**
A: Based on initial reading: very few studies will meet Tier-1 crossover criteria. Most advantage claims likely rely on asymptotic speedups without full overhead accounting. The gap analysis will be the most impactful output.
