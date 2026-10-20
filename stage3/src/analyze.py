"""
Stage 3: Statistical Analysis Engine (Revision 4.3 Clean Architecture)
======================================================================
Implements the preregistered three-part statistical evaluation:
1. Primary Continuous Analysis (Dual-Valid Trials Subset):
   - Pre-requisite dual-validity gate (>= 90% validity for both arms)
   - Finite numeric trial-level differences: Delta_t = Score_C,t - Score_A,t
   - Two-sided paired Wilcoxon signed-rank test on finite differences
   - 10,000-resample paired bootstrap CI for the mean difference E[Delta]
   - Practical meaningfulness threshold: CI_upper < -1.0 color
   - Holm-Bonferroni correction across primary (C vs A) and secondary comparisons

2. Binary Reliability Analysis (Separate Endpoint):
   - Counts of valid/invalid trials for each arm
   - Paired discordant counts (b: A valid, C fail; c: A fail, C valid)
   - Risk difference RD = P(Fail_C) - P(Fail_A) with 95% Wald CI
   - Exact two-sided McNemar test via Binomial(b + c, 0.5)
   - Reliability failure flag if C is significantly less reliable or valid rate < 90%

3. Worst-Case Bounded-Imputation Sensitivity Analysis:
   - Pre-verified worst-case penalty: S_penalty = 19,001 colors
   - Imputes 19,001 for zero-valid arm outcomes across all T trials
   - Finite numeric differences across all T trials
   - Recomputes 10,000 paired bootstrap CI for imputed mean difference
   - Recomputes paired Wilcoxon test on imputed differences
   - Classifies outcome into: ROBUST_SUCCESS, FRAGILE_SUCCESS, RELIABILITY_FAILURE, NOT_SUPPORTED
"""

import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from scipy import stats


WORST_CASE_PENALTY_BOUND = 19001


def holm_bonferroni_correction(p_values: Dict[str, float]) -> Dict[str, float]:
    """
    Applies Holm-Bonferroni step-down correction to a dict of {comparison_name: p_value}.
    Returns {comparison_name: adjusted_p_value}.
    """
    if not p_values:
        return {}

    sorted_items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(sorted_items)
    adjusted: Dict[str, float] = {}

    prev_adj = 0.0
    for rank, (name, p_val) in enumerate(sorted_items):
        multiplier = m - rank
        raw_adj = p_val * multiplier
        adj_p = max(prev_adj, min(1.0, raw_adj))
        prev_adj = adj_p
        adjusted[name] = float(adj_p)

    return adjusted


def paired_bootstrap_ci_mean(
    diffs: List[float],
    n_resamples: int = 10000,
    ci_level: float = 0.95,
    seed: int = 303
) -> Tuple[float, float, float]:
    """
    Computes paired bootstrap confidence interval for the mean difference E[Delta].
    Returns (mean_diff, ci_lower, ci_upper).
    """
    if not diffs:
        return float("nan"), float("nan"), float("nan")

    arr = np.array(diffs, dtype=np.float64)
    n = len(arr)
    mean_val = float(np.mean(arr))

    if n == 1:
        return mean_val, mean_val, mean_val

    rng = np.random.default_rng(seed)
    boot_indices = rng.integers(0, n, size=(n_resamples, n))
    boot_means = np.mean(arr[boot_indices], axis=1)

    alpha = 1.0 - ci_level
    lower_pct = (alpha / 2.0) * 100.0
    upper_pct = (1.0 - alpha / 2.0) * 100.0

    ci_lower = float(np.percentile(boot_means, lower_pct))
    ci_upper = float(np.percentile(boot_means, upper_pct))

    return mean_val, ci_lower, ci_upper


def paired_wilcoxon_test(diffs: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """
    Runs two-sided paired Wilcoxon signed-rank test strictly on finite numeric differences.
    Returns (statistic, p_value).
    If all differences are zero, returns (0.0, 1.0).
    If fewer than 1 difference, returns (None, None).
    """
    if not diffs:
        return None, None

    arr = np.array(diffs, dtype=np.float64)
    # Check that all elements are finite
    if not np.all(np.isfinite(arr)):
        raise ValueError("Wilcoxon signed-rank test requires strictly finite numeric values.")

    # If all differences are zero, p-value is 1.0
    non_zero = arr[arr != 0]
    if len(non_zero) == 0:
        return 0.0, 1.0

    try:
        res = stats.wilcoxon(arr, alternative="two-sided")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        # Edge case with very few points or ties
        return None, None


def analyze_binary_reliability(
    arm_x_valid: List[bool],
    arm_y_valid: List[bool],
    arm_x_name: str = "Arm_C",
    arm_y_name: str = "Arm_A"
) -> Dict[str, Any]:
    """
    Computes binary reliability analysis between two paired arms.
    arm_x is candidate method (e.g. C), arm_y is reference method (e.g. A).
    Returns contingency table, discordance, risk difference, and exact McNemar test.
    """
    t_total = len(arm_x_valid)
    if t_total != len(arm_y_valid):
        raise ValueError(f"Arm lengths mismatch: {t_total} vs {len(arm_y_valid)}")

    t_x_valid = sum(1 for v in arm_x_valid if v)
    t_x_fail = t_total - t_x_valid
    t_y_valid = sum(1 for v in arm_y_valid if v)
    t_y_fail = t_total - t_y_valid

    # Contingency counts
    # b: Y valid, X fail (X is worse)
    # c: Y fail, X valid (X is better)
    # a: both valid
    # d: both fail
    a = sum(1 for vx, vy in zip(arm_x_valid, arm_y_valid) if vx and vy)
    b = sum(1 for vx, vy in zip(arm_x_valid, arm_y_valid) if (not vx) and vy)
    c = sum(1 for vx, vy in zip(arm_x_valid, arm_y_valid) if vx and (not vy))
    d = sum(1 for vx, vy in zip(arm_x_valid, arm_y_valid) if (not vx) and (not vy))

    fail_rate_x = t_x_fail / t_total if t_total > 0 else 0.0
    fail_rate_y = t_y_fail / t_total if t_total > 0 else 0.0
    valid_rate_x = t_x_valid / t_total if t_total > 0 else 0.0
    valid_rate_y = t_y_valid / t_total if t_total > 0 else 0.0

    risk_diff = (b - c) / t_total if t_total > 0 else 0.0

    # Paired SE for risk difference: sqrt((b + c) - (b - c)^2 / T) / T
    if t_total > 0:
        se_var = (b + c) - ((b - c) ** 2) / t_total
        se_rd = math.sqrt(max(0.0, se_var)) / t_total
        rd_ci_lower = max(-1.0, risk_diff - 1.96 * se_rd)
        rd_ci_upper = min(1.0, risk_diff + 1.96 * se_rd)
    else:
        se_rd = 0.0
        rd_ci_lower = 0.0
        rd_ci_upper = 0.0

    # Exact McNemar test using Binomial(n = b + c, p = 0.5)
    n_discordant = b + c
    if n_discordant > 0:
        mcnemar_res = stats.binomtest(b, n_discordant, 0.5, alternative="two-sided")
        mcnemar_p = float(mcnemar_res.pvalue)
    else:
        mcnemar_p = 1.0

    # Reliability gate: fails if C validity rate < 90% or C is significantly less reliable than A
    reliability_failure = (
        valid_rate_x < 0.90 or
        (fail_rate_x > fail_rate_y and mcnemar_p < 0.05)
    )

    return {
        f"{arm_x_name}_valid_count": t_x_valid,
        f"{arm_x_name}_fail_count": t_x_fail,
        f"{arm_x_name}_valid_rate": round(valid_rate_x, 4),
        f"{arm_y_name}_valid_count": t_y_valid,
        f"{arm_y_name}_fail_count": t_y_fail,
        f"{arm_y_name}_valid_rate": round(valid_rate_y, 4),
        "contingency_table": {
            "both_valid": a,
            f"{arm_y_name}_valid_{arm_x_name}_fail": b,
            f"{arm_y_name}_fail_{arm_x_name}_valid": c,
            "both_fail": d
        },
        "discordant_pairs": {
            f"{arm_x_name}_fails_only": b,
            f"{arm_y_name}_fails_only": c,
            "total_discordant": n_discordant
        },
        "risk_difference_fail_x_minus_y": round(risk_diff, 4),
        "risk_difference_95_ci": [round(rd_ci_lower, 4), round(rd_ci_upper, 4)],
        "mcnemar_exact_p_value": mcnemar_p,
        "reliability_failure_triggered": reliability_failure
    }


def analyze_paired_continuous_dual_valid(
    trials_x: List[Dict[str, Any]],
    trials_y: List[Dict[str, Any]],
    arm_x_name: str = "Arm_C",
    arm_y_name: str = "Arm_A",
    n_bootstrap: int = 10000,
    seed: int = 303
) -> Dict[str, Any]:
    """
    Runs primary continuous analysis on the Dual-Valid Trial Subset.
    Delta_t = Score_X,t - Score_Y,t
    """
    t_total = len(trials_x)
    if t_total != len(trials_y):
        raise ValueError("Trials length mismatch")

    dual_valid_diffs = []
    dual_valid_scores_x = []
    dual_valid_scores_y = []
    dual_valid_trial_ids = []

    for i in range(t_total):
        tx = trials_x[i]
        ty = trials_y[i]
        t_id = tx.get("trial_id", i + 1)

        x_valid = (tx.get("status") == "VALID") and (tx.get("hidden_score") is not None)
        y_valid = (ty.get("status") == "VALID") and (ty.get("hidden_score") is not None)

        if x_valid and y_valid:
            sx = float(tx["hidden_score"])
            sy = float(ty["hidden_score"])
            diff = sx - sy
            dual_valid_diffs.append(diff)
            dual_valid_scores_x.append(sx)
            dual_valid_scores_y.append(sy)
            dual_valid_trial_ids.append(t_id)

    t_dual_valid = len(dual_valid_diffs)
    dual_valid_rate = t_dual_valid / t_total if t_total > 0 else 0.0

    if t_dual_valid == 0:
        return {
            "status": "NO_DUAL_VALID_TRIALS",
            "T_total": t_total,
            "T_dual_valid": 0,
            "dual_valid_rate": 0.0,
            "mean_delta": None,
            "median_delta": None,
            "bootstrap_ci_95": [None, None],
            "wilcoxon_stat": None,
            "wilcoxon_raw_p": None,
            "practical_criterion_met": False
        }

    mean_delta, ci_low, ci_high = paired_bootstrap_ci_mean(
        dual_valid_diffs, n_resamples=n_bootstrap, seed=seed
    )
    median_delta = float(np.median(dual_valid_diffs))
    w_stat, w_p = paired_wilcoxon_test(dual_valid_diffs)

    # Practical criterion: CI upper bound < -1.0 color
    practical_criterion_met = (ci_high is not None) and (ci_high < -1.0)

    return {
        "status": "COMPLETED",
        "T_total": t_total,
        "T_dual_valid": t_dual_valid,
        "dual_valid_rate": round(dual_valid_rate, 4),
        "dual_valid_trial_ids": dual_valid_trial_ids,
        "mean_delta": round(mean_delta, 4),
        "median_delta": round(median_delta, 4),
        "mean_x": round(float(np.mean(dual_valid_scores_x)), 4),
        "mean_y": round(float(np.mean(dual_valid_scores_y)), 4),
        "bootstrap_ci_95": [round(ci_low, 4), round(ci_high, 4)],
        "wilcoxon_stat": w_stat,
        "wilcoxon_raw_p": w_p,
        "practical_criterion_met": practical_criterion_met,
        "finite_differences": dual_valid_diffs
    }


def analyze_bounded_imputation_sensitivity(
    trials_x: List[Dict[str, Any]],
    trials_y: List[Dict[str, Any]],
    penalty_score: int = WORST_CASE_PENALTY_BOUND,
    n_bootstrap: int = 10000,
    seed: int = 303
) -> Dict[str, Any]:
    """
    Worst-case bounded-imputation sensitivity analysis across ALL T trials.
    Imputes penalty_score for any trial with 0 valid candidates.
    """
    t_total = len(trials_x)
    if t_total != len(trials_y):
        raise ValueError("Trials length mismatch")

    imputed_diffs = []
    imputed_scores_x = []
    imputed_scores_y = []

    for i in range(t_total):
        tx = trials_x[i]
        ty = trials_y[i]

        x_valid = (tx.get("status") == "VALID") and (tx.get("hidden_score") is not None)
        y_valid = (ty.get("status") == "VALID") and (ty.get("hidden_score") is not None)

        sx = float(tx["hidden_score"]) if x_valid else float(penalty_score)
        sy = float(ty["hidden_score"]) if y_valid else float(penalty_score)

        diff = sx - sy
        imputed_diffs.append(diff)
        imputed_scores_x.append(sx)
        imputed_scores_y.append(sy)

    mean_delta, ci_low, ci_high = paired_bootstrap_ci_mean(
        imputed_diffs, n_resamples=n_bootstrap, seed=seed
    )
    median_delta = float(np.median(imputed_diffs))
    w_stat, w_p = paired_wilcoxon_test(imputed_diffs)

    sensitivity_criterion_met = (ci_high is not None) and (ci_high < -1.0)

    return {
        "T_total": t_total,
        "penalty_score_used": penalty_score,
        "imputed_mean_delta": round(mean_delta, 4),
        "imputed_median_delta": round(median_delta, 4),
        "imputed_bootstrap_ci_95": [round(ci_low, 4), round(ci_high, 4)],
        "imputed_wilcoxon_stat": w_stat,
        "imputed_wilcoxon_raw_p": w_p,
        "sensitivity_criterion_met": sensitivity_criterion_met,
        "imputed_differences": imputed_diffs
    }


def run_full_stage3_analysis(
    experiment_results: List[Dict[str, Any]],
    penalty_score: int = WORST_CASE_PENALTY_BOUND,
    n_bootstrap: int = 10000,
    seed: int = 303
) -> Dict[str, Any]:
    """
    Runs the complete Stage 3 statistical suite across Arms A, B, and C for all trials.
    Implements Holm-Bonferroni correction across:
    1. C vs A (primary)
    2. C vs B (secondary)
    3. B vs A (tertiary)

    Classifies overall experimental outcome according to Revision 4.3 decision rules.
    """
    trials_a = [t["arm_a"] for t in experiment_results]
    trials_b = [t["arm_b"] for t in experiment_results]
    trials_c = [t["arm_c"] for t in experiment_results]

    t_total = len(experiment_results)

    # 1. Primary Continuous Dual-Valid Analyses
    c_vs_a_cont = analyze_paired_continuous_dual_valid(
        trials_c, trials_a, "Arm_C", "Arm_A", n_bootstrap, seed
    )
    c_vs_b_cont = analyze_paired_continuous_dual_valid(
        trials_c, trials_b, "Arm_C", "Arm_B", n_bootstrap, seed
    )
    b_vs_a_cont = analyze_paired_continuous_dual_valid(
        trials_b, trials_a, "Arm_B", "Arm_A", n_bootstrap, seed
    )

    # Holm-Bonferroni Correction on Dual-Valid Wilcoxon p-values
    raw_p_map = {}
    if c_vs_a_cont.get("wilcoxon_raw_p") is not None:
        raw_p_map["C_vs_A"] = c_vs_a_cont["wilcoxon_raw_p"]
    if c_vs_b_cont.get("wilcoxon_raw_p") is not None:
        raw_p_map["C_vs_B"] = c_vs_b_cont["wilcoxon_raw_p"]
    if b_vs_a_cont.get("wilcoxon_raw_p") is not None:
        raw_p_map["B_vs_A"] = b_vs_a_cont["wilcoxon_raw_p"]

    adj_p_map = holm_bonferroni_correction(raw_p_map)

    c_vs_a_cont["wilcoxon_holm_adj_p"] = adj_p_map.get("C_vs_A")
    c_vs_b_cont["wilcoxon_holm_adj_p"] = adj_p_map.get("C_vs_B")
    b_vs_a_cont["wilcoxon_holm_adj_p"] = adj_p_map.get("B_vs_A")

    # 2. Binary Reliability Analyses
    c_valid = [(t.get("status") == "VALID" and t.get("hidden_score") is not None) for t in trials_c]
    a_valid = [(t.get("status") == "VALID" and t.get("hidden_score") is not None) for t in trials_a]
    b_valid = [(t.get("status") == "VALID" and t.get("hidden_score") is not None) for t in trials_b]

    rel_c_vs_a = analyze_binary_reliability(c_valid, a_valid, "Arm_C", "Arm_A")
    rel_c_vs_b = analyze_binary_reliability(c_valid, b_valid, "Arm_C", "Arm_B")
    rel_b_vs_a = analyze_binary_reliability(b_valid, a_valid, "Arm_B", "Arm_A")

    # 3. Sensitivity Analyses under Bounded Imputation
    c_vs_a_sens = analyze_bounded_imputation_sensitivity(
        trials_c, trials_a, penalty_score, n_bootstrap, seed
    )
    c_vs_b_sens = analyze_bounded_imputation_sensitivity(
        trials_c, trials_b, penalty_score, n_bootstrap, seed
    )
    b_vs_a_sens = analyze_bounded_imputation_sensitivity(
        trials_b, trials_a, penalty_score, n_bootstrap, seed
    )

    # 4. Overall Decision Classification for Primary Comparison (C vs A)
    # Gates:
    gate_c_valid = rel_c_vs_a["Arm_C_valid_rate"] >= 0.90
    gate_a_valid = rel_c_vs_a["Arm_A_valid_rate"] >= 0.90
    gate_validity_passed = gate_c_valid and gate_a_valid

    primary_stat_sig = (
        c_vs_a_cont.get("wilcoxon_holm_adj_p") is not None and
        c_vs_a_cont["wilcoxon_holm_adj_p"] < 0.05
    )
    primary_practical_met = c_vs_a_cont.get("practical_criterion_met", False)
    primary_cont_success = gate_validity_passed and primary_stat_sig and primary_practical_met

    rel_failure = rel_c_vs_a["reliability_failure_triggered"]
    sens_success = c_vs_a_sens["sensitivity_criterion_met"]

    if rel_failure or not gate_validity_passed:
        final_classification = "RELIABILITY_FAILURE"
        verdict_explanation = (
            f"Reliability gate failed: Arm C valid rate={rel_c_vs_a['Arm_C_valid_rate']:.1%}, "
            f"Arm A valid rate={rel_c_vs_a['Arm_A_valid_rate']:.1%}, "
            f"McNemar p={rel_c_vs_a['mcnemar_exact_p_value']:.4f}."
        )
    elif primary_cont_success and sens_success:
        final_classification = "ROBUST_SUCCESS"
        verdict_explanation = (
            "Both primary continuous analysis and bounded-imputation sensitivity analysis passed: "
            f"Wilcoxon Holm adj p={c_vs_a_cont['wilcoxon_holm_adj_p']:.4e}, "
            f"Primary 95% CI upper={c_vs_a_cont['bootstrap_ci_95'][1]:.2f} < -1.0, "
            f"Sensitivity 95% CI upper={c_vs_a_sens['imputed_bootstrap_ci_95'][1]:.2f} < -1.0."
        )
    elif primary_cont_success and not sens_success:
        final_classification = "FRAGILE_SUCCESS"
        verdict_explanation = (
            "Primary continuous analysis passed, but bounded-imputation sensitivity analysis failed "
            f"(imputed 95% CI upper={c_vs_a_sens['imputed_bootstrap_ci_95'][1]:.2f} >= -1.0)."
        )
    else:
        final_classification = "NOT_SUPPORTED"
        verdict_explanation = (
            "Execution-driven adaptive search did not demonstrate statistically significant and practically meaningful "
            "superiority over independent Best-of-100 search."
        )

    return {
        "governance_revision": "4.3",
        "T_trials": t_total,
        "penalty_bound": penalty_score,
        "final_classification": final_classification,
        "verdict_explanation": verdict_explanation,
        "primary_comparison_C_vs_A": {
            "continuous_dual_valid": c_vs_a_cont,
            "binary_reliability": rel_c_vs_a,
            "bounded_imputation_sensitivity": c_vs_a_sens
        },
        "secondary_comparison_C_vs_B": {
            "continuous_dual_valid": c_vs_b_cont,
            "binary_reliability": rel_c_vs_b,
            "bounded_imputation_sensitivity": c_vs_b_sens
        },
        "tertiary_comparison_B_vs_A": {
            "continuous_dual_valid": b_vs_a_cont,
            "binary_reliability": rel_b_vs_a,
            "bounded_imputation_sensitivity": b_vs_a_sens
        },
        "holm_bonferroni_summary": {
            "raw_p_values": raw_p_map,
            "adjusted_p_values": adj_p_map
        }
    }
