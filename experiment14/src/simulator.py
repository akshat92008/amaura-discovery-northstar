"""
Kubernetes-Style Cloud Pod Scheduling Simulator
================================================
Deterministic simulation of cloud pod placement onto heterogeneous worker nodes.

Entities:
- Pod: CPU and Memory requirements (cores, GB)
- Node: CPU and Memory capacities (cores, GB), hourly cost rate ($)
- State: Allocated resources, remaining capacities, active nodes, placement history

Objective Function (Lower is Better):
Cost = Sum_{j in Active} [ Cost_j * (1.0 + 0.2 * |u_cpu_j - u_mem_j|) ] + 1000.0 * N_unscheduled
Where:
- Cost_j: Hourly rate for node j
- u_cpu_j = allocated_cpu / cpu_capacity
- u_mem_j = allocated_mem / mem_capacity
- Active nodes: Nodes with at least 1 placed pod (idle nodes cost 0 via autoscaling to zero)
- Unscheduled penalty: 1000.0 per unplaceable pod (hard constraint enforcement)
"""

import copy
import math
from typing import Dict, Any, List, Optional, Callable, Set, Tuple


def simulate_schedule(
    instance: Dict[str, Any],
    select_node_fn: Callable[[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]], int],
    select_pod_fn: Optional[Callable[[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]], int]] = None
) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = instance["nodes"]
    pods: List[Dict[str, Any]] = instance["pods"]

    node_map = {n["id"]: n for n in nodes}
    pod_map = {p["id"]: p for p in pods}

    allocated_cpu: Dict[int, float] = {n["id"]: 0.0 for n in nodes}
    allocated_mem: Dict[int, float] = {n["id"]: 0.0 for n in nodes}
    placed_pods: Dict[int, List[int]] = {n["id"]: [] for n in nodes}
    active_nodes: Set[int] = set()
    unscheduled_pods: List[int] = []

    pending_pods = list(pods)

    # Simulation loop
    while pending_pods:
        # Construct read-only state snapshot for candidate
        remaining_cpu = {nid: node_map[nid]["cpu_capacity"] - allocated_cpu[nid] for nid in node_map}
        remaining_mem = {nid: node_map[nid]["mem_capacity"] - allocated_mem[nid] for nid in node_map}

        state_snapshot = {
            "allocated_cpu": dict(allocated_cpu),
            "allocated_mem": dict(allocated_mem),
            "remaining_cpu": remaining_cpu,
            "remaining_mem": remaining_mem,
            "active_node_ids": list(active_nodes),
            "placed_pods_count": {nid: len(placed_pods[nid]) for nid in placed_pods}
        }

        # 1. Select next pod to schedule
        chosen_pod_id = None
        if select_pod_fn is not None:
            try:
                candidate_pod_id = select_pod_fn(list(pending_pods), list(nodes), state_snapshot)
                if any(p["id"] == candidate_pod_id for p in pending_pods):
                    chosen_pod_id = candidate_pod_id
            except Exception:
                pass

        if chosen_pod_id is None:
            chosen_pod_id = pending_pods[0]["id"]

        pod = pod_map[chosen_pod_id]
        pending_pods = [p for p in pending_pods if p["id"] != chosen_pod_id]

        # 2. Determine feasible nodes (hard resource constraints)
        feasible_nodes = [
            n for n in nodes
            if (node_map[n["id"]]["cpu_capacity"] - allocated_cpu[n["id"]] >= pod["cpu"] - 1e-9)
            and (node_map[n["id"]]["mem_capacity"] - allocated_mem[n["id"]] >= pod["mem"] - 1e-9)
        ]

        if not feasible_nodes:
            unscheduled_pods.append(pod["id"])
            continue

        # 3. Select node from feasible nodes
        chosen_node_id = None
        try:
            candidate_node_id = select_node_fn(dict(pod), list(feasible_nodes), state_snapshot)
            if any(n["id"] == candidate_node_id for n in feasible_nodes):
                chosen_node_id = candidate_node_id
        except Exception:
            pass

        if chosen_node_id is None:
            chosen_node_id = feasible_nodes[0]["id"]

        # 4. State update
        allocated_cpu[chosen_node_id] += pod["cpu"]
        allocated_mem[chosen_node_id] += pod["mem"]
        placed_pods[chosen_node_id].append(pod["id"])
        active_nodes.add(chosen_node_id)

    # 5. Calculate Metrics and Objective Score
    total_cost = 0.0
    active_base_cost = 0.0
    fragmentation_cost = 0.0
    node_imbalances = []

    for nid in active_nodes:
        n = node_map[nid]
        c_cpu = n["cpu_capacity"]
        c_mem = n["mem_capacity"]
        u_cpu = allocated_cpu[nid] / c_cpu if c_cpu > 0 else 0.0
        u_mem = allocated_mem[nid] / c_mem if c_mem > 0 else 0.0
        imbalance = abs(u_cpu - u_mem)
        node_imbalances.append(imbalance)

        base_c = n["cost_per_hour"]
        frag_c = base_c * 0.2 * imbalance
        active_base_cost += base_c
        fragmentation_cost += frag_c
        total_cost += (base_c + frag_c)

    unscheduled_penalty = 1000.0 * len(unscheduled_pods)
    total_cost += unscheduled_penalty

    # Utilization statistics
    total_cluster_cpu = sum(n["cpu_capacity"] for n in nodes)
    total_cluster_mem = sum(n["mem_capacity"] for n in nodes)
    used_cpu = sum(allocated_cpu.values())
    used_mem = sum(allocated_mem.values())

    active_cap_cpu = sum(node_map[nid]["cpu_capacity"] for nid in active_nodes) if active_nodes else 0.0
    active_cap_mem = sum(node_map[nid]["mem_capacity"] for nid in active_nodes) if active_nodes else 0.0

    return {
        "is_valid": True,
        "total_cost": round(total_cost, 4),
        "active_base_cost": round(active_base_cost, 4),
        "fragmentation_cost": round(fragmentation_cost, 4),
        "unscheduled_penalty": round(unscheduled_penalty, 4),
        "unscheduled_count": len(unscheduled_pods),
        "active_nodes_count": len(active_nodes),
        "total_nodes": len(nodes),
        "placed_pods_count": len(pods) - len(unscheduled_pods),
        "total_pods": len(pods),
        "mean_active_imbalance": round(sum(node_imbalances) / len(node_imbalances), 4) if node_imbalances else 0.0,
        "cluster_cpu_utilization": round(used_cpu / total_cluster_cpu, 4) if total_cluster_cpu > 0 else 0.0,
        "cluster_mem_utilization": round(used_mem / total_cluster_mem, 4) if total_cluster_mem > 0 else 0.0,
        "active_cpu_utilization": round(used_cpu / active_cap_cpu, 4) if active_cap_cpu > 0 else 0.0,
        "active_mem_utilization": round(used_mem / active_cap_mem, 4) if active_cap_mem > 0 else 0.0,
        "placed_pods": placed_pods,
        "unscheduled_pods": unscheduled_pods
    }
