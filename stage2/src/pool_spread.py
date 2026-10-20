"""
Stage 2: Pool Spread Metric & Variance Gate
===========================================
Enforces Section 9:
Calculates the pre-registered pool spread metrics on candidate dev scores:
- pool mean
- pool median
- pool standard deviation
- pool min
- pool max
- pool coefficient of variation (CV = std / mean)
- pool relative range ((max - min) / mean)
- number of unique scores
- best-vs-mean gap
- best-vs-worst gap

Verifies whether the candidate pool meets the pre-registered spread threshold gate.
Fails closed if the threshold is missing or breached.
"""

import math
from typing import List, Dict, Any, Tuple
import numpy as np


class PoolSpreadAnalyzer:
    def __init__(
        self,
        min_unique_scores: int = 3,
        min_cv: float = 0.01,
        min_relative_range: float = 0.02
    ):
        self.min_unique_scores = min_unique_scores
        self.min_cv = min_cv
        self.min_relative_range = min_relative_range

    def analyze_pool(self, scores: List[float], pool_name: str = "pool") -> Dict[str, Any]:
        """
        Analyzes the spread of scores for a 20-candidate pool on dev data.
        Lower scores are better (minimization: colors or makespan).
        """
        if not scores:
            return {
                "pool_name": pool_name,
                "n_candidates": 0,
                "valid": False,
                "error": "Empty score list"
            }

        valid_scores = [s for s in scores if s < 900000]
        if len(valid_scores) < 2:
            return {
                "pool_name": pool_name,
                "n_candidates": len(scores),
                "valid_count": len(valid_scores),
                "valid_candidates": len(valid_scores),
                "mean": float(np.mean(valid_scores)) if valid_scores else 999999.0,
                "median": float(np.median(valid_scores)) if valid_scores else 999999.0,
                "std": 0.0,
                "min": min(valid_scores) if valid_scores else 999999.0,
                "max": max(valid_scores) if valid_scores else 999999.0,
                "coefficient_of_variation": 0.0,
                "relative_range": 0.0,
                "unique_scores": len(set(valid_scores)),
                "best_vs_mean_gap": 0.0,
                "best_vs_worst_gap": 0.0,
                "passes_unique_gate": False,
                "passes_cv_gate": False,
                "passes_range_gate": False,
                "gate_passed": False,
                "is_spread_valid": False,
                "reason": "Fewer than 2 valid candidates in pool"
            }

        arr = np.array(valid_scores, dtype=float)
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        std_val = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        
        cv_val = std_val / mean_val if mean_val > 0 else 0.0
        rel_range = (max_val - min_val) / mean_val if mean_val > 0 else 0.0
        unique_scores_count = len(set(valid_scores))
        
        # Minimization gaps (best is min_val):
        best_vs_mean_gap = mean_val - min_val
        best_vs_worst_gap = max_val - min_val

        # Gate verification
        passes_unique = unique_scores_count >= self.min_unique_scores
        passes_cv = cv_val >= self.min_cv
        passes_range = rel_range >= self.min_relative_range

        is_spread_valid = passes_unique and (passes_cv or passes_range)

        return {
            "pool_name": pool_name,
            "n_candidates": len(scores),
            "valid_candidates": len(valid_scores),
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std": round(std_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "coefficient_of_variation": round(cv_val, 6),
            "relative_range": round(rel_range, 6),
            "unique_scores": unique_scores_count,
            "best_vs_mean_gap": round(best_vs_mean_gap, 4),
            "best_vs_worst_gap": round(best_vs_worst_gap, 4),
            "passes_unique_gate": passes_unique,
            "passes_cv_gate": passes_cv,
            "passes_range_gate": passes_range,
            "gate_passed": is_spread_valid,
            "is_spread_valid": is_spread_valid
        }
