# CANDIDATE SPACE ANALYSIS: PFSP Declarative Representation
## Structural Expressiveness, Combinatorial Boundaries, and Behavioral Degeneracy

**Date:** 2026-10-19  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Evaluator Target:** Makespan Minimization ($C_{\max}$)  
**Auditor:** Independent AI Research Scientist & Algorithm-Discovery Engineer  

---

## 1. Declarative Schema Architecture

The candidate space implemented in `discovery_kernel/pfsp_declarative.py` and documented in `CANDIDATE_SPACE.md` defines a declarative Domain-Specific Language (DSL) over verified algorithm components.

### 1.1 Supported Component Choices

```
                                      [ PFSP Candidate Specification ]
                                                     │
                 ┌───────────────────────────────────┴───────────────────────────────────┐
                 ▼                                                                       ▼
       [ Construction Phase ]                                                  [ Local Search Phase ]
  - initial_order (5 options)                                             - local_search (4 options)
    • total_processing_time_desc (LPT)                                      • none
    • total_processing_time_asc (SPT)                                       • pairwise_swap
    • first_machine_asc                                                      • single_pass_insertion
    • last_machine_desc                                                      • multi_pass_insertion
    • weighted_profile_desc (Palmer slope)                                - search_strategy (3 options)
  - construction_criterion (3 options)                                       • none, first_imp, best_imp
    • makespan_only                                                       - acceptance_rule (3 options)
    • makespan_and_flow_time                                                 • none, strictly_better, better_or_flow
    • makespan_and_idle_time                                              - budget_evaluations (integer)
  - tie_break (4 options)                                                    • 0 (if none)
    • first_found, last_found                                                • [50, 500] (if active)
    • flow_time_min, idle_time_min
```

---

## 2. Combinatorial Space Size vs. Behavioral Redundancy

### 2.1 Theoretical Combination Count

1. **Constructive Combinations:**
   $$N_{\mathrm{constructive}} = |\mathrm{initial\_order}| \times |\mathrm{criterion}| \times |\mathrm{tie\_break}| = 5 \times 3 \times 4 = 60$$

2. **Local Search Operator Combinations (excluding budget):**
   - For `local_search == "none"`: Exactly $1$ valid combination (`search_strategy="none"`, `acceptance_rule="none"`, `budget=0`).
   - For `local_search != "none"`:
     $$N_{\mathrm{ls\_ops}} = |\mathrm{neighborhood}| \times |\mathrm{strategy}| \times |\mathrm{rule}| = 3 \times 2 \times 2 = 12$$

3. **Total Structural Configurations (Topology only, excluding budget):**
   $$N_{\mathrm{structural}} = 60 \times 1 + (60 \times 12) = 60 + 720 = \mathbf{780}$$

4. **Nominal Parameter Space (including discrete budgets):**
   - Discretizing `budget_evaluations` into 10 levels ($[50, 100, 150, \dots, 500]$):
     $$N_{\mathrm{discrete}} = 60 + (720 \times 10) = \mathbf{7,260}$$
   - Continuous integer budgets ($[50, 500]$, 451 values):
     $$N_{\mathrm{continuous}} = 60 + (720 \times 451) = \mathbf{324,780}$$

---

### 2.2 Mathematical and Behavioral Redundancies (Degeneracy)

The nominal count of 780 structural configurations overstates the number of genuinely distinct algorithms. Direct inspection of the solver implementation in `pfsp_declarative.py` identifies four major structural degeneracies:

#### Degeneracy 1: Criterion / Tie-Break Collapsing
In `_evaluate_partial_schedule`:
```python
if criterion == "makespan_only":
    primary = cmax
    if tie_break == "flow_time_min":
        secondary = flow
    ...
elif criterion == "makespan_and_flow_time":
    primary = cmax
    secondary = flow
```
- Configuration A: `{"construction_criterion": "makespan_only", "tie_break": "flow_time_min"}`
- Configuration B: `{"construction_criterion": "makespan_and_flow_time", "tie_break": "first_found"}`
- **Mathematical Reality:** Both configurations sort candidate positions by the exact same tuple: `(cmax, flow, 0)`. They produce mathematically identical insertion decisions on all instances. The same holds for `idle_time_min`.

#### Degeneracy 2: Budget Truncation Masking Multi-Pass Search
- On an instance with $n = 50$ jobs, testing the insertion neighborhood requires testing $n(n-1) = 2,450$ moves.
- On an instance with $n = 75$ jobs, a single pass requires $75 \times 74 = 5,550$ moves.
- Because `budget_evaluations` is capped at $500$, `multi_pass_insertion` **never reaches a second pass** on any medium or large instance ($n \ge 30$).
- Consequently, `multi_pass_insertion` with budget $\le 500$ is behaviorally identical to `single_pass_insertion` with the same budget on all instances where $n(n-1) > \text{budget}$.

#### Degeneracy 3: Search Strategy Invariance Under Small Budgets
With a low budget evaluation limit (e.g. 50–100), `best_improvement` evaluates only a partial prefix of the neighborhood for the first 1 or 2 jobs before exhausting its budget. In contrast, `first_improvement` may accept an early improving move and advance. When no neighbor improves in the first few moves, both strategies stall identically.

---

## 3. Excluded and Fixed Algorithmic Capabilities

The current declarative DSL fixes several algorithmic control structures that prevent genuine structural innovation:

| Dimension | Current Implementation | Excluded / Fixed Capabilities |
|---|---|---|
| **Control Flow** | Fixed sequential pipeline: `Order` $\rightarrow$ `Insert` $\rightarrow$ `Local Search` | No loops, no iterative restarts, no adaptive phase switching |
| **Metaheuristic Operators** | Pure descent local search only | No destruction/construction (Ruin-and-Recreate / Iterated Greedy), no simulated annealing, no tabu lists |
| **Neighborhood Types** | Pairwise adjacent swap, sequential insertion | No block insertion, no 2-opt, no variable neighborhood descent (VND) |
| **Scoring Functions** | Hardcoded scalar metrics ($C_{\max}$, flow time, idle time) | No learned weights, no dynamic penalties, no linear combinations |
| **Evaluation Acceleration** | Standard reference makespan calculation | No incremental Taillard acceleration matrix $\mathcal{O}(m)$ per insertion move |

---

## 4. Analysis of Core Research Questions

### Question 1: Is the search space too small, too large, or poorly structured?
**Assessment: The space is moderately sized (780 structural recipes) but poorly structured.**
- It is not too large: 780 configurations can be completely enumerated in fewer than 1,000 evaluations.
- It is poorly structured because:
  1. It mixes categorical architectural choices (order, neighborhood) with a single continuous budget dial that truncates execution mid-stream.
  2. Multiple syntax combinations map to the exact same partial evaluation tuples.
  3. It lacks the iterative loop construct necessary to express modern metaheuristics (such as Iterated Greedy).

### Question 2: Does canonicalization eliminate genuine alternatives or merely syntactic variants?
**Assessment: Canonicalization eliminates only true syntactic duplicates.**
- The canonicalization function `canonicalize_config()` in `discovery_kernel/pfsp_declarative.py` normalizes key order, cleans whitespace, and sets `search_strategy="none"` and `budget=0` when `local_search="none"`.
- It does not merge semantic or mathematical redundancies (e.g. Degeneracies 1 and 2 above). Therefore, canonicalization is strictly sound and conservative; it did not discard any genuine alternatives.

### Question 3: Are important known algorithm families excluded?
**Assessment: YES. The entire class of high-performing PFSP metaheuristics is completely excluded.**
- In PFSP literature (Ruiz & Stützle 2007), standard constructive heuristics (NEH) and single-pass descent (NEH-LS) are merely initialization phases. State-of-the-art results are dominated by **Iterated Greedy (IG)**, **Iterated Local Search (ILS)**, and **Memetic Algorithms**.
- The declarative representation cannot express a destruction phase (removing $d$ jobs) followed by constructive repair, nor can it express an acceptance temperature.

### Question 4: Does the representation primarily permit parameter variations of a few established heuristics?
**Assessment: YES.**
- The representation is essentially a Cartesian product of classical components: Nawaz-Enscore-Ham (1983), Palmer (1965), and Taillard (1990).
- Candidates are not discovering new mathematical principles; they are selecting which classical pre-composed heuristic block to toggle.

### Question 5: Is there direct evidence that the representation prevented an otherwise promising candidate from being expressed?
**Assessment: Direct empirical evidence is NEGATIVE for the tested candidates.**
- While the representation excludes metaheuristics, within the space of constructive heuristics, the representation **already contained the winning baseline** (`neh_ls_insertion`).
- The AI generator failed to select `neh_ls_insertion`'s exact recipe (`initial_order="total_processing_time_desc"`, `criterion="makespan_only"`, `tie_break="first_found"`, `local_search="single_pass_insertion"`, `strategy="best_improvement"`, `budget=250+`).
- Arm A came very close with `arm_a_prop_08` (which differed only in using `tie_break="flow_time_min"` and `budget=300`).
- Therefore, the immediate failure of this pilot was **search navigation**, not representational impossibility. The winning baseline was already in the candidate space, but the search failed to find it.
