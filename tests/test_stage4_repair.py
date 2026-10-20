"""
Offline Regression Tests for Stage 4 Repair:
1. Truncation detection when finish_reason == 'length'
2. No-final-answer detection when content is empty and only reasoning_content exists
3. Separation of seed vs AI candidates in Stage4IslandArchive
4. Early validity stopping rule (< 60% validity after first 15 AI candidates)
5. Comprehensive candidate logging (error_text, finish_reason, completion_tokens, is_truncation)
"""

import os
import hashlib
import json
import math
import pytest
from unittest.mock import MagicMock, patch
import scipy.stats

from stage4.src.archive import Stage4Candidate, Stage4IslandArchive
from stage4.src.client import Stage4LLMClient
from stage4.src.budget_enforcer import BudgetEnforcer, CorruptedLedgerException
from stage4.src.search import (
    LowValidityEarlyStopException,
    run_arm_a_search,
    run_arm_c_search,
    get_canonical_seeds
)
from stage4.src.evaluator import Stage4Evaluator, Stage4EvaluationResult
from stage4.src.runner import (
    Stage4Runner,
    compute_sha256,
    compute_wilcoxon_test,
    compute_wilcoxon_signed_rank,
    validate_trial_record,
    compute_experiment_fingerprint
)


def test_client_truncation_detection(tmp_path):
    """Verify finish_reason='length' is flagged as truncation."""
    ledger_path = str(tmp_path / "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_cost_usd=15.0)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False, api_key="mock-key")

    mock_resp_body = {
        "id": "test-req-1",
        "choices": [{
            "message": {"content": "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n    # Incomplete function..."},
            "finish_reason": "length"
        }],
        "model": "nvidia/nvidia/nemotron-3-super-120b-a12b",
        "usage": {"prompt_tokens": 100, "completion_tokens": 4096, "total_tokens": 4196}
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_resp_body).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        res = client.query("test prompt", "test system prompt")
        assert res["finish_reason"] == "length"
        assert res["is_truncation"] is True
        assert res["completion_tokens"] == 4096


def test_client_no_final_answer_from_reasoning(tmp_path):
    """Verify that if content is empty and only reasoning_content exists, 'no_final_answer' is recorded."""
    ledger_path = str(tmp_path / "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_cost_usd=15.0)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False, api_key="mock-key")

    mock_resp_body = {
        "id": "test-req-2",
        "choices": [{
            "message": {
                "content": "",
                "reasoning_content": "def priority(item, remaining, cap): return 1.0  # I am thinking about this solution"
            },
            "finish_reason": "stop"
        }],
        "model": "nvidia/nvidia/nemotron-3-super-120b-a12b",
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_resp_body).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        res = client.query("test prompt", "test system prompt")
        assert res["success"] is False
        assert res["error"] == "no_final_answer"
        assert res["code"] == ""  # Did NOT extract code from reasoning
        assert res["reasoning_content"] != ""


def test_archive_seed_vs_ai_separation():
    """Verify that canonical seeds and AI candidates are accounted separately."""
    archive = Stage4IslandArchive()

    # 4 Canonical seeds
    for i in range(4):
        seed_cand = Stage4Candidate(
            code=f"def priority_{i}(): pass",
            is_valid=True,
            fitness=0.1 * i,
            is_seed=True,
            mutation_type="canonical_seed"
        )
        archive.add(seed_cand)

    stats = archive.get_stats()
    assert stats["seed_total"] == 4
    assert stats["seed_valid"] == 4
    assert stats["ai_total"] == 0
    assert stats["ai_valid"] == 0

    # Add 10 AI candidates: 7 valid, 3 invalid
    for i in range(7):
        ai_valid_cand = Stage4Candidate(
            code=f"def ai_valid_{i}(): pass",
            is_valid=True,
            fitness=0.05 * i,
            is_seed=False,
            mutation_type="ai_generated"
        )
        archive.add(ai_valid_cand)

    for i in range(3):
        ai_invalid_cand = Stage4Candidate(
            code=f"def ai_invalid_{i}(): pass",
            is_valid=False,
            fitness=float("inf"),
            error_message="SyntaxError: invalid syntax",
            is_seed=False,
            mutation_type="ai_generated"
        )
        archive.add(ai_invalid_cand)

    stats = archive.get_stats()
    assert stats["seed_total"] == 4
    assert stats["seed_valid"] == 4
    assert stats["ai_total"] == 10
    assert stats["ai_valid"] == 7
    assert stats["ai_validity_pct"] == 70.0
    assert len(stats["candidate_logs"]) == 14


def test_early_validity_stop_triggered():
    """Verify that if AI-only validity < 60% after 15 candidates, LowValidityEarlyStopException is raised."""
    mock_client = MagicMock()
    mock_evaluator = MagicMock()

    # Return valid for first 5, invalid for next 10 -> 5/15 = 33.3% (< 60%)
    call_count = 0

    def mock_query(**kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "success": True,
            "code": f"def priority(item, rem, cap): return {call_count}",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost": 0.001,
            "finish_reason": "stop",
            "is_truncation": False,
            "error": None
        }

    mock_client.query.side_effect = mock_query

    eval_count = 0

    def mock_eval(code, streams, func_name="priority"):
        nonlocal eval_count
        eval_count += 1
        # 4 seeds are evaluated first (eval_count 1..4), then AI candidates start at 5
        # eval_count <= 9 means 5 valid AI candidates (eval_count 5..9), and 10 invalid AI candidates (10..19)
        # Total AI valid: 5/15 = 33.3%
        if eval_count <= 9:
            return Stage4EvaluationResult(is_valid=True, fitness=0.01, mean_excess_ratio=0.01, pooled_excess_ratio=0.01, total_bins=1, total_l1=1, runtime_ms=1.0, passed_streams=1, total_streams=1, error_message=None)
        else:
            return Stage4EvaluationResult(is_valid=False, fitness=float("inf"), mean_excess_ratio=float("inf"), pooled_excess_ratio=float("inf"), total_bins=0, total_l1=0, runtime_ms=1.0, passed_streams=0, total_streams=1, error_message="ZeroDivisionError: division by zero")

    mock_evaluator.evaluate_candidate.side_effect = mock_eval

    with pytest.raises(LowValidityEarlyStopException) as excinfo:
        run_arm_a_search(
            client=mock_client,
            evaluator=mock_evaluator,
            dev_streams=[{"items": [0.5], "bin_capacity": 1.0}],
            candidate_slots=25,
            seed=40401
        )

    assert "< 60% after first 15 AI candidates" in str(excinfo.value)
    assert "33.3%" in str(excinfo.value)


def test_early_validity_stop_not_triggered_when_healthy():
    """Verify that if AI-only validity >= 60% after 15 candidates, the search proceeds without exception."""
    mock_client = MagicMock()
    mock_evaluator = MagicMock()

    call_count = 0

    def mock_query(**kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "success": True,
            "code": f"def priority(item, rem, cap): return {call_count}",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost": 0.001,
            "finish_reason": "stop",
            "is_truncation": False,
            "error": None
        }

    mock_client.query.side_effect = mock_query

    eval_count = 0

    def mock_eval(code, streams, func_name="priority"):
        nonlocal eval_count
        eval_count += 1
        # 12 valid out of first 15 = 80% (>= 60%)
        if eval_count <= 12 or eval_count > 15:
            return Stage4EvaluationResult(is_valid=True, fitness=0.01, mean_excess_ratio=0.01, pooled_excess_ratio=0.01, total_bins=1, total_l1=1, runtime_ms=1.0, passed_streams=1, total_streams=1, error_message=None)
        else:
            return Stage4EvaluationResult(is_valid=False, fitness=float("inf"), mean_excess_ratio=float("inf"), pooled_excess_ratio=float("inf"), total_bins=0, total_l1=0, runtime_ms=1.0, passed_streams=0, total_streams=1, error_message="RuntimeError")

    mock_evaluator.evaluate_candidate.side_effect = mock_eval

    # Total budget of 16 candidates (4 seeds + 16 AI candidates = 20 total)
    best_cand, archive = run_arm_a_search(
        client=mock_client,
        evaluator=mock_evaluator,
        dev_streams=[{"items": [0.5], "bin_capacity": 1.0}],
        candidate_slots=20,
        seed=40401
    )

    stats = archive.get_stats()
    assert stats["ai_total"] == 16
    assert stats["ai_valid"] >= 12
    assert stats["ai_validity_pct"] >= 60.0


def test_early_validity_stop_arm_c_triggered():
    """Verify that Arm C also triggers early validity stop when AI validity < 60% after 15 candidates."""
    mock_client = MagicMock()
    mock_evaluator = MagicMock()

    call_count = 0

    def mock_query(**kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "success": True,
            "code": f"def priority(item, rem, cap): return {call_count}",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost": 0.001,
            "finish_reason": "stop",
            "is_truncation": False,
            "error": None
        }

    mock_client.query.side_effect = mock_query

    eval_count = 0

    def mock_eval(code, streams, func_name="priority"):
        nonlocal eval_count
        eval_count += 1
        # Seeds 1..4 valid, then 5 valid AI candidates (eval_count 5..9), then invalid
        if eval_count <= 9:
            return Stage4EvaluationResult(is_valid=True, fitness=0.01, mean_excess_ratio=0.01, pooled_excess_ratio=0.01, total_bins=1, total_l1=1, runtime_ms=1.0, passed_streams=1, total_streams=1, error_message=None)
        else:
            return Stage4EvaluationResult(is_valid=False, fitness=float("inf"), mean_excess_ratio=float("inf"), pooled_excess_ratio=float("inf"), total_bins=0, total_l1=0, runtime_ms=1.0, passed_streams=0, total_streams=1, error_message="TypeError: unsupported operand")

    mock_evaluator.evaluate_candidate.side_effect = mock_eval

    with pytest.raises(LowValidityEarlyStopException) as excinfo:
        run_arm_c_search(
            client=mock_client,
            evaluator=mock_evaluator,
            dev_streams=[{"items": [0.5], "bin_capacity": 1.0}],
            candidate_slots=25,
            seed=40401
        )

    assert "< 60% after first 15 AI candidates" in str(excinfo.value)
    assert "33.3%" in str(excinfo.value)


# ==============================================================================
# Task 2: Missing API credentials offline test
# ==============================================================================

def test_client_initialization_fails_when_omniroute_api_key_missing(monkeypatch, tmp_path):
    """Verify that removing OMNIROUTE_API_KEY causes client initialization to fail clearly before network requests."""
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    monkeypatch.delenv("STAGE4_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    ledger_path = str(tmp_path / "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_cost_usd=15.0)

    with pytest.raises(ValueError) as excinfo:
        Stage4LLMClient(budget_enforcer=enforcer, mock_mode=False, api_key=None)

    assert "OMNIROUTE_API_KEY environment variable is missing" in str(excinfo.value)


def test_client_mock_mode_allows_missing_api_key(monkeypatch, tmp_path):
    """Verify that mock_mode=True allows offline execution even without OMNIROUTE_API_KEY."""
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    monkeypatch.delenv("STAGE4_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    ledger_path = str(tmp_path / "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_cost_usd=15.0)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=True, api_key=None)
    assert client.mock_mode is True
    assert client.api_key is None


# ==============================================================================
# Task 1: Confirmatory holdout selection, integrity, and isolation tests
# ==============================================================================

def test_confirmatory_mode_selects_private_hidden_holdout(tmp_path):
    """Verify confirmatory evaluation explicitly binds to private_hidden holdout."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    hidden_data = [{"stream_id": 101, "items": [0.1, 0.2]}]
    hidden_path = bdir / "hidden.json"
    with open(hidden_path, "w", encoding="utf-8") as f:
        json.dump(hidden_data, f)
    hidden_hash = compute_sha256(str(hidden_path))

    private_hidden_data = [{"stream_id": 201, "items": [0.3, 0.4]}]
    private_hidden_path = bdir / "private_hidden.json"
    with open(private_hidden_path, "w", encoding="utf-8") as f:
        json.dump(private_hidden_data, f)
    private_hidden_hash = compute_sha256(str(private_hidden_path))

    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash},
        "hidden": {"path": "hidden.json", "sha256": hidden_hash},
        "private_hidden": {"path": "private_hidden.json", "sha256": private_hidden_hash}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        mock_mode=True
    )
    assert runner.holdout_key == "private_hidden"

    # Confirmatory mode validates private_hidden
    dev_streams, computed_dev_hash = runner.validate_preconditions(is_pilot=False)
    assert computed_dev_hash == dev_hash
    assert len(dev_streams) == 1


def test_confirmatory_mode_fails_if_private_hidden_missing_from_manifest(tmp_path):
    """Verify confirmatory evaluation fails closed if private_hidden is missing (no fallback to hidden)."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    hidden_data = [{"stream_id": 101, "items": [0.1, 0.2]}]
    hidden_path = bdir / "hidden.json"
    with open(hidden_path, "w", encoding="utf-8") as f:
        json.dump(hidden_data, f)
    hidden_hash = compute_sha256(str(hidden_path))

    # Manifest only contains dev and hidden — private_hidden is omitted
    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash},
        "hidden": {"path": "hidden.json", "sha256": hidden_hash}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        mock_mode=True
    )

    with pytest.raises(KeyError) as excinfo:
        runner.validate_preconditions(is_pilot=False)

    assert "Confirmatory holdout key 'private_hidden' not found in manifest" in str(excinfo.value)
    assert "No fallback permitted" in str(excinfo.value)


def test_confirmatory_mode_fails_if_private_hidden_file_missing(tmp_path):
    """Verify confirmatory evaluation fails closed if private_hidden file is absent on disk."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash},
        "private_hidden": {"path": "private_hidden.json", "sha256": "abcdef1234567890"}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        mock_mode=True
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        runner.validate_preconditions(is_pilot=False)

    assert "Missing confirmatory holdout benchmark file" in str(excinfo.value)


def test_confirmatory_mode_fails_if_private_hidden_corrupted(tmp_path):
    """Verify confirmatory evaluation fails closed if private_hidden hash does not match manifest."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    private_hidden_data = [{"stream_id": 201, "items": [0.3, 0.4]}]
    private_hidden_path = bdir / "private_hidden.json"
    with open(private_hidden_path, "w", encoding="utf-8") as f:
        json.dump(private_hidden_data, f)

    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash},
        "private_hidden": {"path": "private_hidden.json", "sha256": "wrong_hash_deadbeef"}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        mock_mode=True
    )

    with pytest.raises(ValueError) as excinfo:
        runner.validate_preconditions(is_pilot=False)

    assert "CORRUPTED CONFIRMATORY HOLDOUT BENCHMARK" in str(excinfo.value)


def test_pilot_mode_never_touches_private_hidden(tmp_path):
    """Verify that pilot mode never touches or requires private_hidden."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    # Manifest has dev only; private_hidden.json does not even exist
    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        mock_mode=True
    )

    dev_streams, computed_dev_hash = runner.validate_preconditions(is_pilot=True)
    assert computed_dev_hash == dev_hash
    assert len(dev_streams) == 1


# =============================================================================
# Priority P0 Regression Tests
# =============================================================================

def test_trial_record_integrity_and_validation(tmp_path):
    """P0.A: Verify that run_paired_trial populates all required fields and passes validate_trial_record."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    manifest = {"dev": {"path": "dev.json", "sha256": dev_hash}}
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        candidate_slots=5,
        mock_mode=True
    )

    streams, _ = runner.validate_preconditions(is_pilot=True)
    record = runner.run_paired_trial(trial_id=1, seed=40401, dev_streams=streams)

    # Validate structure
    validate_trial_record(record)
    assert record["trial_id"] == 1
    assert record["seed"] == 40401
    assert "delta_dev" in record

    for arm in ("arm_a", "arm_c"):
        arm_data = record[arm]
        assert "candidate_id" in arm_data
        assert "code" in arm_data
        assert "is_valid" in arm_data and isinstance(arm_data["is_valid"], bool)
        assert "mutation_type" in arm_data and isinstance(arm_data["mutation_type"], str)
        assert "is_seed" in arm_data and isinstance(arm_data["is_seed"], bool)
        assert "dev_fitness" in arm_data and math.isfinite(arm_data["dev_fitness"])
        assert "stats" in arm_data
        assert "error_message" in arm_data


def test_trial_record_validation_rejects_missing_fields():
    """P0.A: validate_trial_record fails closed on missing required fields."""
    base_record = {
        "trial_id": 1,
        "seed": 40401,
        "delta_dev": 0.0,
        "arm_a": {
            "candidate_id": "c1",
            "code": "def priority(...): pass",
            "is_valid": True,
            "mutation_type": "independent_sample",
            "is_seed": False,
            "dev_fitness": 0.05
        },
        "arm_c": {
            "candidate_id": "c2",
            "code": "def priority(...): pass",
            "is_valid": True,
            "mutation_type": "evolutionary_step",
            "is_seed": False,
            "dev_fitness": 0.04
        }
    }
    # Valid record passes
    validate_trial_record(base_record)

    # Missing arm_a is_valid
    bad_rec = json.loads(json.dumps(base_record))
    del bad_rec["arm_a"]["is_valid"]
    with pytest.raises(ValueError, match="MALFORMED_TRIAL_RECORD: Missing field 'is_valid'"):
        validate_trial_record(bad_rec)

    # Missing arm_c mutation_type
    bad_rec = json.loads(json.dumps(base_record))
    del bad_rec["arm_c"]["mutation_type"]
    with pytest.raises(ValueError, match="MALFORMED_TRIAL_RECORD: Missing field 'mutation_type'"):
        validate_trial_record(bad_rec)

    # Missing delta_dev
    bad_rec = json.loads(json.dumps(base_record))
    del bad_rec["delta_dev"]
    with pytest.raises(ValueError, match="MALFORMED_TRIAL_RECORD: Missing required key 'delta_dev'"):
        validate_trial_record(bad_rec)


def test_trial_record_validation_rejects_contradictions():
    """P0.A: validate_trial_record detects contradictory provenance and invalid fitness."""
    # Seed marked with AI mutation type
    rec1 = {
        "trial_id": 1, "seed": 40401, "delta_dev": 0.0,
        "arm_a": {
            "candidate_id": "c1", "code": "def priority(...): pass",
            "is_valid": True, "mutation_type": "independent_sample", "is_seed": True, "dev_fitness": 0.05
        },
        "arm_c": {
            "candidate_id": "c2", "code": "def priority(...): pass",
            "is_valid": True, "mutation_type": "evolutionary_step", "is_seed": False, "dev_fitness": 0.04
        }
    }
    with pytest.raises(ValueError, match="CONTRADICTORY_TRIAL_RECORD"):
        validate_trial_record(rec1)

    # Non-seed marked with seed mutation type
    rec2 = json.loads(json.dumps(rec1))
    rec2["arm_a"]["is_seed"] = False
    rec2["arm_a"]["mutation_type"] = "seed_best_fit"
    with pytest.raises(ValueError, match="CONTRADICTORY_TRIAL_RECORD"):
        validate_trial_record(rec2)

    # is_valid=True with non-finite fitness
    rec3 = json.loads(json.dumps(rec1))
    rec3["arm_a"]["is_seed"] = False
    rec3["arm_a"]["dev_fitness"] = float("inf")
    with pytest.raises(ValueError, match="CONTRADICTORY_TRIAL_RECORD"):
        validate_trial_record(rec3)

    # is_valid=False with finite fitness
    rec4 = json.loads(json.dumps(rec1))
    rec4["arm_a"]["is_seed"] = False
    rec4["arm_a"]["is_valid"] = False
    rec4["arm_a"]["dev_fitness"] = 0.05
    with pytest.raises(ValueError, match="CONTRADICTORY_TRIAL_RECORD"):
        validate_trial_record(rec4)


def test_confirmatory_mode_fails_if_pilot_results_path_omitted(tmp_path):
    """P0.B: Confirmatory run cannot proceed if pilot_results_path is omitted."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    priv_data = [{"stream_id": 201, "items": [0.5, 0.5]}]
    priv_path = bdir / "private_hidden.json"
    with open(priv_path, "w", encoding="utf-8") as f:
        json.dump(priv_data, f)
    priv_hash = compute_sha256(str(priv_path))

    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash},
        "private_hidden": {"path": "private_hidden.json", "sha256": priv_hash}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    runner = Stage4Runner(output_dir=str(outdir), benchmark_dir=str(bdir), mock_mode=True)

    with pytest.raises(ValueError, match="PHASE 2 LAUNCH REJECTED: pilot_results_path is required"):
        runner.execute_campaign(
            num_trials=10,
            start_seed=40411,
            is_pilot=False,
            phase_two_authorized=True,
            pilot_results_path=None
        )


def test_confirmatory_mode_fails_if_fingerprint_mismatch(tmp_path):
    """P0.B: Confirmatory execution rejects pilot artifact with mismatched configuration fingerprint."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    priv_data = [{"stream_id": 201, "items": [0.5, 0.5]}]
    priv_path = bdir / "private_hidden.json"
    with open(priv_path, "w", encoding="utf-8") as f:
        json.dump(priv_data, f)
    priv_hash = compute_sha256(str(priv_path))

    manifest = {
        "dev": {"path": "dev.json", "sha256": dev_hash},
        "private_hidden": {"path": "private_hidden.json", "sha256": priv_hash}
    }
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    pilot_file = tmp_path / "pilot_mismatch.json"
    pilot_payload = {
        "config_fingerprint": "incompatible_fingerprint_deadbeef",
        "final_statistics": {
            "phase": "phase_1_pilot_feasibility",
            "num_trials": 3,
            "operational_feasibility_passed": True,
            "dev_improvement_passed": True,
            "gate1_passed": True
        },
        "trials": []
    }
    with open(pilot_file, "w", encoding="utf-8") as f:
        json.dump(pilot_payload, f)

    runner = Stage4Runner(output_dir=str(outdir), benchmark_dir=str(bdir), mock_mode=True)

    with pytest.raises(RuntimeError, match="PHASE 2 LAUNCH REJECTED: Pilot configuration fingerprint"):
        runner.execute_campaign(
            num_trials=10,
            start_seed=40411,
            is_pilot=False,
            phase_two_authorized=True,
            pilot_results_path=str(pilot_file)
        )


def test_confirmatory_mode_fails_if_holdout_key_overridden(tmp_path):
    """P0.B: Overriding holdout_key to anything other than 'private_hidden' in confirmatory mode fails closed."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        mock_mode=True,
        holdout_key="hidden"  # Unauthorized holdout key override
    )

    with pytest.raises(ValueError, match="CONFIRMATORY PROTOCOL VIOLATION: Confirmatory holdout must be 'private_hidden'"):
        runner.validate_preconditions(is_pilot=False)


def test_evaluate_on_hidden_benchmark_fails_without_authorization():
    """P0.B: Lower-level evaluate_on_hidden_benchmark cannot be invoked without phase_two_authorized=True."""
    runner = Stage4Runner(output_dir="dummy", benchmark_dir="dummy", mock_mode=True)
    with pytest.raises(RuntimeError, match="PHASE 2 ACCESS FORBIDDEN: Direct call to evaluate_on_hidden_benchmark requires explicit phase_two_authorized=True"):
        runner.evaluate_on_hidden_benchmark(trials=[], hidden_streams=[], phase_two_authorized=False)


def test_wilcoxon_signed_rank_tie_handling_mixed_signs():
    """P0.C: Verify tie-handling correctness on mixed-sign ties against scipy reference."""
    diffs = [2.0, -2.0, 3.0, -3.0, 4.0]
    t_stat, p_val = compute_wilcoxon_test(diffs)
    scipy_res = scipy.stats.wilcoxon(diffs, alternative="two-sided")

    # Scipy reference: statistic=5.0, p-value=0.6875
    assert t_stat == scipy_res.statistic
    assert abs(p_val - scipy_res.pvalue) < 1e-4
    assert t_stat == 5.0
    assert p_val == 0.6875  # The buggy loop previously returned 0.0625!


def test_wilcoxon_signed_rank_reference_cases():
    """P0.C: Verify test statistic and p-value against reference cases."""
    cases = [
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.0, 0.0625),
        ([-1.0, -2.0, -3.0, -4.0, -5.0], 0.0, 0.0625),
        ([1.0, -1.0, 2.0, -2.0, 3.0, -3.0], 10.5, 1.0),
        ([0.0, 0.0, 0.0], 0.0, 1.0),
    ]
    for diffs, exp_stat, exp_p in cases:
        stat, pval = compute_wilcoxon_test(diffs)
        assert stat == exp_stat
        assert abs(pval - exp_p) < 1e-4

    # Non-finite handling
    stat_nan, pval_nan = compute_wilcoxon_test([1.0, float("nan"), 2.0])
    assert math.isnan(stat_nan) and math.isnan(pval_nan)


def test_budget_enforcer_fails_closed_on_corrupted_json(tmp_path):
    """P0.D: BudgetEnforcer raises CorruptedLedgerException and preserves backup on corrupt JSON."""
    ledger_path = str(tmp_path / "budget.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("{corrupted json contents")

    with pytest.raises(CorruptedLedgerException, match="CORRUPTED BUDGET LEDGER: Failed to parse JSON"):
        BudgetEnforcer(ledger_path=ledger_path)

    # Verify that a backup copy was created
    files = os.listdir(str(tmp_path))
    backup_files = [f for f in files if "budget.json.corrupted" in f]
    assert len(backup_files) == 1


def test_budget_enforcer_fails_closed_on_empty_ledger_file(tmp_path):
    """P0.D: BudgetEnforcer raises CorruptedLedgerException on empty 0-byte file."""
    ledger_path = str(tmp_path / "budget.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        pass  # 0 bytes

    with pytest.raises(CorruptedLedgerException, match="empty \\(0 bytes\\)"):
        BudgetEnforcer(ledger_path=ledger_path)

    files = os.listdir(str(tmp_path))
    backup_files = [f for f in files if "budget.json.corrupted" in f]
    assert len(backup_files) == 1


def test_budget_enforcer_fails_closed_on_negative_or_missing_fields(tmp_path):
    """P0.D: BudgetEnforcer rejects negative or missing numeric telemetry fields."""
    ledger_path = str(tmp_path / "budget.json")
    bad_data = {
        "requests_count": -10,  # Negative value
        "retries_count": 0,
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.05,
        "elapsed_sec": 10.0
    }
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(bad_data, f)

    with pytest.raises(CorruptedLedgerException, match="must be a non-negative finite number"):
        BudgetEnforcer(ledger_path=ledger_path)


def test_checkpoint_resumption_rejects_incompatible_fingerprint(tmp_path):
    """P0.E: Checkpoint resumption rejects checkpoint with mismatched experiment fingerprint."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    manifest = {"dev": {"path": "dev.json", "sha256": dev_hash}}
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Create a checkpoint with a different fingerprint
    chk_file = outdir / "checkpoint.json"
    chk_payload = {
        "timestamp": 123456789.0,
        "config_fingerprint": "incompatible_config_hash_xyz",
        "completed_trials": [{"trial_id": 1, "seed": 40401}],
        "is_pilot": True
    }
    with open(chk_file, "w", encoding="utf-8") as f:
        json.dump(chk_payload, f)

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        candidate_slots=5,
        mock_mode=True
    )

    with pytest.raises(RuntimeError, match="CHECKPOINT REUSE REJECTED: Checkpoint fingerprint"):
        runner.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)


def test_checkpoint_fails_closed_on_corrupted_file(tmp_path):
    """P0.E: Runner fails closed if checkpoint.json is corrupted."""
    bdir = tmp_path / "benchmarks"
    bdir.mkdir()
    outdir = tmp_path / "output"
    outdir.mkdir()

    dev_data = [{"stream_id": 1, "items": [0.5, 0.5]}]
    dev_path = bdir / "dev.json"
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_data, f)
    dev_hash = compute_sha256(str(dev_path))

    manifest = {"dev": {"path": "dev.json", "sha256": dev_hash}}
    with open(bdir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Write corrupt checkpoint
    chk_file = outdir / "checkpoint.json"
    with open(chk_file, "w", encoding="utf-8") as f:
        f.write("{invalid json")

    runner = Stage4Runner(
        output_dir=str(outdir),
        benchmark_dir=str(bdir),
        candidate_slots=5,
        mock_mode=True
    )

    with pytest.raises(RuntimeError, match="CORRUPTED CHECKPOINT: Failed to load checkpoint"):
        runner.execute_campaign(num_trials=3, start_seed=40401, is_pilot=True)



