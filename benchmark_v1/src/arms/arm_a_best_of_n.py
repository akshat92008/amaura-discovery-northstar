"""
Arm A — Independent Best-of-N (Control)
=======================================
Implements strictly independent candidate sampling with zero feedback.
Earlier candidate scores, winners, or failures are NEVER fed back into subsequent prompts.
Evaluates every candidate against the training set and selects the best.
"""

from typing import Dict, Any, List, Optional
import time

from benchmark_v1.src.arms.base import SearchArm, SearchCandidate, TrajectoryProgress
from benchmark_v1.src.domains.base import ProblemDomain


class ArmABestOfN(SearchArm):
    def __init__(self, domain: ProblemDomain, generator):
        super().__init__("arm_a_best_of_n", domain, generator)

    def run_trajectory(
        self,
        trajectory_id: int,
        proposal_budget: int,
        initial_seeds: List[Dict[str, Any]],
        rng_seed: int
    ) -> TrajectoryProgress:
        proposals: List[SearchCandidate] = []
        best_so_far_curve: List[float] = []
        best_so_far_gap_curve: List[float] = []

        best_cand: Optional[SearchCandidate] = None
        best_score = float("inf")
        best_gap = float("inf")

        # 1. Baseline seeds initialization (does not consume generation slots)
        for s in initial_seeds:
            cand = SearchCandidate(
                candidate_id=f"arm_a_seed_{s['name']}",
                code=s["code"],
                description=s.get("description", "Canonical seed"),
                arm_name=self.name,
                trajectory_id=trajectory_id,
                proposal_index=-1,
                is_seed=True
            )
            eval_res = self.domain.evaluate(cand.code, split="train")
            cand.train_eval = eval_res
            if eval_res.is_valid and eval_res.raw_score < best_score:
                best_score = eval_res.raw_score
                best_gap = eval_res.relative_gap
                best_cand = cand

        # 2. Exactly proposal_budget independent generation slots
        for proposal_idx in range(proposal_budget):
            code, desc, hyp = self.generator.generate_independent(
                domain=self.domain,
                trajectory_id=trajectory_id,
                proposal_idx=proposal_idx,
                seed=rng_seed
            )
            cand = SearchCandidate(
                candidate_id=f"arm_a_t{trajectory_id}_p{proposal_idx}",
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

            if eval_res.is_valid and eval_res.raw_score < best_score:
                best_score = eval_res.raw_score
                best_gap = eval_res.relative_gap
                best_cand = cand

            best_so_far_curve.append(best_score)
            best_so_far_gap_curve.append(best_gap)
            proposal_idx += 1

        assert best_cand is not None, "At least one candidate must be evaluated"
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
