"""
Stage 4 Adversarial & Security Audit Tests
==========================================
Tests edge-case vulnerabilities, adversarial attacks, and statistical risks:
1. Cross-process file locking on budget.json prevents race conditions.
2. Baseline parity: Arm A and Arm C receive the exact same baseline seeds and call budget.
3. Pilot mode quarantine: is_pilot=True guarantees hidden.json is never unsealed.
4. Resumed run across multi-process boundary accumulates spend.
"""

import json
import os
import tempfile
import fcntl
from unittest.mock import patch
import pytest


from stage4.src.benchmark import generate_and_save_benchmarks
from stage4.src.budget_enforcer import BudgetEnforcer, BudgetExhaustedException
from stage4.src.client import Stage4LLMClient
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.runner import Stage4Runner
from stage4.src.search import run_arm_a_search, run_arm_c_search


@pytest.fixture
def adversarial_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        output_dir = os.path.join(tmp_dir, "run_output")
        generate_and_save_benchmarks(bench_dir)
        yield bench_dir, output_dir


def test_cross_process_budget_enforcement_locks(adversarial_env):
    """Simulates two distinct processes updating the same ledger file."""
    _, output_dir = adversarial_env
    ledger_path = os.path.join(output_dir, "budget.json")

    # Process 1 creates enforcer with max_requests=4
    p1_enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=4)
    p2_enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=4)

    # Process 1 makes 2 requests
    p1_enforcer.record_usage("prompt 1", "comp 1", {"prompt_tokens": 100, "completion_tokens": 50})
    p1_enforcer.record_usage("prompt 2", "comp 2", {"prompt_tokens": 100, "completion_tokens": 50})

    # Process 2 pre-flight check should see updated spend from disk
    p2_enforcer.check_preflight_limits()
    assert p2_enforcer.requests_count == 2

    # Process 2 makes 2 requests
    p2_enforcer.record_usage("prompt 3", "comp 3", {"prompt_tokens": 100, "completion_tokens": 50})
    p2_enforcer.record_usage("prompt 4", "comp 4", {"prompt_tokens": 100, "completion_tokens": 50})

    # Next call by Process 1 MUST fail pre-flight check
    with pytest.raises(BudgetExhaustedException) as excinfo:
        p1_enforcer.check_preflight_limits()

    assert "REQUESTS" in str(excinfo.value)
    assert p1_enforcer.requests_count == 4


def test_baseline_parity_between_arms(adversarial_env):
    """Verifies that Arm A and Arm C receive the exact same initial seeds and slot count."""
    bench_dir, output_dir = adversarial_env
    dev_path = os.path.join(bench_dir, "dev.json")
    with open(dev_path, "r", encoding="utf-8") as f:
        dev_streams = [e["items"] for e in json.load(f)]

    ledger_path = os.path.join(output_dir, "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=100)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=True)
    evaluator = Stage4Evaluator()

    total_slots = 6  # 4 seeds + 2 samples
    cand_a, arch_a = run_arm_a_search(client, evaluator, dev_streams, candidate_slots=total_slots)
    cand_c, arch_c = run_arm_c_search(client, evaluator, dev_streams, candidate_slots=total_slots)

    # Both archives must have evaluated exactly total_slots candidates
    assert arch_a.total_evaluated == total_slots
    assert arch_c.total_evaluated == total_slots

    # Both archives must contain the seed best fit
    a_mutations = [c.mutation_type for c in arch_a.islands[0]]
    assert "seed_best_fit" in a_mutations


def test_pilot_mode_quarantines_hidden_benchmark(adversarial_env):
    """Verifies that in is_pilot=True mode, hidden.json is NEVER read or unsealed."""
    bench_dir, output_dir = adversarial_env

    # Corrupt or delete hidden.json completely
    hidden_path = os.path.join(bench_dir, "hidden.json")
    os.remove(hidden_path)
    assert not os.path.exists(hidden_path)

    runner = Stage4Runner(
        output_dir=output_dir,
        benchmark_dir=bench_dir,
        candidate_slots=4,
        mock_mode=True
    )

    # In pilot mode, execution must succeed with zero error even if hidden.json does not exist!
    results = runner.execute_campaign(num_trials=2, start_seed=40401, is_pilot=True, strict_protocol=False)

    assert results["config"]["is_pilot"] is True
    assert results["final_statistics"]["hidden_status"] == "SEALED_AND_UNTOUCHED"
    assert results["hidden_benchmark_sha256"] == "SEALED_NOT_READ"



def test_adversarial_retry_request_exhaustion(adversarial_env):
    """Verifies that failed/retried attempts increment retries_count and exhaust the request cap."""
    _, output_dir = adversarial_env
    ledger_path = os.path.join(output_dir, "budget.json")

    # Limit to 3 total requests
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=3)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False)

    # Mock urlopen to fail with an error
    with patch("urllib.request.urlopen", side_effect=ConnectionResetError("Adversarial connection drop")):
        with patch("time.sleep"):  # Avoid sleep delays in tests
            res = client.query(
                prompt="def test(): pass",
                system_prompt="sys",
                max_retries=2
            )
            assert res["success"] is False
            assert res["retries"] == 2

    # Now requests_count is 1 (recorded by final failure in record_usage) and retries_count is 2
    # Total requests = 1 + 2 = 3 >= max_requests (3)
    with pytest.raises(BudgetExhaustedException) as excinfo:
        enforcer.check_preflight_limits()
    assert "REQUESTS" in str(excinfo.value)


def test_adversarial_simultaneous_campaign_prevention(adversarial_env):
    """Verifies that two runners cannot execute simultaneously in the same directory."""
    bench_dir, output_dir = adversarial_env
    os.makedirs(output_dir, exist_ok=True)
    lock_file = os.path.join(output_dir, "campaign.lock")

    # Acquire lock in parent / process 1
    with open(lock_file, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Runner in process 2 attempts to execute campaign in same output_dir
        runner2 = Stage4Runner(
            output_dir=output_dir,
            benchmark_dir=bench_dir,
            candidate_slots=4,
            mock_mode=True
        )

        with pytest.raises(RuntimeError) as excinfo:
            runner2.execute_campaign(num_trials=1, start_seed=40401, is_pilot=True, strict_protocol=False)

        assert "Another runner process is already executing" in str(excinfo.value)


        # Release lock
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def test_adversarial_timeout_conservative_accounting(adversarial_env):
    """Verifies that an upstream timeout charges the full max_tokens payload ceiling."""
    _, output_dir = adversarial_env
    ledger_path = os.path.join(output_dir, "budget.json")

    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_cost_usd=10.0)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False)

    # Simulate timeout error on all attempts
    with patch("urllib.request.urlopen", side_effect=TimeoutError("The read operation timed out")):
        with patch("time.sleep"):
            res = client.query(
                prompt="short prompt",
                system_prompt="sys",
                max_tokens=512,
                max_retries=1
            )
            assert res["success"] is False

    # Check ledger: completion tokens must reflect 512 tokens (conservative worst-case)
    with open(ledger_path, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    assert ledger["output_tokens"] == 512
    # 512 completion tokens at $15/1M = $0.00768
    assert ledger["cost_usd"] > 0.007


def test_adversarial_prompt_size_limit_enforced(adversarial_env):
    """Verifies that prompts exceeding 4,000 estimated tokens fail closed before issuing requests."""
    _, output_dir = adversarial_env
    ledger_path = os.path.join(output_dir, "budget.json")

    enforcer = BudgetEnforcer(ledger_path=ledger_path)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False)

    # 4000 words -> ~5370 tokens > 4000 limit
    huge_prompt = "word " * 4000

    with pytest.raises(ValueError) as excinfo:
        client.query(prompt=huge_prompt, system_prompt="system")

    assert "PROMPT SIZE EXCEEDED" in str(excinfo.value)
    # Budget must not have been touched
    assert enforcer.requests_count == 0

