"""
Benchmark Generation for Experiment #13
=======================================
Generates:
- Development Benchmark: 30 instances across 6 workload families (seed 1042)
- Hidden Benchmark: 120 instances across 6 workload families (seed 70099)

Workload Families:
1. Uniform
2. CPU_Heavy
3. Memory_Heavy
4. Bimodal
5. Anti_Correlated
6. Correlated
"""

import hashlib
import json
import math
import os
import random
from typing import Dict, Any, List


NODE_PROFILES = [
    {"type": "standard_m", "cpu": 16.0, "mem": 64.0, "cost": 0.80},
    {"type": "standard_l", "cpu": 32.0, "mem": 128.0, "cost": 1.60},
    {"type": "compute_opt", "cpu": 32.0, "mem": 64.0, "cost": 1.30},
    {"type": "mem_opt", "cpu": 16.0, "mem": 128.0, "cost": 1.40},
    {"type": "general_s", "cpu": 8.0, "mem": 32.0, "cost": 0.40},
]


def generate_single_instance(
    instance_id: str,
    family: str,
    n_pods: int,
    m_nodes: int,
    rng: random.Random
) -> Dict[str, Any]:
    # 1. Generate Nodes
    nodes = []
    for i in range(m_nodes):
        prof = rng.choice(NODE_PROFILES)
        nodes.append({
            "id": i,
            "type": prof["type"],
            "cpu_capacity": prof["cpu"],
            "mem_capacity": prof["mem"],
            "cost_per_hour": prof["cost"]
        })

    total_cluster_cpu = sum(n["cpu_capacity"] for n in nodes)
    total_cluster_mem = sum(n["mem_capacity"] for n in nodes)

    # 2. Generate Pods according to Family
    pods = []
    for i in range(n_pods):
        if family == "Uniform":
            cpu = round(rng.uniform(1.0, 8.0), 1)
            mem = round(rng.uniform(2.0, 32.0), 1)
        elif family == "CPU_Heavy":
            cpu = round(rng.uniform(4.0, 16.0), 1)
            mem = round(rng.uniform(2.0, 8.0), 1)
        elif family == "Memory_Heavy":
            cpu = round(rng.uniform(0.5, 2.5), 1)
            mem = round(rng.uniform(16.0, 64.0), 1)
        elif family == "Bimodal":
            if rng.random() < 0.75:
                cpu = round(rng.uniform(0.5, 1.5), 1)
                mem = round(rng.uniform(1.0, 4.0), 1)
            else:
                cpu = round(rng.uniform(8.0, 16.0), 1)
                mem = round(rng.uniform(32.0, 64.0), 1)
        elif family == "Anti_Correlated":
            if rng.random() < 0.5:
                cpu = round(rng.uniform(6.0, 16.0), 1)
                mem = round(rng.uniform(2.0, 6.0), 1)
            else:
                cpu = round(rng.uniform(0.5, 2.0), 1)
                mem = round(rng.uniform(24.0, 64.0), 1)
        elif family == "Correlated":
            cpu = round(rng.uniform(1.0, 8.0), 1)
            # 4 GB per core with small noise
            mem = round(max(1.0, cpu * 4.0 + rng.uniform(-1.0, 1.0)), 1)
        else:
            cpu = round(rng.uniform(1.0, 4.0), 1)
            mem = round(rng.uniform(2.0, 16.0), 1)

        # Ensure individual pod fits on at least the largest node profile
        cpu = min(cpu, 30.0)
        mem = min(mem, 120.0)

        pods.append({
            "id": i,
            "cpu": cpu,
            "mem": mem
        })

    # Scale check: ensure total demand <= 0.65 of cluster capacity so packing is feasible
    req_cpu = sum(p["cpu"] for p in pods)
    req_mem = sum(p["mem"] for p in pods)

    if req_cpu > total_cluster_cpu * 0.65 or req_mem > total_cluster_mem * 0.65:
        scale_cpu = (total_cluster_cpu * 0.60) / max(req_cpu, 1e-6)
        scale_mem = (total_cluster_mem * 0.60) / max(req_mem, 1e-6)
        scale = min(scale_cpu, scale_mem, 1.0)
        for p in pods:
            p["cpu"] = max(0.5, round(p["cpu"] * scale, 1))
            p["mem"] = max(1.0, round(p["mem"] * scale, 1))

    return {
        "instance_id": instance_id,
        "family": family,
        "n_pods": len(pods),
        "m_nodes": len(nodes),
        "nodes": nodes,
        "pods": pods,
        "total_cluster_cpu": total_cluster_cpu,
        "total_cluster_mem": total_cluster_mem,
        "total_pod_cpu": round(sum(p["cpu"] for p in pods), 1),
        "total_pod_mem": round(sum(p["mem"] for p in pods), 1)
    }


def generate_benchmark_suite(
    num_instances: int,
    seed: int,
    scale_label: str
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    families = ["Uniform", "CPU_Heavy", "Memory_Heavy", "Bimodal", "Anti_Correlated", "Correlated"]
    instances_per_family = num_instances // len(families)

    instances = []
    idx = 0

    for fam in families:
        for f_idx in range(instances_per_family):
            idx += 1
            iid = f"{scale_label}_{fam.lower()}_{f_idx+1:02d}"
            if scale_label == "dev":
                n_pods = rng.randint(30, 65)
                m_nodes = rng.randint(8, 16)
            else:
                # Hidden: distribution shift to larger clusters
                n_pods = rng.randint(60, 140)
                m_nodes = rng.randint(16, 32)

            inst = generate_single_instance(iid, fam, n_pods, m_nodes, rng)
            instances.append(inst)

    return instances


def main():
    os.makedirs("experiment13/benchmarks", exist_ok=True)

    # 1. Dev Benchmark (30 instances, seed 1042)
    dev_instances = generate_benchmark_suite(num_instances=30, seed=1042, scale_label="dev")
    dev_path = "experiment13/benchmarks/dev.json"
    with open(dev_path, "w") as f:
        json.dump(dev_instances, f, indent=2)
    dev_sha = hashlib.sha256(open(dev_path, "rb").read()).hexdigest()
    print(f"Dev Benchmark generated: {len(dev_instances)} instances -> {dev_path} (SHA256: {dev_sha})")

    # 2. Hidden Benchmark (120 instances, seed 70099)
    hidden_instances = generate_benchmark_suite(num_instances=120, seed=70099, scale_label="hidden")
    hidden_path = "experiment13/benchmarks/hidden.json"
    with open(hidden_path, "w") as f:
        json.dump(hidden_instances, f, indent=2)
    hidden_sha = hashlib.sha256(open(hidden_path, "rb").read()).hexdigest()
    print(f"Hidden Benchmark generated: {len(hidden_instances)} instances -> {hidden_path} (SHA256: {hidden_sha})")


if __name__ == "__main__":
    main()
