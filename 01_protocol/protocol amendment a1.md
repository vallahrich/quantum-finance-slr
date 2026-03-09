# Protocol Amendment A1 — Query Refinement for OpenAlex and arXiv

## Amendment Log Entry (for `amendments_log.md`)

| Date (YYYY-MM-DD) | Version | Change | Rationale | Expected impact | Approved by |
|---|---|---|---|---|---|
| 2026-03-09 | v1.1 | §7 Search strategy: OpenAlex and arXiv queries revised to use phrase + Boolean + concept/field constraints. Original noisy runs archived to `03_raw_exports/_deprecated_noisy/`. | Pilot runs returned ≈92.7% noise due to incidental "finance/financial" matches in full-text (OpenAlex) and unscoped field search (arXiv). Precision failure, not recall failure. | Estimated reduction from ~18k to ~200–600 records per source. Negligible recall loss for on-topic papers; false negatives mitigated by mandatory snowballing (§7). | [Your name] |

---

## Amendment Log Entry (for `amendments_log.csv`)

```csv
2026-03-09,v1.1,§7 Search strategy,"OpenAlex and arXiv queries revised to use phrase + Boolean + concept/field constraints; original noisy runs archived to 03_raw_exports/_deprecated_noisy/",[Your name]
```

---

## Detailed Amendment Narrative

**Amendment ID:** A1
**Date:** 2026-03-09
**Protocol section affected:** §7 (Search strategy — reproducible + logged)
**Protocol version:** v1.0 → v1.1

### 1. Problem identified

During the pilot search execution (pre-screening), the OpenAlex and arXiv runs returned a combined corpus in which approximately 92.7% of records were not relevant to finance as a research domain. Manual inspection revealed the following root causes:

**OpenAlex:** The `search=` parameter performs full-text relevance matching across titles, abstracts, and full-text content. The term "finance" / "financial" matched incidental occurrences (e.g., "financial support from grant X," "financially motivated," "financed by") in papers from unrelated domains (cosmology, pure mathematics, category theory, etc.). Despite OpenAlex treating multi-term queries as AND by default, the full-text search scope produced an unmanageably large result set with very low precision.

**arXiv:** The API expects field-prefixed queries (`ti:`, `abs:`, `cat:`) combined with Boolean operators (`AND`, `OR`, `ANDNOT`). The pilot query was passed as a loose free-text string without field prefixes, resulting in an all-fields relevance search rather than a targeted title/abstract constraint. arXiv's own documentation recommends refining queries that return >1,000 results.

### 2. Change description

The following changes are applied to §7 of the protocol:

#### 2a. OpenAlex query revision

**Previous (pilot):**
```
search="quantum computing" AND "finance"
filter=publication_year:2016-{current_year}
```

**Revised:**
```
Step 1 — Resolve concept IDs:
  https://api.openalex.org/concepts?search="quantum computing"
  https://api.openalex.org/concepts?search=finance

Step 2 — Concept-filtered intersection + phrase search:
  filter=concept.id:C_QUANTUM,concept.id:C_FINANCE,from_publication_date:2016-01-01
  search=("quantum computing" AND (finance OR "quantitative finance"
          OR pricing OR portfolio OR CVA OR xVA))
```

Optionally, `search.exact` (unstemmed matching) may be used for maximum precision if the concept-filtered run still contains excessive noise.

#### 2b. arXiv query revision

**Previous (pilot):**
```
search_query="quantum computing" AND "finance"
```

**Revised:**
```
search_query=(ti:"quantum computing" OR abs:"quantum computing")
  AND (ti:finance OR abs:finance OR ti:financial OR abs:financial
       OR cat:q-fin*)
```

This forces finance relevance into title or abstract fields, with an additional category hook for the `q-fin.*` subject classes. Cross-listed papers (e.g., `quant-ph` + `q-fin`) are captured by the field-prefix OR.

#### 2c. Scopus / WoS / IEEE / ACM — no change

The Scopus `TITLE-ABS-KEY(...)` query produced results in a manageable range consistent with expectations. No revision is needed for field-restricted databases. These remain the primary ("gold baseline") sources, with OpenAlex and arXiv serving as coverage extensions per §6.

### 3. Disposition of noisy pilot runs

Per PRISMA-S transparency expectations, the original noisy runs are **archived, not deleted**:

- Moved to: `03_raw_exports/_deprecated_noisy/`
- Each deprecated folder contains a `README.txt` stating: "Pilot run — not used in synthesis. See Protocol Amendment A1."
- These runs may be referenced in the thesis appendix as calibration data (synonym discovery, false-positive analysis) but are excluded from the PRISMA flow counts.

### 4. Rationale

- **Screening ~18k mostly-noise records** increases reviewer fatigue, selection error, and time cost without improving recall for on-topic papers.
- **PRISMA-S** (Rethlefsen et al., 2021) explicitly expects exact search strategies per source/interface to be reported. A clean rerun with corrected strings produces a defensible, reproducible audit trail.
- **The protocol's mandatory snowballing rule** (§7) mitigates any marginal recall loss from tighter queries: backward + forward snowballing on the final included set captures seminal and highly cited works regardless of API search precision.
- Basing the SLR on a known-noisy corpus risks appearing as a query-design failure in the PRISMA flow diagram, undermining the review's methodological credibility.

### 5. Expected impact

| Metric | Before (pilot) | After (projected) |
|--------|----------------|-------------------|
| OpenAlex raw hits | ~12,000+ | ~200–500 |
| arXiv raw hits | ~6,000+ | ~100–300 |
| Estimated precision | ~7% | ~60–80% |
| Recall for on-topic papers | ~High | ~High (snowballing compensates) |
| Screening workload | Weeks (infeasible) | Days (manageable) |

### 6. PRISMA-S search log update

The `02_search_logs/search_log.xlsx` will be updated with:
- New rows for each revised search run (OpenAlex v2, arXiv v2)
- Full query strings as executed
- Fields searched (concept IDs for OpenAlex; ti/abs/cat for arXiv)
- Date limits, result counts, export filenames
- Notes column referencing this amendment (A1)

The deprecated pilot rows will be annotated with `Notes: "Deprecated — see Amendment A1"` but not removed.

---

## References

- Hoefler, T., Häner, T., & Troyer, M. (2023). Disentangling Hype from Practicality. *CACM*, 66(5). DOI: 10.1145/3571725.
- OpenAlex documentation: https://docs.openalex.org
- arXiv API documentation: https://info.arxiv.org/help/api/
- Rethlefsen, M. L., et al. (2021). PRISMA-S. *Systematic Reviews*, 10. DOI: 10.1186/s13643-020-01542-z.