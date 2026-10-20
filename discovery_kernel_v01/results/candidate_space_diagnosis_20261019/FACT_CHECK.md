# FACT CHECK: PFSP AI Discovery Pilot (2026-10-19)
## Empirical Verification and Discrepancy Audit

**Date:** 2026-10-19  
**Target Pilot:** `discovery_kernel_v01/results/ai_discovery_pilot_20261019/`  
**Auditor:** Independent AI Research Scientist & Algorithm-Discovery Engineer  
**Source Code Modules Audited:**
- `discovery_kernel_v01/run_ai_discovery_experiment.py`
- `discovery_kernel/pfsp_declarative.py`
- `discovery_kernel/generator.py`
- `discovery_kernel/execution.py`
- `discovery_kernel/problem_spec.py`
- `discovery_kernel/method_adapter.py`
- `discovery_kernel/controller.py`
**Raw Data Records Audited:**
- `development_results.json` (SHA-256: `037f4a9905981965...`)
- `final_results.json` (SHA-256: `4f3158ae47622828...`)
- `run_records.jsonl` (SHA-256: `d411cca149c3c4aa...`, 768 events)
- `seed_manifest.json` (SHA-256: `f6a854194df16ec1...`)

---

## 1. Summary of Recalculated Experimental Metrics

All counts and metrics below were independently recalculated directly from the raw event logs in `run_records.jsonl` and structured arrays in `development_results.json` and `final_results.json`.

| Metric / Dimension | Arm A (Independent Search) | Arm B (Evidence-Guided Search) | Discrepancy with Audit Report? |
|---|:---:|:---:|:---:|
| **Total Proposals Generated** | 12 | 12 | None (exact match: 24 total) |
| **Schema Valid Proposals** | 12 (100.0%) | 12 (100.0%) | None (100% validity confirmed) |
| **Malformed / Rejected Proposals** | 0 (0.0%) | 0 (0.0%) | None |
| **Syntactic Duplicates (flagged in run)** | 5 (41.7%) | 12 (100.0% against global seen) | Clarified below |
| **Unique Canonical Recipes (`recipe_hash`)** | **7** | **2** | None (exact match) |
| **Empirically Distinct Behaviors (Dev Set)** | **6** | **1** | **NEW FINDING** (Arm B tested only 1 behavior) |
| **Champion Identifier** | `arm_a_prop_08` | `arm_b_prop_01` | None |
| **Champion Development Score (Mean $C_{\max}$)** | **3587.75** | **3654.15** | None (exact match) |
| **Primary Baseline Identifier** | `neh_ls_insertion` | `neh_ls_insertion` | None |
| **Primary Baseline Dev Score** | **3576.95** | **3576.95** | None (exact match) |
| **Holdout Instances Evaluated** | 30 | 30 | None (seeds 500101–500130) |
| **Champion Holdout Score (Mean $C_{\max}$)** | **3887.70** | **3974.43** | None (exact match) |
| **Primary Baseline Holdout Score** | **3872.23** | **3872.23** | None (exact match) |
| **Relative Improvement vs Primary Baseline ($\bar{g}$)** | **-0.372%** | **-2.528%** | None (exact match) |
| **95% Bootstrap Confidence Interval** | **[-0.680%, -0.093%]** | **[-2.984%, -2.015%]** | None (10,000 resamples verified) |
| **Search Strategy Comparison ($\bar{g}_{B \text{ vs } A}$)** | — | **-2.151%** | None (CI: [-2.625%, -1.658%]) |
| **Total Spend** | **$0.0000** | **$0.0000** | None (Ollama local inference verified) |

---

## 2. Proposal Breakdown and Duplicate Analysis

### 2.1 Arm A Proposal Inventory

| Proposal ID | Recipe Hash (Prefix) | Initial Order | Criterion | Tie Break | Local Search | Search Strategy | Acceptance Rule | Budget | Dev Mean $C_{\max}$ | Syntactic Duplicate? | Behavioral Group |
|---|:---:|---|---|---|---|---|---|:---:|:---:|:---:|:---:|
| `arm_a_prop_01` | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 250 | 3654.15 | First seen | Group 1 |
| `arm_a_prop_02` | `caf27aa2` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 300 | 3652.65 | No | Group 2 |
| `arm_a_prop_03` | `ba2a4d61` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 350 | 3650.10 | No | Group 3 |
| `arm_a_prop_04` | `bd213a3f` | weighted_profile_desc | makespan_only | flow_time_min | multi_pass | best_imp | strictly_better | 400 | 3649.45 | No | Group 4 |
| `arm_a_prop_05` | `ab117bd1` | total_processing_time_asc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 200 | 3642.05 | No | Group 5 |
| `arm_a_prop_06` | `ab896d87` | weighted_profile_desc | makespan_only | flow_time_min | multi_pass | best_imp | strictly_better | 250 | 3654.15 | No | Group 1 (Identical) |
| `arm_a_prop_07` | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 250 | 3654.15 | Yes (of prop 01) | Group 1 |
| `arm_a_prop_08` | `f54ed96d` | total_processing_time_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 300 | **3587.75** | No (Champion A) | Group 6 |
| `arm_a_prop_09` | `f54ed96d` | total_processing_time_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 300 | 3587.75 | Yes (of prop 08) | Group 6 |
| `arm_a_prop_10` | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 250 | 3654.15 | Yes (of prop 01) | Group 1 |
| `arm_a_prop_11` | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 250 | 3654.15 | Yes (of prop 01) | Group 1 |
| `arm_a_prop_12` | `caf27aa2` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | best_imp | strictly_better | 300 | 3652.65 | Yes (of prop 02) | Group 2 |

**Arm A Summary:** 12 proposals generated; 7 unique canonical recipes; 6 empirically distinct behaviors.

---

### 2.2 Arm B Proposal Inventory Across Feedback Rounds

| Proposal ID | Round | Recipe Hash (Prefix) | Initial Order | Criterion | Tie Break | Local Search | Budget | Dev Mean $C_{\max}$ | Syntactic Duplicate of | Behavioral Outcome |
|---|:---:|:---:|---|---|---|---|:---:|:---:|:---:|:---:|
| `arm_b_prop_01` | R1 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_a_prop_01` / prompt example | Group 1 |
| `arm_b_prop_02` | R1 | `ab896d87` | weighted_profile_desc | makespan_only | flow_time_min | multi_pass | 250 | 3654.15 | `arm_a_prop_06` | Group 1 |
| `arm_b_prop_03` | R1 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_04` | R1 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_05` | R2 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_06` | R2 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_07` | R2 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_08` | R2 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_09` | R3 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_10` | R3 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_11` | R3 | `4e970cdd` | weighted_profile_desc | makespan_only | flow_time_min | single_pass | 250 | 3654.15 | `arm_b_prop_01` | Group 1 |
| `arm_b_prop_12` | R3 | `ab896d87` | weighted_profile_desc | makespan_only | flow_time_min | multi_pass | 250 | 3654.15 | `arm_b_prop_02` | Group 1 |

---

## 3. Critical Verification Findings & Corrections

### 3.1 Prompt Demonstration Copying (Root Source of Mode Collapse)
In `discovery_kernel/generator.py`, the generator prompt contained a single few-shot example:
```json
SCHEMA_EXAMPLE = """{
  "rationale": "Prioritize jobs by Palmer slope index and use flow time tie-breaking during insertion, followed by single-pass insertion local search to polish sequence.",
  "config": {
    "initial_order": "weighted_profile_desc",
    "construction_criterion": "makespan_only",
    "tie_break": "flow_time_min",
    "local_search": "single_pass_insertion",
    "search_strategy": "best_improvement",
    "acceptance_rule": "strictly_better_makespan",
    "budget_evaluations": 250
  }
}"""
```
**Verification:**
Recipe `4e970cdd` is the **exact canonical representation of this prompt example**.
- Across Arm A and Arm B, **14 of 24 proposals (58.3%)** copied this recipe verbatim.
- In Arm B, **10 of 12 proposals (83.3%)** copied this exact recipe.

### 3.2 Distinction: Syntactic vs Behavioral Duplicates
The audit report noted that Arm B produced 2 unique recipes: `4e970cdd` (single-pass insertion, budget 250) and `ab896d87` (multi-pass insertion, budget 250).
**Recalculation:**
On all 20 development instances:
- The per-instance makespans of `4e970cdd` and `ab896d87` are **100% identical** across every instance ($p_1 == p_2$).
- **Reason:** For any instance with $n \ge 30$, a single pass of insertion requires testing $n(n-1) \ge 870$ moves. With an evaluation cap of 250, neither algorithm ever completes pass 1. Both algorithms terminate at exactly evaluation 250 on the exact same prefix of moves.
- **Fact:** While Arm B produced 2 syntactically distinct recipes, it produced **exactly 1 unique empirical behavior**. Arm B's effective sample size was $N_{\mathrm{eff}} = 1$.

### 3.3 Parity of Generation Settings
- Both arms were executed sequentially using `qwen2.5-coder:1.5b` via local Ollama.
- Both arms used identical generation settings: `temperature = 0.7`, `format = "json"`.
- Both arms had an identical total proposal budget: $N = 12$.
- The prompt differences between Arm A and Arm B consisted strictly of the intended feedback intervention (round progress, prior round makespan summary, and current leader recipe).

---

## 4. Verification Verdict

The reported numbers in `development_results.json` and `final_results.json` are **mathematically and cryptographically authentic**. The report correctly recorded the failure of the 1.0% discovery gate. However, the diagnosis in the original report underemphasized that:
1. The mode collapse was directly initiated by a static few-shot demonstration in `generator.py`.
2. Arm B evaluated only one distinct empirical behavior due to budget truncation masking the difference between single-pass and multi-pass search.
