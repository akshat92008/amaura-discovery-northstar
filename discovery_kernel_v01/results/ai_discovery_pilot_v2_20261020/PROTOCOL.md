# PREREGISTERED EXPERIMENTAL PROTOCOL: AI Discovery Pilot v2

**Experiment Title:** Corrected AI Discovery Pilot v2: Fair Budgets, Search Diversity and Unseen-Data Verification  
**Date:** 2026-10-20  
**Domain:** Permutation Flow-Shop Scheduling (PFSP) — Makespan Minimization ($C_{\max}$)  
**System:** North BlueStar Discovery Kernel v0.1  
**Lead Experimental Scientist & Infrastructure Engineer:** Amaura Labs  

---

## 1. Scientific Hypotheses & Objective

### 1.1 Core Hypotheses
1. **$H_1$ (Discovery Advantage):** A diversity-controlled, evidence-guided AI search process (Arm B) can discover an algorithm within the declarative candidate space that achieves $\ge 1.0\%$ mean relative makespan improvement over the established NEH-LS baseline on untouched holdout instances.
2. **$H_2$ (Search Policy Advantage):** Evidence-guided search with explicit diversity control and tabu mechanisms (Arm B) produces higher-performing and more distinct algorithm configurations than independent Best-of-N candidate generation (Arm A) under identical proposal budgets.

---

## 2. Experimental Design & Resource Allocation

### 2.1 Arm Comparison
Both arms use the exact same model, candidate grammar, dataset, evaluation supervisor, and generation budget:

| Arm | Description | Block Structure | Total Proposal Calls | Feedback / Interventions |
|---|---|---|:---:|---|
| **Arm A (Independent Best-of-N)** | Neutral independent candidate generation | 5 independent blocks $\times$ 6 proposals per block | **30** | Zero feedback. Model receives only the neutral grammar and format schema. No recipe examples provided. |
| **Arm B (Diversity-Controlled Search)** | Evidence-guided search with tabu memory | 5 independent blocks $\times$ 6 proposals per block (3 rounds of 2) | **30** | Round 1 (2 props): Neutral schema.<br>Round 2 (2 props): Evidence from Rd 1 + Tabu list + Mutation directive.<br>Round 3 (2 props): Evidence from Rds 1-2 + Tabu list + Mutation directive. |
| **Total** | — | — | **60 calls** | **$0.00 spend** |

### 2.2 Duplicate Handling Policy
- Every proposal is mapped to its canonical recipe hash.
- If a proposal produces an identical hash to a previously evaluated candidate in that block/arm, it is marked as `is_syntactic_duplicate = True`.
- The duplicate counts against the 30-call proposal budget; no extra replenishment calls are issued.
- Redundant evaluations are skipped by reusing the already-recorded development results.

---

## 3. Candidate Grammar & Fixed-Budget Enforcement

- **Permitted Options:**
  - `initial_order`: `total_processing_time_desc`, `total_processing_time_asc`, `first_machine_asc`, `last_machine_desc`, `weighted_profile_desc`
  - `construction_criterion`: `makespan_only`, `makespan_and_flow_time`, `makespan_and_idle_time`
  - `tie_break`: `first_found`, `last_found`, `flow_time_min`, `idle_time_min`
  - `local_search`: `none`, `pairwise_swap`, `single_pass_insertion`
  - `search_strategy`: `first_improvement`, `best_improvement` (or `none`)
  - `acceptance_rule`: `strictly_better_makespan`, `better_makespan_or_flow` (or `none`)
- **Exclusion:** `multi_pass_insertion` is excluded from the primary candidate grammar to prevent budget ambiguity.
- **Fair-Compute Budget Policy:**
  Every candidate with active local search is executed with `budget_evaluations = "single_pass"`, allocating exactly $B(n) = n(n-1)$ evaluations for insertion or $n-1$ for swap. Candidates cannot choose arbitrary budgets.
- **Safety Timeout:** 5.0 seconds per instance via process-isolated `ExecutionSupervisor`.

---

## 4. Model Provenance & Local Host Policy

- **Provider:** Local Ollama runtime (`http://127.0.0.1:11434/api/generate`).
- **Model:** `qwen2.5-coder:1.5b`.
- **Financial Spend:** Exactly **$0.00** (strictly local loopback inference).
- **External API Calls:** Exactly **0**.
- **Sampling Temperature:** 0.7 across all proposal calls.

---

## 5. Dataset Governance & Strict Firewall

1. **Development Dataset (`data/dev_instances.json`):**
   - 20 instances. Seeds: **600001 to 600020**.
   - SHA-256: `a036d4aff75cf88de2b9a4c8bb846649f2e44c479ad7fc341311897fe8b47d97`.
   - Used exclusively for candidate search, feedback generation, and champion selection.
2. **Final Holdout Dataset (`data/holdout_instances.json`):**
   - 30 instances. Seeds: **600101 to 600130**.
   - SHA-256: `8c4e8995896a75ebd98a52079c756a34d3daad1ece0a54c2be55c7e6a4f8be66`.
   - Zero overlap with any historical seed in repository.
   - **Strict Firewall:** Sealed until Champion A and Champion B are selected and frozen.

---

## 6. Conventional Baselines

1. **NEH-LS (`neh_ls_solve`):** Nawaz-Enscore-Ham with single-pass insertion local search (Frozen Reference Baseline).
2. **Classical NEH (`neh_solve`):** Classical constructive heuristic (1983).
3. **Iterated Greedy (`iterated_greedy_solve`):** Ruin-and-recreate metaheuristic ($d=4$, $\text{max\_iter}=20$).

---

## 7. Preregistered Discovery Gate & Success Criteria

The primary discovery gate requires an AI-generated champion to:
1. **Valid Execution:** Produce valid permutations on all 30 final holdout instances.
2. **Discovery Threshold:** Achieve $\ge 1.0\%$ mean relative makespan improvement against the frozen NEH-LS baseline:
   $$\bar{g} = \frac{1}{30} \sum_{i=1}^{30} \frac{C_{\max,\mathrm{baseline},i} - C_{\max,\mathrm{candidate},i}}{C_{\max,\mathrm{baseline},i}} \ge +0.010$$
3. **Statistical Confidence:** Paired 95% bootstrap confidence interval (10,000 resamples) lower bound $> 0.0\%$.
4. **Budget Compliance:** Complete all instances within the preregistered budget ($B(n)=n(n-1)$) and safety timeout ($5.0\text{s}$).

A result below the 1.0% threshold constitutes a **failed discovery gate**, regardless of whether it achieves marginal statistical significance or faster runtime.
