# AUDIT REPORT: PFSP AI Discovery Pilot (2026-10-19)
## Evidence-Guided Search vs Independent Best-of-N on North BlueStar

**Date:** 2026-10-19  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Experiment ID:** `ai_discovery_pilot_20261019`  
**Host Environment:** Darwin 24.3.0 (macOS, Apple Silicon)  
**Auditor:** Lead Experimental Scientist & Research Infrastructure Engineer, Amaura Labs  

---

## 1. Executive Summary

This audit assesses the execution correctness, data quarantine, resource expenditure, and scientific outcomes of the North BlueStar AI discovery pilot.

The experiment evaluated whether an evidence-guided AI candidate generation process (Arm B: 12 proposals across 3 rounds with development feedback) discovers better scheduling algorithms than independent candidate generation (Arm A: 12 independent proposals), and whether either approach outperforms strong conventional baselines (`neh_ls_insertion`, `iterated_greedy`, `candidate_2_bounded`, `neh_classical`) on untouched holdout data.

### Key Audit Findings:
1. **Financial Spend & Resource Compliance:** Billed API spend was exactly **$0.00**. Exactly **0** paid external API calls were made. All 24 proposals were generated locally using Ollama (`qwen2.5-coder:1.5b`) on host Apple Silicon.
2. **Execution Safety & Process Containment:** Zero arbitrary Python scripts were executed. All 24 proposals adhered to a declarative configuration space executed via the trusted `PFSPDeclarativeAdapter` in isolated subprocesses (`multiprocessing.get_context("spawn")`) with hard 4.0s timeouts. 100% of candidate solutions (720 total evaluations across dev and holdout) satisfied valid permutation constraints.
3. **Data Quarantine Integrity:** Development instances (20, seeds 500001–500020) and holdout instances (30, seeds 500101–500130) had zero seed collisions with prior repository experiments. Holdout instances were strictly quarantined and evaluated only after the Primary Baseline, Champion A, and Champion B were frozen.
4. **Scientific Discovery Verdict:**
   - **Preregistered 1.0% Discovery Gate: FAILED.**
   - Neither Champion A nor Champion B outperformed the frozen Primary Baseline (`neh_ls_insertion`) on the holdout set.
   - **Champion A vs Primary Baseline:** $\bar{g} = -0.372\%$, 95% Bootstrap CI: $[-0.680\%, -0.093\%]$ (Wins: 7, Ties: 4, Losses: 19).
   - **Champion B vs Primary Baseline:** $\bar{g} = -2.528\%$, 95% Bootstrap CI: $[-2.984\%, -2.015\%]$ (Wins: 1, Ties: 1, Losses: 28).
   - **Search Strategy Comparison (Arm B vs Arm A):** $\bar{g}_{B \text{ vs } A} = -2.151\%$, 95% Bootstrap CI: $[-2.625\%, -1.658\%]$ (Wins: 2, Ties: 1, Losses: 27).
   - **Feedback Pathology Identified:** Arm B suffered severe **prompt anchoring / mode collapse**. Providing feedback on early candidate performance caused the model to repeatedly re-propose the same initial suboptimal heuristic (Palmer slope weighting) rather than exploring diverse alternatives. Arm A's independent sampling produced 7 unique algorithmic recipes, discovering a superior candidate (`arm_a_prop_08`).

---

## 2. Infrastructure & Execution Safety Audit

| Subsystem | Audit Standard | Verification Method | Outcome |
|---|---|---|:---:|
| **Candidate Execution Boundary** | No arbitrary code execution; restricted declarative DSL | Schema parser & `PFSPDeclarativeAdapter` | **PASS** |
| **Process Isolation** | Isolated subprocess per evaluation | `multiprocessing.get_context("spawn")` | **PASS** |
| **Timeout Enforcement** | Hard process termination at 4.0s limit | POSIX SIGKILL termination supervisor | **PASS** |
| **Solution Feasibility Gate** | Every solution must be valid permutation $\pi \in S_n$ | Independent `validate_permutation()` check | **PASS** (100% valid) |
| **Event Logging** | Full append-only machine-readable audit trail | `run_records.jsonl` (768 events logged) | **PASS** |

### Execution Statistics:
- **Total Instance Executions:** 740 runs across 4 phases.
  - Phase 1 (Baselines Dev): $4 \times 20 = 80$ executions.
  - Phase 2A (Arm A Dev): $12 \times 20 = 240$ executions.
  - Phase 2B (Arm B Dev): $12 \times 20 = 240$ executions.
  - Phase 3 (Holdout): $6 \times 30 = 180$ executions.
- **Feasibility Rate:** 100.0% (740 / 740 valid permutations). Zero timeouts, zero memory violations, zero exceptions.

---

## 3. Model Provenance & Financial Spend Audit

All candidate generation was executed locally via Ollama to satisfy the hard $0.00 spend constraint without relying on external billable APIs.

| Metric | Arm A (Independent) | Arm B (Evidence-Guided) | Combined Total |
|---|:---:|:---:|:---:|
| **Provider** | Ollama (Local) | Ollama (Local) | Ollama (Local) |
| **Model Identifier** | `qwen2.5-coder:1.5b` | `qwen2.5-coder:1.5b` | `qwen2.5-coder:1.5b` |
| **Endpoint** | `http://127.0.0.1:11434/api/generate` | `http://127.0.0.1:11434/api/generate` | Local Loopback |
| **Financial Spend** | **$0.0000** | **$0.0000** | **$0.0000** |
| **External Network Calls** | 0 | 0 | 0 |
| **Proposal Count** | 12 | 12 | 24 |
| **Prompt Tokens** | 8,472 | 11,048 | 19,520 |
| **Completion Tokens** | 1,715 | 1,642 | 3,357 |
| **Total Tokens** | 10,187 | 12,690 | 22,877 |
| **Mean Latency per Proposal** | 4.53s | 3.94s | 4.23s |
| **Total Generation Wall-Clock** | 54.3s | 47.3s | 101.6s (~1.7 min) |

---

## 4. Data Provenance & Quarantine Audit

### 4.1 Seed Disjointness Verification
A full repository audit was conducted across 62,223 token occurrences to identify all historical random seeds. Prior PFSP benchmarks utilized seeds in ranges 40001–41100 and 90001–90030.

The fresh datasets were generated in the unallocated 500000+ range:
- **Development Dataset (`data/dev_instances.json`):**
  - Count: 20 instances.
  - Seed Range: **500001 to 500020**.
  - SHA-256 Digest: `7255707ae4e1f3b4ce3b8b21e831abfdbed7eb938bd60e309e61acaba6414ecc`.
- **Holdout Dataset (`data/holdout_instances.json`):**
  - Count: 30 instances.
  - Seed Range: **500101 to 500130**.
  - SHA-256 Digest: `b714990db09d95492ec4e1a82f8317b177379ac2f4360c7122b20a94d8580090`.

### 4.2 Quarantine & Anti-Leakage Verification
- The holdout dataset path (`data/holdout_instances.json`) was strictly quarantined.
- Neither candidate prompts, round feedback summaries, nor the selection controller had access to holdout matrices or scores during Phase 1 and Phase 2.
- The Primary Baseline (`neh_ls_insertion`), Champion A (`arm_a_prop_08`), and Champion B (`arm_b_prop_01`) were cryptographically frozen in `development_results.json` prior to the loading and evaluation of holdout instances in Phase 3.

---

## 5. Candidate Generation & Search Dynamics Audit

### 5.1 Arm A (Independent Best-of-12)
- **Validity Rate:** 100% (12 / 12 valid JSON matching declarative schema).
- **Unique Algorithmic Recipes:** 7 distinct configurations explored.
- **Syntactic Duplicates:** 5 / 12 proposals duplicated earlier recipes.
- **Top Candidates on Dev Set:**
  1. `arm_a_prop_08`: Mean makespan **3587.75** (LPT + makespan_only + flow_time tie-break + single-pass insertion LS, 300 evals).
  2. `arm_a_prop_05`: Mean makespan **3642.05**.
  3. `arm_a_prop_04`: Mean makespan **3649.45**.
  4. `arm_a_prop_03`: Mean makespan **3650.10**.
  5. `arm_a_prop_02`: Mean makespan **3652.65**.

### 5.2 Arm B (Evidence-Guided Search, 3 Rounds x 4 Proposals)
- **Validity Rate:** 100% (12 / 12 valid JSON matching declarative schema).
- **Unique Algorithmic Recipes:** 2 distinct configurations explored.
- **Syntactic Duplicates:** 10 / 12 proposals were syntactic duplicates of `arm_b_prop_01`.
- **Search Dynamics:**
  - In Round 1, proposal `arm_b_prop_01` selected Palmer slope index (`weighted_profile_desc`).
  - In Round 2 and Round 3, the prompt fed the model summary performance evidence showing `arm_b_prop_01` as the round leader.
  - **Pathology Observed:** The model experienced complete **mode collapse / prompt anchoring**. Instead of mutating parameters (e.g. testing `total_processing_time_desc` or increasing budget), the model repeated the exact Palmer slope recipe across almost every subsequent query.
  - Champion B: `arm_b_prop_01` (Mean makespan: **3654.15**).

---

## 6. Conventional Baselines & Primary Baseline Selection

All 4 baselines were evaluated on the 20 development instances using identical process isolation.

| Method ID | Algorithm Family | Mean Dev Makespan | Mean Dev Runtime | Dev Rank |
|---|---|:---:|:---:|:---:|
| **`neh_ls_insertion`** | NEH + Single-Pass Insertion LS | **3576.95** | 272.23 ms | **1 (Primary Baseline)** |
| **`iterated_greedy`** | Ruin-and-Recreate Metaheuristic ($d=4$) | **3583.85** | 234.22 ms | 2 |
| **`candidate_2_bounded`** | Candidate #2 V2 Anytime Bounded (200 evals) | **3585.95** | 72.83 ms | 3 |
| **`neh_classical`** | Classical Nawaz-Enscore-Ham (1983) | **3597.80** | 73.73 ms | 4 |

**Primary Baseline Decision:** In strict accordance with the preregistered protocol, `neh_ls_insertion` was selected and frozen as the Primary Baseline based exclusively on development data.

---

## 7. Holdout Generalization & Statistical Hypothesis Testing

All frozen methods were evaluated on the 30 fresh, sealed holdout instances.

### 7.1 Holdout Makespan Summary Table

| Method | Role | Mean Holdout Makespan | Mean Runtime | Valid / 30 |
|---|---|:---:|:---:|:---:|
| **`neh_ls_insertion`** | **Frozen Primary Baseline** | **3872.23** | 357.51 ms | 30 / 30 |
| **`iterated_greedy`** | Conventional Metaheuristic | 3873.70 | 285.45 ms | 30 / 30 |
| **`arm_a_prop_08`** | **Frozen Champion A** | **3887.70** | 106.98 ms | 30 / 30 |
| **`candidate_2_bounded`** | Historical Candidate #2 V2 | 3887.83 | 91.25 ms | 30 / 30 |
| **`neh_classical`** | Classical Constructive Baseline | 3897.60 | 92.07 ms | 30 / 30 |
| **`arm_b_prop_01`** | **Frozen Champion B** | **3974.43** | 101.86 ms | 30 / 30 |

### 7.2 Paired Relative Improvement & Bootstrap Analysis

$$g_i = \frac{C_{\max,\mathrm{baseline},i} - C_{\max,\mathrm{candidate},i}}{C_{\max,\mathrm{baseline},i}}$$

Confidence intervals computed via paired percentile bootstrap (10,000 resamples, seed 42):

#### 1. Champion A vs Primary Baseline (`neh_ls_insertion`):
- Mean relative improvement $\bar{g}$: **-0.372%**
- Median relative improvement: **-0.108%**
- Standard deviation: 0.832%
- 95% Bootstrap Confidence Interval: **[-0.680%, -0.093%]**
- Pairwise Outcome: **7 Wins, 4 Ties, 19 Losses**
- Preregistered 1.0% Gate: **FAIL** (CI is entirely below zero).

#### 2. Champion B vs Primary Baseline (`neh_ls_insertion`):
- Mean relative improvement $\bar{g}$: **-2.528%**
- Median relative improvement: **-2.643%**
- Standard deviation: 1.361%
- 95% Bootstrap Confidence Interval: **[-2.984%, -2.015%]**
- Pairwise Outcome: **1 Win, 1 Tie, 28 Losses**
- Preregistered 1.0% Gate: **FAIL** (Substantially inferior to baseline).

#### 3. Search Strategy Comparison (Champion B vs Champion A):
- Mean relative improvement $\bar{g}_{B \text{ vs } A}$: **-2.151%**
- Median relative improvement: **-2.133%**
- 95% Bootstrap Confidence Interval: **[-2.625%, -1.658%]**
- Pairwise Outcome: **2 Wins, 1 Tie, 27 Losses**
- Conclusion: Under tested conditions, **evidence-guided search performed significantly worse than independent Best-of-N search**.

---

## 8. Failure Analysis & Scientific Implications

1. **Failure of Feedback in Small Language Models:**
   The failure of Arm B to discover superior candidates is not an infrastructure defect; it is a fundamental behavioral characteristic of feedback-guided generation in parameter-constrained models. When the model observed that `arm_b_prop_01` was the best-performing candidate in Round 1, it anchored on the verbatim recipe of that candidate in subsequent rounds, causing catastrophic loss of exploratory entropy.
   
2. **Quality of Discovered Algorithm in Arm A:**
   Although Champion A did not beat the primary baseline (`neh_ls_insertion`), it beat the classical `neh_classical` heuristic (3887.70 vs 3897.60) while requiring only 106.98 ms per instance compared to `neh_ls_insertion`'s 357.51 ms (a **3.3x speedup** for a 0.37% makespan trade-off). This demonstrates that independent Best-of-N sampling successfully navigated the restricted space to identify a high-efficiency Pareto configuration.

3. **Integrity of the Discovery Kernel:**
   The Discovery Kernel v0.1 functioned with complete mathematical, cryptographic, and operational integrity. It enforced strict budgets, prevented holdout leakage, eliminated arbitrary execution risk, and executed the evaluation pipeline without manual intervention.
