"""
Unit Tests: Candidate Budget Accounting & Slot Invariants
=========================================================
Verifies:
1. Exactly 100 candidate slots consumed per arm per trial.
2. Crashing, timing out, or invalid candidates consume exactly 1 slot without retry.
3. Zero bonus candidates, zero replacements.
4. Zero-valid trials yield ARM_FAILURE_NO_VALID_CANDIDATE.
"""

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
    blind_p.write_text("Blind select prompt text")

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
    # Triangle graph K3
    return [{"adj": [[1, 2], [0, 2], [0, 1]]}]


def test_arm_a_budget_and_slot_accounting(mock_config, dummy_dataset, tmp_path):
    lineage_file = tmp_path / "lineage.jsonl"
    tracker = LineageTracker(str(lineage_file))

    # Mock LLM client: 90 valid candidates, 10 crashes
    llm = MagicMock(spec=Stage3LLMClient)
    call_count = 0

    def mock_query(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 10:
            # Crashing code
            code = "def color_graph(adj):\n    raise RuntimeError('crash')\n"
        else:
            # Valid code
            code = "def color_graph(adj):\n    return list(range(len(adj)))\n"
        return {
            "code": code,
            "raw_response": code,
            "prompt_hash": "hash123",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "latency_ms": 20.0,
            "cost": 0.001,
            "returned_model": "test-model"
        }

    llm.query.side_effect = mock_query
    evaluator = GraphColoringEvaluator()
    engine = Stage3SearchEngine(mock_config, llm, evaluator, tracker)

    res = engine.run_arm_a(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)

    # Invariants:
    assert res["total_candidates_generated"] == 100
    assert len(res["candidates"]) == 100
    assert call_count == 100
    assert res["valid_candidates_count"] == 90
    assert res["status"] == "VALID"
    assert res["selected_candidate_id"] is not None


def test_arm_a_zero_valid_handling(mock_config, dummy_dataset, tmp_path):
    lineage_file = tmp_path / "lineage.jsonl"
    tracker = LineageTracker(str(lineage_file))

    # Mock LLM client: 100% crashing candidates
    llm = MagicMock(spec=Stage3LLMClient)
    call_count = 0

    def mock_query(**kwargs):
        nonlocal call_count
        call_count += 1
        code = "def color_graph(adj):\n    raise RuntimeError('fatal')\n"
        return {
            "code": code,
            "raw_response": code,
            "prompt_hash": "hash123",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "latency_ms": 20.0,
            "cost": 0.001,
            "returned_model": "test-model"
        }

    llm.query.side_effect = mock_query
    evaluator = GraphColoringEvaluator()
    engine = Stage3SearchEngine(mock_config, llm, evaluator, tracker)

    res = engine.run_arm_a(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)

    # Must consume exactly 100 slots and output ARM_FAILURE_NO_VALID_CANDIDATE
    assert res["total_candidates_generated"] == 100
    assert call_count == 100
    assert res["valid_candidates_count"] == 0
    assert res["status"] == "ARM_FAILURE_NO_VALID_CANDIDATE"
    assert res["selected_candidate_id"] is None
    assert res["selected_dev_score"] is None


def test_arm_b_and_c_budget_accounting(mock_config, dummy_dataset, tmp_path):
    lineage_file = tmp_path / "lineage.jsonl"
    tracker = LineageTracker(str(lineage_file))

    llm = MagicMock(spec=Stage3LLMClient)

    def mock_query(**kwargs):
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
            sel_text = "SELECTED_CANDIDATE: Candidate_01"
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

    # Arm B test
    res_b = engine.run_arm_b(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)
    assert res_b["total_candidates_generated"] == 100
    assert len(res_b["candidates"]) == 100
    assert res_b["valid_candidates_count"] == 100

    # Arm C test
    res_c = engine.run_arm_c(trial_id=1, dev_dataset=dummy_dataset, trial_seed=30301)
    assert res_c["total_candidates_generated"] == 100
    assert len(res_c["candidates"]) == 100
    assert res_c["valid_candidates_count"] == 100


def test_search_curves_computation():
    from stage3.src.search_curves import compute_best_so_far_curve, analyze_trial_trajectories

    # Create 100 synthetic candidates with decreasing scores
    cands = []
    for i in range(1, 101):
        score = 100 - i  # 99 down to 0
        cands.append({
            "global_candidate_index": i,
            "validity": True,
            "development_score": score
        })

    curve = compute_best_so_far_curve(cands)
    assert curve[1] == 99
    assert curve[5] == 95
    assert curve[10] == 90
    assert curve[20] == 80
    assert curve[50] == 50
    assert curve[100] == 0

    analysis = analyze_trial_trajectories(1, cands, cands, cands)
    assert "retrospective" in analysis["Arm_A_Independent_Best_of_N"]["nature"].lower()

