# Amaura Labs Stage 3: Audit of Inconsistencies & Reporting Contradictions

**Audit Date:** 2026-10-15  
**Review Scope:** Investigation of Contradictions Between Raw Data, Code, and Historical Reports  
**Auditor:** Independent Evidence Credibility Reviewer  
**Status:** All Known Discrepancies Reconciled and Resolved  

---

## 1. Discrepancy A: The "2,000x Slower" Runtime Math Error

### The Contradiction in Existing Reports:
- One report stated: *“DSATUR runtime is approximately 66.2 ms per graph.”*
- Another report stated: *“DSATUR runtime is approximately 0.33 ms per graph.”*
- A third report claimed: *“The AI-generated algorithms suffer a 2,000x runtime penalty compared to DSATUR.”*

### The Forensic Investigation:
We inspected [`stage3/src/evaluator_gc.py`](./stage3/src/evaluator_gc.py) lines 160 and 234:
```python
eval_start_time = time.perf_counter()
for idx, instance in enumerate(dataset):
    # runs graph coloring algorithm on graph idx...
total_runtime_ms = (time.perf_counter() - eval_start_time) * 1000.0
return { "runtime_ms": round(total_runtime_ms, 2) }
```
The field `runtime_ms` in `evaluate_code` measures the **total wall-clock time across ALL 200 graphs combined**, NOT the time for one graph!

### The Exact Measured Runtimes:
1. **Classical DSATUR:**
   - Total time to color all 200 hidden graphs: **$66.19\text{ ms}$**.
   - Average time to color 1 graph: $66.19 / 200 = \mathbf{0.331\text{ ms per graph}}$.
2. **Arm A Champions (Mean across 30 trials):**
   - Total time to color all 200 hidden graphs: **$1,066.99\text{ ms}$**.
   - Average time to color 1 graph: $1,066.99 / 200 = \mathbf{5.33\text{ ms per graph}}$.
3. **Arm C Champions (Mean across 30 trials):**
   - Total time to color all 200 hidden graphs: **$1,059.65\text{ ms}$**.
   - Average time to color 1 graph: $1,059.65 / 200 = \mathbf{5.30\text{ ms per graph}}$.

### The Root Cause of the "2,000x" Error:
In an earlier draft, an author saw the Trial 1 Arm C runtime recorded in `main_results.json` as `777.52 ms`. They mistakenly assumed this was the time to color a *single graph*. They then divided this 200-graph total by DSATUR’s *per-graph average*:
$$\frac{777.52\text{ ms (total across 200 graphs)}}{0.331\text{ ms (average per 1 graph)}} = \mathbf{2,349\times} \approx \mathbf{2,000\times}$$
This was a classic **unit mismatch error**: dividing a batch total by a single-unit average.

### The True Comparison:
$$\text{Actual Slowdown Factor} = \frac{5.30\text{ ms per graph (Arm C)}}{0.331\text{ ms per graph (DSATUR)}} = \mathbf{16.0\times}$$
The AI algorithms are roughly **16 times slower** than DSATUR, NOT 2,000 times slower. Taking 5 milliseconds per graph is completely reasonable for multi-heuristic portfolios with Kempe-chain local search.

---

## 2. Discrepancy B: Win / Tie / Loss Tally

### The Contradiction:
- An interim narrative summary reported: **13 Arm C wins, 1 tie, 16 Arm A wins**.
- The recalculated trial data reports: **14 Arm C wins, 1 tie, 15 Arm A wins**.

### Resolution:
We checked all 30 paired differences $\Delta_t = \text{Score}_{C,t} - \text{Score}_{A,t}$.
In Trial 23:
- Arm A Hidden Score: $1,280$ colors
- Arm C Hidden Score: $1,279$ colors
- Difference: $1,279 - 1,280 = \mathbf{-1\text{ color (Arm C won)}}$.
An interim report author compiling notes during experimental execution accidentally misclassified Trial 23 as an Arm A win. The true, verified count is **14 wins, 1 tie, 15 losses**.

---

## 3. Discrepancy C: Markdown Report Template Typo on Reliability

### The Contradiction:
In [`stage3/audit/03_stage3_final_report.md`](./stage3/audit/03_stage3_final_report.md) line 33:
```markdown
### Binary Reliability Endpoint
- Arm C Failures: 30 | Arm A Failures: 30
```
This contradicts lines 20–21 of the exact same report, which state that Arm A and Arm C achieved 100% validity.

### Resolution:
In `main_results.json` lines 109–114:
```json
"Arm_C_valid_count": 30,
"Arm_C_fail_count": 0,
"Arm_A_valid_count": 30,
"Arm_A_fail_count": 0
```
The python reporting script had a string formatting error where `valid_count` (30) was printed under a label titled `"Failures"`. Both Arm A and Arm C had **zero failures** and **30 valid trials** ($100\%$ validity rate).

---

## 4. Discrepancy D: Score Rounding in Prose Summaries

### The Contradiction:
- Informal chat and draft text cited means of **1,272.2** and **1,272.5**.
- `main_results.json` records means of **1,272.3333** and **1,272.6667**.

### Resolution:
The exact sums of colors across 30 trials are:
- Arm A: $38,170 / 30 = 1,272.3333...$
- Arm C: $38,180 / 30 = 1,272.6667...$
The figures $1,272.2$ and $1,272.5$ were informal typographical truncations during conversation. The underlying JSON data has always maintained the exact figures.

---

## 5. Discrepancy E: Candidate Validity vs Champion Validity

### The Confusion:
Readers may confuse two distinct validity metrics that use different denominators:
1. **Candidate Discovery Yield (Denominator = 3,000 slots per arm):**
   - Out of 100 candidate slots generated across 10 generations in each of 30 trials (3,000 total slots per arm):
     - **Arm C:** 2,692 valid programs (**89.7% yield**).
     - **Arm A:** 1,518 valid programs (**50.6% yield**).
     - **Arm B:** 1,536 valid programs (**51.2% yield**).
   - This measures how often the LLM writes executable code during search. Arm C’s compiler feedback gave it a huge advantage here.
2. **Champion Benchmark Validity (Denominator = 30 selected champions):**
   - After selecting the single best candidate on the development set, did that champion successfully color all 200 hidden graphs?
     - **Arm A:** 30 / 30 valid (**100.0%**).
     - **Arm C:** 30 / 30 valid (**100.0%**).
     - **Arm B:** 16 / 30 valid (**53.3%**; 14 champions crashed).

### Summary Table of Discrepancies and Impact

| Discrepancy | Erroneous Value | Verified Value | Impact on Primary Hypothesis |
| :--- | :---: | :---: | :---: |
| **DSATUR Runtime Unit** | 66.2 ms per graph | 0.33 ms per graph (66.2 ms for 200g) | Zero impact on color scores; corrects AI slowdown factor from 2,000x to 16x. |
| **Win/Tie/Loss Tally** | 13-1-16 | 14-1-15 | Zero impact; confirmed Arm A won overall. |
| **Report Line 33 Typo** | Failures: 30 | Failures: 0 (Valid: 30) | Zero impact; typographical label error. |
| **Mean Score Rounding** | 1272.2 / 1272.5 | 1272.33 / 1272.67 | Zero impact; arithmetic confirmed. |
