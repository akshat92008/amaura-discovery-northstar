# Stage 3 Scientific Manuscript Discrepancy Log

**Audit Date:** 2026-10-15  
**Review Scope:** Reconciliation Between Authoritative Raw Data and Historical Manuscript Claims  
**Auditor:** Research Engineer & Reproducibility Auditor  
**Status:** All Discrepancies Traced to Root Causes & Formally Reconciled  

---

## 1. Discrepancy Reconciliation Table

| Claim or Metric | Existing Report / Prior Narrative | Raw-Data Authoritative Result | Resolution & Root Cause | Confidence |
| :--- | :--- | :--- | :--- | :---: |
| **Win / Tie / Loss Tally** | 13 Arm C wins, 1 tie, 16 Arm A wins | **14 Arm C wins, 1 tie, 15 Arm A wins** | In Trial 23, Arm C scored 1,279 vs Arm A's 1,280 ($\Delta = -1$, Arm C win). An interim manual tally misclassified this narrow 1-color win as a loss. | **Very High** |
| **Arm A & C Mean Scores** | 1,272.2 and 1,272.5 in informal narrative | **1,272.3333 and 1,272.6667** | The figures 1,272.2 and 1,272.5 were informal typographical truncations during live chat. Raw sums are 38,170 / 30 and 38,180 / 30. | **Very High** |
| **AI Runtime Slowdown Factor** | Approximately 2,000× slower than DSATUR | **15.5× slower than DSATUR** (5.30 ms vs 0.34 ms/graph) | A prior author divided a 200-graph total runtime (~777 ms) by DSATUR's single-graph average (0.33 ms), creating a massive unit mismatch error. | **Very High** |
| **Report Line 33 Reliability** | `Arm C Failures: 30 \| Arm A Failures: 30` | **0 Failures each** (30 Valid / 30) | A string template error in the report generation script printed `valid_count` (30) under a label titled `"Failures"`. Line 20 correctly states 100% validity. | **Very High** |
| **Candidate Yield Counts** | A: 1,518, B: 1,536, C: 2,692 (out of 3,000) | **A: 1,519 (50.6%), B: 1,535 (51.2%), C: 2,691 (89.7%)** | Minor 1-candidate rounding/off-by-one difference from earlier interim logs; ledger confirms 1519, 1535, 2691. | **Very High** |
| **Baseline Characterization** | DSATUR labeled as "human gold standard" | **DSATUR is a classical greedy heuristic (Brélaz 1979)** | DSATUR is a fast $O(V^2)$ polynomial heuristic, not an optimal solver or world record. Calling it a "human gold standard" was inaccurate. | **Very High** |
| **Champion Determinism** | Claimed fully deterministic | **Exact when seeded; $\pm 0.35\%$ unseeded** | Arm C code uses internal `random.shuffle()` and coin tosses. Evaluator omitted local seed reset; seed 303 exactly reproduces 1,278 bit-for-bit. | **Very High** |
| **Overfitting Attribution** | Feedback proven to cause benchmark overfitting | **Generalization gap observed; causality unproven** | The difference on dev was $-0.67$ colors across 40 graphs (0.016 colors/graph), which is within the stochastic noise floor and selection bias. | **High** |
| **Cryptographic Secrecy** | Hashes prove hidden data was never seen | **Hashes prove file immutability at audit time** | Hashes prove files were not altered after recording, but cannot prove no human ever read `hidden.json` on disk prior to unsealing. | **Very High** |

---

## 2. Detailed Root-Cause Analyses

### 2.1 The 2,000x Runtime Error
- **What happened:** The field `runtime_ms` in `stage3/src/evaluator_gc.py` measures the **total execution time for all 200 graphs combined**. In Trial 1, Arm C took `777.52 ms` to color all 200 graphs.
- **The error:** An auditor divided `777.52 ms` by DSATUR's single-graph runtime (`0.33 ms`):
  $$777.52 / 0.33 = 2,356 \approx 2,000\times$$
- **The correction:** Comparing like units:
  - Total time across 200 graphs: Arm C $= 1,059.65\text{ ms}$, DSATUR $= 68.28\text{ ms} \implies \mathbf{15.5\times}$.
  - Per-graph time: Arm C $= 5.30\text{ ms}$, DSATUR $= 0.34\text{ ms} \implies \mathbf{15.5\times}$.
  The AI is ~15.5x slower, NOT 2,000x slower.

### 2.2 Report Template Typo (Line 33)
- In `stage3/audit/03_stage3_final_report.md` line 33, the text states `- Arm C Failures: 30 | Arm A Failures: 30`.
- Inspection of `stage3/results/main_results.json` reveals that both Arm A and Arm C had `valid_count: 30` and `fail_count: 0`.
- The reporting template had a variable substitution typo where `valid_count` was printed under the `"Failures"` header. Both arms had **0 failures** and a **100% validity rate**.

### 2.3 Win / Tie / Loss Tally Correction
- An interim summary noted 13 Arm C wins, 1 tie, 16 Arm A wins.
- Exact recount from `main_results.json` confirms:
  - Arm C won 14 trials (Trials 1, 3, 5, 8, 10, 11, 12, 18, 19, 23, 24, 25, 27, 30).
  - 1 trial tied (Trial 2: both scored 1,277).
  - Arm A won 15 trials (Trials 4, 6, 7, 9, 13, 14, 15, 16, 17, 20, 21, 22, 26, 28, 29).
  - Total: $14 + 1 + 15 = 30$.
- Trial 23 was $A=1280, C=1279$ (Arm C won by 1 color), which was misclassified in interim notes.
