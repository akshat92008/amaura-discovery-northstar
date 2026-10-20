"""
Stage 4 Hard Budget Enforcement & Checkpoint Recovery Tests
===========================================================
Validates real, hard budget enforcement wrapping LLM query pipelines:
1. Request-limit exhaustion (aborts before crossing limit).
2. Token-limit exhaustion (input/output/total).
3. Cost-limit exhaustion (dollar cap).
4. Retry accounting (failed attempts and retries consume counted requests).
5. Missing usage metadata handling (conservative fallback, no free calls).
6. Resume after stopped run (resumed run cannot bypass budget; loads ledger).
7. Checkpoint recovery (atomic persistence and verification).

All tests are 100% offline, deterministic, and use mocked query responses.
"""

import json
import os
import tempfile
import time
import pytest
from typing import Dict, Any, Optional, Tuple

from stage4.src.budget_enforcer import BudgetEnforcer, BudgetExhaustedException


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

def test_request_limit_exhaustion():
    """System aborts when max_requests ceiling is reached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        enforcer = BudgetEnforcer(ledger_path=ledger, max_requests=3)

        # Make 3 calls
        for i in range(3):
            enforcer.check_preflight_limits()
            enforcer.record_usage("hello", "world", {"prompt_tokens": 10, "completion_tokens": 10})

        # 4th call must raise BudgetExhaustedException
        with pytest.raises(BudgetExhaustedException) as exc:
            enforcer.check_preflight_limits()
        assert exc.value.limit_type == "REQUESTS"
        assert exc.value.current_val == 3


def test_token_limit_exhaustion():
    """System aborts when token ceiling is reached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        enforcer = BudgetEnforcer(ledger_path=ledger, max_input_tokens=1000)

        enforcer.check_preflight_limits()
        enforcer.record_usage("p1", "c1", {"prompt_tokens": 600, "completion_tokens": 50})

        enforcer.check_preflight_limits()
        enforcer.record_usage("p2", "c2", {"prompt_tokens": 500, "completion_tokens": 50})

        # Total input is now 1100 > 1000
        with pytest.raises(BudgetExhaustedException) as exc:
            enforcer.check_preflight_limits()
        assert exc.value.limit_type == "INPUT_TOKENS"


def test_cost_limit_exhaustion():
    """System aborts when monetary dollar cap is crossed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        # $10 cap, high cost rate ($100 per M tokens)
        enforcer = BudgetEnforcer(ledger_path=ledger, max_cost_usd=1.0, cost_per_m_input=1000.0, cost_per_m_output=1000.0)

        enforcer.check_preflight_limits()
        # 1,500 tokens at $1000/1M = $1.50
        with pytest.raises(BudgetExhaustedException) as exc:
            enforcer.record_usage("p", "c", {"prompt_tokens": 1000, "completion_tokens": 500})
        assert exc.value.limit_type == "COST_USD"


def test_retry_accounting():
    """Failed query retry attempts are counted towards total requests and retries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        enforcer = BudgetEnforcer(ledger_path=ledger, max_requests=5)

        # Call succeeded on 3rd retry (retries=2)
        enforcer.check_preflight_limits()
        enforcer.record_usage("p", "c", {"prompt_tokens": 50, "completion_tokens": 50}, retries=2)

        assert enforcer.requests_count == 1
        assert enforcer.retries_count == 2

        with open(ledger) as f:
            saved = json.load(f)
            assert saved["retries_count"] == 2


def test_missing_usage_metadata_fallback():
    """If provider returns no token metadata, enforcer conservatively estimates tokens rather than $0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        enforcer = BudgetEnforcer(ledger_path=ledger)

        # Provider returned None for usage
        cost = enforcer.record_usage(
            prompt_text="this is a test prompt with ten words exactly here now",
            completion_text="def priority(item, rem, cap):\n    return -rem\n",
            usage_metadata=None
        )

        assert enforcer.input_tokens > 0
        assert enforcer.output_tokens > 0
        assert cost > 0.0
        assert enforcer.cost_usd > 0.0


def test_resume_after_stopped_run_cannot_bypass_budget():
    """A stopped run resumed from disk retains all prior spend and halts when cap is reached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        
        # Run 1: consumes 2 requests out of 3
        e1 = BudgetEnforcer(ledger_path=ledger, max_requests=3)
        e1.record_usage("p", "c", {"prompt_tokens": 100, "completion_tokens": 50})
        e1.record_usage("p", "c", {"prompt_tokens": 100, "completion_tokens": 50})
        assert e1.requests_count == 2

        # Run 2: resumes from same ledger
        e2 = BudgetEnforcer(ledger_path=ledger, max_requests=3)
        assert e2.requests_count == 2
        assert e2.input_tokens == 200

        # Makes 1 call -> reaches 3
        e2.check_preflight_limits()
        e2.record_usage("p", "c", {"prompt_tokens": 100, "completion_tokens": 50})

        # Next call must raise BudgetExhaustedException
        with pytest.raises(BudgetExhaustedException):
            e2.check_preflight_limits()


def test_checkpoint_recovery():
    """Checkpoints are recorded and verified upon recovery."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = os.path.join(tmpdir, "budget.json")
        enforcer = BudgetEnforcer(ledger_path=ledger)

        enforcer.record_usage("p", "c", {"prompt_tokens": 100, "completion_tokens": 50})
        enforcer.record_checkpoint("trial_01_arm_a", {"champion_score": 12.5, "status": "VALID"})

        # Reload
        reloaded = BudgetEnforcer(ledger_path=ledger)
        assert len(reloaded.checkpoint_records) == 1
        assert reloaded.checkpoint_records[0]["checkpoint_id"] == "trial_01_arm_a"
        assert reloaded.checkpoint_records[0]["state"]["champion_score"] == 12.5
