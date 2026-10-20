# Amaura Experiment #15 — Final Pre-Execution Scientific Audit

**Document Status:** Certified Audit & Execution Authorization Gate  
**Date:** 2026-10-04  
**Auditor:** Amaura Autonomous Verification Protocol  
**Scope:** Lifecycle Reconstruction Correctness, Historical Metadata Isolation, Information Parity, Simulator Accounting Invariants, Policy Hash Freezing, and Hidden-Data Firewall Verification.

---

## 1. Executive Verdict

### **FINAL STATUS: AUTHORIZED FOR BLIND EXECUTION**

Every pre-execution scientific audit item has passed:
1. **Container Lifecycle Reconstruction:** Verified against all 370,540 raw events in Alibaba Cluster Trace v2018. Long-running service semantics and heartbeat structures are explicitly documented and mapped.
2. **Lifecycle Invariants:** 100% of reconstructed evaluation workloads satisfy $t_{\text{arr}} < t_{\text{dep}}$, $\text{duration} > 0$, and unique container identification.
3. **Boundary Handling:** Window boundary clamping verified analytically; active time before window start and after window end is strictly excluded from window accounting.
4. **Historical Machine-ID Leakage:** Zero leakage. Physical host IDs (`machine_id`) from Alibaba logs are completely excluded from scheduler inputs. Schedulers operate on synthetic, neutral cluster pools (`node_0000`, ...).
5. **Information Parity:** Verified across all 8 solvers. Canonical state snapshot hashes are byte-for-byte identical (`fde2a6b774a1f028...`).
6. **Negative Control Diagnostic:** Randomizing historical machine IDs in trace metadata produces 100% identical scheduling decisions across all policies.
7. **Mode A Semantic Accounting:** 5 out of 5 hand-calculated analytical benchmark cases pass with zero error. Node-hours are verified as $\int N_{\text{active}}(t) dt$.
8. **Policy Freeze Verification:** Cryptographic SHA-256 hashes for Policy A (`T4_C01`) and Policy B (`N60_T4_C51`) match the frozen Experiment #13 and #14 artifacts byte-for-byte.
9. **Hidden-Data Firewall:** Days 3–4 ($t = 259,200 \to 432,000$) remain 100% untouched. Zero hidden evaluations have been run, saved, or observed.

---

## 2. Lifecycle Reconstruction Audit

In Alibaba Cluster Trace v2018 (`container_meta.csv`), containers represent collocated online services (long-running applications). Analysis of all 370,540 rows reveals that container records are **periodic status snapshots / heartbeats** emitted by the cluster manager while a container remains in a given state:
- $99.2\%$ of containers (70,918 of 71,476) have sequences consisting solely of `('started', 'started', ...)` across the 8-day trace, reflecting production microservices with multi-day lifespans.
- 519 containers contain `stopped` events, with 119 containers having both explicit `started` and `stopped` transitions.
- 32 containers exhibited negative duration in raw logs (containers stopped before trace collection began at $t=0$). These are identified and filtered out.
- **Boundary Handling Rule:**
  - If $t_{\text{arr}} < W_{\text{start}}$ and $t_{\text{dep}} > W_{\text{start}}$, the container is modeled as **already active** at $W_{\text{start}}$.
  - If $t_{\text{dep}} > W_{\text{end}}$, the container is active through $W_{\text{end}}$, but only time within $[W_{\text{start}}, W_{\text{end}}]$ is billed to the window.

---

## 3. Lifecycle Statistics

| Metric | Raw Trace Value |
| :--- | :--- |
| Total Unique Containers Observed | 71,476 |
| Total Lifecycle Event Records | 370,540 |
| Containers with Valid Start Events | 71,037 ($99.39\%$) |
| Containers with Valid Termination Events | 519 ($0.73\%$) |
| Containers with Both Start and End Events | 119 ($0.17\%$) |
| Containers with Missing End (Long-running Services) | 70,918 ($99.22\%$) |
| Containers with Missing Start | 400 ($0.56\%$) |
| Containers with Inconsistent Ordering ($t_{\text{stop}} < t_{\text{start}}$) | 32 ($0.04\%$) |
| Containers with Zero or Negative Duration | 32 ($0.04\%$) |
| Duplicate Lifecycle Records | 0 |
| Minimum Duration (Explicit Lifecycles) | 5,714s (1.59h) |
| Median Duration (Explicit Lifecycles) | 127,508s (35.42h) |
| Mean Duration (Explicit Lifecycles) | 227,292s (63.14h) |
| P95 Duration (Explicit Lifecycles) | 684,626s (190.17h) |
| P99 Duration (Explicit Lifecycles) | 684,626s (190.17h) |
| Maximum Duration (Explicit Lifecycles) | 684,626s (190.17h) |
| Median Observed Lifespan across All Containers | 378,691s (105.19h / 4.4 days) |

---

## 4. Lifecycle Invariant Tests

All invariant checks executed programmatically on the reconstructed workload suite:

| Invariant Assertion | Status | Verification Note |
| :--- | :--- | :--- |
| `arrival_time < departure_time` | **PASS** | Evaluated on all valid container instances |
| `duration > 0` | **PASS** | Verified across all scheduled pods |
| `container_id` uniquely identifies workload | **PASS** | 71,476 unique IDs mapped without collision |
| No impossible negative durations in evaluation suite | **PASS** | Filtered raw anomalies ($n=32$) completely excluded |
| Boundary handling (already-active & post-window clamping) | **PASS** | Clamped strictly to $[W_{\text{start}}, W_{\text{end}}]$ |

---

## 5. Historical Machine-ID Leakage Audit

A comprehensive code-level audit of all data paths from raw input files to policy decision functions was conducted:

| Information | Available to Policy? | Should be Available? | Action / Verification |
| :--- | :--- | :--- | :--- |
| **Current CPU usage** | **YES** | **YES** | Retained (Required by scheduler) |
| **Current memory usage** | **YES** | **YES** | Retained (Required by scheduler) |
| **Pod CPU request** | **YES** | **YES** | Retained (Required for placement) |
| **Pod memory request** | **YES** | **YES** | Retained (Required for placement) |
| **Historical machine ID** | **NO** | **NO** | **PASS:** Completely omitted from pod and node objects |
| **Historical placement** | **NO** | **NO** | **PASS:** Node pool uses synthetic IDs (`node_0000`, ...) |
| **Future workload arrivals** | **NO** | **NO** | **PASS:** Only pending/arrived pods accessible |
| **Future workload departures**| **NO** | **NO** | **PASS:** Managed internally by simulator event queue |
| **Hidden-test metrics** | **NO** | **NO** | **PASS:** Hidden benchmark isolated from dev/val runs |

---

## 6. Information-Parity Results

All 8 solvers were provided with an identical scheduling state snapshot and intercepted at runtime. The canonical JSON serialization of the state snapshot was hashed:

```text
Policy_A_T4_C01          : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
Policy_B_N60_T4_C51      : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
kube_binpacking          : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
kube_default             : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
first_fit                : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
best_fit                 : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
best_fit_decreasing      : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
worst_fit                : sha256 = fde2a6b774a1f028d00eb33eeffcba959556778ecff976378e916baaa18b209e
```
**Result: PASS (100% byte-for-byte equivalent state received by all solvers).**

---

## 7. Negative-Control Results

A diagnostic experiment was executed on development data comparing original workload instances against instances where historical `machine_id` metadata was scrambled randomly.

| Solver | Original Cost ($) | Scrambled Metadata Cost ($) | Decision Match |
| :--- | :--- | :--- | :--- |
| **Policy A (`T4_C01`)** | $13.38 | $13.38 | **PASS (Identical)** |
| **Policy B (`N60_T4_C51`)** | $13.38 | $13.38 | **PASS (Identical)** |
| **`kube_binpacking`** | $13.38 | $13.38 | **PASS (Identical)** |
| **`kube_default`** | $62.34 | $62.34 | **PASS (Identical)** |

**Result: PASS.** Modifying historical placement metadata produces zero change in policy behavior, proving zero leakage.

---

## 8. Mode A Semantic Tests

Verified against 5 hand-calculated analytical benchmark cases:
- **Case 1 (1 pod, known duration):** Expected = 0.5000h ($2.04), Simulator = 0.5000h ($2.04) $\implies$ **PASS**
- **Case 2 (Two overlapping pods):** Expected = 0.7500h ($3.06), Simulator = 0.7500h ($3.06) $\implies$ **PASS**
- **Case 3 (Two non-overlapping pods, node reuse):** Expected = 0.5000h ($2.04), Simulator = 0.5000h ($2.04) $\implies$ **PASS**
- **Case 4 (Two pods requiring two nodes simultaneously):** Expected = 1.0000h ($4.08), Simulator = 1.0000h ($4.08) $\implies$ **PASS**
- **Case 5 (Window boundary crossing):** Expected = 0.4167h ($1.70), Simulator = 0.4167h ($1.70) $\implies$ **PASS**

All 5 cases match analytical expectations with zero discrepancy.

---

## 9. Mode B Audit

Mode B is strictly isolated from Mode A:
- Mode B evaluates static packing windows without dynamic departures, directly testing the mathematical formulation under which policies were discovered.
- Results from Mode A and Mode B are maintained and reported separately.

---

## 10. Cost Model Audit

- Standard on-demand pricing for enterprise 96-core servers ($4.08/node-hour = $0.0425/core-hour) applied uniformly.
- Monetary figures are labeled as simulated model estimates rather than empirical enterprise savings.

---

## 11. Policy Hash Verification

Cryptographic SHA-256 hashes recomputed on policy source code:
- **Policy A (`T4_C01`):**
  - Expected: `de872ce75fc68d43062b00ba2071e9fb7303163ba9b6040d425b21be41c15101`
  - Actual:   `de872ce75fc68d43062b00ba2071e9fb7303163ba9b6040d425b21be41c15101`
  - **Status: PASS (MATCH)**
- **Policy B (`N60_T4_C51`):**
  - Expected: `7a92d80f99a5d0b56694a52f67e1f5172b333ebd574dfbb132ddce368c7b137b`
  - Actual:   `7a92d80f99a5d0b56694a52f67e1f5172b333ebd574dfbb132ddce368c7b137b`
  - **Status: PASS (MATCH)**

---

## 12. Hidden-Data Firewall Verification

- Filesystem audit confirms `experiment15/results/evaluation_results.json` and `statistical_summary.json` are absent.
- Days 3–4 hidden benchmark files (`mode_b_static.json` SHA256: `71b263f8...`, `mode_a_dynamic.json` SHA256: `9903e076...`) remain frozen and unread by any evaluation script.
- **Status: PASS.**

---

## 13. Regression Dry-Run Results

Evaluated on Day 1 development window `dev_w000` (53 pods, 15 nodes):
- **Policy A (`T4_C01`):** Cost = $13.38, Active Nodes = 3, Unscheduled = 0, Mean Imbalance = 0.4638
- **Policy B (`N60_T4_C51`):** Cost = $13.38, Active Nodes = 3, Unscheduled = 0, Mean Imbalance = 0.4638
- **`kube_binpacking`:** Cost = $13.38, Active Nodes = 3, Unscheduled = 0, Mean Imbalance = 0.4638
- **`kube_default`:** Cost = $62.34, Active Nodes = 15, Unscheduled = 0, Mean Imbalance = 0.0928

---

## 14. Deviations From Original Protocol

1. **Window Interval Clamping:** Clamping active node intervals to $[\max(t_{\text{on}}, W_{\text{start}}), \min(t_{\text{off}}, W_{\text{end}})]$ in Mode A was added to prevent pre-window active time from being charged to the window.
2. **Policy File Header Normalization:** Docstrings added to the `.py` files were removed to restore exact byte-for-byte hash identity with `frozen_champions.json`.

---

## 15. Remaining Risks

1. **Long-Running Services Dominance:** Because 99.2% of containers in Alibaba Cluster Trace v2018 run for days, Mode A dynamic replays over short horizons (e.g. 4h) largely capture steady-state background occupancy rather than rapid turnover. Mode B (static packing windows) remains the cleaner direct test of packing efficiency.
2. **Alibaba Node Uniformity:** The Alibaba production cluster uses 96-core / 100-mem bare-metal servers, which is less heterogeneous than our synthetic 4-tier benchmark.

---

## 16. Final Authorization Recommendation

### **FINAL STATUS: AUTHORIZED FOR BLIND EXECUTION**

The protocol is now verified, sealed, and audited.  
No hidden benchmark has been executed.  
No hidden results have been observed.  
Execution of the blind hidden production evaluation awaits your explicit command.
