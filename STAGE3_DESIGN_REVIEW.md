# Amaura Labs — Stage 3 Experimental Design Review (Revision 4.3)
## Iterative Execution-Driven Discovery vs. Independent Best-of-N Search

**Date:** 2026-10-07  
**Revision:** 4.3 (Final Pre-Implementation Specification — Clean Finite Statistical Architecture)  
**Author / Lead Investigator:** Antigravity Autonomous Research Agent  
**Domain:** Minimum Vertex Graph Coloring  
**Status:** **FINAL PRE-IMPLEMENTATION SPECIFICATION COMPLETE — AWAITING HUMAN APPROVAL BEFORE PILOT**  
**Execution Gate:** **STRICTLY LOCKED (Zero experiments run; no pilot or main trials executed)**  

### Epistemic Taxonomy Applied Throughout Document:
- `[FACT]`: Empirically verified fact from existing code, data, logs, or system state.
- `[INFERENCE]`: Logical deduction or scientific reasoning grounded in established facts.
- `[PROPOSED DESIGN]`: Design specification proposed for Stage 3 implementation.
- `[NOT YET VERIFIED]`: Known unknown, empirical assumption, or pending empirical test.

---

## 1. Core Scientific Question, Hypotheses, and Variable Separation

### 1.1 The Primary Scientific Question
Stage 2 established that execution-based selection from a fixed pool out-selects execution-blind LLM judging ($p = 8.00 \times 10^{-6}$) by catching fatal runtime crashes and constraint violations.

Stage 3 asks a fundamentally different and higher-order question about discovery:
> **"For a fixed candidate-generation budget ($N = 100$), does execution-feedback-driven adaptive search discover better solutions than simply generating the same number of independent candidates and selecting the best one?"**

The core claim under test is strictly:
> **"Does Amaura use a fixed search budget more effectively than non-adaptive Best-of-N search?"**

### 1.2 Unambiguous Distinction Between $N$ and $T$
`[PROPOSED DESIGN]`
- **$N = 100$:** The **candidate-generation budget** (slots) per arm per trial. Every arm receives exactly 100 candidate-generation opportunities in every trial.
- **$T$:** The **number of paired experimental trials** (replications). Each trial is an independent run of the entire 100-candidate search process across Arms A, B, and C.
  - $T_{\text{pilot}} = 3$ paired trials in the pilot.
  - $T_{\text{main}}$ = frozen number of paired trials in the main experiment (target range: 20 to 40, default $T=30$).

### 1.3 Primary Effect Estimand, Hypothesis, and Direction
`[PROPOSED DESIGN]`
In Graph Coloring, the objective is to **minimize** the total chromatic number across benchmark instances (lower is better).

For each experimental trial $t \in \{1, 2, \dots, T\}$ where both Arm A and Arm C produce valid winners, define the paired trial-level difference:
$$\Delta_t = \text{Score}_{C,t} - \text{Score}_{A,t}$$
where $\text{Score}_{C,t}$ and $\text{Score}_{A,t}$ are the aggregate hidden-benchmark chromatic scores of the single selected winners from trial $t$.

- **Primary Effect Estimand:** The **mean trial-level difference** $\mathbb{E}[\Delta]$ on the Dual-Valid Trial Subset.
- **Primary Hypothesis ($\mathcal{H}_1$):**
  > *"Execution-feedback-driven adaptive search produces a statistically significant and practically meaningful lower mean hidden objective than independent Best-of-100 search on dual-valid trials ($\mathbb{E}[\Delta] < 0$)."*
- **Primary Success Criterion:** A successful primary outcome strictly requires meeting **ALL THREE** of the following conditions:
  1. **Dual-Validity Gate:** Both Arm A and Arm C satisfy the $\ge 90\%$ trial-validity gate ($T_{\text{valid}} / T \ge 0.90$).
  2. **Statistical Significance:** The two-sided paired Wilcoxon signed-rank test on the finite numeric differences of the dual-valid trials achieves $p_{\text{corrected}} < 0.05$ after Holm-Bonferroni adjustment across the primary and secondary comparisons.
  3. **Practical Meaningfulness:** The 95% paired bootstrap confidence interval for the mean dual-valid trial difference $\mathbb{E}[\Delta]$ lies **entirely below $-1.0$ color** ($\text{CI}_{\text{upper}} < -1.0$).
- **Methodological Distinction Between Tests:**
  - The paired Wilcoxon signed-rank test evaluates the distribution of finite trial-level signed ranks (stochastic dominance). It does NOT test the mean directly.
  - The 10,000-resample paired bootstrap confidence interval specifically estimates the primary effect estimand, the mean trial-level difference $\mathbb{E}[\Delta]$.
  - The median difference is reported as secondary descriptive information, but is NOT the primary estimand.

### 1.4 Secondary and Tertiary Comparisons
`[PROPOSED DESIGN]`
- **Secondary Comparison ($C \text{ vs } B$):**
  $C \text{ vs } B$ is designed to estimate the incremental value of execution feedback over blind iterative search, while acknowledging that the arms may differ in information structure and decision-making. We do not claim this comparison "conclusively" isolates execution feedback beyond the controlled differences of the preregistered prompts.
- **Tertiary Comparison ($B \text{ vs } A$):**
  $B \text{ vs } A$ tests whether iterative textual reflection without empirical scores provides any advantage or causes drift/degradation relative to independent generation.

### 1.5 Pre-Registered Symmetrical Negative Result Interpretation
`[PROPOSED DESIGN]`
If Arm A equals or outperforms Arm C on the mean difference ($\mathbb{E}[\Delta] \ge 0$) or if the 95% bootstrap CI includes values $\ge -1.0$, this is recorded and reported as a **legitimate negative result**:
> *"For this task and fixed candidate-generation budget of $N=100$, execution-driven adaptation did not outperform independent Best-of-100 search."*

**Governance Rule:** We will NOT modify the search strategy post-hoc, alter prompts, adjust parameters, or rerun the experiment until C wins. A negative outcome is a valid scientific finding.

### 1.6 Narrow Scope & Explicit Non-Claims
- **NO Claim of Global Optimality:** We do not claim the winning algorithm finds the mathematically global minimum chromatic number for all possible graphs.
- **NO Claim of Infinite-Horizon Superiority:** We test performance only within the predefined candidate-generation budget $N = 100$.
- **NO Claim of Universal Algorithm Dominance:** Claims are strictly bounded to the tested problem domain, candidate budget, and benchmark distributions.
- **NO Claim of General AGI:** This tests a specific, bounded algorithmic search mechanism, nothing more.

---

## 2. Statistical Architecture & Zero-Valid Handling

`[PROPOSED DESIGN]`
To eliminate mathematical ambiguity, avoid non-standard rank hacks (such as passing $\pm\infty$ into Wilcoxon), and cleanly separate optimization quality from execution reliability, the statistical evaluation is structured into three clearly separated procedures:
1. **Primary Continuous Analysis (Dual-Valid Trials)**
2. **Binary Reliability Analysis (Failure Rates & Discordance)**
3. **Prespecified Worst-Case Bounded-Imputation Sensitivity Analysis**

```
                                  STAGE 3 STATISTICAL ARCHITECTURE
                                  
   +-----------------------------------------------------------------------------------+
   |                             ALL T PAIRED TRIALS RUN                               |
   |   For each trial t = 1 .. T:                                                      |
   |   Arm A generates 100 cands -> selects dev-best -> hidden evaluation              |
   |   Arm C generates 100 cands -> selects dev-best -> hidden evaluation              |
   +-------------------------------------------+---------------------------------------+
                                               |
                                               v
   +-----------------------------------------------------------------------------------+
   |                               TRIAL OUTCOME AUDIT                                 |
   |   - Count dual-valid trials: T_dual_valid                                         |
   |   - Count A-only failures:   T_A_fail (Arm A produced 0 valid cands)              |
   |   - Count C-only failures:   T_C_fail (Arm C produced 0 valid cands)              |
   |   - Count both-fail trials:  T_both_fail                                          |
   +-------------------+-----------------------+-----------------------+---------------+
                       |                       |                       |
                       v                       v                       v
   +-----------------------+   +-----------------------+   +-----------------------+
   |   1. PRIMARY ANALYSIS  |   | 2. RELIABILITY ANAL.  |   | 3. SENSITIVITY ANAL.  |
   |   (Dual-Valid Trials) |   | (Binary Endpoints)    |   | (Worst-Case Imputed)  |
   |                       |   |                       |   |                       |
   | - Gate: Valid >= 90%  |   | - Failure counts      |   | - Verify S_penalty    |
   | - Finite numeric diffs|   | - McNemar's test      |   | - Impute 19,001       |
   | - Paired Wilcoxon     |   | - P(Fail_C)-P(Fail_A) |   | - All T finite diffs  |
   | - 10,000 bootstrap CI |   | - Flag failure if     |   | - Recompute CI        |
   | - E[Δ] < -1.0 color   |   |   C is less reliable  |   | - Confirm robustness  |
   +-----------------------+   +-----------------------+   +-----------------------+
```

### 2.1 The Slot Invariant & Categorical Failure Logging
- Exactly 100 candidate-generation slots are available per arm per trial.
- Every generated candidate consumes exactly one slot, regardless of whether it is valid, invalid, crashes, times out, duplicates another candidate, or fails AST security.
- There are **NO retries, replacements, bonus candidates, or additional generation slots**.
- The LLM is **never** allowed to decide whether a candidate is valid. Validity is determined exclusively and mechanically by the frozen AST sandbox and evaluator.
- If an arm produces zero valid candidates after all 100 slots, the trial is logged as an explicit categorical failure: `ARM_FAILURE_NO_VALID_CANDIDATE`.
- Zero-valid trials remain in the primary analysis accounting and are **never** silently dropped.

### 2.2 Primary Analysis (Dual-Valid Trial Subset)
`[PROPOSED DESIGN]`
The primary continuous analysis operates strictly on the paired trials where **both Arm A and Arm C produced valid winners** ($T_{\text{dual\_valid}}$):
1. **Pre-Requisite Dual-Validity Gate:**
   - Both Arm A and Arm C must achieve at least a 90% trial validity rate ($T_{\text{valid}} / T \ge 0.90$).
   - If either arm has $< 90\%$ valid trials, the primary continuous comparison is declared **INCONCLUSIVE (RELIABILITY_FAILURE)**. We do not manufacture a numerical win or silently exclude the experiment; failure rates are reported explicitly.
2. **Finite Differences Only:**
   - For every dual-valid trial $t \in \{1, \dots, T_{\text{dual\_valid}}\}$, compute the finite numeric difference:
     $$\Delta_t = \text{Score}_{C,t} - \text{Score}_{A,t}$$
3. **Primary Wilcoxon Signed-Rank Test:**
   - Executed strictly on the finite numeric differences $(\Delta_1, \dots, \Delta_{T_{\text{dual\_valid}}})$.
   - **Crucial Rule:** The Wilcoxon test receives **ONLY finite numeric differences**. No $\pm\infty$ or non-numeric codes are passed into the Wilcoxon function.
4. **Primary Bootstrap Confidence Interval:**
   - 10,000 paired bootstrap resamples of the dual-valid trial differences to compute the 95% CI of the mean difference $\mathbb{E}[\Delta]$.
5. **Reported Quantities:**
   - $T_{\text{dual\_valid}}$ (number of dual-valid trials)
   - $T_{A\text{-fail}}$ (A-only failures)
   - $T_{C\text{-fail}}$ (C-only failures)
   - $T_{\text{both-fail}}$ (both-fail trials)
   - Mean dual-valid difference $\text{Mean}(\Delta)$
   - Median dual-valid difference $\text{Median}(\Delta)$
   - 95% paired bootstrap CI for $\text{Mean}(\Delta)$
   - Two-sided paired Wilcoxon $p$-value (raw and Holm-corrected)

### 2.3 Binary Reliability Analysis (Separate Endpoint)
`[PROPOSED DESIGN]`
Zero-valid-candidate outcomes are treated as a **separate binary reliability endpoint**:
1. **Reported Metrics:**
   - Arm C valid count and invalid count ($T_{C\text{-valid}}, T_{C\text{-fail}}$)
   - Arm A valid count and invalid count ($T_{A\text{-valid}}, T_{A\text{-fail}}$)
   - Paired discordant failure counts ($T_{C\text{-fail}, A\text{-valid}}$ vs $T_{A\text{-fail}, C\text{-valid}}$)
   - Risk difference in failure rates: $\text{RD} = P(\text{Fail}_C) - P(\text{Fail}_A)$ with 95% score CI
   - Exact McNemar's test on paired discordance
2. **Reliability Gate Rule:**
   - A method that obtains a better chromatic score only by frequently producing no valid solution must not be allowed to claim an optimization victory.
   - If Arm C exhibits a statistically significantly worse failure rate than Arm A ($p < 0.05$ on McNemar's test, or Arm C valid rate $< 90\%$), this is formally reported as a **RELIABILITY FAILURE**, and Arm C is disqualified from claiming a primary win.

### 2.4 Prespecified Bounded-Imputation Sensitivity Analysis
`[PROPOSED DESIGN]`
To assess the sensitivity of the results to candidate failures across all $T$ trials:
1. **Mathematical Worst-Case Bound Verification:**
   - On the frozen hidden benchmark of 200 graphs, the maximum possible number of colors any valid coloring can use is $|V|$.
   - The evaluator dynamically verifies the benchmark bound:
     $$S_{\text{penalty}} = \left( \sum_{i=1}^{200} |V_i| \right) + 1 \le 19,001 \text{ colors}$$
   - Any proper coloring strictly uses $\le 19,000$ colors. Hence $S_{\text{penalty}} = 19,001$ is mathematically proven to be strictly worse than every possible valid coloring.
2. **Imputation Procedure:**
   - In the sensitivity analysis across all $T$ trials:
     - If Arm A produced 0 valid candidates in trial $t$, impute $\text{Score}_{A,t} = 19,001$.
     - If Arm C produced 0 valid candidates in trial $t$, impute $\text{Score}_{C,t} = 19,001$.
     - If both produced 0 valid candidates, both are imputed with $19,001$ ($\Delta_t = 0$).
   - This produces exactly $T$ **finite numeric differences**.
3. **Sensitivity Metrics:**
   - Recompute the 95% paired bootstrap CI of the mean difference under worst-case bounded imputation.
   - Recompute the paired Wilcoxon signed-rank test on the $T$ imputed finite differences.
   - This analysis is labeled: *"Sensitivity analysis under worst-case bounded imputation."* It does **NOT** replace the primary dual-valid continuous analysis.
4. **Fragility vs. Robustness Decision Rule:**
   - **ROBUST SUCCESS:** The primary dual-valid analysis succeeds (Wilcoxon $p_{\text{corrected}} < 0.05$, bootstrap $\text{CI}_{\text{upper}} < -1.0$) **AND** the bounded-imputation sensitivity analysis also succeeds (imputed bootstrap $\text{CI}_{\text{upper}} < -1.0$).
   - **FRAGILE SUCCESS:** The primary dual-valid analysis succeeds, but the bounded-imputation sensitivity analysis fails. The result must be reported as **FRAGILE**, and cannot be called a robust Stage 3 success.
   - **NOT SUPPORTED:** Neither succeeds, or Arm A equals/outperforms Arm C.

---

## 3. Search Arms & Selection Mechanisms

```
+----------------------------------------------------------------------------------------------------+
|                                    STAGE 3 SEARCH ARMS ARCHITECTURE                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ ARM A: INDEPENDENT_BEST_OF_100 ]   [ ARM B: BLIND_ITERATIVE ]        [ ARM C: AMAURA ]          |
|  - 100 Independent candidates         - 10 Generations x 10 cands       - 10 Generations x 10 cands|
|  - Zero inter-candidate influence     - Textual context from past gens  - Execution on Dev Set (40)|
|  - All 100 generated first            - ZERO execution scores / feedback- Feedback packet to gen+1 |
|  - Evaluate all 100 on Dev Set (40)   - Evaluated on Dev Set silently   - Lineage & mutation tracked|
|  - Pick Best Valid on Dev             - Blind Selection at Gen 10       - Pick Best Valid on Dev   |
|                 |                                   |                                  |           |
|                 +-----------------------------------+----------------------------------+           |
|                                                     |                                              |
|                                                     v                                              |
|                                     [ TECHNICAL HIDDEN FIREWALL ]                                  |
|                                                     |                                              |
|                                                     v                                              |
|                               [ HIDDEN BENCHMARK EVALUATION (N=200) ]                              |
|                                  Evaluate 1 Selected Winner per Arm                                |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Arm A — Independent Best-of-100 (`A_INDEPENDENT_BEST_OF_100`)
- **Generation:** Generates 100 independent candidates ($C_1, \dots, C_{100}$) using the baseline expert prompt at $\text{temperature} = 0.7$. Candidates have zero knowledge of each other.
- **Evaluation & Selection:** All 100 candidates are evaluated on the 40 development instances post-hoc. The candidate with the lowest dev score among valid candidates is selected:
  $$C_{A,t}^* = \arg\min_{C \in \text{Valid}(A)} \text{Score}_{\text{dev}}(C)$$
- **Zero-Valid:** If no candidate in Arm A is valid, record `Outcome_{A,t} = ARM_FAILURE_NO_VALID_CANDIDATE`.
- **Hidden Evaluation:** If valid, $C_{A,t}^*$ is evaluated on the 200 hidden instances to yield $\text{Score}_{A,t}$.

### 3.2 Arm B — Execution-Blind Iterative Search & Deterministic Selection (`B_BLIND_ITERATIVE`)
- **Generation:** 10 generations $\times$ 10 candidates. Generation 1 generates 10 candidates. Generations 2..10 receive textual code and descriptions of prior candidates, prompting for conceptual refinement, recombination, and algorithmic reasoning.
- **Blinding Rule:** Strictly ZERO execution scores, runtimes, instance numbers, or validity feedback.
- **Deterministic Primary Selection Mechanism:**
  At the conclusion of generation 10, Arm B's primary selected winner is determined via a **deterministic blind-selection call**:
  1. The model receives the complete source code and textual descriptions of the **10 candidates generated in generation 10**.
  2. The model receives a fixed, frozen blind-selection prompt:
     ```text
     Review the following 10 algorithm candidates generated in Generation 10.
     Based purely on your theoretical analysis, algorithmic rigor, and mathematical structure,
     select exactly ONE candidate algorithm to represent your search.
     Output your final selection in the exact format:
     SELECTED_CANDIDATE: Candidate_XX
     ```
  3. The prompt contains **ZERO execution scores, ZERO validity results, ZERO runtimes, ZERO development benchmark metrics, and ZERO hidden information**.
  4. Parsing is deterministic: selects the candidate matching `SELECTED_CANDIDATE: Candidate_XX`. If parsing fails, deterministic fallback selects `Candidate_01` in generation 10.
  5. The selected candidate is evaluated on the development set post-hoc for validity:
     - If valid, it is evaluated on the hidden set to yield $\text{Score}_{B,t}$.
     - If invalid, Arm B's primary selection fails, recorded as `ARM_FAILURE_NO_VALID_CANDIDATE`.
  6. The oracle dev-best candidate in Arm B's pool is recorded as a **secondary diagnostic only**.

### 3.3 Arm C — Amaura Execution-Driven Adaptive Search (`C_AMAURA`)
- **Generation:** 10 generations $\times$ 10 candidates. Generation 1 generates 10 candidates. Generations 2..10 receive the mechanically constrained, purely structured Development Feedback Packet based on development benchmark performance of generation $g-1$.
- **Selection:** The candidate achieving the lowest development score across all 100 candidates is selected:
  $$C_{C,t}^* = \arg\min_{C \in \text{Valid}(C)} \text{Score}_{\text{dev}}(C)$$
- **Zero-Valid:** If no candidate in Arm C is valid, record `Outcome_{C,t} = ARM_FAILURE_NO_VALID_CANDIDATE`.
- **Hidden Evaluation:** If valid, $C_{C,t}^*$ is evaluated once on the 200 hidden instances to yield $\text{Score}_{C,t}$.

---

## 4. Mechanically Constrained Execution Feedback for Arm C

`[PROPOSED DESIGN]`
Arm C's execution feedback channel is **mechanically constrained to structured fields only**.

### 4.1 Exact Structured Schema for Arm C Feedback Packet
The feedback packet exposed to the model for each candidate in generation $g-1$ consists strictly of a JSON array of structured objects conforming to:

```json
[
  {
    "candidate_id": "T01_C_G02_C01",
    "validity": "VALID",
    "development_score": 1218,
    "failure_category": null,
    "runtime_ms": 28.4
  },
  {
    "candidate_id": "T01_C_G02_C04",
    "validity": "INVALID",
    "development_score": null,
    "failure_category": "WRONG_OUTPUT",
    "runtime_ms": 14.1
  },
  {
    "candidate_id": "T01_C_G02_C07",
    "validity": "INVALID",
    "development_score": null,
    "failure_category": "TIMEOUT",
    "runtime_ms": 5002.3
  }
]
```

### 4.2 Strict Prohibition of Free-Form Diagnostics
- **NO Evaluator-Written Explanations:** The evaluator produces **zero natural-language explanations, zero textual summaries, and zero aggregate prose diagnostics**.
- **Fixed Enum Only:** `failure_category` is strictly drawn from: `INVALID`, `TIMEOUT`, `CRASH`, `WRONG_OUTPUT`, `SLOW`, `NO_IMPROVEMENT`, `REGRESSION`, `DUPLICATE`, `OTHER`, or `null`.
- **Reasoning Responsibility:** Amaura's model performs all algorithmic synthesis, interpretation, and diagnosis directly over these raw structured records and candidate source code. The evaluator acts as a pure measurement oracle.
- **NO Hidden Data or Evaluator Internals:** The packet contains zero hidden data, zero instance details, and zero evaluator source code.

---

## 5. Candidate Budget ($N$) vs. Experimental Trials ($T$)

`[PROPOSED DESIGN]`
We maintain absolute accounting transparency across generation budgets and experimental replications:

| Metric | Definition | Arm A (`BEST_OF_100`) | Arm B (`BLIND_ITER`) | Arm C (`AMAURA`) | Strict Parity Rule |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Candidate Budget ($N$)** | LLM solution generation opportunities per trial | **100** | **100** | **100** | **MATCHED ($N=100$)** |
| **Generations** | Generational batches | 1 (or $10 \times 10$) | 10 | 10 | 100 total slots |
| **Slot Consumption** | Crashes, timeouts, syntax errors | Consumes 1 slot | Consumes 1 slot | Consumes 1 slot | **Zero retries / replacements** |
| **Dev Execution Budget** | Candidate runs $\times$ Dev instances (40) | Up to 4,000 | Up to 4,000 | Up to 4,000 | 100 cands $\times$ 40 graphs |
| **Hidden Execution Budget** | Winner run $\times$ Hidden instances (200) | 200 runs | 200 runs | 200 runs | 1 winner $\times$ 200 graphs |
| **Experimental Trials ($T$)** | Replications of entire search process | $T$ | $T$ | $T$ | **Paired across arms** |

### 5.1 Pre-Registered Rule for Freezing Candidate Budget ($N$)
- **Default Budget:** $N = 100$ candidate-generation slots.
- **Modification Rule:** $N = 100$ remains the main experiment budget **unless** one of four objective pilot failure criteria is met:
  1. *Severe generation failure rate:* $> 40\%$ of slots produce unparseable or crashing code across all arms.
  2. *Evaluator infeasibility:* Development evaluation time exceeds 5 minutes per trial.
  3. *Inability to obtain score spread:* Coefficient of variation ($CV$) on dev set is $< 0.005$, or relative range is $< 0.01$.
  4. *Benchmark saturation:* $> 90\%$ of valid candidates across all arms achieve the identical minimum score.
- **Non-Contingency Rule:** The decision to change $N$ **must never depend on which arm is winning** (it will not be changed because C plateaus or because C needs more budget).

---

## 6. Search-Efficiency & Paired Candidate-Budget Checkpoints

`[PROPOSED DESIGN]`
While the primary statistical test operates on the final $N=100$ hidden result, we mandate reporting the **best development score found at predefined budget checkpoints**:

### 6.1 Pre-Registered Budget Checkpoints
For every trial, report the best development chromatic score achieved up to checkpoint:
$$k \in \{1, 5, 10, 20, 50, 100\}$$

| Candidate Budget Checkpoint ($k$) | Arm A Best-of-$k$ (Retrospective) | Arm B Best-so-far ($k$) | Arm C Best-so-far ($k$) |
| :---: | :---: | :---: | :---: |
| **$k = 1$** | $\text{Score}(C_1)$ | $\text{Score}(B_1)$ | $\text{Score}(C_1)$ |
| **$k = 5$** | $\min(C_1 \dots C_5)$ | Best in Gen 1 (first 5) | Best in Gen 1 (first 5) |
| **$k = 10$** | $\min(C_1 \dots C_{10})$ | Best after Gen 1 | Best after Gen 1 |
| **$k = 20$** | $\min(C_1 \dots C_{20})$ | Best after Gen 2 | Best after Gen 2 |
| **$k = 50$** | $\min(C_1 \dots C_{50})$ | Best after Gen 5 | Best after Gen 5 |
| **$k = 100$** | $\min(C_1 \dots C_{100})$ | Best after Gen 10 | Best after Gen 10 |

### 6.2 Strict Nature of Arm A's Best-So-Far Curve
- For Arm A, candidates $C_1, \dots, C_{100}$ are generated independently.
- The prefix curve $\min_{i=1 \dots k} \text{Score}(C_i)$ is calculated purely post-hoc.
- **Explicit Protocol Statement:**
  > *"Arm A's best-so-far curve is retrospective and descriptive; it does not represent adaptive behavior."*
- Arm A never receives these scores during generation.

---

## 7. Pilot Study Protocol & Power-Planning Procedure

### 7.1 Pilot Study Structure ($T_{\text{pilot}} = 3$)
`[PROPOSED DESIGN]`
The pilot study consists of **$T_{\text{pilot}} = 3$ paired trials (9 trial runs total, 900 candidate-generation calls)**.

The pilot will empirically answer:
1. **Feasibility:** Does the execution pipeline complete reliably without crashing or timing out?
2. **Spread & Difficulty:** Do development instances produce meaningful score spread ($CV \ge 0.005$)?
3. **Baseline Competitiveness:** How competitive is `A_INDEPENDENT_BEST_OF_100`?
4. **Saturation Check:** Is the benchmark non-saturated ($<90\%$ identical scores)?
5. **Zero-Valid Failure Frequency:** Does any arm suffer zero-valid candidate rates approaching the failure threshold?
6. **Checkpoints:** Are the budget checkpoints ($k = 1, 5, 10, 20, 50, 100$) clearly measurable?
7. **Blinding & Firewall:** Does the technical hidden firewall successfully block hidden dataset access?

### 7.2 Pilot Power-Planning Rule for $T_{\text{main}}$
`[PROPOSED DESIGN]`
The pilot provides an initial empirical variance estimate $s_{\Delta}$ of the paired trial-level differences $\Delta_t = \text{Score}_{C,t} - \text{Score}_{A,t}$.

The planned number of paired trials $T_{\text{planned}}$ is calculated as a **planning estimate**:
$$T_{\text{planned}} = \left\lceil \frac{7.849 \cdot s_{\Delta}^2}{\delta_{\text{practical}}^2} \right\rceil$$
where:
- $s_{\Delta}$ = standard deviation of dual-valid trial differences from the pilot.
- $\delta_{\text{practical}} = 1.0$ color = preregistered practical improvement margin.
- $7.849 = (z_{0.975} + z_{0.80})^2 = (1.960 + 0.842)^2$, representing nominal 80% power at $\alpha = 0.05$.

### 7.3 Explicit Governance Disclaimers on Power Planning
`[INFERENCE]`
- **Noisy Variance Warning:** 3 pilot trials provide a small, noisy estimate of $s_{\Delta}$. Therefore, $T_{\text{planned}}$ is strictly a **planning estimate**, NOT a mathematical guarantee of achieving exactly 80% power.
- **Bound Enforcement:** We enforce pre-registered bounds:
  $$T_{\min} = 20 \le T_{\text{main}} \le T_{\max} = 40, \quad \text{default target } T_{\text{main}} = 30$$
  If $T_{\text{planned}} < 20$, set $T_{\text{main}} = 20$. If $T_{\text{planned}} > 40$, set $T_{\text{main}} = 40$.
- **Freeze Before Main Execution:** $T_{\text{main}}$ is frozen in `02_pilot_report.md` before main execution begins.
- **No Optional Stopping:** Do not recompute $T_{\text{main}}$ after observing main results. Do not add trials because C is losing; do not truncate trials because C is winning.

---

## 8. Compute, Token, Cost, and Runtime Estimates

`[FACT]` Model: `nvidia/nvidia/nemotron-3-super-120b-a12b` via local OmniRoute proxy (`http://127.0.0.1:20128/v1/chat/completions`).  
`[PROPOSED DESIGN]` Token pricing: \$3.00 / M input tokens, \$15.00 / M output tokens.

### 8.1 Pilot Study Cost Estimate (CLEARLY LABELED AS AN ESTIMATE)
> **ESTIMATED PILOT PARAMETERS ($T_{\text{pilot}} = 3$):**
> - Trials: 3 trials $\times$ 3 arms = **9 trial runs**
> - Total candidate-generation calls: 9 trial runs $\times$ 100 candidates = **900 calls**
> - Average prompt length: ~1,800 tokens | Average completion length: ~550 tokens
> - Estimated Input Tokens: 900 calls $\times$ 1,800 tokens $\approx$ **1.62 M tokens**
> - Estimated Output Tokens: 900 calls $\times$ 550 tokens $\approx$ **0.50 M tokens**
> - Estimated Input Cost: $1.62 \times \$3.00 = \$4.86$
> - Estimated Output Cost: $0.50 \times \$15.00 = \$7.50$
> - **TOTAL ESTIMATED PILOT COST: ~\$12.36 (ESTIMATE)**
> - Estimated Pilot Runtime: ~9 trial runs $\times$ 56s $\approx$ **8.4 minutes**

### 8.2 Main Experiment Cost Estimate (PRELIMINARY ESTIMATE, $T_{\text{main}} = 30$)
> **ESTIMATED MAIN EXPERIMENT PARAMETERS ($T_{\text{main}} = 30$):**
> - Trials: 30 trials $\times$ 3 arms = **90 trial runs**
> - Total candidate-generation calls: 90 trial runs $\times$ 100 candidates = **9,000 calls**
> - Estimated Input Tokens: ~16.20 M | Estimated Output Tokens: ~4.95 M
> - **TOTAL ESTIMATED MAIN COST: ~\$122.85 (ESTIMATE)**
> - Estimated Main Runtime: ~90 trial runs $\times$ 56s $\approx$ **84 minutes** (1.4 hours)

---

## 9. Implementation Readiness Gate

`[FACT]` All final amendments and statistical clean-ups have been integrated:
- [x] 1. Primary continuous analysis defined on finite differences of dual-valid trials ($T_{\text{dual\_valid}}$), with $\ge 90\%$ validity gate.
- [x] 2. Wilcoxon signed-rank test receives strictly finite numeric differences (zero $\pm\infty$ values).
- [x] 3. Binary reliability analysis separated cleanly as its own endpoint (McNemar's test, discordant counts).
- [x] 4. Bounded-imputation sensitivity analysis prespecified using verified $S_{\text{penalty}} = 19,001$ colors across all $T$ trials.
- [x] 5. Fragile vs. robust decision rules codified.
- [x] 6. Arm B deterministic blind selection and Arm C 5-field structured JSON feedback frozen.
- [x] 7. Zero experiments run; execution remains strictly locked.

**STATUS: REVISION 4.3 IS THE FINAL PRE-IMPLEMENTATION SPECIFICATION.**
