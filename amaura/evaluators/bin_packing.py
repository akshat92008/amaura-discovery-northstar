"""
Online 1D Bin Packing Evaluator
===============================
Standard operations-research benchmark for automated heuristic discovery.
Formulation identical to DeepMind FunSearch (Nature 2023).
"""

import math
import random
from typing import List, Tuple, Any, Optional
from amaura.engine.candidate import Candidate
from amaura.evaluators.base import BaseEvaluator


class BinPackingEvaluator(BaseEvaluator):
    """
    Evaluates online 1D bin packing heuristics.
    Candidate signature:
    def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
        ...
    """

    def __init__(
        self,
        bin_capacity: float = 100.0,
        train_count: int = 30,
        test_count: int = 50,
        gen_count: int = 40,
        items_per_instance: int = 120,
        seed: int = 42,
        timeout_sec: float = 2.5
    ):
        super().__init__(timeout_sec=timeout_sec)
        self.bin_capacity = bin_capacity
        self.items_per_instance = items_per_instance
        self.seed = seed

        # Generate deterministic benchmark datasets
        rng = random.Random(seed)
        self.datasets = {
            "train": self._generate_uniform_instances(rng, train_count, items_per_instance),
            "test": self._generate_uniform_instances(rng, test_count, items_per_instance),
            "generalization": self._generate_weibull_instances(rng, gen_count, items_per_instance)
        }

    def _generate_uniform_instances(
        self, rng: random.Random, count: int, num_items: int
    ) -> List[List[float]]:
        instances = []
        for _ in range(count):
            items = [round(rng.uniform(10.0, 80.0), 2) for _ in range(num_items)]
            instances.append(items)
        return instances

    def _generate_weibull_instances(
        self, rng: random.Random, count: int, num_items: int
    ) -> List[List[float]]:
        # Skewed real-world distribution (Weibull with shape 1.8, scale 42.0)
        instances = []
        for _ in range(count):
            items = []
            for _ in range(num_items):
                val = 42.0 * ((-math.log(1.0 - rng.random())) ** (1.0 / 1.8))
                val = max(10.0, min(85.0, val))
                items.append(round(val, 2))
            instances.append(items)
        return instances

    def simulate_packing(
        self, priority_func: Any, items: List[float]
    ) -> Tuple[int, int]:
        """
        Simulate packing for a single instance.
        Returns: (bins_used, theoretical_lower_bound)
        """
        # Open bins list storing remaining capacity of each open bin
        open_bins: List[float] = []

        for item in items:
            best_bin_idx = -1
            best_priority = -float("inf")

            # Evaluate priority on all feasible open bins
            for idx, rem in enumerate(open_bins):
                if rem >= item - 1e-6:
                    try:
                        p = float(priority_func(item, rem, self.bin_capacity))
                    except Exception as e:
                        raise RuntimeError(f"Candidate raised exception on item={item}, rem={rem}: {e}") from e
                    if math.isnan(p) or math.isinf(p):
                        raise RuntimeError(f"Candidate returned non-finite priority {p} on item={item}, rem={rem}")
                    if p > best_priority:
                        best_priority = p
                        best_bin_idx = idx

            if best_bin_idx >= 0:
                open_bins[best_bin_idx] -= item
            else:
                # Open a new bin
                open_bins.append(self.bin_capacity - item)

        total_weight = sum(items)
        lower_bound = math.ceil(total_weight / self.bin_capacity)
        return len(open_bins), lower_bound

    def evaluate_callable(
        self, func: Any, dataset: str = "train"
    ) -> Tuple[bool, float, float, int, int, Optional[str]]:
        instances = self.datasets.get(dataset, [])
        if not instances:
            return False, float("inf"), 0.0, 0, 0, f"Unknown dataset: {dataset}"

        total_bins = 0
        total_lower_bounds = 0
        passed = 0

        for instance in instances:
            try:
                bins_used, lb = self.simulate_packing(func, instance)
                # Verification: bins_used cannot be less than theoretical lower bound
                if bins_used < lb:
                    return False, float("inf"), 0.0, passed, len(instances), "Physical impossibility: bins < lower bound"
                total_bins += bins_used
                total_lower_bounds += lb
                passed += 1
            except Exception as e:
                return False, float("inf"), 0.0, passed, len(instances), f"Simulation failed: {str(e)}"

        avg_bins = total_bins / len(instances)
        # Ratio of bins used to lower bound (1.0 = perfect theoretical packing)
        # Fitness is (ratio - 1.0) * 100: percentage excess bins over theoretical minimum
        excess_percentage = ((total_bins / max(1, total_lower_bounds)) - 1.0) * 100.0

        return True, excess_percentage, avg_bins, passed, len(instances), None

    def get_seed_candidates(self) -> List[Candidate]:
        """Return canonical human baseline candidates."""
        # Baseline 1: Best Fit (standard greedy champion)
        bf_code = (
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    # Best Fit: pack into bin with least remaining space\n"
            "    return -remaining_capacity\n"
        )
        c1 = Candidate(
            code=bf_code,
            function_name="priority",
            mutation_type="seed_best_fit",
            generation=0,
            island_id=0
        )

        # Baseline 2: Worst Fit (distribute load across bins)
        wf_code = (
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    # Worst Fit: pack into bin with most remaining space\n"
            "    return remaining_capacity\n"
        )
        c2 = Candidate(
            code=wf_code,
            function_name="priority",
            mutation_type="seed_worst_fit",
            generation=0,
            island_id=1
        )

        # Baseline 3: First Fit
        ff_code = (
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    # First Fit: place in earliest available bin\n"
            "    return 0.0\n"
        )
        c3 = Candidate(
            code=ff_code,
            function_name="priority",
            mutation_type="seed_first_fit",
            generation=0,
            island_id=2
        )

        # Baseline 4: Almost Worst Fit
        awf_code = (
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    # Almost Worst Fit heuristic\n"
            "    space_after = remaining_capacity - item\n"
            "    if space_after < 0.05 * bin_capacity:\n"
            "        return 1000.0 - space_after\n"
            "    return remaining_capacity * 0.5\n"
        )
        c4 = Candidate(
            code=awf_code,
            function_name="priority",
            mutation_type="seed_almost_worst_fit",
            generation=0,
            island_id=0
        )

        return [c1, c2, c3, c4]
