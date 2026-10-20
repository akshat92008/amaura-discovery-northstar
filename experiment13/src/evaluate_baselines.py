"""
Baseline Evaluation for Experiment #13
======================================
Evaluates all 7 established baselines on:
1. Development Benchmark (30 instances) -> experiment13/results/baselines_dev.json
2. Hidden Benchmark (120 instances) -> experiment13/results/baselines_hidden.json
"""

import json
import time
from typing import Dict, Any, List

from experiment13.src.baselines import BASELINES
from experiment13.src.simulator import simulate_schedule


def evaluate_baseline_on_suite(baseline_key: str, instances: List[Dict[str, Any]]) -> Dict[str, Any]:
    b_spec = BASELINES[baseline_key]
    select_pod = b_spec["select_pod"]
    select_node = b_spec["select_node"]

    t0 = time.perf_counter()
    instance_costs = []
    total_cost = 0.0
    active_base_cost = 0.0
    fragmentation_cost = 0.0
    unscheduled_total = 0
    active_nodes_total = 0

    family_costs = {}

    for inst in instances:
        fam = inst["family"]
        if fam not in family_costs:
            family_costs[fam] = []

        res = simulate_schedule(inst, select_node_fn=select_node, select_pod_fn=select_pod)
        cost = res["total_cost"]
        instance_costs.append(cost)
        family_costs[fam].append(cost)

        total_cost += cost
        active_base_cost += res["active_base_cost"]
        fragmentation_cost += res["fragmentation_cost"]
        unscheduled_total += res["unscheduled_count"]
        active_nodes_total += res["active_nodes_count"]

    runtime_ms = (time.perf_counter() - t0) * 1000.0

    family_means = {fam: round(sum(vals)/len(vals), 4) for fam, vals in family_costs.items()}

    return {
        "baseline_key": baseline_key,
        "name": b_spec["name"],
        "total_cost": round(total_cost, 4),
        "mean_cost_per_instance": round(total_cost / len(instances), 4),
        "active_base_cost": round(active_base_cost, 4),
        "fragmentation_cost": round(fragmentation_cost, 4),
        "unscheduled_total": unscheduled_total,
        "active_nodes_mean": round(active_nodes_total / len(instances), 2),
        "runtime_ms": round(runtime_ms, 2),
        "mean_runtime_per_instance_ms": round(runtime_ms / len(instances), 4),
        "family_mean_costs": family_means,
        "instance_costs": instance_costs
    }


def main():
    with open("experiment13/benchmarks/dev.json") as f:
        dev_instances = json.load(f)
    with open("experiment13/benchmarks/hidden.json") as f:
        hidden_instances = json.load(f)

    print("==================================================")
    print("EVALUATING BASELINES ON DEVELOPMENT BENCHMARK (30 INST)")
    print("==================================================")
    dev_results = {}
    for b_key in BASELINES:
        res = evaluate_baseline_on_suite(b_key, dev_instances)
        dev_results[b_key] = res
        print(f"[{b_key:20s}] Total Cost: {res['total_cost']:10.2f} | Mean: {res['mean_cost_per_instance']:6.2f} | Unscheduled: {res['unscheduled_total']} | Active Nodes: {res['active_nodes_mean']:4.1f} | Runtime: {res['runtime_ms']:.1f}ms")

    with open("experiment13/results/baselines_dev.json", "w") as f:
        json.dump(dev_results, f, indent=2)

    print("\n==================================================")
    print("EVALUATING BASELINES ON HIDDEN BENCHMARK (120 INST)")
    print("==================================================")
    hidden_results = {}
    for b_key in BASELINES:
        res = evaluate_baseline_on_suite(b_key, hidden_instances)
        hidden_results[b_key] = res
        print(f"[{b_key:20s}] Total Cost: {res['total_cost']:10.2f} | Mean: {res['mean_cost_per_instance']:6.2f} | Unscheduled: {res['unscheduled_total']} | Active Nodes: {res['active_nodes_mean']:4.1f} | Runtime: {res['runtime_ms']:.1f}ms")

    with open("experiment13/results/baselines_hidden.json", "w") as f:
        json.dump(hidden_results, f, indent=2)


if __name__ == "__main__":
    main()
