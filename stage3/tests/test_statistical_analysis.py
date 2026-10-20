"""
Unit Tests: Statistical Analysis Engine (Revision 4.3 Architecture)
===================================================================
Verifies:
1. Paired bootstrap CI on mean difference.
2. Finite-only Wilcoxon signed-rank test (rejects non-finite/infinite inputs).
3. Binary reliability analysis (discordant counts, risk difference, exact McNemar test).
4. Bounded-imputation sensitivity analysis with penalty = 19,001.
5. Holm-Bonferroni correction across comparisons.
6. Decision classifications: ROBUST_SUCCESS, FRAGILE_SUCCESS, RELIABILITY_FAILURE, NOT_SUPPORTED.
"""

import pytest
import numpy as np
from stage3.src.analyze import (
    paired_bootstrap_ci_mean,
    paired_wilcoxon_test,
    analyze_binary_reliability,
    analyze_paired_continuous_dual_valid,
    analyze_bounded_imputation_sensitivity,
    run_full_stage3_analysis,
    holm_bonferroni_correction
)


def test_bootstrap_ci_mean_calculation():
    # Mean is -2.0, standard normal noise
    rng = np.random.default_rng(42)
    diffs = (-2.0 + rng.normal(0, 0.2, 50)).tolist()

    mean_d, ci_low, ci_high = paired_bootstrap_ci_mean(diffs, n_resamples=5000, seed=42)
    assert -2.2 < mean_d < -1.8
    assert ci_low < mean_d < ci_high
    assert ci_high < -1.0  # Pass practical threshold


def test_wilcoxon_finite_only_enforcement():
    # Valid finite input
    stat, p = paired_wilcoxon_test([-2.0, -1.0, -3.0, -2.5, -1.5])
    assert stat is not None
    assert p is not None
    assert 0.0 <= p <= 1.0

    # Non-finite input must raise ValueError
    with pytest.raises(ValueError) as exc_info:
        paired_wilcoxon_test([-2.0, float("inf"), -1.0])
    assert "Wilcoxon signed-rank test requires strictly finite numeric values" in str(exc_info.value)

    with pytest.raises(ValueError):
        paired_wilcoxon_test([-2.0, float("nan"), -1.0])

    # All zero differences
    stat_zero, p_zero = paired_wilcoxon_test([0.0, 0.0, 0.0])
    assert stat_zero == 0.0
    assert p_zero == 1.0


def test_binary_reliability_analysis_and_mcnemar():
    # Arm C fails 5 times, Arm A fails 0 times out of 30
    c_valid = [True] * 25 + [False] * 5
    a_valid = [True] * 30

    rel = analyze_binary_reliability(c_valid, a_valid, "Arm_C", "Arm_A")
    assert rel["Arm_C_valid_count"] == 25
    assert rel["Arm_C_fail_count"] == 5
    assert rel["Arm_A_valid_count"] == 30
    assert rel["Arm_A_fail_count"] == 0
    assert rel["discordant_pairs"]["Arm_C_fails_only"] == 5
    assert rel["discordant_pairs"]["Arm_A_fails_only"] == 0
    assert rel["risk_difference_fail_x_minus_y"] == pytest.approx(5 / 30, abs=1e-4)

    # 5 discordant pairs all in direction of C failing -> p = (0.5)^5 * 2 = 0.0625
    assert rel["mcnemar_exact_p_value"] == pytest.approx(0.0625, abs=1e-4)
    # Valid rate is 25/30 = 83.3% < 90% -> reliability failure triggered!
    assert rel["reliability_failure_triggered"] is True


def test_bounded_imputation_sensitivity():
    # 2 trials: trial 1 both valid (C=10, A=12, diff=-2)
    # trial 2: C fails (impute 19001), A succeeds (A=15, diff=18986)
    trials_c = [
        {"status": "VALID", "hidden_score": 10},
        {"status": "ARM_FAILURE_NO_VALID_CANDIDATE", "hidden_score": None}
    ]
    trials_a = [
        {"status": "VALID", "hidden_score": 12},
        {"status": "VALID", "hidden_score": 15}
    ]

    sens = analyze_bounded_imputation_sensitivity(trials_c, trials_a, penalty_score=19001, n_bootstrap=1000)
    assert sens["T_total"] == 2
    assert sens["imputed_differences"] == [-2.0, 19001.0 - 15.0]
    assert not sens["sensitivity_criterion_met"]


def test_holm_bonferroni_correction_logic():
    raw_p = {"A": 0.01, "B": 0.04, "C": 0.03}
    adj_p = holm_bonferroni_correction(raw_p)

    # Sorted: A (0.01, mult 3 -> 0.03), C (0.03, mult 2 -> 0.06), B (0.04, mult 1 -> 0.06)
    assert adj_p["A"] == pytest.approx(0.03, abs=1e-4)
    assert adj_p["C"] == pytest.approx(0.06, abs=1e-4)
    assert adj_p["B"] == pytest.approx(0.06, abs=1e-4)


def test_full_analysis_robust_success():
    # Construct 30 synthetic trials where C consistently beats A and both are 100% valid
    results = []
    for i in range(30):
        results.append({
            "trial_id": i + 1,
            "arm_a": {"status": "VALID", "hidden_score": 1000 + i * 2},
            "arm_b": {"status": "VALID", "hidden_score": 995 + i * 2},
            "arm_c": {"status": "VALID", "hidden_score": 990 + i * 2}  # C is 10 colors better than A
        })

    report = run_full_stage3_analysis(results, penalty_score=19001, n_bootstrap=1000, seed=303)
    assert report["final_classification"] == "ROBUST_SUCCESS"
    assert report["primary_comparison_C_vs_A"]["continuous_dual_valid"]["practical_criterion_met"] is True
    assert report["primary_comparison_C_vs_A"]["continuous_dual_valid"]["wilcoxon_holm_adj_p"] < 0.05


def test_full_analysis_reliability_failure():
    # Construct 30 synthetic trials where C has 5 failures (validity = 25/30 = 83.3% < 90%)
    results = []
    for i in range(30):
        c_status = "VALID" if i < 25 else "ARM_FAILURE_NO_VALID_CANDIDATE"
        c_score = 990 if i < 25 else None
        results.append({
            "trial_id": i + 1,
            "arm_a": {"status": "VALID", "hidden_score": 1000},
            "arm_b": {"status": "VALID", "hidden_score": 995},
            "arm_c": {"status": c_status, "hidden_score": c_score}
        })

    report = run_full_stage3_analysis(results, penalty_score=19001, n_bootstrap=1000, seed=303)
    assert report["final_classification"] == "RELIABILITY_FAILURE"
