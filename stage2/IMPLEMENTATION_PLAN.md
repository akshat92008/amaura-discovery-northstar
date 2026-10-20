# Amaura Labs — Stage 2 Implementation Plan

**Date:** 2026-10-05  
**Mission:** Implement complete experimental infrastructure for Amaura Labs Stage 2:
> *"At a matched generation budget, does choosing candidates by actually running them add value over a strong prompt that chooses without running anything?"*
> **Primary Comparison: D vs B** (both using the exact same 20 expert-generated candidates).

---

## 1. Repository Audit: Existing Infrastructure vs. Stage 2 Requirements

| Component | Existing Location | Status / Reusability | Stage 2 Gap / Action |
| :--- | :--- | :--- | :--- |
| **Graph-Coloring Generator** | `experiment7/evaluator.py`, `experiment8/evaluator.py` | Working: 8 graph families (Erdos-Renyi, Geometric, Barabasi-Albert, Mycielski-like, Watts-Strogatz, Bipartite-Bridges, Regular, Clustered-Partition). | **Reuse & Expand:** Modularize generator into `stage2/benchmarks/generator.py`. Standardize split creation for Pilot, Dev, Hidden-final (~200 instances), and Sealed Reserve. |
| **Graph-Coloring Evaluator** | `experiment8/evaluator.py` | Working: AST sandbox, K3 sanity check, `signal.alarm` timeout handling, chromatic validation. | **Harden:** Port to `stage2/src/evaluator_gc.py`. Add defensive copying, process-level isolation, strict determinism, and 12 canary defenses. |
| **PFSP Generator** | `experiment9/src/benchmarks.py` | Working: 6 instance families (Taillard uniform, machine correlation, job correlation, bimodal, high-ratio, square, U-load). | **Reuse & Modularize:** Integrate into `stage2/benchmarks/generator.py` for 4-way data splitting. |
| **PFSP Evaluator** | `experiment11/src/evaluator.py` | Working: $O(nm)$ DP makespan calculator, scale-aware timeout formula, AST safety checks, permutation validation. | **Harden:** Port to `stage2/src/evaluator_pfsp.py`. Add canary verification and immutable reporting. |
| **Baselines (Graph Coloring)** | `experiment7/evaluator.py` | Partial: Natural Greedy, Welsh-Powell, DSATUR, RLF present. | **Gap:** **TabuCol** (Hertz & de Werra 1987) is missing. Must implement strict, reproducible TabuCol in `stage2/baselines/graph_coloring.py`. |
| **Baselines (PFSP)** | `experiment11/src/baselines.py` | Working: Palmer, CDS, NEH, Bounded Iterated Greedy (IG). | **Reuse:** Package NEH and IG into `stage2/baselines/pfsp.py`. |
| **Model / Provider Interface** | `experiment11/src/llm_client.py`, `experiment16/src/llm_client.py` | Working: OmniRoute HTTP client, token counting, truncation detection, SSE/JSON parsing. | **Harden for Section 16:** Enforce strict provider provenance check. If returned `model` != requested `model`, **fail closed and abort immediately**. Add judge querying mode with temperature=0.0/0.2. |
| **Sandbox / Runner** | `experiment16/src/runner.py` | Working: Multi-threaded generation, candidate caching, atomic disk appending. | **Redesign:** Build `stage2/src/runner.py` supporting Arms A, B, C, D with hash-identical candidate pools between B and D (`assert candidate_i_hash_B == candidate_i_hash_D`). |
| **Candidate Storage** | `experiment16/candidates/candidates.jsonl` | Working: JSONL serialization. | **Harden for Section 18:** Ensure all 23 required metadata fields are captured (including `experiment_id`, `trial_id`, `arm`, `pool_id`, `prompt_hash`, `model_id`, etc.). |
| **Hidden-Set Handling** | `experiment16/src/runner.py` | Working: Split separation. | **Critical Section 32 Gap:** Implement a formal, programmatic **Hidden Firewall**. Accessing hidden benchmarks before the state machine reaches `SELECTIONS_FROZEN` raises `PermissionError` and logs access attempt. |
| **Experiment State Machine** | None (Previously implicit in scripts) | Missing. | **New Component:** Build `stage2/src/state_machine.py` implementing the 10 formal states (`DRAFT` $\to$ `AUDIT` $\to$ `PILOT` $\to$ `PROMPTS_FROZEN` $\to$ `DATA_FROZEN` $\to$ `MAIN_RUNNING` $\to$ `SELECTIONS_FROZEN` $\to$ `HIDDEN_RUNNING` $\to$ `ANALYSIS_FROZEN` $\to$ `REPORT_COMPLETE`). |
| **Arm B Judge & Aggregator** | None | Missing. | **New Component:** Build `stage2/src/judge.py` implementing 3-shuffle blind LLM judging, randomized candidate presentation, and deterministic aggregation rules. |
| **Pool Spread Analyzer** | None | Missing. | **New Component:** Build `stage2/src/pool_spread.py` calculating mean, median, SD, CV, relative range, unique score count, and verifying pre-registered spread thresholds. |
| **Subsampling Scaling Engine** | `experiment14/` | Ad-hoc script. | **New Component:** Build `stage2/src/scaling.py` evaluating $N \in \{1, 2, 5, 10, 20\}$ from the same 20-candidate pool without extra calls. |
| **Evaluator Canaries & Red-Team** | Partial in exp tests. | Missing unified suite. | **New Component:** Build `stage2/src/canaries.py` implementing all 12 explicit canary tests. |
| **Statistical Analysis Scripts** | `experiment11/src/analyze.py`, `experiment16/analysis/analyze.py` | Working: Wilcoxon, Bootstrap CI, Cohen's d. | **Harden for Section 23-26:** Add Holm correction across both problems, selection regret calculation ($S_{\text{selected}} - S_{\text{best}}$), practical-margin equivalence rule, and automated outcome classification. |

---

## 2. Architecture & File Structure

```text
stage2/
├── config.json                     # Complete Stage 2 configuration (budgets, seeds, thresholds)
├── preregistration.md              # Preregistration protocol document
├── IMPLEMENTATION_PLAN.md          # This implementation plan
├── IMPLEMENTATION_AUDIT.md         # Final audit certification
├── state.json                      # Immutable state machine tracker
├── audit/
│   ├── audit_log.jsonl             # Cryptographic audit receipts (SHA-256 for all components)
│   └── red_team_review.md          # Independent red-team evaluation review
├── benchmarks/
│   ├── generator.py                # Deterministic generator for Graph Coloring & PFSP
│   ├── manifest.json               # Cryptographic checksums of all 4 splits per problem
│   ├── graph_coloring/             # pilot.json, dev.json, hidden.json, sealed.json
│   └── pfsp/                       # pilot.json, dev.json, hidden.json, sealed.json
├── baselines/
│   ├── graph_coloring.py           # DSATUR, RLF, TabuCol
│   └── pfsp.py                     # NEH, Iterated Greedy
├── prompts/
│   ├── expert_prompt_gc.txt        # Frozen expert prompt for Graph Coloring
│   ├── expert_prompt_pfsp.txt      # Frozen expert prompt for PFSP
│   ├── amaura_perspectives_gc.py   # Diversified perspectives for Arm C (Graph Coloring)
│   ├── amaura_perspectives_pfsp.py # Diversified perspectives for Arm C (PFSP)
│   ├── judge_prompts.py            # Execution-blind judge prompt template
│   └── manifest.json               # Checksums of all prompts
├── src/
│   ├── __init__.py
│   ├── state_machine.py            # State Machine + Technical Hidden Firewall
│   ├── llm_client.py               # Strict provenance client (no silent fallbacks)
│   ├── sandbox.py                  # Process/AST execution sandbox
│   ├── evaluator_gc.py             # Graph Coloring Evaluator
│   ├── evaluator_pfsp.py           # PFSP Evaluator
│   ├── canaries.py                 # 12 Evaluator canary checks
│   ├── judge.py                    # Arm B 3-shuffle judge & deterministic aggregator
│   ├── pool_spread.py              # Pool spread metric calculation & threshold gates
│   ├── scaling.py                  # N=1,2,5,10,20 deterministic subsampling
│   ├── runner.py                   # Stage 2 Orchestrator (Arms A, B, C, D)
│   ├── analyze.py                  # Statistical engine (Wilcoxon, Holm, Bootstrap, Regret)
│   └── power_analysis.py           # Simulation-based power analysis from pilot
├── tests/
│   ├── test_state_machine.py       # State transitions & firewall enforcement
│   ├── test_hidden_firewall.py     # Attempted leak defense & logging
│   ├── test_hash_identity.py       # Pool identity B == D enforcement
│   ├── test_judge_aggregation.py   # 3-shuffle voting & tie-breakers
│   ├── test_canaries.py            # All 12 evaluator canary tests
│   ├── test_determinism.py         # Evaluator reproducibility tests
│   ├── test_baselines.py           # Verification of DSATUR, RLF, TabuCol, NEH, IG
│   ├── test_pool_spread.py         # Spread metrics calculation
│   ├── test_scaling.py             # Subsampling mechanics
│   └── test_statistics.py          # Wilcoxon, Holm, Bootstrap, Regret
└── cli.py                          # Unified CLI: pilot, freeze, main, hidden, analyze, audit, dry-run
```

---

## 3. Protocol Rules & Implementation Directives

1. **Primary Comparison (D vs B):**
   - For every trial, the exact same 20 candidates generated via the expert prompt are passed to Arm B and Arm D.
   - The runner verifies `candidate_i_hash_B == candidate_i_hash_D` for all $i \in [1, 20]$ and halts if mismatched.
   - Arm B selects a candidate via 3-shuffle blind LLM judging.
   - Arm D selects a candidate via dev-set evaluation.
2. **Arm A (Random Pick):**
   - Seeded random draw from the 20 candidates.
   - Pool mean reported alongside as the expected value benchmark.
3. **Arm C (Amaura Diversified):**
   - 20 candidates generated from 20 predefined distinct conceptual perspectives.
   - Evaluated on dev set; best selected.
4. **Technical Hidden Firewall:**
   - Hidden benchmark data is stored encrypted/isolated and cannot be queried by `runner.py` or `evaluator.py` until the state machine transitions to `SELECTIONS_FROZEN`.
   - Any premature access attempts trigger an alert and are logged in `stage2/audit/audit_log.jsonl`.
5. **Evaluator Canaries:**
   - 12 canaries must pass before any pilot or main run proceeds.
6. **No Premature Main Run:**
   - The 30-trial main run requires human confirmation after all tests, dry-runs, canaries, and red-team audits are completed.

---

## 4. Step-by-Step Implementation Sequence

1. **Step 1: Baselines & Benchmark Generator**
   - Implement `stage2/baselines/graph_coloring.py` (DSATUR, RLF, and TabuCol).
   - Implement `stage2/baselines/pfsp.py` (NEH and Iterated Greedy).
   - Implement `stage2/benchmarks/generator.py` (generating Pilot, Dev, Hidden, Sealed splits).
2. **Step 2: Core Evaluators, Sandbox, and 12 Canaries**
   - Implement `stage2/src/sandbox.py`.
   - Implement `stage2/src/evaluator_gc.py` and `stage2/src/evaluator_pfsp.py`.
   - Implement `stage2/src/canaries.py` (covering all 12 canary requirements).
3. **Step 3: State Machine, Hidden Firewall, and Provenance LLM Client**
   - Implement `stage2/src/state_machine.py` with fail-closed hidden data access.
   - Implement `stage2/src/llm_client.py` enforcing strict model ID verification.
4. **Step 4: Prompts, Arm B Judge, and Pool Spread Engine**
   - Create frozen expert prompts (`expert_prompt_gc.txt`, `expert_prompt_pfsp.txt`).
   - Create diversified perspectives for Arm C.
   - Implement `stage2/src/judge.py` with 3-shuffle randomized presentation and deterministic aggregation.
   - Implement `stage2/src/pool_spread.py`.
5. **Step 5: Subsampling Scaling, Power Analysis, and Statistical Engine**
   - Implement `stage2/src/scaling.py` ($N \in \{1, 2, 5, 10, 20\}$).
   - Implement `stage2/src/power_analysis.py`.
   - Implement `stage2/src/analyze.py` (Wilcoxon, Holm correction, Bootstrap CI, Selection Regret).
6. **Step 6: Orchestrator, CLI, and Comprehensive Test Suite**
   - Implement `stage2/src/runner.py`.
   - Implement `stage2/cli.py` supporting `pilot`, `freeze`, `main`, `hidden`, `analyze`, `audit`, `dry-run`.
   - Implement unit and integration test suite across `stage2/tests/`.
7. **Step 7: Verification, Red-Teaming, and Audit Certification**
   - Execute all tests (`pytest stage2/tests`).
   - Execute dry-run (`python3 stage2/cli.py dry-run`).
   - Execute evaluator canaries.
   - Generate independent red-team review artifact.
   - Produce `stage2/config.json`, `stage2/preregistration.md`, and `stage2/IMPLEMENTATION_AUDIT.md`.
