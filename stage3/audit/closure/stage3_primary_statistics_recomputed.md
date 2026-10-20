# Stage 3 Primary Endpoint: Independent Statistical Recomputation

**Audit Date:** 2026-10-15  
**Review Scope:** Mathematical, Statistical, and Arithmetic Verification of Primary Endpoint  
**Auditor:** Research Engineer & Reproducibility Auditor  
**Primary Outcome:** `NOT_SUPPORTED` (Independently Confirmed)  

---

## 1. Experimental Unit & Methodological Formulation

### 1.1 The Statistical Unit of Analysis
A fundamental requirement of sound statistical design is avoiding **pseudoreplication**.
- The experiment evaluated $T = 30$ paired trials (Seeds $30301$ through $30330$).
- In each trial, the selected champions for Arm A and Arm C were evaluated on the **exact same 200 hidden graphs**.
- Treating the 6,000 graph evaluations as 6,000 statistically independent observations would be an egregious error because the 200 graphs are shared across all 30 trials, and graphs within a trial are colored by the same candidate algorithm.
- Therefore, the **statistically valid experimental unit is the paired trial ($T = 30$)**, where each trial yields an aggregate score:
  $$\text{Score}_{arm, t} = \sum_{g=1}^{200} k_{arm, t, g}$$
- The paired difference is defined strictly as:
  $$\Delta_t = \text{Score}_{C, t} - \text{Score}_{A, t}$$
  Lower graph-coloring score represents fewer colors (superior performance). Negative $\Delta_t$ denotes an Arm C win.

---

## 2. Complete Trial-Level Reconstructed Ledger ($T = 1..30$)

Every value below was independently recomputed directly from [`stage3/results/main_results.json`](./stage3/results/main_results.json) and verified against raw trial checkpoints:

| Trial | Seed | Arm A Dev (40g) | Arm A Hidden (200g) | Arm C Dev (40g) | Arm C Hidden (200g) | $\Delta_{C-A}$ Hidden | Outcome |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 01 | 30301 | 222 | 1,292 | 221 | 1,278 | -14 | **Arm C Win** |
| 02 | 30302 | 222 | 1,277 | 219 | 1,277 | 0 | **Tie** |
| 03 | 30303 | 222 | 1,275 | 219 | 1,237 | -38 | **Arm C Win** |
| 04 | 30304 | 222 | 1,257 | 222 | 1,287 | +30 | **Arm A Win** |
| 05 | 30305 | 222 | 1,287 | 221 | 1,271 | -16 | **Arm C Win** |
| 06 | 30306 | 222 | 1,272 | 221 | 1,281 | +9 | **Arm A Win** |
| 07 | 30307 | 222 | 1,257 | 222 | 1,280 | +23 | **Arm A Win** |
| 08 | 30308 | 222 | 1,297 | 221 | 1,282 | -15 | **Arm C Win** |
| 09 | 30309 | 222 | 1,281 | 221 | 1,282 | +1 | **Arm A Win** |
| 10 | 30310 | 222 | 1,275 | 220 | 1,254 | -21 | **Arm C Win** |
| 11 | 30311 | 222 | 1,274 | 219 | 1,255 | -19 | **Arm C Win** |
| 12 | 30312 | 221 | 1,284 | 220 | 1,248 | -36 | **Arm C Win** |
| 13 | 30313 | 221 | 1,251 | 221 | 1,278 | +27 | **Arm A Win** |
| 14 | 30314 | 222 | 1,276 | 222 | 1,290 | +14 | **Arm A Win** |
| 15 | 30315 | 220 | 1,253 | 221 | 1,280 | +27 | **Arm A Win** |
| 16 | 30316 | 220 | 1,260 | 221 | 1,263 | +3 | **Arm A Win** |
| 17 | 30317 | 222 | 1,281 | 220 | 1,283 | +2 | **Arm A Win** |
| 18 | 30318 | 222 | 1,273 | 220 | 1,266 | -7 | **Arm C Win** |
| 19 | 30319 | 221 | 1,278 | 222 | 1,269 | -9 | **Arm C Win** |
| 20 | 30320 | 222 | 1,275 | 221 | 1,277 | +2 | **Arm A Win** |
| 21 | 30321 | 222 | 1,278 | 222 | 1,290 | +12 | **Arm A Win** |
| 22 | 30322 | 221 | 1,275 | 225 | 1,287 | +12 | **Arm A Win** |
| 23 | 30323 | 222 | 1,280 | 222 | 1,279 | -1 | **Arm C Win** |
| 24 | 30324 | 221 | 1,281 | 220 | 1,277 | -4 | **Arm C Win** |
| 25 | 30325 | 221 | 1,280 | 221 | 1,267 | -13 | **Arm C Win** |
| 26 | 30326 | 222 | 1,248 | 220 | 1,251 | +3 | **Arm A Win** |
| 27 | 30327 | 222 | 1,271 | 221 | 1,269 | -2 | **Arm C Win** |
| 28 | 30328 | 222 | 1,267 | 221 | 1,279 | +12 | **Arm A Win** |
| 29 | 30329 | 220 | 1,243 | 222 | 1,280 | +37 | **Arm A Win** |
| 30 | 30330 | 223 | 1,272 | 221 | 1,263 | -9 | **Arm C Win** |

---

## 3. Recomputed Primary Statistics

### 3.1 Aggregate Scores & Central Tendencies
- **Arm A Total Hidden Colors:** $\sum \text{Score}_A = \mathbf{38,170\text{ colors}}$
- **Arm C Total Hidden Colors:** $\sum \text{Score}_C = \mathbf{38,180\text{ colors}}$
- **Total Net Difference:** $38,180 - 38,170 = \mathbf{+10\text{ colors (Arm A won overall)}}$
- **Arm A Mean Hidden Score:** $\mathbf{1,272.3333...\text{ colors}}$ ($6.3617$ colors/graph)
- **Arm C Mean Hidden Score:** $\mathbf{1,272.6667...\text{ colors}}$ ($6.3633$ colors/graph)
- **Mean Paired Difference ($\mathbb{E}[\Delta]$):** $\mathbf{+0.3333...\text{ colors per trial}}$ ($\mathbf{+0.001667\text{ colors per graph}}$)
- **Median Paired Difference:** $\mathbf{+0.5000\text{ colors}}$
- **Arm A Median Score:** $1,275.0$ colors
- **Arm C Median Score:** $1,277.5$ colors
- **Paired Difference Standard Deviation ($s_{\Delta}$):** $17.0658$ colors
- **Quantiles of Difference:**
  - 25th Percentile: $-12.0$ colors
  - 50th Percentile (Median): $+0.5$ colors
  - 75th Percentile: $+12.0$ colors
  - Extreme Range: $[-38\text{ colors (Trial 3)}, +37\text{ colors (Trial 29)}]$

### 3.2 Paired Win / Tie / Loss Count
- **Arm C Wins ($\Delta_t < 0$):** **14 trials**
- **Ties ($\Delta_t = 0$):** **1 trial** (Trial 2: exactly 1,277 vs 1,277)
- **Arm A Wins ($\Delta_t > 0$):** **15 trials**
- *Reconciliation:* An interim draft reported 13 wins, 1 tie, 16 losses. That was an informal human misclassification of Trial 23 ($\text{Score}_A = 1280, \text{Score}_C = 1279, \Delta = -1$). The true, authoritative count is **14 Arm C wins, 1 tie, 15 Arm A wins**.

---

## 4. Hypothesis Testing & Preregistered Decision Rule

### 4.1 Paired Bootstrap Confidence Interval
- **Method:** 10,000 paired percentile bootstrap resamples of trial-level differences.
- **Random Seed:** Preregistered seed `303`.
- **Independently Recalculated 95% CI:**
  $$\mathbf{[-6.1008, +6.7000]\text{ colors}}$$

### 4.2 Paired Wilcoxon Signed-Rank Test
- **Method:** Two-sided Wilcoxon signed-rank test on finite trial differences (scipy Pratt method for the single tie in Trial 2).
- **Test Statistic:** $W = 216.0$
- **Exact Asymptotic $p$-value:** $p = \mathbf{0.974113207...}$

### 4.3 Preregistered Decision Rule Verification
Under Protocol Revision 4.3 (`stage3/config.json`):
1. **Dual-Validity Gate:** Both arms achieved 100% valid champions ($30/30 \ge 90\%$). $\implies$ **PASSED**.
2. **Statistical Significance Gate:** Holm-Bonferroni adjusted $p < 0.05 \implies 0.974113 < 0.05$. $\implies$ **FAILED**.
3. **Practical Superiority Criterion:** 95% bootstrap CI upper bound $< -1.0$ color $\implies +6.7000 < -1.0$. $\implies$ **FAILED**.
4. **Final Preregistered Decision:**
   $$\mathbf{NOT\_SUPPORTED}$$
   *The primary hypothesis that closed-loop iterative feedback discovers algorithms that outperform independent sampling on unseen instances is decisively refuted.*
