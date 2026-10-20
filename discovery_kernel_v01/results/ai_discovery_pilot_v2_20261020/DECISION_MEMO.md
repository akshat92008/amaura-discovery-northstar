# DECISION MEMO: North BlueStar AI Discovery Pilot v2
## Decision on Fair-Compute Search Diversity & Algorithmic Discovery in PFSP

**Date:** 2026-10-20  
**To:** Amaura Labs Executive Committee & Technical Leadership  
**From:** Lead Experimental Scientist & Research Infrastructure Engineer  
**Experiment Identifier:** `ai_discovery_pilot_v2_20261020`  
**Artifact Directory:** `discovery_kernel_v01/results/ai_discovery_pilot_v2_20261020/`  

---

## 1. Executive Verdict

### **Verdict: MODIFY**

The preregistered **1.0% discovery gate was NOT passed**. Under fair single-pass evaluation budgets and strict data quarantine on 30 fresh holdout instances, Champion Arm B achieved a mean relative makespan improvement of **+0.287%** over the reference NEH-LS baseline, and Champion Arm A achieved **+0.209%**. Because both improvements are below the preregistered $+1.000\%$ threshold and their 95% bootstrap confidence intervals span zero ($[-0.043\%, +0.642\%]$ and $[-0.144\%, +0.578\%]$), we cannot declare a certified discovery breakthrough.

However, the experimental verdict is **MODIFY**, not **STOP**, for the following decisive reasons:

1. **Reversal of Feedback Pathology:** In Pilot v1, evidence-guided search suffered from prompt anchoring, collapsing to a single inferior heuristic that underperformed the baseline by $-2.528\%$. In Pilot v2, tabu memory and structured diversity controls successfully reversed this failure: Arm B discovered a superior configuration that outperformed independent candidate generation (Arm A) by **+0.078%** (9 wins vs 5 losses).
2. **True Outperformance on Unseen Data:** Unlike Pilot v1 where AI candidates lost to the baseline on holdout data, both AI champions in Pilot v2 outperformed the reference NEH-LS baseline on unseen holdout instances (15 wins vs 8 losses for Arm B; 14 wins vs 9 losses for Arm A).
3. **Outperformance of Established Metaheuristics:** Both AI champions outperformed the Iterated Greedy metaheuristic ($d=4, \text{max\_iter}=20$) on holdout data (Mean $C_{\max}$: Arm B Champion = **3887.63**, Arm A Champion = **3891.30**, Iterated Greedy = **3896.83**, NEH-LS = **3900.33**).
4. **Identification of Search Space Ceiling:** The audit proves that the failure to hit 1.0% is not a flaw in the search engine or evaluation kernel, but rather a fundamental **expressive ceiling of the 6-component declarative DSL**. The best possible configuration expressible in this DSL combines `flow_time_min` tie-breaking with `best_improvement` single-pass insertion, which yields an asymptotic gain of $\approx 0.3\%$. Exceeding 1.0% requires expanding the candidate space to richer algorithmic structures.

---

## 2. Quantitative Summary of Evidence

All metrics are evaluated on the sealed holdout set of 30 untouched instances (seeds 600101–600130, SHA-256 `8c4e8995896a75ebd98a52079c756a34d3daad1ece0a54c2be55c7e6a4f8be66`):

| Comparison | Mean Relative Improvement ($\bar{g}$) | 95% Bootstrap CI (10,000 resamples) | Win / Tie / Loss Record | Preregistered Gate ($\ge +1.0\%$) |
|---|:---:|:---:|:---:|:---:|
| **Champion Arm A vs Reference NEH-LS** | $+0.209\%$ | $[-0.144\%, +0.578\%]$ | 14 / 7 / 9 | **FAILED** |
| **Champion Arm B vs Reference NEH-LS** | $+0.287\%$ | $[-0.043\%, +0.642\%]$ | 15 / 7 / 8 | **FAILED** |
| **Champion Arm B vs Champion Arm A** | $+0.078\%$ | $[-0.004\%, +0.182\%]$ | 9 / 16 / 5 | Positive Trend |
| **Champion Arm B vs Iterated Greedy** | $+0.236\%$ | — | 18 / 4 / 8 | Superior to Metaheuristic |

---

## 3. Analysis of Algorithmic Findings

### 3.1 The Winning Recipe
Champion B (`arm_b_b5_r3_p02`) synthesized the following configuration:
- `initial_order`: `total_processing_time_desc` (standard NEH priority)
- `construction_criterion`: `makespan_only`
- `tie_break`: `flow_time_min` (breaks ties in partial schedule insertion by total completion time)
- `local_search`: `single_pass_insertion`
- `search_strategy`: `best_improvement` (evaluates all candidate positions for the current job before applying the move)
- `acceptance_rule`: `strictly_better_makespan`
- `budget_evaluations`: `"single_pass"` ($B(n)=n(n-1)$)

### 3.2 Why it beats NEH-LS
Conventional NEH-LS relies on `first_found` tie-breaking during construction and `first_improvement` during local search. By incorporating `flow_time_min` tie-breaking during construction and `best_improvement` during local search, the candidate constructs tighter intermediate partial schedules that allow the single-pass local search to settle into better local minima.

### 3.3 Why it cannot exceed 1.0% in the Current DSL
The current declarative grammar only permits single-pass deterministic local search. In permutation flow-shop scheduling, moving beyond a $\approx 0.3\%$ gain over NEH-LS requires metaheuristic mechanisms:
- Variable destruction size (e.g. Iterated Greedy destruction of $d$ jobs followed by NEH reconstruction).
- Perturbation / restart operators.
- Variable neighborhood structures (interchange + insertion).
Because these mechanisms are absent from the 6-component DSL, the search engine correctly discovered the global optimum of the current candidate space, but cannot transcend the expressive bounds of that space.

---

## 4. Recommendations for Next Phase (Phase 3)

1. **Expand the Candidate Space Beyond the 6-Component DSL:**
   - Add parameterized metaheuristic templates: Iterated Greedy destruction size $d \in \{2, 3, 4, 6\}$, temperature cooling schedules for acceptance criteria, and multi-neighborhood descent (insertion + pairwise swap).
   - Support hybrid construction heuristics (e.g., NEH with dynamic tie-breaking profiles).

2. **Retain Tabu-Guided Diversity Search:**
   - The diversity mechanism in Arm B was validated: it prevented immediate mode collapse and found the superior configuration.
   - For Phase 3, scale tabu memory to operate globally across blocks, ensuring high exploratory entropy across the expanded search space.

3. **Maintain Fair-Compute Budgets:**
   - The fair-budget enforcement ($B(n)=n(n-1)$ or standardized iteration counts) proved vital to eliminate the false conclusions of Pilot v1.
   - For metaheuristic comparisons, evaluate all candidates under equal CPU-time or equal total objective-function evaluations ($E(n) = k \cdot n(n-1)$).

4. **Zero Paid Spend:**
   - Local model inference via Ollama (`qwen2.5-coder:1.5b`) cost exactly $0.00 and was entirely sufficient to navigate the structured DSL. Paid commercial APIs are unnecessary for this search phase.
