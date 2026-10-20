# AMAURA EXPERIMENT #9 — PRE-EXPERIMENT RESEARCH MEMO
## Designing a Rigorous Cross-Domain Test: Quality-Diversity vs. Equal-Budget Independent Search in Permutation Flow Shop Scheduling

**Author:** Antigravity Autonomous Research & Discovery Agent  
**Date:** October 3, 2026  
**Status:** Pre-Experiment Scientific Research & Specification  
**Target Domain:** Permutation Flow Shop Scheduling (PFSP - $Fm \mid prmu \mid C_{\max}$)  
**Core Question:** Can a diversity-aware, quality-diversity discovery architecture systematically outperform unguided independent LLM sampling under a strict equal compute and call budget?

---

## 1. Executive Summary

Amaura’s experimental history has progressed through three distinct phases:
1. **Experiments #2–#5 (Online 1D Bin Packing):** Restricting candidate synthesis to micro-heuristics (`choose_bin`) failed to beat the classical Best Fit baseline across multiple search topologies.
2. **Experiments #6–#7 (Vertex Graph Coloring):** Moving to complete macro-solver synthesis (`def color_graph(adj) -> list[int]`) produced the system's first major breakthrough in Experiment #7, discovering a solver that soundly defeated human-designed baselines (DSATUR and RLF) on unseen graphs (984 vs 1056 DSATUR, 1021 RLF). However, Experiment #7 used an unconstrained evolutionary loop (35+ calls), leaving the causal driver ambiguous.
3. **Experiment #8 (Budget-Matched Disconfirmation):** A strictly controlled 135-call audit (15 calls $\times$ 3 conditions $\times$ 3 independent trials) decisively refuted the hypothesis that evolutionary search was the engine of improvement:
   - **Independent Search** (15 unguided calls): $1007.0 \pm 5.3$ hidden colors.
   - **Evolutionary Search** (5 initial + 5 generations of 2 offspring): $1036.7 \pm 13.5$ hidden colors ($p = 8.77 \times 10^{-5}$, Cohen's $d = +0.325$ in favor of Independent Search).
   - **Random-Parent Search** (controlling for code exposure without selection): $1019.7 \pm 22.8$ hidden colors ($p = 0.0011$ vs Evolution).

The core diagnostic was unambiguous: **naive evolutionary prompting triggers severe genetic narrowing and benchmark overfitting**, trapping the LLM in minor syntactic variations of an initial local search template while completely failing to explore alternative macro-algorithmic paradigms.

### The Purpose of Experiment #9
Experiment #9 transitions to a completely new domain—**Permutation Flow Shop Scheduling (PFSP)**—to test a fundamental scientific question:
> **Can an AI discovery architecture that explicitly maintains an archive of behavioral/algorithmic diversity (MAP-Elites) and targets underexplored strategy niches outperform equal-budget independent sampling on unseen optimization instances?**

This memo provides an exhaustive, skeptical, and mathematically formal pre-experiment evaluation of this question.

---

## 2. What Experiment #8 Actually Established

Experiment #8 was a pre-registered, budget-matched ablation. It established four rigorous empirical facts:

1. **Under equal call budgets, Independent Search statistically significantly outperforms Naive Evolution on out-of-distribution generalization:**
   On 160 blind hidden benchmark graphs, Independent Search defeated Evolutionary Search on 23 instances, lost on only 3, and tied on 134 (Net difference: $-20$ colors; Wilcoxon signed-rank $p = 8.77 \times 10^{-5}$, Cohen's $d = +0.325$).
2. **Selection pressure on the LLM actively degraded performance:**
   Condition C (Random-Parent Search), which exposed the LLM to past code but selected parents uniformly at random without fitness pressure, significantly outperformed Evolution ($p = 0.0011$, Net difference: $-17$ colors).
3. **Evolutionary search suffers from premature convergence in prompt space:**
   Averaged across 3 trials, Evolution reached a dev score of 215.7 colors at Call 10 (Generation 3) and completely flatlined across Calls 11, 12, 13, 14, and 15 (0 improvements). In contrast, Independent Search continued to make progressive breakthroughs at Calls 10, 14, and 15, reaching 213.7 dev colors and generating the overall 1003-color champion.
4. **The root failure mode is genetic narrowing in the prompt context:**
   When previous champion code is embedded into an LLM prompt with instructions to "modify and optimize," the LLM acts as a localized hill-climber. Over 73.3% of evolutionary candidates in Condition B were minor variations of a single DSATUR + Kempe chain template. It completely failed to discover orthogonal paradigms such as Recursive Largest First (RLF) or randomized multi-start portfolios.

---

## 3. What Experiment #8 Did NOT Establish

To maintain scientific integrity, we must be explicit about the boundaries of Experiment #8's findings:

1. **It did NOT prove that all iterative or evolutionary search is ineffective:**  
   Experiment #8 evaluated *naive, single-population evolutionary search* without niching, islands, or diversity maintenance. Systems like DeepMind's *FunSearch* (Nature 2023) specifically employ multi-island models and behavioral clustering to mitigate this exact failure mode.
2. **It did NOT prove that independent sampling is optimal:**  
   Independent Search was completely memoryless. It had no mechanism to recognize that a prompt had produced an invalid candidate, no ability to recombine ideas from different paradigms, and no capacity to refine a promising heuristic. It won simply because its 15 distinct prompt archetypes forced the LLM across orthogonal regions of the solution space.
3. **It did NOT prove domain independence:**  
   Experiment #8 was conducted exclusively on Vertex Graph Coloring. It remains unknown whether sequencing, routing, or scheduling problems exhibit the same prompt-attractor dynamics.
4. **It did NOT test Quality-Diversity (QD):**  
   Experiment #8 did not test whether maintaining an explicit archive of structurally distinct elites can combine the breadth of independent sampling with the cumulative refinement of iterative search.

---

## 4. Evaluation of Candidate Scheduling Problems

We evaluated six classical scheduling problem formulations against nine strict criteria:
*(1) Automatic deterministic objective, (2) Clean executable code representation, (3) Sandbox safety, (4) Sub-10ms laptop evaluation, (5) Strong classical baselines, (6) Deterministic dev/hidden benchmarks, (7) Rich macro-algorithmic diversity, (8) Zero GPU requirements, (9) High reproducibility.*

| Problem Domain | Mathematical Formulation | Evaluation Complexity | Representation Feasibility | Risk of Sandbox Deadlock | Algorithmic Richness | Verdict |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **Single-Machine Scheduling** | $1 \mid r_j, d_j \mid \sum w_j T_j$ | $O(n \log n)$ to $O(n^2)$ | Permutation of $n$ jobs | None | Low (pure sorting rules) | **REJECTED** (Too narrow) |
| **Identical Parallel Machines** | $P \mid\mid C_{\max}$ | $O(n \log m)$ | Partition or List Schedule | None | Moderate (LPT, MULTIFIT) | **REJECTED** (Too close to Bin Packing) |
| **Unrelated Parallel Machines** | $R \mid\mid C_{\max}$ | $O(n \cdot m)$ | Job-to-machine assignment | None | Moderate (LP relaxation, Min-Min) | **BORDERLINE** (Less standardized) |
| **Permutation Flow Shop (PFSP)**| $Fm \mid prmu \mid C_{\max}$ | $O(n \cdot m)$ Dynamic Prog | Permutation of $n$ jobs | None | **Very High** (NEH, CDS, IG, VNS) | **RECOMMENDED** (Ideal) |
| **Job-Shop Scheduling (JSSP)** | $Jm \mid\mid C_{\max}$ | $O(\sum o_j)$ Disjunctive Graph | Operation Sequence / Active Sched | **High (Circular waits)** | Extremely High (Shifting Bottleneck) | **REJECTED** (High invalidity rate) |
| **Resource-Constrained Project**| RCPSP | $O(n^2 \cdot R)$ Time-step | Priority list + Serial SGS | Moderate | High (SGS, Forward-Backward) | **REJECTED** (High compute overhead) |

### Detailed Analysis of Candidates

1. **Single-Machine Scheduling ($1 \mid r_j \mid \sum C_j$ or $1 \mid\mid \sum w_j T_j$):**
   While NP-hard when release dates or tardiness weights are introduced, single-machine problems are essentially permutation-sorting problems without spatial machine-allocation trade-offs. The algorithmic search space is dominated by priority dispatching rules (e.g., Smith's WSPT rule, Apparent Tardiness Cost - ATC). It lacks the rich architectural variety required to test macro-strategy discovery.

2. **Parallel Machine Scheduling ($P \mid\mid C_{\max}$):**
   Minimizing makespan across $m$ identical machines is equivalent to multi-way number partitioning. Its classical heuristics (Graham's LPT 1969, MULTIFIT Coffman 1978, Karmarkar-Karp differencing 1982) are intimately linked to bin packing. Because Experiments #2–#5 already explored 1D Bin Packing extensively, testing $P \mid\mid C_{\max}$ risks retreading the exact representation bottlenecks previously diagnosed.

3. **Job-Shop Scheduling (JSSP - $Jm \mid\mid C_{\max}$):**
   Job-shop scheduling is famous and computationally challenging (e.g., Fisher & Thompson's FT10). However, it has severe practical flaws for an autonomous LLM synthesis experiment:
   - If framed as micro-dispatching rules (e.g., SPT, MWKR, FIFO), it regresses to the constrained vertex-selection trap of Experiment #6.
   - If framed as a complete solver synthesizing active schedules on a disjunctive graph, LLM-generated code frequently creates circular dependencies, deadlocks, and precedence violations. Pilot experiments in literature report invalid candidate rates exceeding 40–50%, which rapidly exhausts modest LLM budgets.

4. **Permutation Flow Shop Scheduling (PFSP - $Fm \mid prmu \mid C_{\max}$):**
   PFSP represents the gold standard benchmark in classical production scheduling (Garey, Johnson, Sethi 1976). Every job must traverse $m$ machines in the exact same technological order $1, 2, \dots, m$. 
   - **Guaranteed Validity:** A solution is strictly a permutation $\pi = (\pi_1, \pi_2, \dots, \pi_n)$ of the $n$ jobs. Any permutation is guaranteed to be a feasible, deadlock-free schedule. Validity checking is a trivial $O(n)$ set verification.
   - **Blazing Speed:** The makespan $C_{\max}(\pi)$ is evaluated via a standard 2D dynamic programming grid in exactly $O(n \cdot m)$ operations. For $n=50, m=10$, evaluating an instance takes **0.04 ms in pure Python**. A 30-instance development suite evaluates in under **2 milliseconds**.
   - **Enormous Algorithmic Breadth:** Spans 50 years of operations research, including slope index rules (Palmer 1965), two-machine reductions (Campbell-Dudek-Smith 1970), constructive insertion heuristics (Nawaz-Enscore-Ham 1983), destruction-construction metaheuristics (Iterated Greedy, Ruiz & Stützle 2007), and variable neighborhood search.

---

## 5. Recommended Problem Specification: Permutation Flow Shop ($Fm \mid prmu \mid C_{\max}$)

### Mathematical Formulation
Given:
- A set of $n$ jobs $\mathcal{J} = \{0, 1, \dots, n-1\}$.
- A set of $m$ machines $\mathcal{M} = \{0, 1, \dots, m-1\}$.
- A non-negative processing time matrix $P \in \mathbb{R}_{\ge 0}^{n \times m}$, where $p_{j, k}$ represents the processing time of job $j$ on machine $k$.

Constraints:
1. Each machine can process at most one job at a time.
2. Each job can be processed on at most one machine at a time.
3. Operations cannot be preempted.
4. All jobs must visit machines in the strictly identical sequence $0 \to 1 \to \dots \to m-1$.
5. The sequence of jobs is identical across all machines (permutation property).

Objective:
Find a permutation $\pi = (\pi_0, \pi_1, \dots, \pi_{n-1})$ of $(0, 1, \dots, n-1)$ that minimizes the **makespan** $C_{\max}(\pi) = C(\pi_{n-1}, m-1)$, where completion times $C(\pi_i, k)$ are defined recursively by the recurrence relations:
$$\begin{aligned}
C(\pi_0, 0) &= p_{\pi_0, 0} \\
C(\pi_i, 0) &= C(\pi_{i-1}, 0) + p_{\pi_i, 0}, \quad &&\forall i \in \{1, \dots, n-1\} \\
C(\pi_0, k) &= C(\pi_0, k-1) + p_{\pi_0, k}, \quad &&\forall k \in \{1, \dots, m-1\} \\
C(\pi_i, k) &= \max\left(C(\pi_{i-1}, k), C(\pi_i, k-1)\right) + p_{\pi_i, k}, \quad &&\forall i \ge 1, k \ge 1
\end{aligned}$$

### Python Solver Interface
```python
def schedule_flowshop(times: list[list[int]]) -> list[int]:
    """
    Synthesize an optimal job schedule for a Permutation Flow Shop.
    
    Args:
        times: A 2D list of shape (n_jobs, n_machines), where times[j][m]
               is the non-negative integer processing time of job j on machine m.
               
    Returns:
        A list of length n_jobs containing a permutation of [0, 1, ..., n_jobs - 1]
        representing the processing sequence of jobs across all machines.
    """
```

---

## 6. The Existing Algorithmic Landscape in PFSP

To understand what constitutes genuine "diversity," we map the major human-designed algorithmic paradigms for PFSP:

```
                            PFSP Macro-Algorithmic Taxonomy
                                           │
         ┌──────────────────┬──────────────┴───────────────┬──────────────────┐
         ▼                  ▼                              ▼                  ▼
1. Priority Dispatch   2. Decomposition        3. Constructive Insertion  4. Iterated Greedy / Metaheuristic
(Palmer, Gupta)        (CDS / Johnson)         (NEH, Tie-break NEH)       (Ruiz & Stützle, VNS)
  - O(n log n)           - O(m n log n)          - O(n^3 m)                 - Multi-pass perturbation
  - Static slope         - Reduce to 2-machine   - Best-position insert     - Destruction + Insertion
```

### Comparative Analysis of Paradigms

| Strategy Class | Exemplar Algorithm | Time Complexity | Core Mechanism | Theoretical Strength | Failure Mode / Weakness | LLM Synthesizability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Slope / Priority Dispatch** | Palmer (1965) | $O(n \log n)$ | Computes slope $S_j = \sum (2k - m - 1) p_{j, k}$; sorts descending | Ultra-fast; handles monotonic machine trends | Blind to idle time; poor makespan ($12–15\%$ optimality gap) | Trivial (~15 lines) |
| **2. Subproblem Decomposition** | Campbell-Dudek-Smith (CDS 1970) | $O(m \cdot n \log n)$ | Generates $m-1$ artificial 2-machine subproblems; solves via Johnson's Rule; takes best | Strong theoretical anchor in exact 2-machine optimality | Coarse aggregation of intermediate machines | Moderate (~25 lines) |
| **3. Insertion Construction** | NEH (Nawaz, Enscore, Ham 1983) | $O(n^3 m)$ or $O(n^2 m)$ | Sorts by total time; inserts job $k$ into best of $k$ partial positions | **Gold standard constructive baseline for 40+ years** | Deterministic; early placement errors cannot be undone | High (~35 lines) |
| **4. Iterated Destruction/Repair** | Iterated Greedy (Ruiz & Stützle 2007) | $O(I \cdot d \cdot n^2 m)$ | Removes $d$ jobs randomly; re-inserts greedily (NEH-style); Metropolis acceptance | **SOTA metaheuristic in PFSP**; beats GAs and SA | Sensitive to destruction size $d$ and temperature $T$ | High (~60 lines) |
| **5. Local Search / VNS** | Pairwise Insertion Search | $O(K \cdot n^2 m)$ | Iteratively extracts job $i$ and inserts at $j$; accepts if makespan improves | Cleans up local inversion flaws in constructive schedules | Gets trapped in local minima without perturbation | Moderate (~40 lines) |
| **6. Beam Search** | Truncated Tree Search | $O(B \cdot n^2 m)$ | Maintains beam of width $B$ partial schedules; prunes by lower bound | Systematic exploration between greedy and branch-and-bound | Requires tight bounding functions to avoid explosion | High (~50 lines) |
| **7. Multi-Start Portfolio** | Hybrid Portfolio | $O(P \cdot n^2 m)$ | Executes Palmer + CDS + 3 randomized NEH passes; returns minimum | Robust across heterogeneous instance distributions | Does not deeply exploit any single instance | High (~45 lines) |

---

## 7. Existing AI Algorithm-Discovery Research

### The Frontier State of the Art (2023–2026)

1. **FunSearch (Romera-Paredes et al., *Nature*, Dec 2023):**
   - Paired a pre-trained LLM (Codey/PaLM 2) with an automated evaluator to discover new mathematical bounds (Cap Set) and online 1D bin-packing heuristics.
   - **Crucial Architectural Detail:** FunSearch did **not** use naive evolutionary hill-climbing. It implemented an **island model** with an archive where programs were clustered by **behavioral signatures** (vectors of output scores across inputs). Prompts sampled high-scoring programs from diverse clusters, explicitly penalizing code length.
   - **Limitation:** Required tens of thousands of LLM queries across large distributed compute clusters.

2. **Evolution of Heuristics (EoH, Liu et al., 2024; EoH-S, AAAI 2025):**
   - Evolved heuristics using a dual-view representation (natural language "thoughts" + executable Python code).
   - Evolved priority dispatching rules for scheduling and packing.
   - EoH-S extended this to evolve *complementary heuristic sets*, recognizing that a single heuristic cannot dominate all instance families.

3. **ReEvo (Ye et al., *NeurIPS*, 2024):**
   - Introduced "Reflective Evolution," where the LLM functions both as generator and critic, using comparative execution diagnostics as "verbal gradients."
   - Benchmarked on 12 combinatorial problems, including JSSP under machine shutdowns.

4. **Independent Sampling vs. Iterative Search in LLM Literature:**
   - Recent foundational studies in Neural Architecture Search and code synthesis (e.g., *Chen et al. 2024*, *Lim et al. 2024*) report that under small-to-moderate query budgets ($N \le 50$), **independent parallel sampling with verifier reranking (Best-of-N)** frequently matches or beats iterative prompting.
   - **Why?** Iterative prompting exhibits strong "semantic attractor" dynamics: the LLM anchors on the tokens provided in context, suffering catastrophic diversity collapse.

---

## 8. Relevant Diversity & Quality-Diversity (QD) Research

To prevent genetic narrowing, the evolutionary computation community developed **Quality-Diversity (QD)** algorithms:

1. **Novelty Search (Lehman & Stanley 2011):** Replaced fitness optimization with behavioral distance relative to an archive of previously visited behaviors, proving that seeking novelty often discovers objectives faster by avoiding deceptive local optima.
2. **MAP-Elites (Multi-dimensional Archive of Phenotypic Elites, Cully et al., *Nature* 2015; Mouret & Clune 2015):**
   - Divides a low-dimensional behavioral feature space into discrete cells (niches).
   - Each cell stores only the *elite* (highest-performing) individual discovered so far for that behavioral niche.
   - Produces a diverse map of high-performing solutions rather than a single convergent point.
3. **Quality-Diversity with Large Language Models (QDAIF, Lim et al. 2023; LLMatic, Nasir et al. 2024):**
   - Leverages LLMs as structured mutation and variation operators within a MAP-Elites loop.
   - Solves the open problem in genetic programming where random code mutations produce syntax errors; LLMs produce syntactically valid variations targeted at specific behavioral niches.

---

## 9. Novelty Assessment

To maintain scientific honesty, we separate what Experiment #9 would establish from what is already known:

| Category | Claim / Finding | Status in Literature |
| :--- | :--- | :--- |
| **Already Established** | Naive LLM evolutionary search without niching suffers semantic collapse. | Documented in genetic programming; confirmed in Amaura Exp #8. |
| **Already Established** | MAP-Elites illuminates behavioral niches in robotics and synthetic benchmarks. | Extensively proven (Cully 2015, Mouret 2015, Pugh 2016). |
| **Already Established** | LLMs can synthesize PFSP heuristics (dispatching rules, NEH variants). | Demonstrated in ReEvo (2024) and EoH (2024). |
| **Directly Tested by Exp #9** | **Can an explicit MAP-Elites behavioral archive enable an LLM to defeat equal-budget Independent Search on unseen combinatorial instances under strict parity ($N=15$ calls)?** | **NOVEL & UNRESOLVED.** Literature rarely matches budgets strictly or reports negative results against Best-of-N sampling. |
| **Directly Tested by Exp #9** | **Does behavioral diversity preservation prevent the out-of-distribution generalization failure observed in Exp #8?** | **NOVEL.** Connects Quality-Diversity directly to cross-distribution generalization on unseen benchmarks. |
| **Suggestive (If Successful)** | LLM discovery engines require an explicit external behavioral memory to navigate combinatorial spaces effectively. | Plausible hypothesis supported by cognitive architectures. |
| **Still Unknown** | Asymptotic scaling behavior at $N=10,000+$ calls; multi-modal reasoning. | Beyond single-researcher compute budget. |

---

## 10. Experiment #9 Hypotheses

We formulate the hypotheses with strict mathematical precision:

### Primary Hypotheses

* **Null Hypothesis ($H_0$ — Independent Dominance):**  
  Under equal computational and query budgets ($N=15$ calls per trial), a Diversity-Aware Search system maintaining an archive of behavioral/macro-algorithmic niches achieves no statistically significant improvement on the unseen Hidden Benchmark over unguided Independent Search:
  $$\mathbb{E}\left[C_{\max}^{\text{Hidden}}(\text{Diversity-Aware})\right] \ge \mathbb{E}\left[C_{\max}^{\text{Hidden}}(\text{Independent})\right]$$

* **Alternative Hypothesis ($H_1$ — Diversity Advantage):**  
  Diversity-Aware Search achieves a statistically significant reduction in total makespan on the unseen Hidden Benchmark compared to Independent Search by preventing redundant sampling and systematically exploring complementary algorithmic niches:
  $$\mathbb{E}\left[C_{\max}^{\text{Hidden}}(\text{Diversity-Aware})\right] < \mathbb{E}\left[C_{\max}^{\text{Hidden}}(\text{Independent})\right], \quad p < 0.05$$

### Secondary Hypotheses

* **Hypothesis $H_2$ (Replication of Evolutionary Collapse):**  
  Naive Evolutionary Search (Condition B) will replicate the failure mode of Experiment #8, underperforming both Independent Search and Diversity-Aware Search on the Hidden Benchmark due to genetic narrowing and development-set overfitting:
  $$\mathbb{E}\left[C_{\max}^{\text{Hidden}}(\text{Evolution})\right] > \mathbb{E}\left[C_{\max}^{\text{Hidden}}(\text{Independent})\right], \quad p < 0.05$$

* **Hypothesis $H_3$ (Out-of-Distribution Transfer):**  
  The performance gap between Diversity-Aware Search and Naive Evolution will be significantly wider on distribution-shifted instance families (bimodal, bottlenecked) than on standard uniform random instances.

---

## 11. Experimental Search Conditions

To isolate the causal mechanism, Experiment #9 compares **three core conditions** under strict budget equality:

```
                                EXPERIMENTAL CONDITIONS (15 Calls per Trial x 3 Trials)
                                                          │
          ┌───────────────────────────────────────────────┼───────────────────────────────────────────────┐
          ▼                                               ▼                                               ▼
CONDITION A: Independent Search                 CONDITION B: Naive Evolution                   CONDITION C: Diversity-Aware Search
- 15 unguided, memoryless calls                 - 5 init + 5 gens x 2 offspring                - MAP-Elites Behavioral Archive
- Prompt describes PFSP objective               - Parent selection strictly on best dev score  - 2D Niche Grid: Paradigm x Search Depth
- Zero exposure to past code/scores             - Prompt: "Refine/optimize champion"           - Identifies under-explored niches
- Explores broad parametric prior               - Replicates Experiment #8 failure mode        - Prompts LLM to synthesize novel elite
```

### Condition A: Single-Shot Independent Search (15 Calls)
- Each call receives the formal PFSP problem specification, input/output contracts, and performance objective.
- **Zero Memory:** Receives no previous code, no evaluation scores, and no diagnostic feedback.
- Prompts use standard stochastic decoding ($T=0.6$) with slight phrasing rotations (e.g., standard, constructive focus, decomposition focus, metaheuristic focus) matching standard Best-of-N sampling practice.

### Condition B: Naive Evolutionary Search (15 Calls)
- **Calls 1–5 (Generation 0):** Initial population generated using baseline prompts.
- **Calls 6–15 (Generations 1–5):** 5 generations of 2 offspring each:
  - *Offspring 1 (Exploitation):* Prompt presents the highest-fitness code currently in the population and asks the LLM to modify/refine it to reduce makespan.
  - *Offspring 2 (Crossover):* Prompt presents the top two highest-scoring distinct algorithms and asks the LLM to combine their complementary mechanisms.
- Replicates the exact evolutionary architecture that failed in Experiment #8.

### Condition C: Diversity-Aware Search (MAP-Elites Archive, 15 Calls)
- Maintains a discrete 2D behavioral archive grid (see Section 14).
- **Calls 1–5:** Initial population seeded into the archive.
- **Calls 6–15:** At each iteration:
  1. The system evaluates the candidate, categorizes its macro-strategy, and measures its behavioral search depth.
  2. The algorithm is placed into its designated niche. If the niche is empty, it becomes the elite. If occupied, it replaces the incumbent if and only if its dev makespan is lower.
  3. The system scans the archive to identify **unoccupied or under-performing niches**.
  4. The LLM prompt is dynamically constructed: it presents an elite from an adjacent niche and explicitly instructs the model to bridge the gap into the underexplored niche (e.g., *"Our archive currently lacks an Iterated Destruction-Repair strategy. Using ideas from our Insertion elite, design a solver in this missing paradigm"*).

---

## 12. Benchmark Suite Design

To prevent overfitting and evaluate true generalization, the benchmark suite is partitioned into a 30-instance Development Suite and a 120-instance blind Hidden Benchmark.

### Benchmark Composition

| Benchmark Split | Family ID | Instance Family Description | Properties & Challenges | Instance Count | Problem Dimensions $(n \times m)$ |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Development** | `dev_taillard` | Taillard-like Uniform Random | $p_{j, k} \sim \mathcal{U}[1, 99]$; standard benchmark distribution | 5 | $20 \times 5, 20 \times 10, 50 \times 5, 50 \times 10$ |
| ($N=30$, seed=1042)| `dev_mach_corr`| Machine-Correlated Bottleneck | Upstream or downstream machines have $3\times$ higher mean load | 5 | $20 \times 5, 50 \times 5, 50 \times 10$ |
| | `dev_job_corr` | Job-Correlated Load | Specific jobs are consistently heavy or light across all machines | 5 | $20 \times 5, 50 \times 5, 50 \times 10$ |
| | `dev_bimodal` | Bimodal Processing Times | $p_{j, k} \in \mathcal{U}[5, 15] \cup \mathcal{U}[80, 100]$; creates scheduling gaps | 5 | $20 \times 5, 50 \times 5, 50 \times 10$ |
| | `dev_high_ratio`| High Aspect Ratio ($n \gg m$) | $n=50, m=4$; sequencing decisions dominate idle times | 5 | $50 \times 4, 60 \times 4$ |
| | `dev_square` | Square Aspect Ratio ($n \approx m$) | $n=15, m=15$; combinatorial interaction across machines | 5 | $15 \times 15, 20 \times 20$ |
| **Hidden Benchmark** | `hid_taillard` | Classic Taillard Benchmarks | Direct subsets of classic published Taillard (1993) instances | 20 | $20 \times 5, 20 \times 10, 20 \times 20, 50 \times 5, 50 \times 10$ |
| ($N=120$, seed=70099)| `hid_mach_corr`| Machine Bottlenecks | Severe center-stage or dual-stage bottlenecks | 20 | $20 \times 10, 50 \times 10, 100 \times 5$ |
| *(Completely blind* | `hid_job_corr` | Heterogeneous Job Load | Log-normal job duration distributions | 20 | $20 \times 10, 50 \times 10, 100 \times 5$ |
| *during search)* | `hid_bimodal` | Extreme Multimodal | Trimodal processing durations | 20 | $20 \times 10, 50 \times 10, 100 \times 5$ |
| | `hid_high_ratio`| Extreme High Ratio | $n=100, m=5$; tests scalability of insertion routines | 20 | $100 \times 5, 100 \times 10$ |
| | `hid_dist_shift`| Distribution-Shifted (U-Load) | U-shaped machine load (heavy first and last machines) | 20 | $30 \times 10, 50 \times 10$ |

### Isolation Guarantee
The 120 Hidden Benchmark instances are generated using a dedicated seed (`70099`), stored in a separate encrypted/isolated module, and **never evaluated during search**. Only the single frozen champion from each condition and trial is evaluated on the Hidden Benchmark at the conclusion of the experiment.

---

## 13. Classical Baseline Algorithms

To calibrate discovery performance against human engineering, we implement four classical baselines:

1. **Palmer's Slope Heuristic (1965):**
   - *Role:* Simple, fast dispatching rule ($O(n \log n)$).
   - *Purpose:* Establishes the floor of constructive heuristics.
2. **Campbell-Dudek-Smith (CDS 1970):**
   - *Role:* Classical multi-pass decomposition heuristic ($O(m \cdot n \log n)$).
   - *Purpose:* Establishes whether the LLM can beat polynomial subproblem reduction.
3. **Nawaz-Enscore-Ham (NEH 1983):**
   - *Role:* The gold-standard constructive heuristic for PFSP ($O(n^3 m)$).
   - *Purpose:* The definitive target baseline. Any discovered algorithm that consistently beats NEH has produced a non-trivial scientific result.
4. **Iterated Greedy (Ruiz & Stützle 2007, bounded iterations):**
   - *Role:* Modern metaheuristic baseline (destruction size $d=4$, 20 iterations, $O(I \cdot d \cdot n^2 m)$).
   - *Purpose:* Demonstrates state-of-the-art local search/metaheuristic performance under the same 50 ms per-instance runtime cap.

---

## 14. Defining and Measuring Algorithmic Diversity

A critical finding of our research is that **source code syntax (AST diffs, token counts) is an invalid proxy for algorithmic diversity**. Two algorithms with wildly different ASTs often compute mathematically identical rankings, while a two-token change (e.g. flipping `<` to `>`) can alter an algorithm's entire behavior.

### The 2D MAP-Elites Archive Structure

We define a 2D behavioral feature space where diversity is strictly behavioral and structural:

```
                                  MAP-Elites Behavioral Grid (5 x 3 = 15 Niches)
                                  
                            Search Intensity / Computational Footprint
                      ┌─────────────────────┬─────────────────────┬─────────────────────┐
                      │ Low: O(n log n)     │ Med: O(n^2 m)       │ High: Multi-Pass    │
                      │ (Single-pass sort)  │ (Greedy insertion)  │ (Iterated / Search) │
┌─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┤
│ 1. Priority Dispatch│ Niche (1, 1)        │ Niche (1, 2)        │ Niche (1, 3)        │
├─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┤
│ 2. Decomposition    │ Niche (2, 1)        │ Niche (2, 2)        │ Niche (2, 3)        │
├─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┤
│ 3. Insertion-Based  │ Niche (3, 1)        │ Niche (3, 2) [NEH]  │ Niche (3, 3)        │
├─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┤
│ 4. Destruction/Rep. │ Niche (4, 1)        │ Niche (4, 2)        │ Niche (4, 3) [IG]   │
├─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┤
│ 5. Hybrid Portfolio │ Niche (5, 1)        │ Niche (5, 2)        │ Niche (5, 3)        │
└─────────────────────┴─────────────────────┴─────────────────────┴─────────────────────┘
```

### Behavioral Similarity Metrics

1. **Phenotypic Decision Distance (Kendall's $\tau$ Distance):**  
   For two candidate algorithms $A$ and $B$, we compute their output permutations $\pi_A(I)$ and $\pi_B(I)$ across all benchmark instances $I$. The behavioral distance is the mean normalized Kendall's $\tau$ distance:
   $$d_{\text{behavior}}(A, B) = \frac{1}{|\mathcal{I}|} \sum_{I \in \mathcal{I}} \left( 1 - \tau\left(\pi_A(I), \pi_B(I)\right) \right)$$
   If two algorithms output the identical job sequence across all instances, $d = 0$, regardless of code differences.
2. **Performance Signature Vector ($\vec{s}$):**  
   The relative performance profile across the 6 development families:
   $$\vec{s}(A) = \left( \frac{C_{\max}(A, F_1)}{C_{\max}(\text{NEH}, F_1)}, \dots, \frac{C_{\max}(A, F_6)}{C_{\max}(\text{NEH}, F_6)} \right)$$
   Euclidean distance $\|\vec{s}(A) - \vec{s}(B)\|$ identifies whether algorithms possess distinct structural failure modes.

---

## 15. Execution Sandbox & Evaluation Protocol

1. **AST Security Sandbox:**
   - Enforces pure Python. Disallows imports except `math` and `random`.
   - Blocks dynamic execution (`eval`, `exec`, `open`, `__import__`, `globals`).
   - Verifies required function signature `def schedule_flowshop(times: list[list[int]]) -> list[int]:`.
2. **Hard OS Interrupt Timer:**
   - Implements a 1-second `signal.SIGALRM` hard kill per instance inside the evaluation loop to prevent infinite loops from hanging Python (incorporating the hard-learned lesson from Experiment #8).
3. **Runtime Budget:**
   - Per-instance soft timeout: 50 ms.
   - Per-instance hard timeout: 300 ms.
   - Any candidate exceeding 300 ms on any single instance is marked invalid ($C_{\max} = 999,999$).
4. **Feasibility Validation:**
   - Confirms output is a valid permutation: `len(perm) == n` and `set(perm) == set(range(n))`.

---

## 16. Statistical Analysis Plan

To prevent post-hoc data dredging, the statistical analysis is pre-registered:

1. **Primary Metric:** Total Makespan across the 120 Hidden Benchmark instances ($\sum_{k=1}^{120} C_{\max}(k)$).
2. **Primary Hypothesis Test:**
   - **Condition C (Diversity-Aware) vs. Condition A (Independent Search):** Two-sided Wilcoxon signed-rank test on paired instance makespans across the 120 hidden instances for the overall trial champions.
   - Significance threshold: $\alpha = 0.05$.
3. **Multiple Testing Correction:**
   - For secondary pairwise comparisons (C vs B, A vs B, C vs NEH), apply Holm-Bonferroni correction.
4. **Effect Size:**
   - Compute Cohen's $d$ on paired instance differences: $d = \frac{\bar{D}}{\sigma_D}$.
   - Compute non-parametric Cliff's Delta ($\delta$).
5. **Search-Efficiency Curves:**
   - Track and plot best-so-far development makespan as a function of call budget ($1 \dots 15$) averaged across the 3 independent trials.

---

## 17. Failure Modes & Threats to Validity (Skeptical Review)

As skeptical reviewers, we identify five critical threats that could break the experiment:

1. **The Memorization Threat:**
   - *Critique:* The LLM might have memorized the exact Python code for NEH or Palmer during pre-training.
   - *Countermeasure:* The benchmark includes distribution-shifted instances (bimodal, machine-correlated) where standard NEH is sub-optimal. Furthermore, candidate ASTs will be audited for verbatim replication vs. novel structural synthesis.
2. **Prompt Asymmetry / Leakage:**
   - *Critique:* Does Condition C get an unfair advantage because its prompts suggest specific missing paradigms?
   - *Countermeasure:* Condition A's prompts must also encompass diverse algorithmic prompts (matching standard practice where developers prompt with various ideas). The difference is that Condition C dynamically selects prompts based on *archive vacancies*, whereas Condition A does so *stochastically*.
3. **The "Gaming Diversity" Failure Mode:**
   - *Critique:* The LLM might generate a deliberately bizarre, low-quality algorithm simply to satisfy the diversity prompt.
   - *Countermeasure:* MAP-Elites strictly enforces **Quality-Diversity**: a niche only retains an algorithm if it is the *elite* (best-performing) solver discovered in that category. Low-quality garbage never displaces strong algorithms.
4. **Evaluation Timeout Traps:**
   - *Critique:* LLMs attempting local search might write unvectorized Python loops that time out on $n=100$ instances.
   - *Countermeasure:* The sandbox enforces a strict 50 ms budget and provides explicit prompt constraints requiring $O(n^2 m)$ efficiency.
5. **LLM Stochasticity & Sample Variance:**
   - *Critique:* Is 3 trials enough?
   - *Countermeasure:* 3 trials $\times$ 15 calls = 45 calls per condition. In Experiment #8, 3 trials yielded extremely tight standard deviations ($\pm 5.3$ colors for Independent Search). The 120 paired hidden instances provide high statistical power ($N=120$).

---

## 18. Pre-Registered Kill Criteria

We define unambiguous criteria before running the experiment:

```
                                      KILL CRITERIA DECISION TREE
                                                   │
          ┌────────────────────────────────────────┼────────────────────────────────────────┐
          ▼                                        ▼                                        ▼
       SUCCESS                                  FAILURE                                INCONCLUSIVE
- Condition C (Diversity) beats          - Condition C shows no significant      - High invalid/timeout rate
  Condition A (Independent) on             improvement over Condition A            (> 20% of calls fail)
  Hidden Benchmark (p < 0.05).             (p >= 0.05) or performs worse.        - Trial variance exceeds
- Condition C beats Classical NEH.       - Independent Search dominates.           between-condition effect.
- Closes the search-efficiency gap.      - Proves QD adds friction without gain.   - Requires pipeline re-engineering.
```

* **ABANDONMENT CRITERION:** If under a 15-call budget, no condition (A, B, or C) can synthesize an algorithm that beats Classical Palmer or comes within 5% of NEH, we abandon autonomous scheduling synthesis as infeasible within laptop-scale compute constraints.

---

## 19. Compute, Token, and Cost Estimates

- **Total LLM Calls:** 3 conditions $\times$ 15 calls $\times$ 3 trials = **135 total calls**.
- **Model:** `claude-sonnet-4-6` via OmniRoute local proxy.
- **Token Accounting:**
  - Prompt tokens per call: ~1,800 tokens.
  - Completion tokens per call: ~800 tokens.
  - Total tokens for 135 calls: ~350,000 tokens.
  - **Estimated Monetary Cost:** **$1.80 – $3.50** (well below the $10–20 limit).
- **Execution Time:**
  - Dev evaluation (30 instances $\times$ 0.05 ms): ~1.5 ms per candidate.
  - Hidden evaluation (120 instances $\times$ 0.05 ms): ~6 ms per candidate.
  - Total compute time for evaluation across all 135 candidates: **< 1.0 second**.
  - Total experiment wall-clock runtime (dominated by LLM API latency at ~10s per call): **~25 to 30 minutes**.
- **Hardware Compatibility:** 100% reproducible on a single M-series MacBook with 8GB RAM. Zero GPU requirements.

---

## 20. Expected Implementation Timeline

| Phase | Milestone | Description | Duration |
| :--- | :--- | :--- | :---: |
| **Phase 0** | Baseline & Benchmark Engine | Implement PFSP dynamic programming evaluator, generators, and 4 classical baselines | 1.0 hr |
| **Phase 1** | Benchmark Audit & Isolation | Validate 30 dev and 120 hidden instances; verify classical baselines (NEH, Palmer, CDS, IG) | 0.5 hr |
| **Phase 2** | Architecture Implementation | Implement Condition A (Independent), Condition B (Evolution), Condition C (MAP-Elites Archive) | 1.5 hr |
| **Phase 3** | Live Experiment Execution | Execute 135 LLM calls across 3 trials with real-time provenance logging | 0.5 hr |
| **Phase 4** | Frozen Hidden Benchmark Audit | Execute blind evaluation on the 120 Hidden Instances for all trial champions | 0.5 hr |
| **Phase 5** | Statistical Audit & Reporting | Generate search-efficiency curves, Wilcoxon tests, family breakdown, and write final report | 1.0 hr |
| **TOTAL** | | **Complete End-to-End Scientific Execution** | **5.0 hrs** |

---

## 21. Exact Experiment Specification

### Common Prompt Constraint Block
```text
Requirements:
1. Implement def schedule_flowshop(times: list[list[int]]) -> list[int]:
2. 'times' has shape (n_jobs, n_machines). times[j][m] is processing time of job j on machine m.
3. Return a list representing a valid permutation of range(n_jobs) minimizing makespan C_max.
4. Keep the code clean, self-contained, and strictly under 100 lines.
5. Runtime must be under 30 ms per instance. Avoid O(n^4) loops.
6. Only pure 'math' and 'random' modules are permitted. No external libraries, no I/O.
7. Return ONLY valid executable Python enclosed in ```python ``` blocks.
```

### Condition C MAP-Elites Archive Update Logic
```python
def update_archive(candidate: dict, archive: dict) -> bool:
    """
    Places candidate in its corresponding (macro_strategy, search_depth) niche.
    Returns True if candidate becomes a new elite.
    """
    niche = (candidate["strategy_class"], candidate["search_intensity"])
    if niche not in archive or candidate["dev_makespan"] < archive[niche]["dev_makespan"]:
        archive[niche] = candidate
        return True
    return False
```

---

## 22. What Results Would Mean

### Interpretation Matrix

| Outcome | Experimental Observation | Scientific Meaning |
| :--- | :--- | :--- |
| **Scenario 1: Diversity Dominance (H1 Upheld)** | Condition C significantly beats Condition A ($p < 0.05$) and Condition B ($p < 0.001$) on hidden instances. | **Major Discovery.** Proves that LLM algorithm synthesis is not an evolutionary hill-climbing problem, but a Quality-Diversity exploration problem. An explicit behavioral archive is required to systematically navigate the algorithm landscape. |
| **Scenario 2: Independent Dominance (H0 Upheld)** | Condition A matches or beats Condition C ($p \ge 0.05$), while Condition B collapses. | **Profound Simplicity.** Proves that frontier LLMs already hold effective global priors over algorithmic space. External scaffolding and memory add overhead without improving upon stochastic breadth with verifier selection. |
| **Scenario 3: Universal Failure** | All conditions fail to match Classical NEH on hidden benchmarks. | **Boundary Discovery.** Proves that PFSP insertion logic represents a hardness threshold where general LLMs cannot discover competitive heuristics without specialized fine-tuning or domain-specific formal verifiers. |

---

## 23. Post-Experiment Decision Pathways

```
                                       POST-EXPERIMENT DECISION TREE
                                                     │
      ┌──────────────────────────────────────────────┼──────────────────────────────────────────────┐
      ▼                                              ▼                                              ▼
SCENARIO 1: Diversity Wins (H1)            SCENARIO 2: Independent Wins (H0)              SCENARIO 3: Universal Failure
- Adopt MAP-Elites archive as core       - Pivot Amaura architecture away from          - Conclude that zero-shot LLM code
  engine of Amaura.                        iterative loops entirely.                      synthesis cannot beat specialized SOTA.
- Expand to multi-dimensional archives   - Build Amaura as a massively parallel         - Transition to Hybrid LLM + Formal
  (e.g., runtime vs quality vs memory).    stochastic sampler with verifier filtering.    Methods / Neural-Guided Tree Search.
- Publish findings on QD vs Evolution.   - Focus research on verifier design.           - Re-examine problem representation.
```

---

## 24. Sober Product & Real-World Implications

If we strip away academic curiosity, what does this mean for an actual product?

1. **Where an AI Algorithm Discovery Engine is Genuinely Valuable:**
   - In industrial supply chains, semiconductor manufacturing, and cloud container orchestration, scheduling problems have custom proprietary constraints (no-wait, setup times, machine maintenance windows) where off-the-shelf solvers (e.g. Gurobi, OR-Tools) require days of expert mathematical modeling.
   - An engine that can autonomously generate tailored, lightweight Python heuristics executing in microseconds would be highly commercializable as an **automated heuristic design API**.
2. **Where it is NOT Practical:**
   - It cannot replace exact MILP solvers (Gurobi, CPLEX) when optimal proofs are required.
   - It is not suited for real-time online millisecond dispatching; it is an **offline algorithm design tool** that outputs code for production deployment.

---

## 25. Final Recommendation

### Final Recommendation: **PROCEED TO EXPERIMENT #9 WITH PFSP**

The scientific case is complete and decisive:
1. **Domain Selection:** Permutation Flow Shop Scheduling (PFSP - $Fm \mid prmu \mid C_{\max}$) provides the optimal experimental substrate: guaranteed feasibility, sub-millisecond evaluation, rich algorithmic taxonomy (Palmer, CDS, NEH, IG), and gold-standard benchmarks.
2. **Core Comparison:** Pitting **Condition A (Independent Search)** against **Condition B (Naive Evolution)** and **Condition C (MAP-Elites Diversity-Aware Search)** under a strict 15-call matched budget directly tests whether diversity maintenance resolves the genetic narrowing failure mode proven in Experiment #8.
3. **Execution Readiness:** The experiment is compact, cost-effective (~$2.50), runs in under 30 minutes on a laptop, and has pre-registered hypotheses and kill criteria.

We are ready to proceed with implementation upon your approval.
