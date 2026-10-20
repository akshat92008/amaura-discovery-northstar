"""
Experiment Runner and Width-vs-Depth Execution Engine
=====================================================
Orchestrates Search Strategy Benchmark V1 trials under strictly matched proposal budgets:
- Allocations:
  * 1 trajectory (Depth): 1 x Budget proposals
  * 4 trajectories (Width 4): 4 x (Budget / 4) proposals
  * 8 trajectories (Width 8): 8 x (Budget / 8) proposals
- Proposal Accounting: every generated proposal attempt counts toward the budget.
- Evaluation Firewall: Candidate selection is performed EXCLUSIVELY on training data.
  The sealed held-out test set is unsealed only after selection is frozen to measure generalization.
"""

from dataclasses import dataclass, asdict
import json
import os
import tempfile
import time
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from typing import Dict, Any, List, Optional

from benchmark_v1.src.domains.base import ProblemDomain, DomainEvaluationResult
from benchmark_v1.src.domains.bin_packing import BinPackingDomain
from benchmark_v1.src.domains.graph_coloring import GraphColoringDomain
from benchmark_v1.src.domains.pfsp import PFSPDomain

from benchmark_v1.src.arms.base import SearchArm, SearchCandidate, TrajectoryProgress
from benchmark_v1.src.arms.generator import SimulatedMutator, LiveLLMGenerator
from benchmark_v1.src.arms.arm_a_best_of_n import ArmABestOfN
from benchmark_v1.src.arms.arm_b_refinement import ArmBRefinement
from benchmark_v1.src.arms.arm_c_evolution import ArmCEvolution
from benchmark_v1.src.arms.arm_d_multi_island import ArmDMultiIsland
from benchmark_v1.src.arms.arm_e_evidence import ArmEEvidence


def get_domain(name: str) -> ProblemDomain:
    if name == "bin_packing":
        return BinPackingDomain()
    elif name == "graph_coloring":
        return GraphColoringDomain()
    elif name == "pfsp":
        return PFSPDomain()
    raise ValueError(f"Unknown domain: {name}")


def create_arm(arm_name: str, domain: ProblemDomain, generator) -> SearchArm:
    if arm_name == "arm_a_best_of_n":
        return ArmABestOfN(domain, generator)
    elif arm_name == "arm_b_refinement":
        return ArmBRefinement(domain, generator)
    elif arm_name == "arm_c_evolution":
        return ArmCEvolution(domain, generator, population_size=10)
    elif arm_name == "arm_d_multi_island":
        return ArmDMultiIsland(domain, generator, num_islands=3, island_size=4, migration_interval=16)
    elif arm_name == "arm_e_evidence":
        return ArmEEvidence(domain, generator)
    raise ValueError(f"Unknown arm: {arm_name}")


@dataclass
class TrialConfig:
    trial_id: int
    domain_name: str
    arm_name: str
    total_budget: int
    num_trajectories: int
    seed: int
    generator_type: str = "simulated"


class BenchmarkRunner:
    def __init__(self, results_dir: Optional[str] = None):
        if results_dir is None:
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "results")
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)

    def execute_trial(self, config: TrialConfig) -> Dict[str, Any]:
        fname = f"trial_{config.trial_id:04d}_{config.domain_name}_{config.arm_name}_b{config.total_budget}_w{config.num_trajectories}_{config.generator_type}.json"
        target_path = os.path.join(self.results_dir, fname)
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        t0 = time.time()
        domain = get_domain(config.domain_name)

        if config.generator_type == "live_llm":
            query_log = os.path.join(self.results_dir, "llm_queries.jsonl")
            generator = LiveLLMGenerator(query_log_path=query_log)
        else:
            generator = SimulatedMutator(invalid_rate=0.04)

        arm = create_arm(config.arm_name, domain, generator)
        budget_per_traj = config.total_budget // config.num_trajectories
        assert budget_per_traj * config.num_trajectories == config.total_budget, (
            f"Budget {config.total_budget} must be divisible by num_trajectories {config.num_trajectories}"
        )

        trajectories_progress: List[TrajectoryProgress] = []
        all_proposals: List[SearchCandidate] = []
        global_best_candidate: Optional[SearchCandidate] = None
        global_best_train_score = float("inf")

        cumulative_curve: List[float] = []
        running_best_score = float("inf")

        for traj_idx in range(config.num_trajectories):
            traj_seed = config.seed * 1009 + traj_idx * 17
            prog = arm.run_trajectory(
                trajectory_id=traj_idx,
                proposal_budget=budget_per_traj,
                initial_seeds=domain.canonical_seeds,
                rng_seed=traj_seed
            )
            trajectories_progress.append(prog)
            all_proposals.extend(prog.proposals_history)

            # Update running cumulative curve across interleaved proposals
            for cand in prog.proposals_history:
                if cand.train_eval and cand.train_eval.is_valid and cand.train_eval.raw_score < running_best_score:
                    running_best_score = cand.train_eval.raw_score
                cumulative_curve.append(running_best_score)

            if prog.best_candidate and prog.best_train_score < global_best_train_score:
                global_best_train_score = prog.best_train_score
                global_best_candidate = prog.best_candidate

        assert global_best_candidate is not None, "A champion candidate must be selected"
        assert len(all_proposals) == config.total_budget, (
            f"Expected {config.total_budget} proposals, got {len(all_proposals)}"
        )

        # -------------------------------------------------------------
        # STRICT EVALUATION FIREWALL: Unseal held-out test set
        # -------------------------------------------------------------
        test_eval = domain.evaluate(global_best_candidate.code, split="test")
        global_best_candidate.test_eval = test_eval

        # Exploratory pilot validation evaluation
        pilot_val_eval = None
        if hasattr(domain, "pilot_val_streams") and domain.pilot_val_streams:
            pilot_val_eval = domain.evaluate(global_best_candidate.code, split="pilot_val")

        elapsed_sec = round(time.time() - t0, 3)

        # Candidate deduplication tracking
        seen_hashes = set()
        duplicates_count = 0
        for c in all_proposals:
            h = c.code_hash
            if h in seen_hashes:
                duplicates_count += 1
            seen_hashes.add(h)

        result_payload = {
            "trial_id": config.trial_id,
            "domain": config.domain_name,
            "arm": config.arm_name,
            "total_budget": config.total_budget,
            "num_trajectories": config.num_trajectories,
            "budget_per_trajectory": budget_per_traj,
            "seed": config.seed,
            "generator_type": config.generator_type,
            "elapsed_sec": elapsed_sec,
            "accounting": {
                "model_calls": len(all_proposals) if config.generator_type == "live_llm" else 0,
                "candidate_slots": len(all_proposals),
                "evaluator_runs": len(domain.canonical_seeds) + len(all_proposals) + (2 if pilot_val_eval else 1),
                "retries": 0,
                "invalid_outputs": sum(1 for c in all_proposals if not c.train_eval or not c.train_eval.is_valid),
                "duplicate_candidates": duplicates_count
            },
            "selection": {
                "candidate_id": global_best_candidate.candidate_id,
                "code": global_best_candidate.code,
                "description": global_best_candidate.description,
                "hypothesis": global_best_candidate.hypothesis,
                "is_seed": global_best_candidate.is_seed,
                "train_score": global_best_train_score,
                "train_rel_gap": global_best_candidate.train_eval.relative_gap if global_best_candidate.train_eval else None,
                "train_beats_baseline": global_best_candidate.train_eval.beats_baseline if global_best_candidate.train_eval else False,
            },
            "generalization_test": {
                "test_score": test_eval.raw_score,
                "test_avg_score": test_eval.avg_score,
                "test_rel_gap": test_eval.relative_gap,
                "test_beats_baseline": test_eval.beats_baseline,
                "test_is_valid": test_eval.is_valid,
                "test_runtime_ms": test_eval.runtime_ms
            },
            "pilot_validation": {
                "pilot_val_score": pilot_val_eval.raw_score if pilot_val_eval else None,
                "pilot_val_rel_gap": pilot_val_eval.relative_gap if pilot_val_eval else None,
                "pilot_val_beats_baseline": pilot_val_eval.beats_baseline if pilot_val_eval else False,
                "pilot_val_is_valid": pilot_val_eval.is_valid if pilot_val_eval else False,
                "pilot_val_runtime_ms": pilot_val_eval.runtime_ms if pilot_val_eval else None
            } if pilot_val_eval else None,
            "best_so_far_curve": cumulative_curve,
            "all_proposals": [
                {
                    "candidate_id": c.candidate_id,
                    "proposal_index": c.proposal_index,
                    "is_seed": c.is_seed,
                    "parent_ids": c.parent_ids,
                    "generation": c.generation,
                    "hypothesis": c.hypothesis,
                    "description": c.description,
                    "code": c.code,
                    "code_hash": c.code_hash,
                    "train_eval": {
                        "is_valid": c.train_eval.is_valid if c.train_eval else False,
                        "raw_score": c.train_eval.raw_score if c.train_eval else None,
                        "relative_gap": c.train_eval.relative_gap if c.train_eval else None,
                        "beats_baseline": c.train_eval.beats_baseline if c.train_eval else False,
                        "error_message": c.train_eval.error_message if c.train_eval else None,
                        "runtime_ms": c.train_eval.runtime_ms if c.train_eval else None
                    }
                }
                for c in all_proposals
            ],
            "trajectory_summaries": [
                {
                    "trajectory_id": p.trajectory_id,
                    "best_train_score": p.best_train_score,
                    "best_train_rel_gap": p.best_train_rel_gap,
                    "total_proposals": p.total_proposals
                }
                for p in trajectories_progress
            ]
        }

        # Atomic persistence
        fname = f"trial_{config.trial_id:04d}_{config.domain_name}_{config.arm_name}_b{config.total_budget}_w{config.num_trajectories}_{config.generator_type}.json"
        target_path = os.path.join(self.results_dir, fname)
        temp_path = target_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, indent=2)
        os.replace(temp_path, target_path)

        return result_payload
