# Amaura Labs Stage 4: Implementation-Readiness Audit & Protocol Reconciliation

**Audit Identifier:** Stage_4_Readiness_Audit_v1.0  
**Lead Auditor:** Senior Research Engineer, Experimental Statistician & Code Auditor  
**Date:** 2026-10-15  
**Audit Status:** COMPLETE — READINESS VERDICT: **NOT READY FOR LIVE INFERENCE (AWAITING FOUNDER GATE 1 AUTHORIZATION; ALL PRE-PILOT UNIT TESTS VERIFIED)**  
**Directory:** `stage4_research_decision/`  

---

## 1. Executive Summary & Readiness Verdict

This forensic audit evaluates the technical readiness of Amaura Labs' Discovery Engine for the proposed Stage 4 experiment (Program-Space Heuristic Evolution for Online 1D Bin Packing).

### Formal Readiness Verdict:
```
════════════════════════════════════════════════════════════════════════════════════
   READINESS VERDICT: CODE INFRASTRUCTURE & PROTOCOLS ARE AUDITED AND VERIFIED;
   LIVE INFERENCE IS STRICTLY BLOCKED AWAITING FOUNDER AUTHORIZATION (GATE 1)
════════════════════════════════════════════════════════════════════════════════════
```

1. **Pre-Pilot Verification Status:** **PASSED (32/32 unit tests passing).** The canonical function interface, deterministic simulator, bounds enforcement, discrete metric aggregation, and hard budget enforcer have been implemented in isolated local test modules and pass with 100% success.
2. **Experimental Execution Status:** **STRICTLY PROHIBITED.** In compliance with founder instructions, zero live LLM queries, zero paid API calls, and zero benchmark evaluations have been launched.
3. **NEET Preparation Constraint:** The protocol is engineered to be fully self-terminating, budget-capped ($\le \$50.00$), and bounded to a 3-trial pilot gate requiring zero continuous founder supervision.

---

## 2. Repository State & Trace Call Paths

We audited the physical repository to distinguish working implementations from prior assumptions:

| File / Component | Repository Location | Verified Reality vs. Documentation Claims |
| :--- | :--- | :--- |
| **Bin Packing Evaluator** | `amaura/evaluators/bin_packing.py` | **Claim:** Standard FunSearch benchmark.<br>**Verified Reality:** Uses canonical signature `priority(item, remaining_capacity, bin_capacity)`. **Critical defect found:** Line 89 contains `except Exception: p = -rem  # Fallback to Best Fit`. Crashed candidates were silently credited as Best-Fit! |
| **Base Evaluator Protocol** | `amaura/evaluators/base.py` | **Claim:** 4-layer evaluation protocol.<br>**Verified Reality:** Lines 149–165 evaluate `train`, `test`, and `generalization` in a single pass to compute `fitness = 0.6*test + 0.4*gen`. This causes severe held-out data leakage during search. |
| **Evolutionary Archive** | `amaura/engine/archive.py` | **Verified Reality:** Fully functional multi-island population archive with migration and Pareto tracking. |
| **Program Generator** | `amaura/engine/generator.py` | **Verified Reality:** Contains LLM query handlers and autonomous AST mutators. Prompts require updating to enforce the canonical signature. |
| **Stage 3 LLM Client** | `stage3/src/llm_client.py` | **Claim:** Strict budget and cost tracking.<br>**Verified Reality:** Client logs tokens and costs, but **completely lacks hard execution ceilings**. Can issue unbounded requests if a loop does not stop. Requires `BudgetEnforcer` wrapper. |
| **Stage 3 Sandbox** | `stage3/src/sandbox.py` | **Claim:** "Strict Security Sandbox".<br>**Verified Reality:** Static AST whitelist and safe builtins. **Lacks OS-level process, filesystem, and network isolation.** |
| **Stage 3 State Machine** | `stage3/src/state_machine.py` | **Verified Reality:** Valid state transitions and in-memory firewall check (`raise PermissionError` on hidden access during `MAIN_RUNNING`). |

---

## 3. Discrepancies Identified & Resolved

### 3.1 Interface Incompatibility
- **The Discrepancy:** The initial Stage 4 proposal proposed `priority(item, capacity, current_fill)`, whereas `amaura/evaluators/bin_packing.py`, `amaura/engine/generator.py`, and `experiment4` universally implemented `priority(item, remaining_capacity, bin_capacity)`.
- **Resolution:** We standardized universally on the existing canonical signature:
  `def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float`
- **Verification:** Unit test suite `tests/test_stage4_interface_and_simulator.py` verifies all argument mappings, feasible capacity decrements, exact fits, and deterministic tie-breaking (10/10 passed).

### 3.2 Simulator Silent Fallback Elimination
- **The Discrepancy:** `amaura/evaluators/bin_packing.py` silently masked candidate exceptions by assigning `p = -rem` (Best-Fit fallback).
- **Resolution:** Strict error handling enforced. Any candidate raising an exception or returning NaN is marked `INVALID` and discarded.

### 3.3 Metric Formulation & Discrete Lattice Nature
- **The Discrepancy:** Prior drafts referred to the normalized excess ratio as "continuous and noise-free."
- **Resolution:** Acknowledged that bin counts $B(s)$ are discrete integers and $L_1(s)$ is an integer. Thus, $\rho(s) = (B(s) - L_1(s))/L_1(s)$ is a discrete rational metric. Defined both:
  - Stream-level mean: $\bar{\rho} = \frac{1}{M} \sum \rho(s)$ (Primary Estimand).
  - Pooled ratio: $\rho_{\text{pooled}} = \frac{\sum B - \sum L_1}{\sum L_1}$ (Secondary Diagnostic).
- **Verification:** Hand-calculated examples verified in `tests/test_stage4_benchmark_and_metric.py` (8/8 passed).

### 3.4 Conflation of Absolute vs. Relative Effect Sizes
- **The Discrepancy:** Prior drafts stated $\mathcal{H}_1: \mathbb{E}[\Delta] < -0.015$ and interchangeably called it a "1.5% improvement."
- **Resolution:** Formally decoupled the primary estimand (absolute difference $\Delta_{\text{abs}} = \rho_C - \rho_A < -0.005$, representing a 0.5 percentage-point drop in excess bins) from the secondary metric (relative percentage reduction $\ge 10.0\%$).

### 3.5 Budget Modeling & Financial Cap Reconciliation
- **The Discrepancy:** The initial proposal quoted $2.00 / $6.00 rates ($21.20 full) but claimed $45.00 total cost without explanation.
- **Resolution:** Reconciled against Stage 3 code rates ($3.00 / $15.00) plus a 15% retry contingency. Established:
  - Phase 1 Pilot Cap: **$15.00 USD**
  - Phase 2 Expansion Cap: **$35.00 USD**
  - Automatic Software Tripwire: **$40.00 USD**
  - Hard Governance Budget Ceiling: **$50.00 USD**
- **Verification:** Built and verified `BudgetEnforcer` in `tests/test_stage4_budget_enforcement.py` (7/7 passed).

---

## 4. Tests Actually Executed & Verified

All unit tests were run locally, completely offline, with zero external network or paid API calls:

```
Command Executed: pytest tests/
Test Results: 32 passed in 3.90 seconds (100% success rate)
Platform: macOS, Python 3.13.2, pytest-9.1.1
```

### Test Suite Breakdown:
1. `tests/test_stage4_interface_and_simulator.py` (10 tests, PASSED):
   - `test_canonical_signature_arguments`
   - `test_feasible_placement_and_capacity_update`
   - `test_no_feasible_placement_opens_new_bin`
   - `test_exact_fit_reaches_zero_remaining`
   - `test_empty_stream`
   - `test_deterministic_tie_breaking_first_found`
   - `test_tie_breaking_multiple_open_bins`
   - `test_best_fit_vs_worst_fit`
   - `test_invalid_item_bounds`
   - `test_error_handling_no_silent_best_fit_fallback`
2. `tests/test_stage4_benchmark_and_metric.py` (8 tests, PASSED):
   - `test_generator_bounds_enforcement` (Uniform, Weibull $k=0.8$, Zipf)
   - `test_generator_deterministic_reproducibility`
   - `test_hand_calculated_metric_stream_1`
   - `test_hand_calculated_metric_stream_2`
   - `test_hand_calculated_aggregation`
   - `test_divergence_between_mean_and_pooled_ratio`
   - `test_empty_stream_metric`
   - `test_offline_baseline_ffd_reference`
3. `tests/test_stage4_budget_enforcement.py` (7 tests, PASSED):
   - `test_request_limit_exhaustion`
   - `test_token_limit_exhaustion`
   - `test_cost_limit_exhaustion`
   - `test_retry_accounting`
   - `test_missing_usage_metadata_fallback`
   - `test_resume_after_stopped_run_cannot_bypass_budget`
   - `test_checkpoint_recovery`
4. Historical Stage 1 tests (`tests/test_engine.py`, `tests/test_evaluators.py`, 7 tests, PASSED).

---

## 5. Security & Sandbox Audit

| Layer | Implemented Reality | Protection Level | Stage 4 Status |
| :--- | :--- | :---: | :---: |
| **AST Inspection** | Whitelist of allowed nodes; forbids `open`, `exec`, `eval`, `__import__`, dunder names. | Moderate | **Adequate for pure math priority functions.** |
| **Process Isolation** | Thread-pool execution within the main Python interpreter. | **None** | Acceptable only with strict AST validator. |
| **Filesystem Isolation** | None (blocked only by AST check preventing `open`). | Low | Relying on AST check; no OS jail. |
| **Network Isolation** | None (blocked only by AST check preventing `socket`/`urllib`). | Low | Relying on AST check. |
| **Held-Out Benchmark Firewall** | Software state machine raises `PermissionError` during `MAIN_RUNNING`. | Moderate | Must decouple search evaluation from hidden evaluation. |

**Stage 4 Sandboxing Protocol:**
Because candidate programs for bin packing are pure mathematical scoring functions, we mandate an even stricter AST whitelist:
- **Zero imports permitted** (even `import math` is disallowed in candidate code; pure math functions `exp`, `log`, `sqrt` are injected directly into globals).
- **Zero dunder identifiers.**
- **Zero I/O calls.**

---

## 6. Outstanding Blockers & Governance Prerequisites

Before experimental execution can be authorized, the following prerequisites must be fulfilled:

1. **Founder Gate 1 Authorization:**
   - The founder must explicitly authorize the 3-trial Pilot Study spend (capped at **$15.00 USD**).
2. **Provider-Side Hard Billing Cap Configuration:**
   - The founder must confirm that a hard spend limit of **$50.00 USD** is configured in the cloud provider's account console (OpenAI / OpenRouter).
3. **Model Endpoint Configuration:**
   - Confirm whether the experiment will query an external API (e.g. `gpt-4o-mini`) or a local self-hosted endpoint (as in Stage 3: `nemotron-3-super-120b`).

---

## 7. Founder Decision Required

The founder is requested to make **one specific decision**:

> **Do you approve the Stage 4 protocol and authorize the implementation of the pilot runner script (Gate 1), capped at a maximum of $15.00 USD across 3 development trials?**

*(No further code execution or experimental runs will occur until this decision is rendered.)*
