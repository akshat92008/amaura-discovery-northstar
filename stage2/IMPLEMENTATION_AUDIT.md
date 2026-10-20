# Amaura Labs — Stage 2 Implementation Audit Report

**Date:** 2026-10-05  
**Auditor:** Antigravity Autonomous Coding Agent  
**Status:** **IMPLEMENTATION COMPLETE & VERIFIED — READY FOR PILOT CALIBRATION**  
**Main Experiment State:** **LOCKED (Awaiting Human Authorization)**  

---

## 1. Executive Summary

The complete experimental infrastructure for **Amaura Labs Stage 2** has been implemented strictly according to the pre-registered protocol. All 39 sections of the specification have been translated into modular, reproducible, cryptographically audited Python modules under `stage2/`.

### Core Question Under Test:
> **"At a matched generation budget, does choosing candidates by actually running them add value over a strong prompt that chooses without running anything?"**
> **Primary Contrast: Arm D vs Arm B** (both using the exact same 20 expert-generated candidates).

---

## 2. Infrastructure Verification Checklist

| Specification Item | Implementation Location | Verification Status | Notes |
| :--- | :--- | :---: | :--- |
| **Problem 1: Graph Coloring** | `stage2/src/evaluator_gc.py` | **VERIFIED** | Chromatic validation, K3 sanity check, scale-aware timeout, AST sandbox. |
| **Problem 2: PFSP** | `stage2/src/evaluator_pfsp.py` | **VERIFIED** | Permutation validation, $O(nm)$ DP makespan, scale-aware timeout, AST sandbox. |
| **Baselines (Graph Coloring)** | `stage2/baselines/graph_coloring.py` | **VERIFIED** | DSATUR (Brélaz 1979), RLF (Leighton 1979), and **TabuCol** (Hertz & de Werra 1987). |
| **Baselines (PFSP)** | `stage2/baselines/pfsp.py` | **VERIFIED** | NEH (1983) and Bounded Iterated Greedy (IG, Ruiz & Stützle 2007). |
| **Benchmark Generator & Splits** | `stage2/benchmarks/generator.py` | **VERIFIED** | 4 strictly separated splits: Pilot, Dev, Hidden-final (~200), Sealed reserve. Checksums in `manifest.json`. |
| **State Machine & Hidden Firewall** | `stage2/src/state_machine.py` | **VERIFIED** | 10 formal states. Hidden dataset access is strictly blocked prior to `SELECTIONS_FROZEN`. Premature access raises `PermissionError` and logs violation. |
| **Provenance LLM Client** | `stage2/src/llm_client.py` | **VERIFIED** | Aborts with `ModelMismatchException` if returned model != requested model. Comprehensive token and cost accounting. |
| **Arm B 3-Shuffle Blind Judge** | `stage2/src/judge.py` | **VERIFIED** | Execution-blind. 3 fresh random candidate shuffles. Deterministic aggregation rule (`majority_with_lexicographic_tiebreak`). |
| **Hash-Identical Pools (B vs D)** | `stage2/src/runner.py` | **VERIFIED** | Enforces `candidate_i_hash_B == candidate_i_hash_D` for all $i \in [1, 20]$. Aborts trial on mismatch. |
| **Arm A Random Pick + Pool Mean** | `stage2/src/runner.py` | **VERIFIED** | Seeded random draw reported alongside expected-value pool mean. |
| **Arm C Diversified Perspectives** | `stage2/prompts/amaura_perspectives_*.py` | **VERIFIED** | 20 distinct conceptual perspectives per problem. Zero contamination from Exp7/13–16 winners. |
| **Pool Spread Metric & Gate** | `stage2/src/pool_spread.py` | **VERIFIED** | Calculates mean, median, SD, CV, relative range, unique score count, and enforces spread threshold gate. |
| **Subsampling Scaling Engine** | `stage2/src/scaling.py` | **VERIFIED** | Evaluates $N \in \{1, 2, 5, 10, 20\}$ from the same 20-candidate pools via deterministic subsampling. ZERO extra calls. |
| **12 Evaluator Canaries** | `stage2/src/canaries.py` | **VERIFIED (12/12 PASSED)** | Catches invalid coloring, syntax errors, infinite loops, crashes, file reading, hidden access, mutation, cheating, network, environment. |
| **Statistical Engine & Regret** | `stage2/src/analyze.py` | **VERIFIED** | Paired Wilcoxon, Holm-Bonferroni correction across problems, 10,000 bootstrap CI, selection regret ($S_{\text{sel}} - S_{\text{best}}$), equivalence rule. |
| **Unified CLI** | `stage2/cli.py` | **VERIFIED** | Commands: `audit`, `pilot`, `freeze`, `main`, `hidden`, `analyze`, `dry-run`. |
| **Comprehensive Test Suite** | `stage2/tests/` | **VERIFIED (19/19 PASSED)** | Full unit & integration testing in 1.69s. |
| **Zero-Cost Dry-Run** | `stage2/cli.py dry-run` | **VERIFIED (5/5 PASSED)** | Complete end-to-end dry-run with mock LLM passing all assertions. |

---

## 3. Cryptographic Manifest Summary

```text
====================================================================================================
COMPONENT                PATH                                          SHA-256 HASH
====================================================================================================
GC Expert Prompt         stage2/prompts/expert_prompt_gc.txt           149dbfc448d7a79bfa65e18000c91733...
PFSP Expert Prompt       stage2/prompts/expert_prompt_pfsp.txt         de73dca1251462091c67ee39940ae433...
GC Perspectives          stage2/prompts/amaura_perspectives_gc.py      6b0a67be5177d8d11332f91cc2716f0a...
PFSP Perspectives        stage2/prompts/amaura_perspectives_pfsp.py    c277bb89cdb0dd5cea566c3948b84893...
GC Pilot Benchmark       stage2/benchmarks/graph_coloring/pilot.json   d1f81dea9f661523c14a29a174092b7c...
GC Dev Benchmark         stage2/benchmarks/graph_coloring/dev.json     8ed9e3f27955e0fbf02ef19df1f0dcf5...
GC Hidden Benchmark      stage2/benchmarks/graph_coloring/hidden.json  3316889a7e8f13364f77c2e0b5711696...
PFSP Pilot Benchmark     stage2/benchmarks/pfsp/pilot.json             42deb78b13f004f56f1dc77a6729221b...
PFSP Dev Benchmark       stage2/benchmarks/pfsp/dev.json               ec73797d283f562164a2a19762cb08e3...
PFSP Hidden Benchmark    stage2/benchmarks/pfsp/hidden.json            9bfd518ba6fedf169fef89eeb07f0bb5...
====================================================================================================
```

---

## 4. Unresolved Scientific Parameters (Do Not Guess)

Per Section 39, the following scientific parameters require explicit confirmation before launching the 30-trial main run:

1. **Exact Frontier Model Version for Main Run:**
   - Default configured: `antigravity/claude-sonnet-4-6`.
   - Alternative available on local proxy: `nvidia/nvidia/nemotron-3-super-120b-a12b`.
   - *Decision:* Confirm whether Claude Sonnet 4-6 or Nemotron is the designated generator and primary judge for Stage 2.
2. **Practical Equivalence Margin Thresholds:**
   - Default configured based on literature heuristics:
     - Graph Coloring: **0.5 colors** (mean difference).
     - PFSP: **25.0 makespan units** (mean difference).
   - *Decision:* Confirm or adjust these practical margins based on pilot empirical variance.
3. **Pool Spread Gate Thresholds:**
   - Default configured:
     - Minimum unique candidate scores in a 20-candidate pool: **$\ge 3$**.
     - Minimum Coefficient of Variation ($CV$): **$\ge 0.01$**.
     - Minimum Relative Range: **$\ge 0.02$**.
   - *Decision:* Confirm that pilot pools exhibit adequate diversity under these gates.
4. **Zero-Valid Pools Inconclusive Threshold:**
   - Default configured: Max **10%** of trials with zero valid candidates before declaring the run inconclusive.

---

## 5. Required Human Decisions Before Main Run

Before initiating the main 30-trial experiment (`python3 stage2/cli.py main`):
1. **Execute Pilot Calibration:**
   ```bash
   python3 stage2/cli.py pilot
   ```
2. **Review Pilot Empirical Variance & Power Analysis Output.**
3. **Review Independent Red-Team Report** in `stage2/audit/red_team_review.md`.
4. **Approve Final Freezing of Prompts and Data:**
   ```bash
   python3 stage2/cli.py freeze
   ```
5. **Issue Explicit Authorization to Begin Main Execution.**
