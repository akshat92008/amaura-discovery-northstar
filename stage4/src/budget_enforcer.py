"""
Stage 4 Hard Budget Enforcement & Ledger Management
===================================================
Enforces unbreachable resource limits wrapping all LLM calls:
1. Pre-flight check before initiating HTTP requests (aborts if limit reached).
2. Atomic disk ledger persistence (accumulates across interrupted/resumed runs).
3. Thread-safe execution via re-entrant locks.
4. Retry accounting (failed attempts and retries increment counted requests and costs).
5. Conservative fallback token estimation if provider omits usage metadata.
6. Tripwire warning and graceful wind-down when approaching limits.
"""

import contextlib
import fcntl
import json
import math
import os
import threading
import time
from typing import Dict, Any, Optional, List


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


class CorruptedLedgerException(RuntimeError):
    """Raised when the budget ledger file is unreadable, corrupted, or schema-invalid."""
    pass


# NOTE ON SPENDING ENFORCEMENT & BILLING BOUNDS:
# BudgetEnforcer is a local client-side software estimation and request-limiting guard.
# It tracks and bounds local requests, estimated/reported tokens, and estimated cost.
# It does NOT constitute a remote provider-enforced billing cap. Provider-side
# quota limits and credit spending hard-limits must be configured in the model provider console.


class BudgetEnforcer:
    """
    Thread-safe and cross-process safe budget supervisor that wraps LLM calls
    and enforces hard ceilings with atomic reservations to prevent check-then-request races.
    Persists consumption to disk so restarted/resumed runs accumulate spend.
    """
    def __init__(
        self,
        ledger_path: str,
        max_requests: int = 1000,
        max_input_tokens: int = 7_000_000,
        max_output_tokens: int = 1_200_000,
        max_cost_usd: float = 45.0,
        tripwire_cost_usd: Optional[float] = None,
        max_wall_clock_sec: float = 18_000.0,
        cost_per_m_input: float = 3.0,
        cost_per_m_output: float = 15.0
    ):
        if tripwire_cost_usd is None:
            tripwire_cost_usd = round(max_cost_usd * 0.8, 4)
        # Fail closed on missing, non-numeric, non-positive, or non-finite parameters
        for param_name, param_val in [
            ("max_requests", max_requests),
            ("max_input_tokens", max_input_tokens),
            ("max_output_tokens", max_output_tokens),
            ("max_cost_usd", max_cost_usd),
            ("tripwire_cost_usd", tripwire_cost_usd),
            ("max_wall_clock_sec", max_wall_clock_sec),
            ("cost_per_m_input", cost_per_m_input),
            ("cost_per_m_output", cost_per_m_output),
        ]:
            if (
                param_val is None
                or not isinstance(param_val, (int, float))
                or not math.isfinite(param_val)
                or param_val <= 0
            ):
                raise ValueError(
                    f"INVALID_BUDGET_PARAMETER: '{param_name}' must be a positive finite number, got {param_val}."
                )

        if tripwire_cost_usd > max_cost_usd:
            raise ValueError(
                f"INVALID_BUDGET_PARAMETER: 'tripwire_cost_usd' ({tripwire_cost_usd}) cannot exceed 'max_cost_usd' ({max_cost_usd})."
            )

        self.ledger_path = ledger_path
        self.lock_path = f"{ledger_path}.lock"
        self.max_requests = int(max_requests)
        self.max_input_tokens = int(max_input_tokens)
        self.max_output_tokens = int(max_output_tokens)
        self.max_cost_usd = float(max_cost_usd)
        self.tripwire_cost_usd = float(tripwire_cost_usd)
        self.max_wall_clock_sec = float(max_wall_clock_sec)
        self.cost_per_m_input = float(cost_per_m_input)
        self.cost_per_m_output = float(cost_per_m_output)

        # Configurable pricing provenance metadata
        self.pricing_source = "NVIDIA API Catalog / OmniRoute (nemotron-3-super-120b-a12b)"
        self.pricing_last_verified = "2026-10-14"

        self._lock = threading.RLock()
        self._file_lock_depth = 0
        self._lock_file = None

        # Telemetry counters
        self.requests_count = 0
        self.retries_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.actual_reported_cost_usd = 0.0
        self.estimated_cost_usd = 0.0
        self.elapsed_sec = 0.0
        self.last_sync_time = time.time()
        self.stop_reason: Optional[str] = None
        self.checkpoint_records: List[Dict[str, Any]] = []

        # Atomic active reservations to eliminate check-then-request race conditions
        self.active_reservations: Dict[str, Dict[str, Any]] = {}
        self.settled_reservations: Dict[str, float] = {}
        self.reserved_requests = 0
        self.reserved_input_tokens = 0
        self.reserved_output_tokens = 0
        self.reserved_cost_usd = 0.0

        self._load_ledger_if_exists()

    @contextlib.contextmanager
    def _file_lock(self):
        """Re-entrant cross-process advisory lock to prevent deadlock within same process."""
        with self._lock:
            if self._file_lock_depth > 0:
                self._file_lock_depth += 1
                try:
                    yield
                finally:
                    self._file_lock_depth -= 1
                return

            dir_name = os.path.dirname(self.lock_path) or "."
            os.makedirs(dir_name, exist_ok=True)
            f_lock = open(self.lock_path, "w")
            fcntl.flock(f_lock.fileno(), fcntl.LOCK_EX)
            self._file_lock_depth = 1
            self._lock_file = f_lock
            try:
                yield
            finally:
                self._file_lock_depth = 0
                try:
                    fcntl.flock(f_lock.fileno(), fcntl.LOCK_UN)
                    f_lock.close()
                except Exception:
                    pass
                self._lock_file = None

    def _recalculate_reserved_totals(self):
        """Recalculates reserved totals from active reservations dictionary."""
        self.reserved_requests = len(self.active_reservations)
        self.reserved_input_tokens = sum(r.get("prompt_tokens", 0) for r in self.active_reservations.values())
        self.reserved_output_tokens = sum(r.get("output_tokens", 0) for r in self.active_reservations.values())
        self.reserved_cost_usd = round(sum(r.get("worst_case_cost", 0.0) for r in self.active_reservations.values()), 6)

    def _backup_corrupted_ledger(self):
        """Preserves a recoverable copy of corrupted ledger before raising exception."""
        if not os.path.exists(self.ledger_path):
            return
        ts = int(time.time())
        backup_path = f"{self.ledger_path}.corrupted.{ts}"
        try:
            with open(self.ledger_path, "rb") as src, open(backup_path, "wb") as dst:
                dst.write(src.read())
        except Exception:
            pass

    def _load_ledger_if_exists(self):
        with self._file_lock():
            if not os.path.exists(self.ledger_path):
                return

            if os.path.getsize(self.ledger_path) == 0:
                self._backup_corrupted_ledger()
                raise CorruptedLedgerException(
                    f"CORRUPTED BUDGET LEDGER: Ledger file at '{self.ledger_path}' is empty (0 bytes). Backup created."
                )

            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                self._backup_corrupted_ledger()
                raise CorruptedLedgerException(
                    f"CORRUPTED BUDGET LEDGER: Failed to parse JSON from '{self.ledger_path}': {e}. Backup created."
                )

            if not isinstance(data, dict):
                self._backup_corrupted_ledger()
                raise CorruptedLedgerException(
                    f"CORRUPTED BUDGET LEDGER: Root JSON structure must be a dict, got {type(data).__name__} in '{self.ledger_path}'."
                )

            # Validate required numeric fields
            required_numeric = [
                "requests_count",
                "retries_count",
                "input_tokens",
                "output_tokens",
                "cost_usd",
                "elapsed_sec"
            ]
            for fld in required_numeric:
                if fld not in data:
                    self._backup_corrupted_ledger()
                    raise CorruptedLedgerException(
                        f"CORRUPTED BUDGET LEDGER: Missing required numeric field '{fld}' in '{self.ledger_path}'."
                    )
                val = data[fld]
                if not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
                    self._backup_corrupted_ledger()
                    raise CorruptedLedgerException(
                        f"CORRUPTED BUDGET LEDGER: Field '{fld}' must be a non-negative finite number, got {val} in '{self.ledger_path}'."
                    )

            # Validate collections if present
            if "checkpoints" in data and not isinstance(data["checkpoints"], list):
                self._backup_corrupted_ledger()
                raise CorruptedLedgerException(f"CORRUPTED BUDGET LEDGER: 'checkpoints' must be a list in '{self.ledger_path}'.")
            if "active_reservations" in data and not isinstance(data["active_reservations"], dict):
                self._backup_corrupted_ledger()
                raise CorruptedLedgerException(f"CORRUPTED BUDGET LEDGER: 'active_reservations' must be a dict in '{self.ledger_path}'.")
            if "settled_reservations" in data and not isinstance(data["settled_reservations"], dict):
                self._backup_corrupted_ledger()
                raise CorruptedLedgerException(f"CORRUPTED BUDGET LEDGER: 'settled_reservations' must be a dict in '{self.ledger_path}'.")

            self.requests_count = data["requests_count"]
            self.retries_count = data["retries_count"]
            self.input_tokens = data["input_tokens"]
            self.output_tokens = data["output_tokens"]
            self.cost_usd = float(data["cost_usd"])
            self.actual_reported_cost_usd = float(data.get("actual_reported_cost_usd", 0.0))
            self.estimated_cost_usd = float(data.get("estimated_cost_usd", 0.0))
            self.elapsed_sec = float(data["elapsed_sec"])
            self.stop_reason = data.get("stop_reason")
            self.checkpoint_records = data.get("checkpoints", [])
            self.active_reservations = data.get("active_reservations", {})
            self.settled_reservations = data.get("settled_reservations", {})
            self._recalculate_reserved_totals()

    def save_ledger(self):
        with self._file_lock():
            now = time.time()
            self.elapsed_sec += (now - self.last_sync_time)
            self.last_sync_time = now

            self._recalculate_reserved_totals()

            data = {
                "requests_count": self.requests_count,
                "retries_count": self.retries_count,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost_usd, 6),
                "actual_reported_cost_usd": round(self.actual_reported_cost_usd, 6),
                "estimated_cost_usd": round(self.estimated_cost_usd, 6),
                "reserved_requests": self.reserved_requests,
                "reserved_cost_usd": self.reserved_cost_usd,
                "active_reservations": self.active_reservations,
                "settled_reservations": self.settled_reservations,
                "elapsed_sec": round(self.elapsed_sec, 2),
                "tripwire_triggered": (self.cost_usd >= self.tripwire_cost_usd),
                "stop_reason": self.stop_reason,
                "checkpoints": self.checkpoint_records,
                "pricing_metadata": {
                    "cost_per_m_input": self.cost_per_m_input,
                    "cost_per_m_output": self.cost_per_m_output,
                    "pricing_source": self.pricing_source,
                    "pricing_last_verified": self.pricing_last_verified
                }
            }
            # Atomic disk write via temporary file
            dir_name = os.path.dirname(self.ledger_path) or "."
            os.makedirs(dir_name, exist_ok=True)
            tmp_path = f"{self.ledger_path}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.ledger_path)

    def check_preflight_limits(self):
        """Pre-flight check before initiating an LLM call. Fails closed."""
        with self._file_lock():
            self._load_ledger_if_exists()

            total_requests = self.requests_count + self.retries_count + self.reserved_requests
            if total_requests >= self.max_requests:
                self.stop_reason = f"REQUESTS_LIMIT_EXCEEDED ({total_requests} >= {self.max_requests})"
                self.save_ledger()
                raise BudgetExhaustedException("REQUESTS", total_requests, self.max_requests)

            total_input = self.input_tokens + self.reserved_input_tokens
            if total_input >= self.max_input_tokens:
                self.stop_reason = f"INPUT_TOKENS_LIMIT_EXCEEDED ({total_input} >= {self.max_input_tokens})"
                self.save_ledger()
                raise BudgetExhaustedException("INPUT_TOKENS", total_input, self.max_input_tokens)

            total_output = self.output_tokens + self.reserved_output_tokens
            if total_output >= self.max_output_tokens:
                self.stop_reason = f"OUTPUT_TOKENS_LIMIT_EXCEEDED ({total_output} >= {self.max_output_tokens})"
                self.save_ledger()
                raise BudgetExhaustedException("OUTPUT_TOKENS", total_output, self.max_output_tokens)

            total_cost = round(self.cost_usd + self.reserved_cost_usd, 6)
            if total_cost >= self.max_cost_usd:
                self.stop_reason = f"COST_USD_LIMIT_EXCEEDED ({total_cost} >= {self.max_cost_usd})"
                self.save_ledger()
                raise BudgetExhaustedException("COST_USD", total_cost, self.max_cost_usd)

            if self.elapsed_sec >= self.max_wall_clock_sec:
                self.stop_reason = f"WALL_CLOCK_LIMIT_EXCEEDED ({self.elapsed_sec} >= {self.max_wall_clock_sec})"
                self.save_ledger()
                raise BudgetExhaustedException("WALL_CLOCK_SEC", self.elapsed_sec, self.max_wall_clock_sec)

            self.stop_reason = None

    def reserve_allowance(self, estimated_prompt_tokens: int, max_output_tokens: int = 4096) -> str:
        """
        Atomically checks limits and reserves worst-case request allowances BEFORE any network transmission.
        Eliminates check-then-request race conditions across concurrent callers and processes.
        Returns a unique reservation_id to be finalized post-flight.
        """
        with self._file_lock():
            self._load_ledger_if_exists()

            worst_case_cost = (
                (estimated_prompt_tokens / 1_000_000.0) * self.cost_per_m_input
                + (max_output_tokens / 1_000_000.0) * self.cost_per_m_output
            )
            worst_case_cost = round(worst_case_cost, 6)

            # Check request ceiling
            total_requests = self.requests_count + self.retries_count + self.reserved_requests + 1
            if total_requests > self.max_requests:
                self.stop_reason = f"REQUESTS_LIMIT_EXCEEDED ({total_requests} > {self.max_requests})"
                self.save_ledger()
                raise BudgetExhaustedException("REQUESTS", total_requests, self.max_requests)

            # Check input token ceiling
            total_input = self.input_tokens + self.reserved_input_tokens + estimated_prompt_tokens
            if total_input > self.max_input_tokens:
                self.stop_reason = f"INPUT_TOKENS_LIMIT_EXCEEDED ({total_input} > {self.max_input_tokens})"
                self.save_ledger()
                raise BudgetExhaustedException("INPUT_TOKENS", total_input, self.max_input_tokens)

            # Check output token ceiling
            total_output = self.output_tokens + self.reserved_output_tokens + max_output_tokens
            if total_output > self.max_output_tokens:
                self.stop_reason = f"OUTPUT_TOKENS_LIMIT_EXCEEDED ({total_output} > {self.max_output_tokens})"
                self.save_ledger()
                raise BudgetExhaustedException("OUTPUT_TOKENS", total_output, self.max_output_tokens)

            # Check cost ceiling
            total_cost = round(self.cost_usd + self.reserved_cost_usd + worst_case_cost, 6)
            if total_cost > self.max_cost_usd:
                self.stop_reason = f"COST_USD_LIMIT_EXCEEDED ({total_cost} > {self.max_cost_usd})"
                self.save_ledger()
                raise BudgetExhaustedException("COST_USD", total_cost, self.max_cost_usd)

            # Reservation succeeded: record reservation atomically
            res_id = f"res_{os.getpid()}_{time.time_ns()}_{len(self.active_reservations)}"
            self.active_reservations[res_id] = {
                "prompt_tokens": estimated_prompt_tokens,
                "output_tokens": max_output_tokens,
                "worst_case_cost": worst_case_cost,
                "timestamp": time.time()
            }
            self.stop_reason = None
            self._recalculate_reserved_totals()
            self.save_ledger()
            return res_id

    def finalize_reservation(
        self,
        reservation_id: str,
        prompt_text: str,
        completion_text: str = "",
        usage_metadata: Optional[Dict[str, int]] = None,
        is_error: bool = False,
        is_timeout: bool = False,
        is_final: bool = True,
        is_retry: bool = False
    ) -> float:
        """
        Atomically settles an active reservation into committed ledger spend post-flight.
        Releases reserved budget and commits actual/conservative fallback tokens.
        Guarantees idempotency (repeated settlements of same reservation return previously recorded cost
        without double-counting).
        """
        with self._file_lock():
            self._load_ledger_if_exists()

            # 1. Idempotency guard: if already settled, return committed cost without double charging
            if reservation_id in self.settled_reservations:
                return self.settled_reservations[reservation_id]

            # 2. Untracked reservation guard: prevent settling unreserved requests
            if reservation_id not in self.active_reservations:
                raise ValueError(
                    f"UNTRACKED_RESERVATION: Cannot finalize unknown or unreserved reservation '{reservation_id}'."
                )

            res_data = self.active_reservations[reservation_id]
            reserved_output = res_data.get("output_tokens", 4096)

            # Compute actual or conservative tokens
            is_actual = False
            if usage_metadata and (usage_metadata.get("prompt_tokens", 0) > 0 or usage_metadata.get("prompt_token_count", 0) > 0):
                p_tok = usage_metadata.get("prompt_tokens") or usage_metadata.get("prompt_token_count", 0)
                c_tok = usage_metadata.get("completion_tokens") or usage_metadata.get("candidates_token_count", 0)
                is_actual = True
            elif is_timeout:
                # Conservative remote timeout charge: remote server received request and generated full output
                p_tok = int(len(prompt_text.split()) * 1.33) + 50
                c_tok = reserved_output
            elif is_error and not completion_text:
                # Network dropped before server response received
                p_tok = int(len(prompt_text.split()) * 1.33) + 50
                c_tok = 0
            else:
                p_tok = int(len(prompt_text.split()) * 1.33) + 50
                c_tok = int(len(completion_text.split()) * 1.33) + 20 if completion_text else reserved_output

            call_cost = (p_tok / 1_000_000.0) * self.cost_per_m_input + (c_tok / 1_000_000.0) * self.cost_per_m_output
            call_cost = round(call_cost, 6)

            # 3. Atomic transition: remove from active, add to settled
            del self.active_reservations[reservation_id]
            self.settled_reservations[reservation_id] = call_cost
            self._recalculate_reserved_totals()

            if is_retry:
                self.retries_count += 1
            self.requests_count += 1

            self.input_tokens += p_tok
            self.output_tokens += c_tok
            self.cost_usd = round(self.cost_usd + call_cost, 6)

            if is_actual:
                self.actual_reported_cost_usd = round(self.actual_reported_cost_usd + call_cost, 6)
            else:
                self.estimated_cost_usd = round(self.estimated_cost_usd + call_cost, 6)

            self.save_ledger()

            if self.cost_usd > self.max_cost_usd:
                self.stop_reason = f"COST_USD_OVERRUN ({self.cost_usd} > {self.max_cost_usd})"
                self.save_ledger()
                raise BudgetExhaustedException("COST_USD", self.cost_usd, self.max_cost_usd)

            return call_cost


    def is_tripwire_triggered(self) -> bool:
        """Returns True if spend has crossed the software tripwire."""
        with self._lock:
            return self.cost_usd >= self.tripwire_cost_usd

    def record_retry_attempt(self):
        """Records an HTTP retry attempt immediately to enforce hard request limits across process boundaries."""
        with self._file_lock():
            self._load_ledger_if_exists()
            self.retries_count += 1
            self.save_ledger()

    def record_usage(
        self,
        prompt_text: str,
        completion_text: str,
        usage_metadata: Optional[Dict[str, int]],
        retries: int = 0
    ) -> float:
        """
        Records actual usage after call (preserved for direct / legacy caller compatibility).
        If usage_metadata is missing or 0, computes a conservative token estimate.
        """
        with self._file_lock():
            self._load_ledger_if_exists()
            self.requests_count += 1
            if retries > 0 and self.retries_count == 0:
                self.retries_count += retries

            is_actual = False
            if usage_metadata and usage_metadata.get("prompt_tokens", 0) > 0:
                p_tok = usage_metadata["prompt_tokens"]
                c_tok = usage_metadata.get("completion_tokens", 0)
                is_actual = True
            else:
                p_tok = int(len(prompt_text.split()) * 1.33) + 50
                if usage_metadata and "completion_tokens" in usage_metadata:
                    c_tok = usage_metadata["completion_tokens"]
                elif completion_text:
                    c_tok = int(len(completion_text.split()) * 1.33) + 20
                else:
                    c_tok = 4096

            call_cost = (p_tok / 1_000_000.0) * self.cost_per_m_input + (c_tok / 1_000_000.0) * self.cost_per_m_output
            call_cost = round(call_cost, 6)

            self.input_tokens += p_tok
            self.output_tokens += c_tok
            self.cost_usd = round(self.cost_usd + call_cost, 6)

            if is_actual:
                self.actual_reported_cost_usd = round(self.actual_reported_cost_usd + call_cost, 6)
            else:
                self.estimated_cost_usd = round(self.estimated_cost_usd + call_cost, 6)

            self.save_ledger()

            if self.cost_usd > self.max_cost_usd:
                self.stop_reason = f"COST_USD_OVERRUN ({self.cost_usd} > {self.max_cost_usd})"
                self.save_ledger()
                raise BudgetExhaustedException("COST_USD", self.cost_usd, self.max_cost_usd)

            return call_cost

    def record_checkpoint(self, checkpoint_id: str, state_summary: Dict[str, Any]):
        """Persists checkpoint state linked to current budget expenditure."""
        with self._file_lock():
            rec = {
                "checkpoint_id": checkpoint_id,
                "timestamp": time.time(),
                "requests": self.requests_count,
                "cost_usd": round(self.cost_usd, 4),
                "state": state_summary
            }
            self.checkpoint_records.append(rec)
            self.save_ledger()

    def get_summary(self) -> Dict[str, Any]:
        with self._file_lock():
            self._load_ledger_if_exists()
            return {
                "requests_count": self.requests_count,
                "retries_count": self.retries_count,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost_usd, 6),
                "actual_reported_cost_usd": round(self.actual_reported_cost_usd, 6),
                "estimated_cost_usd": round(self.estimated_cost_usd, 6),
                "reserved_requests": self.reserved_requests,
                "reserved_cost_usd": self.reserved_cost_usd,
                "settled_reservations_count": len(self.settled_reservations),
                "elapsed_sec": round(self.elapsed_sec, 2),
                "tripwire_triggered": (self.cost_usd >= self.tripwire_cost_usd),
                "stop_reason": self.stop_reason,
                "pricing_source": self.pricing_source,
                "pricing_last_verified": self.pricing_last_verified
            }

