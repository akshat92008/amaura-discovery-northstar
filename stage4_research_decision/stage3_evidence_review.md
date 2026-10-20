# Amaura Labs Stage 3: Comprehensive Evidence Review & Forensic Synthesis

**Document Status:** Official Research Engineering Document  
**Auditor / Author:** Senior Research Engineer, Amaura Labs Discovery Engine  
**Date:** 2026-10-15  
**Directory:** `stage4_research_decision/`  
**Referenced Sources:**  
- `stage3/results/main_results.json` (SHA-256: `9fb7bc6dc3e8142f5cb265b72f57cef47bd3e3f6e5d585152354769cafb058c9`)  
- `stage3/config.json` (SHA-256: `efd6d2d51c717db0a86f2343b46c6e1b7d8db0b0cee8fbb6f89141d3d6eb943f`)  
- `stage3/candidates/main_candidates.jsonl` (SHA-256: `8c7ab8874f549664321f583229b18ecbbbae420785e8f33315efd6fb5a972a52`)  
- `stage3/audit/closure/stage3_corrected_scientific_report.md`  
- `stage3/audit/closure/stage3_discrepancy_log.md`  
- `stage3/audit/closure/closure_statistics.json`  

---

## 1. Executive Summary of the Stage 3 Review

Amaura Labs Stage 3 evaluated whether closed-loop iterative execution feedback (**Arm C / Amaura**) discovers graph-coloring algorithms that generalize better to unseen instances than independent best-of-100 sampling (**Arm A**) or blind iterative prompting (**Arm B**), under a strict budget of $N = 100$ candidate generations per arm per trial across $T = 30$ independent paired trials ($9,000$ total candidate slots).

The primary preregistered hypothesis was:
$$\mathcal{H}_1: \mathbb{E}[\Delta = \text{Score}_C - \text{Score}_A] < -1.0 \text{ colors (with } p < 0.05 \text{ and } \text{CI}_{\text{upper}} < -1.0\text{)}$$

The final certified scientific verdict is **`NOT_SUPPORTED`**.

Below is the definitive account of what the empirical evidence establishes, what it fails to establish, and the exact discrepancies identified and resolved during forensic audits.

---

## 2. What the Empirical Evidence Establishes

### 2.1 Primary Numerical Results ($T = 30$ Paired Trials)
1. **Total Hidden Chromatic Score (200 unseen graphs $\times$ 30 trials):**
   - **Arm A (Independent Best-of-100):** $38,170$ total colors (mean $1,272.3333$ colors per trial; $6.3617$ colors/graph).
   - **Arm C (Amaura Closed-Loop):** $38,180$ total colors (mean $1,272.6667$ colors per trial; $6.3633$ colors/graph).
   - **Net Total Difference:** $+10$ colors in favor of Arm A.
2. **Mean Paired Difference ($\mathbb{E}[\Delta = C - A]$):**
   - **$+0.3333$ colors per trial** ($+0.001667$ colors per graph in favor of Arm A; lower is better).
   - **Median Paired Difference:** $+0.5000$ colors.
   - **Sample Paired Standard Deviation ($s_{\Delta}$):** $17.0658$ colors (json reports $18.2026$).
3. **Trial-by-Trial Win / Tie / Loss Count:**
   - **Arm A Wins ($\Delta > 0$):** **15 trials** (Trials 04, 06, 07, 09, 13, 14, 15, 16, 17, 20, 21, 22, 26, 28, 29).
   - **Arm C Wins ($\Delta < 0$):** **14 trials** (Trials 01, 03, 05, 08, 10, 11, 12, 18, 19, 23, 24, 25, 27, 30).
   - **Ties ($\Delta = 0$):** **1 trial** (Trial 02: both scored $1,277$ colors).
4. **Hypothesis Testing & Statistical Significance:**
   - **Two-Sided Paired Wilcoxon Signed-Rank Test:** $W = 216.0$, $p = 0.974113$ (Holm-Bonferroni adjusted $p = 0.974113$).
   - **95% Paired Bootstrap Confidence Interval:** $[-6.1008, +6.7000]$ colors (10,000 resamples, master seed 303).
   - **Preregistered Practical Superiority Gate ($\text{CI}_{\text{upper}} < -1.0$):** **FAILED** (`False`).
   - The primary hypothesis is definitively and irrefutably refuted.

### 2.2 Secondary Reliability Endpoint (Arm B vs Arm C)
1. **Blind Iterative Prompting (Arm B) Collapse:**
   - In Arm B, where the model was shown prior generated code but received **zero execution feedback**, the candidate code accumulated syntax and runtime bugs.
   - At Generation 10, the blind LLM selector chose an invalid candidate in **14 out of 30 trials (46.7% failure rate)**.
2. **Closed-Loop Feedback (Arm C) Stability:**
   - Arm C suffered **0 failures out of 30 trials (0.0% failure rate)**.
   - Exact McNemar test on discordant pairs: $p = 0.00012207$.
   - Candidate discovery yield during generation: Arm C achieved an **$89.7\%$ valid candidate yield** ($2,691 / 3,000$), compared to $50.6\%$ for Arm A ($1,519 / 3,000$) and $51.2\%$ for Arm B ($1,535 / 3,000$).
3. **Bounded-Imputation Sensitivity Analysis ($S_{\text{penalty}} = 19,001$):**
   - Imputing the verified worst-case penalty for invalid champions yields:
     $$\mathbb{E}[\Delta_{C - B, \text{imp}}] = -8,279.30 \text{ colors} \quad (95\%\text{ CI: } [-11235.90, -5322.93], p = 0.000147)$$
   - *Verified Conclusion:* Execution feedback is extraordinarily effective as an **automated debugging and reliability engine**, preventing conversational degeneration into invalid code.

### 2.3 Classical Baseline Performance
1. On the identical 200 hidden graphs (15,086 total vertices):
   - **Greedy First-Fit:** 1,552 colors (7.7600 avg/graph; 0.060 ms/graph).
   - **Welsh-Powell (1967):** 1,450 colors (7.2500 avg/graph; 0.068 ms/graph).
   - **DSATUR (Brélaz 1979):** 1,333 colors (6.6650 avg/graph; 0.341 ms/graph).
   - **Recursive Largest First (RLF 1979):** 1,299 colors (6.4950 avg/graph; 0.439 ms/graph).
   - **Arm A Champion Mean:** 1,272.33 colors (6.3617 avg/graph; 5.335 ms/graph).
   - **Arm C Champion Mean:** 1,272.67 colors (6.3633 avg/graph; 5.298 ms/graph).
2. Both AI arms beat DSATUR by $\sim 60$ colors and RLF by $\sim 26$ colors on the 200 hidden graphs.
3. This was accomplished by synthesizing multi-heuristic hybrid ensembles (combining Welsh-Powell, DSATUR, Leighton's RLF, Matula smallest-last peeling, and Kempe BFS chain local search).

### 2.4 Search Trajectory Dynamics Across Generations
A deep inspection of the candidate generation ledger (`main_candidates.jsonl`) reveals the following generational progression for Arm C:
- **Generation 1:** Valid rate = 55.7%, Mean Best Dev Score = 223.90
- **Generation 2:** Valid rate = 87.7%, Mean Best Dev Score = 222.47
- **Generation 3:** Valid rate = 94.0%, Mean Best Dev Score = 221.93
- **Generation 4:** Valid rate = 93.7%, Mean Best Dev Score = 221.70
- **Generation 5:** Valid rate = 90.3%, Mean Best Dev Score = 221.43
- **Generation 10:** Valid rate = 96.0%, Mean Best Dev Score = 220.97
- 29 out of 30 Arm C champions (96.7%) came from Generation 2 or later, demonstrating that the search loop actively filtered and refined candidate solutions over time on the development set.
- However, Arm A, by drawing 100 independent diverse samples across the search space, encountered champions whose dev scores averaged 221.63—nearly identical to Arm C's final 220.97.

---

## 3. What the Evidence Does NOT Establish

The Stage 3 evidence must not be overstated. Critical negative boundaries and unproven claims include:

1. **Does NOT Establish Discovery Engine General Superiority:**
   The primary claim—that iterative execution feedback discovers better algorithms than diverse random sampling—was **refuted on the hidden benchmark** ($p = 0.9741$). Closed-loop prompt refinement showed zero quality advantage over independent sampling under equal budgets ($N = 100$).
2. **Does NOT Establish Algorithmic Novelty:**
   Abstract syntax tree (AST) analysis confirms that the LLMs did not invent novel mathematical principles. The generated code consisted of known textbook heuristics from 1879 to 1979 stitched into multi-stage pipelines with randomized tie-breakers.
3. **Does NOT Prove State-of-the-Art Combinatorial Performance:**
   The AI algorithms beat standard classical greedy single-pass heuristics from 1979. Modern high-performance solvers (such as Culberson’s full Iterated Greedy, TabuCol, or Hybrid Evolutionary Algorithms with crossover) were not evaluated.
4. **Does NOT Prove Causal Benchmark Overfitting:**
   While Arm C achieved a statistically significant advantage on the 40 development graphs ($\Delta = -0.6667$ colors, $p = 0.0158$) that disappeared on the 200 hidden graphs ($\Delta = +0.3333$ colors, $p = 0.9741$), the difference is only **0.016 colors per graph**. This margin is within the stochastic noise floor of the algorithms' randomized tie-breakers and normal sample selection variance.
5. **Does NOT Prove Deterministic Execution Without Explicit Seed Control:**
   Candidate algorithms utilized internal randomized routines (`random.shuffle()`, `random.random() < 0.5`). When the test harness re-evaluates the code without fixing the global Python PRNG seed, hidden scores fluctuate by $\pm 0.35\%$ ($\pm 4$ colors). Setting `random.seed(303)` reproduces the exact score (1,278) bit-for-bit, but this highlights that the inter-arm treatment effect (+0.33 colors) was smaller than the unseeded stochastic variation of the code itself.
6. **Does NOT Establish a General-Purpose Discovery System:**
   The pipeline tested monolithic function generation (`def color_graph(adj)`) in a single NP-hard domain. It does not establish that the architecture works across other domains or on broader scientific problems.
7. **Does NOT Establish an OS Security Boundary:**
   The Stage 3 execution environment relied on static AST parsing and Python restricted globals. It did not provide operating system process, filesystem, or network isolation. Benchmark protection was an in-process state machine check, not a cryptographic enclave.

---

## 4. Discrepancy Log & Reconciliations

Forensic audits uncovered four material reporting discrepancies in early manuscripts, all of which have been traced and corrected:

| Issue | Prior Erroneous Narrative | Recomputed Authoritative Fact | Root Cause & Scientific Resolution |
| :--- | :--- | :--- | :--- |
| **Win/Loss Tally** | 13 Arm C wins, 1 tie, 16 Arm A wins | **14 Arm C wins, 1 tie, 15 Arm A wins** | In Trial 23, Arm C scored 1,279 vs Arm A's 1,280 ($\Delta = -1$, Arm C win). An interim manual tally miscounted this narrow 1-color win as an Arm A win. |
| **Runtime Slowdown** | "AI is ~2,000× slower than classical DSATUR" | **AI is 15.5× slower than DSATUR** (5.30 ms vs 0.34 ms/graph) | Arithmetic unit mismatch: a prior author divided Arm C's total execution time across all 200 graphs (~777 ms in Trial 1) by DSATUR's single-graph runtime (0.33 ms): $777 / 0.33 \approx 2,356 \approx 2,000\times$. |
| **Report Line 33 Typo** | "Arm C Failures: 30 \| Arm A Failures: 30" | **0 Failures each** (30 Valid / 30) | Markdown report string template typo: printed the variable `valid_count` (30) under a label titled `"Failures"`. |
| **Candidate Yield vs Solution Validity** | Confused candidate generation yield with benchmark validity | **Yield: C=89.7%, A=50.6%; Benchmark Validity: C=100%, A=100%** | Yield measures candidate validity during search (100 slots). Benchmark validity measures champion validity on 200 hidden graphs. Both arms had 100% valid champions. |

---

## 5. Summary Takeaway for Next-Stage Planning

Stage 3 provided a rigorous, decisive negative result for conversational prompt refinement on monolithic combinatorial solvers:
1. **The Positive Result:** Closed-loop execution feedback is an exceptional tool for **code reliability and automated debugging**, eliminating code crashes ($p = 0.000122$) and raising valid code yield to nearly $90\%$.
2. **The Negative Result:** Prompt-based conversational mutation of whole programs does **not** discover superior algorithmic principles compared to diverse independent sampling under an equal candidate budget ($p = 0.9741$).
3. **The Architectural Bottleneck:** Searching over entire monolithic functions (`def color_graph`) causes models to re-generate boilerplate, hardcode defensive checks, and plateau on known greedy heuristic ensembles. 

To achieve genuine algorithmic discovery, future research must shift from conversational prompt mutation of monolithic code to **program-space evolution over targeted heuristic priority functions**.
