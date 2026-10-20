"""
Statistical Analysis and Hypothesis Testing Module
===================================================
Pre-registered inferential statistics for Benchmark V1:
- Paired Wilcoxon signed-rank test (two-sided).
- Holm-Bonferroni multiple testing correction.
- 10,000 resample bootstrap confidence intervals.
- Monte Carlo power analysis.
- Best-so-far curve aggregation.
"""

import math
import random
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import scipy.stats as st


def compute_bootstrap_ci(
    diffs: List[float],
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 404
) -> Tuple[float, float]:
    """Computes paired bootstrap confidence interval for the mean difference."""
    if not diffs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(diffs)
    boot_means = []
    for _ in range(n_resamples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    low_idx = int((alpha / 2.0) * n_resamples)
    high_idx = int((1.0 - alpha / 2.0) * n_resamples)
    return round(boot_means[low_idx], 6), round(boot_means[high_idx], 6)


def compute_paired_wilcoxon(diffs: List[float]) -> Tuple[float, float]:
    """
    Computes two-sided paired Wilcoxon signed-rank test on paired differences (Arm - Control).
    Returns (statistic, p_value).
    """
    clean_diffs = [d for d in diffs if abs(d) > 1e-9]
    if len(clean_diffs) < 5:
        # If nearly all differences are 0 or sample size is tiny
        if all(abs(d) < 1e-9 for d in diffs):
            return 0.0, 1.0
        return 0.0, 1.0

    try:
        res = st.wilcoxon(clean_diffs, alternative="two-sided")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        return 0.0, 1.0


def apply_holm_bonferroni(p_values: List[float]) -> List[float]:
    """
    Applies Holm-Bonferroni step-down correction to a list of p-values.
    Returns adjusted p-values in the original order.
    """
    m = len(p_values)
    if m == 0:
        return []

    # Sort indices by p-value
    sorted_indices = sorted(range(m), key=lambda i: p_values[i])
    adj = [0.0] * m

    cum_max = 0.0
    for rank, idx in enumerate(sorted_indices):
        factor = m - rank
        raw_p = p_values[idx]
        adj_p = min(1.0, raw_p * factor)
        cum_max = max(cum_max, adj_p)
        adj[idx] = cum_max

    return [round(p, 6) for p in adj]


def compute_power_simulation(
    effect_size: float = -0.01,
    std_dev: float = 0.015,
    sample_size: int = 20,
    alpha: float = 0.05,
    n_sims: int = 5000,
    seed: int = 404
) -> float:
    """
    Simulates statistical power of paired Wilcoxon signed-rank test
    to detect a given effect_size under standard deviation std_dev with sample_size trials.
    """
    rng = np.random.default_rng(seed)
    rejections = 0

    for _ in range(n_sims):
        # Sample paired differences from Normal(effect_size, std_dev)
        diffs = rng.normal(loc=effect_size, scale=std_dev, size=sample_size)
        try:
            res = st.wilcoxon(diffs, alternative="two-sided")
            if res.pvalue < alpha:
                rejections += 1
        except Exception:
            pass

    return round(rejections / n_sims, 4)


def aggregate_curves(curves: List[List[float]]) -> Dict[str, List[float]]:
    """Aggregates best-so-far curves across trials (mean, median, p25, p75)."""
    if not curves:
        return {"mean": [], "median": [], "p25": [], "p75": []}

    min_len = min(len(c) for c in curves)
    arr = np.array([c[:min_len] for c in curves])

    return {
        "mean": [round(float(x), 6) for x in np.mean(arr, axis=0)],
        "median": [round(float(x), 6) for x in np.median(arr, axis=0)],
        "p25": [round(float(x), 6) for x in np.percentile(arr, 25, axis=0)],
        "p75": [round(float(x), 6) for x in np.percentile(arr, 75, axis=0)]
    }


def compute_descriptive_stats(values: List[float]) -> Dict[str, float]:
    """Computes standard summary statistics for a metric series."""
    if not values:
        return {"mean": 0.0, "median": 0.0, "std": 0.0, "iqr": 0.0, "min": 0.0, "max": 0.0}

    arr = np.array(values)
    q25, q75 = np.percentile(arr, [25, 75])
    return {
        "mean": round(float(np.mean(arr)), 6),
        "median": round(float(np.median(arr)), 6),
        "std": round(float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0, 6),
        "iqr": round(float(q75 - q25), 6),
        "min": round(float(np.min(arr)), 6),
        "max": round(float(np.max(arr)), 6)
    }
