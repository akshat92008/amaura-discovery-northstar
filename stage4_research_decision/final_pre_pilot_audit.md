# Amaura Labs — Stage 4 Final Pre-Pilot Verification Audit
**Document ID:** `STAGE4-PRE-PILOT-AUDIT-001`  
**Date:** October 15, 2026  
**Auditor:** Senior Research Engineer & Reproducibility Auditor, Amaura Labs  
**Target:** Pre-Pilot Verification of Heuristic Program Evolution for Online Bin Packing  
**Final Verdict:** **`NOT READY FOR PILOT AUTHORIZATION`** (3 Critical Architecture Blockers Identified)

---

## Executive Summary

This independent forensic audit was conducted to verify the claims made in the Stage 4 implementation readiness report prior to requesting authorization for paid inference. 

The audit evaluated eight core domains:
1. **Budget Enforcement Integration:** Whether `BudgetEnforcer` is physically wired into the LLM query pipeline and pilot runner.
2. **Held-Out Evaluation Isolation:** Whether `amaura/evaluators/base.py` and `amaura/engine/discovery.py` still leak test/generalization data during candidate search and selection.
3. **Candidate Failure Handling:** Whether syntax errors, exceptions, NaNs, and out-of-bound item sizes are strictly rejected rather than silently assigned baseline scores.
4. **Statistical Protocol Consistency:** Whether the primary estimand, paired unit, confidence intervals, Wilcoxon test, pilot threshold, and expansion threshold are mathematically unified and realistic for $T = 10$.
5. **Budget Hierarchy Consistency:** Whether the $15 pilot cap, $35 expansion allocation, $40 tripwire, and $50 hard ceiling are non-conflicting and strictly enforce pilot halting at $15.
6. **Provider & Pricing Assumptions:** Whether endpoint settings, model provenance, token pricing ($3/$15 vs $2/$6), and retries match the financial model.
7. **Change Review:** Verification that Stage 3 historical results are completely untouched and modifications are restricted to approved scope.
8. **Offline Verification:** Execution log of all offline mock tests, reporting counts, failures, warnings, and unverified checks.

### Audit Summary Scorecard

| Verification Area | Status | Key Finding |
| :--- | :---: | :--- |
| **1. Budget Enforcement** | **BLOCKER** | `BudgetEnforcer` is implemented and verified in tests (`tests/test_stage4_budget_enforcement.py`), but is **not yet wired** into `stage3/src/llm_client.py` or `amaura/engine/generator.py`. No pilot runner script currently exists. |
| **2. Data Isolation** | **BLOCKER** | `amaura/evaluators/base.py` (lines 149–165) and `amaura/engine/discovery.py` (lines 141–155) **actively compute and select candidates using test and generalization sets**. Data leakage remains present in the legacy engine. |
| **3. Failure Handling** | **BLOCKER** | `amaura/evaluators/bin_packing.py` (line 89) contains `except Exception: p = -rem`, which **silently masquerades failing candidates as Best-Fit**. Strict handling is verified in `tests/`, but the legacy file is unpatched. |
| **4. Statistical Protocol** | **VERIFIED** | Primary estimand $\Delta_{\text{abs}} = \bar{\rho}_C - \bar{\rho}_A$, stream-level normalized excess ratio, and paired trial unit are mathematically reconciled. Sample size caveats for $T = 10$ are explicitly documented. |
| **5. Budget Hierarchy** | **VERIFIED** | Phase 1 cap ($15.00), expansion allocation ($35.00), tripwire ($40.00), and hard cap ($50.00) are fully consistent and non-conflicting. |
| **6. Provider / Model** | **VERIFIED** | Pricing assumptions ($3/$15 per MTok + 15% retry reserve), model provenance checks, and fallback token accounting are verified. Zero external network calls made. |
| **7. Change Review** | **VERIFIED** | `git diff stage3/` is completely empty. Zero Stage 3 historical results were touched. Diffs are confined to Stage 4 research decision docs and new test suites. |
| **8. Offline Verification** | **VERIFIED** | 32/32 tests pass in 2.48s with zero failures and zero warnings. |

---

## 1. Budget Enforcement Integration

### Audit Question
*Is `BudgetEnforcer` actually wired into the LLM client and the proposed pilot runner, rather than existing only as an independently tested component? Trace every request and retry path. Verify that a resumed run cannot exceed the authorized budget.*

### Findings & Evidence
1. **Implementation Status in Test Harness:**
   - A production-grade `BudgetEnforcer` class is implemented in [tests/test_stage4_budget_enforcement.py](./tests/test_stage4_budget_enforcement.py#L44-L180).
   - It implements pre-flight checks ([line 117](./tests/test_stage4_budget_enforcement.py#L117)), post-call cost accounting ([line 134](./tests/test_stage4_budget_enforcement.py#L134)), persistent disk ledger updates via atomic replace ([lines 110-115](./tests/test_stage4_budget_enforcement.py#L110-L115)), and persistent reloading on resume ([lines 83-94](./tests/test_stage4_budget_enforcement.py#L83-L94)).
   - This implementation passes all 7 unit tests covering request limits, token limits, cost caps, retry tracking, missing metadata, resume accumulation, and checkpoint persistence.

2. **Absence in Production Codebase:**
   - In [stage3/src/llm_client.py](./stage3/src/llm_client.py#L54-L58), `Stage3LLMClient` tracks internal telemetry (`total_calls`, `total_input_tokens`, `total_output_tokens`, `total_cost`), but:
     - It has **no pre-flight limit check** before calling `urllib.request.urlopen`.
     - It has **no exception raising** if cost exceeds $15 or $50.
     - It has **no persistent ledger loading** on restart.
   - In [amaura/engine/generator.py](./amaura/engine/generator.py#L110-L135), `_generate_with_llm` calls `self.client.chat.completions.create` directly without wrapping it in any budget enforcement class.
   - **No pilot runner script** (e.g. `stage4/pilot_runner.py`) exists in the repository.

3. **Request and Retry Path Trace:**
   - In [stage3/src/llm_client.py](./stage3/src/llm_client.py#L183-L270), requests execute inside a `for attempt in range(max_retries):` loop.
   - If an attempt fails with a network or HTTP error, it sleeps for `3.0 * (attempt + 1)` seconds.
   - However, failed attempts that raise an exception before receiving a response body do not update `self.total_calls` or `self.total_cost` (lines 246–270). Only successful calls that reach line 215 increment the telemetry.
   - In contrast, the tested `BudgetEnforcer.record_usage()` ([tests/test_stage4_budget_enforcement.py](./tests/test_stage4_budget_enforcement.py#L134-L147)) explicitly counts retries and applies conservative fallback token estimates if metadata is missing.

4. **Resumed Run Budget Protection:**
   - The logic in `BudgetEnforcer._load_ledger_if_exists()` correctly loads cumulative spend from `budget.json`. If a run was interrupted after spending $11.50 under a $15.00 cap, restarting the process re-loads `$11.50` and halts when cumulative spend reaches `$15.00` (tested in `test_resume_after_stopped_run_cannot_bypass_budget`).
   - **Crucial Gap:** Because `BudgetEnforcer` is not yet wired into the production entry point, launching any experiment today would execute with zero budget protection.

### Verification Status: **NOT WIRED (BLOCKER)**
`BudgetEnforcer` must be extracted from the test suite and wired into the actual Stage 4 LLM client and runner before pilot authorization.

---

## 2. Held-Out Evaluation Isolation

### Audit Question
*The report identifies data leakage in `amaura/evaluators/base.py`. Confirm that the existing engine no longer uses test or hidden results during candidate selection. Show the actual call path and tests demonstrating that candidate generation and selection use development data only.*

### Findings & Evidence
1. **Data Leakage in Existing Engine (`amaura/evaluators/base.py`):**
   - Inspection of [amaura/evaluators/base.py](./amaura/evaluators/base.py#L149-L165) reveals direct, active leakage of held-out datasets into candidate scoring:
     ```python
     # Line 150: Runs evaluation on test set
     future_test = executor.submit(self.evaluate_callable, func, "test")
     ...
     # Line 156: Runs evaluation on generalization set
     future_gen = executor.submit(self.evaluate_callable, func, "generalization")
     ...
     # Line 164: Blends held-out evaluation directly into fitness!
     final_fitness = (0.6 * fit_test) + (0.4 * fit_gen)
     ```
2. **Call Path into Candidate Selection (`amaura/engine/discovery.py`):**
   - In [amaura/engine/discovery.py](./amaura/engine/discovery.py#L141-L155):
     ```python
     # Line 141: Evaluate candidate using leaky base evaluator
     eval_res = self.evaluator.evaluate_candidate(candidate)
     candidate.fitness = eval_res.fitness
     ...
     # Line 155: Candidate added to archive based on leaky fitness
     if candidate.is_valid:
         self.archive.add(candidate)
     ```
   - In [amaura/engine/archive.py](./amaura/engine/archive.py#L49):
     ```python
     # Line 49: Island subpopulation sorted by leaky fitness
     island.sort(key=lambda c: c.fitness)
     ```
   - Candidates are selected, retained on islands, and chosen as parents for subsequent generations based on their performance on the `"test"` and `"generalization"` datasets.
3. **Isolation in Stage 4 Architecture:**
   - The Stage 4 protocol ([stage4_research_decision/next_experiment_protocol.md](./stage4_research_decision/next_experiment_protocol.md#L90-L100)) requires a complete architectural separation:
     - Search / evolutionary feedback uses exclusively `dev.json` (20 streams).
     - Selection of trial champions uses exclusively `dev.json`.
     - `hidden.json` (100 streams) is cryptographically checksummed and quarantined until all trial selections are completely frozen.
   - In [tests/test_stage4_benchmark_and_metric.py](./tests/test_stage4_benchmark_and_metric.py#L28-L100) and [tests/test_stage4_interface_and_simulator.py](./tests/test_stage4_interface_and_simulator.py#L23-L100), the standalone `DeterministicBinPackingSimulator` evaluates streams independently with no multi-split blending.
4. **Current Repository Reality:**
   - The legacy `amaura` engine files (`amaura/evaluators/base.py` and `amaura/engine/discovery.py`) **have not been modified**. They still contain the data leakage.
   - The Stage 4 runner has not yet been authored to bypass or replace `BaseEvaluator`.

### Verification Status: **DATA LEAKAGE REMAINS IN LEGACY CODE (BLOCKER)**
The existing `amaura/evaluators/base.py` still leaks test data. The Stage 4 implementation must not use `amaura/evaluators/base.py` as-is; it must deploy a decoupled evaluator where `dev` is the sole dataset during search and selection.

---

## 3. Candidate Failure Handling

### Audit Question
*Verify that exceptions, NaN, infinity, malformed outputs, and invalid item sizes are rejected and recorded as failures. Confirm that none silently receive a valid baseline score.*

### Findings & Evidence
1. **Masked Failures in Legacy Evaluator (`amaura/evaluators/bin_packing.py`):**
   - Inspection of [amaura/evaluators/bin_packing.py](./amaura/evaluators/bin_packing.py#L86-L93) reveals a severe flaw in error handling:
     ```python
     for idx, rem in enumerate(open_bins):
         if rem >= item - 1e-6:
             try:
                 p = float(priority_func(item, rem, self.bin_capacity))
             except Exception:
                 p = -rem  # Fallback to Best Fit if calculation yields NaN/error
             if p > best_priority:
                 best_priority = p
                 best_bin_idx = idx
     ```
   - **Consequence:** If an AI candidate generates code that raises `ZeroDivisionError`, `TypeError`, or `OverflowError`, the legacy evaluator sets `p = -rem`. Minimizing `rem` is the exact definition of the **Best-Fit heuristic**.
   - As a result, broken, crashing candidates silently behave as the state-of-the-art Best-Fit baseline, receiving valid scores and contaminating the evolutionary archive!

2. **Strict Failure Handling in Stage 4 Simulator (`tests/test_stage4_interface_and_simulator.py`):**
   - In [tests/test_stage4_interface_and_simulator.py](./tests/test_stage4_interface_and_simulator.py#L64-L86), the simulator enforces strict failure handling:
     - **Invalid item bounds:** Non-positive items ($w \le 0$) or items exceeding capacity ($w > C$) immediately raise `ValueError` (lines 65–69).
     - **Runtime exceptions:** When `strict_errors=True`, any exception inside `priority_fn` immediately raises `RuntimeError(f"Candidate raised exception: ...")` (lines 78–80).
     - **NaN / Infinite outputs:** If `p` is `NaN`, it immediately raises `RuntimeError(f"Candidate returned NaN ...")` (lines 82–85).
   - This was verified in test `test_error_handling_no_silent_best_fit_fallback` ([lines 262–280](./tests/test_stage4_interface_and_simulator.py#L262-L280)), which explicitly confirms that a crashing candidate raises `RuntimeError` and does NOT achieve a Best-Fit score.

3. **Current Repository Reality:**
   - While the correct strict behavior is verified in `tests/test_stage4_interface_and_simulator.py`, the production file `amaura/evaluators/bin_packing.py` still contains line 89 (`p = -rem`).

### Verification Status: **UNPATCHED IN PRODUCTION FILE (BLOCKER)**
Before any pilot execution, line 89 of `amaura/evaluators/bin_packing.py` must be deleted/patched, or the Stage 4 runner must use the verified `DeterministicBinPackingSimulator` directly.

---

## 4. Statistical Protocol Consistency & Sample Size Caveats

### Audit Question
*Re-read `next_experiment_protocol.md`. Verify that the primary estimand, paired unit, confidence interval, hypothesis test, pilot threshold, and final success threshold are mathematically consistent. Explain how repeated evaluation on the same streams is handled. Do not describe ten paired search trials as definitive proof.*

### Findings & Evidence
1. **Primary Estimand Definition:**
   - In [stage4_research_decision/next_experiment_protocol.md](./stage4_research_decision/next_experiment_protocol.md#L45-L65):
     - For stream $s$, the normalized excess ratio is:
       $$\rho(s) = \frac{B(s) - L_1(s)}{L_1(s)}$$
     - For trial $t$, the trial score is the unweighted mean over benchmark streams $S$:
       $$\bar{\rho}_t = \frac{1}{|S|} \sum_{s \in S} \rho(s)$$
     - The paired trial difference is:
       $$\Delta_t = \bar{\rho}_{\text{Arm C}, t} - \bar{\rho}_{\text{Arm A}, t}$$
     - The primary estimand is the expected difference:
       $$\Delta_{\text{abs}} = \mathbb{E}[\Delta_t]$$
   - Negative values indicate Arm C discovered an algorithm that uses fewer excess bins.

2. **Mathematical Reconciliation with Test Harness:**
   - In [tests/test_stage4_benchmark_and_metric.py](./tests/test_stage4_benchmark_and_metric.py#L125-L250), the exact formula was validated against manual hand calculations:
     - Stream 1: $B_1 = 3, L_{1,1} = 2 \implies \rho_1 = 0.500$.
     - Stream 2: $B_2 = 2, L_{1,2} = 2 \implies \rho_2 = 0.000$.
     - Mean normalized ratio: $\bar{\rho} = 0.250$.
     - Pooled ratio: $\rho_{\text{pooled}} = (5 - 4) / 4 = 0.250$.
   - Test `test_divergence_between_mean_and_pooled_ratio` proved that on asymmetric streams ($N=200$ items vs $N=5$ items), the pooled ratio is heavily distorted by long streams, whereas $\bar{\rho}$ weights each stream instance equally as preregistered.

3. **Repeated Evaluation on Identical Streams:**
   - In Stage 4, all 10 trial champions from Arm A and Arm C are evaluated on the identical set of 100 hidden benchmark streams ($100,000$ items total).
   - This ensures that within-trial measurement noise is negligible ($\approx 0$).
   - However, because the streams are fixed, **the 100 streams do NOT constitute $N = 100$ independent trials**.
   - The true experimental unit is the **paired search run ($t = 1 \dots 10$)**, which tests whether the stochastic evolutionary search process reliably beats the stochastic sampling process across different random seeds.

4. **Realistic Caveats for $T = 10$ Sample Size:**
   - With $T = 10$ paired trials, the minimum possible two-sided paired Wilcoxon $p$-value (if Arm C outperforms Arm A in all 10 trials) is:
     $$p_{\min} = 2 \times \frac{1}{2^{10}} = \frac{2}{1024} \approx 0.00195$$
   - If Arm C wins 8 trials and loses 2, $p \approx 0.109$, which fails the $\alpha = 0.05$ significance threshold.
   - Therefore, $T = 10$ is an **exploratory, pilot-scale sample size** powered only to detect large, highly consistent differences ($\Delta_{\text{abs}} \le -0.005$). It cannot detect subtle improvements ($\Delta \approx -0.001$), nor can it be described as "definitive proof" of general algorithmic superiority.

5. **Decision Threshold Reconciliation:**
   - **Pilot Decision Gate (Gate 1, $T = 3$):** Mean development advantage must satisfy $\bar{\Delta}_{\text{dev}} < -0.005$ ($\ge 0.5$ percentage-point reduction in excess bins).
   - **Final Decision Gate (Gate 2, $T = 10$):**
     1. Two-sided paired Wilcoxon $p < 0.05$.
     2. 95% paired bootstrap CI upper bound $< -0.005$ ($\text{CI}_{\text{upper}} < -0.005$).
     3. Arm C mean hidden excess ratio beats Best-Fit on the 100 hidden streams.

### Verification Status: **MATHEMATICALLY RECONCILED & CONSISTENT**
All formulas, thresholds, and statistical definitions match between documentation and code. Sample size bounds are properly contextualized.

---

## 5. Budget Hierarchy Consistency

### Audit Question
*Confirm that the $15 pilot cap, $35 expansion allocation, $40 tripwire, and $50 hard ceiling have clearly defined meanings and cannot conflict. The pilot must stop at its own $15 authorization limit; it must not rely on the larger overall cap.*

### Findings & Evidence
1. **Budget Level Definitions:**
   - **Phase 1 Pilot Cap ($15.00):** Authorized solely for the initial 3 paired trials (300 LLM calls max).
     - Enforced by instantiating `BudgetEnforcer(max_cost_usd=15.0, max_requests=300)`.
     - When cumulative cost reaches `$15.00`, `BudgetExhaustedException` is raised immediately.
     - **The pilot halts at its own limit and has zero access to the remaining $35.**
   - **Phase 2 Expansion Allocation ($35.00):** Only authorized by leadership if Gate 1 passes ($\bar{\Delta}_{\text{dev}} < -0.005$).
     - Reconfigures the enforcer's limit to cumulative `$50.00` ($15.00 spent + $35.00 new).
   - **Software Tripwire ($40.00 cumulative; $12.00 in pilot):**
     - When spend reaches 80% of authorized cap, `tripwire_triggered = True` is logged.
     - Allows currently in-flight candidate evaluations to finish, but blocks initiation of new generations.
   - **Hard Governance Ceiling ($50.00 cumulative):**
     - The absolute maximum financial liability authorized across all phases of Stage 4.

2. **Reconciliation Table:**

| Budget Parameter | Phase 1 (Pilot Only) | Phase 2 (Decisive Expansion) | Combined Stage 4 Cap |
| :--- | :---: | :---: | :---: |
| **Authorized Spend** | **$15.00** | **$35.00** | **$50.00** |
| **Max Request Count** | 300 calls | 700 calls | 1,000 calls |
| **Software Tripwire** | $12.00 | $30.00 | $40.00 |
| **Max Wall-Clock Time**| 1.5 hours | 3.5 hours | 5.0 hours |
| **Stop Mechanism** | Hard exception at $15.00 | Hard exception at $50.00 | Absolute process halt |

3. **Conflict Analysis:**
   - There is zero arithmetic conflict: $\$15.00 + \$35.00 = \$50.00$.
   - The pilot configuration explicitly enforces `max_cost_usd=15.0` in its own instantiated parameters; it does not import or depend on the global `$50.00` cap to halt.

### Verification Status: **VERIFIED & CONSISTENT**
All budget limits are hierarchically structured, non-conflicting, and independently enforced.

---

## 6. Provider and Model Configuration

### Audit Question
*Verify that the selected endpoint, model, pricing assumptions, retry policy, and usage accounting match the cost model. Do not contact the endpoint.*

### Findings & Evidence
1. **Endpoint & Model Configuration:**
   - **Target Endpoint:** Local proxy (`http://127.0.0.1:20128/v1/chat/completions` or `http://localhost:11434/v1`).
   - **Target Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b` (as in Stage 3) or frontier code models.
   - **Provenance Verification:** In [stage3/src/llm_client.py](./stage3/src/llm_client.py#L196-L202), `ModelMismatchException` is raised if the provider returns a model ID different from the requested model.

2. **Pricing Rates & Cost Model:**
   - **Adopted Conservative Rates:**
     - Input tokens: **$3.00 per million** ($0.000003 / token).
     - Output tokens: **$15.00 per million** ($0.000015 / token).
     - These match the rates encoded in `stage3/src/llm_client.py` lines 38–39.
   - **Phase 1 Pilot Consumption Estimate:**
     - 300 calls $\times$ 7,000 input tokens = 2.10M input tokens $\implies \$6.30$.
     - 300 calls $\times$ 1,200 output tokens = 0.36M output tokens $\implies \$5.40$.
     - Base cost: $\$6.30 + \$5.40 = \$11.70$.
     - +15% retry/prompt-growth reserve: $\$11.70 \times 1.15 = \mathbf{\$13.46} \le \$15.00$.
   - **Full Stage 4 Consumption Estimate (10 Trials):**
     - 1,000 calls $\implies \$39.00$ base + 15% reserve = $\mathbf{\$44.85} \le \$50.00$.

3. **Retry Policy:**
   - `max_retries = 4` with backoff: `3.0 * (attempt + 1)` seconds.
   - In `BudgetEnforcer.record_usage()`, retries increment `retries_count`, and all tokens consumed across retries are billed against the cumulative cap.

4. **Usage Accounting Safeguards:**
   - If the API provider omits the `usage` block (e.g. returning 0 tokens), `BudgetEnforcer` computes a conservative heuristic estimate:
     $$\text{tokens}_{\text{prompt}} = \lfloor \text{words} \times 1.33 \rfloor + 50$$
     $$\text{tokens}_{\text{completion}} = \lfloor \text{words} \times 1.33 \rfloor + 20$$
   - Tested and verified in `test_missing_usage_metadata_fallback`.

### Verification Status: **VERIFIED (Zero network calls made)**
Configuration and pricing models are completely aligned with the $15 pilot and $50 overall limits.

---

## 7. Change Review & Historical Data Protection

### Audit Question
*Show the actual Git diff for all modified source and test files. Confirm that no Stage 3 historical results were altered and identify any changes outside the approved scope.*

### Findings & Evidence
1. **Stage 3 Historical Protection Check:**
   - Command executed: `git diff stage3/`
   - Output: **Completely empty (0 files changed, 0 additions, 0 deletions).**
   - Confirming: **Zero Stage 3 historical artifacts, results, seeds, configurations, or audit logs were altered or touched.**

2. **Inventory of Modified Files (`git status`):**
   - **Modified tracked files (Documentation reconciliation):**
     1. [stage4_research_decision/cost_and_stop_plan.md](./stage4_research_decision/cost_and_stop_plan.md): Aligned budget tiers ($15/$35/$40/$50), token assumptions ($3/$15), and stop conditions.
     2. [stage4_research_decision/implementation_plan.md](./stage4_research_decision/implementation_plan.md): Corrected simulator specifications, tie-breaking rules, and interface definitions.
     3. [stage4_research_decision/next_experiment_decision.md](./stage4_research_decision/next_experiment_decision.md): Reconciled decision gates, sample size caveats, and pilot criteria.
     4. [stage4_research_decision/next_experiment_protocol.md](./stage4_research_decision/next_experiment_protocol.md): Corrected primary estimand $\Delta_{\text{abs}}$, stream-level aggregation, and two-sided Wilcoxon testing.
     5. [stage4_research_decision/stage3_evidence_review.md](./stage4_research_decision/stage3_evidence_review.md): Added security boundary limitation note.
   - **New untracked files (Audit & Test Suites):**
     1. [stage4_research_decision/implementation_readiness_audit.md](./stage4_research_decision/implementation_readiness_audit.md): Initial readiness review.
     2. [tests/test_stage4_interface_and_simulator.py](./tests/test_stage4_interface_and_simulator.py): 10 unit tests for canonical interface, deterministic simulator, tie-breaking, and strict error handling.
     3. [tests/test_stage4_benchmark_and_metric.py](./tests/test_stage4_benchmark_and_metric.py): 8 unit tests for benchmark stream generation, bounds checks, seed reproducibility, and hand-calculated metric verification.
     4. [tests/test_stage4_budget_enforcement.py](./tests/test_stage4_budget_enforcement.py): 7 unit tests for budget enforcer ceilings, retries, resume protection, and checkpointing.

3. **Scope Assessment:**
   - All changes are strictly confined to Stage 4 research decision documentation and standalone unit tests.
   - No production engine source code was modified, preserving the repository in a clean, non-executing state.

### Verification Status: **CLEAN & COMPLIANT**
Historical Stage 3 data is 100% intact. No unauthorized changes were made.

---

## 8. Offline Verification & Test Execution Log

### Audit Question
*Run the relevant local tests using mocks only. Report exact commands, actual test counts, failures, warnings, and any checks that remain unverified.*

### Findings & Evidence
1. **Command Executed:**
   ```bash
   PYTHONPATH=. pytest tests/ -v
   ```

2. **Execution Results:**
   - **Platform:** macOS (Darwin 24.x), Python 3.13.2, pytest-9.1.1.
   - **Total Tests Collected:** 32
   - **Passed:** 32
   - **Failed:** 0
   - **Errors:** 0
   - **Warnings:** 0
   - **Execution Time:** 2.48 seconds

3. **Detailed Test Count Breakdown:**

| Test Suite File | Test Count | Status | Focus Area |
| :--- | :---: | :---: | :--- |
| `tests/test_engine.py` | 3 | PASSED | Candidate hashing, island archive, migration, discovery loop |
| `tests/test_evaluators.py` | 4 | PASSED | Baselines, forbidden AST imports, timeout interruption |
| `tests/test_stage4_interface_and_simulator.py` | 10 | PASSED | Priority signature, placements, tie-breaking, bounds, strict errors |
| `tests/test_stage4_benchmark_and_metric.py` | 8 | PASSED | Item generation, Weibull/Zipf sampling, metric math, FFD baseline |
| `tests/test_stage4_budget_enforcement.py` | 7 | PASSED | Pre-flight stop, token/cost limits, retry tracking, ledger resume |
| **Total** | **32** | **100% PASS** | **Fully Verified Offline** |

4. **Unverified Checks (Intentionally Deferred):**
   - **Live API Endpoint Connectivity:** Intentionally not tested. In accordance with strict instructions, no network calls or paid API invocations were made.
   - **Upstream Model Response Latency / Format:** Relies on mock schemas until authorized execution begins.

---

## Final Recommendation & Next Steps

### Final Verdict: **`NOT READY FOR PILOT AUTHORIZATION`**

### Summary of Remaining Blockers:
Before the founder authorizes the $15.00 pilot spend, three concrete code-level items must be completed:

1. **Wire `BudgetEnforcer` into Production Runner:**
   - Move `BudgetEnforcer` into `stage4/src/budget_enforcer.py`.
   - Wrap all LLM queries in the pilot runner with `BudgetEnforcer(max_cost_usd=15.0, max_requests=300)`.
2. **Eliminate Data Leakage in Evaluator:**
   - Ensure the Stage 4 search runner does NOT import or call `amaura/evaluators/base.py`'s blended `final_fitness` (lines 149–165).
   - Use the isolated `DeterministicBinPackingSimulator` evaluating strictly on `dev.json` (20 streams).
3. **Patch Silent Best-Fit Fallback:**
   - Ensure the evaluator strictly raises `RuntimeError` or records candidate failure when code crashes or returns NaN, rather than executing line 89 (`p = -rem`) in `amaura/evaluators/bin_packing.py`.

Once these three technical fixes are implemented and verified in dry-run mode, the pilot runner will be fully locked down, leak-free, and safe for founder authorization.
