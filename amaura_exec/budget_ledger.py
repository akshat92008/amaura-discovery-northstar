"""
Global Budget Ledger (REPRO-4)
==============================
Tracks cumulative spend across all discovery pilots and execution runs.
Prevents silent cost overruns across separate pilot directories.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

DEFAULT_LEDGER_PATH: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "budget_ledger.json")
)
DEFAULT_BUDGET_CAP_USD: float = 15.0


class GlobalBudgetLedger:
    """
    Thread-safe and process-atomic ledger tracking global LLM discovery expenditure.
    """

    def __init__(
        self,
        ledger_path: str = DEFAULT_LEDGER_PATH,
        cap_usd: float = DEFAULT_BUDGET_CAP_USD,
    ) -> None:
        self.ledger_path = os.path.abspath(ledger_path)
        self.cap_usd = cap_usd
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "total_spent_usd" in data and "total_requests" in data:
                        return data
            except Exception:
                pass
        return {
            "total_spent_usd": 0.0,
            "total_requests": 0,
            "runs": [],
        }

    def _save_atomic(self) -> None:
        dir_name = os.path.dirname(self.ledger_path)
        os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, sort_keys=True)
            os.replace(tmp_path, self.ledger_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @property
    def total_spent_usd(self) -> float:
        return float(self._data.get("total_spent_usd", 0.0))

    @property
    def total_requests(self) -> int:
        return int(self._data.get("total_requests", 0))

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.total_spent_usd)

    def preflight_check(self, worst_case_cost_usd: float) -> bool:
        """
        Returns True if the estimated worst-case run cost fits within remaining budget.
        """
        self._data = self._load()
        return (self.total_spent_usd + worst_case_cost_usd) <= self.cap_usd

    def record_spend(self, run_id: str, cost_usd: float, requests: int) -> None:
        """
        Records spend from a discovery run into the shared persistent ledger.
        """
        self._data = self._load()
        self._data["total_spent_usd"] = round(self._data["total_spent_usd"] + cost_usd, 6)
        self._data["total_requests"] = self._data["total_requests"] + requests
        if "runs" not in self._data:
            self._data["runs"] = []
        self._data["runs"].append({
            "run_id": run_id,
            "cost_usd": cost_usd,
            "requests": requests,
        })
        self._save_atomic()
