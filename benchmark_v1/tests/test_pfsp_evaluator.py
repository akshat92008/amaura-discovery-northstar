"""
Unit tests for PFSP Evaluator Correctness, Constraint Validation, and Manual Makespan Verification.
"""

import math
import pytest
from benchmark_v1.src.domains.pfsp import PFSPSimulator


def test_manual_makespan_calculation():
    # 3 jobs, 2 machines
    times = [
        [3, 2], # Job 0
        [2, 4], # Job 1
        [5, 1], # Job 2
    ]

    # Permutation [1, 0, 2]
    # Job 1: M0=2, M1=6
    # Job 0: M0=5, M1=8
    # Job 2: M0=10, M1=11
    assert PFSPSimulator.calc_makespan(times, [1, 0, 2]) == 11

    # Permutation [0, 1, 2]
    # Job 0: M0=3, M1=5
    # Job 1: M0=5, M1=9
    # Job 2: M0=10, M1=11
    assert PFSPSimulator.calc_makespan(times, [0, 1, 2]) == 11

    # Permutation [2, 0, 1]
    # Job 2: M0=5, M1=6
    # Job 0: M0=8, M1=10
    # Job 1: M0=10, M1=14
    assert PFSPSimulator.calc_makespan(times, [2, 0, 1]) == 14


def test_empty_and_single_job():
    times_single = [[7, 4, 9]]
    assert PFSPSimulator.calc_makespan(times_single, [0]) == 20
    assert PFSPSimulator.calc_makespan([], []) == 0


def test_permutation_validation():
    from benchmark_v1.src.domains.pfsp_full_algorithm import validate_permutation

    # Valid
    assert validate_permutation([0, 1, 2], 3)[0] is True
    assert validate_permutation([2, 0, 1], 3)[0] is True

    # Invalid: wrong length
    assert validate_permutation([0, 1], 3)[0] is False

    # Invalid: duplicate job
    assert validate_permutation([0, 1, 1], 3)[0] is False

    # Invalid: missing job / out of range
    assert validate_permutation([0, 1, 3], 3)[0] is False
    assert validate_permutation([-1, 0, 1], 3)[0] is False

    # Invalid: wrong type
    assert validate_permutation("not a list", 3)[0] is False
    assert validate_permutation([0, 1, "2"], 3)[0] is False
    assert validate_permutation([0, 1, 2.0], 3)[0] is False
    assert validate_permutation([True, 1, 2], 3)[0] is False
