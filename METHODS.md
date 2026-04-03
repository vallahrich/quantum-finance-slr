# Methods Quick-Reference Guide

Maps protocol sections to thesis chapters, PRISMA items, and Hoefler framework dimensions.

## Overarching Research Design

This SLR (Phase 1a) sits within an exploratory sequential mixed-methods design.

The mappings below cover Phase 1a.

## Protocol -> Thesis Chapter Mapping

| Protocol section | Topic | Thesis chapter / section |
|------------------|-------|--------------------------|
| 0 | Title and registration | Ch. 1 Introduction |
| 0b | Position within overarching research design | Ch. 3 section 3.0 |
| 1 | Review type | Ch. 3 Methodology |
| 1b | Positioning against prior reviews | Ch. 2 Related Work |
| 2 | Review questions | Ch. 3 section 3.1 |
| 3 | Objectives | Ch. 1 section 1.2 |
| 4 | Scope boundaries | Ch. 3 section 3.2 |
| 5 | Advantage framework | Ch. 3 section 3.3 |
| 6 | Information sources | Ch. 3 section 3.4 |
| 7 | Search strategy | Ch. 3 section 3.5 |
| 7b | Benchmark sensitivity check | Ch. 3 section 3.6 |
| 7c | Snowballing procedure | Ch. 3 section 3.7 |
| 8 | Screening and selection | Ch. 3 section 3.8 |
| 8b | Split-screening limitations | Ch. 6 Discussion section 6.3 |
| 9 | Eligibility criteria | Ch. 3 section 3.9 |
| 10 | Data extraction | Ch. 3 section 3.10 |
| 11 | Quality appraisal | Ch. 3 section 3.11 |
| 11b | Certainty-of-evidence framework | Ch. 3 section 3.12 |
| 11c | Reporting bias assessment | Ch. 3 section 3.13 |
| 12 | Synthesis plan | Ch. 3 section 3.14 |
| 13 | Reporting standards | Ch. 3 section 3.15 |

## PRISMA 2020 Items -> Thesis Location

See `01_protocol/PRISMA_2020_checklist.md` for the full mapping.

## PRISMA-S Items -> Thesis Location

See `01_protocol/PRISMA_S_checklist.md` for the full mapping.

## Hoefler Framework Dimensions -> Extraction Fields

| Hoefler dimension | Codebook field(s) |
|-------------------|-------------------|
| Input data specification | `input_data_size`, `big_compute_small_data` |
| Output type | `output_type` |
| I/O bottleneck | `io_bottleneck_discussed`, `q_io_bottleneck` |
| Speedup characterization | `speedup_type_detailed`, `speedup_constant_reported` |
| Oracle / state-prep cost | `oracle_stateprep_cost_included` |
| End-to-end overhead | `end_to_end_overhead`, `q_end_to_end` |
| Tier-1 crossover | `crossover_time_estimated`, `crossover_time_value`, `crossover_size_estimated`, `crossover_size_value`, `tier1_achievable`, `q_crossover_framing` |
| Tier-2 finance SLA | `tier2_finance_sla` |
| Classical baseline quality | `classical_baseline_detail`, `classical_baseline_hardware`, `q_classical_baseline_risk` |
| Error correction model | `error_correction_model`, `qubit_type`, `t_count_or_gate_cost` |
| Advantage evidence | `advantage_claim`, `advantage_evidence`, `q_advantage_evidence_risk` |
