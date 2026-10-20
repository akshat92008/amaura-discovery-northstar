"""
Adversarial Verification Suite for Stage 2
==========================================
Specifically targets potential false-positive mechanisms in the D vs B comparison:
1. B/D candidate identity tampering & abort enforcement
2. Execution-blind judge prompt leakage tests
3. Technical hidden firewall penetration tests across unauthorized states
4. Statistical engine ground-truth verification
5. Invalid candidate & zero-valid pool regret handling
"""

import copy
import hashlib
import json
import os
import tempfile
import pytest
import numpy as np

from stage2.src.runner import Stage2Runner
from stage2.src.judge import BlindJudgeEngine
from stage2.prompts.judge_prompts import build_judge_prompt
from stage2.src.state_machine import StateMachine, ExperimentState
from stage2.src.analyze import (
    paired_bootstrap_ci,
    compute_effect_size,
    run_paired_comparison,
    apply_holm_bonferroni,
    calculate_selection_regret,
    classify_stage2_outcome
)


# =========================================================================
# 1. B/D IDENTITY ADVERSARIAL TESTS
# =========================================================================

def test_adversarial_b_d_mismatch_aborts():
    """
    Deliberately alters one candidate in pool D and verifies that
    verify_pool_identity strictly aborts with a ValueError.
    """
    base_pool = [
        {
            "candidate_id": f"GC_T01_E_C{i+1:02d}",
            "candidate_hash": hashlib.sha256(f"code_{i}".encode()).hexdigest(),
            "code": f"def color_graph(adj):\n    return [0]*len(adj) # candidate {i}"
        }
        for i in range(20)
    ]

    pool_b = copy.deepcopy(base_pool)
    pool_d = copy.deepcopy(base_pool)

    # Identical pools must pass
    Stage2Runner.verify_pool_identity(pool_b, pool_d)

    # Tamper 1: Modify hash in candidate 7
    pool_d_tampered_hash = copy.deepcopy(pool_d)
    pool_d_tampered_hash[6]["candidate_hash"] = "adversarial_injected_hash"
    with pytest.raises(ValueError, match="CRITICAL EXPERIMENT VIOLATION"):
        Stage2Runner.verify_pool_identity(pool_b, pool_d_tampered_hash)

    # Tamper 2: Modify code in candidate 15
    pool_d_tampered_code = copy.deepcopy(pool_d)
    pool_d_tampered_code[14]["code"] = "def color_graph(adj):\n    # subtle modification\n    return [0]*len(adj)"
    with pytest.raises(ValueError, match="CRITICAL EXPERIMENT VIOLATION"):
        Stage2Runner.verify_pool_identity(pool_b, pool_d_tampered_code)

    # Tamper 3: Pool length mismatch
    with pytest.raises(ValueError, match="Pool size mismatch"):
        Stage2Runner.verify_pool_identity(pool_b[:19], pool_d)


# =========================================================================
# 2. JUDGE BLINDNESS ADVERSARIAL LEAKAGE TESTS
# =========================================================================

def test_adversarial_judge_blindness_leakage():
    """
    Injects dev scores, hidden scores, and rankings into candidate objects
    and verifies that build_judge_prompt completely excludes them.
    """
    shuffled_candidates = [
        {
            "option_id": f"Option_{i+1:02d}",
            "candidate_id": f"C_{i+1:02d}",
            "code": f"def color_graph(adj):\n    return [0]*len(adj)  # variant {i}",
            # Malicious injected fields that must NOT appear in prompt
            "dev_score": 14.8765,
            "hidden_score": 11.2345,
            "runtime_ms": 3.456,
            "rank": 1,
            "is_best": True,
            "dev_error": "None"
        }
        for i in range(20)
    ]

    prompt = build_judge_prompt("graph_coloring", shuffled_candidates)

    forbidden_substrings = [
        "14.8765",
        "11.2345",
        "dev_score",
        "hidden_score",
        "runtime_ms",
        "is_best",
        "dev_error"
    ]

    for forbidden in forbidden_substrings:
        assert forbidden not in prompt, f"ADVERSARIAL LEAKAGE DETECTED: Found '{forbidden}' in judge prompt!"


# =========================================================================
# 3. HIDDEN FIREWALL PENETRATION TESTS
# =========================================================================

def test_adversarial_hidden_firewall_blocks_all_unauthorized_states():
    """
    Attempts to access hidden benchmark datasets from every unauthorized state
    and verifies that PermissionError is strictly raised and logged.
    """
    tmp_dir = tempfile.mkdtemp()
    state_file = os.path.join(tmp_dir, "state.json")
    audit_file = os.path.join(tmp_dir, "audit.jsonl")

    sm = StateMachine(state_file=state_file, audit_log_path=audit_file)

    unauthorized_states = [
        ExperimentState.DRAFT,
        ExperimentState.AUDIT,
        ExperimentState.PILOT,
        ExperimentState.PROMPTS_FROZEN,
        ExperimentState.DATA_FROZEN,
        ExperimentState.MAIN_RUNNING
    ]

    for state in unauthorized_states:
        with open(state_file, "w") as f:
            json.dump({"current_state": state.value, "history": []}, f)

        with pytest.raises(PermissionError, match="HIDDEN FIREWALL VIOLATION"):
            sm.access_hidden_dataset("graph_coloring", caller_tag=f"penetration_test_{state.value}")

    # Verify audit log contains violation records
    with open(audit_file) as f:
        log_entries = [json.loads(line) for line in f]
    
    violation_events = [e for e in log_entries if e["event_type"] == "FIREWALL_VIOLATION_BLOCKED"]
    assert len(violation_events) == len(unauthorized_states)


# =========================================================================
# 4. STATISTICAL ENGINE GROUND TRUTH TESTS
# =========================================================================

def test_adversarial_statistics_known_ground_truth():
    """
    Constructs synthetic datasets with known mathematical properties and
    verifies exact behavior of Wilcoxon, Holm, CI, and Regret.
    """
    # 1. Wilcoxon Identical Inputs (Ties only)
    res_tie = run_paired_comparison([25.0] * 30, [25.0] * 30)
    assert res_tie["wins"] == 0
    assert res_tie["ties"] == 30
    assert res_tie["losses"] == 0
    assert res_tie["p_value_raw"] == 1.0

    # 2. Wilcoxon Constant Superiority (D strictly better)
    res_win = run_paired_comparison([20.0] * 30, [25.0] * 30)
    assert res_win["wins"] == 30
    assert res_win["ties"] == 0
    assert res_win["losses"] == 0
    assert res_win["mean_diff"] == -5.0
    assert res_win["pct_reduction"] == 20.0
    assert res_win["p_value_raw"] < 0.001

    # 3. Holm-Bonferroni Boundary Properties
    # Both significant
    corr1 = apply_holm_bonferroni([0.02, 0.04])
    assert corr1 == [0.04, 0.04]
    assert all(p <= 0.05 for p in corr1)

    # First significant, second not
    corr2 = apply_holm_bonferroni([0.01, 0.08])
    assert corr2 == [0.02, 0.08]

    # Monotonicity test
    corr3 = apply_holm_bonferroni([0.04, 0.02, 0.03])
    assert corr3[1] <= corr3[2] <= corr3[0]

    # 4. Bootstrap CI exactness on constant shift
    diffs = np.array([-4.0] * 30)
    low, high = paired_bootstrap_ci(diffs)
    assert low == -4.0 and high == -4.0

    # 5. Selection Regret calculation
    # Best in pool is 10. Selected are [10, 15, 20]
    reg = calculate_selection_regret([10.0, 15.0, 20.0], [10.0, 10.0, 10.0])
    assert reg["mean_absolute_regret"] == pytest.approx(5.0, rel=1e-3)
    assert reg["zero_regret_rate"] == pytest.approx(1/3, rel=1e-3)

    # 6. Outcome Classification
    # Strong positive
    gc_comp = {"bootstrap_ci_95": (-2.0, -1.0), "mean_diff": -1.5, "p_value_corrected": 0.001}
    pfsp_comp = {"bootstrap_ci_95": (-50.0, -30.0), "mean_diff": -40.0, "p_value_corrected": 0.001}
    verdict_pos = classify_stage2_outcome(gc_comp, pfsp_comp, gc_practical_margin=0.5, pfsp_practical_margin=25.0)
    assert verdict_pos["overall_classification"] == "STRONG_POSITIVE"

    # Equivalence
    gc_eq = {"bootstrap_ci_95": (-0.2, 0.2), "mean_diff": 0.0, "p_value_corrected": 0.9}
    pfsp_eq = {"bootstrap_ci_95": (-10.0, 10.0), "mean_diff": 0.0, "p_value_corrected": 0.9}
    verdict_eq = classify_stage2_outcome(gc_eq, pfsp_eq, gc_practical_margin=0.5, pfsp_practical_margin=25.0)
    assert verdict_eq["overall_classification"] == "NO_MEANINGFUL_ADVANTAGE"
