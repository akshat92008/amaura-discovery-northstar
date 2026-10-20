"""
Unit Tests for Benchmark V1 Problem Domains
===========================================
Tests Bin Packing, Graph Coloring, and PFSP domains:
- Correct loading of train and test datasets.
- Evaluation of canonical seeds.
- Deterministic behavior across repeated evaluations.
- Correct invalid penalty handling (invalid candidates must always have strictly worse score than baselines).
- Correct relative gap calculations.
"""

import pytest
from benchmark_v1.src.domains.bin_packing import BinPackingDomain
from benchmark_v1.src.domains.graph_coloring import GraphColoringDomain
from benchmark_v1.src.domains.pfsp import PFSPDomain


def test_bin_packing_domain():
    domain = BinPackingDomain()
    assert domain.name == "bin_packing"
    assert len(domain.train_streams) == 20
    assert len(domain.test_streams) == 100

    # Best-Fit seed evaluation
    bf_seed = next(s for s in domain.canonical_seeds if s["name"] == "best_fit")
    res1 = domain.evaluate(bf_seed["code"], split="train")
    assert res1.is_valid
    assert abs(res1.relative_gap) < 1e-4

    # Determinism
    res2 = domain.evaluate(bf_seed["code"], split="train")
    assert res1.raw_score == res2.raw_score

    # Invalid penalty
    res_inv = domain.evaluate("def invalid(): pass", split="train")
    assert not res_inv.is_valid
    assert res_inv.raw_score >= 1.0
    assert res_inv.relative_gap > 0


def test_graph_coloring_domain():
    domain = GraphColoringDomain()
    assert domain.name == "graph_coloring"
    assert len(domain.train_graphs) == 20
    assert len(domain.test_graphs) == 40

    # DSATUR seed evaluation
    ds_seed = next(s for s in domain.canonical_seeds if s["name"] == "dsatur")
    res1 = domain.evaluate(ds_seed["code"], split="train")
    assert res1.is_valid
    assert res1.raw_score == 132.0  # Total colors across 20 graphs
    assert abs(res1.relative_gap) < 1e-4

    # Determinism
    res2 = domain.evaluate(ds_seed["code"], split="train")
    assert res1.raw_score == res2.raw_score

    # Invalid penalty
    res_inv = domain.evaluate("syntax error !!!", split="train")
    assert not res_inv.is_valid
    assert res_inv.raw_score > 500  # Penalty is sum of vertices (~1000)
    assert res_inv.relative_gap > 1.0


def test_pfsp_domain():
    domain = PFSPDomain()
    assert domain.name == "pfsp"
    assert len(domain.train_data) == 18
    assert len(domain.test_data) == 36

    # NEH seed evaluation
    neh_seed = next(s for s in domain.canonical_seeds if s["name"] == "neh")
    res1 = domain.evaluate(neh_seed["code"], split="train")
    assert res1.is_valid
    assert res1.raw_score == 84907.0
    assert abs(res1.relative_gap) < 1e-4

    # Determinism
    res2 = domain.evaluate(neh_seed["code"], split="train")
    assert res1.raw_score == res2.raw_score

    # Invalid penalty
    res_inv = domain.evaluate("import os; os.system('echo hi')", split="train")
    assert not res_inv.is_valid
    assert res_inv.raw_score > 1000000.0  # 2 * sum of processing times
    assert res_inv.relative_gap > 10.0
