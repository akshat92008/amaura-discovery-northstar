"""
Unit Tests: Statistics, Holm Correction, and Selection Regret
============================================================
Enforces Section 12, 22, 23, 24, 25, 26, 35.
"""

import numpy as np
import pytest
from stage2.src.analyze import (
    run_paired_comparison,
    apply_holm_bonferroni,
    calculate_selection_regret,
    classify_stage2_outcome
)
from stage2.src.scaling import SubsamplingScalingEngine


def test_holm_bonferroni_correction():
    raw_p = [0.01, 0.04]  # 2 problem tests
    adj_p = apply_holm_bonferroni(raw_p)
    # Ranked: 0.01 * 2 = 0.02, 0.04 * 1 = 0.04
    assert adj_p[0] == pytest.approx(0.02, rel=1e-3)
    assert adj_p[1] == pytest.approx(0.04, rel=1e-3)


def test_selection_regret_calculation():
    # Selected candidate scores vs best candidate scores in pool
    selected = [25.0, 22.0, 30.0, 24.0]
    best_pool = [22.0, 22.0, 28.0, 20.0]

    regret = calculate_selection_regret(selected, best_pool)
    # Absolute regrets: [3.0, 0.0, 2.0, 4.0] -> mean = 2.25
    assert regret["mean_absolute_regret"] == pytest.approx(2.25, rel=1e-3)
    assert regret["zero_regret_rate"] == pytest.approx(0.25, rel=1e-3)


def test_subsampling_scaling():
    pool = [{"candidate_id": f"C_{i}", "dev_score": i + 5.0, "hidden_score": i + 10.0} for i in range(20)]
    scaling = SubsamplingScalingEngine(n_levels=[1, 5, 10, 20])
    res = scaling.evaluate_scaling(pool, "dev_score", "hidden_score", seed=42)

    assert 1 in res
    assert 5 in res
    assert 10 in res
    assert 20 in res
    # As N increases from 1 to 20, mean hidden score should decrease (improve)
    assert res[20]["mean_hidden_score"] <= res[1]["mean_hidden_score"]


def test_outcome_classification_strong_positive():
    comp_gc = {
        "bootstrap_ci_95": (-2.5, -0.8),
        "mean_diff": -1.65,
        "p_value_corrected": 0.005
    }
    comp_pfsp = {
        "bootstrap_ci_95": (-120.0, -35.0),
        "mean_diff": -77.5,
        "p_value_corrected": 0.012
    }
    outcome = classify_stage2_outcome(comp_gc, comp_pfsp, gc_practical_margin=0.5, pfsp_practical_margin=25.0)
    assert outcome["overall_classification"] == "STRONG_POSITIVE"
