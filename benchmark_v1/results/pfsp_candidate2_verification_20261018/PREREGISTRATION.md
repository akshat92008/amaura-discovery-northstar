# PREREGISTRATION & PROTOCOL SPECIFICATION
## Experiment: PFSP Candidate #2 Verification & Scalability Benchmark
**Milestone:** Candidate Verification & Independent Replication  
**Date:** 2026-10-18  
**Experiment ID:** `pfsp_candidate2_verification_20261018`  
**Results Directory:** `benchmark_v1/results/pfsp_candidate2_verification_20261018/`  
**Domain File:** [`benchmark_v1/src/domains/pfsp_candidate2_variants.py`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/src/domains/pfsp_candidate2_variants.py)  

---

### 1. Research Hypothesis & Core Objectives

In our previous live-LLM discovery pilot (`pfsp_full_algorithm_pilot_20261018`), Proposal #2 emerged as the sole valid candidate across all training instances, achieving:
- Total Training Makespan: **84,530** ($-0.44\%$ vs classical NEH at $84,907$; $-0.07\%$ vs single-pass NEH-LS at $84,593$).
- The algorithm combines:
  1. NEH constructive heuristic with initial total-processing-time sorting.
  2. Multi-objective tie-breaking during insertion (minimizing total flow time on equal makespan).
  3. First-improvement pairwise exchange local search.

However, Proposal #2 timed out on held-out test instance 4 ($n=100, m=15$) because its unaccelerated $O(n^2 \cdot m)$ pure-Python search loop exceeded the 4.0s runtime cutoff.

**Primary Objectives:**
1. Independently reproduce the training baseline scores (84,530 vs 84,907 vs 84,593) and document the exact single-pass vs multi-pass distinction in NEH-LS.
2. Mathematically profile the computational growth pattern of Proposal #2.
3. Construct an **exact accelerated variant (Variant 1)** that preserves the candidate's exact moves and decisions while eliminating redundant prefix/suffix operations via Taillard prefix/suffix matrices.
4. Construct an **anytime bounded variant (Variant 2)** that guarantees graceful termination under predefined move evaluation budgets (100, 500, 2000, 10000) and time limits.
5. Formalize a **protocol amendment** evaluating all frozen variants on 30 completely untouched, fresh PFSP instances (seeds 90001–90030) across small, medium, and large dimensions.
6. Issue a definitive **GO, MODIFY, or STOP** verdict based on empirical held-out performance.

---

### 2. Frozen Algorithm Implementations & Hashes

| Variant / Baseline | Function Name | Algorithmic Mechanism | Code SHA-256 Hash |
| :--- | :--- | :--- | :--- |
| **Variant 0 (Reference)** | `solve_v0_original` | Immutable Proposal #2 (pure Python unaccelerated swap) | `78b488ae102af57e35b08e45770bae67d50495e3ac0442f4a57b9404e291a060` |
| **Variant 1 (Exact Accel)** | `solve_v1_exact_accel` | Exact accelerated pairwise swap via prefix $E$ and tail $Q$ vectors | `d94d70903009920aa67a1d2328cb1433fbdf2b6bc9ef8d42680e7c8c32c2f809` |
| **Variant 2 (Anytime Bounded)** | `solve_v2_anytime_bounded` | Budget-capped local search with anytime graceful exit (budgets 100, 500, 2000, 10000) | `ea8eb32ca2999d02d9171a12e72a391d6c4bd25e0d8a3ecaf22fa400a55ab846` |
| **Variant 3 (Insertion LS)** | `solve_v3_insertion_ls` | NEH-Flow-Time + Taillard accelerated insertion neighborhood | `03a78c1aafbff3779ad731b8239f3e90bd1db1490be38e8e6ce6819283ef4e3c` |
| **Baseline 1** | `neh_solve` | Nawaz-Enscore-Ham standard constructive heuristic | `aec1c0cedd0812d6e639a06c1e36ef047cc819dd87265881a4870c4d170a5050` |
| **Baseline 2A** | `neh_ls_single_pass_solve` | NEH + single-pass insertion local search (original repo baseline) | `5a09282245b7f0535928df77c41369cb6a213032b4927b587a8f3319be7f66ca` |
| **Baseline 2B** | `neh_ls_multi_pass_solve` | NEH + multi-pass insertion local search until local minimum | `99d3ba67cf7596ad7442340576fe9cae74ad08ca06ec8f67e5b22b27bc888065` |
| **Baseline 3** | `iterated_greedy_solve` | Ruiz & Stützle (2007) Iterated Greedy ($d=4$, NEH insert, SA acceptance) | `ad19bbcdb4d1e9c1010431a1e3b5704fafe21f4e3fd8976a24adb2f86227ef3c` |

---

### 3. Protocol Amendment: Datasets & Seed Governance

The historical dataset quarantine is preserved:
1. **Training Set (`benchmark_v1/data/pfsp/train.json`):** 18 instances (seeds 40001–40020), SHA-256: `558d5eaf61c313553f32ac0e32be971ef3d8ae84c4d0756d905d8fb4eb4a8595`.
2. **Development Set (`benchmark_v1/data/pfsp/test.json`):** 36 instances (seeds 41001–41100), SHA-256: `2f450676400f71f9085f0c3e3866c112ed3256d78bb5736d1a1f979a56460bbb`. Formerly held-out; reclassified as development data due to timeout inspection.
3. **Protocol Amendment — Fresh Replication Dataset (`benchmark_v1/data/pfsp/fresh_replication_instances.json`):**
   - 30 fresh, independent instances generated using `taillard_uniform` distributions ($p_{j,m} \in [1, 99]$).
   - Seeds: **90001 to 90030** (disjoint from all prior experiments).
   - SHA-256: `a601678c7f8b5a4805da567ee43214e2f05f41c48abd941842426ad0906e54b0`.
   - Instance Breakdown:
     - Small ($n \in [20, 30], m \in [5, 10]$): 8 instances (seeds 90001–90008)
     - Medium ($n \in [50, 75], m \in [5, 15]$): 14 instances (seeds 90009–90022)
     - Large ($n \in [100, 120], m \in [10, 15]$): 8 instances (seeds 90023–90030)

---

### 4. Correctness & Unit Test Gate
Before evaluating on fresh instances, all algorithms must pass the formal correctness suite in [`benchmark_v1/tests/test_candidate2_verification.py`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/tests/test_candidate2_verification.py):
- Reference makespan manual calculation match.
- Exhaustive mathematical equivalence of accelerated swap evaluation against full recomputation across all moves.
- Complete search trajectory and permutation equivalence between Variant 0 and Variant 1.
- Monotonic non-degradation of Variant 2.
- Permutation validation edge cases.

---

### 5. Preregistered Decision Rules

1. **GO — Verified Discovery:**
   - Improved variant (Variant 1 or 2) achieves $\ge 1.0\%$ relative makespan reduction over NEH on the 30 fresh instances.
   - Non-inferior to NEH-LS under comparable computational budgets.
   - Zero timeouts and 100% permutation validity.
2. **MODIFY — Partial Improvement / Architectural Refinement:**
   - Correctness and scalability established (0 timeouts, exact speedup verified).
   - Outperforms NEH on fresh data, but margin is $< 1.0\%$ or dominated by multi-pass insertion search.
   - Requires modular hybridization or refinement of neighborhood topology.
3. **STOP — Candidate Disconfirmed:**
   - Candidate fails to beat NEH on fresh data, or loses across all instance sizes to standard baselines.
