"""
Unit Tests: Experiment State Machine & Technical Hidden Firewall
================================================================
Verifies:
1. Legal state transitions succeed and are logged.
2. Illegal state transitions raise RuntimeError and log violation.
3. Accessing hidden benchmark before SELECTIONS_FROZEN strictly raises PermissionError.
4. Accessing hidden benchmark in SELECTIONS_FROZEN succeeds.
"""

import os
import json
import pytest
from stage3.src.state_machine import StateMachine, ExperimentState


@pytest.fixture
def clean_sm(tmp_path):
    state_file = str(tmp_path / "state.json")
    audit_file = str(tmp_path / "audit.jsonl")
    bench_file = str(tmp_path / "hidden.json")
    with open(bench_file, "w") as f:
        json.dump([{"adj": [[1], [0]]}], f)

    sm = StateMachine(state_file=state_file, audit_log_path=audit_file)
    return sm, bench_file


def test_firewall_blocks_premature_access(clean_sm):
    sm, bench_file = clean_sm
    assert sm.get_current_state() == ExperimentState.DRAFT

    # Attempt premature access in DRAFT state
    with pytest.raises(PermissionError) as exc_info:
        sm.access_hidden_dataset("test_caller", bench_file)
    assert "HIDDEN FIREWALL VIOLATION" in str(exc_info.value)


def test_state_machine_transitions_and_firewall_opening(clean_sm):
    sm, bench_file = clean_sm

    # Transition sequence
    sm.transition_to(ExperimentState.AUDIT, "Starting audit")
    sm.transition_to(ExperimentState.IMPLEMENTATION_VERIFIED, "Tests passed")
    sm.transition_to(ExperimentState.PILOT_READY, "Ready for pilot")
    sm.transition_to(ExperimentState.PILOT_RUNNING, "Running pilot")
    sm.transition_to(ExperimentState.PILOT_COMPLETE, "Pilot complete")
    sm.transition_to(ExperimentState.PROTOCOL_FROZEN, "Freezing protocol")
    sm.transition_to(ExperimentState.MAIN_RUNNING, "Running main")
    sm.transition_to(ExperimentState.SELECTIONS_FROZEN, "Selections frozen")

    # In SELECTIONS_FROZEN, firewall must allow access
    data = sm.access_hidden_dataset("legitimate_evaluator", bench_file)
    assert len(data) == 1
    assert data[0]["adj"] == [[1], [0]]


def test_illegal_state_transition_raises_error(clean_sm):
    sm, _ = clean_sm
    assert sm.get_current_state() == ExperimentState.DRAFT

    # Attempt invalid jump DRAFT -> MAIN_RUNNING
    with pytest.raises(RuntimeError) as exc_info:
        sm.transition_to(ExperimentState.MAIN_RUNNING, "Illegal jump")
    assert "Invalid state transition attempted" in str(exc_info.value)
