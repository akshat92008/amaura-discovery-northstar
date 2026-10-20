# AMAURA LABS — LIVE LLM SEARCH STRATEGY PILOT REPORT
## Empirical Evaluation of Five Search Strategies Using Nemotron-3 Super on Online 1D Bin Packing

**Date:** October 18, 2026  
**Author:** Principal Research Scientist, Experimental Statistician & Engineering Lead, Amaura Labs  
**Subject:** Empirical evaluation of live-LLM candidate heuristic generation across five search arms under strict proposal accounting  
**Target Architecture:** `nvidia/nvidia/nemotron-3-super-120b-a12b` via OmniRoute local proxy  
**Experimental Status:** Completed (160/160 measured live LLM queries, 5/5 trials complete, 0 simulated substitutions)  
**Dataset Quarantines:** Training (20 streams, `train.json`), Sealed Benchmark Test (100 streams, `test.json`), Exploratory Pilot Validation (100 streams, `pilot_validation.json`, SHA-256: `e7e870c009511d1ad7092ee8e48dc20477f598eac89420e85f181a4c7bdbd6ea`)

---

## 1. Executive Summary & Verdict

### 1.1 The Core Scientific Question
Does feedback from evaluated algorithmic candidates (single-lineage iterative refinement, population-based evolution, multi-island diversity niching, or instance-level diagnostic evidence) allow an LLM-driven discovery system to discover superior heuristic policies compared to independent candidate sampling when evaluated under strictly matched candidate proposal budgets?

### 1.2 The Empirical Verdict: Decisive Null Result
Across **160 live queries** to the frontier reasoning model `nvidia/nemotron-3-super-120b-a12b`, **not a single model-generated heuristic policy outperformed the canonical Best-Fit seed** on online one-dimensional bin packing.

| Search Arm | Live Queries | Valid Proposals | Unique Codes | Train Score ($\rho$) | Relative Gap vs Best-Fit | Test Score ($\rho$) | Pilot Val Score ($\rho$) | Beats Best-Fit? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Arm A (Independent Best-of-N)** | 32 | 22 (68.8%) | 32 (100%) | 0.031433 | **+0.00%** | 0.032435 | 0.031923 | **NO** |
| **Arm B (Iterative Refinement)** | 32 | 27 (84.4%) | 32 (100%) | 0.031433 | **+0.00%** | 0.032435 | 0.031923 | **NO** |
| **Arm C (Standard Evolution)** | 32 | 30 (93.8%) | 32 (100%) | 0.031433 | **+0.00%** | 0.032435 | 0.031923 | **NO** |
| **Arm D (Multi-Island Diversity)** | 32 | 27 (84.4%) | 32 (100%) | 0.031433 | **+0.00%** | 0.032435 | 0.031923 | **NO** |
| **Arm E (Evidence-Guided Search)** | 32 | 32 (100.0%) | 31 (96.9%) | 0.031433 | **+0.00%** | 0.032435 | 0.031923 | **NO** |

**Key Findings:**
1. **Zero Measured Advantage for Feedback:** The paired quality difference between all four feedback-driven search arms (Arms B, C, D, and E) and independent Best-of-N (Arm A) is exactly $\Delta = +0.00\%$ on training, sealed test, and pilot validation sets. The best solution discovered in every single arm was the starting Best-Fit baseline seed.
2. **The "Monotonic Equivalence" Trap:** 116 out of 138 valid candidate proposals (84.1%) produced packing performances mathematically identical to Best-Fit ($\rho = 0.031433$). The model repeatedly generated complex mathematical formulations—including quadratic penalties $\left(-(C-w)^2\right)$, exponential decay $\left(e^{-(C-w)}\right)$, and ratio power laws—failing to recognize that all strictly monotonic transformations of leftover capacity yield identical pairwise argmax rankings across open bins.
3. **Validity Gradient Driven by Prompt Grounding:** Candidate code validity exhibited a steep, monotonic increase with prompt context structure: Arm A (68.8%) $\rightarrow$ Arm B (84.4%) $\rightarrow$ Arm D (84.4%) $\rightarrow$ Arm C (93.8%) $\rightarrow$ Arm E (100.0%). Feeding champion code and diagnostic feedback sharply eliminated syntax errors and structural hallucinations.
4. **Computational Cost:** The 160 sequential queries consumed 582,492 tokens and required 1.41 hours of wall-clock time (mean latency: 29.87s/query).

---

## 2. Experimental Design & Audit Trail

### 2.1 Environmental & Protocol Parameters
- **Problem Domain:** Online 1D Bin Packing (Bin Capacity $C = 100.0$, item weights $w \in [5.0, 95.0]$).
- **Objective:** Minimize normalized excess ratio $\rho = \frac{\text{bins\_used} - L_1}{L_1}$, where $L_1 = \lceil \frac{\sum w}{C} \rceil$.
- **Model Endpoint:** `nvidia/nvidia/nemotron-3-super-120b-a12b` via local OmniRoute proxy (`http://127.0.0.1:20128/v1/chat/completions`).
- **Proposal Allocation:** Exactly 32 live-model proposal slots per arm. Baseline seeds (4 canonical heuristics: Best-Fit, Worst-Fit, First-Fit, Almost-Worst-Fit) were evaluated as initialization baselines and consumed zero live proposal slots.
- **Execution Mode:** Strictly sequential execution (`--workers 1`, single thread) under `caffeinate -dimsu` to prevent system sleep or concurrent proxy contention.
- **Quarantined Evaluation Firewall:**
  - Candidate selection was performed strictly on 20 training streams (`train.json`, seeds 40001–40020).
  - Generalization was measured after freezing the champion on the sealed benchmark test set (100 streams, `test.json`, seeds 41001–41100).
  - Exploratory pilot generalization was simultaneously measured on a fresh 100-stream synthetic dataset (`pilot_validation.json`, seeds 80001–80100, SHA-256: `e7e870c009511d1ad7092ee8e48dc20477f598eac89420e85f181a4c7bdbd6ea`).
- **Zero Simulation Substitution Rule:** Verified. All 160 proposals were queried from the live API. No synthetic fallbacks were invoked.

### 2.2 Telemetry Summary
- **Total Measured Model Calls:** 160
- **Total Evaluator Runs:** 185 (4 seeds $\times$ 5 arms + 160 live proposals + 5 sealed evaluations)
- **Mean API Latency:** 29.87 seconds (Min: 9.37s, Max: 109.14s)
- **Mean Prompt Tokens:** 2,405.0 tokens
- **Mean Completion Tokens:** 1,235.6 tokens (Mean Reasoning Tokens: 1,029.2 tokens)
- **Total Tokens Consumed:** 582,492 tokens

---

## 3. Candidate Validity & Structural Adherence

### 3.1 Overall & Trajectory Validity Breakdown
A proposal was classified as **valid** if and only if:
1. It contained a valid Python code block defining `def priority(item, remaining_capacity, bin_capacity) -> float`.
2. It passed the strict AST security sandbox (no unauthorized imports, no OS/filesystem access, `math` only).
3. It executed across all 20 training streams (20,000 total item placements) without raising runtime exceptions (e.g., `ZeroDivisionError`, `TypeError`, `OverflowError`).

| Search Arm | Total Slots | Valid Slots | Overall Validity | Q1 (P0–P7) | Q2 (P8–P15) | Q3 (P16–P23) | Q4 (P24–P31) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Arm A (Best-of-N)** | 32 | 22 | **68.8%** | 62.5% | 75.0% | 75.0% | 62.5% |
| **Arm B (Refinement)** | 32 | 27 | **84.4%** | 100.0% | 62.5% | 100.0% | 75.0% |
| **Arm C (Evolution)** | 32 | 30 | **93.8%** | 75.0% | 100.0% | 100.0% | 100.0% |
| **Arm D (Multi-Island)**| 32 | 27 | **84.4%** | 50.0% | 100.0% | 87.5% | 100.0% |
| **Arm E (Evidence)** | 32 | 32 | **100.0%** | 100.0% | 100.0% | 100.0% | 100.0% |

### 3.2 Failure Mode Taxonomy
Across the 22 invalid candidate proposals (13.8% failure rate across the grid):
- **Syntax & Markdown Framing Errors (19 cases, 86.4% of failures):** The model emitted an extensive chain-of-thought essay that either exhausted the `max_tokens` token budget or concluded without closing the ` ```python ` markdown code block. This occurred primarily in Arm A (9 cases) and early generation slots of Arm B and Arm D where no reference code template was provided in the immediate context.
- **Runtime Exceptions (3 cases, 13.6% of failures):** 
  - 1 in Arm A (`RuntimeError` from floating-point comparison failure on empty bin handling).
  - 2 in Arm D (`RuntimeError` from division-by-zero during un-normalized behavioral correlation distance computation in an island candidate).

### 3.3 The Context Grounding Effect
As shown in the quarterly validity breakdown:
- Arm A remained noisy throughout the search ($\sim 62.5\% - 75.0\%$) because every query was zero-shot with no example code.
- Arm C, Arm D, and Arm E rapidly converged to **100% validity** after the initialization phase. Providing one or two valid code blocks in the context (either as parents, champions, or evidence targets) provides an implicit syntactic scaffold that eliminates syntax errors.

---

## 4. Search Dynamics & The Monotonic Equivalence Phenomenon

### 4.1 Search Dynamics Table (Best-so-Far Objective $\rho$)
The table below logs the best-so-far excess ratio on the training set at key proposal milestones:

| Proposal Slot | Arm A (Control) | Arm B (Refinement) | Arm C (Evolution) | Arm D (Multi-Island) | Arm E (Evidence) | Best-Fit Baseline |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Seed 0 (Baseline)** | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 |
| **P01** | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 |
| **P08 (End Q1)** | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 |
| **P16 (Midpoint)**| 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 |
| **P24 (End Q3)** | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 |
| **P32 (Final)** | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 | 0.031433 |

**Did any arm improve upon Best-Fit?** No. Across 160 live candidate proposals, the best-so-far curve remained completely horizontal at $\rho = 0.031433$.

### 4.2 Candidate Performance Distribution
Examining the raw scores of all 138 valid candidate proposals reveals the underlying distribution:

| Search Arm | Valid Proposals | Exactly Matching Best-Fit | Worse than Best-Fit | Better than Best-Fit | Worst Discovered $\rho$ | Maximum Degradation |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Arm A** | 22 | 13 (59.1%) | 9 (40.9%) | **0 (0.0%)** | 0.137627 | +337.84% |
| **Arm B** | 27 | 23 (85.2%) | 4 (14.8%) | **0 (0.0%)** | 0.137627 | +337.84% |
| **Arm C** | 30 | 28 (93.3%) | 2 (6.7%) | **0 (0.0%)** | 0.102217 | +225.19% |
| **Arm D** | 27 | 20 (74.1%) | 7 (25.9%) | **0 (0.0%)** | 0.127081 | +304.29% |
| **Arm E** | 32 | 32 (100.0%) | 0 (0.0%) | **0 (0.0%)** | 0.031433 | +0.00% |

### 4.3 Mathematical Analysis: The Monotonic Equivalence Trap
Why did 84.1% of all valid proposals—and **100% of Arm E proposals**—produce the exact same score down to 6 decimal places ($\rho = 0.031433$)?

In online 1D bin packing, an arriving item $w$ must be placed into the feasible open bin $b \in \mathcal{B}_{\text{feasible}}$ that maximizes the priority function:
$$b^* = \arg\max_{b \in \mathcal{B}_{\text{feasible}}} \text{priority}(w, R_b, C)$$
where $R_b$ is the remaining capacity of bin $b$, and $C$ is the total bin capacity.

Standard Best-Fit selects the bin that minimizes the leftover space after placement:
$$b^*_{\text{BF}} = \arg\min_{b \in \mathcal{B}_{\text{feasible}}} (R_b - w) = \arg\max_{b \in \mathcal{B}_{\text{feasible}}} -(R_b - w)$$

Let $x_b = R_b - w \ge 0$ denote the leftover space in bin $b$. Any priority function $f(x_b)$ that is a **strictly monotonically decreasing function of $x_b$** preserves the pairwise order of all bins:
$$\forall b_1, b_2 \in \mathcal{B}_{\text{feasible}}: \quad x_{b_1} < x_{b_2} \iff f(x_{b_1}) > f(x_{b_2})$$
Therefore:
$$\arg\max_{b \in \mathcal{B}_{\text{feasible}}} f(x_b) \equiv \arg\min_{b \in \mathcal{B}_{\text{feasible}}} x_b = b^*_{\text{BF}}$$

Across the 160 queries, Nemotron-3 Super repeatedly proposed functions that it claimed were "fundamentally different" or "convex non-linear improvements":
1. **Quadratic leftover penalty:** $f(x) = -x^2$. Since $x \ge 0$, $\frac{d}{dx}(-x^2) = -2x \le 0$. Strictly monotonic $\implies$ **Identical to Best-Fit**.
2. **Cubic leftover penalty:** $f(x) = -x^3$. $\frac{d}{dx}(-x^3) = -3x^2 \le 0$. Strictly monotonic $\implies$ **Identical to Best-Fit**.
3. **Exponential leftover decay:** $f(x) = e^{-x/C}$. $\frac{d}{dx}(e^{-x/C}) = -\frac{1}{C}e^{-x/C} < 0$. Strictly monotonic $\implies$ **Identical to Best-Fit**.
4. **Normalized fill ratio:** $f(x) = \frac{w}{R_b} = \frac{w}{w + x}$. For fixed $w > 0$, $\frac{d}{dx}(\frac{w}{w+x}) = -\frac{w}{(w+x)^2} < 0$. Strictly monotonic $\implies$ **Identical to Best-Fit**.

The LLM repeatedly hallucinated that changing the numerical gradient or curvature of the penalty would "punish large gaps more severely," failing to realize that `argmax` is an ordinal operator invariant under monotonic scaling.

### 4.4 Why Non-Monotonic Variations Failed
When candidates attempted genuinely non-monotonic policies (e.g., thresholding based on bin fullness or adding an item-size bonus):
```python
# Discovered in Arm A (Proposal 12, Score: 0.137627, +337.84% worse)
def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    waste = remaining_capacity - item
    if waste < 0.1 * bin_capacity:
        return 100.0 - waste
    return waste # Reverts to Worst-Fit for larger remainders!
```
These non-monotonic heuristics broke the Best-Fit guarantee by steering items into less full bins (Worst-Fit behavior) or refusing to place items into near-empty bins, causing severe capacity fragmentation and increasing bin count by over $300\%$.

---

## 5. Qualitative Code Review & Snippet Analysis

### 5.1 Arm A — Independent Best-of-N (Control)
- **Early Candidate (`arm_a_t0_p2`, Score: 0.031433):**
  ```python
  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      """Prioritize tighter fits by penalizing leftover capacity."""
      leftover = remaining_capacity - item
      return -leftover
  ```
  *Analysis:* Exact linear Best-Fit. Clean, concise, but completely unoriginal.

- **Late Candidate (`arm_a_t0_p28`, Score: 0.031433):**
  ```python
  import math

  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      leftover = remaining_capacity - item
      if leftover < 0:
          return -math.inf
      return -(leftover * leftover)
  ```
  *Analysis:* Quadratic Best-Fit. Re-derived independently. Demonstrates prompt adherence and mathematical validity, but zero algorithmic divergence from Best-Fit.

### 5.2 Arm B — Iterative Refinement
- **Early Candidate (`arm_b_t0_p0`, Score: 0.031433):**
  ```python
  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      # Refinement: add quadratic penalty to amplify preference for small leftover space
      leftover = remaining_capacity - item
      return -(leftover ** 2)
  ```
  *Analysis:* Direct mutation of Champion's linear penalty into a quadratic penalty. Identical decisions.

- **Late Candidate (`arm_b_t0_p29`, Score: 0.031433):**
  ```python
  import math

  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      leftover = remaining_capacity - item
      if leftover < 0:
          return -math.inf
      # Refined exponential formulation
      return math.exp(-leftover / bin_capacity)
  ```
  *Analysis:* Shift from quadratic to exponential decay. Adheres strictly to the champion code structure, but remains trapped in the monotonic equivalence orbit.

### 5.3 Arm C — Standard Evolution
- **Early Candidate (`arm_c_t0_p2_init`, Score: 0.031433):**
  ```python
  import math

  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      eps = 1e-12
      if item > remaining_capacity + eps:
          return -float('inf')
      fill = item / remaining_capacity
      leftover = remaining_capacity - item
      leftover_ratio = leftover / bin_capacity if bin_capacity > eps else 0.0
      return fill * math.exp(-leftover_ratio * leftover_ratio)
  ```
  *Analysis:* Sophisticated blending of fill ratio and Gaussian penalty. Highly articulate docstrings and floating-point safeguards (`eps`), yet strictly rank-equivalent to Best-Fit.

- **Late Candidate (`arm_c_t0_p28`, Score: 0.031433):**
  ```python
  import math

  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      eps = 1e-12
      if item > remaining_capacity + eps:
          return -math.inf
      fill = item / remaining_capacity
      leftover_ratio = (remaining_capacity - item) / bin_capacity
      alpha = 0.6
      combined_penalty = alpha * math.exp(-leftover_ratio) + (1.0 - alpha) * (1.0 - leftover_ratio)
      return fill * combined_penalty
  ```
  *Analysis:* Recombinant offspring combining exponential and linear penalties from two selected parents. Demonstrates clear genetic inheritance of parental traits, but the underlying decision boundary is unaffected.

### 5.4 Arm D — Multi-Island Evolution
- **Early Candidate (`arm_d_t0_p2_isl1_init`, Score: 0.031433):**
  ```python
  import math

  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      if remaining_capacity < item - 1e-12:
          return -math.inf
      return (item * (bin_capacity - remaining_capacity)) / (remaining_capacity * bin_capacity)
  ```
  *Analysis:* Ratio combining fill snugness with current bin fullness. Matches Best-Fit ordering across all test streams.

- **Late Candidate (`arm_d_t0_p28_isl2`, Score: 0.031433):**
  ```python
  import math

  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      if item > remaining_capacity:
          return -1e9
      waste = remaining_capacity - item
      return -(waste * waste) / bin_capacity + math.log(item + 1)
  ```
  *Analysis:* Generated on Island 2 (worst-case mitigation). Adds `math.log(item + 1)` which is independent of bin choice (constant shift for a given item), therefore leaving the argmax over bins completely unchanged!

### 5.5 Arm E — Evidence-Guided Search
- **Early Candidate (`arm_e_t0_p1`, Score: 0.031433):**
  - *Hypothesis:* "The current Best-Fit heuristic penalizes leftover space linearly... By applying a convex (quadratic) penalty, we strongly favor bins that leave minimal waste, tightening the selection threshold."
  ```python
  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      leftover = remaining_capacity - item
      return -(leftover * leftover)
  ```

- **Late Candidate (`arm_e_t0_p28`, Score: 0.031433):**
  - *Hypothesis:* "The evaluator evidence shows underfilled bins when large remainders are left... Applying an amplified penalty on leftover space forces immediate waste reduction."
  ```python
  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      leftover = remaining_capacity - item
      if leftover < 0:
          return -float('inf')
      return -(leftover * leftover)
  ```
  *Analysis:* In all 32 proposals, Arm E followed the evaluator's diagnostic directive faithfully in natural language, but every single hypothesis implemented an order-preserving monotonic variant.

---

## 6. Detailed Comparison of Search Mechanisms

| Criterion | Arm A (Best-of-N) | Arm B (Refinement) | Arm C (Evolution) | Arm D (Multi-Island) | Arm E (Evidence) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Feedback Mechanism** | None (Independent) | Single champion code | Population tournament | 3 islands + migration | Instance diagnostics + hypothesis |
| **Validity Rate** | 68.8% | 84.4% | 93.8% | 84.4% | **100.0%** |
| **Syntactic Stability** | Low (9 syntax errors) | Medium (5 syntax errors) | High (2 syntax errors) | Medium (3 syntax errors) | **Flawless (0 errors)** |
| **Exploration Breadth** | High (random jumps) | Narrow (local drift) | Medium (recombination) | Highest (niching) | Focused (hypothesis-bound) |
| **Unique Code Count** | 32 / 32 | 32 / 32 | 32 / 32 | 32 / 32 | 31 / 32 |
| **Best Discovered Gap** | +0.00% | +0.00% | +0.00% | +0.00% | +0.00% |
| **Worst Discovered Gap**| +337.84% | +337.84% | +225.19% | +304.29% | **+0.00%** |
| **Beats Best-Fit Seed?**| **NO** | **NO** | **NO** | **NO** | **NO** |

### Key Mechanistic Insights:
1. **Iterative Refinement (Arm B vs. Arm A):** Arm B did not produce higher-quality algorithms than Arm A. It merely constrained variance: the proportion of candidates matching Best-Fit rose from 59.1% (Arm A) to 85.2% (Arm B) because the prompt anchored the model to the champion.
2. **Evolutionary Recombination (Arm C):** Arm C demonstrated genuine syntactic crossover (e.g., blending exponential and linear penalties from two distinct parents), but this syntactic recombination did not generate functional algorithmic innovation.
3. **Multi-Island Niching (Arm D):** Multi-island structuring successfully prevented early population convergence—islands explored distinct mathematical families (rational functions on Island 0, power laws on Island 1, logarithmic offsets on Island 2)—but none of these niches yielded superior packing.
4. **Diagnostic Evidence (Arm E):** Evidence-guided search achieved **100% validity and 0% degradation**, acting as an extraordinarily strong conservative regularizer. However, the model lacked the domain reasoning required to translate "tighten threshold" into a valid non-monotonic policy (such as lookahead or reservation buffers), defaulting instead to inert algebraic transformations.

---

## 7. Statistical Power & Methodological Learnings

### 7.1 Effect Size & Inferential Statistics
Under the paired evaluation protocol against Arm A:
- **Mean Paired Difference ($\Delta$):** $0.000000$ across all four comparison arms.
- **Median Paired Difference:** $0.000000$.
- **Sample Variance:** $s^2 = 0.000000$.
- **p-value (Two-sided Wilcoxon):** $p = 1.0000$ (Holm-Bonferroni adjusted $p = 1.0000$).

### 7.2 Power Analysis Update
In classical power analysis, sample size requirements are governed by Cohen's $d = \frac{\mu_1 - \mu_2}{\sigma}$.
When the true effect size between search mechanisms is zero ($\mu_1 - \mu_2 = 0$), no increase in sample size $N$ will achieve statistical significance. 

Running 100 or 500 trials of live-model querying under this formulation will simply measure $\Delta = 0.00\%$ with tighter confidence intervals around zero, at a financial cost of tens of thousands of dollars and hundreds of GPU hours.

### 7.3 Why the Simulated Mutator Produced Differences While the Live LLM Did Not
In our prior 225-trial benchmark with `SimulatedMutator`:
- `SimulatedMutator` injected synthetic Gaussian perturbations directly into numerical thresholds ($\pm \mathcal{N}(0, \sigma^2)$) and selected from a curated library of structurally distinct subroutines.
- In contrast, the **live frontier LLM** reasons in natural language and algebra. When asked to "improve" an existing optimal greedy heuristic, it instinctively reaches for continuous mathematical adjustments (exponents, coefficients, logs) that have **zero impact on discrete argmax selection**.

---

## 8. Definitive Decision Recommendations

### 8.1 Proceed with Full Live-LLM Benchmark on Online Bin Packing?
**RECOMMENDATION: DO NOT PROCEED.**

Executing a full 225-trial confirmatory benchmark using live Nemotron-3 Super on online 1D bin packing is **scientifically unjustified and computationally wasteful**:
- Expected live queries: $225 \times 32 = 7,200$ live model calls.
- Estimated compute time: $\sim 60$ hours.
- Expected outcome: A 100% reproducible null result confirming that frontier LLMs cannot discover an online bin packing heuristic that outperforms Best-Fit without broader state representations.

### 8.2 What Technology Must Amaura Labs Build Instead?
If Amaura Labs wishes to build an effective AI discovery engine for combinatorial algorithms, the bottleneck is not the search topology (islands vs. single lineage vs. MCTS). The bottleneck is **the heuristic interface and the action space**:

1. **Expand Heuristic Expressivity Beyond Stateless Priority Functions:**
   - In online 1D bin packing, Best-Fit is proven to achieve an asymptotic competitive ratio of $1.7$. It is known mathematically that no online algorithm can achieve a competitive ratio better than $1.54037$.
   - A stateless priority function `priority(item, remaining_capacity, bin_capacity)` cannot maintain history, estimate future item distributions, or reserve bins for anticipated item sizes.
   - **Architectural Fix:** Upgrade the domain interface to provide stateful or windowed context (e.g., `priority(item, open_bins, stream_history)`), allowing the LLM to implement dynamic thresholding and distribution-aware bin reservation.
2. **Implement Semantic Equivalence Filtering (AST SymPy / Decision Invariance):**
   - The search engine must detect that $-(R - w)^2$, $e^{-(R-w)}$, and $-(R-w)$ produce identical permutations on the open bins before spending evaluation compute.
   - If a candidate's per-instance decision vector is identical to an existing candidate, it should be pruned immediately without entering the evaluation pool.
3. **Explicit Anti-Monotonic Prompt Directives:**
   - Evaluator diagnostics must explicitly instruct the LLM:
     *"Note: Applying strictly monotonic transformations (e.g. squaring or exponentiating leftover space) does not change argmax selection. Your heuristic MUST implement non-monotonic decision rules or conditional branching."*
4. **Prioritize Discrete Graph and Permutation Domains:**
   - Graph Coloring and PFSP possess vastly more complex, rugged combinatorial fitness landscapes where heuristics do not collapse into trivial single-variable monotonic ordering. Future live-LLM pilots should prioritize Graph Coloring and PFSP where structural algorithmic diversity is genuinely possible.

---

## 9. Artifact & Repository Verification

All artifacts, trial logs, and code updates are committed to branch `search-benchmark-v1`:
- **Results Directory:** [`benchmark_v1/results/live_llm_binpacking_pilot_20261018/`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/results/live_llm_binpacking_pilot_20261018/)
- **Trial Records:**
  - `trial_0001_bin_packing_arm_a_best_of_n_b32_w1_live_llm.json`
  - `trial_0002_bin_packing_arm_b_refinement_b32_w1_live_llm.json`
  - `trial_0003_bin_packing_arm_c_evolution_b32_w1_live_llm.json`
  - `trial_0004_bin_packing_arm_d_multi_island_b32_w1_live_llm.json`
  - `trial_0005_bin_packing_arm_e_evidence_b32_w1_live_llm.json`
- **Telemetry Audit Log:** `llm_queries.jsonl` (160 recorded queries with prompt, response, reasoning trace, tokens, and latency)
- **Pilot Summary Chart:** `plots/live_pilot_summary.png`
- **Exploratory Pilot Validation Dataset:** `benchmark_v1/data/bin_packing/pilot_validation.json` (SHA-256: `e7e870c009511d1ad7092ee8e48dc20477f598eac89420e85f181a4c7bdbd6ea`)
