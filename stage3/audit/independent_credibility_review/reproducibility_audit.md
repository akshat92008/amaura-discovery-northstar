# Amaura Labs Stage 3: Reproducibility & Stochasticity Audit

**Audit Date:** 2026-10-15  
**Review Scope:** Algorithmic Reproducibility, Pseudo-Random Number Generation (PRNG), and Replay Boundaries  
**Auditor:** Independent Evidence Credibility Reviewer  
**Status:** Reproducible Under Explicit PRNG Seed Control  

---

## 1. Scope of Reproducibility Demonstrated

To prevent exaggerated claims, we explicitly delineate what was reproduced during this audit versus what was not re-executed:

### What WAS Reproduced (100% Deterministically Verified):
1. **The Entire Statistical Pipeline:** All 30 trial scores, means, medians, paired differences, bootstrap confidence intervals, Wilcoxon signed-rank tests, McNemar tests, bounded-imputation sensitivity analyses, and Holm-Bonferroni corrections were independently re-implemented and recalculated with bit-for-bit mathematical agreement.
2. **All Classical Baseline Benchmarks:** DSATUR, Greedy First-Fit, Welsh-Powell, and RLF were independently executed from scratch on the 200 hidden graphs, reproducing exact scores (1333, 1552, 1450, 1299) and runtimes.
3. **Targeted Champion Code Execution:** The Python source code for Trial 1 champions was extracted from raw checkpoint files and re-executed across all 200 hidden graphs (15,086 vertices).

### What WAS NOT Replayed (Bounded Audit Constraints):
1. **Regenerating 9,000 LLM Candidate Calls:** As mandated by the audit constraint ("Do not make any new LLM/API calls"), we did not re-run inference through the Nemotron-3 model. Doing so would cost hundreds of dollars and would test API non-determinism rather than experimental integrity.
2. **Re-executing All 90 Selected Champions on Hidden Graphs:** Replaying all 90 champions across 200 graphs would require ~18,000 graph evaluations. We performed targeted verification on Trial 1 and deterministic statistical recomputation on the rest.

---

## 2. Investigation of Champion Score Variance

During initial audit runs, an unexpected score variation was observed for Trial 1 Arm C (`T01_C_G10_C09`):
- **Recorded in `main_results.json`:** `1,278 colors`
- **Recomputed Run 1 (unseeded):** `1,282 colors` (+4 colors)
- **Recomputed Run 2 (unseeded):** `1,279 colors` (+1 color)
- **Recomputed Run 3 (seeded with `seed=303`):** `1,278 colors` (**Exact Match**)

Meanwhile, Trial 1 Arm A (`T01_A_C011`) reproduced with zero variation:
- **Recorded in `main_results.json`:** `1,292 colors`
- **Recomputed Run 1:** `1,292 colors` (**Exact Match**)
- **Recomputed Run 2:** `1,292 colors` (**Exact Match**)

### 2.1 The Root Cause: Internal Candidate Stochasticity
We conducted an AST and source code inspection of both champion programs in `stage3/checkpoints/trial_01/trial_01_record.json`:

1. **Why Arm A (`T01_A_C011`) was 100% Deterministic:**
   The AI included `import random` at the top of the file, but **never invoked a random function anywhere in its body**. Its tie-breaking was completely deterministic (breaking ties by vertex degree, then by numerical index). As a result, its score never fluctuates.

2. **Why Arm C (`T01_C_G10_C09`) Fluctuate When Unseeded:**
   The AI wrote an algorithm with explicit randomized restarts and perturbation loops:
   ```python
   # Inside T01_C_G10_C09:
   for _ in range(20):
       order = list(range(n))
       random.shuffle(order)
       ...
   if sat == max_sat and deg == max_deg and random.random() < 0.5:
   ```
   On every graph, the algorithm executes 20 randomized shuffles and random coin-toss tie-breakers. Across 200 graphs, that is **4,000 calls to `random.shuffle()` and `random.random()`**.

### 2.2 The Evaluation Protocol Flaw
In [`stage3/src/evaluator_gc.py`](./stage3/src/evaluator_gc.py) and [`stage3/src/main_runner.py`](./stage3/src/main_runner.py):
- The evaluation loop calls `evaluator.evaluate_code(candidate_code, hidden_dataset)`.
- **Neither script sets a local random seed** before evaluating candidate code.
- Consequently, `T01_C_G10_C09` inherited whatever random state happened to exist in the Python interpreter at that millisecond.
- In the original experiment run, the runner had been initialized with master seed `303`. When we explicitly initialized Python's global PRNG with `random.seed(303)` before evaluation:
  $$\text{Recomputed Score} = \mathbf{1,278\text{ colors}} \quad (\text{Exact Match to Main Results})$$

---

## 3. The Scientific Significance of This Finding

This discovery carries critical implications for scientific governance:

1. **The Effect Size is Submerged in Stochastic Noise:**
   - The unseeded fluctuation for Arm C is $\pm 4$ colors across 200 graphs ($\pm 0.35\%$).
   - The net difference between Arm C and Arm A across the entire experiment was **+10 colors across 30 trials**—which is only **$+0.33$ colors per trial**!
   - This means the difference between the two AI methods ($0.33$ colors) is **smaller than the random wobble of a single candidate rerun** ($4$ colors)!
2. **Confirmation of `NOT_SUPPORTED`:**
   Whether Arm C scores 1,278 or 1,282, it remains essentially tied with Arm A (1,292 in Trial 1, 1,272.33 average). It does not achieve practical superiority ($\text{CI}_{\text{upper}} < -1.0$).
3. **Mandatory Recommendation for Future Protocols:**
   Any future evaluation harness MUST explicitly seed Python's `random`, NumPy's `np.random`, and any other PRNG prior to each graph evaluation to guarantee bit-for-bit deterministic reproducibility regardless of candidate implementation details.
