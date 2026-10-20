# FAIR COMPARISON PROTOCOL: Standardized Evaluation Policy for PFSP Algorithm Discovery

**Date:** 2026-10-20  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**System:** North BlueStar Discovery Kernel v0.1  
**Auditor:** Independent AI Research Scientist & Infrastructure Engineer  

---

## 1. Objective & Scope

This protocol establishes a reproducible, scientifically defensible evaluation policy for comparing AI-discovered heuristics against established conventional baselines in the PFSP domain. 

The objective is to eliminate confounding resource asymmetries—such as granting unconstrained compute to baselines while capping AI candidates, or confusing interpreter overhead with algorithmic search quality.

---

## 2. Evaluation Resource Regimes

In combinatorial optimization benchmarking, three distinct resource regimes exist:

### 2.1 Regime A: Equal Move-Evaluation Budget (Algorithmic Efficiency)
- **Definition:** Every competing method is allocated an identical ceiling on candidate objective function evaluations ($C_{\max}$ calculations):
  $$\text{Budget}(n) = \alpha \cdot n(n - 1) \quad (\text{e.g. } \alpha = 1.0)$$
- **Strengths:** Hardware-agnostic and language-agnostic. Measures the mathematical efficiency of the neighborhood traversal and search heuristics directly.
- **Weaknesses:** Does not penalize algorithms that use complex per-move bookkeeping (e.g. calculating higher-order auxiliary objectives) if they share the same evaluation count.

### 2.2 Regime B: Equal Wall-Clock Budget (Engineering Efficiency)
- **Definition:** Every competing method is allocated an identical wall-clock runtime limit (e.g. 500 ms per instance):
  $$T_{\mathrm{wall}} \le T_{\max}$$
- **Strengths:** Directly reflects real-time deployment constraints. Rewards vectorized code, efficient caching, and fast implementations.
- **Weaknesses:** Heavily confounded by implementation language and low-level optimization (e.g., C/Cython vs pure Python). An inferior search strategy written in C will easily defeat a superior search strategy written in Python under wall-clock parity.

### 2.3 Regime C: Fixed Operation-Complete Budget (Algorithmic Phase Parity)
- **Definition:** Both methods are permitted to complete a defined atomic algorithmic phase (e.g., exactly one full neighborhood pass of insertion or pairwise swap), regardless of move count or elapsed time:
  $$\text{Passes} = 1$$
- **Strengths:** Ensures structural comparability between established heuristics that have well-defined stopping criteria (such as standard NEH-LS).
- **Weaknesses:** If methods employ fundamentally different neighborhood sizes (e.g., adjacent swap vs arbitrary 2-opt), move counts and CPU cost will diverge significantly.

---

## 3. Recommended Default Comparison Policy: Two-Tier Architecture

To evaluate AI-generated candidates fairly without manufacturing artificial advantages for any method, North BlueStar establishes the following **Default Two-Tier Policy**:

```
+-----------------------------------------------------------------------------------+
|                           NORTH BLUESTAR EVALUATION POLICY                        |
+-----------------------------------------------------------------------------------+
|  Tier 1: Algorithmic Quality Gate (Primary)                                       |
|  - Dimension-Adaptive Move Parity: Budget(n) = 1.0 * n(n - 1)                      |
|  - Baseline and candidate MUST operate under the IDENTICAL move evaluation budget.|
|  - Full single-pass completion is guaranteed across all instance sizes.          |
+-----------------------------------------------------------------------------------+
|  Tier 2: Operational Safety Gate (Secondary)                                      |
|  - Wall-clock timeout: 5.0 seconds per instance (process SIGTERM/SIGKILL).         |
|  - Catches infinite loops or pathological algorithmic stalls.                     |
+-----------------------------------------------------------------------------------+
```

### Justification for Default Selection:
1. **Fairness:** Conventional NEH-LS requires exactly $n(n-1)$ evaluations to complete its pass. Allocating $\text{Budget}(n) = 1.0 \cdot n(n-1)$ guarantees that both the baseline and candidates have the computational freedom to complete a full insertion pass, eliminating the truncation artifacts documented in Experiment 0.
2. **Scientific Interpretability:** Operating under equal move budgets isolates the true research question: *Does the candidate make better optimization decisions than the baseline when given the same number of opportunities to explore?*
3. **Robustness Against Implementation Artifacts:** Because both the declarative candidates and the reference baseline are implemented using the same underlying `calc_makespan_ref` and `calc_makespan_and_flow_ref` routines in `benchmark_v1`, equal move budgets translate to consistent, fair CPU utilization.

---

## 4. Multi-Dimensional Reporting Standard

To prevent conflation of quality, algorithmic work, and compute speed, future benchmark reports MUST report outcomes across three orthogonal dimensions:

| Reporting Dimension | Primary Metric | Secondary Metric | Purpose |
|---|---|---|---|
| **Solution Quality** | Mean Makespan ($C_{\max}$) | Relative Percentage Gap vs Baseline ($\Delta\%$) | Measures solution optimization performance. |
| **Algorithmic Work** | Total Evaluations Used | Pass Completion Rate (`completed_pass %`) | Measures search trajectory efficiency and convergence behavior. |
| **Computational Cost** | Mean Wall-Clock Runtime (ms) | Speedup Ratio ($T_{\mathrm{base}} / T_{\mathrm{cand}}$) | Measures practical execution cost and runtime feasibility. |

Under no circumstances may a candidate be declared superior to a baseline if it achieves a lower makespan solely by consuming a larger evaluation budget.
