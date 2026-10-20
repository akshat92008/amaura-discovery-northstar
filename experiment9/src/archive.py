"""
Experiment #9: Unstructured Quality-Diversity Archive with Local Competition
=============================================================================
Parameters (FROZEN):
    delta_min = 0.20
    max_archive_size = 10

Implements:
- Nearest-neighbor behavioral niche matching via mean Kendall-Tau distance
- Local competition: replaces incumbent elite if quality (makespan) is strictly lower
- Novelty admission: adds candidate if distance to all elites >= delta_min
- Deterministic density pruning: when size > 10, removes the worse-scoring member
  of the mutually closest pair of elites
- Reference selection: Global champion + maximally behaviorally distant elite
"""

from typing import List, Dict, Any, Tuple, Optional
from experiment9.src.kendall import mean_behavioral_distance


class QDArchive:
    def __init__(self, delta_min: float = 0.20, max_archive_size: int = 10):
        self.delta_min = delta_min
        self.max_archive_size = max_archive_size
        self.elites: List[Dict[str, Any]] = []

    def size(self) -> int:
        return len(self.elites)

    def get_champion(self) -> Optional[Dict[str, Any]]:
        """Returns the elite with the lowest development makespan."""
        if not self.elites:
            return None
        return min(self.elites, key=lambda e: e["development_score"])

    def add_candidate(self, candidate: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        Attempts to insert a candidate into the QD archive.
        Candidate must contain:
            'candidate_id': str
            'code': str
            'development_score': int (makespan)
            'behavior_signature': list[list[int]] (permutations across dev instances)
            'runtime_ms': float
            'validity': bool
            
        Returns:
            (is_accepted: bool, reason: str, min_distance: float)
        """
        if not candidate.get("validity", False) or candidate.get("development_score", 999999) >= 999999:
            return False, "invalid_candidate", 0.0

        if not self.elites:
            self.elites.append(candidate)
            return True, "seeded_first_elite", 1.0

        # Calculate behavioral distance to all existing elites
        distances = []
        for e in self.elites:
            d = mean_behavioral_distance(candidate["behavior_signature"], e["behavior_signature"])
            distances.append((d, e))

        min_dist, nearest_elite = min(distances, key=lambda x: x[0])

        if min_dist < self.delta_min:
            # Belongs to existing behavioral niche: local competition
            if candidate["development_score"] < nearest_elite["development_score"]:
                self.elites.remove(nearest_elite)
                self.elites.append(candidate)
                return True, "replaced_niche_incumbent", min_dist
            else:
                return False, "rejected_niche_dominated", min_dist
        else:
            # Genuinely novel behavior: add to archive
            self.elites.append(candidate)
            pruned_id = None
            if len(self.elites) > self.max_archive_size:
                pruned_id = self._prune_densest_niche()
            return True, f"added_novel_elite (pruned: {pruned_id})" if pruned_id else "added_novel_elite", min_dist

    def _prune_densest_niche(self) -> str:
        """
        Deterministically prunes the archive down to max_archive_size:
        1. Finds the pair of elites (Ei, Ej) with the minimum mutual behavioral distance.
        2. Prunes the member with the higher (worse) development score.
        3. Ties broken by keeping the more recently discovered candidate.
        """
        n = len(self.elites)
        min_pair_dist = float("inf")
        worst_pair = (None, None)

        for i in range(n):
            for j in range(i + 1, n):
                dist = mean_behavioral_distance(
                    self.elites[i]["behavior_signature"], 
                    self.elites[j]["behavior_signature"]
                )
                if dist < min_pair_dist:
                    min_pair_dist = dist
                    worst_pair = (self.elites[i], self.elites[j])

        e1, e2 = worst_pair
        # Prune the one with worse makespan
        if e1["development_score"] > e2["development_score"]:
            victim = e1
        elif e2["development_score"] > e1["development_score"]:
            victim = e2
        else:
            # Tie: prune the earlier one
            victim = e1

        self.elites.remove(victim)
        return victim["candidate_id"]

    def select_references(self) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Selects two reference elites for Condition C prompting:
        Reference 1: Global development champion (lowest makespan).
        Reference 2: Archived elite that has maximum behavioral distance from Reference 1.
        """
        if not self.elites:
            raise ValueError("Cannot select references from empty archive.")

        champ = min(self.elites, key=lambda e: e["development_score"])
        if len(self.elites) == 1:
            return champ, None

        # Find elite with maximum distance to champion
        distant_elite = max(
            self.elites,
            key=lambda e: mean_behavioral_distance(e["behavior_signature"], champ["behavior_signature"])
        )
        return champ, distant_elite
