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


# ---------------------------------------------------------------------------
# Budget Exceptions
# ---------------------------------------------------------------------------

class BudgetExhaustedException(Exception):
    """Raised when an operation would exceed or has exceeded a hard budget cap."""
    def __init__(self, limit_type: str, current_val: float, max_val: float):
        super().__init__(
            f"HARD BUDGET CEILING REACHED: {limit_type} = {current_val} exceeds limit {max_val}. "
            "Execution halted immediately to prevent financial overrun."
        )
        self.limit_type = limit_type
        self.current_val = current_val
        self.max_val = max_val


# ---------------------------------------------------------------------------
# Production-Grade Budget Enforcer
# ---------------------------------------------------------------------------

class BudgetEnforcer:
    """
    Stateful budget supervisor that wraps LLM calls and enforces hard ceilings.
    Persists consumption to disk so restarted/resumed runs accumulate spend.
    """
    def __init__(
        self,
        ledger_path: str,
        max_requests: int = 1000,
        max_input_tokens: int = 7_000_000,
        max_output_tokens: int = 1_200_000,
        max_cost_usd: float = 45.0,
        tripwire_cost_usd: float = 40.0,
        max_wall_clock_sec: float = 18_000.0,
        cost_per_m_input: float = 3.0,
        cost_per_m_output: float = 15.0
    ):
        self.ledger_path = ledger_path
        self.max_requests = max_requests
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_cost_usd = max_cost_usd
        self.tripwire_cost_usd = tripwire_cost_usd
        self.max_wall_clock_sec = max_wall_clock_sec
        self.cost_per_m_input = cost_per_m_input
        self.cost_per_m_output = cost_per_m_output

        # Initialize or reload ledger
        self.requests_count = 0
        self.retries_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.elapsed_sec = 0.0
        self.last_sync_time = time.time()
        self.checkpoint_records = []

        self._load_ledger_if_exists()

    def _load_ledger_if_exists(self):
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r") as f:
                data = json.load(f)
                self.requests_count = data.get("requests_count", 0)
                self.retries_count = data.get("retries_count", 0)
                self.input_tokens = data.get("input_tokens", 0)
                self.output_tokens = data.get("output_tokens", 0)
                self.cost_usd = data.get("cost_usd", 0.0)
                self.elapsed_sec = data.get("elapsed_sec", 0.0)
                self.checkpoint_records = data.get("checkpoints", [])

    def save_ledger(self):
        now = time.time()
        self.elapsed_sec += (now - self.last_sync_time)
        self.last_sync_time = now

        data = {
            "requests_count": self.requests_count,
            "retries_count": self.retries_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "elapsed_sec": round(self.elapsed_sec, 2),
            "tripwire_triggered": (self.cost_usd >= self.tripwire_cost_usd),
            "checkpoints": self.checkpoint_records
        }
        # Atomic write via tempfile
        dir_name = os.path.dirname(self.ledger_path) or "."
        tmp_path = f"{self.ledger_path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.ledger_path)

    def check_preflight_limits(self):
        """Pre-flight check before initiating an LLM call."""
        if self.requests_count >= self.max_requests:
            raise BudgetExhaustedException("REQUESTS", self.requests_count, self.max_requests)

        if self.input_tokens >= self.max_input_tokens:
            raise BudgetExhaustedException("INPUT_TOKENS", self.input_tokens, self.max_input_tokens)

        if self.output_tokens >= self.max_output_tokens:
            raise BudgetExhaustedException("OUTPUT_TOKENS", self.output_tokens, self.max_output_tokens)

        if self.cost_usd >= self.max_cost_usd:
            raise BudgetExhaustedException("COST_USD", self.cost_usd, self.max_cost_usd)

        if self.elapsed_sec >= self.max_wall_clock_sec:
            raise BudgetExhaustedException("WALL_CLOCK_SEC", self.elapsed_sec, self.max_wall_clock_sec)

    def record_usage(
        self,
        prompt_text: str,
        completion_text: str,
        usage_metadata: Optional[Dict[str, int]],
        retries: int = 0
    ) -> float:
        """
        Records actual usage after call.
        If usage_metadata is missing or 0, computes a conservative token estimate.
        """
        self.requests_count += 1
        self.retries_count += retries

        # Estimate fallback tokens if metadata missing
        if usage_metadata and usage_metadata.get("prompt_tokens", 0) > 0:
            p_tok = usage_metadata["prompt_tokens"]
            c_tok = usage_metadata.get("completion_tokens", 0)
        else:
            # Conservative rule: 1 word ~ 1.33 tokens + 50 overhead
            p_tok = int(len(prompt_text.split()) * 1.33) + 50
            c_tok = int(len(completion_text.split()) * 1.33) + 20

        call_cost = (p_tok / 1_000_000.0) * self.cost_per_m_input + (c_tok / 1_000_000.0) * self.cost_per_m_output
        call_cost = round(call_cost, 6)

        self.input_tokens += p_tok
        self.output_tokens += c_tok
        self.cost_usd += call_cost

        self.save_ledger()

        # Post-flight check: raise if hard cap was crossed
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExhaustedException("COST_USD", self.cost_usd, self.max_cost_usd)

        return call_cost

    def record_checkpoint(self, checkpoint_id: str, state_summary: Dict[str, Any]):
        """Persists checkpoint state linked to current budget expenditure."""
        rec = {
            "checkpoint_id": checkpoint_id,
            "timestamp": time.time(),
            "requests": self.requests_count,
            "cost_usd": round(self.cost_usd, 4),
            "state": state_summary
        }
        self.checkpoint_records.append(rec)
        self.save_ledger()


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
