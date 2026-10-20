"""
Dataset Generation Script for PFSP Corrected AI Discovery Pilot v2 (2026-10-20)
=============================================================================
Generates:
1. 20 development instances (seeds 600001–600020)
2. 30 holdout instances (seeds 600101–600130)

Guarantees 100% non-overlap with all historical seeds:
- Historical Pilot 1: seeds 500001–500020 (dev), 500101–500130 (holdout)
- Historical Stage 4 / fresh replication: seeds 90001–90030

Uses standard Taillard uniform distribution: processing times drawn uniformly
from [1, 99] using python standard random.Random(seed).
"""

import hashlib
import json
import os
import random
from typing import List, Dict, Any, Tuple


DEV_SIZES: List[Tuple[int, int]] = [
    # Small (6)
    (20, 5), (20, 5), (20, 10), (20, 10), (30, 5), (30, 10),
    # Medium (8)
    (50, 5), (50, 5), (50, 10), (50, 10), (50, 15), (50, 15), (75, 10), (75, 15),
    # Large (6)
    (75, 10), (75, 15), (100, 10), (100, 10), (100, 15), (120, 10)
]

HOLDOUT_SIZES: List[Tuple[int, int]] = [
    # Small (8)
    (20, 5), (20, 5), (20, 10), (20, 10), (30, 5), (30, 5), (30, 10), (30, 10),
    # Medium (14)
    (50, 5), (50, 5), (50, 10), (50, 10), (50, 10), (50, 15), (50, 15), (50, 15),
    (75, 10), (75, 10), (75, 10), (75, 15), (75, 15), (75, 15),
    # Large (8)
    (100, 10), (100, 10), (100, 10), (100, 15), (100, 15), (120, 10), (120, 10), (120, 15)
]

HISTORICAL_SEEDS = set(range(90001, 90031)) | set(range(500001, 500021)) | set(range(500101, 500131))


def generate_instance(inst_id: str, seed: int, n: int, m: int) -> Dict[str, Any]:
    assert seed not in HISTORICAL_SEEDS, f"Seed {seed} overlaps with historical seeds!"
    rng = random.Random(seed)
    times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]
    return {
        "id": inst_id,
        "seed": seed,
        "family": "taillard_uniform",
        "n": n,
        "m": m,
        "times": times
    }


def main():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(target_dir, exist_ok=True)

    # 1. Dev instances
    dev_instances = []
    dev_start_seed = 600001
    for idx, (n, m) in enumerate(DEV_SIZES):
        seed = dev_start_seed + idx
        inst_id = f"pfsp_dev_{idx:02d}"
        dev_instances.append(generate_instance(inst_id, seed, n, m))

    dev_path = os.path.join(target_dir, "dev_instances.json")
    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_instances, f, indent=2)

    with open(dev_path, "rb") as f:
        dev_hash = hashlib.sha256(f.read()).hexdigest()

    # 2. Holdout instances
    holdout_instances = []
    holdout_start_seed = 600101
    for idx, (n, m) in enumerate(HOLDOUT_SIZES):
        seed = holdout_start_seed + idx
        inst_id = f"pfsp_holdout_{idx:02d}"
        holdout_instances.append(generate_instance(inst_id, seed, n, m))

    holdout_path = os.path.join(target_dir, "holdout_instances.json")
    with open(holdout_path, "w", encoding="utf-8") as f:
        json.dump(holdout_instances, f, indent=2)

    with open(holdout_path, "rb") as f:
        holdout_hash = hashlib.sha256(f.read()).hexdigest()

    # 3. Seed Manifest
    manifest = {
        "dataset_generator": "generate_datasets.py",
        "distribution": "Taillard uniform [1, 99]",
        "development_set": {
            "count": len(dev_instances),
            "start_seed": dev_start_seed,
            "end_seed": dev_start_seed + len(dev_instances) - 1,
            "file": "data/dev_instances.json",
            "sha256": dev_hash,
            "dimensions": [(x["n"], x["m"]) for x in dev_instances]
        },
        "holdout_set": {
            "count": len(holdout_instances),
            "start_seed": holdout_start_seed,
            "end_seed": holdout_start_seed + len(holdout_instances) - 1,
            "file": "data/holdout_instances.json",
            "sha256": holdout_hash,
            "dimensions": [(x["n"], x["m"]) for x in holdout_instances]
        },
        "historical_overlap_check": {
            "historical_seeds_checked": len(HISTORICAL_SEEDS),
            "overlap_detected": False
        }
    }

    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {len(dev_instances)} dev instances: {dev_path} (SHA-256: {dev_hash})")
    print(f"Generated {len(holdout_instances)} holdout instances: {holdout_path} (SHA-256: {holdout_hash})")
    print(f"Saved seed manifest: {manifest_path}")


if __name__ == "__main__":
    main()
