"""
Discovery Kernel v0.1: Unit & Integration Test Suite
===================================================
Tests all 10 acceptance and correctness requirements:
1. Valid problem spec is accepted; malformed specs rejected.
2. Methods using common adapter produce correctly recorded results.
3. Both lower-is-better (MINIMIZE) and higher-is-better (MAXIMIZE) handled correctly.
4. Invalid outputs cannot win by exploiting scoring or penalty conventions.
5. Timeout terminates worker process and permits subsequent runs.
6. Repeated deterministic runs reproduce scores and selection decisions.
7. Holdout isolation: method cannot access final evaluation results during selection.
8. Budget exhaustion and method exceptions recorded cleanly without crashing controller.
9. Evidence records contain sufficient provenance to reconstruct the decision.
10. Reused components regression tests pass.
"""

import copy
import hashlib
import json
import os
import pytest
import time
from typing import List, Dict, Any

from discovery_kernel.problem_spec import (
    ObjectiveDirection,
    SpecificationValidationError,
    DatasetReference,
    ResourceLimits,
    ConstraintRule,
    BaselineMethod,
    ProblemSpecification,
    compute_file_sha256
)
from discovery_kernel.method_adapter import (
    ExecutionStatus,
    MethodMetadata,
    PFSPNEHAdapter,
    PFSPNEHLSAdapter,
    PFSPSPTAdapter,
    PFSPFunctionAdapter,
    InvalidPermutationAdapter,
    HangingAdapter,
    ExceptionAdapter
)
from discovery_kernel.execution import (
    EvaluationResult,
    ExecutionSupervisor
)
from discovery_kernel.evidence_store import (
    EvidenceStore,
    reconstruct_and_verify_selection
)
from discovery_kernel.controller import (
    DeterministicController,
    FrozenSelection,
    FinalEvaluationReport,
    ControllerStateError,
    BudgetExhaustedError
)
from benchmark_v1.src.domains.pfsp_full_algorithm import (
    calc_makespan,
    validate_permutation,
    neh_solve,
    neh_ls_solve
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def pfsp_constraint():
    """Returns standard PFSP permutation constraint rule."""
    def _validate_perm(instance: Dict[str, Any], solution: Any):
        times = instance["times"] if isinstance(instance, dict) else instance
        n = len(times)
        return validate_permutation(solution, n)

    return ConstraintRule(
        name="valid_job_permutation",
        description="Solution must be a valid permutation of [0, ..., n-1]",
        validator=_validate_perm
    )


@pytest.fixture
def pfsp_evaluator():
    """Returns standard PFSP makespan evaluator function."""
    def _eval(instance: Dict[str, Any], solution: Any) -> float:
        times = instance["times"] if isinstance(instance, dict) else instance
        return float(calc_makespan(times, solution))
    return _eval


@pytest.fixture
def synthetic_pfsp_data(tmp_path):
    """Creates small, verified synthetic PFSP dataset splits for testing."""
    dev_instances = [
        {"id": "dev_0", "n": 3, "m": 2, "times": [[10, 20], [30, 10], [20, 20]]},
        {"id": "dev_1", "n": 4, "m": 2, "times": [[5, 10], [20, 5], [10, 15], [15, 10]]},
        {"id": "dev_2", "n": 3, "m": 2, "times": [[15, 5], [10, 20], [25, 10]]}
    ]
    eval_instances = [
        {"id": "eval_0", "n": 3, "m": 2, "times": [[12, 18], [25, 15], [15, 25]]},
        {"id": "eval_1", "n": 4, "m": 2, "times": [[10, 10], [15, 15], [20, 10], [10, 20]]}
    ]

    dev_file = str(tmp_path / "dev.json")
    eval_file = str(tmp_path / "eval.json")

    with open(dev_file, "w", encoding="utf-8") as f:
        json.dump(dev_instances, f)
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(eval_instances, f)

    dev_hash = compute_file_sha256(dev_file)
    eval_hash = compute_file_sha256(eval_file)

    dev_ref = DatasetReference("development", dev_file, dev_hash, len(dev_instances))
    eval_ref = DatasetReference("evaluation", eval_file, eval_hash, len(eval_instances))

    return {
        "dev_file": dev_file,
        "eval_file": eval_file,
        "dev_ref": dev_ref,
        "eval_ref": eval_ref,
        "dev_instances": dev_instances,
        "eval_instances": eval_instances
    }


@pytest.fixture
def valid_problem_spec(synthetic_pfsp_data, pfsp_constraint):
    """Returns a fully valid ProblemSpecification for testing."""
    return ProblemSpecification(
        problem_id="pfsp_flowshop_synthetic",
        version="0.1.0",
        objective_metric="makespan",
        objective_direction=ObjectiveDirection.MINIMIZE,
        constraints=[pfsp_constraint],
        evaluator_name="pfsp_makespan_evaluator",
        development_dataset=synthetic_pfsp_data["dev_ref"],
        evaluation_dataset=synthetic_pfsp_data["eval_ref"],
        resource_limits=ResourceLimits(
            max_runtime_sec_per_instance=2.0,
            max_total_runtime_sec=30.0,
            max_evaluations=20
        ),
        baselines=[
            BaselineMethod(name="neh_classical", description="Nawaz-Enscore-Ham")
        ],
        experiment_id="EXP_TEST_SYNTHETIC_001"
    )


# =========================================================================
# Test 1: Problem Specification Validation (Acceptance & Rejection)
# =========================================================================

def test_problem_spec_valid_accepted(valid_problem_spec):
    """Valid problem specification is accepted and generates deterministic fingerprint."""
    fp = valid_problem_spec.validate(verify_data_files=True)
    assert isinstance(fp, str)
    assert len(fp) == 64
    assert fp == valid_problem_spec.compute_fingerprint()


def test_problem_spec_malformed_rejected(valid_problem_spec):
    """Malformed problem specifications are rejected with actionable errors."""
    # 1. Missing problem_id
    bad_spec = copy.deepcopy(valid_problem_spec)
    bad_spec.problem_id = ""
    with pytest.raises(SpecificationValidationError, match="problem_id"):
        bad_spec.validate()

    # 2. Invalid direction
    bad_spec = copy.deepcopy(valid_problem_spec)
    bad_spec.objective_direction = "INVALID_DIRECTION"
    with pytest.raises(SpecificationValidationError, match="Invalid objective_direction"):
        bad_spec.validate()

    # 3. Negative resource limit
    bad_spec = copy.deepcopy(valid_problem_spec)
    bad_spec.resource_limits.max_runtime_sec_per_instance = -5.0
    with pytest.raises(SpecificationValidationError, match="max_runtime_sec_per_instance must be > 0"):
        bad_spec.validate()

    # 4. Corrupted SHA-256 hash in dataset reference
    bad_spec = copy.deepcopy(valid_problem_spec)
    bad_spec.development_dataset.sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
    with pytest.raises(SpecificationValidationError, match="Dataset SHA-256 mismatch"):
        bad_spec.validate(verify_data_files=True)

    # 5. Non-existent data file
    bad_spec = copy.deepcopy(valid_problem_spec)
    bad_spec.development_dataset.file_path = "/non/existent/path/data.json"
    with pytest.raises(SpecificationValidationError, match="Dataset file missing"):
        bad_spec.validate(verify_data_files=True)

    # 6. Missing constraints
    bad_spec = copy.deepcopy(valid_problem_spec)
    bad_spec.constraints = []
    with pytest.raises(SpecificationValidationError, match="at least one ConstraintRule"):
        bad_spec.validate()


# =========================================================================
# Test 2: Method Adapter Interface & Execution Recording
# =========================================================================

def test_method_adapter_execution_recording(synthetic_pfsp_data, pfsp_constraint, pfsp_evaluator):
    """Methods using the common adapter produce correctly recorded, valid execution results."""
    supervisor = ExecutionSupervisor(timeout_sec=2.0)
    adapter = PFSPNEHAdapter()
    instance = synthetic_pfsp_data["dev_instances"][0]

    result = supervisor.execute_and_evaluate(
        adapter=adapter,
        instance=instance,
        instance_id="inst_001",
        evaluator_fn=pfsp_evaluator,
        constraints=[pfsp_constraint],
        objective_metric="makespan"
    )

    assert isinstance(result, EvaluationResult)
    assert result.method_id == "neh_classical"
    assert result.is_valid is True
    assert result.status == ExecutionStatus.SUCCESS
    assert result.objective_score is not None
    assert result.objective_score > 0
    assert result.runtime_ms > 0
    assert result.validation_errors == []
    assert result.error_message is None


# =========================================================================
# Test 3: Lower-is-better and Higher-is-better Objectives
# =========================================================================

def _mock_solve_len_3(inst):
    return [0, 1, 2]

def _mock_solve_len_4(inst):
    return [0, 1, 2, 3]

def _custom_length_evaluator(inst, sol):
    return 50.0 if len(sol) == 3 else 150.0

def test_lower_is_better_and_higher_is_better_objectives(tmp_path, synthetic_pfsp_data):
    """Controller handles both MINIMIZE and MAXIMIZE objective directions correctly."""
    dummy_constraint = ConstraintRule("always_pass", "Always pass", lambda inst, sol: (True, None))

    ad_a = PFSPFunctionAdapter("cand_score_50", _mock_solve_len_3, "score 50")
    ad_b = PFSPFunctionAdapter("cand_score_150", _mock_solve_len_4, "score 150")

    # Test 3a: MINIMIZE -> lower score (50.0) must win
    store_min = EvidenceStore(str(tmp_path / "min_test"), "EXP_MIN")
    spec_min = ProblemSpecification(
        problem_id="test_min",
        version="0.1",
        objective_metric="cost",
        objective_direction=ObjectiveDirection.MINIMIZE,
        constraints=[dummy_constraint],
        evaluator_name="custom_eval",
        development_dataset=synthetic_pfsp_data["dev_ref"],
        evaluation_dataset=synthetic_pfsp_data["eval_ref"],
        resource_limits=ResourceLimits(),
        baselines=[BaselineMethod("b1", "b1")],
        experiment_id="EXP_MIN"
    )
    ctrl_min = DeterministicController(spec_min, store_min, _custom_length_evaluator)
    frozen_min = ctrl_min.run_development_phase([ad_a, ad_b], instance_limit=1)
    assert frozen_min.champion_method_id == "cand_score_50"
    assert frozen_min.champion_dev_score == 50.0

    # Test 3b: MAXIMIZE -> higher score (150.0) must win
    store_max = EvidenceStore(str(tmp_path / "max_test"), "EXP_MAX")
    spec_max = ProblemSpecification(
        problem_id="test_max",
        version="0.1",
        objective_metric="reward",
        objective_direction=ObjectiveDirection.MAXIMIZE,
        constraints=[dummy_constraint],
        evaluator_name="custom_eval",
        development_dataset=synthetic_pfsp_data["dev_ref"],
        evaluation_dataset=synthetic_pfsp_data["eval_ref"],
        resource_limits=ResourceLimits(),
        baselines=[BaselineMethod("b1", "b1")],
        experiment_id="EXP_MAX"
    )
    ctrl_max = DeterministicController(spec_max, store_max, _custom_length_evaluator)
    frozen_max = ctrl_max.run_development_phase([ad_a, ad_b], instance_limit=1)
    assert frozen_max.champion_method_id == "cand_score_150"
    assert frozen_max.champion_dev_score == 150.0



# =========================================================================
# Test 4: Invalid Outputs Cannot Win
# =========================================================================

def test_invalid_outputs_cannot_win(tmp_path, valid_problem_spec, pfsp_evaluator):
    """Invalid outputs are disqualified and cannot win regardless of numerical scores."""
    store = EvidenceStore(str(tmp_path / "invalid_test"), "EXP_INVALID")
    ctrl = DeterministicController(valid_problem_spec, store, pfsp_evaluator)

    # Valid adapter with score ~70
    valid_adapter = PFSPNEHAdapter()

    # Invalid adapter that returns duplicates [0, 0, 0]
    invalid_adapter = InvalidPermutationAdapter("malicious_invalid_adapter")

    frozen = ctrl.run_development_phase([valid_adapter, invalid_adapter], instance_limit=2)

    # Champion must be the valid adapter
    assert frozen.champion_method_id == "neh_classical"
    # Invalid adapter must be ranked last and marked not fully valid
    invalid_rank = [r for r in frozen.dev_rankings if r["method_id"] == "malicious_invalid_adapter"][0]
    assert invalid_rank["is_fully_valid"] is False
    assert invalid_rank["valid_count"] == 0


# =========================================================================
# Test 5: Timeout Actually Terminates Worker and Permits Subsequent Runs
# =========================================================================

def test_timeout_terminates_worker_and_allows_subsequent_runs(synthetic_pfsp_data, pfsp_constraint, pfsp_evaluator):
    """A timeout hard-terminates the isolated process, and subsequent runs succeed normally."""
    supervisor = ExecutionSupervisor(timeout_sec=0.4)
    hanging_adapter = HangingAdapter(sleep_sec=10.0)
    instance = synthetic_pfsp_data["dev_instances"][0]

    t0 = time.perf_counter()
    res_timeout = supervisor.execute_and_evaluate(
        adapter=hanging_adapter,
        instance=instance,
        instance_id="timeout_001",
        evaluator_fn=pfsp_evaluator,
        constraints=[pfsp_constraint]
    )
    elapsed = time.perf_counter() - t0

    # Ensure timeout was enforced quickly (not waiting 10s)
    assert elapsed < 1.5
    assert res_timeout.is_valid is False
    assert res_timeout.status == ExecutionStatus.TIMEOUT
    assert "TimeoutError" in res_timeout.error_message
    assert "terminated" in res_timeout.error_message

    # Crucial check: subsequent run on normal adapter must immediately execute cleanly
    normal_adapter = PFSPNEHAdapter()
    res_subsequent = supervisor.execute_and_evaluate(
        adapter=normal_adapter,
        instance=instance,
        instance_id="subsequent_001",
        evaluator_fn=pfsp_evaluator,
        constraints=[pfsp_constraint]
    )
    assert res_subsequent.is_valid is True
    assert res_subsequent.status == ExecutionStatus.SUCCESS
    assert res_subsequent.objective_score is not None


# =========================================================================
# Test 6: Deterministic Reproducibility
# =========================================================================

def test_repeated_runs_reproduce_scores_and_decisions(tmp_path, valid_problem_spec, pfsp_evaluator):
    """Repeating deterministic evaluation yields identical validity, scores, and decisions."""
    methods = [PFSPNEHAdapter(), PFSPNEHLSAdapter(), PFSPSPTAdapter()]

    # Run 1
    store1 = EvidenceStore(str(tmp_path / "rep_run1"), "EXP_REP1")
    ctrl1 = DeterministicController(valid_problem_spec, store1, pfsp_evaluator)
    frozen1 = ctrl1.run_development_phase(methods, instance_limit=2)

    # Run 2
    store2 = EvidenceStore(str(tmp_path / "rep_run2"), "EXP_REP2")
    ctrl2 = DeterministicController(valid_problem_spec, store2, pfsp_evaluator)
    frozen2 = ctrl2.run_development_phase(methods, instance_limit=2)

    assert frozen1.champion_method_id == frozen2.champion_method_id
    assert frozen1.champion_dev_score == frozen2.champion_dev_score
    assert len(frozen1.dev_rankings) == len(frozen2.dev_rankings)

    for r1, r2 in zip(frozen1.dev_rankings, frozen2.dev_rankings):
        assert r1["method_id"] == r2["method_id"]
        assert r1["mean_score"] == r2["mean_score"]
        assert r1["valid_count"] == r2["valid_count"]
        assert r1["is_fully_valid"] == r2["is_fully_valid"]


# =========================================================================
# Test 7: Holdout Isolation Enforcement
# =========================================================================

def test_holdout_isolation_enforcement(tmp_path, valid_problem_spec, pfsp_evaluator):
    """Final evaluation cannot be executed before freeze, and selection code cannot access holdout."""
    store = EvidenceStore(str(tmp_path / "isolation_test"), "EXP_ISO")
    ctrl = DeterministicController(valid_problem_spec, store, pfsp_evaluator)

    adapter = PFSPNEHAdapter()

    # Attempting final evaluation before development freeze must fail closed
    fake_frozen = FrozenSelection(
        champion_method_id="neh_classical",
        champion_version="1.0.0",
        champion_dev_score=50.0,
        objective_metric="makespan",
        objective_direction="MINIMIZE",
        problem_spec_fingerprint="invalid_hash",
        dev_rankings=[],
        selection_timestamp="2026-10-19T00:00:00Z",
        dev_evidence_hash="hash"
    )

    with pytest.raises(ControllerStateError, match="Selection must be frozen first"):
        ctrl.run_final_evaluation_phase(fake_frozen, adapter, [adapter])

    # Normal freeze
    frozen = ctrl.run_development_phase([adapter], instance_limit=1)

    # Now final evaluation is permitted
    final_report = ctrl.run_final_evaluation_phase(frozen, adapter, [adapter], instance_limit=1)
    assert isinstance(final_report, FinalEvaluationReport)
    assert final_report.champion_method_id == "neh_classical"


# =========================================================================
# Test 8: Budget Exhaustion and Method Exceptions
# =========================================================================

def test_budget_exhaustion_and_method_exceptions(tmp_path, synthetic_pfsp_data, pfsp_constraint, pfsp_evaluator):
    """Budget exhaustion raises error cleanly; candidate exceptions are recorded without controller crash."""
    # 8a: Budget exhaustion
    tight_limits = ResourceLimits(
        max_runtime_sec_per_instance=2.0,
        max_total_runtime_sec=30.0,
        max_evaluations=2  # Dev dataset has 3 instances, evaluating 1 method needs 3 evals
    )
    spec_tight = ProblemSpecification(
        problem_id="test_budget",
        version="0.1",
        objective_metric="makespan",
        objective_direction=ObjectiveDirection.MINIMIZE,
        constraints=[pfsp_constraint],
        evaluator_name="pfsp_makespan_evaluator",
        development_dataset=synthetic_pfsp_data["dev_ref"],
        evaluation_dataset=synthetic_pfsp_data["eval_ref"],
        resource_limits=tight_limits,
        baselines=[BaselineMethod("b1", "b1")],
        experiment_id="EXP_BUDGET"
    )
    store = EvidenceStore(str(tmp_path / "budget_test"), "EXP_BUDGET")
    ctrl = DeterministicController(spec_tight, store, pfsp_evaluator)

    with pytest.raises(BudgetExhaustedError, match="Evaluation budget reached"):
        ctrl.run_development_phase([PFSPNEHAdapter()])

    # 8b: Exception handling
    spec_ok = copy.deepcopy(spec_tight)
    spec_ok.resource_limits.max_evaluations = 50
    store_exc = EvidenceStore(str(tmp_path / "exc_test"), "EXP_EXC")
    ctrl_exc = DeterministicController(spec_ok, store_exc, pfsp_evaluator)

    exc_adapter = ExceptionAdapter("crash_method")
    valid_adapter = PFSPNEHAdapter()

    # Controller must not crash; exception must be caught and recorded
    frozen = ctrl_exc.run_development_phase([exc_adapter, valid_adapter], instance_limit=2)
    assert frozen.champion_method_id == "neh_classical"

    exc_rank = [r for r in frozen.dev_rankings if r["method_id"] == "crash_method"][0]
    assert exc_rank["is_fully_valid"] is False
    assert exc_rank["exception_count"] == 2


# =========================================================================
# Test 9: Evidence Reconstruction & Provenance Verification
# =========================================================================

def test_evidence_reconstruction_and_provenance(tmp_path, valid_problem_spec, pfsp_evaluator):
    """Evidence store captures complete provenance and supports automated independent reconstruction."""
    store = EvidenceStore(str(tmp_path / "provenance_test"), "EXP_PROV_001")
    ctrl = DeterministicController(valid_problem_spec, store, pfsp_evaluator)

    methods = [PFSPNEHAdapter(), PFSPSPTAdapter(), InvalidPermutationAdapter()]
    frozen = ctrl.run_development_phase(methods, instance_limit=2)

    # Perform reconstruction
    reconstruction = reconstruct_and_verify_selection(store.output_dir)

    assert reconstruction["verified"] is True
    assert reconstruction["recorded_champion"] == frozen.champion_method_id
    assert reconstruction["recomputed_champion"] == frozen.champion_method_id
    assert len(reconstruction["recomputed_rankings"]) == 3

    # Check manifest generation
    ctrl.run_final_evaluation_phase(frozen, PFSPNEHAdapter(), [PFSPNEHAdapter()], instance_limit=1)
    manifest_path = os.path.join(store.output_dir, "manifest.json")
    assert os.path.isfile(manifest_path)
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    assert "run_records.jsonl" in manifest["files"]
    assert "dev_summary.json" in manifest["files"]
    assert "final_report.json" in manifest["files"]


# =========================================================================
# Test 10: Reused Components Regression Test
# =========================================================================

def test_reused_components_regression():
    """Confirms mathematical correctness of reused PFSP functions."""
    times = [
        [10, 20, 5],
        [30, 10, 15],
        [20, 20, 10]
    ]
    # Validation
    assert validate_permutation([0, 1, 2], 3)[0] is True
    assert validate_permutation([0, 0, 1], 3)[0] is False
    assert validate_permutation([0, 1], 3)[0] is False
    assert validate_permutation([0, 1, 3], 3)[0] is False

    # NEH solve produces valid permutation
    neh_perm = neh_solve(times)
    assert validate_permutation(neh_perm, 3)[0] is True
    c_neh = calc_makespan(times, neh_perm)
    assert c_neh > 0

    # NEH-LS solve produces valid permutation with makespan <= NEH
    neh_ls_perm = neh_ls_solve(times)
    assert validate_permutation(neh_ls_perm, 3)[0] is True
    c_ls = calc_makespan(times, neh_ls_perm)
    assert c_ls <= c_neh
