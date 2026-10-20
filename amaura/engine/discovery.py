"""
Discovery Engine: The Core Evolutionary Algorithm Loop
======================================================
Coordinates multi-island evolution, evaluations, sandboxing, and telemetry.
"""

import json
import os
import time
from typing import Callable, Optional, Dict, Any, List
from amaura.config import DiscoveryConfig
from amaura.engine.candidate import Candidate
from amaura.engine.archive import IslandArchive
from amaura.engine.generator import ProgramGenerator
from amaura.evaluators.base import BaseEvaluator
from amaura.evaluators.bin_packing import BinPackingEvaluator
from amaura.evaluators.cache_policy import CachePolicyEvaluator


class DiscoveryEngine:
    """
    Automated discovery engine that iteratively evolves, evaluates,
    and isolates breakthrough algorithms outperforming human baselines.
    """

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.evaluator: BaseEvaluator = self._init_evaluator()
        self.archive = IslandArchive(
            num_islands=config.num_islands,
            capacity_per_island=max(4, config.population_size // config.num_islands),
            elite_capacity=10
        )
        self.generator = ProgramGenerator(config)
        self.history: List[Dict[str, Any]] = []
        self.human_baseline: Optional[Candidate] = None
        self.telemetry_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Ensure output directory exists
        os.makedirs(config.output_dir, exist_ok=True)

    def _init_evaluator(self) -> BaseEvaluator:
        if self.config.problem == "bin_packing":
            return BinPackingEvaluator(
                train_count=self.config.train_instances,
                test_count=self.config.test_instances,
                gen_count=self.config.generalization_instances,
                seed=self.config.seed,
                timeout_sec=self.config.timeout_per_eval_sec
            )
        elif self.config.problem == "cache_policy":
            return CachePolicyEvaluator(
                train_traces=15,
                test_traces=25,
                gen_traces=20,
                seed=self.config.seed,
                timeout_sec=self.config.timeout_per_eval_sec
            )
        else:
            raise ValueError(f"Unknown problem type: {self.config.problem}")

    def add_telemetry_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self.telemetry_callbacks.append(cb)

    def _emit_telemetry(self, event: Dict[str, Any]):
        for cb in self.telemetry_callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def initialize_population(self):
        """Evaluate seed baseline candidates and establish human baseline benchmark."""
        seeds = self.evaluator.get_seed_candidates()
        best_seed = None

        for idx, seed in enumerate(seeds):
            seed.island_id = idx % self.config.num_islands
            res = self.evaluator.evaluate_candidate(seed)
            seed.is_valid = res.is_valid
            seed.fitness = res.fitness
            seed.raw_score = res.raw_score
            seed.train_score = res.train_score
            seed.test_score = res.test_score
            seed.generalization_score = res.generalization_score
            seed.runtime_ms = res.runtime_ms
            seed.passed_tests = res.passed_tests
            seed.total_tests = res.total_tests
            seed.error_message = res.error_message

            self.archive.add(seed)

            if best_seed is None or seed.fitness < best_seed.fitness:
                best_seed = seed

        self.human_baseline = best_seed
        self._emit_telemetry({
            "type": "initialized",
            "human_baseline": best_seed.to_dict() if best_seed else None
        })

    def run(self, generations: Optional[int] = None) -> Candidate:
        """
        Run the complete evolutionary discovery loop.
        Returns the overall best candidate discovered.
        """
        max_gens = generations or self.config.generations
        self.initialize_population()

        task_desc = (
            "Design an online 1D bin packing priority function `priority(item, remaining_capacity, bin_capacity) -> float`"
            if self.config.problem == "bin_packing"
            else "Design a cache eviction scoring function `evict_score(key, recency, frequency, age, cache_size) -> float`"
        )

        for gen in range(1, max_gens + 1):
            gen_start_time = time.time()
            new_candidates_count = 0
            valid_candidates_count = 0

            # Evolve candidates on each island
            for island_id in range(self.config.num_islands):
                parents = self.archive.get_parents(island_id, count=2)
                if not parents:
                    continue

                # Generate new program variant
                candidate = self.generator.generate_candidate(
                    parents=parents,
                    generation=gen,
                    island_id=island_id,
                    task_desc=task_desc
                )
                new_candidates_count += 1

                # Check if identical candidate was already tested
                if self.archive.is_known(candidate):
                    continue

                # 4-Layer sandbox evaluation
                eval_res = self.evaluator.evaluate_candidate(candidate)
                candidate.is_valid = eval_res.is_valid
                candidate.fitness = eval_res.fitness
                candidate.raw_score = eval_res.raw_score
                candidate.train_score = eval_res.train_score
                candidate.test_score = eval_res.test_score
                candidate.generalization_score = eval_res.generalization_score
                candidate.runtime_ms = eval_res.runtime_ms
                candidate.passed_tests = eval_res.passed_tests
                candidate.total_tests = eval_res.total_tests
                candidate.error_message = eval_res.error_message

                if candidate.is_valid:
                    valid_candidates_count += 1
                    self.archive.add(candidate)

            # Check for island migration
            if gen % self.config.migration_interval == 0:
                self.archive.migrate(count=self.config.migration_count)

            current_best = self.archive.get_best()
            baseline_fit = self.human_baseline.fitness if self.human_baseline else 1.0
            
            # Improvement calculation (percentage improvement over human baseline)
            improvement_pct = 0.0
            if current_best and self.human_baseline:
                improvement_pct = ((baseline_fit - current_best.fitness) / max(1e-6, abs(baseline_fit))) * 100.0

            gen_summary = {
                "generation": gen,
                "duration_sec": round(time.time() - gen_start_time, 2),
                "total_candidates": len(self.archive.all_candidates),
                "valid_candidates": sum(1 for c in self.archive.all_candidates.values() if c.is_valid),
                "best_fitness": round(current_best.fitness, 4) if current_best else None,
                "best_raw_score": round(current_best.raw_score, 4) if current_best else None,
                "baseline_fitness": round(baseline_fit, 4),
                "improvement_pct": round(improvement_pct, 2),
                "best_candidate_id": current_best.id if current_best else None,
                "best_mutation": current_best.mutation_type if current_best else None
            }
            self.history.append(gen_summary)

            self._emit_telemetry({
                "type": "generation_step",
                "summary": gen_summary,
                "best_candidate": current_best.to_dict() if current_best else None
            })

        # Save run results to disk
        self._save_checkpoint()
        return self.archive.get_best()

    def _save_checkpoint(self):
        """Persist discovery run data to output directory."""
        best = self.archive.get_best()
        summary_path = os.path.join(self.config.output_dir, "run_summary.json")
        best_code_path = os.path.join(self.config.output_dir, "best_discovered_algorithm.py")

        run_data = {
            "problem": self.config.problem,
            "generations": len(self.history),
            "human_baseline": self.human_baseline.to_dict() if self.human_baseline else None,
            "best_candidate": best.to_dict() if best else None,
            "history": self.history,
            "pareto_frontier": self.archive.get_pareto_frontier()
        }

        with open(summary_path, "w") as f:
            json.dump(run_data, f, indent=2)

        if best:
            with open(best_code_path, "w") as f:
                f.write(f"# Discovered by Amaura Engine\n")
                f.write(f"# Generation: {best.generation}, ID: {best.id}\n")
                f.write(f"# Fitness: {best.fitness:.4f}, Raw Score: {best.raw_score:.4f}\n")
                f.write(f"# Mutation Type: {best.mutation_type}\n\n")
                f.write(best.code)
