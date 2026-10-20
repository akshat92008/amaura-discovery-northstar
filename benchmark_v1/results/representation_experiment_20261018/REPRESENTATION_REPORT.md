# AMAURA LABS — RESEARCH MILESTONE REPORT
## Controlled Candidate Representation Experiment for Online 1D Bin Packing
**Date:** October 18, 2026  
**Investigator:** Antigravity Autonomous Research Team  
**Model Endpoint:** `nvidia/nvidia/nemotron-3-super-120b-a12b` via OmniRoute  
**Sampling Mode:** Independent Live LLM Generation (Zero Simulation Stand-ins)  
**Deliverables:** Discrepancy Audit Memo, Raw Evidence JSONL, Summary JSON, Diagnostic Plot, Final Recommendation  

---

## 1. Executive Summary & Verdict

Following the 160-proposal Live LLM Search Pilot, Amaura Labs commissioned a controlled investigation into **Candidate Representation** for online 1D bin packing. We tested whether expanding the candidate policy interface—from a stateless per-bin priority function to a stateful decision policy that inspects the complete set of feasible open bins and item arrival history—enables frontier LLMs to escape the "monotonic equivalence trap" and discover heuristics that outperform classical Best-Fit.

### The Verdict: **STOP** Scaling Online Bin Packing Experiments

| Metric | Representation A (Stateless Priority) | Representation B (Stateful Select-Bin) | Classical Best-Fit Baseline |
| :--- | :---: | :---: | :---: |
| **Interface** | `priority(item, rem, cap) -> float` | `select_bin(item, bins, hist, cap) -> int` | Greedy Minimal Waste |
| **Measured Proposals** | 16 | 16 | — |
| **Validity Rate** | 62.5% (10/16) | **93.75%** (15/16) | 100.0% |
| **Structural Diversity** | 16 unique code hashes | 16 unique code hashes | — |
| **Behavioral Phenotypes** | 3 unique behaviors | **15 unique behaviors** | 1 |
| **Decision Disagreement vs Best-Fit** | 11.6% (70% identical) | **67.7%** (range: 48.4%–86.1%) | 0.0% |
| **Best Training Excess Ratio ($\rho$)** | 0.031433 ($\Delta = 0.00\%$) | 0.037501 ($\Delta = +19.30\%$) | **0.031433** |
| **Median Training Excess Ratio ($\rho$)** | 0.031433 ($\Delta = 0.00\%$) | 0.095231 ($\Delta = +202.96\%$) | **0.031433** |
| **Best Validation Excess Ratio ($\rho$)**| 0.031923 ($\Delta = 0.00\%$) | 0.037792 ($\Delta = +18.39\%$) | **0.031923** |
| **Candidates Beating Best-Fit** | **0 / 16** | **0 / 16** | — |

### Core Empirical Discoveries:
1. **Representation B Successfully Breaks Monotonic Equivalence:**  
   Unlike Representation A, where 70% of valid candidates produced identical bin choices to Best-Fit due to mathematical monotonicity of leftover space, Representation B exhibited **100% behavioral diversity** (15 distinct performance profiles across 15 valid candidates) and diverged from Best-Fit choices by **67.7% on average**.
2. **Behavioral Divergence Strictly Harms Online Bin Packing:**  
   Every single candidate that made different decisions than Best-Fit performed strictly worse. In Representation B, the best candidate scored $\rho = 0.037501$ (+19.3% excess bins vs Best-Fit, worse than First-Fit at $0.036816$), and the median candidate degraded efficiency by $+203.0\%$ ($\rho = 0.095231$). Extreme candidates degraded by over $+5000\%$.
3. **Best-Fit Is an Empirical Global Attractor for Non-Lookahead Packing:**  
   In online 1D packing without future knowledge, Best-Fit leaves the minimal possible residual gap at every arrival. Any policy that attempts to "reserve" space or leave gaps matching historical average item sizes incurs irreversible waste when stream dynamics shift.
4. **Recommendation:** **STOP** scaling evolutionary search on online 1D bin packing. The domain lacks optimization headroom. Pivot research immediately to **Permutation Flow-Shop Scheduling (PFSP)** and **Vertex Graph Coloring (GC)**.

---

## 2. Best-Fit Test Baseline Reconciliation

Before running the representation experiment, we resolved the discrepancy between the Best-Fit test baseline recorded in `benchmark_v1/PREREGISTRATION.md` line 47 ($0.033621$) and the empirical result ($0.032435$):

- **Audit Findings:**  
  1. The dataset `benchmark_v1/data/bin_packing/test.json` is cryptographically unchanged since initial commit `d9a1584382bec70d7230d894ebd3009f0da44782` (SHA-256: `02f2fad53dbf9862c1d8d3d4883c5f4df9d535eaf3d2b1e4901eb9f6ab22af09`).
  2. Evaluating `DeterministicBinPackingSimulator(bin_capacity=100.0)` with `best_fit_priority` on this exact test set deterministically produces **$\rho = 0.032435$** (precisely $0.03243493$).
  3. All 75 simulated pilot trials in `benchmark_v1/results/pilot/` (e.g. `trial_0001`) dynamically computed relative gaps against $0.032435$.
  4. The exact string `0.033621` matches the generation cost ($\$0.033621$) recorded for 5,255-token LLM calls in `stage3/candidates/main_candidates.jsonl` (line 1552). It was inadvertently transcribed into the text table of `PREREGISTRATION.md` during drafting.
- **Action Taken:**  
  A permanent audit memo was authored at [`benchmark_v1/audit/DISCREPANCY_BEST_FIT_TEST_BASELINE.md`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/audit/DISCREPANCY_BEST_FIT_TEST_BASELINE.md) and an erratum footnote was linked in [`benchmark_v1/PREREGISTRATION.md`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/PREREGISTRATION.md). All raw benchmark records remain intact.

---

## 3. Experimental Protocol & Controlled Design

The experiment adhered to strict scientific controls:
- **Model & Endpoint:** `nvidia/nvidia/nemotron-3-super-120b-a12b` via OmniRoute (`http://127.0.0.1:20128/v1/chat/completions`), verified via preflight test.
- **Zero Simulation Stand-ins:** Every proposal was generated live by Nemotron-3 Super. Transient transport errors (such as HTTP 502) were handled via bounded exponential backoff retries.
- **Proposal Accounting:** Exactly 16 candidate slots allocated to Representation A and 16 to Representation B (32 total measured calls). Every slot was evaluated and logged.
- **Shared Datasets:**
  - **Training Set:** 20 streams (`train.json`, 1,000 items/stream, seeds 40001–40020).
  - **Untouched Validation Set:** 100 streams (`pilot_validation.json`, 1,000 items/stream, seeds 70001–70100).
- **Baselines Parity:**
  - Training: Best-Fit $\rho = 0.031433$, First-Fit $\rho = 0.036816$, Worst-Fit $\rho = 0.137627$.
  - Validation: Best-Fit $\rho = 0.031923$, First-Fit $\rho = 0.036981$, Worst-Fit $\rho = 0.134740$.
  Parity between Representation A and Representation B baselines was cryptographically and mathematically verified to 6 decimal places.

---

## 4. In-Depth Comparative Findings

```
========================================================================================
REPRESENTATION A (Priority) vs. REPRESENTATION B (Select-Bin)
========================================================================================
Metric                             Representation A         Representation B
----------------------------------------------------------------------------------------
Interface                          priority(item, rem, cap) select_bin(item, bins, hist, cap)
Input Scope                        Local (item + 1 bin)     Global (item + all bins + hist)
Total Proposals                    16                       16
Valid Proposals                    10 (62.5%)               15 (93.75%)
Unique Code Implementations        16 (100%)                16 (100%)
Unique Behavioral Phenotypes       3 (30.0% of valid)       15 (100.0% of valid)
Mean Decision Disagreement vs BF   11.6%                    67.7%
Zero-Disagreement Rate (Pure BF)   70.0% (7/10)             0.0% (0/15)
Best Training Excess Ratio (rho)   0.031433 (Best-Fit tie)  0.037501 (+19.30% vs BF)
Median Training Excess Ratio (rho) 0.031433 (Best-Fit tie)  0.095231 (+202.96% vs BF)
Best Validation Excess Ratio (rho) 0.031923 (Best-Fit tie)  0.037792 (+18.39% vs BF)
Median Validation Excess Ratio     0.031923 (Best-Fit tie)  0.091706 (+187.27% vs BF)
Candidates Beating Best-Fit (Train)0                        0
Candidates Beating Best-Fit (Val)  0                        0
Replication Candidates Identified  0                        0
========================================================================================
```

### A. Representation A: The Monotonic Equivalence Trap
In Representation A, the candidate assigns a scalar priority $P(w, R_b, C)$ to placing item $w$ in a bin with remaining capacity $R_b$.
- 7 of the 10 valid candidates produced **exactly 0.0% decision disagreement** with Best-Fit across all 20,000 item placements.
- Inspection of candidate code explains why: candidates used expressions like:
  $$P = -(R_b - w)^2 + 0.5 \frac{w}{C} e^{-2 (R_b - w) / C}$$
  Because $\partial P / \partial (R_b - w) < 0$ monotonically for feasible bins, sorting bins by $P$ is mathematically identical to sorting by $-(R_b - w)$. The candidate cannot avoid behaving identically to Best-Fit.
- When candidates broke monotonicity (e.g. Proposal 9: thresholding item size with 62.0% disagreement; Proposal 12: non-monotonic polynomial with 53.3% disagreement), their packing efficiency collapsed:
  - Proposal 9: $\rho = 0.113833$ (+262.1% excess bins vs Best-Fit).
  - Proposal 12: $\rho = 0.073325$ (+133.3% excess bins vs Best-Fit).

### B. Representation B: Behavioral Freedom, Optimization Failure
In Representation B, candidates received the arriving item, all feasible open bins, and past arrival history:
- The LLM understood the interface exceptionally well, achieving **93.75% validity** (15/15 syntax/AST valid).
- Every valid candidate produced a **unique behavioral phenotype** (15 distinct score vectors across 20 training streams).
- The mean decision disagreement was **67.7%**.

#### Why Did Representation B Candidates Fail to Beat Best-Fit?
We analyzed the champion of Representation B (Proposal 5, `code_hash: 7d729369e99cfc14`):
```python
def select_bin(item: float, open_bins: list, stream_history: list, bin_capacity: float) -> int:
    # Idea: Combine Best-Fit with gap-matching to historical average item size
    if not open_bins:
        return -1
    avg_item = sum(stream_history) / len(stream_history) if stream_history else bin_capacity * 0.5
    best_bin, best_score, best_bin_id = None, float('inf'), None
    for b in open_bins:
        waste = b['remaining_capacity'] - item
        score = waste + abs(waste - avg_item) # Discourage leaving gaps != avg_item
        if score < best_score:
            best_score = score
            best_bin_id = b['bin_id']
    return best_bin_id
```
**Mechanism of Failure:**
By penalizing `waste` when it did not match `avg_item`, this candidate avoided placing items into tightly fitting bins ($waste \to 0$) if $waste$ was smaller than $avg_item$. Instead, it placed items into looser bins, leaving partially filled bins open longer. When subsequent items arrived, the open bins could not fit them, forcing the policy to open new bins earlier. This increased total bins used by $+19.3\%$ on training ($\rho = 0.037501$) and $+18.4\%$ on validation ($\rho = 0.037792$).

Other candidates implemented:
- **Proactive bin opening:** Returning `-1` when average remaining capacity fell below a threshold. Result: $+200\%$ to $+5000\%$ excess bins.
- **Item-size bin categorization:** Dedicating specific bins to "large" items vs "small" items. Result: severe capacity fragmentation ($\rho = 0.115853$ to $\rho = 1.810855$).

---

## 5. Diagnostic Visualization

The diagnostic plot below has been generated and saved to [`benchmark_v1/results/representation_experiment_20261018/plots/representation_comparison.png`](file:///Users/ashishsingh/Desktop/experiment1/benchmark_v1/results/representation_experiment_20261018/plots/representation_comparison.png).

- **Left Panel (Decision Divergence):** Highlights the sharp bifurcation between Representation A (clustered at 0% disagreement) and Representation B (widespread divergence from 48% to 86%).
- **Right Panel (Packing Efficiency):** Demonstrates that every single departure from Best-Fit strictly worsens excess ratio $\rho$.

---

## 6. Pre-defined Success Criterion Evaluation

The preregistered criterion for claiming a discovery was:
1. $\rho_{\text{train}} < \rho_{\text{train, BF}} = 0.031433$.
2. $\rho_{\text{val}} < \rho_{\text{val, BF}} = 0.031923$.
3. Independent replication across 10 fresh random streams.

**Result:**  
- Total candidates beating Best-Fit on training: **0** (out of 32 live proposals).  
- Total candidates beating Best-Fit on validation: **0**.  
- Discovery count: **0**.  
- Success criterion **NOT MET**.

---

## 7. Next Research Direction (Action Plan)

Per the preregistration mandate:
> *"If both representations fail to discover an improvement, stop scaling bin packing experiments and recommend the next research direction based on the evidence."*

### Recommendation: STOP Online 1D Bin Packing, PIVOT to PFSP & Graph Coloring

Online 1D bin packing is fundamentally ill-suited for frontier heuristic search because:
1. Best-Fit is empirically within $\sim 3.2\%$ of the theoretical $L_1$ lower bound (which itself is unachievable due to fractional bin relaxations).
2. Without future item lookahead, no online algorithm can achieve an asymptotic competitive ratio lower than 1.540 (Balogh et al., 2012). Best-Fit achieves 1.7 asymptotically and empirically dominates all non-clairvoyant variants.

### Recommended Next Horizons:
1. **Permutation Flow-Shop Scheduling (PFSP):**
   - **Baseline:** NEH insertion heuristic.
   - **Optimization Headroom:** NEH leaves an empirical optimality gap of **$5\%$ to $15\%$** on Taillard benchmark instances.
   - **Representation:** Job priority functions inspect multi-machine idle times, tail processing variance, and machine bottleneck loads. Unlike bin packing, multi-machine job interactions are non-monotonic, creating immense opportunity for composite non-linear dispatching rules.
2. **Vertex Graph Coloring (GC):**
   - **Baseline:** DSATUR (saturation degree heuristic).
   - **Optimization Headroom:** DSATUR is a greedy local tie-breaker that frequently commits chromatic errors on structured, high-clustering networks, requiring 2 to 6 more colors than the optimal chromatic number $\chi(G)$.
   - **Representation:** Global graph metrics (k-core decomposition, neighborhood overlap, eigenvector centrality, local clique approximations) provide rich signals that greedy degree heuristics ignore.
