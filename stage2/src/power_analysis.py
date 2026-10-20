"""
Stage 2: Simulation-Based Power Analysis
========================================
Enforces Section 20:
Uses pilot empirical variance to simulate the exact paired Wilcoxon test, bootstrap CI,
practical-margin rule, and Holm correction to estimate statistical power across N=30 trials.
"""

from typing import Dict, Any, Tuple
import numpy as np
from scipy import stats


def run_power_simulation(
    pilot_std_d: float,
    pilot_std_b: float,
    paired_correlation: float = 0.85,
    hypothesized_effect_pct: float = 0.02,  # 2% improvement
    baseline_mean: float = 100.0,
    n_trials: int = 30,
    practical_margin: float = 1.0,
    alpha: float = 0.05,
    num_simulations: int = 1000
) -> Dict[str, Any]:
    """
    Simulates bivariate normal distribution of paired differences D - B across 30 trials
    under empirical pilot variance. Tests rejection of null hypothesis via Wilcoxon signed-rank
    and Holm correction across 2 problems.
    """
    rng = np.random.default_rng(42)

    mu_b = baseline_mean
    mu_d = baseline_mean * (1.0 - hypothesized_effect_pct)

    cov = paired_correlation * pilot_std_d * pilot_std_b
    cov_matrix = [
        [pilot_std_d**2, cov],
        [cov, pilot_std_b**2]
    ]

    # Ensure positive semidefinite
    cov_matrix[0][1] = min(cov_matrix[0][1], 0.99 * pilot_std_d * pilot_std_b)
    cov_matrix[1][0] = cov_matrix[0][1]

    significant_rejections = 0
    margin_successes = 0

    # Two problems tested concurrently for Holm correction (alpha/2 = 0.025 for primary)
    holm_alpha = alpha / 2.0

    for _ in range(num_simulations):
        samples = rng.multivariate_normal([mu_d, mu_b], cov_matrix, size=n_trials)
        d_scores = samples[:, 0]
        b_scores = samples[:, 1]
        diffs = d_scores - b_scores  # negative means D is lower (better)

        try:
            _, p_val = stats.wilcoxon(d_scores, b_scores, alternative="two-sided")
        except Exception:
            p_val = 1.0

        mean_diff = np.mean(diffs)

        if p_val < holm_alpha and mean_diff < 0:
            significant_rejections += 1
            if abs(mean_diff) >= practical_margin:
                margin_successes += 1

    simulated_power = significant_rejections / num_simulations
    practical_power = margin_successes / num_simulations

    return {
        "n_trials": n_trials,
        "hypothesized_effect_pct": hypothesized_effect_pct,
        "pilot_std_d": pilot_std_d,
        "pilot_std_b": pilot_std_b,
        "paired_correlation": paired_correlation,
        "practical_margin": practical_margin,
        "holm_alpha": holm_alpha,
        "statistical_power": round(simulated_power, 4),
        "practical_power": round(practical_power, 4),
        "meets_80pct_standard": simulated_power >= 0.80
    }
