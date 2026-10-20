"""
Stage 2: Statistical Engine & Outcome Classifier
================================================
Enforces Sections 23, 24, 25, 26, 29:
1. Primary unit: trial-level hidden score of selected candidates.
2. Primary contrast: D - B (evaluated separately on Graph Coloring and PFSP).
3. Secondary comparisons: D vs A, C vs D.
4. Paired Wilcoxon signed-rank test.
5. Holm-Bonferroni correction across the two problem families.
6. Paired bootstrap confidence intervals (10,000 resamples).
7. Selection Regret analysis on all 20 candidates per pool.
8. Practical Equivalence gate.
9. Formal outcome classification:
   - Strong positive
   - Narrow positive
   - Negative
   - No meaningful advantage
   - Inconclusive
"""

import json
import math
from typing import Dict, Any, List, Tuple
import numpy as np
from scipy import stats


def paired_bootstrap_ci(diffs: np.ndarray, num_resamples: int = 10000, alpha: float = 0.05) -> Tuple[float, float]:
    n = len(diffs)
    if n == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(42)
    boot_means = np.mean(rng.choice(diffs, size=(num_resamples, n), replace=True), axis=1)
    lower = float(np.percentile(boot_means, 100 * (alpha / 2.0)))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2.0)))
    return round(lower, 4), round(upper, 4)


def compute_effect_size(diffs: np.ndarray) -> float:
    std = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
    if std == 0.0:
        return 0.0
    return float(np.mean(diffs) / std)


def run_paired_comparison(
    scores_d: List[float],
    scores_b: List[float],
    label_d: str = "Arm_D",
    label_b: str = "Arm_B"
) -> Dict[str, Any]:
    d = np.array(scores_d, dtype=float)
    b = np.array(scores_b, dtype=float)
    diffs = d - b  # negative means D is lower (better)

    wins = int(np.sum(diffs < -1e-6))
    ties = int(np.sum(np.abs(diffs) <= 1e-6))
    losses = int(np.sum(diffs > 1e-6))

    mean_d = float(np.mean(d))
    mean_b = float(np.mean(b))
    mean_diff = float(np.mean(diffs))
    median_diff = float(np.median(diffs))
    pct_reduction = -((mean_diff / mean_b) * 100.0) if mean_b > 0 else 0.0

    ci_lower, ci_upper = paired_bootstrap_ci(diffs)
    effect_size = compute_effect_size(diffs)

    if np.all(diffs == 0):
        p_val = 1.0
    else:
        try:
            stat, p_val = stats.wilcoxon(d, b, alternative="two-sided")
        except Exception:
            p_val = 1.0

    return {
        "label_d": label_d,
        "label_b": label_b,
        "n_trials": len(diffs),
        "mean_d": round(mean_d, 4),
        "mean_b": round(mean_b, 4),
        "mean_diff": round(mean_diff, 4),
        "median_diff": round(median_diff, 4),
        "pct_reduction": round(pct_reduction, 2),
        "bootstrap_ci_95": (ci_lower, ci_upper),
        "p_value_raw": float(p_val),
        "p_value_corrected": float(p_val),  # updated during Holm correction
        "effect_size_d": round(effect_size, 4),
        "wins": wins,
        "ties": ties,
        "losses": losses
    }


def apply_holm_bonferroni(p_values: List[float]) -> List[float]:
    """
    Applies Holm-Bonferroni step-down correction to a list of p-values.
    """
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected = [0.0] * m
    running_max = 0.0

    for rank, (orig_idx, p) in enumerate(indexed):
        # Multiplier: (m - rank)
        adj_p = min(1.0, p * (m - rank))
        running_max = max(running_max, adj_p)
        corrected[orig_idx] = running_max

    return [round(p, 6) for p in corrected]


def calculate_selection_regret(
    selected_scores: List[float],
    best_pool_scores: List[float]
) -> Dict[str, Any]:
    """
    Computes Selection Regret (Section 12):
    regret = selected_score - best_possible_score_in_pool
    for minimization (>= 0).
    """
    sel = np.array(selected_scores, dtype=float)
    best = np.array(best_pool_scores, dtype=float)
    abs_regret = sel - best
    rel_regret = np.where(best > 0, abs_regret / best, 0.0) * 100.0

    return {
        "mean_absolute_regret": round(float(np.mean(abs_regret)), 4),
        "median_absolute_regret": round(float(np.median(abs_regret)), 4),
        "max_absolute_regret": round(float(np.max(abs_regret)), 4),
        "mean_relative_regret_pct": round(float(np.mean(rel_regret)), 2),
        "zero_regret_rate": round(float(np.mean(abs_regret <= 1e-6)), 4)
    }


def classify_stage2_outcome(
    gc_comp: Dict[str, Any],
    pfsp_comp: Dict[str, Any],
    gc_practical_margin: float,
    pfsp_practical_margin: float,
    alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Classifies overall experiment according to Section 26:
    - Strong positive: D beats B on both core problems.
    - Narrow positive: D beats B meaningfully on only one core problem.
    - Negative: D performs worse than B.
    - No meaningful advantage: CI lies inside practical equivalence margin [-margin, +margin].
    - Inconclusive: quality gates or integrity failures.
    """
    def check_problem_verdict(comp, margin):
        ci_low, ci_high = comp["bootstrap_ci_95"]
        mean_diff = comp["mean_diff"]
        p_corr = comp["p_value_corrected"]

        # Check equivalence
        if -margin <= ci_low and ci_high <= margin:
            return "NO_MEANINGFUL_ADVANTAGE"

        # Check positive
        if p_corr < alpha and mean_diff < -1e-6 and ci_high < 0 and abs(mean_diff) >= margin:
            return "POSITIVE"

        # Check negative
        if p_corr < alpha and mean_diff > 1e-6 and ci_low > 0 and mean_diff >= margin:
            return "NEGATIVE"

        return "INCONCLUSIVE_OR_MARGINAL"

    gc_verdict = check_problem_verdict(gc_comp, gc_practical_margin)
    pfsp_verdict = check_problem_verdict(pfsp_comp, pfsp_practical_margin)

    if gc_verdict == "POSITIVE" and pfsp_verdict == "POSITIVE":
        overall = "STRONG_POSITIVE"
        desc = "D beats B on both core problems with statistical significance and practical margin."
    elif (gc_verdict == "POSITIVE" and pfsp_verdict != "POSITIVE") or (gc_verdict != "POSITIVE" and pfsp_verdict == "POSITIVE"):
        overall = "NARROW_POSITIVE"
        desc = f"D beats B on only one core problem (GC={gc_verdict}, PFSP={pfsp_verdict})."
    elif gc_verdict == "NEGATIVE" or pfsp_verdict == "NEGATIVE":
        overall = "NEGATIVE"
        desc = f"D performs significantly worse than B (GC={gc_verdict}, PFSP={pfsp_verdict})."
    elif gc_verdict == "NO_MEANINGFUL_ADVANTAGE" and pfsp_verdict == "NO_MEANINGFUL_ADVANTAGE":
        overall = "NO_MEANINGFUL_ADVANTAGE"
        desc = "The bootstrap confidence intervals for D - B lie entirely within the practical equivalence margins."
    else:
        overall = "INCONCLUSIVE"
        desc = f"Insufficient statistical separation or borderline effects (GC={gc_verdict}, PFSP={pfsp_verdict})."

    return {
        "overall_classification": overall,
        "description": desc,
        "graph_coloring_verdict": gc_verdict,
        "pfsp_verdict": pfsp_verdict
    }
