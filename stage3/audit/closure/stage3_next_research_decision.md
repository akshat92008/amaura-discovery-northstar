# Amaura Labs: Scientific Interpretation & Next-Research Decision

**Document Status:** Formal Executive Governance Memorandum  
**Auditor:** Research Engineer & Reproducibility Auditor  
**Date:** 2026-10-15  
**Audience:** Project Lead & Investment Governance Committee  

---

## 1. Direct Answers to the 10 Scientific Governance Questions

### 1. Did Arm C outperform Arm A under the preregistered primary endpoint?
**NO.** Arm A achieved an aggregate hidden score of $38,170$ colors (mean $1,272.3333$) while Arm C achieved $38,180$ colors (mean $1,272.6667$). Arm A outperformed Arm C by $+0.3333$ colors per trial ($+10$ colors overall). The two-sided Wilcoxon signed-rank $p$-value was $0.974113$, the 95% bootstrap confidence interval was $[-6.1008, +6.7000]$, and the preregistered superiority threshold ($\text{CI}_{\text{upper}} < -1.0$) was soundly missed. The hypothesis is **decisively refuted (`NOT_SUPPORTED`)**.

### 2. What does the experiment establish about execution feedback?
Execution feedback dramatically improves **code execution reliability** during generation (increasing candidate validity yield from $50.6\%$ to $89.7\%$ and eliminating trial crashes from $46.7\%$ to $0.0\%$), but it **does not improve the mathematical quality or out-of-distribution generalization** of the discovered heuristics compared to diverse random sampling.

### 3. Does the evidence suggest a reliability advantage over blind iteration?
**YES, INDISPUTABLY.** Blind iterative prompting (Arm B) suffered catastrophic code collapse, failing in $14$ out of $30$ trials ($46.7\%$ failure rate). Arm C suffered zero failures ($0.0\%$). The exact McNemar test confirms this reliability advantage with extreme statistical significance ($p = 0.00012207$).

### 4. Is there evidence that execution feedback improves solution quality at an equal candidate budget?
**NO.** Under an identical budget of $N = 100$ candidate generations, independent Best-of-100 sampling (Arm A) achieved the same or slightly superior chromatic solution quality as closed-loop search (Arm C) across 200 unseen graphs ($1,272.33$ vs $1,272.67$).

### 5. Is development-set overfitting demonstrated, merely plausible, or unsupported?
**PLAUSIBLE, BUT CAUSALLY UNPROVEN.** While Arm C won slightly on the 40 development graphs ($-0.67$ colors, $p = 0.0158$) and lost slightly on the 200 hidden graphs ($+0.33$ colors, $p = 0.9741$), the difference is only **0.016 colors per graph**. This margin is within the stochastic noise floor of the algorithms' randomized tie-breakers ($\pm 0.35\%$) and development-set selection bias.

### 6. Did Amaura discover a demonstrably novel graph-coloring algorithm?
**NO.** Abstract syntax tree (AST) inspection of the champion code confirms that the models assembled known textbook heuristics from 1879 to 1979: Daniel Brélaz's DSATUR (1979), Frank Leighton's RLF (1979), Welsh-Powell (1967), Matula's Smallest-Last Peeling, and Alfred Kempe's color chains (1879). Zero novel mathematical principles were invented.

### 7. Were modern, strong graph-coloring methods compared?
**NO.** Only standard single-pass classical greedy heuristics from 1979 were benchmarked. Modern high-performance combinatorial solvers (such as Culberson’s full Iterated Greedy, TabuCol, or Hybrid Evolutionary Algorithms) were not evaluated.

### 8. Is the system currently demonstrated to be a general-purpose discovery engine?
**NO.** The system is currently demonstrated to be an effective synthesizer of known heuristic ensembles with robust sandbox execution feedback.

### 9. What is the strongest claim we can responsibly make?
> *“Closed-loop execution feedback reliably eliminates syntax and runtime crashes in LLM code generation (raising valid candidate yield from 50.6% to 89.7% and eliminating trial crashes from 46.7% to 0.0%), and LLMs can assemble hybrid heuristic portfolios that outperform textbook single-pass heuristics like DSATUR by ~60 colors on unseen graphs; however, conversational prompt refinement does not discover superior heuristics compared to independent diverse sampling under an equal candidate budget.”*

### 10. What remains unknown?
It remains unknown whether execution feedback provides an advantage when applied to **programmatic search spaces** (such as genetic programming over ASTs or Quality-Diversity algorithms like MAP-Elites) rather than conversational prompt mutation, or when candidate generation budgets are significantly larger ($N \ge 10,000$).

---

## 2. Evaluation of Strategic Options

We evaluate the three options outlined in the mission:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ OPTION A: Stop this line of research and preserve the result.                                    │
│ PROS: Eliminates ongoing cloud/API expenditures; preserves capital; establishes immediate        │
│       scientific credibility by publishing a clean, preregistered negative result.               │
│ CONS: Concludes discovery research on combinatorial optimization for now.                        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ OPTION B: Run one small, pre-budgeted experiment on a new domain with objective evaluators.      │
│ PROS: Tests whether the lack of feedback advantage was domain-specific (e.g. Graph Coloring      │
│       plateaus quickly, whereas 1D Bin Packing or Online Knapsack may show compounding gains).   │
│ CONS: Requires additional engineering, compute, and validation overhead.                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ OPTION C: Commercialize the verified reliability advantage into an automated code engine.        │
│ PROS: Leverages the one rock-solid positive result of Stage 3: closed-loop execution feedback    │
│       eliminates code generation failures (0% crashes vs 46.7% for blind generation).            │
│ CONS: Shifts focus from pure scientific discovery to commercial software engineering.            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Formal Research Recommendation

```
════════════════════════════════════════════════════════════════════════════════════
    PRIMARY RECOMMENDATION: OPTION A (STOP PROMPT-BASED GRAPH COLORING RESEARCH)
    SECONDARY PIVOT: OPTION C (COMMERCIALIZE EXECUTION-FEEDBACK CODE RELIABILITY)
════════════════════════════════════════════════════════════════════════════════════
```

### Recommendation Rationale:
1. **The Graph Coloring Question is Decisively Answered:** Stage 3 was conducted with 30 paired trials, 9,000 candidate slots, 6,000 hidden graph evaluations, and frozen seed sequences. The result is unequivocal ($p = 0.9741$). Continuing to run variations of the same prompt-refinement loop on graph coloring would be a classic sunk-cost fallacy.
2. **Publish the High-Value Negative Finding:** In machine learning, demonstrating that **independent diverse sampling matches or outperforms iterative prompt refinement** is a major scientific finding that directly challenges prevalent industry assumptions about LLM "self-refinement."
3. **Productize the Reliability Advantage (Option C):** Amaura Labs should pivot its engineering assets toward test-driven code generation and automated debugging. The finding that closed-loop execution feedback boosts code validity from $50.6\%$ to $89.7\%$ and reduces crash risk from $46.7\%$ to $0.0\%$ has immense practical and commercial value.

---

## 4. Conditional Specification for Bounded Research Follow-Up (If Option B is Chosen)

If executive leadership decides to test algorithmic discovery on a second domain before halting research, it must be governed by this strict, pre-budgeted specification:

### 1. New Problem Domain: **Online 1D Bin Packing**
- **Why this domain:** Unlike graph coloring (where greedy heuristics with Kempe chains plateau rapidly), online bin packing features clear, continuous algorithmic trade-offs (Best-Fit, First-Fit Decreasing, Harmonic-k) where adaptive mutations can invent novel thresholding functions without heavy combinatorial search.
- **Strongest Relevant Baseline:** Classical Best-Fit (BF) and First-Fit Decreasing (FFD).
- **Evaluation Metric:** Excess bins above theoretical $L_1$ lower bound ($\sum w_i / C$) across 100 test item streams.
- **Minimum Meaningful Improvement:** $\ge 2.0\%$ reduction in excess bins over Best-Fit on unseen streams.
- **Data Separation:** 20 development streams (100 items each) for search; 100 firewalled hidden streams (1,000 items each) for evaluation.

### 2. Strictly Bounded Budget Cap:
- **Number of Trials:** $T = 5$ paired trials (pilot-scale decision gate).
- **Candidate Budget:** $N = 50$ slots per arm per trial (Arm A vs Arm C).
- **Total Model Calls:** $\le 500$ API calls.
- **Total Token Budget:** $\le 5,000,000$ tokens.
- **Financial Cap:** $\mathbf{\le \$35.00}$ in total API costs.
- **Wall-Clock Time:** $\le 4.0\text{ hours}$ sequentially.
- **Stopping Rule:** If after 3 trials, Arm C does not outperform Arm A on the development streams by at least $1.0\%$, the experiment must terminate immediately.
- **Decision Matrix:**
  - If Arm C outperforms Arm A on hidden streams with $p < 0.05 \implies$ Proceed to Stage 4 design.
  - If Arm C fails to beat Arm A $\implies$ Permanently terminate prompt-based algorithmic discovery.
