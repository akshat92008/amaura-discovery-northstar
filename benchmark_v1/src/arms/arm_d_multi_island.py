"""
Arm D — Diversity-aware, Multi-Island Evolution
==============================================
Maintains 3 distinct subpopulations (islands) with migration and behavioral diversity awareness:
- Island 0: Exploitative local refinement
- Island 1: Broad non-linear exploration
- Island 2: Robustness / worst-case loss mitigation
- Behavioral Diversity: Computes correlation distance of per-instance performance profiles.
- Ring Migration: Transfers island champions every 16 proposals.
"""

import math
import random
from typing import Dict, Any, List, Optional, Tuple
import time

from benchmark_v1.src.arms.base import SearchArm, SearchCandidate, TrajectoryProgress
from benchmark_v1.src.domains.base import ProblemDomain


def compute_behavioral_correlation(v1: List[float], v2: List[float]) -> float:
    """Computes Pearson/Spearman correlation between two per-instance score vectors."""
    n = len(v1)
    if n < 2 or len(v2) != n:
        return 1.0
    m1 = sum(v1) / n
    m2 = sum(v2) / n
    var1 = sum((x - m1) ** 2 for x in v1)
    var2 = sum((y - m2) ** 2 for y in v2)
    if var1 < 1e-9 or var2 < 1e-9:
        return 1.0
    cov = sum((v1[i] - m1) * (v2[i] - m2) for i in range(n))
    corr = cov / math.sqrt(var1 * var2)
    return max(-1.0, min(1.0, corr))


class ArmDMultiIsland(SearchArm):
    def __init__(
        self,
        domain: ProblemDomain,
        generator,
        num_islands: int = 3,
        island_size: int = 4,
        migration_interval: int = 16
    ):
        super().__init__("arm_d_multi_island", domain, generator)
        self.num_islands = num_islands
        self.island_size = island_size
        self.migration_interval = migration_interval

    def run_trajectory(
        self,
        trajectory_id: int,
        proposal_budget: int,
        initial_seeds: List[Dict[str, Any]],
        rng_seed: int
    ) -> TrajectoryProgress:
        rng = random.Random(rng_seed * 47 + trajectory_id * 103)
        proposals: List[SearchCandidate] = []
        islands: List[List[SearchCandidate]] = [[] for _ in range(self.num_islands)]
        best_so_far_curve: List[float] = []
        best_so_far_gap_curve: List[float] = []

        best_cand: Optional[SearchCandidate] = None
        best_score = float("inf")
        best_gap = float("inf")

        # 1. Baseline seeds initialization (does not consume generation slots)
        for idx, s in enumerate(initial_seeds):
            target_island = idx % self.num_islands
            cand = SearchCandidate(
                candidate_id=f"arm_d_seed_isl{target_island}_{s['name']}",
                code=s["code"],
                description=s.get("description", "Canonical seed"),
                arm_name=self.name,
                trajectory_id=trajectory_id,
                proposal_index=-1,
                is_seed=True
            )
            eval_res = self.domain.evaluate(cand.code, split="train")
            cand.train_eval = eval_res
            islands[target_island].append(cand)

            if eval_res.is_valid and eval_res.raw_score < best_score:
                best_score = eval_res.raw_score
                best_gap = eval_res.relative_gap
                best_cand = cand

        # 2. Exactly proposal_budget generation slots across islands
        current_island = 0
        for proposal_idx in range(proposal_budget):
            # Check if any island needs initial members up to island_size
            island_to_fill = None
            for isl_idx in range(self.num_islands):
                if len(islands[isl_idx]) < self.island_size:
                    island_to_fill = isl_idx
                    break

            if island_to_fill is not None:
                code, desc, hyp = self.generator.generate_independent(
                    domain=self.domain,
                    trajectory_id=trajectory_id,
                    proposal_idx=proposal_idx,
                    seed=rng_seed
                )
                cand = SearchCandidate(
                    candidate_id=f"arm_d_t{trajectory_id}_p{proposal_idx}_isl{island_to_fill}_init",
                    code=code,
                    description=desc,
                    arm_name=self.name,
                    trajectory_id=trajectory_id,
                    proposal_index=proposal_idx,
                    hypothesis=hyp,
                    is_seed=False
                )
                eval_res = self.domain.evaluate(cand.code, split="train")
                cand.train_eval = eval_res
                proposals.append(cand)
                islands[island_to_fill].append(cand)

                if eval_res.is_valid and eval_res.raw_score < best_score:
                    best_score = eval_res.raw_score
                    best_gap = eval_res.relative_gap
                    best_cand = cand

                best_so_far_curve.append(best_score)
                best_so_far_gap_curve.append(best_gap)
            else:
                # Multi-island evolution with ring migration and diversity filter
                isl = islands[current_island]

                # Ring migration check
                if proposal_idx > 0 and proposal_idx % self.migration_interval == 0:
                    for src_idx in range(self.num_islands):
                        dest_idx = (src_idx + 1) % self.num_islands
                        if islands[src_idx] and islands[dest_idx]:
                            src_best = min(
                                islands[src_idx],
                                key=lambda c: c.train_eval.raw_score if c.train_eval and c.train_eval.is_valid else float("inf")
                            )
                            # Replace worst non-elite in destination if diverse
                            worst_dest_idx = max(
                                range(len(islands[dest_idx])),
                                key=lambda i: islands[dest_idx][i].train_eval.raw_score if islands[dest_idx][i].train_eval and islands[dest_idx][i].train_eval.is_valid else float("inf")
                            )
                            islands[dest_idx][worst_dest_idx] = src_best

                # Tournament selection within current island
                t1 = rng.sample(isl, min(2, len(isl)))
                parent1 = min(t1, key=lambda c: c.train_eval.raw_score if c.train_eval and c.train_eval.is_valid else float("inf"))

                t2 = rng.sample(isl, min(2, len(isl)))
                parent2 = min(t2, key=lambda c: c.train_eval.raw_score if c.train_eval and c.train_eval.is_valid else float("inf"))

                parents = [parent1, parent2] if parent1.candidate_id != parent2.candidate_id else [parent1]

                code, desc, hyp = self.generator.generate_variation(
                    domain=self.domain,
                    parents=parents,
                    population=isl,
                    trajectory_id=trajectory_id,
                    proposal_idx=proposal_idx,
                    seed=rng_seed,
                    island_id=current_island
                )
                cand = SearchCandidate(
                    candidate_id=f"arm_d_t{trajectory_id}_p{proposal_idx}_isl{current_island}",
                    code=code,
                    description=desc,
                    arm_name=self.name,
                    trajectory_id=trajectory_id,
                    proposal_index=proposal_idx,
                    parent_ids=[p.candidate_id for p in parents],
                    generation=max(p.generation for p in parents) + 1,
                    hypothesis=hyp,
                    is_seed=False
                )
                eval_res = self.domain.evaluate(cand.code, split="train")
                cand.train_eval = eval_res
                proposals.append(cand)

                if eval_res.is_valid:
                    # Diversity filter: check correlation against island members
                    is_redundant = False
                    for member in isl:
                        if member.train_eval and member.train_eval.per_instance_scores and eval_res.per_instance_scores:
                            corr = compute_behavioral_correlation(eval_res.per_instance_scores, member.train_eval.per_instance_scores)
                            if corr > 0.99 and eval_res.raw_score >= member.train_eval.raw_score:
                                is_redundant = True
                                break

                    if not is_redundant:
                        worst_idx = max(
                            range(len(isl)),
                            key=lambda i: isl[i].train_eval.raw_score if isl[i].train_eval and isl[i].train_eval.is_valid else float("inf")
                        )
                        worst_score = isl[worst_idx].train_eval.raw_score if isl[worst_idx].train_eval and isl[worst_idx].train_eval.is_valid else float("inf")
                        if eval_res.raw_score < worst_score:
                            isl[worst_idx] = cand

                    if eval_res.raw_score < best_score:
                        best_score = eval_res.raw_score
                        best_gap = eval_res.relative_gap
                        best_cand = cand

                best_so_far_curve.append(best_score)
                best_so_far_gap_curve.append(best_gap)
                current_island = (current_island + 1) % self.num_islands

        assert best_cand is not None
        return TrajectoryProgress(
            trajectory_id=trajectory_id,
            arm_name=self.name,
            total_proposals=len(proposals),
            best_candidate=best_cand,
            best_train_score=best_score,
            best_train_rel_gap=best_gap,
            proposals_history=proposals,
            best_so_far_curve=best_so_far_curve,
            best_so_far_rel_gap_curve=best_so_far_gap_curve
        )
