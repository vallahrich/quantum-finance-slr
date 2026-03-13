# SLR Presentation — Talking Points Cheat Sheet

## 1-Minute Elevator Pitch
"I'm doing a mixed-methods study on quantum computing in finance. The first component is a systematic literature review — mapping all gate-based quantum approaches and assessing practical advantage using the Hoefler framework. In parallel, I'm conducting semi-structured interviews with finance practitioners. The synthesis of both identifies the most promising workloads, which feeds into quantum computing experiments. Today I'm presenting the SLR component."

---

## Key Numbers to Remember
- **5,775** raw records from 4 search runs across 4 databases (OpenAlex, arXiv, Semantic Scholar, Scopus)
- **2,672** unique records after deduplication (3,103 duplicates removed)
- **20** benchmark papers for sensitivity checking
- **2016–present** time window
- **6 research questions** (5 SLR + 1 cross-cutting)
- **2 reviewers** with calibrate-then-split design
- **AI-assisted** screening via ASReview as recall safety net (Protocol §8, Amendment A8)

## The "So What?" for Each Slide

| Slide | Key Takeaway |
|-------|-------------|
| Motivation | QC-finance is hyped — we need both theoretical rigour AND practitioner grounding to assess what's real |
| Gap | No prior review combines systematic search + advantage framework + practitioner triangulation |
| Mixed-methods | SLR = theory, interviews = practice, synthesis = prioritised experiments |
| Tiered extraction | Tier 1 = breadth (what exists?), Tier 2 = depth (is advantage real?) |
| Scope | Gate-based only, excluding annealing — because that's where the open question is |
| Hoefler | The framework gives us objective criteria: ≤2 weeks crossover, real SLAs, full overhead, SOTA baselines |
| Sources | 4 databases, coverage-justified, API-automated |
| Search | Two-block Boolean (refined A5), maximise recall, filter at screening |
| Numbers | Large initial set reflects broad search — expect heavy reduction at screening |
| Screening | Two reviewers + AI safety net: calibrated (κ ≥ 0.70), split, AI flags potential false negatives for re-review |
| Extraction | Codebook directly maps to Hoefler dimensions — every paper assessed on same criteria |
| Outputs | Evidence map + advantage table + gap analysis = actionable research agenda |
| Tooling | Fully reproducible, open, API-driven — not just a Word doc |

## Anticipated Questions & Answers

**Q: Why not include quantum annealing?**
A: Annealing and gate-based are fundamentally different paradigms with different advantage arguments. Including both would conflate the analysis. Prior reviews (Orús 2019) already cover annealing well.

**Q: Why start from 2016?**
A: Meaningful gate-based QC research in finance begins ~2016. Earlier work is predominantly annealing or purely theoretical. We capture the entire relevant era.

**Q: Is 2,672 records enough? Could you be missing relevant papers?**
A: We refined the query through multiple iterations (amendments A1–A2) to remove noise while preserving recall. All 4 sources fetched complete result sets with no API-cap truncation. Coverage is validated by a benchmark sensitivity check against known-relevant papers. Mandatory snowballing (§7c) catches anything missed by the database search.

**Q: How do you ensure screening consistency with two reviewers?**
A: We calibrate first — both reviewers independently screen the same 50 records and compute Cohen's kappa. We only proceed to split screening once kappa >= 0.70. Borderline cases are resolved jointly, and each reviewer re-screens their excluded papers after a time gap to catch inconsistencies.

**Q: Why Hoefler et al. specifically?**
A: It's the most rigorous practical-advantage framework available. It requires accounting for end-to-end overhead, credible baselines, and operational feasibility — exactly the dimensions where most QC-finance claims are weakest.

**Q: How is this different from Herman et al. 2022?**
A: Herman et al. is an excellent survey but explicitly not a systematic review — no formal search protocol, no reproducible methodology, no advantage framework applied per-paper. We build on their work with systematic rigour.

**Q: What do you expect to find?**
A: Based on initial reading: very few studies will meet Tier-1 crossover criteria. Most advantage claims likely rely on asymptotic speedups without full overhead accounting. The gap analysis will be the most impactful output.

**Q: Why not just do the SLR?**
A: The SLR tells us what researchers have found, but practitioners face operational constraints that rarely appear in papers. The most interesting findings will likely be where theory and practice disagree.

**Q: How do the interviews relate to the SLR?**
A: They run in parallel. The interview topic guide uses the same problem families but we don't share SLR conclusions with interviewees to avoid anchoring. Synthesis happens afterward.

**Q: You use AI for screening — doesn't that undermine the systematic methodology?**
A: The AI is a supplementary recall safety net, not a replacement for human screening. Both human reviewers make all final decisions. The AI's only role is to flag records we might have missed (false negatives). This follows the 2025 joint position statement from Cochrane, Campbell Collaboration, JBI, and CEE (Flemyng et al. 2025), which supports AI in evidence synthesis with human oversight. We validate AI performance on a held-out subset (≥100 records) and require recall ≥ 0.95 before trusting it. We also audit 10% of double-excluded records. Everything is reported per PRISMA-trAIce (Holst et al. 2025).
