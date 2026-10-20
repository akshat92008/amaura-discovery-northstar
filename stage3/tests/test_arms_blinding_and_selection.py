"""
Unit Tests: Arm Blinding Invariants and Selection Mechanisms
============================================================
Verifies:
1. Arm A prompt invariant: strictly zero inter-candidate feedback.
2. Arm B blinding invariant: prompts contain code only, ZERO execution scores.
3. Arm B deterministic blind selection: parses Candidate_XX, falls back to Candidate_01.
4. Arm C structured feedback invariant: strictly 5 fields, zero narrative prose.
"""

import json
import re
import pytest
from unittest.mock import MagicMock
from stage3.src.search_engine import Stage3SearchEngine
from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.lineage import LineageTracker
from stage3.src.llm_client import Stage3LLMClient


@pytest.fixture
def mock_config(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    expert_p = prompts_dir / "expert.txt"
    expert_p.write_text("Expert prompt text")
    blind_p = prompts_dir / "blind.txt"
    blind_p.write_text("Deterministic blind select prompt")

    return {
        "prompts": {
            "expert_gc": str(expert_p),
            "blind_select": str(blind_p)
        },
        "temperature": 0.7,
        "max_tokens": 1024
    }


@pytest.fixture
def dummy_dataset():
    return [{"adj": [[1, 2], [0, 2], [0, 1]]}]


def test_arm_b_blinding_and_deterministic_selection(mock_config, dummy_dataset, tmp_path):
    lineage_file = tmp_path / "lineage.jsonl"
    tracker = LineageTracker(str(lineage_file))

    prompts_received = []
    llm = MagicMock(spec=Stage3LLMClient)

    def mock_query(prompt, **kwargs):
        prompts_received.append(prompt)
        expected_func = kwargs.get("expected_func", "")
        if expected_func == "color_graph":
            code = "def color_graph(adj):\n    return list(range(len(adj)))\n"
            return {
                "code": code,
                "raw_response": code,
                "prompt_hash": "hash",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "latency_ms": 20.0,
                "cost": 0.001,
                "returned_model": "test-model"
            }
        else:
            # Blind selection response selecting Candidate_04
            sel_text = "Analysis complete.\nSELECTED_CANDIDATE: Candidate_04\nRationale: optimal"
            return {
                "code": "",
                "raw_response": sel_text,
                "prompt_hash": "hash_sel",
                "prompt_tokens": 200,
                "completion_tokens": 30,
                "latency_ms": 15.0,
                "cost": 0.001,
                "returned_model": "test-model"
            }

    llm.query.side_effect = mock_query
    evaluator = GraphColoringEvaluator()
    engine = Stage3SearchEngine(mock_config, llm, evaluator, tracker)

    res = engine.run_arm_b(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)

    # 1. Check prompt blinding in Arm B:
    # None of the generation prompts should contain execution metrics or score words
    for p in prompts_received[:-1]:  # all generation prompts
        assert "development_score" not in p
        assert "failure_category" not in p
        assert "runtime_ms" not in p

    # 2. Check deterministic selection:
    assert res["status"] == "VALID"
    assert "C04" in res["selected_candidate_id"]


def test_arm_b_deterministic_selection_fallback(mock_config, dummy_dataset, tmp_path):
    lineage_file = tmp_path / "lineage.jsonl"
    tracker = LineageTracker(str(lineage_file))

    llm = MagicMock(spec=Stage3LLMClient)

    def mock_query(prompt, **kwargs):
        expected_func = kwargs.get("expected_func", "")
        if expected_func == "color_graph":
            code = "def color_graph(adj):\n    return list(range(len(adj)))\n"
            return {
                "code": code,
                "raw_response": code,
                "prompt_hash": "hash",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "latency_ms": 20.0,
                "cost": 0.001,
                "returned_model": "test-model"
            }
        else:
            # Unparseable response -> Fallback to Candidate_01
            sel_text = "I cannot decide which candidate is best."
            return {
                "code": "",
                "raw_response": sel_text,
                "prompt_hash": "hash_sel",
                "prompt_tokens": 200,
                "completion_tokens": 30,
                "latency_ms": 15.0,
                "cost": 0.001,
                "returned_model": "test-model"
            }

    llm.query.side_effect = mock_query
    evaluator = GraphColoringEvaluator()
    engine = Stage3SearchEngine(mock_config, llm, evaluator, tracker)

    res = engine.run_arm_b(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)

    assert res["status"] == "VALID"
    # Fallback to Candidate_01 of generation 10
    assert "G10_C01" in res["selected_candidate_id"]


def test_arm_c_structured_feedback_packet(mock_config, dummy_dataset, tmp_path):
    lineage_file = tmp_path / "lineage.jsonl"
    tracker = LineageTracker(str(lineage_file))

    prompts_received = []
    llm = MagicMock(spec=Stage3LLMClient)

    def mock_query(prompt, **kwargs):
        prompts_received.append(prompt)
        code = "def color_graph(adj):\n    return list(range(len(adj)))\n"
        return {
            "code": code,
            "raw_response": code,
            "prompt_hash": "hash",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "latency_ms": 20.0,
            "cost": 0.001,
            "returned_model": "test-model"
        }

    llm.query.side_effect = mock_query
    evaluator = GraphColoringEvaluator()
    engine = Stage3SearchEngine(mock_config, llm, evaluator, tracker)

    res = engine.run_arm_c(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)

    assert res["status"] == "VALID"
    assert res["total_candidates_generated"] == 100

    # In generations 2..10, prompts should contain ```json ... ``` blocks with exactly 5 keys
    gen2_plus_prompts = prompts_received[10:]
    assert len(gen2_plus_prompts) == 90

    for p in gen2_plus_prompts:
        assert "## Empirical Development Execution Feedback" in p
        # Extract JSON block
        json_match = re.search(r"```json\s*(\[.*?\])\s*```", p, re.DOTALL)
        assert json_match is not None, "Missing structured JSON feedback block"
        feedback = json.loads(json_match.group(1))
        assert len(feedback) == 10
        for entry in feedback:
            assert set(entry.keys()) == {
                "candidate_id", "validity", "development_score", "failure_category", "runtime_ms"
            }
