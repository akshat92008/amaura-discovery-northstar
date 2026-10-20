# SEARCH STRATEGY BENCHMARK V1: PREREGISTRATION PROTOCOL
**Amaura Labs — Autonomous Heuristic Discovery Engine Evaluation**  
**Date:** 2026-10-18  
**Status:** Pre-registered Prior to Confirmatory Trials  
**Git Branch:** `search-benchmark-v1`  
**Commit Baseline:** `590f506`  

---

## 1. Executive Summary & Objective

The objective of this investigation is to empirically determine whether feedback from evaluated candidates (iterative refinement, population evolution, diversity-aware multi-island search, or instance-level evidence guidance) allows an LLM-driven discovery engine to discover better combinatorial optimization heuristics than independent Best-of-$N$ candidate sampling under strictly matched proposal budgets.

Every method must earn its place through measured, statistically verified performance. A rigorously documented null result is completely acceptable. A fabricated winner is strictly forbidden.

---

## 2. Research Questions & Formal Hypotheses

### Research Questions
1. Does single-lineage iterative refinement outperform independent Best-of-$N$?
2. Does standard population-based evolution outperform Best-of-$N$?
3. Does diversity-aware, multi-island search outperform ordinary evolution and Best-of-$N$?
4. Is instance-level failure diagnosis more effective than aggregate scalar scores alone?
5. Do multiple independent restarts (width) outperform deeper iterative search (depth) at the exact same proposal budget?
6. Does any observed advantage generalize across unseen test problem instances and multiple distinct problem families?

### Formal Statistical Hypotheses
For any feedback arm $X \in \{\text{Arm B, Arm C, Arm D, Arm E}\}$ compared against the control $\text{Arm A (Best-of-}N\text{)}$:
- **Null Hypothesis ($H_{0, X}$):** The median paired difference in relative gap on held-out test instances between Arm $X$ and Arm A is zero ($\tilde{\Delta} = \text{Gap}_X - \text{Gap}_A = 0$). Feedback provides no generalization advantage over independent sampling.
- **Alternative Hypothesis ($H_{1, X}$):** Arm $X$ achieves a statistically significant, practically meaningful reduction in relative gap compared to Arm A ($\tilde{\Delta} \le -0.01$, i.e. at least 1 percentage point improvement) on held-out test instances.

For Width vs. Depth:
- **Null Hypothesis ($H_{0, \text{alloc}}$):** At fixed budget $B$, allocating proposals across $W$ independent trajectories yields identical test performance to a single deep trajectory ($W=1$).
- **Alternative Hypothesis ($H_{1, \text{alloc}}$):** Distributed width ($W \in \{4, 8\}$) outperforms single-trajectory depth ($W=1$) by reducing stagnation in local basins of attraction.

---

## 3. Benchmark Problem Families & Representations

All search methods receive the identical candidate representation, algorithm skeleton, and evaluation framework within each domain.

### A. Online 1D Bin Packing
- **Skeleton:** `DeterministicBinPackingSimulator` (item placement by priority score).
- **Interface:** `def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float`
- **Objective:** Minimize normalized excess ratio $\rho = \frac{\text{bins\_used} - L_1}{L_1}$, where $L_1 = \lceil \frac{\sum \text{items}}{\text{capacity}} \rceil$.
- **Primary Baseline:** Best-Fit ($\rho_{\text{train}} = 0.031433$, $\rho_{\text{test}} = 0.033621$ [^erratum_test_bf]).
[^erratum_test_bf]: **Erratum (2026-10-18):** Re-computation on cryptographic test set `test.json` (SHA-256 `02f2fad5...`) yields true $\rho_{\text{test}} = 0.032435$. The recorded value `0.033621` was a clerical transcription error during preregistration drafting. The execution engine dynamically computes $0.032435$ at runtime; see full audit memo in [`benchmark_v1/audit/DISCREPANCY_BEST_FIT_TEST_BASELINE.md`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/audit/DISCREPANCY_BEST_FIT_TEST_BASELINE.md).
- **Dataset:** 20 training item streams (`train.json`), 100 sealed held-out test streams (`test.json`).
- **Penalty for Invalid Candidates:** Instance-normalized penalty $\rho = 1.0$ (100% excess bins).

### B. Vertex Graph Coloring
- **Skeleton:** Deterministic greedy sequential coloring engine (`GraphColoringSimulator`).
- **Interface:** `def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float`
- **Objective:** Minimize total unique chromatic number $k$ across all graphs.
- **Primary Baseline:** DSATUR (Brélaz 1979) ($k_{\text{train}} = 132.0$ colors / 6.60 avg; $k_{\text{test}} = 278.0$ colors / 6.95 avg).
- **Secondary Baseline:** Welsh-Powell (1967).
- **Dataset:** 20 training graphs (`train.json`), 40 sealed held-out test graphs (`test.json`).
- **Penalty for Invalid Candidates:** Deterministic upper bound $k = \sum |V|$ (worst possible single-vertex coloring).

### C. Permutation Flow-Shop Scheduling (PFSP)
- **Skeleton:** Constructive NEH insertion engine with Taillard (1990) $O(m \cdot i)$ acceleration (`PFSPSimulator`).
- **Interface:** `def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float`
- **Objective:** Minimize total makespan $C_{\max}$ across all flowshops.
- **Primary Baseline:** Nawaz-Enscore-Ham (NEH 1983) ($C_{\max, \text{train}} = 84,907$ / 4,717.06 avg; $C_{\max, \text{test}} = 176,409$ / 4,900.25 avg).
- **Secondary Baseline:** Natural Order Insertion ($C_{\max, \text{train}} = 85,106$).
- **Dataset:** 18 training flowshops (`train.json`), 36 sealed held-out test flowshops (`test.json`).
- **Penalty for Invalid Candidates:** Corrected instance-normalized penalty: $2 \times \sum \text{processing times}$. Guarantees invalid candidates never beat valid solutions (repaired historical Stage 2 bug).

---

## 4. Search Arms

1. **Arm A — Independent Best-of-$N$ (Control):**
   Evaluates initial seeds, then samples independent candidate heuristics with zero feedback from earlier candidate evaluations, scores, winners, or failures.
2. **Arm B — Single-lineage Iterative Refinement:**
   Selects the best seed as champion. At each step, prompts for targeted refinement conditioned on the champion code and measured training performance. Strictly replaces champion upon discovering a strictly superior valid candidate.
3. **Arm C — Standard Population-based Evolution:**
   Maintains a population of size $P=10$. Uses tournament selection ($k=2$) to choose parents, generates mutations/crossovers, and applies steady-state replacement with elitism.
4. **Arm D — Diversity-aware Multi-Island Evolution:**
   Maintains 3 distinct subpopulations ($P_i=4$ each) with specialized search biases (exploitation, exploration, robustness). Filters candidates based on behavioral profile correlation (Spearman rank correlation $> 0.99$ rejected as redundant). Executes ring migration of island champions every 16 proposals.
5. **Arm E — Evidence-Guided Search:**
   Extracts concrete evaluator diagnostics (per-instance loss, counterexample instances where candidate loses to baseline, structural bottleneck diagnosis). Explicitly requires candidate proposals to state an improvement hypothesis before generating code.

---

## 5. Experimental Conditions & Budget Allocation

### Total Proposal Budgets
- **Budget 128:** 128 total candidate attempts per trial.
- **Budget 512:** 512 total candidate attempts per trial.

### Width-vs-Depth Allocations
At each total budget $B \in \{128, 512\}$:
- **Depth ($W=1$):** 1 trajectory of $B$ proposals.
- **Width 4 ($W=4$):** 4 independent trajectories of $B/4$ proposals each.
- **Width 8 ($W=8$):** 8 independent trajectories of $B/8$ proposals each.

### Strict Accounting & Firewall Rules
1. **Proposal Counting:** Every proposal attempt (canonical seeds, AI proposals, duplicates, syntax errors, timeouts) counts toward the total budget.
2. **Quarantine:** The test set (`test.json`) is strictly sealed during candidate generation and selection. Champion selection is determined purely by performance on `train.json`.
3. **Post-Selection Evaluation:** The selected champion from each trial is evaluated on `test.json` exactly once to assess generalization.

---

## 6. Statistical Decision Framework

- **Primary Metric:** $\text{Relative Gap} = \frac{S_{\text{candidate}} - S_{\text{baseline}}}{S_{\text{baseline}}}$ on held-out test data.
- **Meaningful Difference Threshold:** $\Delta_{\text{rel}} \le -0.01$ (-1.0 percentage point improvement).
- **Hypothesis Testing:** Two-sided paired Wilcoxon signed-rank test across matched seed blocks.
- **Multiple Testing Correction:** Holm-Bonferroni step-down procedure across the 4 feedback arms within each domain-budget condition.
- **Confidence Intervals:** 10,000-resample paired bootstrap 95% confidence intervals for $\mathbb{E}[\text{Gap}_{\text{Arm}} - \text{Gap}_{\text{Arm A}}]$.
- **Stopping Rule:** Fixed sample size of $N=20$ paired trials per cell in confirmatory evaluation. No optional stopping or post-hoc trial expansion.
