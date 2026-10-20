"""
Experiment #7: Macro-Algorithmic Strategy Classifier
=====================================================
Analyzes the AST and source code of candidate solvers to determine their
underlying macro-algorithmic paradigm.
Categories:
- `dsatur_saturation`: Saturation-degree based sequential selection
- `rlf_independent_set`: Independent-set / color-class extraction
- `degree_ordering`: Welsh-Powell / Largest First static or dynamic degree ordering
- `local_search_repair`: Kempe chains, min-conflicts, or iterative recoloring passes
- `iterated_greedy`: Multi-pass iterative coloring (Culberson style)
- `random_restart`: Multiple randomized iterations keeping the best coloring
- `hybrid`: Explicit combination of two or more distinct macro-paradigms
- `pure_greedy`: Simple first-fit or arbitrary traversal
- `other`: Unconventional or unclassified strategy
"""

import ast
from typing import Dict, Any, List


def classify_macro_strategy(code: str) -> Dict[str, Any]:
    """
    Classifies the macro-algorithmic paradigm of a `color_graph` solver.
    Returns primary category, detected features, and rationale.
    """
    code_lower = code.lower()
    features = []

    # Check for saturation degree concepts
    has_saturation = (
        "saturation" in code_lower or
        "sat" in code_lower and ("color" in code_lower or "distinct" in code_lower) or
        "neighbor_colors" in code_lower
    )
    if has_saturation:
        features.append("saturation_tracking")

    # Check for RLF / Independent set extraction
    has_independent_set = (
        "independent" in code_lower or
        "color_class" in code_lower or
        "color_classes" in code_lower or
        ("uncolored - " in code_lower or "uncolored.difference" in code_lower) and "while uncolored:" in code_lower
    )
    if has_independent_set:
        features.append("independent_set_extraction")

    # Check for local search / recoloring / Kempe chains
    has_local_search = (
        "kempe" in code_lower or
        "recolor" in code_lower or
        "local_search" in code_lower or
        "swap" in code_lower or
        "conflicts" in code_lower or
        "improve" in code_lower and "pass" in code_lower
    )
    if has_local_search:
        features.append("local_search_or_recoloring")

    # Check for random restarts
    has_random_restart = (
        ("random.shuffle" in code_lower or "random.choice" in code_lower or "random.sample" in code_lower) and
        ("for _ in range(" in code_lower or "best_colors" in code_lower or "best_k" in code_lower)
    )
    if has_random_restart:
        features.append("randomized_restarts")

    # Check for multi-pass / iterated greedy
    has_iterated_greedy = (
        "iterated" in code_lower or
        ("for iter in range(" in code_lower or "for round in range(" in code_lower or "for pass_idx in range(" in code_lower) and
        ("order" in code_lower or "sort" in code_lower)
    )
    if has_iterated_greedy:
        features.append("multi_pass_iterated_greedy")

    # Check for degree ordering
    has_degree_order = (
        "degrees" in code_lower or "degree" in code_lower or "len(adj" in code_lower
    ) and "sorted" in code_lower
    if has_degree_order:
        features.append("degree_ordering")

    # Determine primary category
    if len(features) >= 2:
        if has_local_search and (has_saturation or has_independent_set or has_degree_order):
            primary = "hybrid_constructive_and_local_search"
        elif has_random_restart and (has_saturation or has_degree_order):
            primary = "hybrid_random_restart"
        elif has_iterated_greedy:
            primary = "iterated_greedy"
        elif has_independent_set:
            primary = "rlf_independent_set"
        elif has_saturation:
            primary = "dsatur_saturation"
        else:
            primary = "hybrid_multistrategy"
    elif has_independent_set:
        primary = "rlf_independent_set"
    elif has_saturation:
        primary = "dsatur_saturation"
    elif has_local_search:
        primary = "local_search_repair"
    elif has_iterated_greedy:
        primary = "iterated_greedy"
    elif has_random_restart:
        primary = "random_restart"
    elif has_degree_order:
        primary = "degree_ordering"
    else:
        primary = "pure_greedy"

    return {
        "primary_category": primary,
        "detected_features": features,
        "is_hybrid": len(features) >= 2,
    }
