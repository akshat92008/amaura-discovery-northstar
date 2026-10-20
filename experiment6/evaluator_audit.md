# Experiment #6: Evaluator Information Boundary & Security Audit

**Date:** October 3, 2026  
**Subject:** Information Isolation and Leakage Audit for Graph Coloring Heuristic Interface (`choose_vertex`)

---

## 1. Concrete Example of Information Provided at Time Step $t$

Consider a graph with $|V|=6$ vertices where vertices $\{0, 1\}$ are already colored, and $\{2, 3, 4, 5\}$ remain uncolored:

```text
======================= CANDIDATE INPUT STATE =======================
uncolored:      [2, 3, 4, 5]
adj:            [
                  [1, 2, 4],     # Vertex 0 neighbors
                  [0, 2, 3],     # Vertex 1 neighbors
                  [0, 1, 3, 5],  # Vertex 2 neighbors
                  [1, 2, 4],     # Vertex 3 neighbors
                  [0, 3, 5],     # Vertex 4 neighbors
                  [2, 4]         # Vertex 5 neighbors
                ]
colors:         [0, 1, -1, -1, -1, -1]  # 0 has color 0, 1 has color 1, others uncolored
saturation:     [1, 1, 2, 1, 1, 0]      # Distinct colored neighbors for each vertex
degrees:        [3, 3, 4, 3, 3, 2]      # Total original degrees
=====================================================================
```

---

## 2. Explicit Information Deliberately Withheld / Not Provided

The following variables are **strictly isolated** and never passed or accessible to the candidate:

```text
=================== DELIBERATELY ISOLATED INFORMATION ================
Optimal chromatic number chi(G):  NOT AVAILABLE (NP-hard optimum is unknown to candidate)
Hidden benchmark graph suite:     NOT AVAILABLE (evaluator holds test graphs privately)
Graph family / Generator type:    NOT AVAILABLE (evaluator does not label 'Erdos-Renyi', 'Geometric', etc.)
Random seed:                      NOT AVAILABLE (evaluator seeds are private)
Total graph sequence count:       NOT AVAILABLE (candidate does not know total instances)
Current aggregate score:          NOT AVAILABLE (evaluator aggregates privately)
Colors of future graphs:          NOT AVAILABLE (state resets per graph)
Inter-graph memory / Globals:     NOT AVAILABLE (global scope purged per evaluation instance)
External environment:             NOT AVAILABLE (network, filesystem, OS calls blocked by sandbox)
======================================================================
```

---

## 3. Defensive Copying Verification

1. `uncolored` is passed as a **shallow copy**: `list(uncolored)`. Modifications by candidate do not alter the loop.
2. `colors` is passed as a **shallow copy**: `list(colors)`.
3. `saturation` is passed as a **shallow copy**: `list(saturation)`.
4. `adj` is passed as a list of lists of immutable integers.
5. If the candidate returns a vertex $v \notin \text{uncolored}$, the evaluator immediately raises `ValueError` and scores `excess_pct = inf`.

---

## 4. Sandbox Policy

Static AST analysis strictly checks:
- Permitted import: Pure `math` module only.
- Forbidden: `eval`, `exec`, `open`, `__import__`, `globals`, `locals`, `getattr`, `setattr`, `os`, `sys`, `socket`.
- Required signature: `def choose_vertex(uncolored, adj, colors, saturation, degrees) -> int:`

---

## 5. Audit Verdict

**PASS**: Zero information leakage. The candidate receives exactly the state of the current graph at the current step and nothing else.
