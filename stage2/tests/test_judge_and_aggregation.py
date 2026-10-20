"""
Unit Tests: Blind Judge & 3-Shuffle Deterministic Aggregation
============================================================
Enforces Section 3 & 35.
"""

import pytest
from stage2.src.judge import BlindJudgeEngine
from stage2.src.llm_client import Stage2LLMClient


def test_judge_aggregation_unanimous():
    client = Stage2LLMClient(mock_mode=True)
    engine = BlindJudgeEngine(client)

    votes = ["Option_05", "Option_05", "Option_05"]
    winner, reason = engine.aggregate_votes(votes)
    assert winner == "Option_05"
    assert "UNANIMOUS" in reason


def test_judge_aggregation_majority():
    client = Stage2LLMClient(mock_mode=True)
    engine = BlindJudgeEngine(client)

    votes = ["Option_02", "Option_07", "Option_02"]
    winner, reason = engine.aggregate_votes(votes)
    assert winner == "Option_02"
    assert "MAJORITY" in reason


def test_judge_aggregation_three_way_tie_break():
    client = Stage2LLMClient(mock_mode=True)
    engine = BlindJudgeEngine(client)

    votes = ["Option_12", "Option_03", "Option_09"]
    winner, reason = engine.aggregate_votes(votes)
    # Lexicographically smallest ID must be selected
    assert winner == "Option_03"
    assert "TIE_BREAK" in reason


def test_judge_candidate_order_randomization():
    candidates = [{"candidate_id": f"C_{i:02d}", "code": f"def f_{i}(): pass"} for i in range(20)]
    client = Stage2LLMClient(mock_mode=True)
    engine = BlindJudgeEngine(client)

    res1 = engine.run_single_shuffle("graph_coloring", candidates, shuffle_seed=101, client=client)
    res2 = engine.run_single_shuffle("graph_coloring", candidates, shuffle_seed=202, client=client)

    # Shuffles with different seeds must produce different presentation orders
    assert res1["presentation_order"] != res2["presentation_order"]
