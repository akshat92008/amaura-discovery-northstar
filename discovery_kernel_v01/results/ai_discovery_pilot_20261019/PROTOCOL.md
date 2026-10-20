# PROTOCOL: Evidence-Guided AI Discovery vs Independent Search in PFSP

## 1. Executive Summary & Research Question

**Research Question:** Does an AI search process that receives feedback from previous candidates discover better algorithms than independent AI candidate generation, and can either approach beat strong established methods on untouched data?

This protocol defines a rigorous, preregistered, bounded experimental pilot conducted by Amaura Labs for North BlueStar.

---

## 2. Experimental Design

### 2.1 Domain & Objective
- **Domain:** Permutation Flow-Shop Scheduling (PFSP).
- **Objective:** Minimize makespan $C_{\max}(\pi)$, subject to valid permutation constraints $\pi \in S_n$.
- **Instance Generation:** Uniform processing times $p_{j,m} \sim U[1, 99]$ across small, medium, and large dimensions.

### 2.2 Comparison Arms
We compare two equal-budget candidate-generation strategies using the exact same model, parameters, prompt representation, and total proposal budget ($N=12$ proposals per arm, 24 total):

- **Arm A — Independent Best-of-N:**
  - 12 candidate algorithm specifications generated independently.
  - The generator prompt contains the problem definition, component options, and JSON schema.
  - The generator receives **zero performance feedback** or results from earlier proposals.
  
- **Arm B — Evidence-Guided Search:**
  - 12 candidate algorithm specifications generated across 3 sequential rounds of 4 proposals each ($3 \times 4 = 12$).
  - **Round 1:** 4 initial proposals generated with identical prompt context as Arm A.
  - **Round 2:** 4 proposals generated with a concise summary of Round 1 development-set makespans, validity status, and the current round champion.
  - **Round 3:** 4 proposals generated with an updated cumulative summary of Rounds 1 & 2 development-set makespans, validity status, and best observed recipes.

---

## 3. Execution Safety & Candidate Representation

All candidates are restricted to the declarative algorithm configuration space defined in `CANDIDATE_SPACE.md`.
- **Zero code execution:** LLM outputs are JSON configuration objects parsed and executed via the trusted `PFSPDeclarativeAdapter`.
- **Validation gate:** Proposals missing required fields, containing invalid enum options, or violating budget bounds ($0 \le \text{budget} \le 500$) are classified as `MALFORMED` and assigned failure records.
- **Canonicalization:** Every proposal is canonicalized with a SHA-256 `recipe_hash` to detect syntactic duplicates. Behavioral duplicates (producing identical schedules across dev instances) are explicitly tracked.

---

## 4. Model Provenance & Quota Policy

- **Provider:** Local Ollama runtime (`http://127.0.0.1:11434`).
- **Model Identifier:** `qwen2.5-coder:1.5b`.
- **Billing Basis:** 100% local host inference (Apple Silicon Metal / CPU).
- **Financial Cost:** Exactly **$0.00**.
- **External Network Calls:** Exactly **0** (strictly local loopback).
- **Parameters:** `temperature = 0.7`, `format = "json"`.
- **Audit Requirement:** Log raw JSON responses, prompt tokens, completion tokens, latency, and cryptographic hashes for all 24 proposals.

---

## 5. Data Protocol & Quarantined Firewalls

### 5.1 Dataset Definitions & Seed Governance
To prevent data contamination or holdout leakage, instance seeds were cross-checked against all 62,223 historical repository references to guarantee zero prior occurrence:

1. **Development Dataset (`data/dev_instances.json`):**
   - 20 instances.
   - Seed range: **500001 to 500020**.
   - SHA-256: `7255707ae4e1f3b4ce3b8b21e831abfdbed7eb938bd60e309e61acaba6414ecc`.
   - Dimensions: 6 Small ($n \in [20, 30], m \in [5, 10]$), 8 Medium ($n \in [50, 75], m \in [5, 15]$), 6 Large ($n \in [75, 120], m \in [10, 15]$).

2. **Final Holdout Dataset (`data/holdout_instances.json`):**
   - 30 instances.
   - Seed range: **500101 to 500130**.
   - SHA-256: `b714990db09d95492ec4e1a82f8317b177379ac2f4360c7122b20a94d8580090`.
   - Dimensions: 8 Small ($n \in [20, 30], m \in [5, 10]$), 14 Medium ($n \in [50, 75], m \in [5, 15]$), 8 Large ($n \in [100, 120], m \in [10, 15]$).

### 5.2 Strict Firewall Invariant
- **Development Firewall:** Candidate generation prompts and Arm B feedback summaries contain **only development instance metrics**.
- **Holdout Firewall:** Holdout instances (`data/holdout_instances.json`) are strictly sealed during candidate generation and selection. They are loaded **only after** Champion A, Champion B, and the Primary Baseline have been frozen.

---

## 6. Conventional Baselines & Primary Baseline Selection

Four established conventional methods are evaluated on the 20 development instances using verified implementations from `pfsp_candidate2_variants.py`:
1. **NEH (`neh_solve`):** Nawaz-Enscore-Ham (1983) constructive heuristic.
2. **NEH-LS (`neh_ls_single_pass_solve`):** NEH followed by single-pass insertion local search.
3. **Iterated Greedy (`iterated_greedy_solve`):** Ruin-and-recreate metaheuristic ($d=4$, max_iter=20).
4. **Candidate #2 Bounded (`solve_v2_anytime_bounded`, max_evals=200):** Historical flow-time guided constructive heuristic with bounded pairwise swap local search.

**Primary Baseline Selection Rule:** The conventional baseline with the lowest mean makespan across the 20 development instances is selected and frozen as the **Primary Baseline**.

---

## 7. Selection, Metrics & Statistical Analysis

### 7.1 Champion Selection Rule
For each arm:
- Disqualify any candidate with validation errors or timeouts.
- Compute the mean makespan across all 20 development instances.
- Select the candidate with the lowest mean development makespan as that arm's **Champion**.
- Freeze `Champion_A`, `Champion_B`, and `Primary_Baseline`.

### 7.2 Final Evaluation & Relative Improvement Metric
Evaluate `Champion_A`, `Champion_B`, and all 4 baselines on the 30 final holdout instances under identical per-instance timeout constraints (4.0s).

For each holdout instance $i \in \{1, \dots, 30\}$:
$$g_i = \frac{C_{\max,\mathrm{baseline},i} - C_{\max,\mathrm{candidate},i}}{C_{\max,\mathrm{baseline},i}}$$

- **Summary Statistics:** Mean relative improvement $\bar{g}$, median, standard deviation, and win/tie/loss counts.
- **Statistical Significance:** Paired 95% bootstrap confidence interval computed via 10,000 resamples with fixed seed (`42`).

### 7.3 Preregistered Discovery Gate
A candidate qualifies as a **promising discovery result** if and only if:
1. **Full Validity:** 100% valid permutations produced across all 30 holdout instances.
2. **Effect Threshold:** Mean paired relative makespan improvement $\bar{g} \ge 1.0\%$ over the frozen primary baseline.
3. **Statistical Rigor:** The 95% bootstrap confidence interval lower bound is strictly greater than 0 ($CI_{95, \mathrm{lower}} > 0\%$).
4. **Resource Compliance:** Runtime and evaluation budgets remain within bounds.
5. **Full Reproducibility:** Results reproduce identically from saved artifacts.

### 7.4 Search Strategy Comparison
Separately evaluate `Champion_B` vs `Champion_A` on the 30 holdout instances:
- Paired effect size $g_{B \text{ vs } A} = \frac{C_{\max, A, i} - C_{\max, B, i}}{C_{\max, A, i}}$.
- 95% bootstrap CI and win/tie/loss counts.
- Determine whether evidence-guided search demonstrated an empirical advantage over independent generation.

---

## 8. Stopping Rules & Deliverables

- **Max proposals:** 12 per arm (24 total).
- **Execution limits:** Max 4.0s per instance evaluation; max 90 minutes total experiment time.
- **Final outputs:**
  1. `PROTOCOL.md` (this preregistration).
  2. `CANDIDATE_SPACE.md` (declarative component schema).
  3. `run_records.jsonl` (append-only machine-readable event log).
  4. `development_results.json` (all dev scores, selection decisions, and freezing manifest).
  5. `final_results.json` (per-instance holdout outcomes, bootstrap CIs, and hypothesis tests).
  6. `AUDIT_REPORT.md` (data quarantine, provenance, and cost verification).
  7. `DECISION_MEMO.md` (verdict: GO, MODIFY, or STOP, with explicit scientific rationale).
  8. `manifest.json` (SHA-256 hashes of all artifacts).
