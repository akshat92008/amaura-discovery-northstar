"""
Stage 4 End-to-End Runner & Budget Integration Tests
====================================================
Validates the complete execution loop using mock mode (zero external calls):
1. End-to-end dry run of Stage4Runner (Arm A vs Arm C, T=2 trials).
2. Hard budget enforcement in real runner path: halts when request or cost cap reached.
3. Fail-closed startup: rejects corrupted or missing benchmark manifests.
4. Checkpoint integrity and state recovery.
5. Machine-readable results and report emission.
"""

import json
import os
import tempfile
import pytest

from stage4.src.benchmark import generate_and_save_benchmarks
from stage4.src.budget_enforcer import BudgetExhaustedException
from stage4.src.runner import Stage4Runner


@pytest.fixture
def test_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        output_dir = os.path.join(tmp_dir, "run_output")
        generate_and_save_benchmarks(bench_dir)
        yield bench_dir, output_dir


def test_runner_end_to_end_mock_campaign(test_env):
    bench_dir, output_dir = test_env
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        max_cost_usd=15.0,
        tripwire_cost_usd=12.0,
        max_requests=100,
        candidate_slots=5,  # 4 seeds + 1 LLM sample per arm
        mock_mode=True
    )

    # Safe default: is_pilot=True, 3 trials, seed 40401
    results = runner.execute_campaign(num_trials=3, start_seed=40401)

    assert "trials" in results
    assert len(results["trials"]) == 3
    assert "final_statistics" in results
    assert "budget_ledger" in results
    assert results["config"]["is_pilot"] is True
    assert results["final_statistics"]["hidden_status"] == "SEALED_AND_UNTOUCHED"

    # Verify budget ledger accumulated spend
    ledger = results["budget_ledger"]
    assert ledger["requests_count"] > 0
    assert ledger["cost_usd"] > 0.0
    assert ledger["cost_usd"] <= 15.0

    # Verify results file written to disk
    assert os.path.exists(os.path.join(output_dir, "results.json"))
    assert os.path.exists(os.path.join(output_dir, "budget.json"))


def test_runner_budget_exhaustion_in_real_path(test_env):
    bench_dir, output_dir = test_env
    # Authorize only 1 request - Arm C will halt on its 1st query
    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        max_cost_usd=15.0,
        max_requests=1,
        candidate_slots=5,
        mock_mode=True
    )

    with pytest.raises(BudgetExhaustedException) as excinfo:
        runner.execute_campaign(num_trials=1, start_seed=40401, strict_protocol=False)

    assert "HARD BUDGET CEILING REACHED" in str(excinfo.value)

    # Check that ledger recorded the halt
    with open(os.path.join(output_dir, "budget.json"), "r") as f:
        data = json.load(f)
    assert data["requests_count"] == 1
    assert "REQUESTS_LIMIT_EXCEEDED" in (data.get("stop_reason") or "")


def test_runner_fail_closed_on_corrupted_benchmark(test_env):
    bench_dir, output_dir = test_env

    # Corrupt dev.json
    dev_path = os.path.join(bench_dir, "dev.json")
    with open(dev_path, "a") as f:
        f.write(" ")  # Tamper with file to invalidate SHA-256

    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=2,
        mock_mode=True
    )

    with pytest.raises(ValueError) as excinfo:
        runner.execute_campaign(num_trials=1, start_seed=40401, strict_protocol=False)

    assert "CORRUPTED DEV BENCHMARK" in str(excinfo.value)


def test_runner_fail_closed_on_missing_manifest(test_env):
    bench_dir, output_dir = test_env
    os.remove(os.path.join(bench_dir, "manifest.json"))

    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=2,
        mock_mode=True
    )

    with pytest.raises(FileNotFoundError):
        runner.execute_campaign(num_trials=1, start_seed=40401, strict_protocol=False)


def test_runner_checkpoint_resumption_skips_completed_trials(test_env):
    bench_dir, output_dir = test_env

    # 1. First run executes 1 trial
    runner1 = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )
    res1 = runner1.execute_campaign(num_trials=1, start_seed=40401, is_pilot=True, strict_protocol=False)
    assert len(res1["trials"]) == 1
    t1_original = res1["trials"][0]

    # Verify checkpoint exists
    chk_file = os.path.join(output_dir, "checkpoint.json")
    assert os.path.exists(chk_file)
    with open(chk_file, "r") as f:
        chk_data = json.load(f)
    assert len(chk_data["completed_trials"]) == 1

    r1_requests = runner1.enforcer.requests_count

    # 2. Second runner instance resumes with num_trials=2 on the same output directory
    runner2 = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=5,
        mock_mode=True
    )
    res2 = runner2.execute_campaign(num_trials=2, start_seed=40401, is_pilot=True, strict_protocol=False)
    assert len(res2["trials"]) == 2

    # Trial 1 in res2 must be identical to t1_original
    assert res2["trials"][0]["trial_id"] == 1
    assert res2["trials"][0]["seed"] == 40401
    assert res2["trials"][0]["arm_a"]["candidate_id"] == t1_original["arm_a"]["candidate_id"]
    assert res2["trials"][0]["arm_c"]["candidate_id"] == t1_original["arm_c"]["candidate_id"]

    # Trial 2 is newly executed
    assert res2["trials"][1]["trial_id"] == 2
    assert res2["trials"][1]["seed"] == 40402

    # Verify that only trial 2 consumed new requests (no double counting for trial 1)
    # Each trial with candidate_slots=5 makes (5-4) * 2 = 2 LLM requests
    incremental_requests = runner2.enforcer.requests_count - r1_requests
    assert incremental_requests == 2

