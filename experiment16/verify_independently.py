import json
import sys
import os
import time

sys.path.insert(0, os.path.abspath("."))

from experiment16.src.simulator import simulate_dynamic_replay
from experiment16.baselines.baselines import BASELINES

def main():
    print("=" * 70)
    print("AMAURA INDEPENDENT LIVE REPRODUCIBILITY TEST")
    print("=" * 70)

    # 1. Load Trial 1 Champion
    champions = json.load(open("experiment16/frozen/frozen_champions.json"))
    t1_info = champions["Trial_1"]
    t1_code = t1_info["code"]
    
    exec_globals = {}
    exec(compile(t1_code, "<Trial_1>", "exec"), exec_globals)
    t1_node_fn = exec_globals["select_node"]
    t1_pod_fn = exec_globals.get("select_pod", None)

    # 2. Load Kubernetes Baselines
    kube_bp = BASELINES["kube_binpacking"]
    kube_def = BASELINES["kube_default"]

    # 3. Load Trace hidden_dyn_09 (Real Alibaba Trace from Days 3-4)
    with open("experiment16/benchmarks/hidden/mode_a_dynamic.json") as f:
        traces = json.load(f)
    trace = [t for t in traces if t["trace_id"] == "hidden_dyn_09"][0]

    print(f"Dataset Partition:  Days 3-4 Hidden Alibaba Trace")
    print(f"Trace ID:           {trace['trace_id']}")
    print(f"Containers (Pods):  {trace['pod_count']}")
    print(f"Cluster Hosts:      {len(trace['nodes'])}")
    print(f"Discrete Events:    {len(trace['events'])} (arrivals & departures)")
    print("-" * 70)

    # 4. Run simulations live
    print("Running Trial 1 Champion (T01_C48)...")
    res_t1 = simulate_dynamic_replay(trace, t1_node_fn, t1_pod_fn)

    print("Running Kubernetes BinPacking (kube_binpacking)...")
    res_bp = simulate_dynamic_replay(trace, kube_bp["select_node"], kube_bp["select_pod"])

    print("Running Kubernetes Default (kube_default)...")
    res_def = simulate_dynamic_replay(trace, kube_def["select_node"], kube_def["select_pod"])

    print("\n" + "=" * 70)
    print(f"{'SOLVER':<25} | {'COST ($)':<10} | {'NODE-HOURS':<12} | {'UNSCHEDULED':<12}")
    print("-" * 70)
    print(f"{'Amaura T01_C48':<25} | ${res_t1['total_cost']:<9.2f} | {res_t1['node_hours']:<12.4f} | {res_t1['unscheduled_count']:<12}")
    print(f"{'kube_binpacking':<25} | ${res_bp['total_cost']:<9.2f} | {res_bp['node_hours']:<12.4f} | {res_bp['unscheduled_count']:<12}")
    print(f"{'kube_default':<25} | ${res_def['total_cost']:<9.2f} | {res_def['node_hours']:<12.4f} | {res_def['unscheduled_count']:<12}")
    print("=" * 70)
    
    diff = res_bp['total_cost'] - res_t1['total_cost']
    print(f"Net Result on hidden_dyn_09: Amaura saved ${diff:.2f} vs kube_binpacking")
    print("=" * 70)

if __name__ == "__main__":
    main()
