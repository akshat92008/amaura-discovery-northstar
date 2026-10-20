# DECISION MEMO: Baseline Representability & Search-Space Architecture

**To:** Amaura Labs Technical Leadership & Research Steering  
**From:** Lead Research Scientist & Infrastructure Engineer  
**Date:** 2026-10-19  
**Subject:** Formal Verdict on Experiment 0: Baseline Parity, Search Space Ceiling, and Search-Controller Redesign  
**Deliverable Directory:** `discovery_kernel_v01/results/baseline_representability_audit_20261019/`  

---

## 1. Executive Verdict & Case Determination

Based on direct code audits, empirical execution benchmarks on all 20 development instances, and counterfactual parity verifications:

### **VERDICT: CASE B & CASE C (Compound Structural & Budget Barrier)**

The prior diagnostic claim—that *"the winning baseline (`neh_ls_insertion`) was already present in the candidate space and AI search failed purely due to poor navigation"*—**is mathematically and empirically FALSE.**

In actual execution under the current kernel rules:
1. **CASE B (Primary Constraint — Budget Truncation):**  
   The baseline `neh_ls_solve` executes an unconstrained single pass of Taillard insertion, consuming $n(n-1)$ evaluations ($380 \le M \le 14,280$ evaluations per instance). In contrast, the declarative candidate schema imposes a hard ceiling of $\text{budget} \le 500$ evaluations. On 80% of development instances ($n \ge 30$), the candidate algorithm is forcibly terminated before examining even a single complete pass of the neighborhood (evaluating as few as 3.5% of the jobs on $n=120$). On average across dev instances, the best reachable bounded candidate in the entire search space under budget=500 achieves $C_{\max} = 3584.15$, trailing the unconstrained baseline ($C_{\max} = 3576.95$) by +7.20 makespan units (+0.201%).
2. **CASE C (Secondary Constraint — Structural Semantics Discrepancy):**  
   Even if the budget is artificially expanded, the nominal declarative configuration fails on 35% of instances due to line 365 of `pfsp_declarative.py`, which hardcodes a secondary flow-time tie-break (`or (c_cand == best_ins_cmax and f_cand < best_ins_flow)`). The baseline `neh_ls_solve` uses strict `<` makespan comparison, breaking ties by first-found position index. Only when both the budget is unconstrained AND the tie-break is aligned does the declarative solver achieve **20/20 (100.0%) exact parity**.

---

## 2. Evidence Synthesis

| Audit Dimension | Target Baseline (`neh_ls_solve`) | Declarative Candidate Space (`pfsp_declarative.py`) | Empirical Consequence |
|---|---|---|---|
| **Local Search Budget** | Unconstrained: evaluates all $n(n-1)$ moves ($380$ to $14,280$) | Capped at $50 \le \text{budget} \le 500$ evaluations | Candidates starved on 80% of dev instances; 28.5x compute advantage granted to baseline at $n=120$. |
| **Local Search Tie-Break** | First-found position index (strict `<` makespan) | Hardcoded secondary total flow-time minimization (`f_cand < best_ins_flow`) | Nominal declarative configuration diverges from baseline on 7/20 instances even with unconstrained budget. |
| **Multi-Pass Semantics** | N/A (single-pass baseline) | Supports `multi_pass_insertion` (up to 5 passes) | **Behavioral Illusion:** Multi-pass exhausts budget inside pass 1 for all $n \ge 30$, making it 100% degenerate with single-pass. |
| **Constructive Heuristics** | Classical NEH ($C_{\max} = 3597.80$) | 60 pure constructive combinations | Best constructive (`idle_time_min`, $C_{\max} = 3588.20$) beats classical NEH by 9.60 units without local search. |
| **Search Space Ceiling** | Reference ($C_{\max} = 3576.95$) | Best bounded reachable config ($C_{\max} = 3584.15$) | **No configuration in the current candidate space can match the baseline on average under schema budget rules.** |

---

## 3. Impact on North BlueStar & Proposed Search-Controller Redesign

### 3.1 The "Search Failure" Fallacy
The previous pilot report concluded that AI candidate generation failed because the LLM was unable to navigate the candidate space toward the baseline. 

This diagnosis is invalid. **An omniscient oracle search controller conducting an exhaustive brute-force search over the candidate space would STILL have failed to discover the baseline**, because the baseline does not exist within the reachable space under the $\text{budget} \le 500$ constraint.

If we had proceeded directly to implementing a sophisticated search controller (e.g., `TabuSearchController` or meta-heuristic search) on the existing DSL, **it would have failed just as reliably**, leading to wasted engineering cycles and erroneous negative conclusions about search algorithms.

### 3.2 Evaluation Budget Asymmetry Must Be Eliminated
The core methodological failure in the pilot was **unequal resource allocation between candidate algorithms and conventional baselines**:
- The baseline was allowed to consume $\mathcal{O}(n^2)$ evaluations (up to 14,280 evaluations).
- Every generated candidate was artificially strangled at 500 evaluations by schema validation.
- Comparing an unconstrained baseline against 500-evaluation bounded candidates is not an algorithm discovery test; it is an unfair compute race.

---

## 4. Mandatory Architectural Requirements for Next Milestone

Before implementing any new search controller or launching further candidate-generation trials, the following four engineering requirements must be satisfied:

### Requirement 1: Instance-Adaptive Budget Scaling
Replace the fixed scalar budget (`budget_evaluations: [50, 500]`) with an instance-adaptive budget rule:
- Either scale candidate budget dynamically by instance dimensions:
  $$\text{Budget}(n) = \alpha \cdot n(n - 1) \quad \text{with } \alpha \in [0.1, 1.0, 2.0]$$
- Or strictly constrain both the baseline and candidates to the **identical evaluation budget** (e.g. 500 evaluations), evaluating the baseline under the same truncation regime.

### Requirement 2: Expose Local Search Tie-Breaking in DSL
Refactor `pfsp_declarative.py` to decouple tie-breaking from hardcoded flow-time logic:
- Add `local_search_tie_break: ["first_found", "last_found", "flow_time_min"]` to the schema.
- Ensure that setting `local_search_tie_break = "first_found"` reproduces strict `<` makespan comparison, granting exact reachable parity with conventional NEH-LS.

### Requirement 3: Prune Search-Space Degeneracies
Cleanse the declarative schema to eliminate deceptive degrees of freedom:
- If `local_search == "none"`, remove inactive fields (`search_strategy`, `acceptance_rule`, `budget_evaluations`) from candidate prompts to avoid wasting LLM context on dead parameters.
- Disallow `multi_pass_insertion` unless the allocated budget is sufficient to complete at least two full passes ($M > 2n(n-1)$).

### Requirement 4: Exploit Constructive Machine-Idle Optimization
The census revealed that purely constructive tie-breaking by machine idle time (`idle_time_min`) improves classical NEH from 3597.80 to 3588.20 (-0.27%), closing 47.6% of the gap to the unconstrained local-search baseline at **zero local-search cost**. This heuristic family should be permanently integrated into the core discovery priors.

---

## 5. Conclusion & Next Step

Experiment 0 is completed and fully documented. 
All four required deliverables are saved in:
`discovery_kernel_v01/results/baseline_representability_audit_20261019/`:
1. `BASELINE_PARITY.md`
2. `BUDGET_ANALYSIS.md`
3. `SEARCH_SPACE_CEILING.md`
4. `DECISION_MEMO.md`

All working tree modifications remain uncommitted in adherence to strict operational constraints. 
No further experimentation, candidate generation, or controller implementation should occur until the candidate space schema and budget scaling are formally updated to ensure mathematical parity with baselines.
