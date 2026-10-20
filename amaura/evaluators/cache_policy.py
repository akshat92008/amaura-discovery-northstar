"""
Cache Eviction Policy Evaluator
===============================
Systems benchmark for automated algorithmic discovery.
Discovers replacement policies outperforming LRU, LFU, and FIFO.
"""

import math
import random
from typing import List, Tuple, Any, Optional, Dict
from amaura.engine.candidate import Candidate
from amaura.evaluators.base import BaseEvaluator


class CachePolicyEvaluator(BaseEvaluator):
    """
    Evaluates cache eviction heuristics.
    Candidate signature:
    def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
        ...
    The entry with the MINIMUM evict_score is evicted on cache misses.
    """

    def __init__(
        self,
        cache_size: int = 40,
        train_traces: int = 15,
        test_traces: int = 25,
        gen_traces: int = 20,
        trace_length: int = 1500,
        seed: int = 42,
        timeout_sec: float = 2.5
    ):
        super().__init__(timeout_sec=timeout_sec)
        self.cache_size = cache_size
        self.trace_length = trace_length
        self.seed = seed

        rng = random.Random(seed)
        self.datasets = {
            "train": self._generate_zipf_traces(rng, train_traces, trace_length, alpha=0.9),
            "test": self._generate_zipf_traces(rng, test_traces, trace_length, alpha=0.95),
            "generalization": self._generate_mixed_traces(rng, gen_traces, trace_length)
        }

    def _generate_zipf_traces(
        self, rng: random.Random, count: int, length: int, alpha: float
    ) -> List[List[int]]:
        """Generate Zipfian access distributions with temporal bursts."""
        n_items = 250
        weights = [1.0 / (i ** alpha) for i in range(1, n_items + 1)]
        cum_weights = []
        c = 0.0
        for w in weights:
            c += w
            cum_weights.append(c)
        total = c

        traces = []
        for _ in range(count):
            trace = []
            for _ in range(length):
                r = rng.random() * total
                # Binary search or scan
                idx = 0
                for i, cw in enumerate(cum_weights):
                    if r <= cw:
                        idx = i
                        break
                trace.append(idx + 1)
            traces.append(trace)
        return traces

    def _generate_mixed_traces(
        self, rng: random.Random, count: int, length: int
    ) -> List[List[int]]:
        """Generate alternating looping and Zipfian traces for generalization test."""
        traces = []
        for _ in range(count):
            trace = []
            while len(trace) < length:
                mode = rng.choice(["loop", "zipf"])
                if mode == "loop":
                    loop_len = rng.randint(self.cache_size + 2, self.cache_size + 15)
                    repeats = rng.randint(3, 6)
                    pattern = list(range(100, 100 + loop_len))
                    for _ in range(repeats):
                        trace.extend(pattern)
                else:
                    for _ in range(rng.randint(50, 150)):
                        trace.append(rng.randint(1, 80))
            traces.append(trace[:length])
        return traces

    def simulate_cache(
        self, score_func: Any, trace: List[int]
    ) -> Tuple[int, int]:
        """
        Simulate cache on an access trace.
        Returns: (hits, misses)
        """
        # Cache entries mapping key -> dict of metadata
        # recency: steps since last access
        # frequency: total hits/accesses
        # age: steps since inserted
        cache: Dict[int, Dict[str, int]] = {}
        hits = 0
        misses = 0

        for step, key in enumerate(trace):
            # Update recency of all entries
            for entry in cache.values():
                entry["recency"] += 1
                entry["age"] += 1

            if key in cache:
                hits += 1
                cache[key]["frequency"] += 1
                cache[key]["recency"] = 0
            else:
                misses += 1
                if len(cache) >= self.cache_size:
                    # Evict entry with lowest score
                    victim_key = None
                    lowest_score = float("inf")
                    for k, meta in cache.items():
                        try:
                            score = float(score_func(
                                k, meta["recency"], meta["frequency"], meta["age"], self.cache_size
                            ))
                        except Exception as e:
                            raise RuntimeError(f"Candidate raised exception on key={k}: {e}") from e
                        if math.isnan(score) or math.isinf(score):
                            raise RuntimeError(f"Candidate returned non-finite score {score} on key={k}")
                        if score < lowest_score:
                            lowest_score = score
                            victim_key = k

                    if victim_key is not None:
                        del cache[victim_key]

                # Insert new entry
                cache[key] = {"recency": 0, "frequency": 1, "age": 0}

        return hits, misses

    def evaluate_callable(
        self, func: Any, dataset: str = "train"
    ) -> Tuple[bool, float, float, int, int, Optional[str]]:
        traces = self.datasets.get(dataset, [])
        if not traces:
            return False, float("inf"), 0.0, 0, 0, f"Unknown dataset: {dataset}"

        total_hits = 0
        total_accesses = 0
        passed = 0

        for trace in traces:
            try:
                hits, misses = self.simulate_cache(func, trace)
                total_hits += hits
                total_accesses += len(trace)
                passed += 1
            except Exception as e:
                return False, float("inf"), 0.0, passed, len(traces), f"Cache simulation error: {str(e)}"

        hit_rate_pct = (total_hits / max(1, total_accesses)) * 100.0
        # Fitness is miss rate % (lower is better)
        miss_rate_pct = 100.0 - hit_rate_pct

        return True, miss_rate_pct, hit_rate_pct, passed, len(traces), None

    def get_seed_candidates(self) -> List[Candidate]:
        """Return canonical human baseline candidates."""
        # Baseline 1: LRU (Least Recently Used)
        lru_code = (
            "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
            "    # LRU: higher recency = longer ago = lower score = evicted\n"
            "    return -float(recency)\n"
        )
        c1 = Candidate(
            code=lru_code,
            function_name="evict_score",
            mutation_type="seed_lru",
            generation=0,
            island_id=0
        )

        # Baseline 2: LFU (Least Frequently Used)
        lfu_code = (
            "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
            "    # LFU: lower frequency = lower score = evicted\n"
            "    return float(frequency)\n"
        )
        c2 = Candidate(
            code=lfu_code,
            function_name="evict_score",
            mutation_type="seed_lfu",
            generation=0,
            island_id=1
        )

        # Baseline 3: FIFO (First In First Out)
        fifo_code = (
            "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
            "    # FIFO: older age = lower score = evicted\n"
            "    return -float(age)\n"
        )
        c3 = Candidate(
            code=fifo_code,
            function_name="evict_score",
            mutation_type="seed_fifo",
            generation=0,
            island_id=2
        )

        # Baseline 4: Hyperbolic decay (frequency / recency)
        hyperbolic_code = (
            "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
            "    # Hyperbolic caching: frequency weighted by recency decay\n"
            "    return float(frequency) / (float(recency) + 1.0)\n"
        )
        c4 = Candidate(
            code=hyperbolic_code,
            function_name="evict_score",
            mutation_type="seed_hyperbolic",
            generation=0,
            island_id=0
        )

        return [c1, c2, c3, c4]
