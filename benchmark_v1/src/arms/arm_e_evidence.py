"""
Arm E — Evidence-guided Search
=============================
Uses concrete instance-level diagnostic evidence (worst-case failures, excess loss vs baseline)
and requires candidate proposals to formulate a concrete improvement hypothesis before code changes.
"""

from typing import Dict, Any, List, Optional
import time

from benchmark_v1.src.arms.base import SearchArm, SearchCandidate, TrajectoryProgress
from benchmark_v1.src.domains.base import ProblemDomain


class ArmEEvidence(SearchArm):
    def __init__(self, domain: ProblemDomain, generator):
        super().__init__("arm_e_evidence", domain, generator)

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

        champion: Optional[SearchCandidate] = None
        best_score = float("inf")
        best_gap = float("inf")

        # 1. Baseline seeds initialization (does not consume generation slots)
        for s in initial_seeds:
            cand = SearchCandidate(
                candidate_id=f"arm_e_seed_{s['name']}",
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
                champion = cand

        assert champion is not None, "Champion must be initialized from seeds"

        # 2. Exactly proposal_budget evidence-guided generation slots
        for proposal_idx in range(proposal_budget):
            # Extract diagnostics from current champion
            diagnostics = champion.train_eval.diagnostics if champion.train_eval and champion.train_eval.diagnostics else {}

            code, desc, hyp = self.generator.generate_evidence_guided(
                domain=self.domain,
                champion=champion,
                diagnostics=diagnostics,
                trajectory_id=trajectory_id,
                proposal_idx=proposal_idx,
                seed=rng_seed
            )
            cand = SearchCandidate(
                candidate_id=f"arm_e_t{trajectory_id}_p{proposal_idx}",
                code=code,
                description=desc,
                arm_name=self.name,
                trajectory_id=trajectory_id,
                proposal_index=proposal_idx,
                parent_ids=[champion.candidate_id],
                generation=champion.generation + 1,
                hypothesis=hyp,
                is_seed=False
            )
            eval_res = self.domain.evaluate(cand.code, split="train")
            cand.train_eval = eval_res
            proposals.append(cand)

            if eval_res.is_valid and eval_res.raw_score < best_score:
                best_score = eval_res.raw_score
                best_gap = eval_res.relative_gap
                champion = cand

            best_so_far_curve.append(best_score)
            best_so_far_gap_curve.append(best_gap)

        return TrajectoryProgress(
            trajectory_id=trajectory_id,
            arm_name=self.name,
            total_proposals=len(proposals),
            best_candidate=champion,
            best_train_score=best_score,
            best_train_rel_gap=best_gap,
            proposals_history=proposals,
            best_so_far_curve=best_so_far_curve,
            best_so_far_rel_gap_curve=best_so_far_gap_curve
        )
