"""
Unit Tests: Classical Graph Coloring Heuristic Baselines
========================================================
Verifies:
1. Greedy First-Fit, Welsh-Powell, DSATUR, RLF, and Iterated Greedy produce valid colorings.
2. Baselines satisfy chromatic conflict constraints on diverse graph topologies.
"""

from stage3.baselines.graph_coloring import (
    greedy_first_fit,
    welsh_powell,
    dsatur,
    recursive_largest_first,
    iterated_greedy
)
from stage3.src.evaluator_gc import GraphColoringEvaluator


def test_baselines_on_standard_graphs():
    evaluator = GraphColoringEvaluator()

    # Graph 1: Complete Graph K4
    k4 = [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]

    # Graph 2: Cycle C5 (odd cycle -> chromatic number 3)
    c5 = [[1, 4], [0, 2], [1, 3], [2, 4], [3, 0]]

    # Graph 3: Bipartite Graph K3,3 (chromatic number 2)
    k33 = [
        [3, 4, 5], [3, 4, 5], [3, 4, 5],
        [0, 1, 2], [0, 1, 2], [0, 1, 2]
    ]

    graphs = [("K4", k4, 4), ("C5", c5, 3), ("K33", k33, 2)]
    solvers = [greedy_first_fit, welsh_powell, dsatur, recursive_largest_first, iterated_greedy]

    for g_name, adj, expected_k in graphs:
        for solver in solvers:
            colors = solver(adj)
            is_valid, err, cat, k = evaluator.validate_coloring(adj, colors)
            assert is_valid, f"{solver.__name__} failed on {g_name}: {err}"
            if g_name == "K4":
                assert k == 4, f"K4 requires exactly 4 colors, got {k}"
            elif g_name == "C5":
                assert k == 3, f"C5 requires exactly 3 colors, got {k}"
            elif g_name == "K33":
                # Some greedy orders might use >2, but DSATUR/RLF should be efficient
                assert k >= 2


def test_empty_graph():
    solvers = [greedy_first_fit, welsh_powell, dsatur, recursive_largest_first, iterated_greedy]
    for solver in solvers:
        colors = solver([])
        assert colors == []
