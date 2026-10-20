# Amaura Labs: Scientific Decision Memorandum

**To:** Investment Committee & Executive Scientific Governance, Amaura Labs  
**From:** Independent Scientific Auditor  
**Date:** 2026-10-15  
**Subject:** Stage 3 Final Audit, Mechanism Analysis, and Go/No-Go Recommendation  
**Experiment:** `Amaura_Stage_3` (Iterative Closed-Loop Discovery vs. Independent Best-of-100 Sampling)  

---

## Direct Answers to Mandated Questions

### 1. What did Stage 3 establish?
1. **Primary Finding (Negative):** Closed-loop iterative execution feedback (Arm C) does **not** discover graph-coloring algorithms that generalize better to unseen instances than independent best-of-100 sampling (Arm A). Across 30 paired trials ($N=6,000$ hidden graph evaluations), Arm A slightly outperformed Arm C by a mean paired difference of $+0.3333$ colors per trial ($+0.001667$ colors per graph), with a two-sided Wilcoxon $p$-value of $0.974113$ and a 95% bootstrap confidence interval of $[-6.1008, +6.7000]$ colors. The preregistered practical superiority threshold ($\text{CI}_{\text{upper}} < -1.0$ color) was soundly missed.
2. **Reliability Finding (Positive for Feedback):** Closed-loop execution feedback dramatically suppresses syntax and runtime failures during generation. Arm C achieved an **$89.7\%$ candidate validity yield** during search (2,692 valid / 3,000 slots) with $0 / 30$ champion trial failures ($0.0\%$). In contrast, blind iterative refinement (Arm B) experienced a catastrophic **$46.7\%$ failure rate** (14 / 30 failed trials, exact McNemar $p = 0.000122$), accumulating uncorrected syntax and logic bugs.
3. **Classical Heuristic Comparison (Positive for LLM Synthesis):** Both LLM discovery arms (Arm A at 1,272.33 colors; Arm C at 1,272.67 colors) decisively outperformed standard classical greedy heuristics—specifically DSATUR (1,333 colors, $-60.5$ delta) and Greedy First-Fit (1,552 colors, $-279.5$ delta)—on the identical 200 hidden graphs by synthesizing multi-heuristic hybrid ensembles with Kempe-chain local search.

---

### 2. What did Stage 3 fail to establish?
1. **Algorithmic Generalization via Iteration:** It failed to establish that iterative prompt-level feedback provides any out-of-distribution performance advantage over independent sampling under equal candidate budgets ($N = 100$).
2. **Algorithmic Novelty:** It failed to establish that LLMs discover new mathematical principles or novel graph-coloring paradigms. Source code inspection confirms that the models synthesized combinations of textbook heuristics dating from 1879 to 1979 (Welsh-Powell, DSATUR, Leighton's RLF, Matula's smallest-last peeling, and Kempe chains).
3. **Causal Attribution of Overfitting:** While Arm C outperformed Arm A on the 40 development graphs ($\Delta = -0.6667$ colors, $p = 0.0158$) but failed on the 200 hidden graphs ($\Delta = +0.3333$ colors, $p = 0.9741$), the experiment failed to isolate the causal mechanism behind this gap. It cannot distinguish true benchmark overfitting from stochastic noise, search stagnation, weak prompt mutations, or shared development-set selection bias.

---

### 3. Is the AI Discovery Engine concept disproven, or only this particular implementation/hypothesis?
**Only this particular implementation and hypothesis are disproven.**
The specific hypothesis that *prompt-level iterative refinement with scalar fitness feedback discovers superior combinatorial heuristics compared to independent diverse sampling* is decisively rejected. However, the broader premise of AI-assisted algorithm discovery is not disproven: LLMs clearly demonstrated the ability to write valid, complex, multi-pass hybrid portfolios that beat standard single-pass heuristics by 60 colors. The failure lies in the **search topology**: iterative prompt modification in natural language creates an evolutionary bottleneck that narrows exploration without generating deeper mathematical insights.

---

### 4. Is the baseline result independently defensible?
**Yes, but strictly as a comparison against standard classical heuristics, not as a comparison against human world records.**
On the 200 hidden graphs, DSATUR requires 1,333 colors and Greedy First-Fit requires 1,552 colors. Both Arm A (1,272.33) and Arm C (1,272.67) consistently beat DSATUR by $\sim 60$ colors across all 30 trials. However:
- DSATUR is a fast, polynomial-time greedy heuristic ($O(V^2)$), running in $0.33$ ms per graph.
- The LLM champions are multi-heuristic ensembles with BFS Kempe-chain reduction passes that run for $600\text{--}800$ ms per graph ($\sim 2,000\times$ more CPU time).
- High-performance classical solvers (such as Culberson's full Iterated Greedy, TabuCol, or Hybrid Evolutionary Algorithms) were not benchmarked. Claiming superiority over "classical heuristics" is defensible; claiming superiority over "human gold standards" or "state of the art" is factually false and must be prohibited.

---

### 5. Is there a specific next experiment justified by the current evidence?
**No.** The empirical evidence does not justify deploying further capital or compute into prompt-based iterative refinement for graph coloring.

---

### 6. If yes, what single uncertainty should it resolve, and how can it be tested with minimal compute and cost?
*Not applicable (see Question 7).*

---

### 7. If no, what should be documented and stopped?
The following actions must be taken immediately:
1. **Document and Publish the Negative Finding:** Document the completed Stage 3 results transparently as a rigorous, preregistered negative finding. In machine learning and algorithm discovery, demonstrating that **independent diverse sampling matches or outperforms iterative prompt refinement** is a highly valuable, publishable contribution that directly challenges prevalent industry assumptions about LLM "self-refinement."
2. **Decommission Iterative Prompt Refinement for Combinatorial Search:** Stop further trials attempting to refine natural-language prompts sequentially with scalar score feedback. This architecture suffers from structural path-dependency, contextual drift, and algorithmic collapse.
3. **Redirect Research to Program Synthesis & Diverse Ensembles:** If Amaura Labs pursues future discovery work, resources should be redirected toward formal program synthesis, genetic programming over ASTs with explicit diversity preservation (e.g., MAP-Elites or Quality-Diversity algorithms), or neuro-symbolic solvers, rather than conversational prompt-tuning.

---

## Final Recommendation

```
════════════════════════════════════════════════════════════════════════════════════
                        RECOMMENDATION: STOP THIS RESEARCH LINE
════════════════════════════════════════════════════════════════════════════════════
```

### Rationale:
1. **Scientific Decisiveness:** The 30 paired trials were conducted with immaculate methodological controls, frozen seeds, a technical hidden firewall, and zero API breaches. The result is not ambiguous or underpowered: with $N=6,000$ hidden graph evaluations, Arm C ($\mu = 1272.67$) is statistically indistinguishable from Arm A ($\mu = 1272.33$, $p = 0.9741$). Continuing to run variations of the same prompt-refinement loop on graph coloring would be a classic sunk-cost fallacy.
2. **Economic & Resource Prudence:** Stage 3 consumed $38.62$ hours of wall-clock compute, $5,117$ API calls, $48$ million tokens, and hundreds of dollars in API credits. A follow-up experiment attempting to tweak the development set size or prompt phrasing would consume identical resources with minimal probability of altering the fundamental reality: independent diverse sampling explores a broader heuristic space than local prompt mutation.
3. **Scientific Integrity:** Amaura Labs will gain far greater credibility in the academic and industrial research communities by publishing a rigorously controlled, preregistered negative result with full cryptographic provenance than by chasing marginal, post-hoc modifications to salvage a disproven hypothesis.

**Recommendation Certified:** Stop this research line immediately. Archive the Stage 3 dataset, publish the forensic report, and redirect discovery resources to formal programmatic synthesis.
