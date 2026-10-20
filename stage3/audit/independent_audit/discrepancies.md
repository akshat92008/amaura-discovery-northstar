# Amaura Labs Stage 3: Audit of Inconsistencies & Discrepancy Resolutions

**Repository:** `Amaura_Stage_3`  
**Domain:** Minimum Vertex Graph Coloring  
**Audit Date:** 2026-10-15  
**Auditor:** Independent Automated Forensic Reviewer  

---

## Executive Summary

During the Phase 3 forensic audit of Amaura Labs Stage 3, several discrepancies between interim prose summaries, markdown reports, and raw execution records in `stage3/results/main_results.json` were investigated. 

Every inconsistency has been traced to its mathematical, algorithmic, or typesetting root cause. Crucially, **none of these discrepancies alter the final preregistered decision: `NOT_SUPPORTED` ($p = 0.9741$)**.

---

## 1. Discrepancy A: Win / Tie / Loss Tally

### The Inconsistency
- **Summary Variant A (Erroneous):** Arm C: 13 wins, 1 tie, 16 losses.
- **Summary Variant B (Audited):** Arm C: 14 wins, 1 tie, 15 losses.

### Investigation & Trial-by-Trial Audit
We independently evaluated all 30 paired trials from `stage3/results/main_results.json` using the preregistered definition $\Delta_t = \text{Score}_{C,t} - \text{Score}_{A,t}$ on the 200 hidden graphs (lower color count is superior):

| Trial | Seed | Arm A Hidden | Arm C Hidden | $\Delta(C-A)$ | Outcome |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 01 | 30301 | 1292 | 1278 | -14 | **Arm C Win** |
| 02 | 30302 | 1277 | 1277 | 0 | **Tie** |
| 03 | 30303 | 1275 | 1237 | -38 | **Arm C Win** |
| 04 | 30304 | 1257 | 1287 | +30 | **Arm A Win** |
| 05 | 30305 | 1287 | 1271 | -16 | **Arm C Win** |
| 06 | 30306 | 1272 | 1281 | +9 | **Arm A Win** |
| 07 | 30307 | 1257 | 1280 | +23 | **Arm A Win** |
| 08 | 30308 | 1297 | 1282 | -15 | **Arm C Win** |
| 09 | 30309 | 1281 | 1282 | +1 | **Arm A Win** |
| 10 | 30310 | 1275 | 1254 | -21 | **Arm C Win** |
| 11 | 30311 | 1274 | 1255 | -19 | **Arm C Win** |
| 12 | 30312 | 1284 | 1248 | -36 | **Arm C Win** |
| 13 | 30313 | 1251 | 1278 | +27 | **Arm A Win** |
| 14 | 30314 | 1276 | 1290 | +14 | **Arm A Win** |
| 15 | 30315 | 1253 | 1280 | +27 | **Arm A Win** |
| 16 | 30316 | 1260 | 1263 | +3 | **Arm A Win** |
| 17 | 30317 | 1281 | 1283 | +2 | **Arm A Win** |
| 18 | 30318 | 1273 | 1266 | -7 | **Arm C Win** |
| 19 | 30319 | 1278 | 1269 | -9 | **Arm C Win** |
| 20 | 30320 | 1275 | 1277 | +2 | **Arm A Win** |
| 21 | 30321 | 1278 | 1290 | +12 | **Arm A Win** |
| 22 | 30322 | 1275 | 1287 | +12 | **Arm A Win** |
| 23 | 30323 | 1280 | 1279 | -1 | **Arm C Win** (C: 1279 < A: 1280) |
| 24 | 30324 | 1281 | 1277 | -4 | **Arm C Win** |
| 25 | 30325 | 1280 | 1267 | -13 | **Arm C Win** |
| 26 | 30326 | 1248 | 1251 | +3 | **Arm A Win** |
| 27 | 30327 | 1271 | 1269 | -2 | **Arm C Win** |
| 28 | 30328 | 1267 | 1279 | +12 | **Arm A Win** |
| 29 | 30329 | 1243 | 1280 | +37 | **Arm A Win** |
| 30 | 30330 | 1272 | 1263 | -9 | **Arm C Win** |

### Mathematical Summary
- **Arm C Wins ($\Delta < 0$):** 14 trials (Trials 1, 3, 5, 8, 10, 11, 12, 18, 19, 23, 24, 25, 27, 30).
- **Ties ($\Delta = 0$):** 1 trial (Trial 2).
- **Arm A Wins ($\Delta > 0$):** 15 trials (Trials 4, 6, 7, 9, 13, 14, 15, 16, 17, 20, 21, 22, 26, 28, 29).
- **Total Trials:** $14 + 1 + 15 = 30$.

### Root Cause
In an interim manual tally compiled during experimental monitoring, Trial 23 ($\text{Score}_A = 1280, \text{Score}_C = 1279, \Delta = -1$) was erroneously categorized as an Arm A win because of the narrow 1-color difference, giving 13-1-16. The exact recomputation confirms **Arm C: 14 wins, 1 tie, 15 losses**.

---

## 2. Discrepancy B: Aggregate Scores and Rounding

### The Inconsistency
- Some text reports state Arm A scored 38,170 total colors and Arm C scored 38,180 across 30 trials, while other narrative text cited means of $1,272.2$ and $1,272.5$.

### Arithmetic Audit
1. **Arm A Total Hidden Colors:**
   $$\sum_{t=1}^{30} \text{Score}_{A,t} = 38,170 \text{ colors}$$
   $$\text{Mean}_{A} = \frac{38,170}{30} = 1,272.3333... \text{ colors}$$
   $$\text{Average colors per graph} = \frac{1,272.3333}{200} = 6.36166... \text{ colors/graph}$$

2. **Arm C Total Hidden Colors:**
   $$\sum_{t=1}^{30} \text{Score}_{C,t} = 38,180 \text{ colors}$$
   $$\text{Mean}_{C} = \frac{38,180}{30} = 1,272.6666... \text{ colors}$$
   $$\text{Average colors per graph} = \frac{1,272.6666}{200} = 6.36333... \text{ colors/graph}$$

3. **Net Difference:**
   $$\text{Total Difference} = 38,180 - 38,170 = +10 \text{ colors (Arm A won overall by 10 colors)}$$
   $$\mathbb{E}[\Delta] = \frac{+10}{30} = +0.3333 \text{ colors/trial} \quad (+0.001667 \text{ colors/graph})$$

### Root Cause
The numbers $1,272.2$ and $1,272.5$ were informal prose truncations/slips. The actual values stored in `stage3/results/main_results.json` lines 65–66 are:
- `mean_x` (Arm C): `1272.6667`
- `mean_y` (Arm A): `1272.3333`
- `mean_delta`: `0.3333`

The exact values are $1,272.33$ and $1,272.67$.

---

## 3. Discrepancy C: Markdown Report Typo in Binary Reliability

### The Inconsistency
In `stage3/audit/03_stage3_final_report.md` line 33:
```markdown
### Binary Reliability Endpoint
- Arm C Failures: 30 | Arm A Failures: 30
```
This contradicts lines 20–21 of the same document:
```markdown
- Arm C Validity: 100.0% (0/30)
- Arm A Validity: 100.0% (0/30)
```

### Audit Finding
In `stage3/results/main_results.json` lines 109–114:
```json
"Arm_C_valid_count": 30,
"Arm_C_fail_count": 0,
"Arm_C_valid_rate": 1.0,
"Arm_A_valid_count": 30,
"Arm_A_fail_count": 0,
"Arm_A_valid_rate": 1.0
```
### Root Cause
The report generator script had a string template typo where `Arm_C_valid_count` was formatted under the header `"Failures"`. Both arms had **zero failures** and **30 / 30 valid trials** ($P(\text{valid}) = 1.0$).

---

## 4. Discrepancy D: Candidate Validity vs Algorithm Validity

### Distinction of Metrics
The audit uncovered that readers may confuse two distinct validity measures present in the dataset:

1. **Candidate Discovery Yield (`valid_count` in candidate generation):**
   - Each arm generates 100 candidate code programs per trial.
   - `valid_count` records how many of these 100 candidate programs successfully compiled, passed AST security, ran within time limits, and produced valid graph colorings on all 40 development graphs.
   - **Arm C (Amaura Closed-Loop):** Average $89.7 \pm 5.1$ valid candidates per 100 slots (Range: 78–98).
   - **Arm A (Independent Best-of-100):** Average $50.6 \pm 5.7$ valid candidates per 100 slots (Range: 40–61).
   - **Arm B (Blind Iterative):** Average $51.2 \pm 23.4$ valid candidates per 100 slots (Range: 3–97).
   - *Interpretation:* Arm C's execution feedback significantly improved code compilation and execution reliability during search ($89.7\%$ vs $50.6\%$).

2. **Benchmark Output Validity (`hidden_valid` on 200 hidden graphs):**
   - Refers exclusively to whether the **selected champion** produced a valid chromatic coloring on all 200 hidden graphs.
   - Arm A Champions: 30 / 30 valid ($100\%$).
   - Arm C Champions: 30 / 30 valid ($100\%$).
   - Arm B Champions: 16 / 30 valid ($53.3\%$). In 14 trials, the LLM blind prompt selected an invalid candidate.

Scores reported on the benchmark are computed strictly across all 200 graphs. If any graph had failed, the candidate would have received `is_valid: False` and a score of `None`.

---

## 5. Discrepancy E: Selection Confounders in Arm B (Blind Iterative)

### The Issue
Arm B crashed in 14 of 30 trials (46.7% failure rate, exact McNemar $p = 0.000122$).
Evaluating Arm B against Arm C strictly on the 16 "surviving" trials yields:
$$\mathbb{E}[\Delta_{C-B}] = -11.4375 \text{ colors} \quad (95\%\text{ CI: } [-25.56, +1.19], p = 0.3062)$$

### Scientific Concern
Reporting only the dual-valid subset introduces severe **survivorship bias**. The 16 surviving trials are systematically selected for instances where blind generation happened to produce working code.

### Resolution
The preregistered protocol correctly anticipated this by mandating the **Worst-Case Bounded-Imputation Sensitivity Analysis** ($S_{\text{penalty}} = 19,001$):
$$\mathbb{E}[\Delta_{\text{imputed}}] = -8,279.30 \text{ colors} \quad (95\%\text{ CI: } [-11235.9, -5322.9], p = 0.000147)$$
This proves that once execution unreliability is taken into account, blind LLM refinement is decisively inferior to closed-loop search.

---

## 6. Discrepancy F: Classical Baseline Claims ("Gold Standard" vs Classical Heuristics)

### The Issue
Informal statements referred to DSATUR as a "human gold standard."

### Audit Assessment
1. **Characterization:** Daniel Brélaz's DSATUR (1979) is a deterministic greedy heuristic that prioritizes vertices with maximum saturation degree. It is polynomial-time ($O(V^2)$), not an optimal chromatic solver, nor a human world-record benchmark.
2. **Performance Audit on 200 Hidden Graphs:**
   - **Greedy First-Fit:** 1,552 colors (7.76 avg, 14.3 ms)
   - **Welsh-Powell (1967):** 1,450 colors (7.25 avg, 14.0 ms)
   - **DSATUR (Brélaz 1979):** 1,333 colors (6.665 avg, 66.2 ms)
   - **Recursive Largest First (RLF 1979):** 1,299 colors (6.495 avg, 91.2 ms)
   - **Arm A Champion Mean:** 1,272.33 colors (6.362 avg)
   - **Arm C Champion Mean:** 1,272.67 colors (6.363 avg)
3. **Conclusion:** Both LLM methods discovered algorithms that beat DSATUR by $\sim 60.5$ to $60.8$ colors and beat RLF by $\sim 26.5$ colors. They did so by synthesizing hybrid multi-pass portfolios (combining Welsh-Powell, DSATUR, RLF, and Kempe chain reduction). However, this represents beating standard classical greedy heuristics, not solving the NP-hard minimum vertex graph coloring problem to optimality.
