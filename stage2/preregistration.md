# Amaura Labs — Stage 2 Formal Preregistration Protocol

**Experiment Title:** Evaluating the Empirical Value of Execution-Based Selection vs. LLM Judging Under Matched Generation Budget  
**Short Name:** Stage 2 (D vs B)  
**Date:** 2026-10-05  
**Laboratory:** Amaura Labs  
**Status:** Pre-Registered & Frozen (Awaiting Human Main-Run Authorization)  

---

## 1. Central Scientific Mission & Primary Hypothesis

### Primary Question
> **At a matched generation budget, does choosing algorithmic candidates by actually executing them on problem instances add value over a strong prompt that chooses without running anything?**

### Primary Contrast
> **Arm D vs Arm B**
where both arms evaluate the **exact same pool of 20 expert-generated candidates**, and the only difference is the selection mechanism:
- **Arm B:** An execution-blind LLM judge selects 1 candidate based purely on code and theoretical reasoning across 3 independent candidate shuffles.
- **Arm D:** The candidate is selected by actually executing all 20 candidates on development instances and selecting the empirical best performer.

### Null Hypothesis ($H_0$)
There is no statistically significant performance difference between execution-based selection (Arm D) and execution-blind LLM judging (Arm B) on unseen production-like problem distributions ($D - B = 0$), or the difference lies within the pre-registered equivalence margin.

### Alternative Hypothesis ($H_1$)
Execution-based selection (Arm D) statistically outperforms execution-blind LLM judging (Arm B) on unseen problem distributions, exceeding the pre-registered practical margin with Holm-corrected $p < 0.05$.

---

## 2. Experimental Scope & Core Problems

Stage 2 focuses on two pure combinatorial optimization problems with clear ground-truth correctness and zero temporal contamination:

1. **Problem 1: Vertex Graph Coloring**
   - Goal: Minimize chromatic number (total colors used).
   - Target Function: `def color_graph(adj: list[list[int]]) -> list[int]`
   - Feasibility Constraint: Adjacent vertices must not share colors ($colors[u] \neq colors[v]$ for all $v \in adj[u]$).
   - Penalties: 999,999 colors for invalid colorings or timeouts.
   - Benchmark: 8 diverse structural families (Erdos-Renyi, Random Geometric, Scale-Free, Mycielski-like, Small-World, Bipartite with Bridges, Regular, Clustered Partition).

2. **Problem 2: Permutation Flow Shop Scheduling (PFSP, $Fm \mid prmu \mid C_{\max}$)**
   - Goal: Minimize makespan $C_{\max}$ across all machines.
   - Target Function: `def schedule_flowshop(times: list[list[int]]) -> list[int]`
   - Feasibility Constraint: Permutation of $0 \dots n-1$.
   - Penalties: 999,999 makespan for invalid permutations or timeouts.
   - Benchmark: 6 diverse structural families (Taillard uniform, center-machine correlation, job-weight correlation, bimodal, high aspect ratio $n \gg m$, U-shaped load).

*(Note: Cloud scheduling is explicitly excluded from Stage 2 because prior traces are considered burned/reused).*

---

## 3. Four Experimental Arms

Each trial generates two 20-candidate pools:
- **Pool 1:** 20 candidates generated via the frozen Expert Prompt.
- **Pool 2:** 20 candidates generated via 20 distinct diversified conceptual perspectives (Arm C).

| Arm | Pool Source | Selection Mechanism | Evaluator Visibility at Selection |
| :--- | :---: | :--- | :--- |
| **Arm A (Random Pick)** | Pool 1 (Expert) | Real seeded random draw from the 20 candidates (+ pool mean reported). | None |
| **Arm B (Expert + Judge)** | Pool 1 (Expert) | Execution-blind LLM Judge with 3 independent candidate shuffles and deterministic majority voting. | Zero execution results (blind) |
| **Arm C (Amaura Diversified)** | Pool 2 (Diversified) | Evaluated on Development benchmark; candidate with lowest dev score selected. | Development data only |
| **Arm D (Amaura + Expert)** | Pool 1 (Expert) | Evaluated on Development benchmark; candidate with lowest dev score selected. | Development data only |

### Absolute Invariant:
```text
candidate_i_hash_B == candidate_i_hash_D  for all i in [1, 20]
```
The candidate pool for Arm B and Arm D must be cryptographically identical.

---

## 4. Frozen Baselines

- **Graph Coloring:**
  1. `DSATUR` (Brélaz, 1979)
  2. `RLF` (Recursive Largest First, Leighton, 1979)
  3. `TabuCol` (Hertz & de Werra, 1987)
- **PFSP:**
  1. `NEH` (Nawaz, Enscore, Ham, 1983)
  2. `Iterated Greedy (IG)` (Ruiz & Stützle, 2007)

---

## 5. Technical Separation & Hidden Firewall

Benchmark splits are strictly isolated:
- **Pilot:** 24 instances per problem (calibration, difficulty, variance).
- **Dev:** 40 instances (GC) / 36 instances (PFSP) (used for Arm C & D selection).
- **Hidden-final:** 200 instances (GC) / 204 instances (PFSP) (final evaluation).
- **Sealed reserve:** 40 instances (GC) / 36 instances (PFSP) (untouched reserve).

**Firewall Rule:** The hidden dataset is programmatically inaccessible prior to the state machine transitioning to `SELECTIONS_FROZEN`. Any unauthorized access attempts immediately abort and log a security violation.

---

## 6. Budget & Sample Size

- **Main Experiment:** 30 independent trials per problem $\times$ 2 problems = **60 total trials**.
- **Candidate Calls per Trial:** 40 calls (20 Expert + 20 Diversified) = **2,400 total generation calls**.
- **Judge Calls per Trial:** 3 calls = **180 total judge calls**.
- **Subsampling Scaling:** $N \in \{1, 2, 5, 10, 20\}$ evaluated from the exact same 20-candidate pools via deterministic subsampling with zero extra LLM calls.

---

## 7. Statistical Decision Protocol

1. **Primary Metric:** Trial-level score on the hidden-final benchmark.
2. **Primary Hypothesis Test:** Paired Wilcoxon signed-rank test on paired differences $(D - B)$.
3. **Multiple Testing Correction:** Holm-Bonferroni step-down correction across the 2 primary problem tests.
4. **Confidence Intervals:** 95% paired bootstrap confidence intervals (10,000 resamples).
5. **Practical Margins:**
   - Graph Coloring: 0.5 colors.
   - PFSP: 25.0 makespan units.
6. **Selection Regret:**
   $$\text{Regret} = S_{\text{selected}}^{\text{hidden}} - \min_{c \in \text{Pool}} S_c^{\text{hidden}}$$
7. **Cost Fairness Gate:**
   $$\text{Direct Compute Cost}(D) \le 1.10 \times \text{Direct Compute Cost}(B)$$

---

## 8. Outcome Classifications

- **Strong Positive:** D beats B with Holm-corrected $p < 0.05$, CI excluding zero, and effect exceeding the practical margin on **both** core problems.
- **Narrow Positive:** D beats B meaningfully on only **one** core problem.
- **Negative:** D performs worse than B with statistical significance.
- **No Meaningful Advantage:** The 95% CI for $(D - B)$ lies entirely within $[-\text{margin}, +\text{margin}]$.
- **Inconclusive:** Evaluator failure, excessive invalidity (>10% zero-valid pools), or unresolved nondeterminism.
