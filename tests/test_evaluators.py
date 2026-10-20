"""
Unit tests for Evaluators & Anti-Reward-Hacking Sandbox
"""

import pytest
from amaura.engine.candidate import Candidate
from amaura.evaluators.bin_packing import BinPackingEvaluator
from amaura.evaluators.cache_policy import CachePolicyEvaluator


def test_bin_packing_seed_evaluation():
    evaluator = BinPackingEvaluator(train_count=5, test_count=5, gen_count=5, seed=42)
    seeds = evaluator.get_seed_candidates()
    assert len(seeds) >= 3

    for seed in seeds:
        res = evaluator.evaluate_candidate(seed)
        assert res.is_valid, f"Seed {seed.mutation_type} failed evaluation: {res.error_message}"
        assert res.fitness < float("inf")
        assert res.raw_score > 0.0


def test_cache_policy_seed_evaluation():
    evaluator = CachePolicyEvaluator(train_traces=3, test_traces=3, gen_traces=3, trace_length=200, seed=42)
    seeds = evaluator.get_seed_candidates()
    assert len(seeds) >= 3

    for seed in seeds:
        res = evaluator.evaluate_candidate(seed)
        assert res.is_valid, f"Cache seed {seed.mutation_type} failed: {res.error_message}"
        assert res.fitness < float("inf")
        # Hit rate must be non-zero
        assert res.raw_score > 0.0


def test_anti_reward_hacking_forbidden_imports():
    evaluator = BinPackingEvaluator(train_count=2, test_count=2, gen_count=2)
    malicious_code = (
        "import os\n"
        "def priority(item, rem, cap):\n"
        "    return 10.0\n"
    )
    cand = Candidate(code=malicious_code, function_name="priority")
    res = evaluator.evaluate_candidate(cand)
    assert not res.is_valid
    assert "Forbidden import" in (res.error_message or "")


def test_sandbox_timeout_interruption():
    evaluator = BinPackingEvaluator(train_count=1, test_count=1, gen_count=1, items_per_instance=10, timeout_sec=0.05)
    infinite_loop_code = (
        "def priority(item, rem, cap):\n"
        "    import time\n"
        "    time.sleep(0.2)\n"
        "    return 10.0\n"
    )
    cand = Candidate(code=infinite_loop_code, function_name="priority")
    res = evaluator.evaluate_candidate(cand)
    assert not res.is_valid
    assert "Timeout" in (res.error_message or "")
