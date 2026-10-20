"""
Tests for Stage 4 Diagnostic Trace Extraction & In-Context Refinement
======================================================================
Validates that:
1. DeterministicBinPackingSimulator produces structured diagnostics (worst streams, waste profiles, distribution breakdowns).
2. Diagnostic summaries contain actionable failure counterexamples.
3. Stage4Evaluator preserves diagnostics through process-isolated execution.
4. Stage4IslandArchive and Stage4Candidate log diagnostic availability.
5. Arm C search prompt builders incorporate parent diagnostic profiles.
"""

import json
import math
import pytest
from typing import List, Dict, Any

from stage4.src.simulator import (
    DeterministicBinPackingSimulator,
    best_fit_priority,
    worst_fit_priority,
    first_fit_priority
)
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.archive import Stage4IslandArchive, Stage4Candidate
from stage4.src.search import run_arm_c_search
from stage4.src.client import Stage4LLMClient
from stage4.src.budget_enforcer import BudgetEnforcer


def test_evaluate_streams_with_diagnostics_structure():
    """Verify that evaluate_streams_with_diagnostics returns all expected keys and distribution data."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)

    # 3 streams with known item sizes
    streams = [
        [50.0, 50.0, 50.0, 50.0],          # 2 bins exact fit
        [80.0, 80.0, 80.0],                # 3 bins
        [20.0, 30.0, 40.0, 10.0, 50.0]     # 2 bins
    ]
    distributions = ["uniform", "weibull", "zipf"]

    res = sim.evaluate_streams_with_diagnostics(
        streams=streams,
        priority_fn=best_fit_priority,
        stream_distributions=distributions
    )

    assert "mean_excess_ratio" in res
    assert "stream_excess_ratios" in res
    assert "diagnostics" in res

    diag = res["diagnostics"]
    assert "worst_stream" in diag
    assert "best_stream" in diag
    assert "distribution_breakdown" in diag
    assert "avg_wasted_per_bin" in diag
    assert "underfilled_bins_pct" in diag
    assert "diagnostic_summary" in diag

    assert "uniform" in diag["distribution_breakdown"]
    assert "weibull" in diag["distribution_breakdown"]
    assert "zipf" in diag["distribution_breakdown"]


def test_diagnostic_summary_contains_actionable_counterexamples():
    """Verify that diagnostic summary text contains actionable breakdown and counterexample details."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    streams = [
        [30.0, 70.0, 40.0, 60.0],
        [90.0, 90.0, 90.0],
        [15.0, 25.0, 35.0, 45.0, 55.0]
    ]
    res = sim.evaluate_streams_with_diagnostics(streams, worst_fit_priority)
    summary = res["diagnostics"]["diagnostic_summary"]

    assert "Overall Mean Excess Ratio:" in summary
    assert "Distribution Breakdown:" in summary
    assert "Worst Stream:" in summary
    assert "Waste Pattern:" in summary
    assert "Counterexample Analysis:" in summary
    assert "Refinement Directive:" in summary


def test_evaluator_preserves_diagnostics_through_process_isolation():
    """Verify that Stage4Evaluator preserves diagnostics from the isolated worker process."""
    evaluator = Stage4Evaluator(bin_capacity=100.0)
    streams = [
        [40.0, 60.0, 50.0, 50.0],
        [70.0, 30.0, 80.0, 20.0]
    ]
    code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return -(remaining_capacity - item)\n"
    )
    result = evaluator.evaluate_candidate(code, streams)

    assert result.is_valid is True
    assert math.isfinite(result.fitness)
    assert result.diagnostics is not None
    assert "diagnostic_summary" in result.diagnostics
    assert "Overall Mean Excess Ratio" in result.diagnostics["diagnostic_summary"]


def test_evaluator_handles_invalid_code_without_crashing_diagnostics():
    """Verify that invalid candidate returns diagnostics=None and is_valid=False cleanly."""
    evaluator = Stage4Evaluator(bin_capacity=100.0)
    streams = [[50.0, 50.0]]
    bad_code = "def priority(a, b, c): import os; return 0.0"
    result = evaluator.evaluate_candidate(bad_code, streams)

    assert result.is_valid is False
    assert result.diagnostics is None
    assert "Forbidden import: os" in result.error_message


def test_archive_candidate_logs_diagnostics_availability():
    """Verify that Stage4IslandArchive tracks has_diagnostics in candidate logs."""
    archive = Stage4IslandArchive(num_islands=1, capacity_per_island=5)
    cand = Stage4Candidate(
        code="def priority(item, rem, cap): return -rem",
        is_valid=True,
        fitness=0.04,
        diagnostic_summary="Sample diagnostic summary text",
        is_seed=False
    )
    archive.add(cand)

    assert archive.valid_count == 1
    assert len(archive.candidate_logs) == 1
    assert archive.candidate_logs[0]["has_diagnostics"] is True


def test_archive_migration_preserves_diagnostics():
    """Verify that Stage4IslandArchive.migrate preserves diagnostic summaries on cloned candidates."""
    arch = Stage4IslandArchive(num_islands=3, capacity_per_island=5)
    cand = Stage4Candidate(
        code="def priority(item, rem, cap): return -rem",
        island_id=0,
        is_valid=True,
        fitness=0.035,
        diagnostic_summary="Migration Preservation Test Profile",
        is_seed=True
    )
    arch.add(cand)
    assert arch.islands[0][0].diagnostic_summary == "Migration Preservation Test Profile"

    arch.migrate(count=1)
    migrated_clone = arch.islands[1][0]
    assert migrated_clone.diagnostic_summary == "Migration Preservation Test Profile"
    assert migrated_clone.is_seed is True
    assert migrated_clone.mutation_type == "migration"


def test_arm_c_prompt_includes_parent_diagnostic_profiles(tmp_path):
    """Verify that run_arm_c_search builds prompts with diagnostic profiles from parents."""
    ledger_path = str(tmp_path / "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=50)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=True)
    evaluator = Stage4Evaluator(bin_capacity=100.0)

    streams = [
        [50.0, 50.0, 50.0, 50.0],
        [30.0, 70.0, 40.0, 60.0]
    ]

    captured_prompts = []
    original_query = client.query
    def mock_query(**kwargs):
        captured_prompts.append(kwargs.get("prompt", ""))
        return original_query(**kwargs)
    client.query = mock_query

    best_cand, archive = run_arm_c_search(
        client=client,
        evaluator=evaluator,
        dev_streams=streams,
        candidate_slots=5,
        seed=50501
    )

    assert best_cand is not None
    assert best_cand.is_valid is True
    # Verify that prompts sent to client actually contained parent diagnostic profiles
    assert len(captured_prompts) > 0
    for prompt_text in captured_prompts:
        assert "Execution Diagnostic Profile for Parent" in prompt_text
        assert "Overall Mean Excess Ratio:" in prompt_text
        assert "Distribution Breakdown:" in prompt_text

