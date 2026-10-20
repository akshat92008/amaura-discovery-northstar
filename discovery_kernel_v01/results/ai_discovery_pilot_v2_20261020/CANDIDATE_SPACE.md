# CANDIDATE SPACE SPECIFICATION: PFSP Declarative Grammar & Resource Policy

**Date:** 2026-10-20  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**System:** North BlueStar Discovery Kernel v0.1 — Experiment Pilot v2  
**Auditor / Infrastructure Engineer:** Lead Experimental Scientist  

---

## 1. Candidate Grammar Architecture

Algorithms in this experiment are composed declaratively from verified, deterministic components. Arbitrary code execution is strictly prohibited. The candidate grammar is constrained to:

### 1.1 Permitted Algorithmic Components

```
1. initial_order:
   - "total_processing_time_desc"      (LPT: Sum of processing times descending, standard NEH)
   - "total_processing_time_asc"       (SPT: Sum of processing times ascending)
   - "first_machine_asc"               (Johnson-like: First machine processing time ascending)
   - "last_machine_desc"               (Johnson-like: Last machine processing time descending)
   - "weighted_profile_desc"           (Palmer's slope weighting index descending)

2. construction_criterion:
   - "makespan_only"                   (Evaluate partial schedules by C_max alone)
   - "makespan_and_flow_time"          (Minimize C_max primary, total flow time secondary)
   - "makespan_and_idle_time"          (Minimize C_max primary, machine idle time secondary)

3. tie_break:
   - "first_found"                     (First position achieving minimum score)
   - "last_found"                      (Last position achieving minimum score)
   - "flow_time_min"                   (Break score ties by minimal total flow time)
   - "idle_time_min"                   (Break score ties by minimal machine idle time)

4. local_search:
   - "none"                            (Pure constructive heuristic, no local search)
   - "pairwise_swap"                   (Adjacent pairwise swap neighborhood)
   - "single_pass_insertion"           (Taillard single-pass insertion neighborhood)
   [NOTE: multi_pass_insertion is excluded from primary grammar per preregistered protocol]

5. search_strategy:
   - "none"                            (Required when local_search is "none")
   - "first_improvement"               (Accept first improving neighbor)
   - "best_improvement"                (Scan neighborhood pass and accept best improving move)

6. acceptance_rule:
   - "none"                            (Required when local_search is "none")
   - "strictly_better_makespan"        (Accept only if makespan strictly decreases)
   - "better_makespan_or_flow"         (Accept if makespan decreases, or makespan ties and flow time decreases)

7. budget_evaluations:
   - Fixed external budget: "single_pass" (or 0 if local_search is "none").
   - Candidate proposals cannot select arbitrary budgets to gain unfair compute advantages.
```

---

## 2. Resource Budget Semantics & Fair Compute Policy

To guarantee mathematical parity with conventional baselines and eliminate computational starvation:
1. **Dynamic Single-Pass Budget Allocation:**
   Every local search candidate is automatically provisioned with the exact single-pass neighborhood budget:
   $$B(n) = n(n - 1) \quad \text{for insertion}$$
   $$B(n) = n - 1 \quad \text{for adjacent swap}$$
   bounded by a hard safety cap of `MAX_EVALUATION_BUDGET = 50000`.
2. **External Controller Enforcement:**
   The search controller injects `budget_evaluations = "single_pass"` for all candidates with active local search. A candidate proposal cannot request or receive additional move evaluations.
3. **Operational Safety Timeout:**
   A hard per-instance timeout of 5.0 seconds is enforced by the process-isolated `ExecutionSupervisor`.

---

## 3. Neutral Representation Format

Candidate proposals must be valid JSON objects with two fields:
- `"rationale"`: String explaining the design hypothesis.
- `"config"`: Object containing the 6 component keys.

No concrete recipe example is provided in prompts to avoid prompt-anchoring bias.
