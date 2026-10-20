"""
Standard Baselines for Experiment #15
======================================
Pre-registered, reproducible implementations of classical heuristics and
Kubernetes scheduling plugins:

1. kube_binpacking: MostAllocated + BalancedAllocation + active node consolidation
2. kube_default: LeastAllocated + BalancedAllocation
3. first_fit: First Feasible Node
4. best_fit: Least Residual Capacity
5. best_fit_decreasing: Norm-sorted Pods + Best Fit
6. worst_fit: Spreading / Load Balancing
"""

import math
from typing import Dict, Any, List, Callable


def select_pod_fifo(pending_pods: List[Dict[str, Any]], nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    return pending_pods[0]["id"]


def select_pod_bfd(pending_pods: List[Dict[str, Any]], nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    # Pod with largest resource norm (CPU + Memory relative to typical machine ratio)
    best_p = max(pending_pods, key=lambda p: math.sqrt(p["cpu"]**2 + (p["mem"] / 1.0)**2))
    return best_p["id"]


def select_node_first_fit(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    return feasible_nodes[0]["id"]


def select_node_best_fit(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    best_nid = feasible_nodes[0]["id"]
    min_residual = float("inf")

    for n in feasible_nodes:
        nid = n["id"]
        rem_cpu = state["remaining_cpu"][nid] - pod["cpu"]
        rem_mem = state["remaining_mem"][nid] - pod["mem"]
        res_vol = (rem_cpu / n["cpu_capacity"]) + (rem_mem / n["mem_capacity"])
        if res_vol < min_residual:
            min_residual = res_vol
            best_nid = nid

    return best_nid


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


def select_node_kube_binpacking(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    best_nid = feasible_nodes[0]["id"]
    max_score = -float("inf")

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


BASELINES: Dict[str, Dict[str, Any]] = {
    "kube_binpacking": {
        "name": "Kube-Scheduler BinPacking (MostAllocated)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_kube_binpacking
    },
    "kube_default": {
        "name": "Kube-Scheduler Default (LeastAllocated)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_kube_default
    },
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
    "best_fit_decreasing": {
        "name": "Best Fit Decreasing (Norm Vector)",
        "select_pod": select_pod_bfd,
        "select_node": select_node_best_fit
    },
    "worst_fit": {
        "name": "Worst Fit (Spreading)",
        "select_pod": select_pod_fifo,
        "select_node": select_node_worst_fit
    }
}
