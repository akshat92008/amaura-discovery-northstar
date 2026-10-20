"""
Stage 4 Deterministic Benchmark Generation & Dataset Management
==============================================================
Generates synthetic item streams with rigorous bounds enforcement:
- Capacity C = 100.0
- All items w satisfy: 5.0 <= w <= 95.0
- 20 Development Streams (dev.json, seeds 40001–40020, 1,000 items each)
- 100 Hidden Streams (hidden.json, seeds 41001–41100, 1,000 items each)
- Exact SHA-256 cryptographic verification.
"""

import hashlib
import json
import math
import os
import random
from typing import List, Dict, Any, Tuple


class BenchmarkStreamGenerator:
    """Generates synthetic item streams with bounds enforcement."""
    def __init__(
        self,
        bin_capacity: float = 100.0,
        min_weight: float = 5.0,
        max_weight: float = 95.0,
        round_digits: int = 2
    ):
        self.capacity = float(bin_capacity)
        self.min_weight = float(min_weight)
        self.max_weight = float(max_weight)
        self.round_digits = round_digits

    def sample_uniform(self, rng: random.Random, n_items: int, low: float = 10.0, high: float = 80.0) -> List[float]:
        low_b = max(self.min_weight, low)
        high_b = min(self.max_weight, high)
        return [round(rng.uniform(low_b, high_b), self.round_digits) for _ in range(n_items)]

    def sample_weibull(
        self,
        rng: random.Random,
        n_items: int,
        shape: float = 1.5,
        scale: float = 35.0,
        max_retries: int = 100
    ) -> List[float]:
        items = []
        for _ in range(n_items):
            for _ in range(max_retries):
                u = rng.random()
                u = max(1e-10, min(1.0 - 1e-10, u))
                val = scale * ((-math.log(1.0 - u)) ** (1.0 / shape))
                if self.min_weight <= val <= self.max_weight:
                    items.append(round(val, self.round_digits))
                    break
            else:
                items.append(round(min(self.max_weight, max(self.min_weight, val)), self.round_digits))
        return items

    def sample_zipf(
        self,
        rng: random.Random,
        n_items: int,
        alpha: float = 1.5,
        num_categories: int = 20
    ) -> List[float]:
        weights = [1.0 / (k ** alpha) for k in range(1, num_categories + 1)]
        cum_weights = []
        c = 0.0
        for w in weights:
            c += w
            cum_weights.append(c)
        total_w = cum_weights[-1]

        category_weights = [
            round(self.min_weight + (self.max_weight - self.min_weight) * (i / (num_categories - 1)), self.round_digits)
            for i in range(num_categories)
        ]

        items = []
        for _ in range(n_items):
            r = rng.uniform(0.0, total_w)
            for idx, cw in enumerate(cum_weights):
                if r <= cw:
                    items.append(category_weights[idx])
                    break
        return items

    def generate_dataset(
        self,
        start_seed: int,
        num_streams: int,
        items_per_stream: int = 1000
    ) -> List[Dict[str, Any]]:
        streams = []
        distribution_types = ["uniform", "weibull", "zipf"]

        for idx in range(num_streams):
            seed = start_seed + idx
            rng = random.Random(seed)
            dist_type = distribution_types[idx % len(distribution_types)]

            if dist_type == "uniform":
                items = self.sample_uniform(rng, items_per_stream)
            elif dist_type == "weibull":
                items = self.sample_weibull(rng, items_per_stream)
            else:
                items = self.sample_zipf(rng, items_per_stream)

            streams.append({
                "stream_id": idx,
                "seed": seed,
                "distribution": dist_type,
                "num_items": len(items),
                "items": items
            })
        return streams


def compute_sha256(file_path: str) -> str:
    """Computes SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_and_save_benchmarks(output_dir: str) -> Tuple[str, str, str, str]:
    """Generates dev and hidden benchmarks, writes to disk, and returns paths and hashes."""
    os.makedirs(output_dir, exist_ok=True)
    generator = BenchmarkStreamGenerator()

    # 1. Dev Benchmark: 20 streams, seeds 40001–40020
    dev_streams = generator.generate_dataset(start_seed=40001, num_streams=20, items_per_stream=1000)
    dev_path = os.path.join(output_dir, "dev.json")
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_streams, f, indent=2)
    dev_hash = compute_sha256(dev_path)

    # 2. Hidden Benchmark: 100 streams, seeds 41001–41100
    hidden_streams = generator.generate_dataset(start_seed=41001, num_streams=100, items_per_stream=1000)
    hidden_path = os.path.join(output_dir, "hidden.json")
    with open(hidden_path, "w", encoding="utf-8") as f:
        json.dump(hidden_streams, f, indent=2)
    hidden_hash = compute_sha256(hidden_path)

    # 3. Private Hidden Benchmark: 100 streams, seeds 70001–70100
    priv_streams = generator.generate_dataset(start_seed=70001, num_streams=100, items_per_stream=1000)
    priv_path = os.path.join(output_dir, "private_hidden.json")
    with open(priv_path, "w", encoding="utf-8") as f:
        json.dump(priv_streams, f, indent=2)
    priv_hash = compute_sha256(priv_path)

    # Save manifest
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "dev": {"path": "dev.json", "num_streams": 20, "sha256": dev_hash},
            "hidden": {"path": "hidden.json", "num_streams": 100, "sha256": hidden_hash},
            "private_hidden": {"path": "private_hidden.json", "num_streams": 100, "sha256": priv_hash}
        }, f, indent=2)

    return dev_path, dev_hash, hidden_path, hidden_hash
