# Amaura Experiment #16 — Pre-Execution Scientific Audit

**Document Status:** Certified Audit & Formal Execution Authorization Gate  
**Date:** 2026-10-04  
**Auditor:** Amaura Autonomous Verification Protocol  
**Scope:** Dynamic Evaluator Accounting, Benchmark Cryptographic Verification, Baseline Freezing, Prompt Anti-Leakage Compliance, and Hidden Data Isolation.

---

## 1. Executive Summary & Verdict

### **STATUS: PRE-REGISTRATION & AUDIT COMPLETE — READY FOR EXECUTION APPROVAL**

Every item in the pre-execution scientific audit has passed:
1. **Dynamic Evaluator Semantics (Mode A):** 5/5 hand-calculated analytical benchmark unit tests passed with zero error. Exact continuous node-hours integration $\int N_{\text{active}}(t) dt$ verified with window boundary clamping.
2. **Benchmark Cryptographic Integrity:** All 6 benchmark data files across Dev, Val, and Hidden splits match the frozen cryptographic manifest byte-for-byte.
3. **Baseline Code Freezing:** All 8 baselines (`kube_binpacking`, `kube_default`, `first_fit`, `best_fit`, `best_fit_decreasing`, `worst_fit`, `Policy_A_T4_C01`, `Policy_B_N60_T4_C51`) have been verified and cryptographically locked.
4. **Zero-Leakage Prompt Audit:** All 60 candidate generation perspectives across 10 theoretical categories passed automated anti-leakage audits with 0 detected violations. Zero mention of `MostAllocated`, zero mention of `T4_C01`, zero mention of the 2.5% gap, and zero mention of Alibaba production traces.
5. **Information Parity & Neutral Namespaces:** Schedulers operate on synthetic, neutral cluster pools (`node_0000`, ...). Zero physical host IDs or historical metadata are exposed to candidate policies.
6. **Hidden Data Firewall:** Days 3–4 hidden partition ($t = 259,200 \to 432,000$) remains 100% untouched. Results, candidate outputs, and frozen champion directories are confirmed clean.

---

## 2. Benchmark Cryptographic Manifest Verification

All benchmark datasets have been verified against `experiment16/benchmarks/manifest.json`:

| Partition / Mode | Instances / Traces | Expected SHA-256 | Actual SHA-256 | Status |
| :--- | :--- | :--- | :--- | :--- |
| `dev/mode_a_dynamic.json` | 2 traces | `a27458997cf8e8d95fd6803475249fc5f29872c0710da93b55d662a568790aed` | `a27458997cf8e8d95fd6803475249fc5f29872c0710da93b55d662a568790aed` | **PASS** |
| `dev/mode_b_static.json` | 20 windows | `eb1c82179fd725b797444ca89913143469a4b19faebbff93d10e7cf401d14c14` | `eb1c82179fd725b797444ca89913143469a4b19faebbff93d10e7cf401d14c14` | **PASS** |
| `val/mode_a_dynamic.json` | 2 traces | `b4aedf0503ec73973b17383507dec96720ae900c8401a20559900720d898c7f6` | `b4aedf0503ec73973b17383507dec96720ae900c8401a20559900720d898c7f6` | **PASS** |
| `val/mode_b_static.json` | 20 windows | `a39b3beecc28d0dc2958c8cac04a45b0287f1ee6388434f8f6c0c2fb7d9fbf38` | `a39b3beecc28d0dc2958c8cac04a45b0287f1ee6388434f8f6c0c2fb7d9fbf38` | **PASS** |
| `hidden/mode_a_dynamic.json` | 10 traces | `9903e076c62d1aacc5e3c3437ed82030e46fbea0bdaebe78e9f2efef6ba2f4f7` | `9903e076c62d1aacc5e3c3437ed82030e46fbea0bdaebe78e9f2efef6ba2f4f7` | **PASS** |
| `hidden/mode_b_static.json` | 55 windows | `71b263f8e6bea8e94601d9eea954576b798adafd4104edf93a6b9fbad6969ffd` | `71b263f8e6bea8e94601d9eea954576b798adafd4104edf93a6b9fbad6969ffd` | **PASS** |

---

## 3. Baseline Freezing & Hash Verification

Cryptographic SHA-256 hashes verified on baseline source implementations:

- **`experiment16/baselines/baselines.py`:**  
  `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` (**MATCH**)
- **`experiment16/policies/policy_a_t4_c01.py`:**  
  `de872ce75fc68d43062b00ba2071e9fb7303163ba9b6040d425b21be41c15101` (**MATCH**)
- **`experiment16/policies/policy_b_n60_t4_c51.py`:**  
  `7a92d80f99a5d0b56694a52f67e1f5172b333ebd574dfbb132ddce368c7b137b` (**MATCH**)
- **`experiment16/src/simulator.py`:**  
  `e58e27314c84ac0c9e7ac25bde26c431f4d4d84eaff77dd4b541f518e5bfb9fc` (**MATCH**)

---

## 4. Analytical Mode A Dynamic Accounting Unit Tests

Executed against 5 hand-calculated analytical ground-truth test cases:

- **Test Case 1 (Single pod, single node, 0.5 hours):**  
  Expected = 0.5000h ($2.04), Simulator = 0.5000h ($2.04) $\implies$ **PASS**
- **Test Case 2 (Two overlapping pods, single node: 0 to 1800s, 900 to 2700s):**  
  Expected = 0.7500h ($3.06), Simulator = 0.7500h ($3.06) $\implies$ **PASS**
- **Test Case 3 (Two non-overlapping pods with node deactivation & reactivation):**  
  Expected = 0.5000h ($2.04), Simulator = 0.5000h ($2.04) $\implies$ **PASS**
- **Test Case 4 (Two pods requiring two distinct nodes simultaneously):**  
  Expected = 1.0000h ($4.08), Simulator = 1.0000h ($4.08) $\implies$ **PASS**
- **Test Case 5 (Window boundary clamping at $t_{\text{end}} = 1500\text{s}$):**  
  Expected = 0.4167h ($1.70), Simulator = 0.4167h ($1.70) $\implies$ **PASS**

**Result: 5/5 PASSED with zero discrepancy.**

---

## 5. Candidate Generation Anti-Leakage Audit

The prompt library (`experiment16/src/prompts.py`) defines 60 distinct perspectives across 10 theoretical categories:
- Active-Node Preference & Hysteresis (6 perspectives)
- Composite & Lexicographic Hybrid Strategies (6 perspectives)
- Dynamic Consolidation & Bin Packing (6 perspectives)
- Multi-Resource Balance & Skew Minimization (6 perspectives)
- Node Drainability & Evacuation Velocity (6 perspectives)
- Online Algorithms & Competitive Analysis (6 perspectives)
- Queueing Theory & Workload Flow (6 perspectives)
- Temporal Locality & Lifecycle Heuristics (6 perspectives)
- Utilization Thresholds & Safe Saturation (6 perspectives)
- Workload Churn & Departure Dynamics (6 perspectives)

### Automated Anti-Leakage Audit Results:
- Prohibited Term `MostAllocated`: **0 occurrences found (PASS)**
- Prohibited Term `T4_C01`: **0 occurrences found (PASS)**
- Prohibited Term `2.5%`: **0 occurrences found (PASS)**
- Prohibited Term `Alibaba`: **0 occurrences found (PASS)**
- Prohibited Term `Days 3-4`: **0 occurrences found (PASS)**
- Prohibited Term `hidden_dyn`: **0 occurrences found (PASS)**

---

## 6. Information Parity & Namespace Isolation

- Schedulers receive neutral synthetic node identifiers (`node_0000`, `node_0001`, ...).
- Historical Alibaba machine IDs are completely absent from the runtime data models.
- All candidate solvers and baselines receive identical state snapshot representations (`allocated_cpu`, `allocated_mem`, `remaining_cpu`, `remaining_mem`, `active_node_ids`, `placed_pods_count`, `sim_time`).

---

## 7. Hidden-Data Firewall Verification

- Filesystem audit confirms `experiment16/results/` is empty (0 files).
- `experiment16/candidates/` is empty (0 files).
- `experiment16/frozen/` is empty (0 files).
- Days 3–4 hidden benchmark files (`mode_a_dynamic.json` SHA256: `9903e076...`, `mode_b_static.json` SHA256: `71b263f8...`) remain frozen and unread by any evaluation script.
- **Firewall Status: SECURE.**

---

## 8. Summary Audit Checklist

| Item # | Verification Criteria | Status | Notes |
| :--- | :--- | :--- | :--- |
| 1 | Continuous node-hour integration $\int N(t)dt$ | **PASS** | Validated via 5 analytical test cases |
| 2 | Window boundary clamping $[W_{\text{start}}, W_{\text{end}}]$ | **PASS** | Clamping strictly enforced |
| 3 | Feasibility penalty ($1000/pod) | **PASS** | Hard constraint preserved |
| 4 | Uniform hardware cost model ($4.08/hr) | **PASS** | 96-core enterprise pricing |
| 5 | Benchmark manifest cryptographic check | **PASS** | 6/6 SHA-256 match |
| 6 | Baselines source code freeze | **PASS** | 8/8 SHA-256 match |
| 7 | Zero historical machine ID leakage | **PASS** | Neutral `node_xxxx` naming |
| 8 | Candidate prompt library size = 60 | **PASS** | Exactly 60 perspectives |
| 9 | Candidate prompt anti-leakage audit | **PASS** | Zero prohibited terms |
| 10 | Independent Best-of-N search architecture | **PASS** | Pure Best-of-N, no QD/evolution |
| 11 | Fixed search budget ($N=60 \times 5 = 300$) | **PASS** | Pre-registered in `config.json` |
| 12 | LLM model endpoint availability | **PASS** | Nemotron-3 120B responsive (<110ms) |
| 13 | AST sandbox and disallowed imports | **PASS** | Pure standard library enforced |
| 14 | Scale-aware timeout with SIGALRM | **PASS** | Base 2000ms + per-nm scaling |
| 15 | Static preservation tracking (Mode B) | **PASS** | Mode B enabled during evaluation |
| 16 | Hidden partition firewall isolation | **PASS** | 0 hidden reads, empty results dir |

---

## 9. Final Pre-Execution Recommendation

The pre-registration protocol and pre-execution scientific audit for **Amaura Experiment #16** are **100% complete, verified, and certified**.

Execution is currently on hold per protocol instructions. Upon user authorization, candidate generation (5 trials $\times$ 60 candidates = 300 calls) will begin immediately.
