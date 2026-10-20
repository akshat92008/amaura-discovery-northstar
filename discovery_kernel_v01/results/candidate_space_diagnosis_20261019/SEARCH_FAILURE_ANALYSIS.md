# SEARCH FAILURE ANALYSIS: Feedback Dynamics, Prompt Anchoring & Model Limitations
## Deconstructing the Failure Modes of Evidence-Guided Search in North BlueStar

**Date:** 2026-10-19  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Auditor:** Independent AI Research Scientist & Algorithm-Discovery Engineer  

---

## 1. The Core Paradox: Why Did Feedback Degrade Performance?

In the pilot experiment, the empirical outcomes exhibited a striking counterintuitive result:
- **Arm A (Independent Search, Zero Feedback):** Discovered `arm_a_prop_08` ($C_{\max} = 3887.70$, 6 distinct behaviors explored).
- **Arm B (Evidence-Guided Search, 3 Rounds of Feedback):** Discovered `arm_b_prop_01` ($C_{\max} = 3974.43$, only 1 distinct behavior explored).
- **Effect Size:** Feedback-guided search was **-2.151% worse** than independent generation (95% Bootstrap CI: $[-2.625\%, -1.658\%]$).

This document separates the causal mechanisms behind this collapse into five distinct hypotheses and evaluates the direct evidence for each.

---

## 2. Dissection of the Generation Pipeline and Prompts

### 2.1 The Prompt Architecture in `discovery_kernel/generator.py`
Inspection of `generator.py` reveals the exact prompt construction:

```python
BASE_SYSTEM_PROMPT = """...allowed options for 7 fields..."""

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

In Arm B, the feedback prompt for Rounds 2 and 3 was assembled as:
```python
prompt = f"""{BASE_SYSTEM_PROMPT}

EVIDENCE FROM PREVIOUS ROUND(S) ON DEVELOPMENT INSTANCES:
{feedback_summary}

Based on this evidence, analyze what worked best (e.g. construction criterion, tie-break, local search neighborhood).
Propose an improved or refined configuration that aims to outperform the best seen makespan.

Example format:
{SCHEMA_EXAMPLE}

Output only the JSON object."""
```

### 2.2 What the System Communicated (and Failed to Communicate)

1. **Reward Formulation:** The feedback prompt reported only scalar mean makespan scores. It communicated **zero per-instance breakdowns**, zero information about why a candidate succeeded or failed (e.g. whether it struggled on small vs. large instances), and zero runtime or resource metrics.
2. **Exploration Direction:** The instruction stated: *"analyze what worked best... propose an improved or refined configuration that aims to outperform the best seen makespan."*  
   In natural language, "refine what worked best" strongly primes a transformer to keep the majority of the leader's features unchanged and tweak only minor parameters.
3. **Absence of Novelty Pressure:** The prompt contained **no instruction to diverge**, no penalty for repeating previously evaluated configurations, and no diversity tracking.
4. **Saturation of Demonstrations:** In Round 2 and Round 3, `SCHEMA_EXAMPLE` contained the Palmer slope recipe, `Best Config Recipe` contained the Palmer slope recipe, and `Recent Round Results` listed 4 proposals all using the Palmer slope recipe. Over 75% of the prompt context was composed of tokens describing a single recipe (`weighted_profile_desc`, `makespan_only`, `flow_time_min`, `single_pass_insertion`).

---

## 3. Evaluation of Competing Explanations

### Explanation 1: Prompt Anchoring (In-Context Attractor Bias)
- **Definition:** The language model treats few-shot examples and in-context feedback as strong attractors in token probability space, causing it to output the demonstration tokens with high probability.
- **Direct Evidence (PROVEN):**
  - Out of 24 total proposals across both arms, **14 proposals (58.3%)** matched the few-shot demonstration (`4e970cdd`) verbatim.
  - In Arm B, where the feedback reinforced that this exact recipe was the "Best Candidate So Far", **10 of 12 proposals (83.3%)** copied it verbatim.
  - In Arm A, where no feedback reinforced it, the model still copied the example 4 times out of 12.
- **Verdict:** **Confirmed Primary Driver.** The prompt's example acted as a deep local attractor that suppressed generation entropy.

---

### Explanation 2: Search-Controller Failure (Exploitation Without Exploration)
- **Definition:** The supervisory controller passed feedback in a manner that greedily exploited the current best score without implementing exploration mechanisms (temperature scheduling, tabu lists, novelty search, or mutation constraints).
- **Direct Evidence (PROVEN):**
  - The controller generated proposals in simple unconstrained batches without checking against a registry of evaluated `recipe_hash`es.
  - When proposal `arm_b_prop_05` duplicated `arm_b_prop_01`, the controller accepted it, spent compute evaluating it on 20 instances, and logged a duplicate score without intervention.
  - The controller provided no temperature scaling or novelty prompts across rounds.
- **Verdict:** **Confirmed Structural Flaw.** The search controller functioned as an open-loop conversational interface rather than an optimization algorithm.

---

### Explanation 3: Representation Collapse (Degenerate Mappings)
- **Definition:** The model proposes syntactically different recipes, but the underlying execution engine maps them to identical trajectories.
- **Direct Evidence (PARTIALLY PROVEN):**
  - In Arm B, `arm_b_prop_02` used `local_search="multi_pass_insertion"`, whereas `arm_b_prop_01` used `single_pass_insertion`.
  - Because `budget_evaluations` was set to 250, both configurations truncated mid-pass on all instances $n \ge 30$, producing mathematically identical scores (3654.15) on all 20 dev instances.
  - However, representation collapse was secondary to prompt anchoring: the model did not propose diverse neighborhoods that collapsed; it failed to propose diverse neighborhoods in the first place.
- **Verdict:** **Contributing Factor.** Low evaluation budgets masked the difference between single-pass and multi-pass search.

---

### Explanation 4: Model Limitations (`qwen2.5-coder:1.5b`)
- **Definition:** The parameter capacity (1.54B) of the local model is insufficient to maintain reasoning context, parse optimization feedback, and perform counterfactual algorithm design.
- **Direct Evidence (STRONGLY SUPPORTED):**
  - The model produced valid JSON (100% syntactic compliance), demonstrating strong base instruction-following.
  - However, when asked to "improve or refine" based on evidence, it lacked the reasoning capacity to perform semantic ablation (e.g. "Palmer slope produced 3654, but NEH LPT order might do better"). Instead, it engaged in simple token copying.
- **Prior Repository Evidence (Crucial Context):**
  - Would a 70B or 120B model solve this?
  - In `benchmark_v1/results/live_llm_binpacking_pilot_20261018/LIVE_PILOT_REPORT.md`, **Nvidia Nemotron-3 Super 120B** was evaluated on online bin packing across 160 live queries.
  - Despite being an order of magnitude larger and having full frontier reasoning capabilities, **116 of 138 valid proposals (84.1%) collapsed into the monotonic equivalence trap of Best-Fit**.
  - Similarly, in `stage3` with **Claude 3.5 Sonnet**, closed-loop conversational feedback on graph coloring led to hallucinated score improvements and prompt saturation.
- **Verdict:** **Major Contributing Factor, but Not Solved by Scale Alone.** Small models suffer from immediate copying; large models suffer from subtler semantic convergence and mathematical equivalence traps.

---

### Explanation 5: Evidence Limitations (Experimental Power)
- **Definition:** The sample size (20 dev instances, 30 holdout instances, 12 proposals per arm) was too small to observe true differences.
- **Direct Evidence (REFUTED):**
  - The statistical power was more than sufficient to detect the failure: the 95% bootstrap confidence interval for Arm B vs Arm A was $[-2.625\%, -1.658\%]$, completely excluding zero.
  - Expanding to 500 instances would not change the fact that Arm B tested only 1 unique behavior.
- **Verdict:** **Refuted.** The experimental power was entirely adequate to confirm search failure.

---

## 4. Synthesis: The Triad of Failure

The search failure was caused by the interaction of three factors:
1. **The Static Attractor (Prompt):** Hardcoding a complete, high-quality recipe as the few-shot JSON example provided an immediate token attractor.
2. **The Passive Model:** A 1.5B parameter model lacks the inductive reasoning to deliberately deviate from a prompt example without explicit instructions.
3. **The Unregulated Controller:** The search controller lacked duplicate rejection, novelty pressure, or structured mutation operators, allowing the feedback loop to devolve into an echo chamber.
