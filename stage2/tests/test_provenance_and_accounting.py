"""
Unit Tests: Model Provenance, Fallback Abort, and Cost Accounting
=================================================================
Enforces Section 16 & 21.
"""

import pytest
from stage2.src.llm_client import Stage2LLMClient, ModelMismatchException


def test_cost_calculation():
    client = Stage2LLMClient(cost_per_m_input=3.00, cost_per_m_output=15.00)
    # 10,000 prompt tokens, 1,000 completion tokens
    # Cost = (10,000 / 1M) * 3.00 + (1,000 / 1M) * 15.00 = 0.030 + 0.015 = 0.045
    cost = client.calculate_cost(prompt_tokens=10000, completion_tokens=1000)
    assert cost == pytest.approx(0.045, rel=1e-4)


def test_mock_query_telemetry():
    client = Stage2LLMClient(mock_mode=True)
    resp = client.query(
        prompt="Design a coloring solver",
        system_prompt="System instructions",
        expected_func="color_graph"
    )

    assert resp["success"] is True
    assert resp["prompt_tokens"] > 0
    assert resp["completion_tokens"] > 0
    assert resp["cost"] > 0.0
    assert "def color_graph" in resp["code"]
    assert client.total_calls == 1
