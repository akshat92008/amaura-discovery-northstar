"""
Arm C — Standard Population-based Evolution
==========================================
Maintains a candidate population (P=10).
Uses tournament selection (k=2) to choose parents, generates mutations or combinations,
evaluates offspring, and applies steady-state replacement with elitism.
"""

import random
from typing import Dict, Any, List, Optional
import time

from benchmark_v1.src.arms.base import SearchArm, SearchCandidate, TrajectoryProgress
from benchmark_v1.src.domains.base import ProblemDomain


class ArmCEvolution(SearchArm):
    def __init__(self, domain: ProblemDomain, generator, population_size: int = 10):
        super().__init__("arm_c_evolution", domain, generator)
        self.population_size = population_size

    def run_trajectory(
        self,
        trajectory_id: int,
        proposal_budget: int,
        initial_seeds: List[Dict[str, Any]],
        rng_seed: int
    ) -> TrajectoryProgress:
        rng = random.Random(rng_seed * 31 + trajectory_id * 101)
        proposals: List[SearchCandidate] = []
        population: List[SearchCandidate] = []
        best_so_far_curve: List[float] = []
        best_so_far_gap_curve: List[float] = []

        best_cand: Optional[SearchCandidate] = None
        best_score = float("inf")
        best_gap = float("inf")

        # 1. Baseline seeds initialization (does not consume generation slots)
        for s in initial_seeds:
            cand = SearchCandidate(
                candidate_id=f"arm_c_seed_{s['name']}",
                code=s["code"],
                description=s.get("description", "Canonical seed"),
                arm_name=self.name,
                trajectory_id=trajectory_id,
                proposal_index=-1,
                is_seed=True
            )
            eval_res = self.domain.evaluate(cand.code, split="train")
            cand.train_eval = eval_res
            population.append(cand)

            if eval_res.is_valid and eval_res.raw_score < best_score:
                best_score = eval_res.raw_score
                best_gap = eval_res.relative_gap
                best_cand = cand

        # 2. Exactly proposal_budget generation slots
        for proposal_idx in range(proposal_budget):
            # If population < population_size, fill using independent samples
            if len(population) < self.population_size:
                code, desc, hyp = self.generator.generate_independent(
                    domain=self.domain,
                    trajectory_id=trajectory_id,
                    proposal_idx=proposal_idx,
                    seed=rng_seed
                )
                cand = SearchCandidate(
                    candidate_id=f"arm_c_t{trajectory_id}_p{proposal_idx}_init",
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
                population.append(cand)

                if eval_res.is_valid and eval_res.raw_score < best_score:
                    best_score = eval_res.raw_score
                    best_gap = eval_res.relative_gap
                    best_cand = cand

                best_so_far_curve.append(best_score)
                best_so_far_gap_curve.append(best_gap)
            else:
                # Evolution loop: tournament selection + variation + replacement
                t1 = rng.sample(population, min(2, len(population)))
                parent1 = min(t1, key=lambda c: c.train_eval.raw_score if c.train_eval and c.train_eval.is_valid else float("inf"))

                t2 = rng.sample(population, min(2, len(population)))
                parent2 = min(t2, key=lambda c: c.train_eval.raw_score if c.train_eval and c.train_eval.is_valid else float("inf"))

                parents = [parent1, parent2] if parent1.candidate_id != parent2.candidate_id else [parent1]

                code, desc, hyp = self.generator.generate_variation(
                    domain=self.domain,
                    parents=parents,
                    population=population,
                    trajectory_id=trajectory_id,
                    proposal_idx=proposal_idx,
                    seed=rng_seed
                )
                cand = SearchCandidate(
                    candidate_id=f"arm_c_t{trajectory_id}_p{proposal_idx}",
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

                # Replacement rule: replace the worst member of population if valid and strictly better
                if eval_res.is_valid:
                    worst_idx = max(
                        range(len(population)),
                        key=lambda i: population[i].train_eval.raw_score if population[i].train_eval and population[i].train_eval.is_valid else float("inf")
                    )
                    worst_score = population[worst_idx].train_eval.raw_score if population[worst_idx].train_eval and population[worst_idx].train_eval.is_valid else float("inf")

                    if eval_res.raw_score < worst_score:
                        population[worst_idx] = cand

                    if eval_res.raw_score < best_score:
                        best_score = eval_res.raw_score
                        best_gap = eval_res.relative_gap
                        best_cand = cand

                best_so_far_curve.append(best_score)
                best_so_far_gap_curve.append(best_gap)

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
