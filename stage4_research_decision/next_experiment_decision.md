# Amaura Labs: Strategic Analysis & Next Experiment Decision

**Document Status:** Formal Executive Research Proposal (Reconciled & Audited)  
**Author:** Senior Research Engineer, Amaura Labs Discovery Engine  
**Date:** 2026-10-15  
**Directory:** `stage4_research_decision/`  

---

## 1. The Core Scientific Dilemma

Stage 3 answered one question definitively:
> *Does conversational prompt refinement over monolithic Python solvers discover better graph-coloring algorithms than independent random sampling under an equal candidate budget ($N = 100$)?*

The answer is **No** ($p = 0.9741$, mean paired difference $+0.3333$ colors across 30 paired trials).

### Why Did Stage 3 Fail to Demonstrate Discovery Superiority?
Our post-mortem analysis of the candidate generation ledger and AST structure points to three fundamental architectural bottlenecks in Stage 3:

1. **The Monolithic Search Trap:**
   In Stage 3, the model was asked to write the entire solver from scratch: `def color_graph(adj: list[list[int]]) -> list[int]`. As a result, candidates spent $70\%\text{--}80\%$ of their token budget generating boilerplate (adjacency matrix checks, degree counting, defensive copying, type conversions). Mutating an entire program textually via prompt feedback caused catastrophic syntactic drift (as seen in Arm B's 46.7% crash rate) or minor parameter tweaks rather than structural innovation.
2. **Combinatorial Heuristic Plateau in Pure Python:**
   Graph coloring heuristics in pure Python plateau very quickly. Once an algorithm combines DSATUR with Kempe-chain local search, further improvements require complex data structures (bitsets, bucket queues) or vast search iterations that run into Python runtime limits. Both Arm A and Arm C quickly reached this plateau.
3. **Conversational Feedback vs. Evolutionary Program Search:**
   Feeding back scalar scores and execution times in a conversational prompt ("Candidate 1 got 222 colors in 142ms") provides very weak gradient information to an LLM. It does not tell the model *which lines of logic* helped or hindered performance. In contrast, successful AI discovery systems (such as DeepMind's FunSearch, Nature 2023) do not mutate monolithic code conversationally; they **evolve targeted heuristic priority functions within a fixed, high-performance algorithmic skeleton using an island-based evolutionary archive**.

---

## 2. Evaluation of Strategic Alternatives

We evaluate four potential research directions against our eight preregistered governance criteria:

### Alternative A: Improve the Discovery Loop on Graph Coloring
- **Concept:** Increase candidate budget to $N = 1,000$, introduce bandit-based parent selection, or provide detailed trace-level execution feedback.
- **Evaluation:**
  - *Scientific Importance:* Low. Sunk-cost trap. Continuing to search the same plateaued space on the same benchmark is unlikely to change the fundamental dynamic.
  - *What We Learned:* The difference between Arm A and Arm C was $+0.33$ colors across 200 graphs (0.0016 colors/graph) with $p = 0.9741$. Scaling $N$ simply gives Arm A $10\times$ more random samples, which will likely match or beat Arm C again.
  - *Feasibility:* Moderate, but expensive ($10\times$ compute cost, ~$3,000).
  - *Verdict:* **REJECT.**

### Alternative B: Program-Space Discovery on Online 1D Bin Packing (Recommended)
- **Concept:** Adopt the FunSearch paradigm. Instead of generating monolithic solvers, hold the algorithmic framework constant (an online bin-packing simulator) and use the Discovery Engine to evolve **pure heuristic priority scoring functions** using the repository's canonical signature:
  ```python
  def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
      """Computes priority score for placing item into candidate open bin."""
      ...
  ```
- **Evaluation:**
  - *Scientific Importance:* High. Tests whether the Discovery Engine can discover novel mathematical heuristics that outperform classical textbook algorithms (Best-Fit, First-Fit) on unseen item distributions.
  - *What We Learned:* Resolves all three Stage 3 failure modes: isolates the search to the pure algorithmic decision function, eliminates boilerplate syntax crashes, and allows microsecond simulation.
  - *Backward Compatibility:* Reuses the exact function interface already implemented in `amaura/evaluators/bin_packing.py`, `amaura/engine/generator.py`, and `experiment4`.
  - *Strength of Hypothesis:* Very strong. FunSearch demonstrated that novel priority functions exist and beat Best-Fit. We can test whether our Discovery Engine reproduces or improves upon this discovery under strict equal-budget controls.
  - *Feasibility:* Extremely high. Evaluators take $< 1.5\text{ ms}$ per 1,000-item stream. We can evaluate thousands of candidates for minimal compute.
  - *Ability to Distinguish Discovery:* Decisive. Bin packing has a rigorous theoretical lower bound (the $L_1$ relaxation $\lceil \sum w_i / C \rceil$). Excess bins above $L_1$ provide an unambiguous, discrete metric ($\rho = (B - L_1)/L_1$).
  - *Quality of Baselines:* Exceptional. Classical Best-Fit (BF), First-Fit (FF), and Worst-Fit (WF) are exact online benchmarks. First-Fit Decreasing (FFD) serves as an offline reference upper bound.
  - *Relevance to General Engine:* Direct. The core discovery loop (evolve function $\to$ execute in sandbox $\to$ evaluate on distribution $\to$ select into island archive) is fully domain-agnostic.
  - *Time to Decision:* Under 5 hours total wall-clock time for a complete 10-trial experiment.
  - *Verdict:* **RECOMMENDED.**

### Alternative C: Multi-Island Quality-Diversity Search (MAP-Elites)
- **Concept:** Implement a full MAP-Elites grid characterizing algorithms by syntactic complexity, greediness, and runtime.
- **Evaluation:**
  - *Scientific Importance:* High, but introduces multiple confounding hyperparameters (grid resolution, feature definition, distance metrics) before we have established a basic program-space feedback advantage.
  - *Feasibility:* Requires substantial new infrastructure (~1,500 lines of code).
  - *Verdict:* **DEFER TO STAGE 5.** Re-evaluate after program-space discovery is validated.

### Alternative D: Stop Algorithmic Discovery & Commercialize Code Reliability
- **Concept:** Halt all discovery engine research; package the Stage 3 reliability finding ($89.7\%$ validity, $0\%$ crashes vs $46.7\%$ blind failure) into a commercial automated testing/debugging tool.
- **Evaluation:**
  - *Commercial Value:* High, but prematurely abandons the core scientific mission of Amaura Labs without testing the proven program-space discovery paradigm.
  - *Verdict:* **HOLD AS FALLBACK.** If Alternative B fails, execute Alternative D immediately.

---

## 3. Decision Matrix Comparison

| Criterion | Alt A: Scale Graph Coloring | Alt B: Program-Space Bin Packing | Alt C: MAP-Elites Archive | Alt D: Halt & Commercialize |
| :--- | :---: | :---: | :---: | :---: |
| **Scientific Value** | Low | **Very High** | High | Low (Engineering only) |
| **Direct Lesson from Stage 3** | Ignores negative result | **Directly fixes failure modes** | Partially fixes | Accepts defeat |
| **Hypothesis Precision** | Weak | **Sharp & Falsifiable** | Diffuse | N/A |
| **Engineering Feasibility** | High | **Very High (1.5 days)** | Low (2 weeks) | High |
| **Compute / Cost Requirement** | High (~$3,000) | **Minimal (< $50)** | Moderate (~$300) | $0 |
| **Distinguishes True Discovery** | Poor (noise floor) | **Excellent ($L_1$ bound)** | Moderate | N/A |
| **Baseline Quality** | Limited greedy | **Rigorous ($L_1$, BF, FF, FFD)**| Good | N/A |
| **Time to Decision** | > 40 hours | **< 5 hours** | > 20 hours | Immediate |
| **FINAL SCORE / DECISION** | **REJECT** | **SELECTED** | **DEFER** | **FALLBACK** |

---

## 4. The Single Recommended Next Experiment: Stage 4 Proposal

### Project Title
**Discovery Engine Stage 4: Program-Space Heuristic Evolution vs. Independent Sampling for Online 1D Bin Packing**

### Executive Statement of Purpose
We will conduct a strictly controlled, small-scale, equal-budget scientific experiment testing whether evolutionary program-space discovery (evolving a heuristic priority function inside an island population) discovers algorithms that achieve statistically significant out-of-distribution superiority over independent random sampling and classical Best-Fit on online bin-packing instances.

### Key Architectural Shifts from Stage 3 to Stage 4:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3 (What Failed)                      │ STAGE 4 (What We Are Doing)                         │
├────────────────────────────────────────────┼─────────────────────────────────────────────────────┤
│ Target: Monolithic solver function         │ Target: Pure priority heuristic function            │
│ def color_graph(adj) -> list[int]          │ def priority(item, rem_cap, bin_cap) -> float       │
│ Model writes boilerplate + data structures │ Framework provides high-performance simulator       │
│ Conversational prompt history feedback     │ Evolutionary island-based population archive        │
│ Domain: Graph Coloring (plateaued greedy)  │ Domain: Online 1D Bin Packing (rich open frontier)  │
│ Costly evaluation (~5.3 ms/graph)          │ Lightning-fast evaluation (< 1.5 ms/1000-item stream│
│ High stochastic noise (±4 colors unseeded) │ Zero stochastic noise (strictly seeded PRNG stream) │
│ Conflated relative & absolute metrics      │ Mathematically distinct absolute Δ and relative %   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

This experiment represents the **smallest, fastest, and most scientifically decisive experiment** capable of determining whether Amaura Labs' Discovery Engine can discover novel, superior algorithms.
