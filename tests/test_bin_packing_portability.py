"""
Discovery Kernel v0.1: Second-Domain Portability Tests (Online 1D Bin Packing)
=============================================================================
Tests cross-domain portability of Discovery Kernel v0.1:
1. Declarative constraint validation (item coverage, capacity bounding, valid bin count).
2. Reference parity between method adapters and Stage 4 DeterministicBinPackingSimulator.
3. Fault injection: overcapacity, missing items, exceptions, and timeouts.
4. End-to-end controller execution: Phase 1 selection -> Freeze -> Phase 2 holdout evaluation.
5. Deterministic reproducibility across repeated trials.
6. Automated evidence reconstruction from machine-readable logs.
"""

import copy
import json
import math
import os
import pytest
from typing import Dict, Any, List

from discovery_kernel.problem_spec import (
    ObjectiveDirection,
    DatasetReference,
    ResourceLimits,
    ConstraintRule,
    BaselineMethod,
    ProblemSpecification,
    compute_file_sha256
)
from discovery_kernel.method_adapter import (
    ExecutionStatus,
    BinPackingBestFitAdapter,
    BinPackingFirstFitAdapter,
    BinPackingWorstFitAdapter,
    BinPackingFunctionAdapter,
    InvalidCapacityBinPackingAdapter,
    MissingItemBinPackingAdapter,
    HangingAdapter,
    ExceptionAdapter,
    validate_bin_packing_solution,
    calc_bin_packing_excess_ratio
)
from discovery_kernel.execution import ExecutionSupervisor
from discovery_kernel.evidence_store import EvidenceStore, reconstruct_and_verify_selection
from discovery_kernel.controller import DeterministicController, ControllerStateError
from stage4.src.simulator import (
    DeterministicBinPackingSimulator,
    best_fit_priority,
    first_fit_priority,
    worst_fit_priority
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_bin_packing_instance():
    """Small deterministic bin packing instance for testing."""
    return {
        "id": "bp_test_001",
        "bin_capacity": 100.0,
        "items": [70.0, 30.0, 60.0, 40.0, 50.0, 50.0, 80.0, 20.0, 10.0, 15.0]
    }


@pytest.fixture
def bin_packing_constraint():
    """Declarative constraint rule for bin packing."""
    def _validate(instance, solution):
        return validate_bin_packing_solution(instance, solution, bin_capacity=100.0)

    return ConstraintRule(
        name="bin_packing_validity",
        description="Every item assigned exactly once; no bin exceeds capacity 100.0",
        validator=_validate
    )


@pytest.fixture
def bin_packing_evaluator():
    """Evaluator function returning normalized excess ratio rho."""
    def _eval(instance, solution):
        return float(calc_bin_packing_excess_ratio(instance, solution, bin_capacity=100.0))
    return _eval


@pytest.fixture
def real_bin_packing_spec(bin_packing_constraint):
    """Problem specification binding to real repository bin packing datasets."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dev_path = os.path.join(repo_root, "benchmark_v1", "data", "bin_packing", "train.json")
    eval_path = os.path.join(repo_root, "benchmark_v1", "data", "bin_packing", "test.json")

    dev_hash = compute_file_sha256(dev_path)
    eval_hash = compute_file_sha256(eval_path)

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_count = len(json.load(f))
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_count = len(json.load(f))

    return ProblemSpecification(
        problem_id="online_1d_bin_packing",
        version="0.1.0-portability",
        objective_metric="excess_ratio",
        objective_direction=ObjectiveDirection.MINIMIZE,
        constraints=[bin_packing_constraint],
        evaluator_name="bin_packing_excess_ratio_evaluator",
        development_dataset=DatasetReference("development", dev_path, dev_hash, dev_count),
        evaluation_dataset=DatasetReference("evaluation", eval_path, eval_hash, eval_count),
        resource_limits=ResourceLimits(
            max_runtime_sec_per_instance=2.0,
            max_total_runtime_sec=30.0,
            max_evaluations=30
        ),
        baselines=[
            BaselineMethod("best_fit", "Best-Fit online heuristic"),
            BaselineMethod("first_fit", "First-Fit online heuristic"),
            BaselineMethod("worst_fit", "Worst-Fit online heuristic")
        ],
        experiment_id="EXP_TEST_BP_PORTABILITY_001"
    )


# =========================================================================
# Test 1: Declarative Constraint Validation
# =========================================================================

def test_bin_packing_constraint_validation(sample_bin_packing_instance):
    """Verifies strict detection of capacity overruns, missing items, and malformed assignments."""
    inst = sample_bin_packing_instance
    items = inst["items"]

    # 1. Valid assignment: pair up complementary items in bins of 100
    # [70, 30] -> bin 0, [60, 40] -> bin 1, [50, 50] -> bin 2, [80, 20] -> bin 3, [10, 15] -> bin 4
    valid_sol = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    ok, err = validate_bin_packing_solution(inst, valid_sol)
    assert ok is True
    assert err is None

    # 2. Overcapacity: pack all items in bin 0 (sum = 425 > 100)
    overcap_sol = [0] * len(items)
    ok, err = validate_bin_packing_solution(inst, overcap_sol)
    assert ok is False
    assert "capacity exceeded" in err

    # 3. Missing items: omit last 2 items
    missing_sol = valid_sol[:-2]
    ok, err = validate_bin_packing_solution(inst, missing_sol)
    assert ok is False
    assert "does not match item count" in err

    # 4. Duplicate/extraneous items: append extra assignment
    extra_sol = valid_sol + [0]
    ok, err = validate_bin_packing_solution(inst, extra_sol)
    assert ok is False
    assert "does not match item count" in err

    # 5. Non-integer assignment
    bad_type_sol = [0, "bin_0", 1, 1, 2, 2, 3, 3, 4, 4]
    ok, err = validate_bin_packing_solution(inst, bad_type_sol)
    assert ok is False
    assert "not an integer" in err

    # 6. Negative bin index
    neg_sol = [-1, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    ok, err = validate_bin_packing_solution(inst, neg_sol)
    assert ok is False
    assert "is negative" in err


# =========================================================================
# Test 2: Reference Parity with Stage 4 Simulator
# =========================================================================

def test_bin_packing_heuristics_reference_parity(sample_bin_packing_instance):
    """Verifies that adapters exactly reproduce Stage 4 simulator bin counts and excess ratios."""
    inst = sample_bin_packing_instance
    items = inst["items"]
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)

    # Reference scores
    ref_bf_bins, _, l1, ref_bf_rho = sim.pack_stream(items, best_fit_priority)
    ref_ff_bins, _, _, ref_ff_rho = sim.pack_stream(items, first_fit_priority)
    ref_wf_bins, _, _, ref_wf_rho = sim.pack_stream(items, worst_fit_priority)

    # Adapter outputs
    bf_adapter = BinPackingBestFitAdapter()
    ff_adapter = BinPackingFirstFitAdapter()
    wf_adapter = BinPackingWorstFitAdapter()

    bf_sol = bf_adapter.solve(inst)
    ff_sol = ff_adapter.solve(inst)
    wf_sol = wf_adapter.solve(inst)

    # Verify validity of all outputs
    for sol, name in [(bf_sol, "Best-Fit"), (ff_sol, "First-Fit"), (wf_sol, "Worst-Fit")]:
        ok, err = validate_bin_packing_solution(inst, sol)
        assert ok is True, f"{name} produced invalid assignment: {err}"

    # Verify exact bin count match
    assert len(set(bf_sol)) == ref_bf_bins
    assert len(set(ff_sol)) == ref_ff_bins
    assert len(set(wf_sol)) == ref_wf_bins

    # Verify excess ratio calculation match
    assert math.isclose(calc_bin_packing_excess_ratio(inst, bf_sol), ref_bf_rho, abs_tol=1e-6)
    assert math.isclose(calc_bin_packing_excess_ratio(inst, ff_sol), ref_ff_rho, abs_tol=1e-6)
    assert math.isclose(calc_bin_packing_excess_ratio(inst, wf_sol), ref_wf_rho, abs_tol=1e-6)

    # Verify known domain ordering (Best-Fit <= First-Fit <= Worst-Fit)
    assert len(set(bf_sol)) <= len(set(ff_sol)) <= len(set(wf_sol))


# =========================================================================
# Test 3: Fault Injection (Overcapacity, Missing Items, Exceptions, Timeouts)
# =========================================================================

def test_bin_packing_fault_injection(sample_bin_packing_instance, bin_packing_constraint, bin_packing_evaluator):
    """Supervisor isolates and distinctly classifies all failure modes in bin packing."""
    supervisor = ExecutionSupervisor(timeout_sec=0.4)
    inst = sample_bin_packing_instance

    # 3a: Overcapacity
    res_overcap = supervisor.execute_and_evaluate(
        adapter=InvalidCapacityBinPackingAdapter(),
        instance=inst,
        instance_id="overcap_001",
        evaluator_fn=bin_packing_evaluator,
        constraints=[bin_packing_constraint],
        objective_metric="excess_ratio"
    )
    assert res_overcap.is_valid is False
    assert res_overcap.status == ExecutionStatus.VALIDATION_ERROR
    assert "capacity exceeded" in res_overcap.error_message
    assert res_overcap.objective_score is None

    # 3b: Missing items
    res_missing = supervisor.execute_and_evaluate(
        adapter=MissingItemBinPackingAdapter(),
        instance=inst,
        instance_id="missing_001",
        evaluator_fn=bin_packing_evaluator,
        constraints=[bin_packing_constraint],
        objective_metric="excess_ratio"
    )
    assert res_missing.is_valid is False
    assert res_missing.status == ExecutionStatus.VALIDATION_ERROR
    assert "does not match item count" in res_missing.error_message

    # 3c: Timeout
    res_timeout = supervisor.execute_and_evaluate(
        adapter=HangingAdapter(sleep_sec=5.0),
        instance=inst,
        instance_id="timeout_001",
        evaluator_fn=bin_packing_evaluator,
        constraints=[bin_packing_constraint],
        objective_metric="excess_ratio"
    )
    assert res_timeout.is_valid is False
    assert res_timeout.status == ExecutionStatus.TIMEOUT
    assert "TimeoutError" in res_timeout.error_message

    # 3d: Exception
    res_exc = supervisor.execute_and_evaluate(
        adapter=ExceptionAdapter(),
        instance=inst,
        instance_id="exc_001",
        evaluator_fn=bin_packing_evaluator,
        constraints=[bin_packing_constraint],
        objective_metric="excess_ratio"
    )
    assert res_exc.is_valid is False
    assert res_exc.status == ExecutionStatus.EXCEPTION
    assert "Simulated internal worker crash" in res_exc.error_message


# =========================================================================
# Test 4: End-to-End Controller Execution on Real Bin Packing Data
# =========================================================================

def test_bin_packing_controller_end_to_end(tmp_path, real_bin_packing_spec, bin_packing_evaluator):
    """Controller executes Phase 1 selection, freezes selection, and runs holdout evaluation."""
    store = EvidenceStore(str(tmp_path / "bp_e2e"), "EXP_BP_E2E")
    ctrl = DeterministicController(real_bin_packing_spec, store, bin_packing_evaluator)

    methods = [
        BinPackingBestFitAdapter(),
        BinPackingFirstFitAdapter(),
        BinPackingWorstFitAdapter(),
        InvalidCapacityBinPackingAdapter("fault_overcapacity"),
        MissingItemBinPackingAdapter("fault_missing_items")
    ]

    # Phase 1: Development
    frozen = ctrl.run_development_phase(methods, instance_limit=3)

    # Disqualified methods must be rejected
    overcap_rank = [r for r in frozen.dev_rankings if r["method_id"] == "fault_overcapacity"][0]
    missing_rank = [r for r in frozen.dev_rankings if r["method_id"] == "fault_missing_items"][0]
    assert overcap_rank["is_fully_valid"] is False
    assert missing_rank["is_fully_valid"] is False

    # Valid methods ranked by excess ratio: Best-Fit beats First-Fit and Worst-Fit
    assert frozen.champion_method_id == "best_fit"
    assert frozen.is_frozen is True

    # Phase 2: Final Evaluation
    champ_adapter = BinPackingBestFitAdapter()
    baseline_adapter = BinPackingFirstFitAdapter()

    final_report = ctrl.run_final_evaluation_phase(
        frozen_selection=frozen,
        champion_adapter=champ_adapter,
        baseline_adapters=[baseline_adapter],
        instance_limit=3
    )

    assert final_report.champion_method_id == "best_fit"
    assert final_report.all_instances_valid is True
    assert final_report.matched_instance_count == 3
    # Best-Fit achieves <= excess ratio than First-Fit
    assert final_report.champion_eval_score <= final_report.baseline_eval_scores["first_fit"]


# =========================================================================
# Test 5: Deterministic Reproducibility
# =========================================================================

def test_bin_packing_reproducibility(tmp_path, real_bin_packing_spec, bin_packing_evaluator):
    """Repeating deterministic bin packing runs yields identical scores and selection decisions."""
    methods = [
        BinPackingBestFitAdapter(),
        BinPackingFirstFitAdapter(),
        BinPackingWorstFitAdapter()
    ]

    # Run 1
    store1 = EvidenceStore(str(tmp_path / "bp_rep1"), "EXP_BP_REP1")
    ctrl1 = DeterministicController(real_bin_packing_spec, store1, bin_packing_evaluator)
    frozen1 = ctrl1.run_development_phase(methods, instance_limit=3)

    # Run 2
    store2 = EvidenceStore(str(tmp_path / "bp_rep2"), "EXP_BP_REP2")
    ctrl2 = DeterministicController(real_bin_packing_spec, store2, bin_packing_evaluator)
    frozen2 = ctrl2.run_development_phase(methods, instance_limit=3)

    assert frozen1.champion_method_id == frozen2.champion_method_id == "best_fit"
    assert frozen1.champion_dev_score == frozen2.champion_dev_score
    assert len(frozen1.dev_rankings) == len(frozen2.dev_rankings)

    for r1, r2 in zip(frozen1.dev_rankings, frozen2.dev_rankings):
        assert r1["method_id"] == r2["method_id"]
        assert r1["mean_score"] == r2["mean_score"]
        assert r1["valid_count"] == r2["valid_count"]


# =========================================================================
# Test 6: Evidence Reconstruction
# =========================================================================

def test_bin_packing_evidence_reconstruction(tmp_path, real_bin_packing_spec, bin_packing_evaluator):
    """Reconstructs bin packing experiment decision directly from append-only logs."""
    store = EvidenceStore(str(tmp_path / "bp_recon"), "EXP_BP_RECON")
    ctrl = DeterministicController(real_bin_packing_spec, store, bin_packing_evaluator)

    methods = [
        BinPackingBestFitAdapter(),
        BinPackingFirstFitAdapter(),
        BinPackingWorstFitAdapter()
    ]
    frozen = ctrl.run_development_phase(methods, instance_limit=3)
    ctrl.run_final_evaluation_phase(frozen, BinPackingBestFitAdapter(), [BinPackingFirstFitAdapter()], instance_limit=2)

    reconstruction = reconstruct_and_verify_selection(store.output_dir)
    assert reconstruction["verified"] is True
    assert reconstruction["recorded_champion"] == "best_fit"
    assert reconstruction["recomputed_champion"] == "best_fit"
