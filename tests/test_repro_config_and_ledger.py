"""
Unit tests for centralized LLM config and Global Budget Ledger (REPRO-1, REPRO-4).
"""
import os
import tempfile
import pytest

from amaura.llm_config import get_config, LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS
from amaura_exec.budget_ledger import GlobalBudgetLedger


def test_llm_config_defaults_and_env_overrides(monkeypatch):
    """Verifies that centralized LLM config provides sensible defaults and respects env."""
    cfg = get_config()
    assert "base_url" in cfg
    assert "model" in cfg
    assert "max_tokens" in cfg
    assert cfg["max_tokens"] >= 512

    # Test override
    monkeypatch.setenv("LLM_MODEL", "custom/test-model-40b")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    cfg2 = get_config()
    assert cfg2["model"] == "custom/test-model-40b"
    assert cfg2["max_tokens"] == 2048


def test_global_budget_ledger_tracking(tmp_path):
    """Verifies global budget ledger persistence, preflight checks, and spend recording."""
    ledger_file = str(tmp_path / "test_budget_ledger.json")
    ledger = GlobalBudgetLedger(ledger_path=ledger_file, cap_usd=10.0)

    # Initially empty
    assert ledger.total_spent_usd == 0.0
    assert ledger.total_requests == 0
    assert ledger.remaining_usd == 10.0
    assert ledger.preflight_check(5.0) is True
    assert ledger.preflight_check(15.0) is False

    # Record spend
    ledger.record_spend("pilot_run_1", cost_usd=3.50, requests=100)
    assert ledger.total_spent_usd == 3.50
    assert ledger.total_requests == 100
    assert ledger.remaining_usd == 6.50
    assert ledger.preflight_check(7.0) is False
    assert ledger.preflight_check(6.0) is True

    # Reload from disk into new instance
    reloaded_ledger = GlobalBudgetLedger(ledger_path=ledger_file, cap_usd=10.0)
    assert reloaded_ledger.total_spent_usd == 3.50
    assert reloaded_ledger.total_requests == 100
    assert reloaded_ledger.remaining_usd == 6.50
    assert len(reloaded_ledger._data["runs"]) == 1
