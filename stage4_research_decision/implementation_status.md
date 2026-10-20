# Amaura Labs — Stage 4 Implementation Status & Technical Inventory
**Document ID:** `STAGE4-STATUS-002`  
**Date:** October 15, 2026  
**Status:** **ENGINEERING IMPLEMENTATION 100% COMPLETE & ADVERSARIALLY VERIFIED**  

---

## 1. Physical Component Inventory

The Stage 4 architecture has been cleanly implemented in [`stage4/`](./stage4/), completely decoupled from legacy Stage 3 files:

```
stage4/
├── __init__.py
├── benchmarks/
│   ├── dev.json               (20 streams, seeds 40001–40020, 1,000 items each)
│   ├── hidden.json            (100 streams, seeds 41001–41100, 1,000 items each)
│   └── manifest.json          (Cryptographic SHA-256 manifest)
└── src/
    ├── __init__.py
    ├── archive.py             (Stage4IslandArchive, Stage4Candidate)
    ├── benchmark.py           (BenchmarkStreamGenerator, SHA-256 generators)
    ├── budget_enforcer.py     (BudgetEnforcer with cross-process fcntl.flock)
    ├── client.py              (Stage4LLMClient, ModelMismatchException)
    ├── evaluator.py           (Stage4Evaluator, AST checks, sandboxed runner)
    ├── runner.py              (Stage4Runner with is_pilot quarantine & Wilcoxon)
    ├── search.py              (run_arm_a_search & run_arm_c_search with seed parity)
    └── simulator.py           (DeterministicBinPackingSimulator, baselines)
```

### Component Details

| Module | Lines | Core Classes / Functions | Primary Responsibility |
| :--- | :---: | :--- | :--- |
| [`budget_enforcer.py`](./stage4/src/budget_enforcer.py) | 275 | `BudgetEnforcer`, `BudgetExhaustedException` | Pre-flight limit checks, atomic disk ledger updates, cross-process `fcntl.flock` re-entrant locking, retry and fallback token accounting. |
| [`client.py`](./stage4/src/client.py) | 278 | `Stage4LLMClient`, `ModelMismatchException` | Wraps all queries with budget enforcer, charges billable usage on JSON decoding errors, model mismatches, and malformed choices, injects seed into payload, enforces `max_tokens=512`. |
| [`simulator.py`](./stage4/src/simulator.py) | 185 | `DeterministicBinPackingSimulator`, baselines | Canonical `priority` interface, First-Found tie-breaking, exact $L_1$ lower bounds, Best-Fit/Worst-Fit/First-Fit/FFD baselines. |
| [`benchmark.py`](./stage4/src/benchmark.py) | 160 | `BenchmarkStreamGenerator`, `generate_and_save_benchmarks` | Uniform/Weibull/Zipf stream generation, item bounds ($5 \le w \le 95$), SHA-256 checksum generation and verification. |
| [`evaluator.py`](./stage4/src/evaluator.py) | 195 | `Stage4Evaluator`, `Stage4EvaluationResult` | Decoupled evaluation on passed dataset, AST whitelist of top-level statements (rejects loops/calls), true OS process isolation with `RLIMIT_CPU` and hard SIGKILL termination. |
| [`archive.py`](./stage4/src/archive.py) | 170 | `Stage4IslandArchive`, `Stage4Candidate` | 3-island subpopulation archive, elite pool, strictly dev-fitness sorted, deterministic RNG tournament selection, complete rejection of invalid candidates. |
| [`search.py`](./stage4/src/search.py) | 230 | `run_arm_a_search`, `run_arm_c_search` | Budget- and baseline-equalized search engines (Arm A independent sampling vs Arm C evolutionary refinement) evaluating strictly on `dev.json` with step-seed derivation. |
| [`runner.py`](./stage4/src/runner.py) | 430 | `Stage4Runner`, `_save_checkpoint`, `_load_checkpoint`, `compute_wilcoxon_signed_rank` | Orchestrates paired trials, default `is_pilot=True`, enforces `phase_two_authorized=True`, verifies Gate 1 and pre-flight `hidden.json` SHA-256 hash, captures rich system execution metadata. |

---

## 2. Legacy Engine Patches

In [`amaura/evaluators/bin_packing.py:86-93`](./amaura/evaluators/bin_packing.py#L86-L93):
- **Problem Fixed:** Line 89 previously contained `except Exception: p = -rem`, allowing crashing candidates to masquerade as Best-Fit.
- **Resolution:** Replaced with explicit `raise RuntimeError` on exceptions and non-finite outputs (`NaN`, `Inf`). Verified that all existing evaluator tests pass without regressions.

---

## 3. Comprehensive Test Coverage (79 Tests Passing)

All tests execute offline using Python 3.13.2 and pytest 9.1.1:

```bash
PYTHONPATH=. pytest tests/ -v
```
**Results:** **`79 passed in 70.02s (100% pass rate)`**

### Coverage by Functional Domain (79 Tests):
1. **Engine & Archive Mechanics (7 tests):** `tests/test_engine.py`, `tests/test_evaluators.py`.
2. **Benchmark Generation & Hand-Calculated Math (8 tests):** `tests/test_stage4_benchmark_and_metric.py`.
3. **Hard Budget Enforcement & Ledger Persistence (7 tests):** `tests/test_stage4_budget_enforcement.py`.
4. **Simulator Interface, Tie-Breaking & Baselines (10 tests):** `tests/test_stage4_interface_and_simulator.py`.
5. **Candidate Failure Handling & Anti-Masking (8 tests):** `tests/test_stage4_failure_modes.py`.
6. **Data Isolation & Quarantine (3 tests):** `tests/test_stage4_isolation.py`.
7. **End-to-End Runner Execution, Checkpointing & Fail-Closed Logic (5 tests):** `tests/test_stage4_runner.py`.
8. **Adversarial Edge-Cases & Security (7 tests):** `tests/test_stage4_adversarial.py` (cross-process file locking, baseline parity, pilot quarantine, retry exhaustion, simultaneous campaign locking, conservative timeout billing, 4,000 prompt token limit).
9. **Targeted Blocker Hardening (11 tests):** `tests/test_stage4_targeted_blockers.py` (billable usage on model mismatch & malformed JSON, OS process isolation & SIGKILL on infinite loops, top-level AST loop/call rejection, safe pilot default, Phase 2 authorization gating, Gate 1 verification, pre-flight hidden hash validation, trial seed & metadata logging).
10. **Pre-Flight Hardening & Statistical Decision Gates (13 tests):** `tests/test_stage4_hardening.py` (Gate 2 decision matrix with all 5 criteria, small effect threshold rejection, boundary conditions, NaN/non-finite fail-closed, Gate 1 feasibility criteria & Phase 2 blocker, multi-threaded atomic reservation concurrency, reproducibility & bit-for-bit replay, benchmark sealing).

---

## 4. Document Registry

### Active Canonical Documentation Set:
- **`stage4_research_decision/stage4_preauth_decision_001.md`**: Governing Decision Document (`STAGE4-PREAUTH-DECISION-001`)
- **`stage4_research_decision/scientific_design_review.md`**: Statistical Design, Power Analysis & Non-Pooling Mandate
- **`stage4_research_decision/cost_and_authorization_audit.md`**: Financial Exposure Modeling & Provider Ledger Audit
- **`stage4_research_decision/final_adversarial_audit.md`**: Adversarial Verification, Isolation & Security Hardening
- **`stage4_research_decision/implementation_status.md`**: Physical Inventory, Architecture & Test Status

### Formally Superseded Legacy Documents:
The following 10 historical audit and protocol files are superseded: `next_experiment_decision.md`, `next_experiment_protocol.md`, `implementation_plan.md`, `implementation_readiness_audit.md`, `cost_and_stop_plan.md`, `final_pre_pilot_audit.md`, `final_engineering_audit.md`, `final_experiment_protocol.md`, `research_strategy_review.md`, `resource_and_authorization_plan.md`.

---

## 5. Execution Commands for Phase 1 Pilot

### Offline Dry-Run Mode (Zero API Calls, Verified Safe):
```bash
python3 -c "
from stage4.src.runner import Stage4Runner
runner = Stage4Runner(
    output_dir='stage4/pilot_dry_run',
    benchmark_dir='stage4/benchmarks',
    max_cost_usd=15.0,
    max_requests=300,
    candidate_slots=50,
    mock_mode=True
)
results = runner.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
print('Dry-run complete. Results saved to stage4/pilot_dry_run/results.json')
"
```

### Live Pilot Execution (Requires Founder Authorization & API Key):
```bash
export STAGE4_API_KEY=\"your-api-key\"
python3 -c "
from stage4.src.runner import Stage4Runner
runner = Stage4Runner(
    output_dir='stage4/pilot_live_results',
    benchmark_dir='stage4/benchmarks',
    max_cost_usd=15.0,
    max_requests=300,
    candidate_slots=50,
    mock_mode=False
)
results = runner.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
print('Pilot complete. Results saved to stage4/pilot_live_results/results.json')
"
```
