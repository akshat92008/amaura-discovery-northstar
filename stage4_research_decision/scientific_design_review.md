# Amaura Labs — Stage 4 Scientific Design Review & Adversarial Challenge
**Document ID:** `STAGE4-SCI-REVIEW-001`  
**Date:** October 15, 2026  
**Author:** Lead Research Engineer, Amaura Labs Discovery Engine  
**Target:** Critical Examination of Problem Domain, Comparison Arms, Statistical Power, and Sequential Decision Bias  

---

## 1. Adversarial Critique of the Benchmark Domain: Online 1D Bin Packing

### 1.1 Why Bin Packing Was Selected
Online 1D bin packing is the benchmark of choice in modern algorithmic program discovery (e.g. DeepMind's *FunSearch*, Nature 2024). It offers four rare scientific properties:
1. **Pristine Mathematical Grounding:** Every stream instance has an exact continuous lower bound $L_1 = \lceil \sum w / C \rceil$. Performance is measured not by arbitrary heuristic scoreboards, but by distance from theoretical perfection.
2. **Deterministic, Noise-Free Simulation:** Zero OS jitter, zero GPU timing variance, zero network delay. Evaluating an algorithm twice on the same stream yields the identical bin count bit-for-bit.
3. **Instantaneous Execution:** Simulating 1,000 items takes < 1 ms in Python. This allows evaluating candidates against thousands of items without compute bottlenecks.
4. **Micro-Scale Program Space:** Rather than generating 100 lines of complex graph algorithms (which failed in Stage 3), the search space consists of 10–25 line priority functions (`priority(item, remaining_capacity, bin_capacity)`). This allows foundation models to compose non-linear mathematical combinations where evolutionary mutation has real semantic leverage.

### 1.2 The Adversarial Counter-Arguments & Domain Limitations
1. **The Headroom Problem (Best-Fit Dominance):**
   - The greedy baseline **Best-Fit** is mathematically proven to have an asymptotic competitive ratio of $1.70$.
   - On stationary uniform distributions (e.g. Uniform[10, 80]), Best-Fit is exceptionally close to optimal (often within 2–4% of $L_1$).
   - *Risk:* If the benchmark consists predominantly of uniform streams, Best-Fit leaves virtually zero headroom for improvement. Evolutionary feedback might fail to beat Best-Fit simply because no heuristic can significantly outperform Best-Fit on uniform data!
   - *Defense in Stage 4:* The benchmark specifically incorporates **Weibull** (skewed) and **Zipfian** (heavy-tailed) distributions. In heavy-tailed distributions, Best-Fit makes greedy errors by packing small items into early bins and stranding large items later in the stream. This provides the necessary mathematical headroom for non-linear heuristics to win.
2. **Lack of Immediate Commercial Utility:**
   - Online bin packing is an academic combinatorial benchmark. It is not an enterprise database platform or a cloud scheduling product.
   - *Verdict:* This is an acceptable trade-off for Stage 4. Proving that closed-loop LLM feedback works in principle on a pristine, noise-free domain for $15–$50 is a necessary scientific prerequisite before investing thousands of dollars in noisy, complex commercial domains.

### 1.3 Comparison with Alternative Domains

| Domain | Determinism | Lower Bound | Simulation Speed | Baseline Strength | Confounding Noise |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Online Bin Packing (Stage 4)** | **100% Bit-for-bit** | **Exact ($L_1$)** | **< 1 ms / stream** | **Best-Fit ($1.7\times$)** | **None** |
| **2. CPU Cache Eviction (ARC/LRU)** | High (trace replay) | Empirical (Belady MIN)| ~50 ms / trace | LRU / 2Q | Memory footprint |
| **3. Cloud Task Scheduling** | Low (arrival jitter) | Soft deadline model | ~200 ms / trace | Earliest Deadline First | Stochastic arrivals |
| **4. Compiler Pass Ordering** | Very Poor (OS jitter) | None | ~5,000 ms / compile | Clang `-O3` | Hardware timing noise |

**Conclusion:** Online bin packing remains the single strongest, most falsifiable domain for testing the Discovery Engine thesis under a strict $50 budget.

---

## 2. Examination of the Arm Comparison: Sampling vs. Evolution

### 2.1 The Baseline Seeding Confounder (Identified and Resolved)
- **The Defect:** In early drafts, Arm C initialized its archive with the 4 canonical baseline seeds (Best-Fit, Worst-Fit, First-Fit, Almost-Worst-Fit), while Arm A received zero seeds.
- **Why this was fatal:** If Arm C's LLM generated only broken or mediocre code, Arm C's archive would retain `seed_best_fit`. Arm A, starting with zero seeds, would select the best of its 50 LLM attempts. If the LLM failed to rediscover Best-Fit from scratch, Arm C would win automatically—not because evolution worked, but because it was handed the human baseline on day one!
- **The Fix:** [`stage4/src/search.py:75-81`](./stage4/src/search.py#L75-L81) now initializes **both Arm A and Arm C with the exact same 4 baseline seeds**. Both arms then make $N - 4 = 46$ LLM calls. If evolution fails to improve on the seeds, both arms default to Best-Fit and $\Delta = 0.0$. A win for Arm C now strictly proves that evolutionary mutation of the seeds discovered a superior heuristic than independent sampling from those seeds.

### 2.2 Search Operator Realism
- In Arm C, parent selection uses tournament selection from island subpopulations.
- The prompt incorporates parent code, measured normalized excess ratios, and explicit improvement directives.
- Mutation is guided by the LLM combining mathematical primitives (ratios, threshold penalties, residual capacity weighting).
- Ring migration across 3 islands preserves population diversity and prevents premature convergence.

---

## 3. Statistical Protocol, Experimental Units & Pseudoreplication Prevention

### 3.1 Precise Definition of the Experimental Unit
A critical error in empirical algorithm benchmarking is **pseudoreplication** (Hurlbert, 1984)—treating multiple evaluations of the same candidate algorithm on different test instances as independent samples of the search engine's performance.

In Stage 4:
- **The candidate heuristic** is generated once per trial by a stochastic search trajectory (LLM queries, prompt mutations, selection stochasticity).
- Evaluating that single heuristic across 100 benchmark streams measures that specific heuristic's performance with high precision, but it **does not represent 100 independent discoveries**.
- **The true independent experimental unit is the paired search trial** ($t = 1, \dots, T$), initialized with seed $s_t$, where Arm A (independent sampling) and Arm C (evolutionary search) execute from the identical starting baseline pool.
- The primary paired observation is:
  $$D_t = \bar{\rho}_{\text{hidden}}(\text{Arm C}_t) - \bar{\rho}_{\text{hidden}}(\text{Arm A}_t)$$
- The effective sample size for statistical inference regarding the Discovery Engine's search superiority is $T$ (the number of search trials), **NOT** $T \times 100$ streams.

### 3.2 Error Decomposition Across Streams and Trials
The variance of the paired difference $D_t$ decomposes mathematically as:
$$\text{Var}(D_t) = \text{Var}_{\text{search}}(\mu(C_t) - \mu(A_t)) + \mathbb{E}_{\text{search}}\left[\frac{\sigma^2_{\text{eval}}}{S}\right]$$
Where:
1. **Evaluation Variance ($\sigma^2_{\text{eval}} / S$):** Across $S = 100$ independent streams of 1,000 items each (100,000 total items per candidate), measurement variance is diminished by a factor of $1/100$. This ensures that observed candidate scores are virtually noise-free representations of their true performance.
2. **Search Trajectory Variance ($\sigma^2_{\text{search}}$):** Search is stochastic. Different seeds yield different LLM prompts, mutations, and local optima. This variance is the true source of uncertainty in evaluating the Discovery Engine.

---

## 4. Reproducible Statistical Power & Sensitivity Analysis

### 4.1 Power Simulation Methodology & Explicit Assumptions
To determine whether $T = 10$ paired trials are adequate, we conducted a Monte Carlo power simulation (3,000 synthetic cohorts per configuration) and analytic non-central $t$ power calculation across plausible effect sizes $\delta$ and inter-trial standard deviations $\sigma$.

> [!IMPORTANT]
> **Explicit Labeling of Assumptions:**  
> The standard deviations ($\sigma \in [0.003, 0.008]$) and effect sizes below are **simulated assumptions for power planning**, not observed empirical facts from live execution. Zero paid calls have been made.

### 4.2 Power Analysis Results Table ($\alpha = 0.05$ two-sided)

| Sample Size ($N$) | True Effect ($\delta$) | Assumed $\sigma$ | Cohen's $d$ | Wilcoxon Signed-Rank Power | Paired $t$-Test Power |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **$N = 10$** | **$-0.0050$** | **$0.0030$** | **$1.67$** | **$0.993$** (99.3%) | **$0.996$** (99.6%) |
| **$N = 10$** | **$-0.0050$** | **$0.0050$** | **$1.00$** | **$0.764$** (76.4%) | **$0.803$** (80.3%) |
| **$N = 10$** | **$-0.0050$** | **$0.0080$** | **$0.62$** | **$0.405$** (40.5%) | **$0.423$** (42.3%) |
| **$N = 10$** | **$-0.0080$** | **$0.0050$** | **$1.60$** | **$0.990$** (99.0%) | **$0.994$** (99.4%) |
| **$N = 10$** | **$-0.0080$** | **$0.0080$** | **$1.00$** | **$0.764$** (76.4%) | **$0.803$** (80.3%) |
| **$N = 15$** | **$-0.0050$** | **$0.0050$** | **$1.00$** | **$0.929$** (92.9%) | **$0.949$** (94.9%) |
| **$N = 15$** | **$-0.0050$** | **$0.0080$** | **$0.62$** | **$0.584$** (58.4%) | **$0.615$** (61.5%) |
| **$N = 20$** | **$-0.0050$** | **$0.0050$** | **$1.00$** | **$0.983$** (98.3%) | **$0.989$** (98.9%) |
| **$N = 20$** | **$-0.0050$** | **$0.0080$** | **$0.62$** | **$0.731$** (73.1%) | **$0.755$** (75.5%) |
| **$N = 25$** | **$-0.0050$** | **$0.0080$** | **$0.62$** | **$0.835$** (83.5%) | **$0.850$** (85.0%) |

### 4.3 Key Findings on $T = 10$ Adequacy & Pilot Role
1. **$T = 10$ is an Exploratory Confirmatory Design:**
   - If the true search advantage is large ($d \ge 1.0$, e.g. $\delta = -0.005$ with tight variance $\sigma \le 0.005$), $T = 10$ achieves **$76.4\%–99.3\%$ power**.
   - If inter-trial variance is higher ($\sigma = 0.008$, $d = 0.62$), $T = 10$ achieves only **$40.5\%$ power**, creating a **$59.5\%$ risk of a Type II error (false negative)**.

2. **Severe Uncertainty of Variance Estimates from Three Observations ($df = 2$):**
   - In a 3-trial pilot ($n = 3$), the sample variance $s^2$ follows a scaled chi-squared distribution with only **2 degrees of freedom**:
     $$\frac{(n-1)s^2}{\sigma^2} \sim \chi^2_2$$
   - The 90% confidence interval for the true population standard deviation $\sigma$ is:
     $$\left[\sqrt{\frac{2 s^2}{\chi^2_{2, 0.95}}}, \sqrt{\frac{2 s^2}{\chi^2_{2, 0.05}}}\right] = \left[\sqrt{\frac{2 s^2}{5.991}}, \sqrt{\frac{2 s^2}{0.103}}\right] \approx [0.578 s, 4.410 s]$$
     The upper bound of the 90% confidence interval is **$7.64\times$** its lower bound. At the 95% level, the ratio is **$12.08\times$** ($[0.521 s, 6.299 s]$).
   - **Conclusion:** A 3-trial pilot **cannot definitively establish empirical variance** or mathematically confirm that $T = 10$ has adequate power. Observing a small $s_{\text{dev}}$ in 3 trials does not rule out a much larger true population variance $\sigma$.

3. **Strict Separation of Exploratory Pilot from Confirmatory Inference:**
   - **Pilot as Feasibility Evidence Only:** Phase 1 ($T = 3$, Seeds 40401–40403) is strictly an **engineering and operational feasibility gate**, testing for unhandled LLM crashes, malformed outputs, infinite loops, and baseline tie-breaking pathologies.
   - **Zero Pooling Rule:** The 3 pilot trials **must NEVER be pooled** into the confirmatory cohort. Pooling would introduce severe pilot-selection bias and invalidate nominal Type I error rates.
   - **Fixed Scientific Hypothesis:** The primary effect threshold ($\delta \le -0.005$) and scientific hypothesis remain strictly fixed. Pilot results cannot be used to arbitrarily shift the goalposts or cherry-pick metrics.
   - **How Pilot Informs Planning Responsibly:** If the pilot reveals gross operational failure (e.g. LLM candidates crashing, $0\%$ validity, or zero variance due to baseline masking), the experiment halts before spending money on Phase 2. If it reveals high inter-trial instability, the team can plan an adequately powered sample size ($T \ge 20$) before launching Phase 2, rather than pretending $T = 10$ is guaranteed to suffice.

---

## 5. Mathematical Correction of Gate 2 Success Criteria

### 5.1 The Mathematical Defect in Prior Formulations
Prior protocol drafts required:
$$\text{Wilcoxon } p < 0.05 \quad \text{AND} \quad \text{Bootstrap } \text{CI}_{95\%, \text{upper}} < -0.005$$
This was mathematically incoherent. If the true effect is exactly at the preregistered threshold $\delta = -0.005$, the sample mean $\bar{D}$ is centered at $-0.005$. Because a 95% confidence interval upper bound is roughly $\bar{D} + 1.96 \times \text{SE}$, the probability of $\text{CI}_{\text{upper}} < -0.005$ is only **$4.6\%$**! Requiring the entire interval to fall below $-0.005$ is a super-superiority test requiring a true effect of at least $\delta \le -0.010$.

### 5.2 The Correct Multi-Criterion Formulation
Gate 2 is now formulated into four mathematically consistent criteria:
1. **Statistical Superiority (Hypothesis Test):**
   $$H_0: \text{median}(D) \ge 0 \quad \text{vs.} \quad H_1: \text{median}(D) < 0 \implies \text{Wilcoxon } p < 0.05$$
2. **Preregistered Effect Magnitude (Practical Significance):**
   $$\bar{D}_{\text{hidden}} = \bar{\rho}_{\text{hidden}}(\text{Arm C}) - \bar{\rho}_{\text{hidden}}(\text{Arm A}) \le -0.005$$
3. **Precision Constraint (Zero Excluded):**
   $$\text{Bootstrap } \text{CI}_{95\%, \text{upper}} < 0.0$$
4. **Benchmark Superiority:**
   $$\bar{\rho}_{\text{hidden}}(\text{Arm C}) < \bar{\rho}_{\text{hidden}}(\text{Best-Fit})$$

---

## 6. Interpretation of Statistically Nonsignificant Results

> [!CAUTION]
> **Failure to reject the null is NOT evidence of equivalence.**

1. **Absence of Evidence:**
   If $p \ge 0.05$ or the 95% confidence interval spans zero, the experiment has **failed to demonstrate a statistically significant advantage of evolutionary feedback over independent sampling**.
2. **Why Equivalence Cannot Be Claimed:**
   - To establish equivalence, one must preregister an equivalence margin (e.g. $[-\Delta_{\text{eq}}, +\Delta_{\text{eq}}] = [-0.005, +0.005]$) and conduct a Two One-Sided Tests (TOST) procedure where the 90% confidence interval must fall entirely within that margin.
   - For $T = 10$, the 90% confidence interval width is $\approx \pm 1.83 \times \text{SE} \approx \pm 0.0046$, which covers nearly the entire margin. Proving equivalence would require $T \ge 60$ trials.
3. **Formal Interpretation:**
   A nonsignificant result in Stage 4 will be recorded as **inconclusive / null**—meaning evolutionary feedback under this prompt structure and budget did not demonstrate a detectable advantage.

---

## 7. What a Positive Result Does (and Does Not) Establish

### What a Positive Result Establishes:
1. Proof-of-concept that closed-loop execution feedback (passing candidate code, numerical performance, and fitness-relative ranking) provides real search leverage over independent sampling from the same LLM with identical baseline seeds.
2. Discovery of a priority rule on heavy-tailed bin packing that genuinely outperforms the classical human Best-Fit heuristic on held-out test data.

### What a Positive Result Does NOT Establish:
1. It does **not** prove the Discovery Engine is a universal scientific discovery platform across arbitrary domains (materials, drug design, complex multi-file software).
2. It does **not** prove evolutionary search is superior to alternative guided paradigms (e.g. MCTS, reinforcement learning from execution feedback).
3. It does **not** demonstrate autonomous problem formulation—the representation (`priority` signature) and objective function were human-engineered.

---

## 8. Final Scientific Verdict & Recommendation

**Verdict:** **`SCIENTIFIC DESIGN IS SOUND UNDER THE TWO-COHORT PROTOCOL`**

**Recommendation:**
Authorize **Phase 1 Exploratory Feasibility Pilot ONLY ($15.00 limit, 300 requests, Seeds 40401–40403)** under `is_pilot=True` with `hidden.json` quarantined. Phase 1 provides qualitative feasibility, error handling, and pipeline diagnostics, not confirmatory variance proofs. A strictly independent confirmatory cohort ($T = 10$, Seeds 40411–40420) is required for formal hypothesis testing.
