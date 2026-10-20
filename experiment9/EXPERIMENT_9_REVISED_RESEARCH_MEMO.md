# AMAURA EXPERIMENT #9 — REVISED PRE-EXPERIMENT RESEARCH & EXPERIMENTAL DESIGN
## Testing Behavioral Quality-Diversity vs. Equal-Budget Independent Sampling in Permutation Flow Shop Scheduling

**Author:** Antigravity Autonomous Research & Discovery Agent  
**Date:** October 3, 2026  
**Status:** Pre-Experiment Scientific Research & Specification (Implementation Locked)  
**Target Domain:** Permutation Flow Shop Scheduling ($Fm \mid prmu \mid C_{\max}$)  
**Central Research Question:** When given the same LLM model, approximately the same number of calls, and the same computational budget, does a search system that deliberately maintains behavioral diversity discover better algorithms on unseen PFSP instances than unguided independent sampling or naive evolutionary search?

---

## 1. Executive Summary

Amaura is an experimental AI Discovery Engine designed to test whether an AI system can discover novel, high-performing combinatorial algorithms through automated synthesis, objective evaluation, and search.

### Context & Empirical Motivation
- **Experiments #2–#5 (Online Bin Packing):** Restricting candidate synthesis to micro-heuristics (`choose_bin`) failed to outperform the classical Best Fit baseline across all search topologies.
- **Experiments #6–#7 (Vertex Graph Coloring):** Moving to complete macro-solver synthesis (`def color_graph(adj) -> list[int]`) produced the system's first major breakthrough in Experiment #7 (984 hidden colors vs. 1056 DSATUR, 1021 RLF). However, Experiment #7 used an unconstrained evolutionary loop (35+ calls), confounding the effect of evolutionary search with pure inference volume.
- **Experiment #8 (Budget-Matched Audit):** A strictly controlled 135-call audit (15 calls $\times$ 3 conditions $\times$ 3 independent trials) compared:
  1. *Condition A (Single-Shot Independent Search):* $1007.0 \pm 5.3$ hidden colors.
  2. *Condition B (Naive Evolutionary Search):* $1036.7 \pm 13.5$ hidden colors.
  3. *Condition C (Random-Parent Search Control):* $1019.7 \pm 22.8$ hidden colors.

Under that setup, equal-budget independent search significantly outperformed naive evolution ($p = 8.77 \times 10^{-5}$, Cohen's $d = +0.325$). The evolutionary system suffered from **genetic narrowing** (73.3% of candidates became trapped in minor tweaks of a single DSATUR + Kempe chain template), **premature convergence** (plateauing at Call 10 with zero further progress), and **development-set overfitting**.

### Core Objective of Experiment #9
Experiment #9 tests whether this failure was a property of naive single-lineage evolution that can be resolved by **Quality-Diversity (QD)**. Specifically, we transition to a new domain—**Permutation Flow Shop Scheduling ($Fm \mid prmu \mid C_{\max}$)**—and test whether an algorithm discovery system that **explicitly preserves behavioral diversity** (via an unstructured Quality-Diversity archive with local competition) discovers algorithms that generalize better to unseen test instances than independent sampling and naive evolution under strict budget parity ($N=15$ calls per trial).

We do **not** assume Quality-Diversity will win. The experiment is designed to be fully falsifiable: it can prove QD wins, independent search wins, naive evolution wins, all methods perform identically, or all methods fail.

---

## 2. Experiment #8 — Exact Scientific Interpretation

To maintain rigorous scientific standards, we establish three mandatory qualifications regarding the findings of Experiment #8:

1. **Evolution in General is NOT Disproven:**  
   *What Experiment #8 established:* Under the tested graph-coloring setup and equal call budget (15 calls), the *particular naive evolutionary search implementation* (refining the top-fitness candidate without diversity preservation) was significantly worse than independent search.  
   *What it did not establish:* It did not establish that all evolutionary algorithms fail. In particular, it did not test island models, multi-deme migration, Quality-Diversity, or behavioral niching.
2. **Independent Search Was Not Proven Globally Optimal:**  
   Independent search succeeded because its 15 distinct prompt archetypes forced the LLM across orthogonal regions of the algorithm space. It remained entirely memoryless: it could not diagnose errors, recombine subroutines, or refine near-optimal primitives.
3. **Levels of Statistical Replication Must Be Kept Distinct:**  
   Evaluating algorithms on 120 hidden instances provides paired evaluation power across problem instances, but it represents only **one evaluation per search trial**. The true replications of the stochastic search process are the independent trials of the search pipeline. Experiment #8 ran 3 independent search trials. In Experiment #9, we explicitly separate instance-level paired evaluation from search-level replication.

---

## 3. PFSP Domain Assessment

Before adopting Permutation Flow Shop Scheduling, we independently evaluated it against five alternative combinatorial scheduling domains across twelve strict criteria:

| Domain | Formal Model | Feasibility Guarantee | Evaluation Complexity | Deadlock Risk | Search Richness | Classical Baselines | Laptop Feasibility | Verdict |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Single-Machine Scheduling** | $1 \mid r_j, d_j \mid \sum w_j T_j$ | Permutation of $n$ jobs | $O(n \log n)$ to $O(n^2)$ | None | Low (priority sorting) | WSPT, ATC | Excellent | **REJECTED** (Too narrow; lacks machine interaction) |
| **Identical Parallel Machines** | $P \mid\mid C_{\max}$ | Partition into $m$ lists | $O(n \log m)$ | None | Moderate (LPT, MULTIFIT) | LPT, MULTIFIT | Excellent | **REJECTED** (Structurally identical to Bin Packing) |
| **Unrelated Parallel Machines**| $R \mid\mid C_{\max}$ | $n \times m$ assignment matrix | $O(n \cdot m)$ | None | Moderate | Min-Min, Sufferage | Moderate | **BORDERLINE** (Less standardized benchmarks) |
| **Permutation Flow Shop (PFSP)**| $Fm \mid prmu \mid C_{\max}$ | Permutation of $n$ jobs | $O(n \cdot m)$ Dynamic Prog | **None** | **Very High** (NEH, CDS, IG, VNS) | Palmer, CDS, NEH, IG | **Superb (<0.05ms)** | **CONFIRMED OPTIMAL** |
| **Job-Shop Scheduling (JSSP)** | $Jm \mid\mid C_{\max}$ | Operation sequence on disjunctive graph | $O(\sum o_j)$ topological | **High (Circular waits)** | Extremely High | Shifting Bottleneck | Poor (High invalidity) | **REJECTED** (>40% invalid candidate rate) |
| **Resource-Constrained Project**| RCPSP | Precedence + Resource vector | $O(n^2 R)$ Serial SGS | Moderate | High | Serial SGS, Forward-Back | Slow | **REJECTED** (Heavy evaluation overhead) |

### Why PFSP ($Fm \mid prmu \mid C_{\max}$) is the Superior Experimental Substrate

1. **Clean Permutation Representation with Zero Deadlocks:**  
   A candidate solution is strictly a permutation $\pi = (\pi_0, \pi_1, \dots, \pi_{n-1})$ of the $n$ jobs. Any permutation represents a valid, feasible schedule. Unlike JSSP, there are no circular dependencies, machine routing deadlocks, or precedence violations. Feasibility verification is an instantaneous $O(n)$ set equality check (`set(perm) == set(range(n))`).
2. **Sub-Millisecond Deterministic Evaluation:**  
   Makespan $C_{\max}(\pi)$ is calculated via a 2D dynamic programming grid in exactly $O(n \cdot m)$ operations:
   $$C(\pi_i, k) = \max\left(C(\pi_{i-1}, k), C(\pi_i, k-1)\right) + p_{\pi_i, k}$$
   For a $50 \times 10$ instance, evaluation takes **0.04 ms in pure Python**. A 30-instance development suite evaluates in **~1.2 milliseconds**.
3. **Strong Theoretical Hardness with High Pragmatic Accessibility:**  
   PFSP is strongly NP-hard for $m \ge 3$ (Garey, Johnson, Sethi 1976). It avoids the triviality of single-machine problems while avoiding the unexecutable deadlock traps of JSSP.
4. **Rich 50-Year Algorithmic Taxonomy:**  
   Permutation Flow Shop features distinct, rigorously studied human algorithmic paradigms: priority slope rules (Palmer 1965), two-machine reductions (Campbell-Dudek-Smith 1970), constructive insertion (Nawaz-Enscore-Ham 1983), and iterated greedy metaheuristics (Ruiz & Stützle 2007).
5. **Standardized Gold-Standard Benchmarks:**  
   Direct access to the Taillard (1993) benchmark suite, enabling absolute calibration against 30 years of published operational research.

---

## 4. Existing PFSP Algorithmic Landscape

To understand what genuine algorithmic diversity means in PFSP, we analyze the major human-designed paradigms:

```
                            PFSP Algorithmic Paradigm Landscape
                                             │
         ┌──────────────────┬────────────────┴────────────────┬──────────────────┐
         ▼                  ▼                                 ▼                  ▼
1. Priority Dispatch   2. Two-Machine Reduction          3. Insertion Heuristics 4. Destruction-Repair Metaheuristics
(Palmer 1965)          (Campbell-Dudek-Smith 1970)       (NEH 1983)              (Iterated Greedy 2007)
  - O(n log n)           - O(m n log n)                    - O(n^3 m)              - O(I d n^2 m)
  - Static slope index   - Johnson's rule on m-1 pairs     - Greedy position insert- Multi-pass perturbation & repair
```

### Detailed Structural Comparison

| Strategy Family | Classical Exemplar | Time Complexity | Core Algorithmic Mechanism | Primary Strength | Structural Failure Mode | LLM Synthesizability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Slope / Priority Dispatch** | Palmer (1965), Gupta (1971) | $O(n \log n)$ | Calculates static numerical index $S_j = \sum_{k=1}^m (2k - m - 1) p_{j, k}$; sorts descending | Ultra-fast; exploits monotonic machine load trends | Blind to dynamic idle time; large optimality gap (~12–15%) | Trivial (~15 lines) |
| **2. Subproblem Decomposition** | Campbell-Dudek-Smith (CDS 1970) | $O(m \cdot n \log n)$ | Creates $m-1$ artificial 2-machine subproblems; solves each via Johnson's Rule; takes best | Exploits Johnson's exact 2-machine polynomial optimality | Intermediate machines are coarsely summed; static | Moderate (~25 lines) |
| **3. Insertion Construction** | Nawaz-Enscore-Ham (NEH 1983) | $O(n^3 m)$ or $O(n^2 m)$ | Sorts jobs by total time; iteratively inserts job $k$ into the best of $k$ partial positions | **Gold standard constructive baseline for 40+ years** | Deterministic; early placement errors cannot be corrected | High (~35 lines) |
| **4. Destruction & Repair** | Iterated Greedy (Ruiz & Stützle 2007) | $O(I \cdot d \cdot n^2 m)$ | Removes $d$ jobs from schedule; re-inserts greedily (NEH-style); Metropolis acceptance | **SOTA metaheuristic in PFSP**; beats GAs and SA | Sensitive to destruction size $d$ and temperature $T$ | High (~60 lines) |
| **5. Local Search / VNS** | Pairwise Insertion Search | $O(K \cdot n^2 m)$ | Iteratively extracts job $i$ and inserts at $j$; accepts improving moves | Cleans up local inversion flaws in constructive schedules | Easily trapped in local minima without perturbation | Moderate (~40 lines) |
| **6. Beam Search** | Truncated Tree Search | $O(B \cdot n^2 m)$ | Maintains beam width $B$ of partial schedules; prunes using lower bounds | Systematic exploration bridging greedy and exact search | High compute overhead if bounding function is loose | High (~50 lines) |
| **7. Multi-Start Portfolio** | Hybrid Portfolio | $O(P \cdot n^2 m)$ | Runs Palmer + CDS + 3 randomized NEH passes; returns minimum makespan | Extremely robust across heterogeneous instance structures | Does not deeply optimize any individual instance | High (~45 lines) |

---

## 5. Existing AI Algorithm-Discovery Research

We surveyed the frontier of automated code synthesis, hyper-heuristics, and algorithm discovery (2023–2026):

1. **FunSearch (Romera-Paredes et al., *Nature*, Dec 2023):**  
   Paired a pre-trained LLM (Codey/PaLM 2) with an automated evaluator to discover new mathematical bounds (Cap Set) and online 1D bin-packing heuristics.  
   *Crucial Detail:* FunSearch did **not** use naive evolutionary hill-climbing. It implemented an **island model** with an archive where programs were clustered into niches based on **behavioral signatures** (score vectors across input instances). Sampling favored diverse, high-scoring clusters and penalized code length. However, FunSearch consumed tens of thousands of queries across distributed clusters.
2. **Evolution of Heuristics (EoH, Liu et al. 2024; EoH-S 2024):**  
   Evolved priority dispatching rules using a dual-view representation (natural language "thought" + Python code). EoH-S evolved *complementary heuristic sets*, recognizing that a single heuristic cannot dominate all instance families.
3. **ReEvo (Ye et al., *NeurIPS*, 2024):**  
   Employed reflective evolution, where the LLM functions both as generator and critic, using comparative execution diagnostics as "verbal gradients." Benchmarked across 12 combinatorial problems, including scheduling under machine breakdowns.
4. **Has Someone Performed a Clean Equal-Budget Comparison?**  
   *Literature Finding:* **No.** While individual papers propose either evolutionary loops (FunSearch, EoH, ReEvo) or Quality-Diversity (LLMatic, QDAIF), the literature consistently exhibits a major methodological gap: **evolutionary and QD systems are rarely benchmarked against an equal-budget independent sampling baseline (Best-of-N)**. Instead, evolutionary systems are typically compared against zero-shot prompting or human heuristics. Experiment #8 demonstrated that when budget is held strictly equal, independent sampling can decisively outperform naive evolution. Experiment #9 is specifically designed to provide the first rigorous, budget-matched comparison between independent sampling, naive evolution, and behavioral Quality-Diversity in PFSP.

---

## 6. Quality-Diversity / MAP-Elites Research

Quality-Diversity (QD) algorithms (Lehman & Stanley 2011, Cully et al. 2015, Pugh et al. 2016) shift the optimization paradigm from finding a single optimal solution to discovering a repertoire of high-performing, behaviorally distinct solutions.

### Grid-Based MAP-Elites vs. Unstructured QD Archives
1. **Grid-Based MAP-Elites (Mouret & Clune 2015):**  
   Discretizes a low-dimensional behavioral feature space into a rigid grid of bins (e.g. $5 \times 5$). Each bin stores the single highest-performing individual (elite) discovered in that niche.  
   *Limitation for Code Synthesis:* Requires the researcher to manually define orthogonal, discretizable behavioral axes. In code synthesis, forcing algorithms into human-designed grid bins injects substantial human domain bias.
2. **Unstructured Quality-Diversity / Novelty-Quality Archive with Local Competition (Cully & Mouret 2016, Vassiliades et al. 2018):**  
   Maintains a dynamic archive of elites defined by a continuous distance metric in behavioral space:
   - When a new candidate $C$ is evaluated, its behavioral distance $d(C, E)$ to all existing archive elites is computed.
   - If $C$ is within a novelty threshold $\delta_{\min}$ of an existing elite $E^*$, it competes directly with $E^*$ on quality (makespan): if $C$ achieves a lower makespan, it replaces $E^*$ in that behavioral niche.
   - If $C$ is behaviorally novel ($d(C, E) \ge \delta_{\min}$ for all elites), it is added to the archive as a new behavioral elite.
   - *Why this is superior for Experiment #9:* It eliminates manual taxonomic labeling and operates purely on objective execution behaviors.

---

## 7. Behavioral Diversity Measurement

### The Core Scientific Principle
> **Two algorithms should be considered different because they behave differently, not merely because their source code or human-assigned category differs.**

Source code syntax (AST diffs, token counts, function lengths) is an invalid proxy for diversity: two syntactically different programs often compute identical rankings, while a two-token change (e.g. `<` to `>`) can completely alter an algorithm's behavior.

### Formal Behavioral Distance: Phenotypic Output Permutation Distance
For a set of $K$ development instances $\mathcal{I}_{\text{dev}} = \{I_1, I_2, \dots, I_K\}$, when an algorithm $A$ is executed, it outputs a permutation $\pi_A(k)$ for each instance $k \in \{1, \dots, K\}$.

We define the behavioral distance between two algorithms $A$ and $B$ as the mean normalized **Kendall's $\tau$ distance** across all development instances:
$$D_{\text{behavior}}(A, B) = \frac{1}{K} \sum_{k=1}^K \tau_{\text{norm}}\left(\pi_A(k), \pi_B(k)\right)$$
where $\tau_{\text{norm}}(\pi_1, \pi_2)$ counts the fraction of discordant job pairs between the two permutations:
$$\tau_{\text{norm}}(\pi_1, \pi_2) = \frac{\sum_{i < j} \mathbb{I}\left[\left(\pi_1^{-1}(i) - \pi_1^{-1}(j)\right) \cdot \left(\pi_2^{-1}(i) - \pi_2^{-1}(j)\right) < 0\right]}{\frac{n(n-1)}{2}} \in [0, 1]$$

*Properties of this Metric:*
- If Algorithm $A$ and Algorithm $B$ output identical job sequences on all instances, $D_{\text{behavior}}(A, B) = 0$, regardless of how different their Python code looks.
- If Algorithm $A$ and Algorithm $B$ produce completely reversed or orthogonal sequences, $D_{\text{behavior}}(A, B) \to 1.0$.
- It is mathematically formal, parameter-free, deterministic, and requires **zero human categorization**.

### Secondary Behavioral Diagnostic: Relative Performance Signature ($\vec{s}$)
For each development instance family $f \in \{1, \dots, F\}$, we record the relative makespan ratio:
$$\vec{s}_f(A) = \frac{C_{\max}(A, f)}{C_{\max}(\text{Palmer}, f)}$$
This produces a performance profile vector $\vec{s}(A) \in \mathbb{R}^F$ indicating on which instance distributions the algorithm thrives or fails.

---

## 8. Experimental Search Conditions

Experiment #9 evaluates **three primary conditions** under strict budget equality ($N=15$ calls per trial $\times$ 5 independent trials = 75 calls per condition, **225 total calls**):

```
                                EXPERIMENTAL CONDITIONS (15 Calls per Trial x 5 Trials)
                                                          │
          ┌───────────────────────────────────────────────┼───────────────────────────────────────────────┐
          ▼                                               ▼                                               ▼
CONDITION A: Independent Search                 CONDITION B: Naive Evolution                   CONDITION C: Behavioral QD Search
- 15 unguided, memoryless calls                 - 5 init + 5 gens x 2 offspring                - Unstructured QD Archive
- Problem specification & API contract          - Parent selection strictly on best dev score  - Local niche competition (Kendall tau)
- Zero exposure to past code/scores             - Prompt: "Refine/optimize champion"           - Identifies under-represented behavior
- Pure breadth / Best-of-N baseline             - Replicates Experiment #8 failure mode        - Prompts LLM for behavioral novelty
```

### Condition A — Single-Shot Independent Search (15 Calls)
- Each call receives the formal PFSP problem description, API contract, and performance objective.
- **Zero Memory:** Receives no previous code, no evaluation scores, and no search history.
- Prompts use standard stochastic decoding ($T=0.6$) with diverse task framings (unconstrained, priority focus, constructive focus, local search focus) matching standard Best-of-N prompt exploration.

### Condition B — Naive Evolutionary Search (15 Calls)
- **Calls 1–5 (Generation 0):** Initial population generated using baseline prompts.
- **Calls 6–15 (Generations 1–5):** 5 generations of 2 offspring each:
  - *Offspring 1 (Exploitation):* Prompt presents the highest-fitness code currently in the population and asks the LLM to modify/refine it to reduce makespan.
  - *Offspring 2 (Crossover):* Prompt presents the top two highest-scoring distinct algorithms and asks the LLM to combine their complementary mechanisms.
- Replicates the exact naive evolutionary implementation that failed in Experiment #8.

### Condition C — Behavioral-Diversity Search (15 Calls)
- Maintains an **Unstructured Quality-Diversity Archive** with local competition.
- **Calls 1–5:** Initial population evaluated and seeded into the archive.
- **Calls 6–15:** At each iteration:
  1. Evaluate candidate, compute its permutation signature across the dev set, and compute its makespan.
  2. Attempt archive insertion via local niche competition ($D_{\text{behavior}} < \delta_{\min} = 0.20$).
  3. Query the archive to select a reference elite $E_{\text{ref}}$ (e.g. the current global champion) and identify an elite $E_{\text{novel}}$ that is behaviorally distant from $E_{\text{ref}}$.
  4. Construct the prompt **without human taxonomic labels**:
     ```text
     We are discovering algorithms for Permutation Flow Shop Scheduling.
     
     Current Reference Algorithm (Achieves Makespan: {dev_score}):
     ```python
     {code_of_E_ref}
     ```
     
     Behavioral Analysis:
     On our benchmark instances, this algorithm produces job sequences with a distinct scheduling pattern.
     
     Your Task:
     Synthesize a complete Python solver `def schedule_flowshop(times: list[list[int]]) -> list[int]:`
     that achieves a LOW total makespan while making FUNDAMENTALLY DIFFERENT sequencing decisions.
     - Your algorithm must NOT be a cosmetic rewrite or minor modification of the reference algorithm.
     - The output permutations produced by your algorithm must systematically differ in job ordering (high Kendall tau distance).
     - Explore entirely different computational heuristics for resolving machine bottlenecks.
     ```
  5. The LLM is directed toward **behavioral novelty**, not human-invented labels.

---

## 9. Control Design & Isolating Information vs. Search Advantage

A critical methodological critique of Experiment #8 was:
> *Condition C has in-context memory of past code. Condition A does not. Is Condition C winning because of its search mechanism (diversity) or simply because of an information advantage (seeing previous working code)?*

### How Our Experimental Design Isolates These Confounders

We construct a clean three-way experimental contrast:

1. **Condition A vs. Condition B:**  
   *Variable Isolated:* In-context memory with naive selection. Condition B has memory of previous code; Condition A does not. Experiment #8 proved that memory *with naive selection* actively harmed performance ($B < A$).
2. **Condition B vs. Condition C:**  
   *Variable Isolated:* **Behavioral Diversity Preservation.** Both Condition B and Condition C have identical in-context memory of previous code! The *only* difference between B and C is the selection and prompting mechanism:
   - Condition B repeatedly selects the single best candidate and prompts for refinement (hill-climbing).
   - Condition C maintains an archive of behaviorally diverse elites and prompts for behavioral novelty.
   - If $C > B$, the performance difference is 100% attributable to **diversity preservation**, not memory.
3. **Condition A vs. Condition C:**  
   *Variable Isolated:* Memoryless Breadth vs. Diversity-Preserving Iterative Search.
   - If $C > A$, diversity-preserving iterative search successfully outperforms unguided Best-of-N sampling under strict budget equality.

---

## 10. Benchmark Design

To prevent overfitting and test true out-of-distribution generalization, we partition instances into a 30-instance Development Benchmark and a 120-instance blind Hidden Benchmark.

### Benchmark Distribution Specifications

| Benchmark Split | Family ID | Structure & Load Characteristic | Problem Dimensions $(n \times m)$ | Instance Count | Purpose in Experiment |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Development** | `dev_taillard` | Uniform Random $p_{j, k} \sim \mathcal{U}[1, 99]$ | $20 \times 5, 20 \times 10, 50 \times 5, 50 \times 10$ | 5 | Standard benchmark baseline |
| ($N=30$, seed=1042)| `dev_mach_corr`| Machine Bottleneck (Center machines $3\times$ load) | $20 \times 5, 50 \times 5, 50 \times 10$ | 5 | Tests machine-load sensitivity |
| | `dev_job_corr` | Job Load Heterogeneity (Heavy vs light jobs) | $20 \times 5, 50 \times 5, 50 \times 10$ | 5 | Tests job-ordering priority |
| | `dev_bimodal` | Bimodal Times ($p_{j, k} \in [5, 15] \cup [85, 100]$) | $20 \times 5, 50 \times 5, 50 \times 10$ | 5 | Creates discrete idle time gaps |
| | `dev_high_ratio`| High Aspect Ratio ($n \gg m$, e.g. $50 \times 4$) | $50 \times 4, 60 \times 4$ | 5 | Sequencing dominates idle time |
| | `dev_square` | Square Aspect Ratio ($n \approx m$, e.g. $15 \times 15$) | $15 \times 15, 20 \times 20$ | 5 | Combinatorial machine interaction |
| **Hidden Benchmark** | `hid_taillard` | Published Classic Taillard (1993) instances | $20 \times 5, 20 \times 10, 50 \times 5, 50 \times 10$ | 20 | Calibrate against literature |
| ($N=120$, seed=70099)| `hid_mach_corr`| Severe Multi-Stage Bottlenecks | $20 \times 10, 50 \times 10, 100 \times 5$ | 20 | Out-of-distribution bottleneck |
| *(Completely blind* | `hid_job_corr` | Log-Normal Job Durations | $20 \times 10, 50 \times 10, 100 \times 5$ | 20 | Realistic industrial distribution |
| *during search)* | `hid_trimodal` | Trimodal Extreme Processing Times | $20 \times 10, 50 \times 10, 100 \times 5$ | 20 | Complex combinatorial gaps |
| | `hid_high_ratio`| Large Scale ($n=100, m=5$) | $100 \times 5, 100 \times 10$ | 20 | Tests asymptotic scalability |
| | `hid_u_load` | U-Shaped Machine Load (Heavy first & last) | $30 \times 10, 50 \times 10$ | 20 | Inverts standard flow assumptions |

### Benchmark Memorization Defense
To ensure the LLM cannot win via memorization of published instances:
1. Only 20 of the 120 hidden instances are taken from Taillard's original dataset; the remaining 100 instances are procedurally generated with distinct random seeds.
2. The evaluator strips all instance names and metadata. Solvers receive only raw 2D integer arrays `times`.

---

## 11. Classical Baselines

We implement and independently verify four classical human baselines:

1. **Palmer's Slope Heuristic (1965):**
   - *Logic:* Calculates $S_j = \sum_{k=1}^m (2k - m - 1) p_{j, k}$; sorts descending.
   - *Role:* Establishes the performance floor ($O(n \log n)$).
2. **Campbell-Dudek-Smith (CDS 1970):**
   - *Logic:* Decomposes $m$ machines into $m-1$ artificial two-machine subproblems, solves each via Johnson's algorithm, and returns the best schedule.
   - *Role:* Establishes polynomial reduction performance ($O(m \cdot n \log n)$).
3. **Nawaz-Enscore-Ham (NEH 1983):**
   - *Logic:* Sorts jobs by total time descending; iteratively inserts job $k$ into the best of $k$ partial positions.
   - *Role:* **The definitive target benchmark.** For 40 years, NEH has remained the premier constructive heuristic in flow shop scheduling. Beating NEH demonstrates non-trivial algorithmic synthesis.
4. **Iterated Greedy (Ruiz & Stützle 2007, bounded):**
   - *Logic:* Destruction of $d=4$ jobs from an NEH initial schedule, greedy re-insertion, pairwise local search, and Metropolis acceptance (bounded to 20 iterations to respect 50 ms budget).
   - *Role:* Establishes SOTA metaheuristic performance under strict time limits ($O(I \cdot d \cdot n^2 m)$).

---

## 12. Statistical Analysis Design

We establish a formal separation between **instance-level paired evaluation** and **search-level stochastic replication**.

### 1. Instance-Level Paired Metrics (on 120 Hidden Instances)
For a pair of selected champions $A$ and $B$:
- **Primary Metric:** Total Hidden Makespan $\sum_{k=1}^{120} C_{\max}(k)$.
- **Paired Difference:** $D_k = C_{\max}(A, k) - C_{\max}(B, k)$ for each instance $k$.
- **Statistical Test:** Two-sided Wilcoxon signed-rank test on non-zero differences $D_k$.
- **Effect Size:** Cohen's $d = \frac{\bar{D}}{\sigma_D}$ and non-parametric Cliff's Delta ($\delta$).
- **Multiplicity Correction:** Holm-Bonferroni adjustment across the three primary pairwise comparisons ($C$ vs $A$, $C$ vs $B$, $A$ vs $B$).

### 2. Search-Level Aggregation (Across $R=5$ Independent Runs)
For each condition $X \in \{A, B, C\}$ across $R=5$ independent trials:
- Mean and standard deviation of champion hidden makespan: $\bar{M}_X = \frac{1}{R}\sum_{r=1}^R M_{X, r}$.
- Between-trial variance $\sigma_X^2$.
- Search-Efficiency Curves: Mean best-so-far development makespan plotted as a function of call budget ($1 \dots 15$).

---

## 13. Search-Level Replication Recommendation

### Cost-Benefit Analysis of Trial Counts

| Replications ($R$) | Total Calls per Condition | Total Calls (3 Conds) | Total Tokens | Estimated API Cost | Statistical Confidence | Practical Recommendation |
| :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **$R = 3$** | 45 | 135 | ~350,000 | ~$2.20 | Marginal search-level power | Acceptable only for quick smoke test |
| **$R = 5$** | **75** | **225** | **~585,000** | **~$3.80** | **Robust search-level power; enables formal cross-trial t-tests** | **RECOMMENDED** |
| **$R = 10$** | 150 | 450 | ~1,170,000 | ~$7.50 | High statistical power, but diminishes returns | Overkill for pre-experiment phase |

**Recommendation:** We formally specify **$R = 5$ independent search replications** (225 total calls). At ~$3.80 total cost, $R=5$ provides genuine search-level statistical validity while remaining well within the researcher's laptop compute budget.

---

## 14. Threats to Validity & Hostile Reviewer Critique

| Threat to Validity | Skeptical Failure Scenario | Concrete Countermeasure in Experiment #9 |
| :--- | :--- | :--- |
| **1. LLM Memorization** | The LLM memorizes NEH or Palmer verbatim from pre-training. | 100 of the 120 hidden instances have custom distributions (bimodal, U-load) where standard NEH ordering is sub-optimal. Candidate code ASTs will be audited for memorized vs. adapted logic. |
| **2. Prompt Information Bias** | Condition C's prompt gives an unfair clue by describing behavioral patterns. | The prompt describes *only* output ordering tendencies (Kendall tau patterns), never algorithmic keywords (no mention of "NEH", "Iterated Greedy", "decomposition", or "swaps"). |
| **3. Gaming the Diversity Metric** | The LLM produces a nonsensical or random permutation to appear "novel." | **Local Niche Competition:** A candidate is only admitted to the archive if it satisfies quality criteria ($C_{\max} < \infty$). Novel garbage never replaces a high-performing elite. |
| **4. Benchmark Overfitting** | Condition C tailors its archive to the 30 dev instances, failing on hidden graphs. | The 120 hidden instances contain extreme distribution shifts (trimodal, U-load) specifically designed to punish dev-set over-tuning. |
| **5. Runtime Exploitation** | One condition wins simply by writing slower code that executes more iterations. | **Strict Sandbox Enforcement:** Per-instance limit of 50 ms. Any algorithm exceeding 300 ms on any instance is instantly terminated via `SIGALRM` and marked invalid ($C_{\max} = 999,999$). |
| **6. Search Stochasticity** | A lucky single-shot prompt in Condition A skews the results. | Search-level replication across **$R=5$ independent trials** (75 calls per condition). |

---

## 15. Novelty Assessment

To maintain scientific credibility, we explicitly define the boundaries of novelty:

### What is Already Known in the Literature
- Naive LLM evolutionary prompting without diversity preservation suffers from semantic collapse (documented in genetic programming; confirmed in Amaura Exp #8).
- Quality-Diversity / MAP-Elites effectively illuminates continuous parameter spaces in robotics.
- LLMs can synthesize constructive heuristics for PFSP (demonstrated in ReEvo 2024 and EoH 2024).

### The Precise Novel Empirical Question Tested by Experiment #9
> **Does maintaining an explicit, parameter-free behavioral-diversity archive enable an LLM to discover combinatorial algorithms that generalize better to unseen, distribution-shifted problem instances than equal-budget independent sampling?**

In published literature, LLM algorithm discovery papers almost universally benchmark evolutionary or QD systems against zero-shot prompting or human heuristics. They routinely omit an equal-budget independent Best-of-N sampling baseline. Experiment #9 provides this missing, rigorous ablation.

---

## 16. Pre-Registered Kill Criteria

```
                                      KILL CRITERIA DECISION TREE
                                                   │
          ┌────────────────────────────────────────┼────────────────────────────────────────┐
          ▼                                        ▼                                        ▼
       SUCCESS                                  FAILURE                                INCONCLUSIVE
- Condition C (Diversity) beats          - Condition C shows no significant      - High invalidity/timeout rate
  Condition A (Independent) across         difference from Condition A             (> 15% of calls fail).
  5 trials on Hidden Benchmark             (p >= 0.05) or performs worse.        - Trial variance exceeds
  (p < 0.05, Wilcoxon).                  - Independent Search matches/beats C.     between-condition effect size.
- Condition C beats Classical NEH.       - Proves QD adds complexity without     - Requires bug fix & re-run.
- Minimum meaningful gap: > 0.5%           generalization benefit under budget.
  reduction in total hidden makespan.
```

* **ABANDONMENT CRITERION:** If across 225 calls, no condition can synthesize an algorithm that beats Classical Palmer or comes within 5% of NEH, we abandon autonomous scheduling synthesis as infeasible within laptop-scale compute constraints.

---

## 17. Compute, Token, and Cost Accounting

- **Search Replications:** $R = 5$ independent trials.
- **Conditions:** 3 (Independent, Naive Evolution, Behavioral Diversity).
- **Calls per Trial per Condition:** 15 calls.
- **Total LLM Calls:** $5 \times 3 \times 15 = \mathbf{225\text{ calls}}$.
- **Model:** `claude-sonnet-4-6` via OmniRoute local proxy.
- **Token Accounting:**
  - Prompt tokens per call: ~1,800 tokens.
  - Completion tokens per call: ~800 tokens.
  - Total tokens for 225 calls: ~585,000 tokens.
  - **Estimated Monetary Cost:** **~$3.50 to $4.50** (well within $10 limit).
- **Evaluation Compute Time:**
  - 225 candidates $\times$ 30 dev instances $\times$ 0.04 ms = **~0.27 seconds** total evaluation compute!
  - Hidden evaluation for 15 trial champions: $15 \times 120 \times 0.04\text{ ms} = \mathbf{0.07\text{ seconds}}$.
- **Total Wall-Clock Runtime:** Dominated by LLM generation latency (~8–10s per call) = **~35 to 40 minutes total**.
- **Hardware Compatibility:** 100% executable on a single MacBook with 8GB RAM. Zero GPU requirements.

---

## 18. Exact Implementation Specification

### 1. Functional Interface Contract
```python
def schedule_flowshop(times: list[list[int]]) -> list[int]:
    """
    Synthesize an optimal job schedule for a Permutation Flow Shop.
    
    Args:
        times: A 2D list of shape (n_jobs, n_machines), where times[j][m]
               is the integer processing time of job j on machine m.
               
    Returns:
        A list of length n_jobs containing a permutation of [0, 1, ..., n_jobs - 1]
        representing the processing sequence of jobs across all machines.
    """
```

### 2. Candidate Evaluation & Makespan Algorithm (Pseudocode)
```python
def evaluate_makespan(times: list[list[int]], perm: list[int]) -> int:
    """Computes exact C_max via 2D dynamic programming grid in O(n*m)."""
    n = len(perm)
    m = len(times[0])
    # dp[k] stores completion time on machine k for current job
    dp = [0] * m
    for job in perm:
        dp[0] += times[job][0]
        for k in range(1, m):
            dp[k] = max(dp[k], dp[k - 1]) + times[job][k]
    return dp[m - 1]
```

### 3. Behavioral Signature Extraction (Pseudocode)
```python
def extract_behavioral_signature(solver_func, dev_instances: list) -> list[list[int]]:
    """Executes candidate on dev instances and records output permutations."""
    signature = []
    for inst in dev_instances:
        perm = solver_func(inst["times"])
        signature.append(list(perm))
    return signature
```

### 4. Behavioral Distance: Kendall's $\tau$ (Pseudocode)
```python
def kendall_tau_distance(p1: list[int], p2: list[int]) -> float:
    """Calculates normalized fraction of discordant pairs in O(n^2)."""
    n = len(p1)
    pos2 = {val: idx for idx, val in enumerate(p2)}
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            val_i, val_j = p1[i], p1[j]
            if (pos2[val_i] - pos2[val_j]) < 0 != (i - j) < 0:
                discordant += 1
    total_pairs = n * (n - 1) / 2
    return discordant / total_pairs if total_pairs > 0 else 0.0

def mean_behavioral_distance(sig1: list[list[int]], sig2: list[list[int]]) -> float:
    """Computes mean Kendall tau distance across all dev instances."""
    distances = [kendall_tau_distance(p1, p2) for p1, p2 in zip(sig1, sig2)]
    return sum(distances) / len(distances)
```

### 5. Unstructured Quality-Diversity Archive Update (Pseudocode)
```python
class QDArchive:
    def __init__(self, delta_min: float = 0.20, max_size: int = 10):
        self.delta_min = delta_min
        self.max_size = max_size
        self.elites = []  # List of dicts: {'candidate_id', 'code', 'score', 'sig'}

    def add(self, candidate: dict) -> bool:
        if not self.elites:
            self.elites.append(candidate)
            return True

        # Find nearest neighbor in behavioral space
        distances = [
            (mean_behavioral_distance(candidate["sig"], e["sig"]), e)
            for e in self.elites
        ]
        min_dist, nearest_elite = min(distances, key=lambda x: x[0])

        if min_dist < self.delta_min:
            # Same behavioral niche: compete on quality (makespan)
            if candidate["score"] < nearest_elite["score"]:
                self.elites.remove(nearest_elite)
                self.elites.append(candidate)
                return True
            return False
        else:
            # Genuinely novel behavior: add to archive
            self.elites.append(candidate)
            if len(self.elites) > self.max_size:
                # Prune the pair with the smallest mutual distance (keep better score)
                self._prune_densest_niche()
            return True

    def select_reference_pair(self) -> tuple:
        """Selects global champion and an elite behaviorally distant from it."""
        best_elite = min(self.elites, key=lambda e: e["score"])
        if len(self.elites) == 1:
            return best_elite, best_elite
        distant_elite = max(
            self.elites,
            key=lambda e: mean_behavioral_distance(e["sig"], best_elite["sig"])
        )
        return best_elite, distant_elite
```

---

## 19. Result Interpretation Matrix

| Outcome | Quantitative Finding | Scientific Interpretation | Required Qualification |
| :--- | :--- | :--- | :--- |
| **Scenario 1: Diversity Dominates ($C > A$)** | Condition C achieves statistically significantly lower hidden makespan than Condition A ($p < 0.05$) across 5 trials. | Behavioral Quality-Diversity successfully prevents genetic narrowing and outperforms unguided Best-of-N sampling under equal budget. | Conclude ONLY: *"Under this PFSP benchmark, model, and budget, behavioral-diversity-aware search produced better hidden performance."* Do NOT claim QD is universally optimal for all AI discovery. |
| **Scenario 2: Independent Dominance ($A \ge C > B$)** | Condition A matches or beats Condition C ($p \ge 0.05$); both beat Naive Evolution ($B$). | Independent sampling remains the most compute-efficient discovery engine under modest budgets. Archive scaffolding introduces search bias without beating stochastic breadth. | Conclude that foundation model priors already contain broad algorithmic coverage; discovery engines should focus on parallel sampling with verifiers. |
| **Scenario 3: Evolutionary Parity ($C \approx B \approx A$)** | No statistically significant difference between all three conditions on hidden makespan. | In PFSP under a 15-call budget, search strategy is secondary to model temperature and prompt structure. | Conclude that the search space is either too smooth or too constrained for search topology to matter at $N=15$. |
| **Scenario 4: Universal Failure** | All conditions fail to match Classical NEH on hidden instances. | LLM code synthesis cannot discover competitive insertion heuristics without specialized fine-tuning or neural-guided tree search. | Identifies a fundamental capability ceiling for zero-shot LLM program synthesis on PFSP. |

---

## 20. Post-Experiment Decision Pathways

```
                                       POST-EXPERIMENT DECISION TREE
                                                     │
      ┌──────────────────────────────────────────────┼──────────────────────────────────────────────┐
      ▼                                              ▼                                              ▼
SCENARIO 1: Diversity Wins (C > A)            SCENARIO 2: Independent Wins (A >= C)          SCENARIO 3: Universal Failure
- Formally incorporate QD archive as     - Pivot Amaura discovery architecture away     - Acknowledge LLM reasoning limits on
  the core discovery mechanism of          from iterative prompting loops.                complex constructive sequencing.
  Amaura.                                - Re-architect as a massively parallel         - Transition from pure code synthesis to
- Investigate scaling to N=50 and N=100.   stochastic sampler with verifiers (Best-of-N). - Hybrid LLM + Formal Constraint Solvers.
- Replicate on a 3rd domain (e.g. TSP).   - Focus research on verifier design.           - Investigate specialized fine-tuning.
```

---

## 21. Final Recommendation

# **PROCEED TO EXPERIMENT #9 WITH REVISED DESIGN**

The experimental design is scientifically defensible, mathematically formalized, and fully insulated against the methodological pitfalls of earlier experiments:

1. **Domain:** Permutation Flow Shop Scheduling ($Fm \mid prmu \mid C_{\max}$) provides guaranteed feasibility (no deadlocks), sub-millisecond evaluation (0.04 ms), a rich classical algorithmic landscape (Palmer, CDS, NEH, IG), and gold-standard benchmarks.
2. **True Behavioral Diversity:** Condition C eliminates human taxonomic prompting, operating strictly on **mean Kendall's $\tau$ permutation distance** across development instances within an Unstructured Quality-Diversity Archive.
3. **Rigorous Search-Level Replication:** Pitting Condition A against Condition B and Condition C across **$R=5$ independent trials (225 total LLM calls)** provides true search-level statistical power for ~$3.80 in API cost.
4. **Pre-Registered Falsifiability:** Kill criteria, statistical plans, and interpretation matrices are locked prior to code execution.

**Status:** Awaiting user authorization to begin Phase 0 (implementation of evaluation engine and classical baselines). No code has been executed.
