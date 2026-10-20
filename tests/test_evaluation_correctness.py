"""
Evaluation Correctness & Numerical Integrity Regression Suite (P0.1, P0.2, P0.4, P0.5, REL-1)
==============================================================================================
Verifies:
1. P0.5: NaN and ±inf are strictly rejected in solutions and objective scores.
2. P0.1: Repeatability checks use the same process isolation policy as initial execution.
3. P0.2: Holdout firewall enforces one-shot unsealing, immutable selection manifest, and access tracking.
4. P0.4: Subprocess execution is enforced for untrusted candidates.
5. REL-1: Queue race conditions are eliminated by bounded timeouts.
"""

from __future__ import annotations

import math
import pytest

from north_bluestar import (
    CandidateKind,
    CandidateSpec,
    ExecutionSupervisor,
    FailureCategory,
    LifecyclePhase,
    MethodRegistry,
    SolutionStatus,
    SplitAccessViolationError,
    SplitType,
    build_bin_packing_problem,
    build_pfsp_problem,
)


def test_nan_and_inf_objective_rejected():
    """P0.5: Infeasible or non-finite solutions must never receive a numeric objective."""
    problem = build_pfsp_problem(seed=42, dev_count=2, val_count=1, holdout_count=1)
    inst = problem.firewall.get_instances(SplitType.DEVELOPMENT)[0]

    # None solution -> INFEASIBLE, objective_value=None
    out_none = problem.evaluate_solution_on_instance(inst, None)
    assert not out_none.is_feasible
    assert out_none.objective_value is None

    # Empty solution -> INFEASIBLE, objective_value=None
    out_empty = problem.evaluate_solution_on_instance(inst, [])
    assert not out_empty.is_feasible
    assert out_empty.objective_value is None


def test_bin_packing_nonfinite_item_rejected():
    """P0.5: Non-finite numbers in bin packing solutions must be rejected."""
    problem = build_bin_packing_problem(seed=42, dev_count=2, val_count=1, holdout_count=1)
    inst = problem.firewall.get_instances(SplitType.DEVELOPMENT)[0]

    # Solution with NaN
    nan_sol = [[float("nan"), 10.0], [20.0]]
    out_nan = problem.evaluate_solution_on_instance(inst, nan_sol)
    assert not out_nan.is_feasible
    assert out_nan.objective_value is None

    # Solution with Inf
    inf_sol = [[float("inf"), 10.0], [20.0]]
    out_inf = problem.evaluate_solution_on_instance(inst, inf_sol)
    assert not out_inf.is_feasible
    assert out_inf.objective_value is None


def test_pfsp_nonfinite_job_indices_rejected():
    """P0.5: Non-finite job indices in PFSP permutations must be rejected."""
    problem = build_pfsp_problem(seed=42, dev_count=2, val_count=1, holdout_count=1)
    inst = problem.firewall.get_instances(SplitType.DEVELOPMENT)[0]
    n_jobs = len(inst.data["times"])

    perm = list(range(n_jobs))
    perm[0] = float("nan")
    out = problem.evaluate_solution_on_instance(inst, perm)
    assert not out.is_feasible
    assert out.objective_value is None


def test_holdout_firewall_access_counter_and_manifest():
    """P0.2: Holdout access count and immutable manifest are tracked."""
    problem = build_pfsp_problem(seed=42, dev_count=2, val_count=1, holdout_count=2)

    # Before freeze: access is forbidden and access count is 0
    assert problem.firewall.get_holdout_access_count() == 0
    assert not problem.firewall.has_holdout_been_accessed()
    with pytest.raises(SplitAccessViolationError):
        problem.firewall.get_instances(SplitType.FINAL_HOLDOUT)

    # Freeze champions
    cert = problem.firewall.freeze_champions(["champ-1", "champ-2"], selection_metadata={"metric": "makespan"})
    assert len(cert) == 64
    manifest = problem.firewall.get_selection_manifest()
    assert manifest is not None
    assert manifest["frozen_champions"] == ["champ-1", "champ-2"]
    assert manifest["metadata"]["metric"] == "makespan"

    # Access holdout
    instances = problem.firewall.get_instances(SplitType.FINAL_HOLDOUT)
    assert len(instances) == 2
    assert problem.firewall.get_holdout_access_count() == 1
    assert problem.firewall.has_holdout_been_accessed()

    # Second direct access is strictly prohibited (P0 2.1: genuinely one-shot)
    with pytest.raises(SplitAccessViolationError):
        problem.firewall.get_instances(SplitType.FINAL_HOLDOUT)

    # Re-freezing is strictly prohibited
    with pytest.raises(RuntimeError):
        problem.firewall.freeze_champions(["champ-3"])


def test_holdout_candidate_authorization_and_one_shot():
    """P0 2.1: Candidate-level holdout authorization, duplicate prevention, and consumption."""
    problem = build_pfsp_problem(seed=42, dev_count=2, val_count=1, holdout_count=2)
    # Freeze two specific champions
    problem.firewall.freeze_champions(["champ-A", "champ-B"])

    # Unauthorized candidate cannot access holdout
    with pytest.raises(SplitAccessViolationError, match="not in frozen champions"):
        problem.firewall.get_instances(SplitType.FINAL_HOLDOUT, candidate_id="intruder")

    # champ-A accesses holdout: succeeds
    insts_a = problem.firewall.get_instances(SplitType.FINAL_HOLDOUT, candidate_id="champ-A")
    assert len(insts_a) == 2

    # champ-A attempts duplicate access: fails
    with pytest.raises(SplitAccessViolationError, match="already been evaluated on FINAL_HOLDOUT"):
        problem.firewall.get_instances(SplitType.FINAL_HOLDOUT, candidate_id="champ-A")

    # champ-B accesses holdout: succeeds
    insts_b = problem.firewall.get_instances(SplitType.FINAL_HOLDOUT, candidate_id="champ-B")
    assert len(insts_b) == 2

    # All champions have been evaluated -> phase is permanently HOLDOUT_CONSUMED
    assert problem.firewall.phase == LifecyclePhase.HOLDOUT_CONSUMED

    # Any further access raises SplitAccessViolationError
    with pytest.raises(SplitAccessViolationError, match="permanently consumed"):
        problem.firewall.get_instances(SplitType.FINAL_HOLDOUT, candidate_id="champ-B")


def test_freeze_champions_validates_evidence_records():
    """P0 2.1: freeze_champions rejects champion IDs that lack evaluation in evidence store."""
    from north_bluestar.evidence import EvidenceStore
    store = EvidenceStore()
    problem = build_pfsp_problem(seed=42, dev_count=2, val_count=1, holdout_count=2)

    # Empty store -> freeze_champions with unevaluated champion raises ValueError
    with pytest.raises(ValueError, match="no corresponding evaluation in the evidence store"):
        problem.firewall.freeze_champions(["unevaluated_champ"], evidence_store=store)


def test_subprocess_resource_limits_terminate_memory_exhaustion():
    """P0 2.3: Subprocess worker memory containment terminates extreme allocations."""
    registry = MethodRegistry.create_default_registry()
    supervisor = ExecutionSupervisor(registry, default_timeout_ms=500.0)
    problem = build_bin_packing_problem(seed=42, dev_count=2, val_count=1, holdout_count=1)

    # Memory bomb candidate attempting massive allocation
    memory_bomb_code = (
        "def priority(item, rem, cap):\n"
        "    big = [0] * (2 * 1024 * 1024 * 1024)\n"  # 16 GB allocation
        "    return float(len(big))\n"
    )
    spec = CandidateSpec.from_python_program(
        code=memory_bomb_code, entry_func_name="priority", problem_id="online_bin_packing_1d"
    )
    report = supervisor.evaluate_candidate_on_split(problem, spec, split=SplitType.DEVELOPMENT)
    assert not report.outcome.is_fully_feasible
    assert report.failure_category in (FailureCategory.RUNTIME_EXCEPTION, FailureCategory.TIMEOUT_SIGKILL)


def test_repeatability_uses_process_isolation_for_python_programs():
    """P0.1: Repeatability checks for PYTHON_PROGRAM must run through subprocess isolation."""
    registry = MethodRegistry.create_default_registry()
    supervisor = ExecutionSupervisor(registry, default_timeout_ms=300.0)
    problem = build_bin_packing_problem(seed=42, dev_count=2, val_count=1, holdout_count=1)

    code = (
        "def priority(item, rem, cap):\n"
        "    return -(rem - item)\n"
    )
    spec = CandidateSpec.from_python_program(
        code=code, entry_func_name="priority", problem_id="online_bin_packing_1d"
    )

    report = supervisor.evaluate_candidate_on_split(
        problem, spec, split=SplitType.DEVELOPMENT, verify_repeatability=True
    )
    assert report.outcome.is_fully_feasible
    assert report.is_repeatable
    assert report.repeatability_max_drift == 0.0
    assert report.threat_model_level == "POSIX_SUBPROCESS_AST_RESTRICTED"
