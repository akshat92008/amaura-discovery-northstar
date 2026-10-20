"""
Experiment #15 Cloud Pod Scheduling Simulator
==============================================
Dual-mode deterministic simulator:
1. Mode A: Dynamic Trace Replay (Discrete-Event Simulation over time)
2. Mode B: Static Packing Windows (Direct backwards-comparability with Exp 13/14)
"""

import copy
import heapq
import math
import time
from typing import Dict, Any, List, Optional, Callable, Set, Tuple


# =========================================================================
# MODE B: Static Packing Simulation (Backwards-Compatible with Exp 13/14)
# =========================================================================
def simulate_static_packing(
    instance: Dict[str, Any],
    select_node_fn: Callable[[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]], int],
    select_pod_fn: Optional[Callable[[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]], int]] = None
) -> Dict[str, Any]:
    """
    Deterministic static placement of a batch of pods onto available cluster nodes.
    Used for Mode B (Static Packing Windows).
    """
    start_time = time.perf_counter()
    nodes: List[Dict[str, Any]] = instance["nodes"]
    pods: List[Dict[str, Any]] = instance["pods"]

    node_map = {n["id"]: n for n in nodes}
    pod_map = {p["id"]: p for p in pods}

    allocated_cpu: Dict[Any, float] = {n["id"]: 0.0 for n in nodes}
    allocated_mem: Dict[Any, float] = {n["id"]: 0.0 for n in nodes}
    placed_pods: Dict[Any, List[Any]] = {n["id"]: [] for n in nodes}
    active_nodes: Set[Any] = set()
    unscheduled_pods: List[Any] = []

    pending_pods = list(pods)
    decisions_count = 0

    while pending_pods:
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

        # 2. Feasible nodes
        feasible_nodes = [
            n for n in nodes
            if (node_map[n["id"]]["cpu_capacity"] - allocated_cpu[n["id"]] >= pod["cpu"] - 1e-9)
            and (node_map[n["id"]]["mem_capacity"] - allocated_mem[n["id"]] >= pod["mem"] - 1e-9)
        ]

        if not feasible_nodes:
            unscheduled_pods.append(pod["id"])
            continue

        # 3. Select node
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
        decisions_count += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Metrics calculation
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
        "active_cpu_utilization": round(used_cpu / active_cap_cpu, 4) if active_cap_cpu > 0 else 0.0,
        "active_mem_utilization": round(used_mem / active_cap_mem, 4) if active_cap_mem > 0 else 0.0,
        "runtime_ms": round(elapsed_ms, 3),
        "decisions_per_sec": round(decisions_count / (elapsed_ms / 1000.0), 1) if elapsed_ms > 0 else 0.0
    }


# =========================================================================
# MODE A: Dynamic Trace Replay Simulator (Discrete Event Over Time)
# =========================================================================
def simulate_dynamic_replay(
    trace: Dict[str, Any],
    select_node_fn: Callable[[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]], int],
    select_pod_fn: Optional[Callable[[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]], int]] = None
) -> Dict[str, Any]:
    """
    Simulates dynamic arrival and departure of pods across real time.
    Pods arrive according to their arrival timestamps, are scheduled onto feasible nodes,
    and depart upon duration completion.
    Idle nodes scale to zero; active nodes accumulate node-seconds while harboring pods.
    """
    start_time_perf = time.perf_counter()
    nodes: List[Dict[str, Any]] = trace["nodes"]
    events: List[Dict[str, Any]] = trace["events"]  # sorted by timestamp

    node_map = {n["id"]: n for n in nodes}

    allocated_cpu: Dict[Any, float] = {n["id"]: 0.0 for n in nodes}
    allocated_mem: Dict[Any, float] = {n["id"]: 0.0 for n in nodes}
    placed_pods_by_node: Dict[Any, Set[Any]] = {n["id"]: set() for n in nodes}

    # Tracking active intervals for node-hours calculation
    node_last_activated: Dict[Any, Optional[float]] = {n["id"]: None for n in nodes}
    node_total_active_seconds: Dict[Any, float] = {n["id"]: 0.0 for n in nodes}
    node_activation_count: Dict[Any, int] = {n["id"]: 0 for n in nodes}

    # Time-series sampling for peak and average metrics
    current_active_nodes: Set[Any] = set()
    peak_active_nodes = 0
    unscheduled_pods: List[Any] = []
    scheduled_pods_count = 0

    # Departure priority queue: list of (departure_time, pod_dict, node_id)
    # Since events are chronological, we step event by event
    sim_start_t = trace.get("start_time", 0)
    sim_end_t = trace.get("end_time", events[-1]["timestamp"] if events else 0)

    # Active departures min-heap: (departure_time, tie_breaker_int, pod_dict, node_id)
    departures: List[Tuple[float, int, Dict[str, Any], Any]] = []

    def process_departures_until(target_t: float):
        nonlocal departures, current_active_nodes
        while departures and departures[0][0] <= target_t:
            dep_t, _, p, nid = heapq.heappop(departures)
            # Release resources
            allocated_cpu[nid] = max(0.0, allocated_cpu[nid] - p["cpu"])
            allocated_mem[nid] = max(0.0, allocated_mem[nid] - p["mem"])
            placed_pods_by_node[nid].discard(p["id"])

            # Check if node became completely idle
            if len(placed_pods_by_node[nid]) == 0 and nid in current_active_nodes:
                current_active_nodes.remove(nid)
                if node_last_activated[nid] is not None:
                    t_on = node_last_activated[nid]
                    t_off = dep_t
                    clamped_start = max(t_on, sim_start_t)
                    clamped_end = min(t_off, sim_end_t)
                    if clamped_end > clamped_start:
                        node_total_active_seconds[nid] += (clamped_end - clamped_start)
                    node_last_activated[nid] = None

    decisions_count = 0

    # Process arrival events
    for ev in events:
        ev_t = ev["timestamp"]
        process_departures_until(ev_t)

        pod = ev["pod"]

        # Build state snapshot
        remaining_cpu = {nid: node_map[nid]["cpu_capacity"] - allocated_cpu[nid] for nid in node_map}
        remaining_mem = {nid: node_map[nid]["mem_capacity"] - allocated_mem[nid] for nid in node_map}

        state_snapshot = {
            "allocated_cpu": dict(allocated_cpu),
            "allocated_mem": dict(allocated_mem),
            "remaining_cpu": remaining_cpu,
            "remaining_mem": remaining_mem,
            "active_node_ids": list(current_active_nodes),
            "placed_pods_count": {nid: len(placed_pods_by_node[nid]) for nid in placed_pods_by_node},
            "sim_time": ev_t
        }

        # Feasible nodes
        feasible_nodes = [
            n for n in nodes
            if (node_map[n["id"]]["cpu_capacity"] - allocated_cpu[n["id"]] >= pod["cpu"] - 1e-9)
            and (node_map[n["id"]]["mem_capacity"] - allocated_mem[n["id"]] >= pod["mem"] - 1e-9)
        ]

        if not feasible_nodes:
            unscheduled_pods.append(pod["id"])
            continue

        # Invoke policy
        chosen_node_id = None
        try:
            candidate_node_id = select_node_fn(dict(pod), list(feasible_nodes), state_snapshot)
            if any(n["id"] == candidate_node_id for n in feasible_nodes):
                chosen_node_id = candidate_node_id
        except Exception:
            pass

        if chosen_node_id is None:
            chosen_node_id = feasible_nodes[0]["id"]

        # Place pod
        allocated_cpu[chosen_node_id] += pod["cpu"]
        allocated_mem[chosen_node_id] += pod["mem"]
        placed_pods_by_node[chosen_node_id].add(pod["id"])
        decisions_count += 1
        scheduled_pods_count += 1

        # Node activation
        if chosen_node_id not in current_active_nodes:
            current_active_nodes.add(chosen_node_id)
            node_last_activated[chosen_node_id] = ev_t
            node_activation_count[chosen_node_id] += 1

        peak_active_nodes = max(peak_active_nodes, len(current_active_nodes))

        # Schedule departure
        duration = pod.get("duration_sec", 3600.0)  # default 1 hour if unspecified
        dep_time = ev_t + duration
        heapq.heappush(departures, (dep_time, decisions_count, pod, chosen_node_id))

    # Process all remaining departures until sim_end_t
    process_departures_until(sim_end_t)

    # For any nodes still active at sim_end_t, close their active window
    for nid in list(current_active_nodes):
        if node_last_activated[nid] is not None:
            t_on = node_last_activated[nid]
            clamped_start = max(t_on, sim_start_t)
            clamped_end = sim_end_t
            if clamped_end > clamped_start:
                node_total_active_seconds[nid] += (clamped_end - clamped_start)
            node_last_activated[nid] = None

    elapsed_ms = (time.perf_counter() - start_time_perf) * 1000.0
    sim_total_hours = max(0.001, (sim_end_t - sim_start_t) / 3600.0)

    # Cost calculation: node-hours * hourly cost rate
    total_node_seconds = sum(node_total_active_seconds.values())
    total_node_hours = total_node_seconds / 3600.0

    total_infra_cost = sum(
        node_map[nid]["cost_per_hour"] * (node_total_active_seconds[nid] / 3600.0)
        for nid in node_map
    )

    avg_active_nodes = total_node_hours / sim_total_hours if sim_total_hours > 0 else 0.0

    unscheduled_penalty = 1000.0 * len(unscheduled_pods)
    final_objective_cost = total_infra_cost + unscheduled_penalty

    return {
        "is_valid": True,
        "total_cost": round(final_objective_cost, 4),
        "infrastructure_cost": round(total_infra_cost, 4),
        "node_hours": round(total_node_hours, 4),
        "avg_active_nodes": round(avg_active_nodes, 2),
        "peak_active_nodes": peak_active_nodes,
        "total_node_activations": sum(node_activation_count.values()),
        "unscheduled_count": len(unscheduled_pods),
        "scheduled_count": scheduled_pods_count,
        "total_pods": len(events),
        "placement_feasibility": round(scheduled_pods_count / len(events), 4) if events else 1.0,
        "sim_duration_hours": round(sim_total_hours, 2),
        "runtime_ms": round(elapsed_ms, 3),
        "decisions_per_sec": round(decisions_count / (elapsed_ms / 1000.0), 1) if elapsed_ms > 0 else 0.0
    }
