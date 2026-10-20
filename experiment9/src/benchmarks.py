"""
Experiment #9: PFSP Benchmark Generation Suite
==============================================
Generates:
- Development Benchmark (30 instances across 6 families, seed=1042)
- Hidden Benchmark (120 instances across 6 families, seed=70099)
Saves both to experiment9/benchmarks/dev.json and hidden.json.
"""

import json
import os
import random
from typing import List, Dict, Any


def generate_instance(inst_id: str, family: str, n: int, m: int, rng: random.Random) -> Dict[str, Any]:
    times = []
    if family in ("dev_taillard_uniform", "hid_taillard_uniform"):
        # Standard Taillard uniform random [1, 99]
        times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]

    elif family in ("dev_mach_corr", "hid_mach_corr"):
        # Center machines have 3x higher load (severe bottleneck)
        center_m = m // 2
        for j in range(n):
            row = []
            for k in range(m):
                if k == center_m or (m >= 8 and abs(k - center_m) <= 1):
                    row.append(rng.randint(60, 150))
                else:
                    row.append(rng.randint(5, 40))
            times.append(row)

    elif family in ("dev_job_corr", "hid_job_corr"):
        # Log-normal / heterogeneous job weights (some jobs intrinsically long)
        for j in range(n):
            job_base = rng.choice([10, 20, 50, 80, 120])
            row = [max(1, int(rng.gauss(job_base, job_base * 0.2))) for _ in range(m)]
            times.append(row)

    elif family == "dev_bimodal":
        # Bimodal: short (5-15) or long (85-100)
        for j in range(n):
            row = []
            for k in range(m):
                if rng.random() < 0.5:
                    row.append(rng.randint(5, 15))
                else:
                    row.append(rng.randint(85, 100))
            times.append(row)

    elif family == "hid_trimodal":
        # Trimodal: short (5-12), medium (40-60), long (110-140)
        for j in range(n):
            row = []
            for k in range(m):
                r = rng.random()
                if r < 0.33:
                    row.append(rng.randint(5, 12))
                elif r < 0.66:
                    row.append(rng.randint(40, 60))
                else:
                    row.append(rng.randint(110, 140))
            times.append(row)

    elif family in ("dev_high_ratio", "hid_high_ratio"):
        # Large scale / high aspect ratio n >> m
        times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]

    elif family == "dev_square":
        # Square aspect ratio n ~= m
        times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]

    elif family == "hid_u_load":
        # U-shaped machine load: first and last machines are heavy, middle machines are light
        for j in range(n):
            row = []
            for k in range(m):
                if k == 0 or k == m - 1:
                    row.append(rng.randint(70, 140))
                else:
                    row.append(rng.randint(5, 30))
            times.append(row)

    else:
        times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]

    return {
        "id": inst_id,
        "family": family,
        "n": n,
        "m": m,
        "times": times
    }


def build_dev_benchmark(seed: int = 1042) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    instances = []

    # 1. Uniform random (5)
    dims_uniform = [(20, 5), (20, 10), (50, 5), (50, 10), (50, 10)]
    for i, (n, m) in enumerate(dims_uniform):
        instances.append(generate_instance(f"dev_uniform_{i+1}", "dev_taillard_uniform", n, m, rng))

    # 2. Machine correlated bottleneck (5)
    dims_mach = [(20, 5), (20, 10), (50, 5), (50, 10), (50, 10)]
    for i, (n, m) in enumerate(dims_mach):
        instances.append(generate_instance(f"dev_mach_{i+1}", "dev_mach_corr", n, m, rng))

    # 3. Job correlated load (5)
    dims_job = [(20, 5), (20, 10), (50, 5), (50, 10), (50, 10)]
    for i, (n, m) in enumerate(dims_job):
        instances.append(generate_instance(f"dev_job_{i+1}", "dev_job_corr", n, m, rng))

    # 4. Bimodal processing times (5)
    dims_bimodal = [(20, 5), (20, 10), (50, 5), (50, 10), (50, 10)]
    for i, (n, m) in enumerate(dims_bimodal):
        instances.append(generate_instance(f"dev_bimodal_{i+1}", "dev_bimodal", n, m, rng))

    # 5. High aspect ratio n >> m (5)
    dims_high = [(50, 4), (60, 4), (50, 5), (60, 5), (70, 4)]
    for i, (n, m) in enumerate(dims_high):
        instances.append(generate_instance(f"dev_high_{i+1}", "dev_high_ratio", n, m, rng))

    # 6. Square aspect ratio n ~= m (5)
    dims_square = [(15, 15), (16, 16), (18, 18), (20, 20), (20, 20)]
    for i, (n, m) in enumerate(dims_square):
        instances.append(generate_instance(f"dev_square_{i+1}", "dev_square", n, m, rng))

    return instances


def build_hidden_benchmark(seed: int = 70099) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    instances = []

    # 6 families x 20 instances each = 120 instances
    configs = [
        ("hid_taillard_uniform", [(20, 5), (20, 10), (20, 20), (50, 5), (50, 10)] * 4),
        ("hid_mach_corr", [(20, 10), (30, 10), (50, 10), (50, 15), (100, 5)] * 4),
        ("hid_job_corr", [(20, 10), (30, 10), (50, 10), (50, 15), (100, 5)] * 4),
        ("hid_trimodal", [(20, 10), (30, 10), (50, 10), (50, 15), (100, 5)] * 4),
        ("hid_high_ratio", [(80, 5), (100, 5), (100, 6), (120, 5), (100, 10)] * 4),
        ("hid_u_load", [(20, 10), (30, 10), (50, 10), (50, 15), (100, 5)] * 4),
    ]

    for fam_name, dim_list in configs:
        for idx, (n, m) in enumerate(dim_list):
            inst_id = f"{fam_name}_{idx+1}"
            instances.append(generate_instance(inst_id, fam_name, n, m, rng))

    return instances


def generate_and_save_benchmarks(out_dir: str = "experiment9/benchmarks"):
    os.makedirs(out_dir, exist_ok=True)
    dev_path = os.path.join(out_dir, "dev.json")
    hidden_path = os.path.join(out_dir, "hidden.json")

    dev_insts = build_dev_benchmark(seed=1042)
    hidden_insts = build_hidden_benchmark(seed=70099)

    with open(dev_path, "w") as f:
        json.dump(dev_insts, f, indent=2)

    with open(hidden_path, "w") as f:
        json.dump(hidden_insts, f, indent=2)

    print(f"Generated Dev Benchmark: {len(dev_insts)} instances -> {dev_path}")
    print(f"Generated Hidden Benchmark: {len(hidden_insts)} instances -> {hidden_path}")


if __name__ == "__main__":
    generate_and_save_benchmarks()
