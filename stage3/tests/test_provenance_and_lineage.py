"""
Unit Tests: Model Provenance, Lineage Logging, and Offline Mock Mode
===================================================================
Verifies:
1. ModelMismatchException raised if returned model does not match requested model.
2. LineageTracker records complete provenance records with hashes.
3. Offline mock mode generates valid synthetic responses without network access.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from stage3.src.llm_client import Stage3LLMClient, ModelMismatchException
from stage3.src.lineage import LineageTracker


def test_model_mismatch_exception():
    client = Stage3LLMClient(
        base_url="http://127.0.0.1:20128/v1/chat/completions",
        model="nvidia/nvidia/nemotron-3-super-120b-a12b",
        mock_mode=False
    )

    fake_api_response = {
        "model": "some-unauthorized-gpt4-model",
        "choices": [{"message": {"content": "def color_graph(adj): return []"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10}
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_api_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(ModelMismatchException) as exc_info:
            client.query(
                prompt="test prompt",
                system_prompt="test system",
                expected_func="color_graph"
            )
        assert "FATAL MODEL MISMATCH" in str(exc_info.value)


def test_offline_mock_mode_zero_network():
    client = Stage3LLMClient(
        base_url="http://invalid-url-that-would-fail",
        model="nvidia/nvidia/nemotron-3-super-120b-a12b",
        mock_mode=True
    )

    res = client.query(
        prompt="Write a graph coloring algorithm",
        system_prompt="You are an algorithm designer",
        expected_func="color_graph"
    )

    assert res["code"] is not None
    assert "def color_graph" in res["code"]
    assert res["returned_model"] == "nvidia/nvidia/nemotron-3-super-120b-a12b"
    assert res["cost"] > 0.0 or res["total_tokens"] > 0


def test_lineage_tracker_16_fields(tmp_path):
    log_file = tmp_path / "candidates.jsonl"
    tracker = LineageTracker(str(log_file))

    rec = tracker.record_candidate(
        trial_id=1,
        arm="C_AMAURA",
        generation=2,
        candidate_index_in_gen=1,
        global_candidate_index=11,
        candidate_id="T01_C_G02_C01",
        code="def color_graph(adj): return []",
        prompt_text="Prompt text",
        system_prompt="System prompt",
        model_identifier="test-model",
        model_call_id="call-011",
        prompt_tokens=150,
        completion_tokens=60,
        generation_cost=0.001,
        latency_ms=45.2,
        validity=True,
        development_score=125,
        failure_category=None,
        runtime_ms=12.5,
        error_msg=None,
        parent_candidate_ids=["T01_C_G01_C03"],
        mutation_type="modify_tiebreaker",
        random_seed=30311
    )

    # Read back from file
    with open(log_file) as f:
        lines = f.readlines()
    assert len(lines) == 1
    logged_data = json.loads(lines[0])

    # Check key lineage fields
    assert logged_data["candidate_id"] == "T01_C_G02_C01"
    assert logged_data["arm"] == "C_AMAURA"
    assert logged_data["generation"] == 2
    assert logged_data["global_candidate_index"] == 11
    assert logged_data["parent_candidate_ids"] == ["T01_C_G01_C03"]
    assert logged_data["mutation_type"] == "modify_tiebreaker"
    assert logged_data["candidate_code_hash"] is not None
    assert logged_data["prompt_hash"] is not None
    assert logged_data["system_prompt_hash"] is not None
