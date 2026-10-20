# AMAURA LABS STAGE 3: SCIENTIFIC CONCURRENCY EQUIVALENCE & INVARIANCE REPORT
**Protocol Revision:** Revision 4.3 (Technical Infrastructure Verification)  
**Target Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b` (Temperature 0.7, Max Tokens 4096)  
**Date:** 2026-10-07  
**Total Incurred Calls:** 495 real LLM calls  
**Raw Data Directory:** `stage3/audit/equivalence_study/`  

---

## 1. EXECUTIVE SUMMARY & FORMAL EQUIVALENCE VERDICT

> [!WARNING]
> **OVERALL CONCURRENCY EQUIVALENCE VERDICT: NOT ESTABLISHED**
> Concurrency equivalence cannot be certified for the production-shaped Arm B and Arm C systems. While Arm A demonstrates distributional invariance under memoryless batch concurrency, production-shaped Arms B and C show statistically significant score and trajectory divergences between sequential and concurrent runs ($d = 1.535$ for Arm B, $d = -0.710$ for Arm C).
> 
> Pursuant to scientific pre-registration integrity:
> **The Stage 3 Main Experiment MUST execute strictly SEQUENTIALLY (Concurrency = 1, Exactly One In-Flight Request).**

### Disaggregated Arm-by-Arm Verdicts

| Arm | Architecture Tested | Sample Sizes | Primary Statistical Metrics | Verdict | Scientific Rationale |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **Arm A** | Independent Best-of-100 | Seq: 30<br>Conc: 65 | $\Delta = -0.08$ colors<br>Cohen's $d = -0.009$<br>Mann-Whitney $p = 0.9613$<br>Validity Diff: $+10.0\%$ ($p = 0.3816$) | **PASS** | Independent calls show negligible effect size ($|d| < 0.01$), identical median dev score (231.0), and invariant AST complexity. |
| **Arm B** | Blind Iterative Search ($10 \times 10$) | Seq: 100<br>Conc: 100 | $\Delta = +12.29$ colors<br>Cohen's $d = 1.535$<br>Mann-Whitney $p = 0.0137$<br>Valid Count: 12 vs 8 | **INCONCLUSIVE / FAIL** | Severe validity collapse ($12\%$ vs $8\%$) caused by blind iteration compounding errors; sample sizes of valid candidates are non-stationary and statistically diverged. |
| **Arm C** | Amaura Adaptive Search ($10 \times 10$) | Seq: 100<br>Conc: 100 | $\Delta = -2.27$ colors<br>Cohen's $d = -0.710$<br>Mann-Whitney $p < 0.0001$<br>Valid Count: 93 vs 90 | **NOT ESTABLISHED / FAIL** | Evolutionary trajectory divergence ($T=1$ run each); pooled comparison shows statistically significant difference ($p < 0.001$), failing the requirement of identical score distributions. |

---

## 2. PART 1: ARM A COMPARISON (SEQUENTIAL 30 vs CONCURRENCY 5, 10, 20, 30)

| Metric | Sequential 30 Baseline | Conc 5 ($N=5$) | Conc 10 ($N=10$) | Conc 20 ($N=20$) | Conc 30 ($N=30$) | Pooled Conc ($N=65$) | Pooled Effect Size ($d$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Batch Latency** | 545.2 s | 41.5 s | 54.9 s | 84.7 s | 143.5 s | — | — |
| **Effective Sec / Cand** | 18.2 s | 8.3 s | 5.5 s | 4.2 s | 4.8 s | — | $3.3\times$ speedup |
| **Validity Rate** | 50.0% | 60.0% | 80.0% | 65.0% | 50.0% | **60.0%** | Risk Diff: $+0.100$ ($p=0.38$) |
| **Mean Dev Score** | 232.47 | 232.33 | 231.62 | 232.54 | 232.67 | **232.38** | $d = -0.009$ ($p=0.96$) |
| **Median Dev Score** | 231.0 | 226.0 | 230.5 | 228.0 | 231.0 | **231.0** | Identical median |
| **Completion Tokens** | 2,098.7 | 2,324.8 | 2,312.5 | 2,551.1 | 2,720.1 | 2,575.0 | $d = 0.539$ |
| **Lines of Code (LOC)** | 170.0 | 171.2 | 161.7 | 203.0 | 191.4 | 188.8 | $d = 0.297$ ($p=0.26$) |
| **AST Node Count** | 1,253.2 | 1,459.0 | 1,340.6 | 1,606.4 | 1,272.5 | 1,400.1 | $d = 0.244$ ($p=0.33$) |
| **Cyclomatic Complexity**| 65.2 | 72.8 | 66.3 | 79.9 | 66.8 | 71.1 | $d = 0.198$ |
| **Truncation Rate** | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | **0.0%** | Zero truncations |
| **Model Verification** | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | **100.0%** | Zero substitutions |

---

## 3. PART 2: PRODUCTION-SHAPED ARM B AUDIT & ROOT CAUSE

* **Sequential Execution (100 candidates):** Completed in 1,701.3 s (~28.4 min).
  - Valid Candidates: 12 / 100 (Gen 1: 6, Gen 9: 1, Gen 10: 5).
  - Mean Dev Score of Valid Candidates: **225.33 colors**.
* **Concurrent Execution (100 candidates):** Completed in 359.8 s (~6.0 min).
  - Valid Candidates: 8 / 100 (Gen 1: 5, Gen 2: 3, Gens 3–10: 0).
  - Mean Dev Score of Valid Candidates: **237.62 colors**.
* **Statistical Divergence:** $\Delta = +12.29$ colors, Cohen's $d = 1.535$, Mann-Whitney $p = 0.0137$.
* **Root Cause Analysis:**
  1. In Arm B (Blind Iteration), model errors compound over generations because no execution feedback is provided.
  2. The concurrent run experienced an early validity collapse at Gen 3 (zero valid candidates in Gens 3–10), leaving only early-generation candidates (which naturally had worse scores $\sim 246$–$249$).
  3. The sequential run recovered in Gen 10 with 5 valid greedy candidates scoring 221.
  4. Comparing the small, highly skewed surviving sets ($N=12$ vs $N=8$) created a large statistical divergence. Equivalence is **NOT ESTABLISHED**.

---

## 4. PART 3: PRODUCTION-SHAPED ARM C AUDIT & ROOT CAUSE

* **Sequential Execution (100 candidates):** Completed in 2,125.7 s (~35.4 min).
  - Valid Candidates: 93 / 100 (exceeds $90\%$ gate).
  - Mean Dev Score: **226.80 colors** (Std: 2.70, Best: 224).
* **Concurrent Execution (100 candidates):** Completed in 563.8 s (~9.4 min).
  - Valid Candidates: 90 / 100 (exceeds $90\%$ gate).
  - Mean Dev Score: **224.52 colors** (Std: 3.62, Best: 222).
* **Statistical Divergence:** $\Delta = -2.28$ colors, Cohen's $d = -0.710$, Mann-Whitney $p < 0.0001$.
* **Root Cause Analysis:**
  1. In Arm C, candidate generation is an evolutionary tree where generation $g$ mutates the best candidate of generation $g-1$.
  2. In the concurrent run, Gen 6 discovered candidate `C-conc-G06-C10` scoring 222. That parent dominated Gens 7–10, pulling all subsequent candidates to scores of 222.
  3. In the sequential run, the best parent found was 224 (at Gen 4), so subsequent generations evolved around 224–226.
  4. Because the test pooled all $\sim 90$ auto-correlated evolutionary steps from each trajectory, the single-trajectory divergence produced a highly significant test statistic ($p < 0.0001$).
  5. The data do not permit proving whether this shift was caused by inference concurrency or by stochastic trajectory divergence in an evolutionary system ($T=1$). Therefore, equivalence is **NOT ESTABLISHED**.

---

## 5. FINAL MANDATE FOR STAGE 3 MAIN EXPERIMENT

1. **Sequential Execution Rule:** The Stage 3 Main Experiment must execute **strictly sequentially**:
   - Concurrency = 1. Exactly one LLM generation request in flight at any moment.
   - Zero batching, zero concurrent requests, zero trial parallelization.
2. **Protocol Integrity:** $T_{\text{main}} = 30$ paired trials, $N = 100$ candidate slots per arm, 9,000 total candidate calls.
3. **Audit Trail Preservation:** All 495 validation calls and artifacts generated during this study are permanently preserved in `stage3/audit/equivalence_study/`.
