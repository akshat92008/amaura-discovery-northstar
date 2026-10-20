"""
Stage 4 Candidate Failure Handling & Anti-Masking Regression Tests
==================================================================
Validates that:
1. Syntax errors, exceptions, NaNs, infinities, and timeouts are marked as failures.
2. Failed candidates NEVER silently receive a Best-Fit baseline score.
3. Invalid candidates NEVER enter the evolutionary archive as successful solutions.
4. Failure rates and error categorizations are tracked accurately.
"""

import math
import pytest
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.archive import Stage4IslandArchive, Stage4Candidate


@pytest.fixture
def evaluator():
    return Stage4Evaluator(bin_capacity=100.0, timeout_sec=1.0)


def test_zero_division_candidate_fails_without_best_fit_masking(evaluator):
    code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    # Division by zero error\n"
        "    return 1.0 / (remaining_capacity - 50.0)\n"
    )
    # Stream with remaining_capacity reaching 50.0
    streams = [[50.0, 20.0]]
    res = evaluator.evaluate_candidate(code, streams)

    assert not res.is_valid
    assert res.fitness == float("inf")
    assert "division by zero" in (res.error_message or "").lower()


def test_nan_returning_candidate_fails_cleanly(evaluator):
    code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return float('nan')\n"
    )
    streams = [[20.0, 30.0]]
    res = evaluator.evaluate_candidate(code, streams)

    assert not res.is_valid
    assert res.fitness == float("inf")
    assert "non-finite priority" in (res.error_message or "")


def test_infinity_returning_candidate_fails_cleanly(evaluator):
    code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return float('inf')\n"
    )
    streams = [[20.0, 30.0]]
    res = evaluator.evaluate_candidate(code, streams)

    assert not res.is_valid
    assert res.fitness == float("inf")
    assert "non-finite priority" in (res.error_message or "")


def test_forbidden_imports_fail_ast(evaluator):
    code = (
        "import os\n"
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return 0.0\n"
    )
    res = evaluator.evaluate_candidate(code, [[10.0]])
    assert not res.is_valid
    assert "Forbidden import: os" in (res.error_message or "")


def test_invalid_signature_fails_ast(evaluator):
    code = (
        "def priority(item: float, remaining_capacity: float) -> float:\n"
        "    return 0.0\n"
    )
    res = evaluator.evaluate_candidate(code, [[10.0]])
    assert not res.is_valid
    assert "must take exactly 3 parameters" in (res.error_message or "")


def test_syntax_error_fails_ast(evaluator):
    code = "def priority(item, rem, cap): return item +++ * 2"
    res = evaluator.evaluate_candidate(code, [[10.0]])
    assert not res.is_valid
    assert "SyntaxError" in (res.error_message or "")


def test_timeout_candidate_fails(evaluator):
    code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    while True:\n"
        "        pass\n"
        "    return 0.0\n"
    )
    # Stream with 2 items so priority is evaluated on the feasible open bin
    res = evaluator.evaluate_candidate(code, [[10.0, 10.0]])
    assert not res.is_valid
    assert "TimeoutError" in (res.error_message or "")


def test_archive_rejects_failed_candidates():
    archive = Stage4IslandArchive(num_islands=1)
    failed_cand = Stage4Candidate(
        code="broken",
        is_valid=False,
        fitness=float("inf"),
        error_message="Execution Failed: ZeroDivisionError"
    )

    accepted = archive.add(failed_cand)
    assert not accepted
    assert archive.total_evaluated == 1
    assert archive.failed_count == 1
    assert archive.valid_count == 0
    assert archive.get_best() is None
    assert "Execution Failed" in archive.failure_reasons
