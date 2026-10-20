# Amaura Labs Stage 3: Independent Evidence Credibility Audit
## Executive Verdict for Project Governance

**Auditor:** Independent Scientific Evidence Reviewer  
**Date:** 2026-10-15  
**Audit Target:** Stage 3 Graph Coloring Experiment (`Amaura_Stage_3`)  
**Audience:** Project Owner & Non-Technical Executive Leadership  

---

## 1. The Bottom Line: Can You Trust the Report?

### Verdict: **YES, WITH LIMITATIONS**

You can **fully trust the core negative finding**: **iterative AI prompt feedback (Arm C) failed to beat independent random sampling (Arm A)**. 

The experiment was run honestly, the raw trial records are genuine, and our independent mathematical recomputation confirmed every single headline score, confidence interval, and statistical test down to the fourth decimal place.

However, you must apply **strict limitations** to the broader narrative:
1. **The AI algorithms are NOT 2,000 times slower than classical baselines:** A prior report made a basic math error (dividing a 200-graph total time by a 1-graph time). In reality, the AI algorithms take about **5.3 milliseconds per graph**, which is roughly **15 to 16 times slower** than classical DSATUR (0.33 milliseconds per graph)—not 2,000 times slower.
2. **The AI did NOT discover a "new mathematical algorithm":** The AI assembled known, textbook heuristics dating from 1879 to 1979 (Welsh-Powell, DSATUR, Leighton's RLF, and Kempe chains).
3. **"Benchmark Overfitting" is an unproven theory:** While Arm C won slightly on the 40 training graphs and lost slightly on the 200 hidden graphs, the difference is only **0.016 colors per graph**—a microscopic margin that is easily explained by normal random fluctuations rather than true overfitting.
4. **Hashes do not prove secrecy:** Cryptographic hashes prove that files were not altered after the fact, but they cannot prove that a human never opened the hidden test file during development.

---

## 2. Which Conclusions Can You Trust?

The following conclusions are backed by solid, verifiable evidence:

| Scientific Conclusion | Reliability | Evidence Summary |
| :--- | :---: | :--- |
| **1. The Primary Experiment Failed (`NOT_SUPPORTED`)** | **100% Trustworthy** | Across 30 trials and 6,000 hidden test graph evaluations, Arm A scored 38,170 total colors and Arm C scored 38,180. Arm A won by 10 colors overall. The statistical test ($p = 0.9741$) proves there is zero evidence that Arm C is superior. |
| **2. Blind Iteration is Disastrous (Arm B Collapse)** | **100% Trustworthy** | When the AI was asked to refine code without executing it (blind iteration), it crashed in 14 out of 30 trials (46.7% failure rate). Execution feedback in Arm C completely eliminated these crashes (0% failure rate). Feedback makes code **reliable**, even if it does not make the underlying algorithm smarter. |
| **3. AI Beats Basic Textbook Heuristics** | **100% Trustworthy** | On the identical 200 test graphs, classical DSATUR needed 1,333 colors and Greedy First-Fit needed 1,552 colors. Both AI approaches needed ~1,272 colors (a genuine improvement of ~60 colors over DSATUR), because the AI combined multiple heuristics and local search into a single program. |
| **4. Trial Integrity & Candidate Accounting** | **100% Trustworthy** | Exactly 9,000 candidate slots (30 trials $\times$ 3 arms $\times$ 100 candidates) were generated and immutably recorded in the ledger. Every selected champion traces directly to its source candidate. |

---

## 3. Which Conclusions Remain Uncertain or Misleading?

The following claims in prior reports must be rejected or qualified:

1. **The "2,000x Slower" Claim is False:**
   - *What was claimed:* The AI algorithms take 2,000 times longer to run than DSATUR.
   - *What the evidence actually shows:* DSATUR takes **0.33 ms** per graph. The AI algorithms take **5.3 ms** per graph. The AI is roughly **15 to 16 times slower**, a perfectly standard trade-off for multi-pass heuristic search.
2. **The "Novel Discovery" Claim is Unsupported:**
   - *What was claimed:* The Discovery Engine discovered a novel algorithmic method.
   - *What the code actually shows:* Inspection of the Python code reveals standard textbook algorithms: Daniel Brélaz's DSATUR (1979), Frank Leighton's RLF (1979), and Alfred Kempe's color chains (1879). The AI acted as a skilled programmer writing a hybrid portfolio, not an inventor of new mathematics.
3. **The "State of the Art" Claim is Unsupported:**
   - *What was claimed:* The AI beats state-of-the-art classical graph coloring.
   - *What the evidence shows:* The AI only beat *single-pass greedy heuristics* from 1979. Modern high-performance algorithms (such as Hybrid Evolutionary Algorithms or TabuCol) were never benchmarked.
4. **The "Proven Overfitting" Narrative is Speculative:**
   - *What was claimed:* Execution feedback caused the AI to overfit the development graphs.
   - *What the evidence shows:* The difference on development graphs was $-0.67$ colors across 40 graphs (one color saved every 60 graphs). This margin is so tiny that it is indistinguishable from random tie-breaking noise.

---

## 4. The Single Most Important Unresolved Issue

### **Uncontrolled Randomness in Candidate Code**

When the AI wrote its graph-coloring programs, it included randomized operations (such as `random.shuffle()` and `random.random() < 0.5`) to break ties and restart search loops.

However, **neither the runner nor the evaluator set a fixed random seed** before running the candidate algorithms on the hidden test graphs.

- When we ran Trial 1 Arm C with a fixed random seed (`seed = 303`), it reproduced the recorded score of **1,278 colors exactly bit-for-bit**.
- When we ran it without setting a seed, the score varied slightly between **1,278 and 1,282 colors** ($\pm 0.35\%$).

**Why this matters to you:**
This random wobble ($\pm 4$ colors) is larger than the entire difference between Arm A and Arm C (+10 colors across 30 trials, or $+0.33$ colors per trial). The experiment was measuring differences so small that they lived inside the random noise of the algorithms themselves!

---

## 5. Summary Table of Claims for the Non-Technical Owner

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ QUESTION                                      │ AUDIT ANSWER & PLAIN ENGLISH MEANING   │
├───────────────────────────────────────────────┼────────────────────────────────────────┤
│ Did Arm C beat Arm A?                         │ NO. Arm A was actually 10 colors       │
│                                               │ better overall. They are essentially   │
│                                               │ tied.                                  │
├───────────────────────────────────────────────┼────────────────────────────────────────┤
│ Did feedback improve code reliability?        │ YES. Arm C had 0 crashes; Arm B        │
│                                               │ (blind) crashed 46.7% of the time.     │
├───────────────────────────────────────────────┼────────────────────────────────────────┤
│ Did the AI beat textbook DSATUR?              │ YES. Both Arm A and Arm C beat DSATUR  │
│                                               │ by ~60 colors on 200 graphs.           │
├───────────────────────────────────────────────┼────────────────────────────────────────┤
│ Is the AI 2,000x slower than DSATUR?          │ NO. It is ~15x slower (5.3 ms vs       │
│                                               │ 0.33 ms per graph). Math error in prior│
│                                               │ report.                                │
├───────────────────────────────────────────────┼────────────────────────────────────────┤
│ Did the AI invent new math?                   │ NO. It combined known algorithms from  │
│                                               │ 1879 to 1979 into an ensemble.         │
├───────────────────────────────────────────────┼────────────────────────────────────────┤
│ Did this audit spend any money or change data?│ NO. 100% read-only, local math, zero   │
│                                               │ API calls, zero dollars spent.         │
└───────────────────────────────────────────────┴────────────────────────────────────────┘
```
