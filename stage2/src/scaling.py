"""
Stage 2: Deterministic Subsampling Scaling Engine
=================================================
Enforces Section 22:
Estimates the search-budget scaling curve for N in {1, 2, 5, 10, 20}
using deterministic seeded subsampling of the already-generated 20-candidate pools.
ZERO extra generation calls.
"""

import random
from typing import List, Dict, Any, Tuple
import numpy as np


class SubsamplingScalingEngine:
    def __init__(self, n_levels: List[int] = None):
        self.n_levels = n_levels or [1, 2, 5, 10, 20]

    def evaluate_scaling(
        self,
        candidate_pool: List[Dict[str, Any]],
        selection_key: str = "dev_score",
        evaluation_key: str = "hidden_score",
        seed: int = 42,
        num_resamples: int = 50
    ) -> Dict[int, Dict[str, float]]:
        """
        For each budget level N, draws random sub-pools of size N, applies the selection rule
        (picking best candidate by selection_key on dev data), and evaluates the selected candidate on hidden data.
        """
        results: Dict[int, Dict[str, float]] = {}
        pool_size = len(candidate_pool)
        if pool_size < 20:
            raise ValueError(f"Pool size must be at least 20, got {pool_size}")

        rng = random.Random(seed)

        for n in self.n_levels:
            if n > pool_size:
                continue

            scores = []
            for _ in range(num_resamples):
                # Deterministic sample of size n without replacement
                sub_pool = rng.sample(candidate_pool, n)
                # Select best candidate by selection_key (minimization)
                best_cand = min(sub_pool, key=lambda c: c.get(selection_key, float("inf")))
                scores.append(best_cand.get(evaluation_key, float("inf")))

            valid_scores = [s for s in scores if s < 900000]
            if valid_scores:
                mean_score = float(np.mean(valid_scores))
                std_score = float(np.std(valid_scores, ddof=1)) if len(valid_scores) > 1 else 0.0
                median_score = float(np.median(valid_scores))
            else:
                mean_score, std_score, median_score = 999999.0, 0.0, 999999.0

            results[n] = {
                "budget_n": n,
                "mean_hidden_score": round(mean_score, 4),
                "std_hidden_score": round(std_score, 4),
                "median_hidden_score": round(median_score, 4),
                "sample_runs": len(scores)
            }

        return results
