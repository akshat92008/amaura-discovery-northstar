"""
Stage 3: Search-Efficiency & Best-So-Far Curve Engine
=====================================================
Calculates and records best development chromatic scores as a function of
candidate-generation budget:
    k in {1, 5, 10, 20, 50, 100}

Guarantees:
- Arm A's curve is strictly retrospective and descriptive.
- Evaluates valid candidates only; if no valid candidate is found by budget k, score is None.
- Tracks generational trajectories across all 3 arms.
"""

from typing import Dict, Any, List, Optional


CHECKPOINTS = [1, 5, 10, 20, 50, 100]


def compute_best_so_far_curve(candidates: List[Dict[str, Any]]) -> Dict[int, Optional[int]]:
    """
    Given a list of candidate records sorted by global_candidate_index (1..100),
    computes the best development score achieved up to each checkpoint k in {1, 5, 10, 20, 50, 100}.
    """
    sorted_cands = sorted(candidates, key=lambda c: c.get("global_candidate_index", 0))
    curve: Dict[int, Optional[int]] = {}

    for k in CHECKPOINTS:
        prefix = sorted_cands[:k]
        valid_scores = [
            c["development_score"]
            for c in prefix
            if c.get("validity") and c.get("development_score") is not None
        ]
        curve[k] = min(valid_scores) if valid_scores else None

    return curve


def analyze_trial_trajectories(
    trial_id: int,
    cands_a: List[Dict[str, Any]],
    cands_b: List[Dict[str, Any]],
    cands_c: List[Dict[str, Any]]
) -> Dict[str, Any]:
    curve_a = compute_best_so_far_curve(cands_a)
    curve_b = compute_best_so_far_curve(cands_b)
    curve_c = compute_best_so_far_curve(cands_c)

    return {
        "trial_id": trial_id,
        "checkpoints": CHECKPOINTS,
        "Arm_A_Independent_Best_of_N": {
            "curve": {str(k): v for k, v in curve_a.items()},
            "nature": "Retrospective and descriptive; does not represent adaptive behavior."
        },
        "Arm_B_Blind_Iterative": {
            "curve": {str(k): v for k, v in curve_b.items()},
            "nature": "Textual context history only; zero execution feedback."
        },
        "Arm_C_Amaura": {
            "curve": {str(k): v for k, v in curve_c.items()},
            "nature": "Adaptive execution-feedback-driven discovery."
        }
    }
