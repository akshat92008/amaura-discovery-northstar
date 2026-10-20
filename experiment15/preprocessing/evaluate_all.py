"""
Comprehensive Evaluation Engine for Amaura Experiment #15
==========================================================
Executes all frozen policies and baselines across:
1. Mode B: Static Packing Windows (Dev, Val, Hidden)
2. Mode A: Dynamic Trace Replay (Dev, Val, Hidden)

Records all primary and secondary metrics with complete determinism.
"""

import os
import sys
import json
import time
import importlib.util
from typing import Dict, Any, List, Tuple

from experiment15.simulator.simulator import simulate_static_packing, simulate_dynamic_replay
from experiment15.baselines.baselines import BASELINES


def load_policy(filepath: str) -> Tuple[Any, Any]:
    spec = importlib.util.spec_from_file_location("pol_mod", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sel_node = getattr(mod, "select_node")
    sel_pod = getattr(mod, "select_pod", None)
    return sel_node, sel_pod


def get_all_solvers():
    p_a_node, p_a_pod = load_policy("experiment15/policies/policy_a_t4_c01.py")
    p_b_node, p_b_pod = load_policy("experiment15/policies/policy_b_n60_t4_c51.py")

    solvers = {
        "Policy_A_T4_C01": {
            "name": "Amaura Policy A (T4_C01 - Exp 13)",
            "select_node": p_a_node,
            "select_pod": p_a_pod,
            "type": "amaura_discovered"
        },
        "Policy_B_N60_T4_C51": {
            "name": "Amaura Policy B (N60_T4_C51 - Exp 14)",
            "select_node": p_b_node,
            "select_pod": p_b_pod,
            "type": "amaura_discovered"
        }
    }

    for k, v in BASELINES.items():
        solvers[k] = {
            "name": v["name"],
            "select_node": v["select_node"],
            "select_pod": v["select_pod"],
            "type": "baseline"
        }

    return solvers


def evaluate_static_suite(instances: List[Dict[str, Any]], solvers: Dict[str, Any]) -> Dict[str, Any]:
    results = {s_id: {"instance_results": [], "total_cost": 0.0, "total_active_nodes": 0, "total_unscheduled": 0, "total_runtime_ms": 0.0} for s_id in solvers}

    for idx, inst in enumerate(instances):
        inst_id = inst["instance_id"]
        if idx % 10 == 0 or idx == len(instances) - 1:
            print(f"    Static instance [{idx+1}/{len(instances)}] {inst_id} ({len(inst['pods'])} pods)...", flush=True)
        for s_id, s_info in solvers.items():
            res = simulate_static_packing(inst, s_info["select_node"], s_info["select_pod"])
            results[s_id]["instance_results"].append({
                "instance_id": inst_id,
                "regime": inst.get("regime", "unknown"),
                "pod_count": inst.get("pod_count", len(inst["pods"])),
                "total_cost": res["total_cost"],
                "active_nodes": res["active_nodes_count"],
                "unscheduled": res["unscheduled_count"],
                "imbalance": res["mean_active_imbalance"],
                "runtime_ms": res["runtime_ms"]
            })
            results[s_id]["total_cost"] += res["total_cost"]
            results[s_id]["total_active_nodes"] += res["active_nodes_count"]
            results[s_id]["total_unscheduled"] += res["unscheduled_count"]
            results[s_id]["total_runtime_ms"] += res["runtime_ms"]

    # Compute averages
    n = len(instances)
    for s_id in solvers:
        results[s_id]["mean_cost"] = round(results[s_id]["total_cost"] / n, 4) if n > 0 else 0.0
        results[s_id]["mean_active_nodes"] = round(results[s_id]["total_active_nodes"] / n, 2) if n > 0 else 0.0
        results[s_id]["total_cost"] = round(results[s_id]["total_cost"], 4)
        results[s_id]["mean_runtime_ms"] = round(results[s_id]["total_runtime_ms"] / n, 3) if n > 0 else 0.0

    return results


def evaluate_dynamic_suite(traces: List[Dict[str, Any]], solvers: Dict[str, Any]) -> Dict[str, Any]:
    results = {s_id: {"trace_results": [], "total_cost": 0.0, "total_node_hours": 0.0, "peak_active_nodes": 0, "total_unscheduled": 0, "total_runtime_ms": 0.0} for s_id in solvers}

    for idx, tr in enumerate(traces):
        tr_id = tr["trace_id"]
        print(f"    Dynamic trace [{idx+1}/{len(traces)}] {tr_id} ({len(tr['events'])} events, {len(tr['nodes'])} nodes)...", flush=True)
        for s_id, s_info in solvers.items():
            res = simulate_dynamic_replay(tr, s_info["select_node"], s_info["select_pod"])
            results[s_id]["trace_results"].append({
                "trace_id": tr_id,
                "pod_count": tr.get("pod_count", len(tr["events"])),
                "total_cost": res["total_cost"],
                "infrastructure_cost": res["infrastructure_cost"],
                "node_hours": res["node_hours"],
                "avg_active_nodes": res["avg_active_nodes"],
                "peak_active_nodes": res["peak_active_nodes"],
                "unscheduled": res["unscheduled_count"],
                "runtime_ms": res["runtime_ms"]
            })
            results[s_id]["total_cost"] += res["total_cost"]
            results[s_id]["total_node_hours"] += res["node_hours"]
            results[s_id]["peak_active_nodes"] = max(results[s_id]["peak_active_nodes"], res["peak_active_nodes"])
            results[s_id]["total_unscheduled"] += res["unscheduled_count"]
            results[s_id]["total_runtime_ms"] += res["runtime_ms"]

    n = len(traces)
    for s_id in solvers:
        results[s_id]["mean_cost"] = round(results[s_id]["total_cost"] / n, 4) if n > 0 else 0.0
        results[s_id]["mean_node_hours"] = round(results[s_id]["total_node_hours"] / n, 2) if n > 0 else 0.0
        results[s_id]["total_cost"] = round(results[s_id]["total_cost"], 4)
        results[s_id]["total_node_hours"] = round(results[s_id]["total_node_hours"], 4)
        results[s_id]["mean_runtime_ms"] = round(results[s_id]["total_runtime_ms"] / n, 3) if n > 0 else 0.0

    return results


def main():
    print("=" * 75)
    print("AMAURA EXPERIMENT #15 — FULL BENCHMARK EVALUATION ENGINE")
    print("=" * 75)

    solvers = get_all_solvers()
    print(f"Loaded {len(solvers)} solvers: {list(solvers.keys())}")

    # Load benchmarks
    with open("experiment15/benchmarks/dev/mode_b_static.json") as f:
        dev_static = json.load(f)
    with open("experiment15/benchmarks/val/mode_b_static.json") as f:
        val_static = json.load(f)
    with open("experiment15/benchmarks/hidden/mode_b_static.json") as f:
        hidden_static = json.load(f)

    with open("experiment15/benchmarks/dev/mode_a_dynamic.json") as f:
        dev_dynamic = json.load(f)
    with open("experiment15/benchmarks/val/mode_a_dynamic.json") as f:
        val_dynamic = json.load(f)
    with open("experiment15/benchmarks/hidden/mode_a_dynamic.json") as f:
        hidden_dynamic = json.load(f)

    print(f"Loaded Benchmarks:")
    print(f"  Mode B Static:  Dev={len(dev_static)}, Val={len(val_static)}, Hidden={len(hidden_static)}")
    print(f"  Mode A Dynamic: Dev={len(dev_dynamic)}, Val={len(val_dynamic)}, Hidden={len(hidden_dynamic)}")

    # 1. Mode B Static Evaluations
    print("\n[1/4] Evaluating Mode B Static Benchmarks...")
    t0 = time.time()
    dev_static_res = evaluate_static_suite(dev_static, solvers)
    val_static_res = evaluate_static_suite(val_static, solvers)
    hidden_static_res = evaluate_static_suite(hidden_static, solvers)
    print(f"  Mode B evaluation complete in {time.time() - t0:.2f}s")

    # 2. Mode A Dynamic Evaluations
    print("\n[2/4] Evaluating Mode A Dynamic Benchmarks...")
    t1 = time.time()
    dev_dynamic_res = evaluate_dynamic_suite(dev_dynamic, solvers)
    val_dynamic_res = evaluate_dynamic_suite(val_dynamic, solvers)
    hidden_dynamic_res = evaluate_dynamic_suite(hidden_dynamic, solvers)
    print(f"  Mode A evaluation complete in {time.time() - t1:.2f}s")

    all_results = {
        "metadata": {
            "experiment": "Amaura Experiment #15",
            "date": "2026-10-04",
            "dataset": "Alibaba Cluster Trace v2018",
            "total_solvers": len(solvers),
            "solvers": list(solvers.keys())
        },
        "mode_b_static": {
            "dev": dev_static_res,
            "val": val_static_res,
            "hidden": hidden_static_res
        },
        "mode_a_dynamic": {
            "dev": dev_dynamic_res,
            "val": val_dynamic_res,
            "hidden": hidden_dynamic_res
        }
    }

    os.makedirs("experiment15/results", exist_ok=True)
    with open("experiment15/results/evaluation_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print("\n[3/4] Saved complete evaluation results to experiment15/results/evaluation_results.json")

    # Print summary tables
    print("\n" + "=" * 80)
    print("HIDDEN PRODUCTION BENCHMARK SUMMARY (55 Real Production Workload Windows)")
    print("=" * 80)
    print(f"{'Solver':<25} | {'Mean Cost ($)':<14} | {'Total Cost ($)':<15} | {'Active Nodes':<14} | {'Unscheduled':<12}")
    print("-" * 85)
    for s_id in solvers:
        res = hidden_static_res[s_id]
        print(f"{s_id:<25} | {res['mean_cost']:<14.2f} | {res['total_cost']:<15.2f} | {res['mean_active_nodes']:<14.2f} | {res['total_unscheduled']:<12}")

    print("\n" + "=" * 80)
    print("DYNAMIC TRACE REPLAY SUMMARY (10 Multi-Hour Production Traces)")
    print("=" * 80)
    print(f"{'Solver':<25} | {'Mean Cost ($)':<14} | {'Total Cost ($)':<15} | {'Node-Hours':<14} | {'Peak Active':<12}")
    print("-" * 85)
    for s_id in solvers:
        res = hidden_dynamic_res[s_id]
        print(f"{s_id:<25} | {res['mean_cost']:<14.2f} | {res['total_cost']:<15.2f} | {res['total_node_hours']:<14.2f} | {res['peak_active_nodes']:<12}")


if __name__ == "__main__":
    main()
