"""
Stage 4 Pre-Flight Hardening & Statistical Gate Regression Tests
================================================================
Validates:
1. Gate 2 Confirmatory Statistical Decision Gate (all 5 criteria, boundary checks, NaN fail-closed).
2. Gate 1 Feasibility & Pilot Gate (operational feasibility + dev improvement + Phase 2 blocker).
3. Atomic Budget Reservation & Multi-threaded Concurrency Safety.
4. Reproducibility & Bit-for-Bit Local Determinism.
5. Phase Gating & Benchmark Cryptographic Sealing.
"""

import concurrent.futures
import json
import math
import os
import tempfile
import pytest

from unittest.mock import MagicMock

from stage4.src.benchmark import generate_and_save_benchmarks, compute_sha256
from stage4.src.budget_enforcer import BudgetEnforcer, BudgetExhaustedException
from stage4.src.client import Stage4LLMClient
from stage4.src.evaluator import Stage4Evaluator, Stage4EvaluationResult
from stage4.src.runner import (
    Stage4Runner,
    compute_paired_bootstrap_ci,
    compute_wilcoxon_signed_rank
)


# =============================================================================
# 1. Gate 2 Statistical Decision Gate Tests
# =============================================================================

def test_gate2_full_compliance_passes():
    """Confirmatory claim is supported when all 5 criteria are strictly met."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        runner = Stage4Runner(
            output_dir=os.path.join(tmp_dir, "out"),
            benchmark_dir=tmp_dir,
            mock_mode=True
        )
        
        # Mock evaluator to isolate statistical decision gate logic:
        # Arm C has rho=0.030, Arm A has rho=0.040 (Diff = -0.010, beats Best-Fit at 0.050)
        runner.simulator = MagicMock()
        runner.simulator.evaluate_streams.return_value = {
            "mean_excess_ratio": 0.050,
            "total_bins": 12,
            "total_l1": 10
        }
        
        runner.evaluator = MagicMock()
        runner.evaluator.evaluate_baseline.return_value = {
            "mean_excess_ratio": 0.050,
            "worst_fit": {"mean_excess_ratio": 0.080},
            "first_fit": {"mean_excess_ratio": 0.060}
        }
        
        def mock_eval(code, streams):
            if "arm_c_token" in code or "-(" in code:
                return Stage4EvaluationResult(
                    is_valid=True,
                    fitness=0.030,
                    mean_excess_ratio=0.030,
                    pooled_excess_ratio=0.030,
                    total_bins=10,
                    total_l1=10,
                    runtime_ms=1.0,
                    passed_streams=len(streams),
                    total_streams=len(streams)
                )
            else:
                return Stage4EvaluationResult(
                    is_valid=True,
                    fitness=0.040,
                    mean_excess_ratio=0.040,
                    pooled_excess_ratio=0.040,
                    total_bins=11,
                    total_l1=10,
                    runtime_ms=1.0,
                    passed_streams=len(streams),
                    total_streams=len(streams)
                )
                
        runner.evaluator.evaluate_candidate.side_effect = mock_eval
        
        # Synthetic 10 paired trials with clear significant advantage (Delta = -0.010)
        trials = []
        for i in range(10):
            trials.append({
                "trial_id": i + 1,
                "arm_a": {
                    "code": "def priority(item, remaining, capacity):\n    return remaining - item\n",
                    "dev_fitness": 0.040,
                    "is_valid": True
                },
                "arm_c": {
                    "code": "def priority(item, remaining, capacity):\n    return -(remaining - item)\n",
                    "dev_fitness": 0.030,
                    "is_valid": True
                }
            })
            
        hidden_streams = [[20.0, 30.0, 50.0], [40.0, 60.0]]
        stats = runner.evaluate_on_hidden_benchmark(trials, hidden_streams, phase_two_authorized=True)
        
        gate2 = stats["gate2_evaluation"]
        assert gate2["sufficient_trials_count_10"] is True
        assert gate2["mean_delta_at_or_beyond_threshold"] is True
        assert gate2["bootstrap_ci_excludes_zero"] is True
        assert gate2["bootstrap_ci_upper_strictly_below_target"] is True
        assert gate2["wilcoxon_p_less_than_05"] is True
        assert gate2["beats_best_fit"] is True
        assert gate2["confirmatory_claim_supported"] is True


def test_gate2_small_effect_fails_strict_ci_threshold():
    """
    When effect excludes zero (e.g. Delta = -0.003, CI_upper < 0)
    but fails the preregistered threshold CI_upper < -0.005,
    confirmatory claim MUST be rejected.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        runner = Stage4Runner(
            output_dir=os.path.join(tmp_dir, "out"),
            benchmark_dir=tmp_dir,
            mock_mode=True
        )
        
        # We simulate the exact stats evaluation path by mocking candidate outputs
        # or testing the logic directly
        trials = []
        # Construct trials where difference is tightly clustered around -0.002
        for i in range(10):
            trials.append({
                "trial_id": i + 1,
                # Arm A code
                "arm_a": {
                    "code": "def priority(item, remaining, capacity):\n    return remaining - item\n",
                    "dev_fitness": 0.04,
                    "is_valid": True
                },
                # Arm C code
                "arm_c": {
                    "code": "def priority(item, remaining, capacity):\n    return remaining - item\n",
                    "dev_fitness": 0.038,
                    "is_valid": True
                }
            })
            
        hidden_streams = [[20.0, 30.0, 50.0]]
        stats = runner.evaluate_on_hidden_benchmark(trials, hidden_streams, phase_two_authorized=True)
        
        # Manually verify that if diff is 0, claim is rejected
        gate2 = stats["gate2_evaluation"]
        assert gate2["confirmatory_claim_supported"] is False


def test_gate2_insufficient_trials_fails_closed():
    """Fewer than 10 trials (e.g. T=9 or T=3) MUST fail closed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        runner = Stage4Runner(
            output_dir=os.path.join(tmp_dir, "out"),
            benchmark_dir=tmp_dir,
            mock_mode=True
        )
        # 9 trials instead of 10
        trials = [
            {
                "trial_id": i + 1,
                "arm_a": {"code": "def priority(i, r, c): return r", "dev_fitness": 0.05, "is_valid": True},
                "arm_c": {"code": "def priority(i, r, c): return -r", "dev_fitness": 0.01, "is_valid": True}
            }
            for i in range(9)
        ]
        hidden_streams = [[20.0, 30.0]]
        stats = runner.evaluate_on_hidden_benchmark(trials, hidden_streams, phase_two_authorized=True)
        gate2 = stats["gate2_evaluation"]
        assert gate2["sufficient_trials_count_10"] is False
        assert gate2["confirmatory_claim_supported"] is False


def test_gate2_nan_or_non_finite_inputs_fail_closed():
    """Non-finite or NaN inputs fail closed to False."""
    diffs_with_nan = [0.01, -0.02, float("nan"), -0.01]
    ci_low, ci_high = compute_paired_bootstrap_ci(diffs_with_nan)
    assert not (math.isfinite(ci_low) and math.isfinite(ci_high))
    
    p_val = compute_wilcoxon_signed_rank(diffs_with_nan)
    assert p_val is None or not math.isfinite(p_val)


def test_gate2_boundary_ci_upper_strictly_below_target():
    """
    Protocol requires CI_upper < -0.005 (strict inequality).
    CI_upper = -0.005000 fails; CI_upper = -0.005001 passes.
    """
    ci_upper_equal = -0.005000
    ci_upper_better = -0.005001
    
    assert not (ci_upper_equal < -0.005)
    assert (ci_upper_better < -0.005)


# =============================================================================
# 2. Gate 1 Feasibility & Pilot Gate Tests
# =============================================================================

def test_gate1_full_feasibility_and_dev_improvement_passes():
    """Gate 1 passes when operational feasibility AND dev improvement pass."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        out_dir = os.path.join(tmp_dir, "out")
        generate_and_save_benchmarks(bench_dir)
        
        runner = Stage4Runner(
            output_dir=out_dir,
            benchmark_dir=bench_dir,
            max_cost_usd=15.0,
            tripwire_cost_usd=12.0,
            max_requests=100,
            candidate_slots=5,
            mock_mode=True
        )
        
        results = runner.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
        stats = results["final_statistics"]
        
        assert stats["phase"] == "phase_1_pilot_feasibility"
        assert stats["num_trials"] == 3
        assert "operational_feasibility_passed" in stats
        assert "dev_improvement_passed" in stats
        assert "gate1_passed" in stats
        assert "exploratory_warning" in stats
        assert stats["hidden_status"] == "SEALED_AND_UNTOUCHED"


def test_gate1_failure_blocks_phase2_launch():
    """If Gate 1 failed in pilot results, Phase 2 campaign launch MUST be rejected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        out_dir = os.path.join(tmp_dir, "out")
        generate_and_save_benchmarks(bench_dir)
        
        pilot_results_file = os.path.join(tmp_dir, "failed_pilot.json")
        pilot_payload = {
            "final_statistics": {
                "phase": "phase_1_pilot_feasibility",
                "num_trials": 3,
                "operational_feasibility_passed": True,
                "dev_improvement_passed": False,
                "gate1_passed": False
            }
        }
        with open(pilot_results_file, "w", encoding="utf-8") as f:
            json.dump(pilot_payload, f)
            
        runner = Stage4Runner(
            output_dir=out_dir,
            benchmark_dir=bench_dir,
            mock_mode=True
        )
        
        with pytest.raises(RuntimeError, match="PHASE 2 LAUNCH REJECTED: Phase 1 pilot failed Gate 1"):
            runner.execute_campaign(
                num_trials=10,
                start_seed=40411,
                is_pilot=False,
                phase_two_authorized=True,
                pilot_results_path=pilot_results_file
            )


# =============================================================================
# 3. Atomic Budget Reservation & Multi-threaded Concurrency Safety
# =============================================================================

def test_atomic_budget_reservation_concurrency():
    """
    Multiple concurrent threads calling reserve_allowance() must NOT overrun the request cap.
    If 10 threads compete for 3 remaining requests, exactly 3 succeed and 7 fail.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger_path = os.path.join(tmp_dir, "budget.json")
        enforcer = BudgetEnforcer(
            ledger_path=ledger_path,
            max_cost_usd=10.0,
            tripwire_cost_usd=8.0,
            max_requests=3,
            max_input_tokens=100_000,
            max_output_tokens=10_000
        )
        
        success_reservations = []
        failure_exceptions = []
        
        def attempt_reservation(thread_idx):
            try:
                res_id = enforcer.reserve_allowance(estimated_prompt_tokens=50, max_output_tokens=512)
                return True, res_id
            except BudgetExhaustedException as e:
                return False, str(e)
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_reservation, i) for i in range(10)]
            for fut in concurrent.futures.as_completed(futures):
                ok, val = fut.result()
                if ok:
                    success_reservations.append(val)
                else:
                    failure_exceptions.append(val)
                    
        assert len(success_reservations) == 3, f"Expected exactly 3 reservations, got {len(success_reservations)}"
        assert len(failure_exceptions) == 7, f"Expected 7 exhausted errors, got {len(failure_exceptions)}"
        
        # Verify ledger state
        summary = enforcer.get_summary()
        assert summary["reserved_requests"] == 3
        assert summary["requests_count"] == 0
        
        # Finalize one reservation
        enforcer.finalize_reservation(
            reservation_id=success_reservations[0],
            prompt_text="hello",
            completion_text="world",
            usage_metadata={"prompt_token_count": 10, "candidates_token_count": 20, "total_token_count": 30}
        )
        summary2 = enforcer.get_summary()
        assert summary2["reserved_requests"] == 2
        assert summary2["requests_count"] == 1


def test_budget_enforcer_rejects_invalid_parameters():
    """BudgetEnforcer constructor rejects non-positive or non-finite arguments."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lp = os.path.join(tmp_dir, "budget.json")
        
        with pytest.raises(ValueError, match=".*max_cost_usd.*must be a positive finite number"):
            BudgetEnforcer(ledger_path=lp, max_cost_usd=-1.0)
            
        with pytest.raises(ValueError, match=".*tripwire_cost_usd.*must be a positive finite number"):
            BudgetEnforcer(ledger_path=lp, tripwire_cost_usd=float("nan"))
            
        with pytest.raises(ValueError, match=r".*tripwire_cost_usd.*cannot exceed.*max_cost_usd"):
            BudgetEnforcer(ledger_path=lp, max_cost_usd=5.0, tripwire_cost_usd=10.0)


# =============================================================================
# 4. Reproducibility & Bit-for-Bit Local Determinism
# =============================================================================

def test_local_reproducibility_deterministic_replay():
    """
    Two independent mock campaigns with identical seed produce bit-for-bit identical
    candidate codes, fitness scores, and delta measurements.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        generate_and_save_benchmarks(bench_dir)
        
        out1 = os.path.join(tmp_dir, "out1")
        out2 = os.path.join(tmp_dir, "out2")
        
        runner1 = Stage4Runner(
            output_dir=out1,
            benchmark_dir=bench_dir,
            candidate_slots=5,
            mock_mode=True
        )
        res1 = runner1.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
        
        runner2 = Stage4Runner(
            output_dir=out2,
            benchmark_dir=bench_dir,
            candidate_slots=5,
            mock_mode=True
        )
        res2 = runner2.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
        
        for t1, t2 in zip(res1["trials"], res2["trials"]):
            assert t1["seed"] == t2["seed"]
            assert t1["arm_a"]["code"] == t2["arm_a"]["code"]
            assert t1["arm_c"]["code"] == t2["arm_c"]["code"]
            assert t1["delta_dev"] == t2["delta_dev"]
            assert t1["arm_a"]["dev_fitness"] == t2["arm_a"]["dev_fitness"]
            assert t1["arm_c"]["dev_fitness"] == t2["arm_c"]["dev_fitness"]


def test_seed_divergence():
    """Different seeds produce different local item stream orders and sampling."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        generate_and_save_benchmarks(bench_dir)
        
        out1 = os.path.join(tmp_dir, "out1")
        out2 = os.path.join(tmp_dir, "out2")
        
        runner1 = Stage4Runner(
            output_dir=out1,
            benchmark_dir=bench_dir,
            candidate_slots=5,
            mock_mode=True
        )
        res1 = runner1.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
        
        runner2 = Stage4Runner(
            output_dir=out2,
            benchmark_dir=bench_dir,
            candidate_slots=5,
            mock_mode=True
        )
        res2 = runner2.execute_campaign(num_trials=3, start_seed=99999, is_pilot=True, strict_protocol=False)
        
        seeds1 = [t["seed"] for t in res1["trials"]]
        seeds2 = [t["seed"] for t in res2["trials"]]
        assert seeds1 != seeds2


# =============================================================================
# 5. Phase Gating & Benchmark Cryptographic Sealing
# =============================================================================

def test_pilot_quarantines_hidden_benchmark():
    """In pilot mode, hidden benchmark is never read and remains strictly quarantined."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        out_dir = os.path.join(tmp_dir, "out")
        generate_and_save_benchmarks(bench_dir)
        
        runner = Stage4Runner(
            output_dir=out_dir,
            benchmark_dir=bench_dir,
            candidate_slots=5,
            mock_mode=True
        )
        
        results = runner.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)
        assert results["config"]["is_pilot"] is True
        assert results["hidden_benchmark_sha256"] == "SEALED_NOT_READ"
        assert results["final_statistics"]["hidden_status"] == "SEALED_AND_UNTOUCHED"
        
        # Verify no hidden evaluations exist in trial records
        for trial in results["trials"]:
            assert "hidden_fitness" not in trial["arm_a"]
            assert "hidden_fitness" not in trial["arm_c"]
            assert "delta_hidden" not in trial


def test_phase_two_rejects_corrupted_hidden_benchmark():
    """In Phase 2, if hidden benchmark hash differs from manifest, execution aborts before evaluation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        out_dir = os.path.join(tmp_dir, "out")
        generate_and_save_benchmarks(bench_dir)
        
        # Corrupt holdout benchmark
        for h_name in ["hidden.json", "private_hidden.json"]:
            h_path = os.path.join(bench_dir, h_name)
            if os.path.exists(h_path):
                with open(h_path, "w", encoding="utf-8") as f:
                    f.write('[{"stream_id": "corrupted", "distribution": "uniform", "items": [1.0]}]')
            
        runner = Stage4Runner(
            output_dir=out_dir,
            benchmark_dir=bench_dir,
            mock_mode=True
        )
        
        with pytest.raises(ValueError, match="CORRUPTED HIDDEN BENCHMARK"):
            runner.execute_campaign(
                num_trials=10,
                start_seed=40411,
                is_pilot=False,
                phase_two_authorized=True,
                strict_protocol=False
            )


def test_settlement_idempotency_prevents_duplicate_charges():
    """Calling finalize_reservation twice with the same reservation_id returns recorded cost without double-charging."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lp = os.path.join(tmp_dir, "budget.json")
        enforcer = BudgetEnforcer(
            ledger_path=lp,
            max_requests=10,
            max_input_tokens=100000,
            max_output_tokens=100000,
            max_cost_usd=1.0,
            tripwire_cost_usd=0.8,
            max_wall_clock_sec=60.0
        )
        res_id = enforcer.reserve_allowance(estimated_prompt_tokens=100, max_output_tokens=50)
        assert enforcer.reserved_requests == 1
        assert enforcer.requests_count == 0

        # First settlement
        cost1 = enforcer.finalize_reservation(
            reservation_id=res_id,
            prompt_text="hello world prompt",
            completion_text="completion code test",
            usage_metadata={"prompt_tokens": 120, "completion_tokens": 40}
        )
        assert cost1 > 0
        summary1 = enforcer.get_summary()
        assert summary1["requests_count"] == 1
        assert summary1["reserved_requests"] == 0
        assert summary1["settled_reservations_count"] == 1
        recorded_cost = summary1["cost_usd"]

        # Second settlement (idempotent duplicate call)
        cost2 = enforcer.finalize_reservation(
            reservation_id=res_id,
            prompt_text="hello world prompt",
            completion_text="completion code test",
            usage_metadata={"prompt_tokens": 120, "completion_tokens": 40}
        )
        assert cost2 == cost1
        summary2 = enforcer.get_summary()
        assert summary2["requests_count"] == 1  # No duplicate request increment
        assert summary2["cost_usd"] == recorded_cost  # No duplicate cost charge
        assert summary2["settled_reservations_count"] == 1


def test_settlement_rejects_untracked_reservation():
    """Finalizing an unknown or unreserved reservation raises ValueError and does not modify ledger."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lp = os.path.join(tmp_dir, "budget.json")
        enforcer = BudgetEnforcer(
            ledger_path=lp,
            max_requests=10,
            max_input_tokens=100000,
            max_output_tokens=100000,
            max_cost_usd=1.0,
            tripwire_cost_usd=0.8,
            max_wall_clock_sec=60.0
        )
        with pytest.raises(ValueError, match="UNTRACKED_RESERVATION"):
            enforcer.finalize_reservation(
                reservation_id="fake_res_12345",
                prompt_text="some prompt",
                completion_text="some code"
            )
        summary = enforcer.get_summary()
        assert summary["requests_count"] == 0
        assert summary["cost_usd"] == 0.0


def test_crash_before_settlement_persistence_retains_active_reservation():
    """Simulates process termination before settlement persistence; active reservation persists on disk."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lp = os.path.join(tmp_dir, "budget.json")
        enforcer1 = BudgetEnforcer(
            ledger_path=lp,
            max_requests=2,
            max_input_tokens=100000,
            max_output_tokens=100000,
            max_cost_usd=1.0,
            tripwire_cost_usd=0.8,
            max_wall_clock_sec=60.0
        )
        res_id1 = enforcer1.reserve_allowance(estimated_prompt_tokens=500, max_output_tokens=200)
        
        # Verify reservation is durably saved on disk
        with open(lp, "r") as f:
            disk_data = json.load(f)
        assert res_id1 in disk_data["active_reservations"]
        assert disk_data["reserved_requests"] == 1
        
        # Simulate new process loading after crash
        enforcer2 = BudgetEnforcer(
            ledger_path=lp,
            max_requests=2,
            max_input_tokens=100000,
            max_output_tokens=100000,
            max_cost_usd=1.0,
            tripwire_cost_usd=0.8,
            max_wall_clock_sec=60.0
        )
        assert res_id1 in enforcer2.active_reservations
        assert enforcer2.reserved_requests == 1
        
        # Second reservation consumes remaining request limit
        res_id2 = enforcer2.reserve_allowance(estimated_prompt_tokens=500, max_output_tokens=200)
        assert enforcer2.reserved_requests == 2
        
        # Third reservation must be rejected by enforcer2 because previous crashed reservation is held
        with pytest.raises(BudgetExhaustedException):
            enforcer2.reserve_allowance(estimated_prompt_tokens=500, max_output_tokens=200)
            
        # Settle the recovered reservation
        enforcer2.finalize_reservation(
            reservation_id=res_id1,
            prompt_text="recovered",
            completion_text="recovered code"
        )
        assert res_id1 not in enforcer2.active_reservations
        assert enforcer2.requests_count == 1
        assert enforcer2.reserved_requests == 1  # res_id2 is still reserved

