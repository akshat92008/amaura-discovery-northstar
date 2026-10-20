# AMAURA LABS — NORTH BLUESTAR DISCOVERY KERNEL V0.1
## Integration Pilot Report & Acceptance Gate Audit

**Experiment ID:** `EXP_PILOT_DK01_20261019`  
**Date:** October 19, 2026  
**Execution Environment:** macOS Darwin / Python 3.13.2  
**Test Suite Status:** 11 passed in 3.46s  
**Results Directory:** [`discovery_kernel_v01/results/pilot_20261019/`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel_v01/results/pilot_20261019/)  

---

## 1. Pilot Mission & Configuration

The objective of this pilot was to execute an end-to-end integration test of the **Discovery Kernel v0.1** on an existing, verified combinatorial optimization domain (**Permutation Flow Shop Scheduling — PFSP**).

The pilot was explicitly designed as an **infrastructure test**, not as proof of algorithmic novelty. It tested problem contract verification, multi-method adapter execution, fault injection handling, development-phase selection, immutable freeze gating, holdout isolation, and automated evidence reconstruction.

### Experimental Parameters

| Parameter | Configuration Value |
| :--- | :--- |
| **Domain Identifier** | `pfsp_flowshop_scheduling` |
| **Objective Metric** | Schedule Makespan $C_{\max}$ (Direction: `MINIMIZE`) |
| **Problem Specification Fingerprint** | `571bb3d854d0dd81e05a21c12a087eaffc0a2bff4e2418ef31224779ae25db32` |
| **Development Dataset** | `benchmark_v1/data/pfsp/train.json` (SHA-256: `558d5eaf61...`) |
| **Evaluation Dataset** | `benchmark_v1/data/pfsp/test.json` (SHA-256: `2f45067640...`) |
| **Development Cohort** | 5 instances ($n \in \{20, 50, 75, 100\}$, $m=10$) |
| **Holdout Cohort** | 5 instances ($n \in \{20, 50, 100\}$, $m \in \{5, 10, 20\}$) |
| **Per-Instance Timeout** | 1.50 seconds (enforced via OS process termination) |
| **Total Evaluation Budget** | 50 evaluations |

### Evaluated Methods (3 Real Algorithms + 2 Fault Doubles)

1. `neh_ls_insertion`: NEH constructive heuristic + single-pass insertion local search.
2. `neh_classical`: Classical Nawaz-Enscore-Ham (1983) constructive baseline.
3. `spt_ascending`: Naive Shortest Processing Time heuristic.
4. `fault_invalid_permutation`: Test double producing duplicate job indices.
5. `fault_hanging_worker`: Test double sleeping 10.0s past timeout.

---

## 2. Phase 1 (Development) Execution & Selection

The controller evaluated all 5 declared methods across the 5 development instances in isolated OS processes:

```
[PHASE 1] Running development phase...
[PHASE 1] Completed in 10.09s.
          Champion Selected: neh_ls_insertion (Dev Score: 3700.40)
          Frozen At:         2026-10-19T16:08:00Z
```

### Development Rankings

| Rank | Method ID | Status | Valid Runs | Mean Makespan | Timeout Count | Exception Count | Selection Decision |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | **`neh_ls_insertion`** | **VALID** | **5 / 5** | **3700.40** | **0** | **0** | **SELECTED CHAMPION** |
| 2 | `neh_classical` | VALID | 5 / 5 | 3738.80 | 0 | 0 | Baseline Runner-Up (+1.04% vs Champ) |
| 3 | `spt_ascending` | VALID | 5 / 5 | 4470.20 | 0 | 0 | Eliminated (+20.80% vs Champ) |
| 4 | `fault_hanging_worker` | INVALID | 0 / 5 | None | 5 | 0 | **DISQUALIFIED (Terminated by SIGTERM/SIGKILL)** |
| 5 | `fault_invalid_permutation` | INVALID | 0 / 5 | None | 0 | 0 | **DISQUALIFIED (Constraint Violations)** |

### Fault Containment Verification
- **Timeout Worker:** Worker PID was hard-terminated after 1.50s on all 5 instances. No runaway processes or hanging threads remained. Subsequent runs proceeded without interference.
- **Invalid Output Worker:** Produced malformed permutations with duplicate job indices. Decoupled `ConstraintRule` flagged `[permutation_validity]` failures, assigned `is_valid = False`, and denied an objective score.

### Immutable Selection Freeze
Before holdout data was unsealed, the selection was committed to disk in [`dev_summary.json`](file:///Users/ashishsingh/Desktop/experiment1/discovery_kernel_v01/results/pilot_20261019/dev_summary.json) and frozen into `FrozenSelection`:
- **Champion:** `neh_ls_insertion` (v1.0.0)
- **Dev Score:** 3700.40
- **Evidence Hash:** `ac13ae5bafe4e3cb48bfefea1621689255ec0c5a2c42385b0d0be0be4f395ee5`
- **Frozen Timestamp:** `2026-10-19T16:08:00Z`

---

## 3. Phase 2 (Holdout Confirmatory) Evaluation

Following the freeze, the controller unsealed the holdout benchmark (`benchmark_v1/data/pfsp/test.json`) to evaluate the frozen champion and the reference baseline (`neh_classical`):

```
[PHASE 2] Unsealing holdout benchmark for frozen selection...
[PHASE 2] Completed in 3.07s.
          Champion Holdout Score: 3474.60
          Baseline Holdout Score: 3495.00
          Relative Gap:           -0.5837%
          Beats Baseline:         True
```

### Per-Instance Matched Evaluation Results

| Instance ID | Problem Size ($n \times m$) | Champion Score (`neh_ls_insertion`) | Baseline Score (`neh_classical`) | Absolute $\Delta$ | Relative Gap | Champion Runtime |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `pfsp_0000` | $20 \times 10$ | 1,119.0 | 1,119.0 | 0.0 | 0.00% | 3.83 ms |
| `pfsp_0001` | $50 \times 10$ | 2,857.0 | 2,871.0 | -14.0 | -0.49% | 45.50 ms |
| `pfsp_0002` | $100 \times 10$ | 6,096.0 | 6,165.0 | -69.0 | -1.12% | 953.38 ms |
| `pfsp_0003` | $20 \times 20$ | 1,047.0 | 1,051.0 | -4.0 | -0.38% | 3.65 ms |
| `pfsp_0004` | $100 \times 5$ | 6,254.0 | 6,269.0 | -15.0 | -0.24% | 943.94 ms |
| **Summary** | **Mean Across Split** | **3,474.60** | **3,495.00** | **-20.40** | **-0.5837%** | **389.8 ms avg** |

- **All Instances Valid:** 5 / 5 (100% completion).
- **Matched Instance Count:** 5 / 5.
- **Overall Relative Gap:** **$-0.5837\%$** (lower makespan, beats baseline).

---

## 4. Independent Audit & Reconstruction

Following execution, the independent verification utility `reconstruct_and_verify_selection()` was invoked against the output directory:

```
[AUDIT] Reconstructing experiment from raw records...
          Reconstruction Verified: True
          Recorded Champion:       neh_ls_insertion
          Recomputed Champion:     neh_ls_insertion
          Generated Files:         ['dev_summary.json', 'final_report.json', 'run_records.jsonl']
```

The verification independently parsed all 35 records from `run_records.jsonl`, recomputed the group means, applied the deterministic sorting rule, and confirmed:
1. Recomputed champion matches recorded champion with 100% bitwise parity.
2. No holdout evaluations occurred prior to the freeze timestamp.
3. Cryptographic manifest `manifest.json` correctly digests all output files.

---

## 5. Acceptance Gate Evaluation

| Gate | Requirement | Verification Evidence | Status |
| :--- | :--- | :--- | :---: |
| **Gate A — Reuse** | Reuse existing reliable infrastructure rather than duplicating. | Built directly on `benchmark_v1` PFSP baselines and `stage4` sandboxing/quarantine patterns. Zero duplicate domain implementations. | **PASS** |
| **Gate B — Correctness** | Focused unit & integration tests pass, covering holdout isolation and worker termination. | `pytest tests/test_discovery_kernel.py`: **11 / 11 tests passed in 3.46s**, covering spec validation, fault injection, budget limits, and holdout gates. | **PASS** |
| **Gate C — Reproducibility** | Repeating deterministic pilot yields identical validity, scores, and decisions. Runtime excluded from equality. | Deterministic tie-breaking by `method_id` verified across repeated trials (`test_repeated_runs_reproduce_scores_and_decisions` passed). | **PASS** |
| **Gate D — Auditability** | Independent developer can reconstruct selection decision from saved records. | Raw event log (`run_records.jsonl`) contains complete provenance; `reconstruct_and_verify_selection()` confirmed bitwise parity. | **PASS** |
| **Gate E — Bounded Scope** | Zero paid calls, zero large compute jobs, no unrequested commits/pushes, no unrelated refactors. | Total API spend: **\$0.00**. Paid calls: **0**. Total compute: **< 15 seconds CPU**. Git commits: **0**. Git pushes: **0**. | **PASS** |

---

## 6. Conclusion

The integration pilot satisfies all five acceptance gates with zero deviations. The Discovery Kernel v0.1 is verified operational, mathematically sound, and leak-free.
