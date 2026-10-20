"""
Unit tests for centralized LLM config and Global Budget Ledger (REPRO-1, REPRO-4, P0 2.4, 3.4).
"""
import multiprocessing as mp
import os
import tempfile
import pytest

from amaura.llm_config import get_config, LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS
from amaura_exec.budget_ledger import (
    GlobalBudgetLedger,
    BudgetExceededError,
    LedgerCorruptError,
)


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
    assert len(reloaded_ledger._load_locked()["runs"]) == 1


def test_budget_reservation_lifecycle(tmp_path):
    """P0 2.4 / 3.4: Atomic budget reservation, reconciliation, and release."""
    ledger_file = str(tmp_path / "ledger_res.json")
    ledger = GlobalBudgetLedger(ledger_path=ledger_file, cap_usd=10.0)

    # Reserve 4.0
    token1 = ledger.reserve_budget("run_a", estimated_cost_usd=4.0, max_requests=50)
    assert token1.startswith("res_")
    assert ledger.total_reserved_usd == 4.0
    assert ledger.remaining_unreserved_usd == 6.0
    assert ledger.total_spent_usd == 0.0

    # Reserve another 5.0
    token2 = ledger.reserve_budget("run_b", estimated_cost_usd=5.0, max_requests=60)
    assert ledger.total_reserved_usd == 9.0
    assert ledger.remaining_unreserved_usd == 1.0

    # Attempting to reserve 2.0 when only 1.0 unreserved must raise BudgetExceededError
    with pytest.raises(BudgetExceededError):
        ledger.reserve_budget("run_c", estimated_cost_usd=2.0)

    # Settle token1: actual cost was 3.20
    ledger.reconcile_reservation(token1, actual_cost_usd=3.20, actual_requests=42)
    assert ledger.total_spent_usd == 3.20
    assert ledger.total_reserved_usd == 5.0
    assert ledger.remaining_unreserved_usd == 1.80

    # Reconciling same token again raises KeyError
    with pytest.raises(KeyError):
        ledger.reconcile_reservation(token1, actual_cost_usd=1.0, actual_requests=10)

    # Release token2 (cancelled run)
    ledger.release_reservation(token2)
    assert ledger.total_reserved_usd == 0.0
    assert ledger.remaining_unreserved_usd == 6.80
    assert ledger.total_spent_usd == 3.20


def test_ledger_fails_closed_on_corruption(tmp_path):
    """P0 2.4: Ledger must fail closed when corrupt, not reset spend to 0."""
    ledger_file = tmp_path / "corrupt_ledger.json"
    ledger_file.write_text("{ this is malformed json", encoding="utf-8")

    with pytest.raises(LedgerCorruptError):
        GlobalBudgetLedger(ledger_path=str(ledger_file), cap_usd=10.0)

    # Empty file also fails closed
    ledger_file.write_text("", encoding="utf-8")
    with pytest.raises(LedgerCorruptError):
        GlobalBudgetLedger(ledger_path=str(ledger_file), cap_usd=10.0)


def _worker_reserve_attempt(ledger_path: str, cap_usd: float, run_id: str, amount: float, result_queue: mp.Queue):
    """Worker process attempting to reserve budget."""
    try:
        ledger = GlobalBudgetLedger(ledger_path=ledger_path, cap_usd=cap_usd)
        token = ledger.reserve_budget(run_id, estimated_cost_usd=amount)
        result_queue.put({"ok": True, "token": token, "error": None})
    except BudgetExceededError as be:
        result_queue.put({"ok": False, "token": None, "error": "BudgetExceeded"})
    except Exception as e:
        result_queue.put({"ok": False, "token": None, "error": str(e)})


def test_concurrent_budget_reservations_cannot_exceed_cap(tmp_path):
    """P0 2.4: Competing concurrent processes cannot double-spend or exceed cap."""
    ledger_file = str(tmp_path / "concurrent_ledger.json")
    # Initialize ledger with cap = 10.0
    GlobalBudgetLedger(ledger_path=ledger_file, cap_usd=10.0)

    # Spawn 4 processes each attempting to reserve 4.0
    # Total requested = 16.0, cap = 10.0 -> at most 2 can succeed (2 * 4.0 = 8.0), remaining 2 must be rejected
    ctx = mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")
    q = ctx.Queue()
    procs = []

    for i in range(4):
        p = ctx.Process(target=_worker_reserve_attempt, args=(ledger_file, 10.0, f"proc_{i}", 4.0, q))
        procs.append(p)
        p.start()

    for p in procs:
        p.join(timeout=5.0)

    results = []
    while not q.empty():
        results.append(q.get_nowait())

    success_count = sum(1 for r in results if r["ok"])
    exceeded_count = sum(1 for r in results if r.get("error") == "BudgetExceeded")

    assert success_count == 2, f"Expected exactly 2 successful reservations of 4.0 from 10.0 cap, got {success_count}"
    assert exceeded_count == 2, f"Expected exactly 2 BudgetExceeded rejections, got {exceeded_count}"

    # Verify final ledger state matches
    final_ledger = GlobalBudgetLedger(ledger_path=ledger_file, cap_usd=10.0)
    assert final_ledger.total_reserved_usd == 8.0
    assert final_ledger.remaining_unreserved_usd == 2.0
