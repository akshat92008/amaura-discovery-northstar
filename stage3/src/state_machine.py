"""
Stage 3: Experiment State Machine & Technical Hidden Firewall
============================================================
Enforces:
1. Formal state transitions:
   DRAFT -> AUDIT -> IMPLEMENTATION_VERIFIED -> PILOT_READY -> PILOT_RUNNING ->
   PILOT_COMPLETE -> PROTOCOL_FROZEN -> MAIN_RUNNING -> SELECTIONS_FROZEN ->
   HIDDEN_RUNNING -> ANALYSIS_COMPLETE

2. Technical Hidden Firewall:
   Access to hidden benchmarks is strictly blocked until the state reaches SELECTIONS_FROZEN.
   Any premature attempt raises PermissionError and writes an immediate violation record to the audit log.
"""

import datetime
import json
import os
from enum import Enum
from typing import Dict, Any, List, Optional


class ExperimentState(str, Enum):
    DRAFT = "DRAFT"
    AUDIT = "AUDIT"
    IMPLEMENTATION_VERIFIED = "IMPLEMENTATION_VERIFIED"
    PILOT_READY = "PILOT_READY"
    PILOT_RUNNING = "PILOT_RUNNING"
    PILOT_COMPLETE = "PILOT_COMPLETE"
    PROTOCOL_FROZEN = "PROTOCOL_FROZEN"
    MAIN_RUNNING = "MAIN_RUNNING"
    SELECTIONS_FROZEN = "SELECTIONS_FROZEN"
    HIDDEN_RUNNING = "HIDDEN_RUNNING"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"


VALID_TRANSITIONS = {
    ExperimentState.DRAFT: {ExperimentState.AUDIT},
    ExperimentState.AUDIT: {ExperimentState.IMPLEMENTATION_VERIFIED, ExperimentState.DRAFT},
    ExperimentState.IMPLEMENTATION_VERIFIED: {ExperimentState.PILOT_READY, ExperimentState.DRAFT},
    ExperimentState.PILOT_READY: {ExperimentState.PILOT_RUNNING, ExperimentState.IMPLEMENTATION_VERIFIED},
    ExperimentState.PILOT_RUNNING: {ExperimentState.PILOT_COMPLETE, ExperimentState.PILOT_READY},
    ExperimentState.PILOT_COMPLETE: {ExperimentState.PROTOCOL_FROZEN, ExperimentState.PILOT_READY},
    ExperimentState.PROTOCOL_FROZEN: {ExperimentState.MAIN_RUNNING},
    ExperimentState.MAIN_RUNNING: {ExperimentState.SELECTIONS_FROZEN},
    ExperimentState.SELECTIONS_FROZEN: {ExperimentState.HIDDEN_RUNNING},
    ExperimentState.HIDDEN_RUNNING: {ExperimentState.ANALYSIS_COMPLETE},
    ExperimentState.ANALYSIS_COMPLETE: {ExperimentState.PROTOCOL_FROZEN}
}


class StateMachine:
    def __init__(
        self,
        state_file: str = "stage3/state.json",
        audit_log_path: str = "stage3/audit/audit_log.jsonl"
    ):
        self.state_file = state_file
        self.audit_log_path = audit_log_path
        self._ensure_init()

    def _ensure_init(self):
        os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(self.audit_log_path) or ".", exist_ok=True)
        if not os.path.exists(self.state_file):
            initial_data = {
                "current_state": ExperimentState.DRAFT.value,
                "history": [
                    {
                        "state": ExperimentState.DRAFT.value,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "reason": "Stage 3 Experiment Initialized"
                    }
                ]
            }
            with open(self.state_file, "w") as f:
                json.dump(initial_data, f, indent=2)

    def get_current_state(self) -> ExperimentState:
        with open(self.state_file) as f:
            data = json.load(f)
        return ExperimentState(data["current_state"])

    def transition_to(self, new_state: ExperimentState, reason: str = "") -> ExperimentState:
        curr_state = self.get_current_state()
        if new_state not in VALID_TRANSITIONS.get(curr_state, set()):
            msg = f"Invalid state transition attempted: {curr_state.value} -> {new_state.value}. Allowed: {[s.value for s in VALID_TRANSITIONS.get(curr_state, set())]}"
            self.log_audit_event("INVALID_TRANSITION_ATTEMPT", {"from": curr_state.value, "to": new_state.value, "reason": reason, "error": msg})
            raise RuntimeError(msg)

        with open(self.state_file) as f:
            data = json.load(f)

        data["current_state"] = new_state.value
        data["history"].append({
            "state": new_state.value,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reason": reason
        })

        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

        self.log_audit_event("STATE_TRANSITION", {"from": curr_state.value, "to": new_state.value, "reason": reason})
        return new_state

    def log_audit_event(self, event_type: str, details: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.audit_log_path) or ".", exist_ok=True)
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "state": self.get_current_state().value if os.path.exists(self.state_file) else "UNKNOWN",
            "event_type": event_type,
            "details": details
        }
        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # =========================================================================
    # TECHNICAL HIDDEN FIREWALL
    # =========================================================================
    def access_hidden_dataset(self, caller_tag: str, benchmark_path: str = "stage3/benchmarks/graph_coloring/hidden.json") -> List[Dict[str, Any]]:
        curr = self.get_current_state()
        allowed_states = {
            ExperimentState.SELECTIONS_FROZEN,
            ExperimentState.HIDDEN_RUNNING,
            ExperimentState.ANALYSIS_COMPLETE
        }

        if curr not in allowed_states:
            violation_details = {
                "caller_tag": caller_tag,
                "current_state": curr.value,
                "required_states": [s.value for s in allowed_states]
            }
            self.log_audit_event("FIREWALL_VIOLATION_BLOCKED", violation_details)
            raise PermissionError(
                f"HIDDEN FIREWALL VIOLATION: Caller '{caller_tag}' attempted to access hidden benchmark while in state '{curr.value}'. "
                f"Access is strictly forbidden until candidates and selections are cryptographically frozen in SELECTIONS_FROZEN."
            )

        if not os.path.exists(benchmark_path):
            raise FileNotFoundError(f"Hidden benchmark file {benchmark_path} not found.")

        self.log_audit_event("HIDDEN_DATA_ACCESSED", {"caller": caller_tag, "state": curr.value})
        with open(benchmark_path) as f:
            return json.load(f)
