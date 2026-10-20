"""
Established Cloud Scheduling Baselines
======================================
Pre-registered, reproducible implementations of classical heuristics and
production Kubernetes scheduling policies:

1. First Fit (FF)
2. Best Fit (Least Residual Capacity)
3. Worst Fit (Most Allocated Residual / Spreading)
4. Best Fit Decreasing (BFD - Vector Norm Ordering)
5. Kube-Scheduler Default (LeastAllocated + BalancedAllocation)
6. Kube-Scheduler BinPacking (MostAllocated + BalancedAllocation)
7. Random Feasible
"""

import math
import random
from typing import Dict, Any, List, Tuple, Callable


# -------------------------------------------------------------------------
# 1. First Fit (FF)
# -------------------------------------------------------------------------
def select_pod_fifo(pending_pods: List[Dict[str, Any]], nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    return pending_pods[0]["id"]


def select_node_first_fit(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    return feasible_nodes[0]["id"]


# -------------------------------------------------------------------------
# 2. Best Fit (Least Residual Capacity)
# -------------------------------------------------------------------------
def select_node_best_fit(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    best_nid = feasible_nodes[0]["id"]
    min_residual = float("inf")

    for n in feasible_nodes:
        nid = n["id"]
        rem_cpu = state["remaining_cpu"][nid] - pod["cpu"]
        rem_mem = state["remaining_mem"][nid] - pod["mem"]
        # Normalized residual volume
        res_vol = (rem_cpu / n["cpu_capacity"]) + (rem_mem / n["mem_capacity"])
        if res_vol < min_residual:
            min_residual = res_vol
            best_nid = nid

    return best_nid


# -------------------------------------------------------------------------
# 3. Worst Fit (Most Residual Capacity / Spreading / Load Balancing)
# -------------------------------------------------------------------------
def select_node_worst_fit(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    best_nid = feasible_nodes[0]["id"]
    max_residual = -1.0

    for n in feasible_nodes:
        nid = n["id"]
        rem_cpu = state["remaining_cpu"][nid] - pod["cpu"]
        rem_mem = state["remaining_mem"][nid] - pod["mem"]
        res_vol = (rem_cpu / n["cpu_capacity"]) + (rem_mem / n["mem_capacity"])
        if res_vol > max_residual:
            max_residual = res_vol
            best_nid = nid

    return best_nid


# -------------------------------------------------------------------------
# 4. Best Fit Decreasing (BFD - Vector Norm)
# -------------------------------------------------------------------------
def select_pod_bfd(pending_pods: List[Dict[str, Any]], nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    # Pod with largest resource norm
    best_p = max(pending_pods, key=lambda p: math.sqrt(p["cpu"]**2 + (p["mem"]/4.0)**2))
    return best_p["id"]


# -------------------------------------------------------------------------
# 5. Kube-Scheduler Default (LeastAllocated + BalancedAllocation)
# -------------------------------------------------------------------------
def select_node_kube_default(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    best_nid = feasible_nodes[0]["id"]
    max_score = -float("inf")

    for n in feasible_nodes:
        nid = n["id"]
        new_cpu = state["allocated_cpu"][nid] + pod["cpu"]
        new_mem = state["allocated_mem"][nid] + pod["mem"]
        u_cpu = new_cpu / n["cpu_capacity"]
        u_mem = new_mem / n["mem_capacity"]

        # LeastAllocated: reward idle capacity
        least_alloc = 0.5 * ((1.0 - u_cpu) + (1.0 - u_mem)) * 50.0
        # BalancedAllocation: reward matching CPU and Memory ratios
        imbalance = abs(u_cpu - u_mem)
        balanced = (1.0 - imbalance) * 50.0

        score = least_alloc + balanced
        if score > max_score:
            max_score = score
            best_nid = nid

    return best_nid


# -------------------------------------------------------------------------
# 6. Kube-Scheduler BinPacking (MostAllocated + BalancedAllocation)
# -------------------------------------------------------------------------
def select_node_kube_binpacking(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    best_nid = feasible_nodes[0]["id"]
    max_score = -float("inf")

    # Prefer currently active nodes first to consolidate
    active_set = set(state["active_node_ids"])

    for n in feasible_nodes:
        nid = n["id"]
        new_cpu = state["allocated_cpu"][nid] + pod["cpu"]
        new_mem = state["allocated_mem"][nid] + pod["mem"]
        u_cpu = new_cpu / n["cpu_capacity"]
        u_mem = new_mem / n["mem_capacity"]

        # MostAllocated: reward higher utilization on active node
        most_alloc = 0.5 * (u_cpu + u_mem) * 50.0
        # BalancedAllocation
        imbalance = abs(u_cpu - u_mem)
        balanced = (1.0 - imbalance) * 50.0

        score = most_alloc + balanced
        # Heavy bonus for keeping pod on an already active node
        if nid in active_set:
            score += 100.0

        if score > max_score:
            max_score = score
            best_nid = nid

    return best_nid


# -------------------------------------------------------------------------
# 7. Random Feasible
# -------------------------------------------------------------------------
def get_random_node_fn(seed: int = 42):
    rng = random.Random(seed)
    def select_node_random(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
        return rng.choice(feasible_nodes)["id"]
    return select_node_random


BASELINES: Dict[str, Dict[str, Any]] = {
    "first_fit": {
        "name": "First Fit",
        "select_pod": select_pod_fifo,
        "select_node": select_node_first_fit
    },
    "best_fit": {
        "name": "Best Fit (Least Residual)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_best_fit
    },
    "worst_fit": {
        "name": "Worst Fit (Load Balancing)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_worst_fit
    },
    "best_fit_decreasing": {
        "name": "Best Fit Decreasing (Norm Vector)",
        "select_pod": select_pod_bfd,
        "select_node": select_node_best_fit
    },
    "kube_default": {
        "name": "Kube-Scheduler Default (LeastAllocated)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_kube_default
    },
    "kube_binpacking": {
        "name": "Kube-Scheduler BinPacking (MostAllocated)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_kube_binpacking
    },
    "random_feasible": {
        "name": "Random Feasible",
        "select_pod": select_pod_fifo,
        "select_node": get_random_node_fn(seed=42)
    }
}
