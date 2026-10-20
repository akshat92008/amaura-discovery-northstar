"""
Global Budget Ledger (REPRO-4 & P0 2.4 / 3.4)
==============================================
Process-atomic, lock-protected ledger tracking global LLM discovery expenditure
and active budget reservations across multiple processes and pilots.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_LEDGER_PATH: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "budget_ledger.json")
)
DEFAULT_BUDGET_CAP_USD: float = 15.0


class BudgetExceededError(RuntimeError):
    """Raised when an operation would exceed the configured global budget cap."""
    pass


class LedgerCorruptError(RuntimeError):
    """Raised when the persistent budget ledger file is corrupted or unparseable."""
    pass


class GlobalBudgetLedger:
    """
    Process-atomic ledger using POSIX fcntl file locks and reservation lifecycle management.
    Guarantees:
    - Preflight checks reserve budget before run execution begins.
    - Concurrent processes cannot race past the global budget cap.
    - Fails closed on corrupted ledger files.
    """

    def __init__(
        self,
        ledger_path: str = DEFAULT_LEDGER_PATH,
        cap_usd: float = DEFAULT_BUDGET_CAP_USD,
    ) -> None:
        self.ledger_path = os.path.abspath(ledger_path)
        self.lock_path = self.ledger_path + ".lock"
        self.cap_usd = float(cap_usd)
        # Ensure lock directory exists
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        # Initial validation under lock
        with self._lock():
            self._data = self._load_locked()

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        """POSIX inter-process advisory lock (fcntl.flock)."""
        lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o666)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)

    def _load_locked(self) -> Dict[str, Any]:
        """Loads ledger state from disk. Fails closed if the file is corrupted."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        raise LedgerCorruptError(f"Ledger file '{self.ledger_path}' is empty.")
                    data = json.loads(content)
                    if not isinstance(data, dict):
                        raise LedgerCorruptError(f"Ledger file content is not a JSON object: {type(data)}")
                    if "total_spent_usd" not in data or "total_requests" not in data:
                        raise LedgerCorruptError("Ledger file missing required 'total_spent_usd' or 'total_requests'.")
                    if data["total_spent_usd"] < 0 or data["total_requests"] < 0:
                        raise LedgerCorruptError("Ledger contains negative spent amounts or request counts.")
                    data.setdefault("active_reservations", {})
                    data.setdefault("runs", [])
                    return data
            except json.JSONDecodeError as jde:
                raise LedgerCorruptError(f"Corrupted JSON in ledger file '{self.ledger_path}': {jde}") from jde
        return {
            "total_spent_usd": 0.0,
            "total_requests": 0,
            "active_reservations": {},
            "runs": [],
        }

    def _save_atomic_locked(self, data: Dict[str, Any]) -> None:
        """Atomically saves ledger state to disk via mkstemp + replace while holding lock."""
        dir_name = os.path.dirname(self.ledger_path)
        os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            os.replace(tmp_path, self.ledger_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @property
    def total_spent_usd(self) -> float:
        with self._lock():
            data = self._load_locked()
            return float(data.get("total_spent_usd", 0.0))

    @property
    def total_requests(self) -> int:
        with self._lock():
            data = self._load_locked()
            return int(data.get("total_requests", 0))

    @property
    def total_reserved_usd(self) -> float:
        with self._lock():
            data = self._load_locked()
            reservations = data.get("active_reservations", {})
            return round(sum(float(r.get("reserved_usd", 0.0)) for r in reservations.values()), 6)

    @property
    def remaining_usd(self) -> float:
        """Unspent budget disregarding reservations."""
        return max(0.0, self.cap_usd - self.total_spent_usd)

    @property
    def remaining_unreserved_usd(self) -> float:
        """Unspent and unreserved budget available for new runs."""
        with self._lock():
            data = self._load_locked()
            spent = float(data.get("total_spent_usd", 0.0))
            reservations = data.get("active_reservations", {})
            reserved = sum(float(r.get("reserved_usd", 0.0)) for r in reservations.values())
            return max(0.0, round(self.cap_usd - (spent + reserved), 6))

    def preflight_check(self, worst_case_cost_usd: float) -> bool:
        """
        Returns True if the estimated worst-case run cost fits within remaining unreserved budget.
        """
        with self._lock():
            data = self._load_locked()
            spent = float(data.get("total_spent_usd", 0.0))
            reservations = data.get("active_reservations", {})
            reserved = sum(float(r.get("reserved_usd", 0.0)) for r in reservations.values())
            return (spent + reserved + worst_case_cost_usd) <= self.cap_usd

    def reserve_budget(
        self,
        run_id: str,
        estimated_cost_usd: float,
        max_requests: int = 0,
    ) -> str:
        """
        Atomically reserves an estimated budget amount before run commencement (P0 2.4, 3.4).
        Returns a unique reservation token to be reconciled on run completion.
        """
        if estimated_cost_usd <= 0:
            raise ValueError(f"Estimated reservation cost must be positive, got {estimated_cost_usd}")

        with self._lock():
            data = self._load_locked()
            spent = float(data.get("total_spent_usd", 0.0))
            reservations = data.get("active_reservations", {})
            reserved = sum(float(r.get("reserved_usd", 0.0)) for r in reservations.values())
            available = self.cap_usd - (spent + reserved)

            if estimated_cost_usd > available:
                raise BudgetExceededError(
                    f"Insufficient unreserved budget: requested ${estimated_cost_usd:.4f}, "
                    f"available unreserved ${max(0.0, available):.4f} (spent: ${spent:.4f}, reserved: ${reserved:.4f}, cap: ${self.cap_usd:.4f})"
                )

            token = f"res_{uuid.uuid4().hex[:12]}"
            reservations[token] = {
                "run_id": run_id,
                "reserved_usd": round(estimated_cost_usd, 6),
                "max_requests": max_requests,
                "timestamp": time.time(),
            }
            data["active_reservations"] = reservations
            self._save_atomic_locked(data)
            return token

    def reconcile_reservation(
        self,
        reservation_token: str,
        actual_cost_usd: float,
        actual_requests: int,
    ) -> None:
        """
        Settles an active budget reservation: releases reserved amount and records actual spend.
        """
        with self._lock():
            data = self._load_locked()
            reservations = data.get("active_reservations", {})
            if reservation_token not in reservations:
                raise KeyError(f"Unknown or already settled reservation token: '{reservation_token}'")

            res_info = reservations.pop(reservation_token)
            run_id = res_info.get("run_id", "unknown")
            data["total_spent_usd"] = round(data.get("total_spent_usd", 0.0) + actual_cost_usd, 6)
            data["total_requests"] = data.get("total_requests", 0) + actual_requests
            data.setdefault("runs", []).append({
                "run_id": run_id,
                "token": reservation_token,
                "cost_usd": round(actual_cost_usd, 6),
                "requests": actual_requests,
                "settled_at": time.time(),
            })
            self._save_atomic_locked(data)

    def release_reservation(self, reservation_token: str) -> None:
        """
        Releases an active budget reservation without charging any spend (e.g. on cancelled run).
        """
        with self._lock():
            data = self._load_locked()
            reservations = data.get("active_reservations", {})
            if reservation_token in reservations:
                reservations.pop(reservation_token)
                self._save_atomic_locked(data)

    def record_spend(self, run_id: str, cost_usd: float, requests: int) -> None:
        """
        Direct spend recording (convenience for non-reservation workflows).
        """
        with self._lock():
            data = self._load_locked()
            new_spent = round(data.get("total_spent_usd", 0.0) + cost_usd, 6)
            reservations = data.get("active_reservations", {})
            reserved = sum(float(r.get("reserved_usd", 0.0)) for r in reservations.values())

            if (new_spent + reserved) > self.cap_usd:
                raise BudgetExceededError(
                    f"Direct spend of ${cost_usd:.4f} would exceed remaining budget "
                    f"(cap: ${self.cap_usd:.4f}, spent: ${new_spent:.4f})"
                )

            data["total_spent_usd"] = new_spent
            data["total_requests"] = data.get("total_requests", 0) + requests
            data.setdefault("runs", []).append({
                "run_id": run_id,
                "cost_usd": round(cost_usd, 6),
                "requests": requests,
                "recorded_at": time.time(),
            })
            self._save_atomic_locked(data)
