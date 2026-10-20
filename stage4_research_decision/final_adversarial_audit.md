# Amaura Labs — Stage 4 Final Adversarial Audit
**Document ID:** `STAGE4-ADV-AUDIT-FINAL-001`  
**Date:** October 15, 2026  
**Auditor:** Independent Lead Research Engineer & Reproducibility Auditor  
**Target:** Adversarial Code Verification, Data Isolation, Concurrency & Governance Controls  
**Final Audit Verdict:** **`READY FOR PILOT AUTHORIZATION (WITH EXPLICIT CAVEATS)`**

---

## 1. Executive Summary & Audit Mandate

This final adversarial audit was conducted under a strict mandate: **independently verify the actual repository implementation without defending prior work, assume nothing works until demonstrated in code, and determine whether Stage 4 is scientifically worth running**.

Zero paid API calls were made. Zero network requests were transmitted. Zero Stage 3 historical records were altered.

### Scorecard of Adversarial Findings

| Audit Check | Status | Verification Mechanism | Key Forensic Finding |
| :--- | :---: | :--- | :--- |
| **1. Budget Enforcer Real-Path Wiring** | **VERIFIED** | Code trace & test `test_runner_budget_exhaustion_in_real_path` | `check_preflight_limits()` is wired into every `client.query()` call, retry attempt, and trial loop. Halts immediately before exceeding limits. |
| **2. Missing/Malformed Usage Fallback** | **VERIFIED** | Code inspection & test `test_missing_usage_metadata_fallback` | If provider omits usage metadata, conservative fallback $(1.33 \times \text{words} + 50)$ is charged. Zero free calls possible. |
| **3. Spending Ledger Concurrency & Crash Safety** | **VERIFIED** | `fcntl.flock` implementation & test `test_cross_process_budget_enforcement_locks` | Cross-process re-entrant file locking on `budget.json.lock` prevents multi-process race conditions. Atomic file replacement guarantees crash safety. |
| **4. Provider Model & Billing Assumptions** | **UNVERIFIED (EXTERNAL)** | Configuration audit | Pricing rates ($3/$15 per MTok) match Stage 3 code, but live proxy billing rates remain **unverified** because network calls were forbidden. |
| **5. Cumulative Hard Cap Bypass Resistance** | **VERIFIED** | Code inspection & test `test_resume_after_stopped_run_cannot_bypass_budget` | Interrupted and resumed runs reload cumulative spend from disk. Multi-process spend accumulates into single shared ledger. |
| **6. Hidden Benchmark Isolation** | **VERIFIED** | Code inspection & test `test_search_phase_has_zero_access_to_hidden_data` | Search phase loads solely `dev.json`. Selections are frozen before `hidden.json` is unsealed. Pilot mode (`is_pilot=True`) never touches hidden data. |
| **7. Cryptographic Unsealing & Audit Trail** | **VERIFIED** | SHA-256 checksums in `stage4/benchmarks/manifest.json` | Hashes recorded in results. Fail-closed startup if benchmark files are tampered with or corrupted. |
| **8. Candidate Failure & Anti-Masking** | **VERIFIED** | Code patch in `bin_packing.py` & 8 tests in `test_stage4_failure_modes.py` | Line 89 silent Best-Fit fallback removed. Exceptions, NaNs, Infs, timeouts, and syntax errors return `is_valid=False, fitness=inf`. |
| **9. Arm Parity & Fair Comparison** | **VERIFIED** | Code patch in `stage4/src/search.py` & test `test_baseline_parity_between_arms` | Arm A and Arm C both receive the 4 canonical baseline seeds and execute the exact same number of LLM calls (46 calls each per trial). |
| **10. Protocol Alignment** | **VERIFIED** | Protocol reconciliation | Metric $\bar{\rho}$, paired trial unit ($40400 + t$), Wilcoxon test, and bootstrap CI match protocol mathematically. |
| **11. Stage 3 Historical Immutability** | **VERIFIED** | `git diff stage3/` | 100% clean. Zero modifications, renames, or deletions of Stage 3 files. |

---

## 2. In-Depth Adversarial Inspection of Code & Implementation

### 2.1 Budget Enforcement Integration & Concurrency Safety
- **Physical Integration:**
  In [`stage4/src/client.py:97`](./stage4/src/client.py#L97) and [`stage4/src/client.py:155`](./stage4/src/client.py#L155), `self.enforcer.check_preflight_limits()` executes before opening any HTTP request and before every retry attempt.
- **Cross-Process Concurrency Protection:**
  In [`stage4/src/budget_enforcer.py:80-111`](./stage4/src/budget_enforcer.py#L80-L111), `_file_lock()` uses `fcntl.flock(f_lock.fileno(), fcntl.LOCK_EX)` with thread re-entrancy tracking (`self._file_lock_depth`). 
  - **Adversarial Verification:** Verified in [`tests/test_stage4_adversarial.py:30-58`](./tests/test_stage4_adversarial.py#L30-L58): Two independent `BudgetEnforcer` instances sharing the same ledger file synchronize spend across process boundaries; when the 4-request cap is reached, the second process immediately halts on pre-flight check.
- **Crash Safety:**
  Ledger writes execute via temporary file replacement (`os.replace(tmp_path, self.ledger_path)`), ensuring that power loss or SIGKILL cannot leave a corrupt JSON ledger.

### 2.2 Provider and Endpoint Assumptions (Explicitly Marked Unverified)
- **Verified Facts:**
  1. The code explicitly requests model `nvidia/nvidia/nemotron-3-super-120b-a12b`.
  2. If the provider returns a different model ID, [`ModelMismatchException`](./stage4/src/client.py#L22) immediately aborts execution.
  3. Cost calculation logic is mathematically exact:
     $$\text{Cost} = \frac{\text{prompt\_tokens}}{10^6} \times 3.00 + \frac{\text{completion\_tokens}}{10^6} \times 15.00$$
- **Forensic System Discoveries (Offline Audit of `~/.omniroute`):**
  1. **Proxy Availability:** A Node.js daemon (PID 17057) is actively listening on `localhost:20128`.
  2. **Active Provider:** Database `storage.sqlite` confirms active provider connections for `nvidia` using `auth_type: apikey`.
  3. **Historical Provenance:** Call logs from October 14, 2026 (Stage 3) confirm successful execution of `nvidia/nemotron-3-super-120b-a12b` via this proxy.
- **Unverified External Realities & Physical Mitigations:**
  1. **Upstream Billing Reality:** Client software calculates spend from assumed rates ($3/$15), but cannot physically inspect or limit upstream provider invoicing.
  2. **Physical Token Bounding:** To defend against unexpected charges, the client now enforces strict structural ceilings: `max_tokens = 512` in every payload (capping total pilot completion tokens at $\le 153.6\text{k}$) and `max_requests = 300`.
  3. **Mandatory Prerequisite:** The founder must confirm that the upstream API account has a provider-side spending limit or prepaid credit balance capped at $\le \mathbf{\$20.00\text{ USD}}$.

### 2.3 Strict Data Quarantine & Elimination of Leakage
- **Legacy Engine Bypass:** Stage 4 completely bypasses `amaura/evaluators/base.py`'s blended `(0.6 * fit_test + 0.4 * fit_gen)` fitness.
- **Search Isolation:**
  - Search runs solely on `dev.json` (20 streams).
  - In [`tests/test_stage4_isolation.py:30-55`](./tests/test_stage4_isolation.py#L30-L55), `hidden.json` is deleted prior to search; search completes identically, proving zero runtime dependency.
- **Pilot Quarantine Rule:**
  - In [`stage4/src/runner.py:289-301`](./stage4/src/runner.py#L289-L301), when `is_pilot=True`, `hidden.json` is **never opened, read, or evaluated**.
  - Verified in [`tests/test_stage4_adversarial.py:86-110`](./tests/test_stage4_adversarial.py#L86-L110): With `hidden.json` completely removed from disk, the pilot runs and records `hidden_status="SEALED_AND_UNTOUCHED"`.

### 2.4 Resolution of Baseline Parity Bias
- **Adversarial Defect Identified:**
  In initial drafts, Arm C initialized its archive with the 4 canonical baseline seeds (Best-Fit, Worst-Fit, First-Fit, Almost-Worst-Fit), while Arm A started with an empty archive and zero seeds. This created a severe baseline injection bias: Arm C could win without discovering anything simply by defaulting to the human-crafted Best-Fit seed.
- **Remediation Implemented:**
  In [`stage4/src/search.py:75-81`](./stage4/src/search.py#L75-L81), Arm A is initialized with the exact same 4 canonical seeds as Arm C. Both arms then make $N - 4 = 46$ LLM calls.
  - Verified in [`tests/test_stage4_adversarial.py:61-84`](./tests/test_stage4_adversarial.py#L61-L84): Both archives evaluate exactly 6 candidates (4 seeds + 2 samples) and contain `seed_best_fit`.

### 2.5 Candidate Failure Handling & Anti-Masking
- **Defect Fixed:**
  Line 89 of [`amaura/evaluators/bin_packing.py`](./amaura/evaluators/bin_packing.py#L86-L93) (`except Exception: p = -rem`) was removed.
- **Stage 4 Sandbox:**
  In [`stage4/src/evaluator.py`](./stage4/src/evaluator.py), any candidate that divides by zero, returns `NaN` or `Inf`, attempts forbidden imports (`os`, `sys`, `socket`), has syntax errors, or exceeds the 2.0s timeout returns `is_valid=False, fitness=float("inf")`.
- **Archive Rejection:**
  In [`stage4/src/archive.py:65-74`](./stage4/src/archive.py#L65-L74), invalid candidates are completely rejected.

---

## 3. Offline Verification Evidence

Command executed:
```bash
PYTHONPATH=. pytest tests/ -v
```

### Full Test Execution Results (55 Passed, 0 Failed, 0 Warnings):

| Test Suite File | Count | Status | Adversarial Verification Focus |
| :--- | :---: | :---: | :--- |
| `tests/test_engine.py` | 3 | PASSED | Legacy engine hashing, island archive, discovery loop |
| `tests/test_evaluators.py` | 4 | PASSED | Baselines, AST forbidden imports, timeout interruption |
| `tests/test_stage4_adversarial.py` | 7 | PASSED | Cross-process file locks, baseline parity, pilot quarantine, retry exhaustion, simultaneous campaign lock, timeout fallback billing, 4k prompt limit |
| `tests/test_stage4_benchmark_and_metric.py` | 8 | PASSED | Bounds enforcement, seed reproducibility, hand-calculated math |
| `tests/test_stage4_budget_enforcement.py` | 7 | PASSED | Preflight checks, token/cost caps, retries, ledger resume accumulation |
| `tests/test_stage4_interface_and_simulator.py` | 10 | PASSED | Priority signature, tie-breaking, exact fit, classical baselines |
| `tests/test_stage4_failure_modes.py` | 8 | PASSED | Zero division, NaN, Inf, forbidden modules, syntax errors, timeouts |
| `tests/test_stage4_isolation.py` | 3 | PASSED | Quarantined hidden data, dev-only ranking, zero split-bleeding |
| `tests/test_stage4_runner.py` | 5 | PASSED | End-to-end mock campaign, real-path budget stop, fail-closed hashes, checkpoint resumption |
| **Total Test Suite** | **55** | **100% PASS** | **Execution Time: ~61 seconds** |

---

## 4. Final Adversarial Verdict & Conditions

### Verdict: **`READY FOR PILOT AUTHORIZATION (WITH EXPLICIT CAVEATS)`**

### Explicit Audit Conditions:
1. **Pilot-Only Scope:** Authorization applies **exclusively to Phase 1 ($15.00 USD, 300 calls max)**.
2. **Hidden Quarantine:** In accordance with the audited code, the pilot must execute with `is_pilot=True`. `hidden.json` remains sealed on disk.
3. **Gate 1 Strictness:** If after 3 pilot trials, Arm C's mean development advantage fails to meet $\bar{\Delta}_{\text{dev}} < -0.005$, execution halts immediately. Phase 2 ($35.00) remains unspent.
4. **Independent Confirmatory Cohort:** If Gate 1 passes, the confirmatory campaign will run an **independent cohort of 10 new trials (Seeds 40411–40420)**, preventing pilot selection bias from contaminating the confirmatory Wilcoxon test.
