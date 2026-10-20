"""
Unit Tests for PFSP Declarative Algorithm Space & Adapter
=========================================================
"""

import pytest
import random
from typing import List

from discovery_kernel.pfsp_declarative import (
    validate_config,
    canonicalize_config,
    solve_declarative,
    PFSPDeclarativeAdapter,
    INITIAL_ORDERS,
    CONSTRUCTION_CRITERIA,
    TIE_BREAKS,
    LOCAL_SEARCHES
)
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    neh_solve,
    neh_ls_single_pass_solve
)
from benchmark_v1.src.domains.pfsp_full_algorithm import validate_permutation


def _gen_test_instance(n: int, m: int, seed: int = 42) -> List[List[int]]:
    rng = random.Random(seed)
    return [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]


def test_validation_success_and_normalization():
    proposal = {
        "rationale": "Test candidate with standard NEH configuration",
        "config": {
            "initial_order": "total_processing_time_desc",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "none",
            "search_strategy": "none",
            "acceptance_rule": "none",
            "budget_evaluations": 0
        }
    }
    is_valid, err, sanitized = validate_config(proposal)
    assert is_valid is True
    assert err is None
    assert sanitized["config"]["budget_evaluations"] == 0


def test_validation_rejects_malformed_proposals():
    # 1. Non-dict
    assert validate_config("string")[0] is False
    # 2. Missing rationale
    assert validate_config({"config": {}})[0] is False
    # 3. Missing config key
    assert validate_config({"rationale": "r", "config": {"initial_order": "total_processing_time_desc"}})[0] is False
    # 4. Invalid enum value
    invalid_proposal = {
        "rationale": "test",
        "config": {
            "initial_order": "invalid_order",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "none",
            "search_strategy": "none",
            "acceptance_rule": "none",
            "budget_evaluations": 0
        }
    }
    is_val, err, _ = validate_config(invalid_proposal)
    assert is_val is False
    assert "Invalid initial_order" in err

    # 5. Invalid budget (< 50 when local search is active)
    invalid_budget = {
        "rationale": "test",
        "config": {
            "initial_order": "total_processing_time_desc",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "pairwise_swap",
            "search_strategy": "first_improvement",
            "acceptance_rule": "strictly_better_makespan",
            "budget_evaluations": 10  # too small
        }
    }
    is_val, err, _ = validate_config(invalid_budget)
    assert is_val is False
    assert "budget_evaluations" in err


def test_canonicalization_invariance():
    cfg1 = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "first_found",
        "local_search": "none",
        "search_strategy": "none",
        "acceptance_rule": "none",
        "budget_evaluations": 0
    }
    cfg2 = {
        "budget_evaluations": 0,
        "acceptance_rule": "none",
        "search_strategy": "none",
        "local_search": "none",
        "tie_break": "first_found",
        "construction_criterion": "makespan_only",
        "initial_order": "total_processing_time_desc"
    }
    _, json1, hash1 = canonicalize_config(cfg1)
    _, json2, hash2 = canonicalize_config(cfg2)
    assert json1 == json2
    assert hash1 == hash2


def test_declarative_neh_reproduction():
    times = _gen_test_instance(30, 10, seed=101)
    neh_cfg = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "first_found",
        "local_search": "none",
        "search_strategy": "none",
        "acceptance_rule": "none",
        "budget_evaluations": 0
    }
    dec_sol = solve_declarative(times, neh_cfg)
    ref_sol = neh_solve(times)

    assert dec_sol == ref_sol
    assert calc_makespan_ref(times, dec_sol) == calc_makespan_ref(times, ref_sol)


def test_declarative_adapter_execution():
    times = _gen_test_instance(20, 5, seed=202)
    cfg = {
        "initial_order": "weighted_profile_desc",
        "construction_criterion": "makespan_and_flow_time",
        "tie_break": "flow_time_min",
        "local_search": "pairwise_swap",
        "search_strategy": "first_improvement",
        "acceptance_rule": "better_makespan_or_flow",
        "budget_evaluations": 100
    }
    adapter = PFSPDeclarativeAdapter("cand_test", cfg, rationale="Palmer + Flow Time + Swap")
    sol = adapter.solve({"id": "inst_test", "times": times})

    is_valid, err = validate_permutation(sol, len(times))
    assert is_valid is True
    assert err is None
    assert len(sol) == 20
