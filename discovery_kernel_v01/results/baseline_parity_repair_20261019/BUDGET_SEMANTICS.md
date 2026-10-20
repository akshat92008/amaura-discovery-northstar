# BUDGET SEMANTICS: Resource Accounting & Neighborhood Dynamics

**Date:** 2026-10-20  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**System:** North BlueStar Discovery Kernel v0.1  
**Auditor:** Independent AI Research Scientist & Infrastructure Engineer  

---

## 1. The Methodological Flaw of Fixed Scalar Budget Caps

In earlier pilots, algorithm candidates were constrained by a rigid schema rule:
$$\text{budget\_evaluations} \in [50, 500]$$

This fixed scalar ceiling introduced a severe methodological flaw:

### 1.1 Non-Linear Neighborhood Scaling
The size of a local search neighborhood depends directly on instance dimension $n$:
- **Pairwise Swap Neighborhood:**
  $$M_{\mathrm{swap}}(n) = n - 1$$
  At $n=20$: 19 moves. At $n=120$: 119 moves.
- **Taillard Single-Pass Insertion Neighborhood:**
  $$M_{\mathrm{ins}}(n) = n(n - 1)$$
  At $n=20$: 380 moves. At $n=120$: 14,280 moves.

### 1.2 Induced Starvation & Asymmetric Distortion
Because the budget limit was a fixed scalar rather than an instance-adaptive parameter:
1. **Small Instances ($n=20$):** Budget 500 exceeded the 380 moves required for a complete pass. The algorithm ran to completion.
2. **Large Instances ($n=120$):** Budget 500 allowed evaluating only 500 out of 14,280 moves (**3.5% neighborhood coverage**). Local search examined only 4 out of 120 jobs before being forcibly terminated.
3. **Induced Behavioral Degeneracy:** On instances $n \ge 30$, `multi_pass_insertion` exhausted its 500-evaluation budget inside pass 1. Consequently, `multi_pass_insertion` was **100% behaviorally identical to `single_pass_insertion`** across 80% of development instances and 73% of holdout instances.

Comparing an unconstrained baseline (evaluating 14,280 moves) against candidates capped at 500 moves was not a comparison of algorithm quality; it was an artifact of computational starvation.

---

## 2. Repaired Resource-Budget Specification

The candidate schema and execution kernel now implement an explicit, validated resource-budget model:

```python
MIN_EVALUATION_BUDGET = 50
MAX_EVALUATION_BUDGET = 50000
```

### 2.1 Supported Budget Modes
1. **Dynamic Single-Pass Mode (`budget_evaluations: "single_pass"`):**
   - Automatically provisions exactly the number of evaluations required to execute one full neighborhood pass over the instance:
     $$\text{Budget}_{\mathrm{ins}}(n) = \min(n(n - 1), \text{MAX\_EVALUATION\_BUDGET})$$
     $$\text{Budget}_{\mathrm{swap}}(n) = \min(n - 1, \text{MAX\_EVALUATION\_BUDGET})$$
   - Eliminates arbitrary starvation while maintaining a strict, non-negotiable upper bound (`MAX_EVALUATION_BUDGET = 50000`).
2. **Explicit Bounded Integer Mode (`budget_evaluations: int`):**
   - Permits candidates to specify an explicit evaluation budget between 50 and 50,000.
   - Allows fine-grained control for fast, lightweight polishing heuristics or multi-pass search.
   - Automatically normalized to `0` when `local_search == "none"`.

---

## 3. Explicit Execution Telemetry & Termination Taxonomy

The solver no longer exits silently. Every execution records structured diagnostics:

```json
{
  "evaluations_used": 2450,
  "budget_evaluations": 2450,
  "termination_condition": "pass_complete",
  "completed_pass": true,
  "passes_completed": 1,
  "runtime_ms": 138.4,
  "initial_cmax": 3149,
  "final_cmax": 3128
}
```

### 3.1 Termination Classification
| Termination Condition | Semantic Definition | Pass Completed? |
|---|---|:---:|
| **`pass_complete`** | Method examined every neighbor in the declared pass(es) without hitting budget. Found at least one improving move. | **True** |
| **`converged`** | Method completed a full pass and found zero improving moves (reached local optimum with respect to operator). | **True** |
| **`budget_exhausted`** | `evals_used >= budget_evals` was reached mid-pass before completing the neighborhood scan. | **False** |
| **`constructive_only`** | Local search was disabled (`"none"`). Terminated upon completing the constructive insertion phase. | **True** |

---

## 4. Separation of Move Evaluations from Wall-Clock Time

A fundamental principle of rigorous algorithm benchmarking is that **move evaluation counts must not be equated with CPU cost**:

1. **Move Evaluations as Algorithmic Work:**
   - Counting makespan evaluations ($C_{\max}$) measures the efficiency of the search trajectory through the permutation space, independent of hardware speed, interpreter overhead, or programming language.
2. **Wall-Clock Time as Practical Overhead:**
   - Incremental evaluation of Taillard insertion can be implemented in $\mathcal{O}(m)$ per move in optimized C or Taillard acceleration tables, whereas naive recomputation requires $\mathcal{O}(m \cdot n)$.
   - Pure Python loops incur interpreter overhead that does not reflect fundamental algorithmic search complexity.
3. **Dual Metric Requirement:**
   - Quality ($C_{\max}$), Algorithmic Work (`evaluations_used`), and Computational Speed (`runtime_ms`) must always be reported as independent, orthogonal dimensions.
