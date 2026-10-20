# Amaura Experiment #6: Domain Selection Analysis

**Date:** October 3, 2026  
**Objective:** Select a single, rigorous, non-bin-packing algorithmic domain to test whether the Amaura automated discovery engine can discover useful algorithms outside Online 1D Bin Packing.

---

## 1. Candidate Domains Evaluated

We evaluated five candidate algorithmic domains against the eight essential criteria specified in the experimental protocol:
1. Executable code output
2. Deterministic, objective evaluation
3. Automatically measurable target metric
4. Strong human-designed baseline (+ secondary sanity baseline)
5. High search-space freedom (not just constant tuning)
6. Secret, diverse hidden benchmark generation
7. Low computational overhead for rapid local execution
8. Independent reproducibility

| Candidate Domain | Evaluator Complexity & Speed | Search Space Richness | Baseline Strength | Hidden Benchmark Diversity | Overfitting Risk | Selected? |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **1. Graph Coloring (Sequential Vertex Ordering)** | **Very Low & Very Fast** (<5ms/graph) | **Extremely Rich** (Graph topology, 2-hop neighborhoods, saturation, spectral/harmonic metrics) | **Extremely Strong** (DSATUR, 1979; Welsh-Powell, 1967) | **Extremely High** (Erdős-Rényi, Geometric, Scale-Free, Small-World, Bipartite, Mycielskian) | **Moderate** (Permits rigorous cross-family generalization testing) | **YES (SELECTED)** |
| **2. Single-Machine Job Scheduling ($1 \|\| \sum w_j T_j$)** | Low & Fast (<2ms/instance) | Moderate (Job weights, due dates, slacks) | Strong (Apparent Tardiness Cost / ATC, EDD, SPT) | High (Tardiness factor $\tau$, range of due dates $R$) | Low-Moderate | No |
| **3. Boolean Satisfiability (SAT Branching Heuristic)** | High & Variable (Can timeout on hard 3-SAT) | High (Clause counts, polarity, Jeroslow-Wang weights) | Extremely Strong (VSIDS, DLIS, MOM's) | High (Uniform random 3-SAT, crafted, industrial) | High | No |
| **4. 2D Euclidean TSP Construction** | Moderate ($O(N^2)$ for insertion) | Moderate-High (Distances, angles, convex hull) | Extremely Strong (Cheapest Insertion, Farthest Insertion, Christofides) | High (Clustered, Uniform, Gaussian, Adversarial) | Low | No |
| **5. Sorting Network Optimization** | Extremely High ($2^N$ zero-one testing) | Restricted (Comparator swap sequences) | Known Optimal Bounds (Knuth) | Limited (Combinatorial exhaust) | Very Low | No |

---

## 2. In-Depth Analysis of Selected Domain: Graph Coloring Vertex Ordering

### Why Graph Coloring?
1. **Fundamental Shift from Bin Packing:**
   In Experiments #2–#5, Online 1D Bin Packing operated over a 1D sequence of numbers where greedy tight-fitting is asymptotically near-optimal ($1.7 \cdot \text{OPT}$). In contrast, **Graph Coloring** is a canonical NP-hard combinatorial graph problem on 2-dimensional network topologies.
2. **The Theoretical Power of Vertex Ordering:**
   A classical theorem of graph coloring states that *for every graph $G$, there exists a vertex permutation $\pi$ such that sequential greedy first-fit coloring achieves the exact chromatic number $\chi(G)$*. The challenge is entirely in designing the **dynamic vertex selection heuristic**.
3. **The Legendary Human Baseline: DSATUR (Brélaz, 1979):**
   Daniel Brélaz's **Degree of Saturation (DSATUR)** heuristic has stood for over 45 years as one of the most effective, elegant constructive heuristics in all of computer science. It dynamically selects the vertex with the maximum number of differently colored neighbors, breaking ties by degree in the uncolored subgraph. A secondary baseline, **Welsh-Powell (1967)** (Largest First static degree ordering), provides an established sanity reference.
4. **Massive Algorithmic Freedom:**
   A candidate algorithm is not just tuning constants. It can synthesize:
   - Dynamic vs static degree ratios
   - Second-order neighborhood saturation (saturation of neighbors)
   - Uncolored neighborhood subgraph density
   - Color frequency distribution and conflict counts
   - Non-linear penalty/bonus terms
   - Phase-aware strategy switching (early-stage vs late-stage coloring based on remaining vertex fraction)
5. **Rich, Unseen Benchmark Families:**
   Unlike scalar numbers, graphs have distinct topological families:
   - *Family 1: Erdős-Rényi Random Graphs $G(n, p)$* (dense and sparse)
   - *Family 2: Random Geometric Graphs* (spatial coordinates, high local clustering)
   - *Family 3: Barabási-Albert Scale-Free Networks* (preferential attachment, power-law degrees)
   - *Family 4: Mycielski-like Triangle-Free Graphs* (adversarial instances with high chromatic number but low clique size)
   - *Family 5 (for Hidden-2): Watts-Strogatz Small-World Networks*
   - *Family 6 (for Hidden-2): Bipartite Graphs with Cross-Cluster Bridges*
   - *Family 7 (for Hidden-2): Regular Random Graphs*
   - *Family 8 (for Hidden-2): Disjoint Clustered Partition Graphs*
6. **Execution Speed and Determinism:**
   A complete coloring of an 80-vertex graph takes under 1.5 milliseconds. Evaluating an entire 25-graph development benchmark takes ~0.04 seconds, allowing 180 evolutionary generations to complete rapidly with zero timeout risk.

---

## 3. Decision

**Selected Domain:** **Graph Coloring Dynamic Vertex Ordering Heuristic**.  
**Candidate Function:**
```python
def choose_vertex(
    uncolored: list[int],
    adj: list[list[int]],
    colors: list[int],
    saturation: list[int],
    degrees: list[int]
) -> int:
    """
    Given the remaining uncolored vertices, the full graph adjacency list,
    current color assignments, current color saturation per vertex, and original degrees,
    return the next vertex ID to color.
    """
```
**Evaluator Action:**
The evaluator takes the chosen vertex, assigns the minimum feasible color (First-Fit Color Assignment), updates saturation, and repeats until all vertices are colored.  
**Objective:** Minimize total number of colors used ($\chi_{heur}(G)$).
