"""
Unit Tests: State Machine & Technical Hidden Firewall
=====================================================
Enforces Section 31, 32, 35.
"""

import os
import pytest
from stage2.src.state_machine import StateMachine, ExperimentState


def test_state_transitions(tmp_path):
    state_file = str(tmp_path / "state.json")
    audit_file = str(tmp_path / "audit.jsonl")
    sm = StateMachine(state_file=state_file, audit_log_path=audit_file)

    assert sm.get_current_state() == ExperimentState.DRAFT

    # Valid progression
    sm.transition_to(ExperimentState.AUDIT, "test audit")
    assert sm.get_current_state() == ExperimentState.AUDIT

    sm.transition_to(ExperimentState.PILOT, "test pilot")
    assert sm.get_current_state() == ExperimentState.PILOT

    sm.transition_to(ExperimentState.PROMPTS_FROZEN, "test prompts frozen")
    assert sm.get_current_state() == ExperimentState.PROMPTS_FROZEN

    sm.transition_to(ExperimentState.DATA_FROZEN, "test data frozen")
    assert sm.get_current_state() == ExperimentState.DATA_FROZEN

    sm.transition_to(ExperimentState.MAIN_RUNNING, "test main running")
    assert sm.get_current_state() == ExperimentState.MAIN_RUNNING


def test_invalid_state_transition_raises_error(tmp_path):
    state_file = str(tmp_path / "state.json")
    audit_file = str(tmp_path / "audit.jsonl")
    sm = StateMachine(state_file=state_file, audit_log_path=audit_file)

    assert sm.get_current_state() == ExperimentState.DRAFT
    # Attempting to jump directly from DRAFT to MAIN_RUNNING must fail closed
    with pytest.raises(RuntimeError):
        sm.transition_to(ExperimentState.MAIN_RUNNING, "illegal jump")


def test_hidden_firewall_blocks_premature_access(tmp_path):
    state_file = str(tmp_path / "state.json")
    audit_file = str(tmp_path / "audit.jsonl")
    sm = StateMachine(state_file=state_file, audit_log_path=audit_file)

    # In DRAFT, access must be blocked
    with pytest.raises(PermissionError):
        sm.access_hidden_dataset("graph_coloring", caller_tag="unauthorized_caller")

    # In AUDIT, access must be blocked
    sm.transition_to(ExperimentState.AUDIT)
    with pytest.raises(PermissionError):
        sm.access_hidden_dataset("graph_coloring", caller_tag="unauthorized_caller")


def test_hidden_firewall_allows_access_after_selections_frozen(tmp_path):
    state_file = str(tmp_path / "state.json")
    audit_file = str(tmp_path / "audit.jsonl")
    sm = StateMachine(state_file=state_file, audit_log_path=audit_file)

    sm.transition_to(ExperimentState.AUDIT)
    sm.transition_to(ExperimentState.PILOT)
    sm.transition_to(ExperimentState.PROMPTS_FROZEN)
    sm.transition_to(ExperimentState.DATA_FROZEN)
    sm.transition_to(ExperimentState.MAIN_RUNNING)
    sm.transition_to(ExperimentState.SELECTIONS_FROZEN)

    # After SELECTIONS_FROZEN, hidden data access must succeed
    hidden_data = sm.access_hidden_dataset("graph_coloring", caller_tag="evaluator")
    assert isinstance(hidden_data, list)
    assert len(hidden_data) > 0
