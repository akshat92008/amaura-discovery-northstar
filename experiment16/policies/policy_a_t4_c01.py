import math

def select_node(pod: dict, feasible_nodes: list[dict], state: dict) -> int:
    """
    Aggressive Node Consolidation:
    - Prefer already active nodes (those in state["active_node_ids"]).
    - Among active nodes, choose the one that will incur the smallest resource imbalance
      after placing the pod (|u_cpu - u_mem|). Lower imbalance reduces stranded capacity.
    - If multiple nodes tie on imbalance, pick the cheaper node (lower cost_per_hour).
    - If no active node is feasible, fall back to the same criteria over inactive nodes,
      thus activating a new node only when necessary.
    """
    best_node_id = None
    best_key = None  # tuple: (is_inactive_flag, imbalance, cost)

    for node in feasible_nodes:
        nid = node["id"]
        # Current allocation from state (default 0 if not present)
        alloc_cpu = state["allocated_cpu"].get(nid, 0.0)
        alloc_mem = state["allocated_mem"].get(nid, 0.0)

        cap_cpu = node["cpu_capacity"]
        cap_mem = node["mem_capacity"]
        # Avoid division by zero (should not happen with valid capacities)
        u_cpu = alloc_cpu / cap_cpu if cap_cpu > 0 else 0.0
        u_mem = alloc_mem / cap_mem if cap_mem > 0 else 0.0

        # Determine if node is already active
        is_active = nid in state.get("active_node_ids", [])
        # After placing the pod
        new_alloc_cpu = alloc_cpu + pod["cpu"]
        new_alloc_mem = alloc_mem + pod["mem"]
        new_u_cpu = new_alloc_cpu / cap_cpu if cap_cpu > 0 else 0.0
        new_u_mem = new_alloc_mem / cap_mem if cap_mem > 0 else 0.0
        imbalance = abs(new_u_cpu - new_u_mem)  # resource skew to minimize

        cost = node["cost_per_hour"]
        # Primary: prefer active nodes (is_active => flag 0), else flag 1
        # Secondary: lower imbalance
        # Tertiary: lower cost
        key = (0 if is_active else 1, imbalance, cost)

        if best_key is None or key < best_key:
            best_key = key
            best_node_id = nid

    # best_node_id should always be set because feasible_nodes is non-empty
    return best_node_id if best_node_id is not None else -1

def select_pod(pending_pods: list[dict], nodes: list[dict], state: dict) -> int:
    """
    Optional pod ordering heuristic: schedule larger/more demanding pods first.
    We approximate pod size by the sum of normalized CPU and memory demands
    relative to the average node capacities in the cluster.
    """
    if not pending_pods:
        return -1

    # Compute average capacities across all nodes (guard against empty nodes list)
    if nodes:
        avg_cpu = sum(n["cpu_capacity"] for n in nodes) / len(nodes)
        avg_mem = sum(n["mem_capacity"] for n in nodes) / len(nodes)
    else:
        avg_cpu = avg_mem = 1.0  # fallback to avoid division by zero

    best_pod_id = None
    best_score = -1.0

    for pod in pending_pods:
        # Normalized demand score (higher = bigger/more constrained pod)
        score = (pod["cpu"] / avg_cpu if avg_cpu > 0 else 0.0) + \
                (pod["mem"] / avg_mem if avg_mem > 0 else 0.0)
        if score > best_score:
            best_score = score
            best_pod_id = pod["id"]

    return best_pod_id if best_pod_id is not None else -1