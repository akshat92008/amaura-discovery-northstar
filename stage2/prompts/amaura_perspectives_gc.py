"""
Stage 2: Diversified Perspectives for Graph Coloring (Arm C)
=============================================================
Defines 20 distinct conceptual perspectives for generating the diversified Arm C pool.
Zero leakage: Does NOT copy the Exp7 champion or Exp13-16 cloud mechanisms.
"""

from typing import List, Dict, Any

AMAURA_PERSPECTIVES_GC: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Smallest-Last Degeneracy Elimination",
        "category": "Structural Analysis",
        "prompt": "Design a graph coloring algorithm based on vertex degeneracy and smallest-last ordering: iteratively remove the vertex with minimum current degree, place it at the end of the order, and color in reverse order with First-Fit. Explain how this bounds chromatic number by graph degeneracy."
    },
    {
        "id": 2,
        "name": "K-Core Shell Peeling",
        "category": "Structural Analysis",
        "prompt": "Design a graph coloring heuristic utilizing k-core decomposition. Decompose the graph into nested core shells, order vertices from outermost (low core) to innermost (high core), and allocate colors to prevent dense core conflicts from spreading to peripheral nodes."
    },
    {
        "id": 3,
        "name": "Dynamic Saturation with Second-Order Tie Breaking",
        "category": "Classical Heuristic",
        "prompt": "Design an algorithm based on dynamic saturation degree (DSATUR). When saturation degrees tie, break ties using the sum of degrees of uncolored neighbors rather than simple degree, ensuring dense clusters are resolved before sparse areas."
    },
    {
        "id": 4,
        "name": "Iterative Maximal Independent Set Extraction",
        "category": "Greedy Decomposition",
        "prompt": "Design a recursive independent set extraction heuristic (RLF style): at each stage, build a color class by finding a maximal independent set that heavily neighbors the remaining uncolored vertices, reducing remaining graph complexity as quickly as possible."
    },
    {
        "id": 5,
        "name": "Graph Bipartition & 2-Color Expansion",
        "category": "Constraint Perspective",
        "prompt": "Design a graph coloring algorithm that first extracts a maximal bipartite subgraph via breadth-first search layers (assigning 2 initial colors), and then resolves remaining odd-cycle conflicts using minimal extra colors."
    },
    {
        "id": 6,
        "name": "Spectral Clustering & Eigen-Proxy Ordering",
        "category": "Structural Analysis",
        "prompt": "Design a heuristic that approximates spectral partitioning without external libraries: compute a random walk diffusion vector to identify graph clusters, and color internally disconnected clusters with identical color classes."
    },
    {
        "id": 7,
        "name": "Bottleneck Vertex Prioritization",
        "category": "Bottleneck Perspective",
        "prompt": "Design a graph coloring algorithm that identifies articulation points, bridge neighbors, and high-betweenness bottleneck vertices. Color critical bridge vertices first so that disconnected components can reuse color indices independently."
    },
    {
        "id": 8,
        "name": "Bounded Conflict-Exchange Local Search",
        "category": "Local Search",
        "prompt": "Design a graph coloring algorithm that generates an initial greedy coloring and then attempts to eliminate the highest-indexed color class by reassigning its vertices to lower colors, using bounded Kempe chain swaps to resolve conflicts."
    },
    {
        "id": 9,
        "name": "Multi-Resource Color Class Balancing",
        "category": "Diversification Perspective",
        "prompt": "Design a coloring algorithm that enforces balanced color class sizes: penalize assigning vertices to already large color classes unless required to avoid creating new colors, thereby maximizing room for later vertices."
    },
    {
        "id": 10,
        "name": "Constraint Propagation & Forward Checking",
        "category": "Constraint Perspective",
        "prompt": "Design a graph coloring algorithm utilizing constraint satisfaction principles: maintain a bitmask or set of available colors for each vertex, update domains with forward checking upon each assignment, and prioritize vertices with minimum remaining values (MRV)."
    },
    {
        "id": 11,
        "name": "Complement Graph Clique Detection",
        "category": "Graph Theory",
        "prompt": "Design a graph coloring algorithm based on complement graph analysis: finding independent sets in G corresponds to finding cliques in the complement graph G'. Use a greedy clique heuristic on G' to form each color class."
    },
    {
        "id": 12,
        "name": "Triad and Triangle Density Minimization",
        "category": "Structural Analysis",
        "prompt": "Design a graph coloring algorithm that counts triangles incident to each vertex. Color vertices with high triangle counts first to collapse 3-cliques before assigning outer trees and cycles."
    },
    {
        "id": 13,
        "name": "Adaptive Weighting & Penalty Accumulation",
        "category": "Adaptive Heuristic",
        "prompt": "Design a graph coloring heuristic inspired by breakout local search: maintain dynamic penalty weights on vertices that cause color expansion, adjusting weights over multiple passes to prioritize hard-to-color subgraphs."
    },
    {
        "id": 14,
        "name": "Multi-Pass Random Order Min-Colors",
        "category": "Diversification Perspective",
        "prompt": "Design an algorithm that runs multiple randomized greedy passes with different randomized perturbation orderings (e.g. 10 fast passes), tracking the best coloring and applying local 1-opt recoloring on the winner."
    },
    {
        "id": 15,
        "name": "Neighborhood Commonality Index (Jaccard Overlap)",
        "category": "Structural Analysis",
        "prompt": "Design a graph coloring heuristic that computes Jaccard similarity of neighborhoods between non-adjacent vertices. Pair non-adjacent vertices with high neighbor overlap into the same color class simultaneously."
    },
    {
        "id": 16,
        "name": "Skeptical Failure-Mode Analysis",
        "category": "Skeptical Perspective",
        "prompt": "Analyze where standard greedy Welsh-Powell fails: specifically on bipartite graphs colored in bad order (Crown graphs) and sparse cycles. Design a robust tie-breaking mechanism specifically immune to pathological bipartite and crown orderings."
    },
    {
        "id": 17,
        "name": "Hybrid Constructive-Tabu Micro-Search",
        "category": "Hybrid Composition",
        "prompt": "Design a hybrid coloring heuristic: use DSATUR to reach k colors, reduce to k-1 colors, and apply a 50-step Tabu Search to resolve conflicts. If unresolved, safely return the valid k-coloring."
    },
    {
        "id": 18,
        "name": "Degree-Discount Peripheral Packing",
        "category": "Greedy Heuristic",
        "prompt": "Design a graph coloring algorithm that orders vertices by degree, but dynamically discounts the degree of neighbors as vertices are colored, preventing over-saturation of peripheral trees."
    },
    {
        "id": 19,
        "name": "Color Frequency Squeezing",
        "category": "Optimization Perspective",
        "prompt": "Design a coloring algorithm that aims to create highly asymmetric color classes (e.g. maximizing class 0, then class 1, etc.) so that the tail color classes contain only 1-2 vertices that can be easily absorbed into lower classes."
    },
    {
        "id": 20,
        "name": "Hierarchical Block-Cut Tree Decomposition",
        "category": "Structural Decomposition",
        "prompt": "Design a graph coloring algorithm that decomposes the graph into 2-connected biconnected components (blocks) and cut vertices. Color each block independently and align colorings at cut vertices by color permutation."
    }
]
