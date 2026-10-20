# BASELINE PARITY AUDIT: NEH-LS Representability in PFSP Declarative DSL

**Date:** 2026-10-19  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Evaluator:** Makespan Minimization ($C_{\max}$)  
**Target Baseline:** `neh_ls_insertion` (`benchmark_v1/src/domains/pfsp_full_algorithm.py::neh_ls_solve`)  
**Auditor:** Independent AI Research Scientist & Algorithm-Discovery Engineer  

---

## 1. Executive Summary

The latest pilot diagnosis (`CANDIDATE_SPACE_ANALYSIS.md` and `SEARCH_FAILURE_ANALYSIS.md`) asserted that:
> *"The representation already contained the winning baseline (`neh_ls_insertion`), yet the AI search failed to locate it."*

This audit tested that assertion by executing direct step-by-step parity comparisons between `PFSPNEHLSAdapter` (`neh_ls_solve`) and `PFSPDeclarativeAdapter` across all 20 development instances.

### Key Finding:
**The assertion was mathematically and empirically FALSE.**
Under the rules of the current declarative schema (`budget_evaluations <= 500`), **the baseline `neh_ls_insertion` is structurally unreachable.**

When configuring the declarative solver with the nominal NEH-LS specification:
```json
{
  "initial_order": "total_processing_time_desc",
  "construction_criterion": "makespan_only",
  "tie_break": "first_found",
  "local_search": "single_pass_insertion",
  "search_strategy": "best_improvement",
  "acceptance_rule": "strictly_better_makespan",
  "budget_evaluations": 500
}
```
The declarative solver **failed to match the baseline on 12 out of 20 development instances (60.0% mismatch rate)**.

Two distinct structural barriers prevent the baseline from being represented:
1. **Severe Budget Asymmetry:** `neh_ls_solve` executes a complete single pass of insertion local search without budget limits, requiring $n(n-1)$ to $n^2$ evaluations (up to 14,400 evaluations per instance for $n=120$). In contrast, `pfsp_declarative.py` imposes a hard ceiling of 500 evaluations, truncating search after evaluating as few as 3.5% of the jobs on large instances.
2. **Hardcoded Tie-Breaking Discrepancy:** Line 365 of `pfsp_declarative.py` hardcodes a secondary flow-time tie-break (`or (c_cand == best_ins_cmax and f_cand < best_ins_flow)`) during local search, whereas `neh_ls_solve` uses strict `<` makespan comparison, breaking ties by first-found position index.

---

## 2. Algorithm Semantics Comparison

| Algorithmic Phase | Baseline Implementation (`neh_ls_solve`) | Declarative Implementation (`solve_declarative`) | Parity Status |
|---|---|---|:---:|
| **Initial Job Order** | Total sum of processing times descending: `sorted(range(n), key=lambda j: sum(times[j]), reverse=True)` | `_order_jobs(..., "total_processing_time_desc")`: `sorted(range(n), key=lambda j: sum(times[j]), reverse=True)` | **EXACT MATCH** (20/20 identical) |
| **Constructive Insertion** | NEH incremental insertion: jobs inserted at best position minimizing partial makespan | `_evaluate_partial_schedule(..., "makespan_only", "first_found")` | **EXACT MATCH** (20/20 identical sequences) |
| **Constructive Tie-Break** | First position achieving minimum makespan (strict `<`) | First position achieving minimum makespan | **EXACT MATCH** |
| **Local Search Neighborhood** | Single-pass Taillard insertion: remove job $i$, test all insertion positions $0 \le j \le n-1$ | Single-pass Taillard insertion: remove job $i$, test all insertion positions $0 \le j \le n-1$ | **MATCH** (Topology identical) |
| **Local Search Move Acceptance** | Best improvement per job: accepts position minimizing makespan (strict `<`) | Best improvement per job: accepts position minimizing makespan | **MATCH** |
| **Local Search Tie-Break** | **First-found position** (strict `<` ignores equal makespans) | **Flow-time minimization** (`f_cand < best_ins_flow`) hardcoded at line 365 | **STRUCTURAL MISMATCH** |
| **Evaluation Budget** | **Unbounded ($\mathcal{O}(n^2)$)**: Evaluates all $n(n-1)$ moves to completion ($380 \le M \le 14,280$) | **Bounded ($50 \le \text{budget} \le 500$)**: Truncates mid-pass on instances $n \ge 30$ | **CRITICAL ASYMMETRY** |

---

## 3. Empirical Verification: Instance-by-Instance Audit

The table below reports the makespan returned by the baseline `neh_ls_solve` versus the declarative solver configured with nominal NEH-LS and maximum allowable schema budget (`budget=500`):

| Instance ID | $n$ | $m$ | Required Moves $n(n-1)$ | Baseline Makespan (`neh_ls_solve`) | Declarative Makespan (`budget=500`) | Exact Match? | Makespan Gap ($\Delta$) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `pfsp_dev_00` | 20 | 5 | 380 | 1247 | 1247 | **MATCH** | +0 |
| `pfsp_dev_01` | 20 | 5 | 380 | 1292 | 1292 | **MATCH** | +0 |
| `pfsp_dev_02` | 20 | 10 | 380 | 1706 | 1706 | **MATCH** | +0 |
| `pfsp_dev_03` | 20 | 10 | 380 | 1689 | 1663 | **MISMATCH** | **-26** (Tie-break divergence) |
| `pfsp_dev_04` | 30 | 5 | 870 | 1902 | 1910 | **MISMATCH** | +8 (Budget truncated) |
| `pfsp_dev_05` | 30 | 10 | 870 | 2074 | 2074 | **MATCH** | +0 |
| `pfsp_dev_06` | 50 | 5 | 2,450 | 2848 | 2848 | **MATCH** | +0 |
| `pfsp_dev_07` | 50 | 5 | 2,450 | 2636 | 2636 | **MATCH** | +0 |
| `pfsp_dev_08` | 50 | 10 | 2,450 | 3128 | 3136 | **MISMATCH** | +8 (Budget truncated) |
| `pfsp_dev_09` | 50 | 10 | 2,450 | 3085 | 3116 | **MISMATCH** | +31 (Budget truncated) |
| `pfsp_dev_10` | 50 | 15 | 2,450 | 3587 | 3622 | **MISMATCH** | +35 (Budget truncated) |
| `pfsp_dev_11` | 50 | 15 | 2,450 | 3449 | 3450 | **MISMATCH** | +1 (Budget truncated) |
| `pfsp_dev_12` | 75 | 10 | 5,550 | 4382 | 4382 | **MATCH** | +0 |
| `pfsp_dev_13` | 75 | 15 | 5,550 | 4978 | 5013 | **MISMATCH** | +35 (Budget truncated) |
| `pfsp_dev_14` | 75 | 10 | 5,550 | 4332 | 4337 | **MISMATCH** | +5 (Budget truncated) |
| `pfsp_dev_15` | 75 | 15 | 5,550 | 4858 | 4887 | **MISMATCH** | +29 (Budget truncated) |
| `pfsp_dev_16` | 100 | 10 | 9,900 | 5735 | 5780 | **MISMATCH** | +45 (Budget truncated) |
| `pfsp_dev_17` | 100 | 10 | 9,900 | 5746 | 5748 | **MISMATCH** | +2 (Budget truncated) |
| `pfsp_dev_18` | 100 | 15 | 9,900 | 6200 | 6271 | **MISMATCH** | +71 (Budget truncated) |
| `pfsp_dev_19` | 120 | 10 | 14,280 | 6665 | 6665 | **MATCH** | +0 |

**Summary Statistics:**
- **Exact Matches:** 8 / 20 (40.0%)
- **Mismatches:** 12 / 20 (60.0%)
- **Mean Development Makespan (`neh_ls_solve`):** **3576.95**
- **Mean Development Makespan (Declarative `budget=500`):** **3586.90** (+9.95 units worse)

---

## 4. Controlled Counterfactual Test: Unbudgeted Parity

To isolate whether the representation contains the logic when budget and tie-breaking restrictions are lifted, we tested a modified runner:
1. Replaced the flow-time tie-break with strict first-found position comparison.
2. Removed the 500 evaluation cap, permitting the single pass to evaluate all $n(n-1)$ moves.

**Result:**
$$\text{Exact Parity Matches} = \mathbf{20 / 20} \quad (100.0\%)$$
Per-instance makespans and final permutation sequences matched `neh_ls_solve` exactly across every single development instance.

---

## 5. Conclusion

The claim that the baseline was already present in the candidate space was false in execution. The baseline was granted an unbudgeted computational advantage (up to 14,280 moves per instance), while the candidate DSL artificially capped all AI proposals at 500 moves. The competition was structurally unfair before generation even began.
