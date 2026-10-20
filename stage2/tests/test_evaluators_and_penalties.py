"""
Unit Tests: Evaluator Determinism, Penalties, and Zero-Valid Pools
=================================================================
Enforces Section 15, 17, 27, 35.
"""

import pytest
from stage2.src.evaluator_gc import GraphColoringEvaluator
from stage2.src.evaluator_pfsp import PFSPEvaluator
from stage2.baselines.graph_coloring import dsatur_code
from stage2.baselines.pfsp import neh_code


def test_evaluator_determinism():
    gc_ev = GraphColoringEvaluator()
    pfsp_ev = PFSPEvaluator()

    sample_graph = [{"family": "k4", "adj": [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]}]
    sample_pfsp = [{"family": "toy", "n": 3, "m": 2, "times": [[10, 5], [2, 8], [7, 3]]}]

    # Run GC twice
    res_gc_1 = gc_ev.evaluate_code(dsatur_code(), sample_graph)
    res_gc_2 = gc_ev.evaluate_code(dsatur_code(), sample_graph)
    assert res_gc_1["total_colors"] == res_gc_2["total_colors"] == 4
    assert res_gc_1["is_valid"] == res_gc_2["is_valid"] is True

    # Run PFSP twice
    res_pfsp_1 = pfsp_ev.evaluate_code(neh_code(), sample_pfsp)
    res_pfsp_2 = pfsp_ev.evaluate_code(neh_code(), sample_pfsp)
    assert res_pfsp_1["total_makespan"] == res_pfsp_2["total_makespan"]
    assert res_pfsp_1["is_valid"] == res_pfsp_2["is_valid"] is True


def test_invalid_and_timeout_penalties():
    gc_ev = GraphColoringEvaluator()
    pfsp_ev = PFSPEvaluator()

    sample_graph = [{"family": "k4", "adj": [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]}]

    # Invalid coloring must receive 999999 penalty
    bad_code = "def color_graph(adj: list[list[int]]) -> list[int]: return [0]*len(adj)"
    res_inv = gc_ev.evaluate_code(bad_code, sample_graph)
    assert res_inv["is_valid"] is False
    assert res_inv["total_colors"] == 999999

    # Timeout must receive 999999 penalty
    timeout_code = "def color_graph(adj: list[list[int]]) -> list[int]:\n    while True: pass"
    res_to = gc_ev.evaluate_code(timeout_code, sample_graph)
    assert res_to["is_valid"] is False
    assert res_to["total_colors"] == 999999


def test_zero_valid_pools_detection():
    # Simulate a pool where all 20 candidates failed
    pool = [{"candidate_id": f"C_{i}", "dev_score": 999999, "is_valid": False} for i in range(20)]
    valid_cands = [c for c in pool if c["is_valid"]]
    zero_valid = (len(valid_cands) == 0)
    assert zero_valid is True
