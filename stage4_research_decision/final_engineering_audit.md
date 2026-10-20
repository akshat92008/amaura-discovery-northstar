# Amaura Labs — Stage 4 Final Engineering & Architectural Audit
**Document ID:** `STAGE4-ENG-AUDIT-FINAL-001`  
**Date:** October 15, 2026  
**Auditor:** Lead Research Engineer, Amaura Labs Discovery Engine  
**Target:** Engineering Completion, Data Isolation, and Budget Enforcer Integration  
**Final Status:** **`ENGINEERING VERIFIED & READY FOR FOUNDER AUTHORIZATION`**

---

## 1. Audit Context & Scope

Following the initial pre-pilot audit, three critical blockers prevented Stage 4 from being authorized:
1. **Unwired Budget Enforcer:** `BudgetEnforcer` existed only as a test component and was not wired into the LLM query pipeline.
2. **Held-Out Data Leakage:** The legacy engine (`amaura/evaluators/base.py` and `amaura/engine/discovery.py`) blended `"test"` and `"generalization"` splits into candidate fitness during active search.
3. **Silent Best-Fit Fallback:** `amaura/evaluators/bin_packing.py` line 89 caught all exceptions and assigned `p = -rem`, allowing crashing candidates to masquerade as the state-of-the-art Best-Fit baseline.

This final audit independently inspects the newly constructed Stage 4 architecture (`stage4/`), verifies the resolution of these blockers, and documents the offline test evidence.

---

## 2. Forensic Resolution of Critical Blockers

### A. Real Budget Enforcement Integration
- **Implementation:** [`stage4/src/budget_enforcer.py`](./stage4/src/budget_enforcer.py) and [`stage4/src/client.py`](./stage4/src/client.py).
- **Physical Wiring:** 
  - Every model query in [`stage4/src/client.py:97`](./stage4/src/client.py#L97) calls `self.enforcer.check_preflight_limits()` *before* opening any network socket or issuing HTTP requests.
  - In retry loops ([`stage4/src/client.py:155`](./stage4/src/client.py#L155)), pre-flight checks execute before each retry attempt.
  - Failed or timed-out requests ([`stage4/src/client.py:209-224`](./stage4/src/client.py#L209-L224)) conservatively charge the ledger using fallback token estimates, guaranteeing no "free" unaccounted calls.
- **Ledger Persistence & Resumption:**
  - Ledgers are atomically persisted to disk via tempfile replacement ([`stage4/src/budget_enforcer.py:116-121`](./stage4/src/budget_enforcer.py#L116-L121)).
  - On restart, [`_load_ledger_if_exists()`](./stage4/src/budget_enforcer.py#L68-L82) reloads cumulative spend, preventing a restarted run from bypassing budget caps.
- **Thread Safety:** All ledger mutations and limit checks are guarded by re-entrant locks (`threading.RLock()`), preventing race conditions during concurrent execution.
- **Telemetry Distinction:** Tracks `actual_reported_cost_usd` versus `estimated_cost_usd` separately.

### B. Strict Held-Out Evaluation Isolation
- **Elimination of Leaky Base Evaluator:** Stage 4 completely bypasses `amaura/evaluators/base.py`.
- **Architectural Separation:**
  - Search Phase ([`stage4/src/runner.py:202-230`](./stage4/src/runner.py#L202-L230)): The search runner validates preconditions and loads **ONLY** `dev.json` (20 streams, 1,000 items each).
  - The hidden benchmark file (`hidden.json`) is not opened or present in memory during search.
  - In [`tests/test_stage4_isolation.py:30-55`](./tests/test_stage4_isolation.py#L30-L55), a test physically deletes `hidden.json` from the filesystem; the search phase completes identically, proving zero runtime dependency on hidden data.
  - Candidate Selection Freeze: Arm A and Arm C trial champions are selected strictly by development excess ratio $\bar{\rho}_{\text{dev}}$. Selections are frozen and recorded in an atomic checkpoint.
  - Unsealing Phase ([`stage4/src/runner.py:233-241`](./stage4/src/runner.py#L233-L241)): `hidden.json` is loaded *only after* candidate selections are frozen. Hidden performance is purely observational and never feeds back into search.
- **Cryptographic Sealing:** Benchmark files are cryptographically locked using SHA-256 hashes recorded in [`stage4/benchmarks/manifest.json`](./stage4/benchmarks/manifest.json):
  - `dev.json` SHA-256: `89e58244eed5272533f206c352bf285e267bc2481c2c1983bec9b7dd7024d74e`
  - `hidden.json` SHA-256: `02f2fad53dbf9862c1d8d3d4883c5f4df9d535eaf3d2b1e4901eb9f6ab22af09`

### C. Correct Candidate Failure Handling
- **Production Evaluator Patch:** In [`amaura/evaluators/bin_packing.py:86-93`](./amaura/evaluators/bin_packing.py#L86-L93), line 89 (`except Exception: p = -rem`) was removed and replaced with explicit exception raising:
  ```python
  try:
      p = float(priority_func(item, rem, self.bin_capacity))
  except Exception as e:
      raise RuntimeError(f"Candidate raised exception on item={item}, rem={rem}: {e}") from e
  if math.isnan(p) or math.isinf(p):
      raise RuntimeError(f"Candidate returned non-finite priority {p} on item={item}, rem={rem}")
  ```
- **Stage 4 Evaluator:** [`stage4/src/evaluator.py`](./stage4/src/evaluator.py) implements complete sandbox validation:
  - Rejects syntax errors, invalid signatures (not 3 arguments), and forbidden module imports (`os`, `sys`, `subprocess`, `socket`, `urllib`).
  - Catches infinite loops via `concurrent.futures` timeout (default 2.0s per instance).
  - All errors return `is_valid=False`, `fitness=float("inf")`.
- **Archive Protection:** In [`stage4/src/archive.py:65-74`](./stage4/src/archive.py#L65-L74), invalid candidates are completely barred from entry into island archives or elite pools. Failure reasons and counts are tracked separately in telemetry.

---

## 3. Dedicated Stage 4 Runner Verification

The dedicated runner is implemented in [`stage4/src/runner.py`](./stage4/src/runner.py).

### Key Features Verified:
1. **Deterministic Bin Packing Simulator:** Enforces canonical `priority(item, remaining_capacity, bin_capacity)` with First-Found tie-breaking and exact $L_1$ lower bounds.
2. **Paired Search Execution:** Executes Arm A (50 independent samples) vs Arm C (50 evolutionary steps across 3 islands) on identical paired seeds ($40400 + t$).
3. **Statistical Analysis Engine:** Computes paired differences $\Delta_t = \bar{\rho}_{\text{Arm C}, t} - \bar{\rho}_{\text{Arm A}, t}$, two-sided Wilcoxon signed-rank test $p$-values, and 10,000 paired bootstrap 95% confidence intervals.
4. **Baseline Standards:** Benchmarks against Best-Fit, Worst-Fit, First-Fit, and offline First-Fit Decreasing (FFD).
5. **Fail-Closed Startup:** Validates presence and SHA-256 integrity of benchmark manifest before initiating any trial.

---

## 4. Offline Test Suite Execution Evidence

All 47 unit and integration tests across the repository were executed offline using Python 3.13.2 and pytest 9.1.1:

```bash
PYTHONPATH=. pytest tests/ -v
```

### Execution Log & Test Count Summary:

| Test File | Tests | Passed | Failed | Focus Area |
| :--- | :---: | :---: | :---: | :--- |
| `tests/test_engine.py` | 3 | 3 | 0 | Legacy engine hashing, island archive, discovery loop |
| `tests/test_evaluators.py` | 4 | 4 | 0 | Baseline evaluation, AST anti-reward hacking, sandbox timeouts |
| `tests/test_stage4_benchmark_and_metric.py` | 8 | 8 | 0 | Bounds enforcement, seed reproducibility, hand-calculated metrics |
| `tests/test_stage4_budget_enforcement.py` | 7 | 7 | 0 | Preflight limits, token/cost caps, retries, ledger resume accumulation |
| `tests/test_stage4_interface_and_simulator.py` | 10 | 10 | 0 | Canonical signature, tie-breaking, exact fit, classical baselines |
| `tests/test_stage4_failure_modes.py` | 8 | 8 | 0 | Zero-division, NaN, Inf, forbidden imports, syntax errors, timeouts |
| `tests/test_stage4_isolation.py` | 3 | 3 | 0 | Quarantined hidden data, dev-only ranking, zero split-bleeding |
| `tests/test_stage4_runner.py` | 4 | 4 | 0 | End-to-end mock campaign, real-path budget stop, fail-closed hashes |
| **Total Test Suite** | **47** | **47** | **0** | **100% Pass Rate (25.83s execution)** |

---

## 5. Preservation of Historical Artifacts

A full Git status and diff check confirms:
- **`git diff stage3/` is completely empty.**
- Zero historical Stage 3 files, results, seeds, configurations, or audit logs were modified or deleted.
- All modifications are strictly confined to:
  1. Fixing line 89 in `amaura/evaluators/bin_packing.py`.
  2. Research decision documents in `stage4_research_decision/`.
  3. The new `stage4/` architecture package.
  4. Unit test suites in `tests/`.

---

## 6. Audit Conclusion & Engineering Verdict

The engineering blockers have been completely resolved. The Stage 4 architecture is robust, deterministic, cryptographically sealed, and bounded by physical budget enforcement.

**Verdict:** **`READY FOR FOUNDER REVIEW AND PILOT AUTHORIZATION`**
