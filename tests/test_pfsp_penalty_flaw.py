"""
Tests for PFSP Evaluator Instance-Normalized Penalty.
Verifies that:
1. Crashing and invalid candidates receive an instance-normalized penalty.
2. The penalty is strictly greater (worse) than any valid schedule under makespan minimization.
3. The numerical inversion flaw (where a crash scored better than a valid schedule) is fully resolved.
"""

import pytest
from stage2.src.evaluator_pfsp import PFSPEvaluator


def test_pfsp_instance_normalized_penalty():
    """
    Verifies that an invalid/crashing candidate receives an instance-normalized makespan
    that is strictly worse than any valid candidate across both small and large datasets.
    """
    evaluator = PFSPEvaluator()

    # Multi-instance dataset: 200 instances with 50 jobs x 10 machines (processing time 100 each)
    # Valid makespan is ~5,900 per instance (~1,180,000 total)
    synthetic_dataset = [
        {"times": [[100] * 10 for _ in range(50)]}
        for _ in range(200)
    ]

    # Valid candidate schedule
    valid_code = "def schedule_flowshop(times: list[list[int]]) -> list[int]: return list(range(len(times)))"
    valid_res = evaluator.evaluate_code(valid_code, synthetic_dataset)
    assert valid_res["is_valid"] is True
    assert valid_res["total_makespan"] > 1_000_000

    # Crashing candidate (syntax error or runtime error)
    crashing_code = "def schedule_flowshop(times: list[list[int]]) -> list[int]: return 1 / 0"
    crash_res = evaluator.evaluate_code(crashing_code, synthetic_dataset)
    assert crash_res["is_valid"] is False

    # Under instance-normalized penalty, the crash penalty must be strictly WORSE (higher makespan)
    # than the valid schedule:
    assert crash_res["total_makespan"] > valid_res["total_makespan"], (
        f"Instance-normalized penalty check failed: crash penalty {crash_res['total_makespan']} "
        f"is not strictly worse than valid makespan {valid_res['total_makespan']}."
    )

    # Verify per-instance penalty calculation
    sample_inst = {"times": [[10, 20], [30, 40]]}
    inst_pen = evaluator.compute_instance_penalty(sample_inst)
    # Sum of times is 100; penalty is 2 * 100 = 200
    assert inst_pen == 200
    assert inst_pen > evaluator.compute_makespan([[10, 20], [30, 40]], [0, 1])


def test_pfsp_single_instance_penalty_strictly_worse():
    """Verifies that even on a single instance, invalid penalty exceeds valid makespan."""
    evaluator = PFSPEvaluator()
    single_inst_dataset = [{"times": [[10, 5], [2, 8], [7, 3]]}]

    valid_code = "def schedule_flowshop(times: list[list[int]]) -> list[int]: return [0, 1, 2]"
    valid_res = evaluator.evaluate_code(valid_code, single_inst_dataset)
    assert valid_res["is_valid"] is True

    bad_code = "def schedule_flowshop(times: list[list[int]]) -> list[int]: return [999]"
    bad_res = evaluator.evaluate_code(bad_code, single_inst_dataset)
    assert bad_res["is_valid"] is False

    assert bad_res["total_makespan"] > valid_res["total_makespan"]
