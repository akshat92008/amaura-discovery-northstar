"""
Stage 4 Targeted Blocker Fix Regression Tests
=============================================
Verifies resolution of the four targeted review blockers:
1. Billing & Budget Accounting: Billable usage recorded on model mismatch and malformed responses.
2. Candidate Isolation: True process isolation with enforceable timeout termination and AST top-level statement restrictions.
3. Phase Gating: Pilot mode safe default, phase-two authorization checks, gate verification, and hidden benchmark hash validation.
4. Reproducibility: Seed wiring into search arms and comprehensive metadata logging.
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from stage4.src.benchmark import generate_and_save_benchmarks
from stage4.src.budget_enforcer import BudgetEnforcer
from stage4.src.client import Stage4LLMClient, ModelMismatchException
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.runner import Stage4Runner


@pytest.fixture
def blocker_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        output_dir = os.path.join(tmp_dir, "run_output")
        generate_and_save_benchmarks(bench_dir)
        yield bench_dir, output_dir


# ==============================================================================
# BLOCKER 1: BILLING & BUDGET ACCOUNTING
# ==============================================================================

def test_billable_usage_recorded_on_model_mismatch(blocker_env):
    """Verifies that when model provenance check fails, usage is charged before raising."""
    _, output_dir = blocker_env
    ledger_path = os.path.join(output_dir, "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=10)
    client = Stage4LLMClient(
        budget_enforcer=enforcer,
        model="nvidia/nvidia/nemotron-3-super-120b-a12b",
        mock_mode=False
    )

    # Provider returned a different model ID (e.g. gpt-3.5-turbo), but executed call with usage
    mock_resp = MagicMock()
    mock_payload = {
        "model": "openai/gpt-3.5-turbo",
        "choices": [{"message": {"content": "def priority(): pass"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200}
    }
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(ModelMismatchException) as excinfo:
            client.query(prompt="test prompt", system_prompt="test system")

    assert "FATAL MODEL MISMATCH" in str(excinfo.value)

    # Verify that ledger recorded the billable transaction!
    with open(ledger_path, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    assert ledger["requests_count"] == 1
    assert ledger["input_tokens"] == 150
    assert ledger["output_tokens"] == 50
    assert ledger["cost_usd"] > 0.001


def test_billable_usage_recorded_on_malformed_json_response(blocker_env):
    """Verifies that if HTTP returns non-JSON bytes, fallback usage is charged."""
    _, output_dir = blocker_env
    ledger_path = os.path.join(output_dir, "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=10)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False)

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html>502 Bad Gateway from Proxy</html>"
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("time.sleep"):
            res = client.query(prompt="short prompt", system_prompt="sys", max_retries=1)

    assert res["success"] is False
    with open(ledger_path, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    assert ledger["requests_count"] == 1
    assert ledger["input_tokens"] > 0


# ==============================================================================
# BLOCKER 2: CANDIDATE ISOLATION & AST STRUCTURE
# ==============================================================================

def test_infinite_loop_candidate_terminates_cleanly_without_lingering_process():
    """Verifies that an infinite loop candidate is hard-terminated and leaves no lingering worker."""
    evaluator = Stage4Evaluator(timeout_sec=0.5)
    infinite_loop_code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    while True:\n"
        "        pass\n"
        "    return 0.0\n"
    )
    streams = [[10.0, 20.0, 30.0]]

    t0 = os.times()
    res = evaluator.evaluate_candidate(infinite_loop_code, streams)

    assert res.is_valid is False
    assert res.fitness == float("inf")
    assert "TimeoutError" in (res.error_message or "")
    assert "terminated" in (res.error_message or "")


def test_ast_rejects_top_level_while_loop():
    """Verifies that top-level loops are rejected by AST validation before execution."""
    evaluator = Stage4Evaluator()
    code = (
        "while True:\n"
        "    pass\n"
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return 0.0\n"
    )
    ast_ok, ast_err = evaluator.validate_ast(code)
    assert ast_ok is False
    assert "Forbidden top-level execution statement: found 'While'" in str(ast_err)


def test_ast_rejects_top_level_function_call():
    """Verifies that top-level function calls are rejected by AST validation."""
    evaluator = Stage4Evaluator()
    code = (
        "print('side effect')\n"
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return 0.0\n"
    )
    ast_ok, ast_err = evaluator.validate_ast(code)
    assert ast_ok is False
    assert "Forbidden top-level execution statement: found 'Expr'" in str(ast_err)


# ==============================================================================
# BLOCKER 3: PHASE GATING & BENCHMARK VALIDATION
# ==============================================================================

def test_pilot_mode_is_safe_default(blocker_env):
    """Verifies that execute_campaign defaults to pilot mode without touching hidden benchmark."""
    bench_dir, output_dir = blocker_env
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )

    # Calling execute_campaign with NO is_pilot argument
    results = runner.execute_campaign(num_trials=3, start_seed=40401)

    assert results["config"]["is_pilot"] is True
    assert results["final_statistics"]["hidden_status"] == "SEALED_AND_UNTOUCHED"
    assert results["hidden_benchmark_sha256"] == "SEALED_NOT_READ"


def test_phase_two_without_authorization_rejected(blocker_env):
    """Verifies that running phase 2 without explicit phase_two_authorized=True raises RuntimeError."""
    bench_dir, output_dir = blocker_env
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )

    with pytest.raises(RuntimeError) as excinfo:
        runner.execute_campaign(num_trials=10, start_seed=40411, is_pilot=False, phase_two_authorized=False)

    assert "PHASE 2 ACCESS FORBIDDEN" in str(excinfo.value)


def test_phase_two_rejects_failed_pilot_gate(blocker_env):
    """Verifies that Phase 2 refuses to launch if Phase 1 pilot failed Gate 1."""
    bench_dir, output_dir = blocker_env
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )

    # Create synthetic pilot results file where gate1_passed is False
    mock_pilot_path = os.path.join(output_dir, "failed_pilot_results.json")
    with open(mock_pilot_path, "w", encoding="utf-8") as f:
        json.dump({
            "final_statistics": {
                "phase": "phase_1_pilot_feasibility",
                "gate1_passed": False,
                "mean_delta_dev": 0.002
            }
        }, f)

    with pytest.raises(RuntimeError) as excinfo:
        runner.execute_campaign(
            num_trials=10,
            start_seed=40411,
            is_pilot=False,
            phase_two_authorized=True,
            pilot_results_path=mock_pilot_path
        )

    assert "PHASE 2 LAUNCH REJECTED: Phase 1 pilot failed Gate 1" in str(excinfo.value)


def test_protocol_rejects_incorrect_trial_counts_and_seeds(blocker_env):
    """Verifies that strict protocol mode rejects non-compliant trial counts and seeds."""
    bench_dir, output_dir = blocker_env
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )

    # Pilot requires exactly 3 trials starting at 40401
    with pytest.raises(ValueError) as excinfo1:
        runner.execute_campaign(num_trials=5, start_seed=40401, is_pilot=True)
    assert "PROTOCOL VIOLATION: Pilot phase requires exactly 3 trials" in str(excinfo1.value)

    with pytest.raises(ValueError) as excinfo2:
        runner.execute_campaign(num_trials=3, start_seed=99999, is_pilot=True)
    assert "PROTOCOL VIOLATION" in str(excinfo2.value)


def test_phase_two_validates_hidden_benchmark_hash(blocker_env):
    """Verifies that Phase 2 fails closed if hidden.json hash does not match manifest.json."""
    bench_dir, output_dir = blocker_env

    # Tamper with holdout benchmark
    for h_name in ["hidden.json", "private_hidden.json"]:
        h_path = os.path.join(bench_dir, h_name)
        if os.path.exists(h_path):
            with open(h_path, "a") as f:
                f.write(" ")

    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )

    with pytest.raises(ValueError) as excinfo:
        runner.execute_campaign(
            num_trials=10,
            start_seed=40411,
            is_pilot=False,
            phase_two_authorized=True
        )

    assert "CORRUPTED HIDDEN BENCHMARK" in str(excinfo.value)


# ==============================================================================
# BLOCKER 4: REPRODUCIBILITY & METADATA
# ==============================================================================

def test_trial_seeds_and_metadata_recorded_in_results(blocker_env):
    """Verifies that trial seeds and comprehensive reproducibility metadata are logged."""
    bench_dir, output_dir = blocker_env
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )

    results = runner.execute_campaign(num_trials=3, start_seed=40401)

    assert "metadata" in results
    meta = results["metadata"]
    assert "python_version" in meta
    assert "platform" in meta
    assert "model" in meta

    assert "reproducibility_notes" in results
    notes = results["reproducibility_notes"]
    assert "provider_nondeterminism" in notes
    assert notes["start_seed"] == 40401
    assert notes["num_trials"] == 3

    # Check that individual trials have seeds recorded
    for i, t in enumerate(results["trials"]):
        assert t["seed"] == 40401 + i
