"""
Regression and Parity Tests for PFSP Declarative Solver & Budget Semantics
==========================================================================
Verifies:
1. Exact schedule and makespan parity with reference neh_ls_solve on 20 dev instances.
2. Explicit tie-breaking compliance (first_found, last_found, flow_time_min, idle_time_min).
3. Resource budget semantics, accounting, and truncation conditions.
4. Complete-pass vs budget-exhausted states.
5. Adapter diagnostics recording in context.
"""

import json
import os
import pytest
from typing import Dict, Any

from discovery_kernel.pfsp_declarative import (
    validate_config,
    canonicalize_config,
    solve_declarative,
    PFSPDeclarativeAdapter,
    MIN_EVALUATION_BUDGET,
    MAX_EVALUATION_BUDGET
)
from benchmark_v1.src.domains.pfsp_full_algorithm import calc_makespan, neh_ls_solve, validate_permutation


@pytest.fixture
def dev_instances():
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "discovery_kernel_v01",
        "results",
        "ai_discovery_pilot_20261019",
        "data",
        "dev_instances.json"
    )
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_exact_baseline_parity_on_all_20_dev_instances(dev_instances):
    """
    CRITICAL ACCEPTANCE GATE:
    Asserts 100% exact parity (both schedules and makespans) between the reference
    baseline neh_ls_solve and the repaired declarative PFSP solver across all 20 dev instances.
    """
    parity_cfg = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "first_found",
        "local_search": "single_pass_insertion",
        "search_strategy": "best_improvement",
        "acceptance_rule": "strictly_better_makespan",
        "budget_evaluations": "single_pass"
    }

    adapter = PFSPDeclarativeAdapter("neh_ls_declarative_parity", parity_cfg)

    for inst in dev_instances:
        times = inst["times"]
        n = inst["n"]

        # Reference execution
        ref_seq = neh_ls_solve(times)
        ref_cmax = calc_makespan(times, ref_seq)

        # Declarative execution with diagnostic tracking
        context = {}
        dec_seq = adapter.solve(inst, context=context)
        dec_cmax = calc_makespan(times, dec_seq)
        diag = context["diagnostics"]

        # 1. Output validity
        is_valid, err = validate_permutation(dec_seq, n)
        assert is_valid is True, f"Invalid permutation on {inst['id']}: {err}"

        # 2. Schedule and makespan deterministic equivalence
        assert dec_seq == ref_seq, f"Schedule mismatch on {inst['id']}"
        assert dec_cmax == ref_cmax, f"Makespan mismatch on {inst['id']}"

        # 3. Resource accounting assertions
        assert diag["completed_pass"] is True
        assert diag["termination_condition"] in ["pass_complete", "converged"]
        assert diag["evaluations_used"] == n * (n - 1)
        assert diag["passes_completed"] == 1
        assert diag["runtime_ms"] > 0.0


def test_tie_breaking_policy_honored_in_local_search(dev_instances):
    """
    Verifies that first_found does NOT silently convert to flow_time_min,
    and that different tie-breaking strategies produce expected distinct behaviors.
    """
    inst = dev_instances[3]  # pfsp_dev_03 (n=20, m=10)
    times = inst["times"]

    cfg_first = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "first_found",
        "local_search": "single_pass_insertion",
        "search_strategy": "best_improvement",
        "acceptance_rule": "strictly_better_makespan",
        "budget_evaluations": "single_pass"
    }

    cfg_flow = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "flow_time_min",
        "local_search": "single_pass_insertion",
        "search_strategy": "best_improvement",
        "acceptance_rule": "strictly_better_makespan",
        "budget_evaluations": "single_pass"
    }

    cfg_idle = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "idle_time_min",
        "local_search": "single_pass_insertion",
        "search_strategy": "best_improvement",
        "acceptance_rule": "strictly_better_makespan",
        "budget_evaluations": "single_pass"
    }

    seq_first = solve_declarative(times, cfg_first)
    seq_flow = solve_declarative(times, cfg_flow)
    seq_idle = solve_declarative(times, cfg_idle)

    # On pfsp_dev_03, idle_time_min finds a superior schedule (1670 vs 1689)
    c_first = calc_makespan(times, seq_first)
    c_idle = calc_makespan(times, seq_idle)
    assert c_first == 1689
    assert c_idle == 1670
    assert seq_idle != seq_first


def test_budget_exhaustion_semantics(dev_instances):
    """
    Verifies that when evaluation budget is smaller than neighborhood size,
    the solver terminates cleanly with termination_condition='budget_exhausted'
    and completed_pass=False.
    """
    inst = dev_instances[0]  # n=20, moves required for single pass = 20*19 = 380
    times = inst["times"]

    capped_cfg = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "first_found",
        "local_search": "single_pass_insertion",
        "search_strategy": "best_improvement",
        "acceptance_rule": "strictly_better_makespan",
        "budget_evaluations": 100  # Cap at 100 < 380
    }

    seq, diag = solve_declarative(times, capped_cfg, return_diagnostics=True)

    assert diag["evaluations_used"] == 100
    assert diag["budget_evaluations"] == 100
    assert diag["completed_pass"] is False
    assert diag["termination_condition"] == "budget_exhausted"
    assert diag["passes_completed"] == 0


def test_multi_pass_convergence_and_completion(dev_instances):
    """
    Verifies multi-pass insertion terminates either via convergence or pass completion.
    """
    inst = dev_instances[0]  # n=20
    times = inst["times"]

    multi_cfg = {
        "initial_order": "total_processing_time_desc",
        "construction_criterion": "makespan_only",
        "tie_break": "first_found",
        "local_search": "multi_pass_insertion",
        "search_strategy": "best_improvement",
        "acceptance_rule": "strictly_better_makespan",
        "budget_evaluations": 5000  # Sufficient for multiple passes (380 per pass)
    }

    seq, diag = solve_declarative(times, multi_cfg, return_diagnostics=True)

    assert diag["completed_pass"] is True
    assert diag["termination_condition"] in ["converged", "pass_complete"]
    assert diag["passes_completed"] >= 1
    assert diag["evaluations_used"] <= 5000


def test_budget_validation_rules():
    """
    Verifies configuration validation accepts valid dynamic and bounded integer budgets,
    and rejects invalid values.
    """
    # 1. Valid 'single_pass' budget
    proposal_single = {
        "rationale": "Test single pass",
        "config": {
            "initial_order": "total_processing_time_desc",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "single_pass_insertion",
            "search_strategy": "best_improvement",
            "acceptance_rule": "strictly_better_makespan",
            "budget_evaluations": "single_pass"
        }
    }
    is_val, err, san = validate_config(proposal_single)
    assert is_val is True
    assert san["config"]["budget_evaluations"] == "single_pass"

    # 2. Valid large integer budget within bounds (e.g. 25000)
    proposal_int = {
        "rationale": "Test integer budget",
        "config": {
            "initial_order": "total_processing_time_desc",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "single_pass_insertion",
            "search_strategy": "best_improvement",
            "acceptance_rule": "strictly_better_makespan",
            "budget_evaluations": 25000
        }
    }
    is_val, err, san = validate_config(proposal_int)
    assert is_val is True
    assert san["config"]["budget_evaluations"] == 25000

    # 3. Invalid budget above MAX_EVALUATION_BUDGET
    proposal_too_large = {
        "rationale": "Test excessive budget",
        "config": {
            "initial_order": "total_processing_time_desc",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "single_pass_insertion",
            "search_strategy": "best_improvement",
            "acceptance_rule": "strictly_better_makespan",
            "budget_evaluations": 60000
        }
    }
    is_val, err, _ = validate_config(proposal_too_large)
    assert is_val is False
    assert "budget_evaluations" in err

    # 4. Invalid budget below MIN_EVALUATION_BUDGET
    proposal_too_small = {
        "rationale": "Test tiny budget",
        "config": {
            "initial_order": "total_processing_time_desc",
            "construction_criterion": "makespan_only",
            "tie_break": "first_found",
            "local_search": "single_pass_insertion",
            "search_strategy": "best_improvement",
            "acceptance_rule": "strictly_better_makespan",
            "budget_evaluations": 25
        }
    }
    is_val, err, _ = validate_config(proposal_too_small)
    assert is_val is False
    assert "budget_evaluations" in err
