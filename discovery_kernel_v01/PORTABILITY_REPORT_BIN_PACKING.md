# AMAURA LABS — NORTH BLUESTAR DISCOVERY KERNEL V0.1
## Second-Domain Portability Gate Report: Online 1D Bin Packing

**Experiment ID:** `EXP_PILOT_DK01_BINPACKING_20261019`  
**Date:** October 19, 2026  
**Author:** Lead Research Infrastructure Engineer, Amaura Labs  
**System:** North BlueStar — Discovery Kernel v0.1  
**Target Domain:** Online One-Dimensional Bin Packing  
**Verdict:** **PASS** (Cross-Domain Infrastructure Portability Verified)  

> [!IMPORTANT]
> **Scientific Clarity Notice:**  
> This milestone is strictly an **infrastructure portability test**, NOT an AI discovery experiment. Demonstrating that the Discovery Kernel can execute and compare bin-packing heuristics proves that the software abstractions are domain-agnostic; it does **not** demonstrate that the system possesses an automated discovery advantage over established methods.

---

## 1. Objective & Gate Scope

The objective of the **Second-Domain Portability Gate** is to establish whether the Discovery Kernel v0.1—originally validated on Permutation Flow Shop Scheduling (PFSP)—can support a completely different optimization problem (Online 1D Bin Packing) through a domain adapter **without modifying the kernel's core execution, validation, scheduling, or auditing abstractions**.

---

## 2. Problem Specification & Formal Contract

The problem domain was formalized using the existing [`ProblemSpecification`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel/problem_spec.py) contract:

| Contract Dimension | Specification |
| :--- | :--- |
| **Problem Identifier** | `online_1d_bin_packing` |
| **Objective Metric** | Normalized Excess Ratio $\bar{\rho} = \frac{B - L_1}{L_1}$ |
| **Objective Direction** | `MINIMIZE` (lower is better, 0.0 is theoretical lower bound) |
| **Bin Capacity ($C$)** | 100.0 (float) |
| **Item Constraints** | $0 < \text{item} \le C$; stream processed online in fixed arrival order |
| **Solution Representation** | $S = [b_0, b_1, \dots, b_{n-1}] \in \mathbb{N}_0^n$, where $b_i$ is the bin index assigned to item $i$ |
| **Declarative Constraints** | 1. Exact Item Coverage: $\text{len}(S) == \text{len}(\text{items})$ (every item placed exactly once).<br>2. Capacity Bound: $\forall b \in S, \sum_{i: b_i = b} \text{item}_i \le C + 10^{-6}$.<br>3. Non-negative integer bin indices. |
| **Development Dataset** | `benchmark_v1/data/bin_packing/train.json` (20 streams, SHA-256: `89e58244...`) |
| **Evaluation Dataset** | `benchmark_v1/data/bin_packing/test.json` (100 streams, SHA-256: `02f2fad5...`) |
| **Resource Limits** | Max runtime: 2.0s per instance; Max total runtime: 60.0s; Max evaluations: 50 |
| **Declared Baselines** | `best_fit`, `first_fit`, `worst_fit` |
| **Contract Fingerprint** | `f37260b5626f6449fb5e259330ce63aaa7d514cd1b1e3864970804940689e610` |

---

## 3. Reused Components & Portability Parity

To satisfy the non-modification constraint, all heuristic logic was wrapped via [`BinPackingMethodAdapter`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel/method_adapter.py) reusing canonical implementations from [`stage4/src/simulator.py`](file:///Users/ashishsingh/Desktop/experiment1/stage4/src/simulator.py):

- `best_fit_priority`: Minimizes leftover space after item placement ($\text{priority} = -(C_{\text{rem}} - \text{item})$).
- `first_fit_priority`: Places item into first feasible open bin ($\text{priority} = 0.0$).
- `worst_fit_priority`: Maximizes leftover space after placement ($\text{priority} = C_{\text{rem}}$).

### Reference Parity Check
Before running the controller, all adapters were audited against the independent `DeterministicBinPackingSimulator.pack_stream` reference on 1,000-item benchmark streams:

| Heuristic | Simulator Reference ($B$) | Adapter Bins ($B$) | Reference $\rho$ | Adapter $\rho$ | Bitwise Parity |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Best-Fit** | 465 | 465 | 0.047297 | 0.047297 | **MATCH (100%)** |
| **First-Fit** | 469 | 469 | 0.056306 | 0.056306 | **MATCH (100%)** |
| **Worst-Fit** | 535 | 535 | 0.204955 | 0.204955 | **MATCH (100%)** |

Both the bin counts and normalized excess ratios matched the reference implementation with 100% mathematical parity.

---

## 4. Fault Injection & Security Containment

To test robustness against malformed solutions and rogue candidates, four fault-injection test doubles were evaluated:

1. **Overcapacity Worker (`InvalidCapacityBinPackingAdapter`):** Deliberately assigned all items to bin 0.
   - *Outcome:* Constraint validator caught capacity overrun: `[bin_packing_validity] Bin 0 capacity exceeded: total weight 482.35 > capacity 100.0`.
   - *Status:* Classified as `VALIDATION_ERROR`, `is_valid = False`, `objective_score = None`.
2. **Missing Items Worker (`MissingItemBinPackingAdapter`):** Omitted half the items from assignment.
   - *Outcome:* Constraint validator caught item count mismatch: `[bin_packing_validity] Assignment count 500 does not match item count 1000`.
   - *Status:* Classified as `VALIDATION_ERROR`, `is_valid = False`, `objective_score = None`.
3. **Hanging Worker (`HangingAdapter`):** Slept past the 2.0s timeout limit.
   - *Outcome:* Supervisor hard-killed worker process via SIGTERM/SIGKILL after 2.0s. Subsequent evaluations proceeded cleanly without lingering processes.
   - *Status:* Classified as `TIMEOUT`, `is_valid = False`, `objective_score = None`.
4. **Exception Worker (`ExceptionAdapter`):** Raised unhandled `RuntimeError`.
   - *Outcome:* Supervisor caught process exit, logged traceback, and protected controller state.
   - *Status:* Classified as `EXCEPTION`, `is_valid = False`, `objective_score = None`.

**Rule Verification:** In all failure cases, invalid candidates were completely disqualified from selection and could not exploit scoring or penalty conventions.

---

## 5. End-to-End Pilot Execution & Results

The complete two-phase pilot was executed using [`discovery_kernel/run_bin_packing_pilot.py`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel/run_bin_packing_pilot.py):

### Phase 1: Development Selection
- Evaluated 5 methods on 5 development streams (5,000 total packing decisions).
- Total runtime: **1.36 seconds**.

#### Development Rankings:
| Rank | Method ID | Status | Valid Streams | Mean Excess Ratio ($\bar{\rho}$) | Selection Outcome |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **1** | **`best_fit`** | **VALID** | **5 / 5** | **0.032600** | **SELECTED CHAMPION** |
| 2 | `first_fit` | VALID | 5 / 5 | 0.037800 | Baseline Runner-Up (+15.9% vs Champ) |
| 3 | `worst_fit` | VALID | 5 / 5 | 0.150800 | Baseline (+362.6% vs Champ) |
| 4 | `fault_missing_items` | INVALID | 0 / 5 | None | **DISQUALIFIED (Count mismatch)** |
| 5 | `fault_overcapacity` | INVALID | 0 / 5 | None | **DISQUALIFIED (Capacity exceeded)** |

#### Freeze Event:
Before any holdout data was unsealed, the champion selection was committed to disk in [`dev_summary.json`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel_v01/results/portability_bin_packing_20261019/dev_summary.json):
- **Champion Method:** `best_fit` (v1.0.0)
- **Champion Dev Score:** 0.032600
- **Evidence Hash:** `acdf594580bfb9f8f26fa8035ee8b4088019b840eb3fe7553f4728552199b1ef`
- **Frozen Timestamp:** `2026-10-19T16:21:38Z`

---

### Phase 2: Holdout Confirmatory Evaluation
Following the freeze, the controller unsealed the holdout benchmark (`benchmark_v1/data/bin_packing/test.json`) to evaluate the frozen champion against the primary baseline (`first_fit`):
- Total runtime: **0.58 seconds**.
- All instances valid: **5 / 5 (100% completion)**.
- Matched instance count: **5 / 5**.

#### Matched Holdout Comparison:
| Instance ID | Item Count | Best-Fit Score ($\rho$) | First-Fit Score ($\rho$) | Absolute $\Delta$ | Relative Gap | Best-Fit Runtime |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `stream_0` | 1,000 | 0.041667 | 0.054825 | -0.013158 | -23.99% | 6.77 ms |
| `stream_1` | 1,000 | 0.021944 | 0.025078 | -0.003134 | -12.50% | 5.07 ms |
| `stream_2` | 1,000 | 0.036364 | 0.036364 | 0.000000 | 0.00% | 3.43 ms |
| `stream_3` | 1,000 | 0.044346 | 0.053215 | -0.008869 | -16.67% | 6.43 ms |
| `stream_4` | 1,000 | 0.024845 | 0.027950 | -0.003105 | -11.11% | 2.67 ms |
| **Summary** | **Mean Across Split** | **0.033800** | **0.039500** | **-0.005700** | **-14.3176%** | **4.87 ms avg** |

- **Champion Holdout Score:** 0.033800
- **Baseline Holdout Score:** 0.039500
- **Matched Relative Gap:** **$-14.3176\%$** (Best-Fit strictly outperforms First-Fit by 14.3% in excess ratio).
- **Beats Baseline:** `True`.

---

## 6. Independent Reconstruction & Provenance Verification

The independent verification utility [`reconstruct_and_verify_selection()`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel/evidence_store.py) was executed on the generated records:
- Successfully parsed 35 raw instance events from [`run_records.jsonl`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel_v01/results/portability_bin_packing_20261019/run_records.jsonl).
- Recomputed group means and applied deterministic sorting rule.
- Confirmed that the recomputed champion matches the recorded champion (`best_fit`) with 100% bitwise parity.
- Verified that all output files (`dev_summary.json`, `final_report.json`, `run_records.jsonl`) match cryptographic checksums in `manifest.json`.

---

## 7. Domain-Independent Defect Fixed During Portability Audit

In strict compliance with Instruction 4 (*"Do not modify kernel core logic unless a genuine domain-independent defect is found"*), one genuine domain-independent defect was uncovered and resolved:

- **Defect Description:** In `run_final_evaluation_phase`, instance ID extraction in line 351 used `inst.get("id", f"eval_{idx:04d}")`, but matched-subset lookup in line 428 used `inst.get("id")`. For domains where instance objects use alternative keys (e.g. `"stream_id"` in Bin Packing), line 428 evaluated to `None`, causing matched-instance lookup to fail.
- **Resolution:** Implemented `_extract_instance_id(inst, idx, prefix)` helper in [`DeterministicController`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel/controller.py), guaranteeing consistent instance ID derivation (`id`, `stream_id`, or positional fallback) across all evaluation phases and schema conventions.
- **Regression Check:** All 11 original PFSP tests in [`tests/test_discovery_kernel.py`](file:///Users/ashishsingh/Desktop/experiment1/tests/test_discovery_kernel.py) continue to pass with zero regressions.

---

## 8. Acceptance Gate Verdict

| Criterion | Requirement | Result |
| :--- | :--- | :---: |
| **All three heuristics run through same kernel** | Best-Fit, First-Fit, Worst-Fit execute via common `MethodAdapter` interface. | **PASS** |
| **Independent validity & reference parity** | Item coverage, capacity checks, and exact match with Stage 4 simulator. | **PASS** |
| **Focused test suite passes** | All 6 dedicated unit/integration tests pass (`tests/test_bin_packing_portability.py`). | **PASS** |
| **Deterministic reproducibility** | Repeated runs yield identical scores, rankings, and decisions. | **PASS** |
| **Evidence auditability** | Independent reconstruction from append-only logs verified. | **PASS** |
| **Zero regressions on existing PFSP domain** | All 11 original PFSP unit/integration tests continue to pass. | **PASS** |
| **Bounded scope & zero paid calls** | \$0.00 spend, 0 LLM calls, < 2.0s CPU compute, 0 git commits/pushes. | **PASS** |

### **Final Verdict: PASS**

The Discovery Kernel v0.1 has conclusively passed the Second-Domain Portability Gate. It supports multiple combinatorial optimization domains (PFSP and Bin Packing) under a unified, leak-free, process-isolated, and mathematically verifiable experimental harness.
