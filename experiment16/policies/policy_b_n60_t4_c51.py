def select_node(pod: dict, feasible_nodes: list[dict], state: dict) -> int:
    """
    Select a node for the given pod using a lexicographic ranking:
      1. Prefer already‑active nodes (is_inactive = 0) over inactive ones.
      2. Among those, choose the placement that yields the smallest resource imbalance
         after the pod is added (|u_cpu - u_mem|).
      3. Finally, break ties by selecting the node with the lowest hourly cost.
    Returns the node_id of the chosen feasible node.
    """
    pod_cpu = pod["cpu"]
    pod_mem = pod["mem"]
    best_key = None
    best_node_id = None

    # Helper to fetch placed pod count; default 0 if missing.
    placed_counts = state.get("placed_pods_count", {})

    for node in feasible_nodes:
        nid = node["id"]
        # Determine if node is already active (has at least one pod)
        is_inactive = 0 if placed_counts.get(nid, 0) > 0 else 1

        # Current allocation on this node
        alloc_cpu = state["allocated_cpu"].get(nid, 0.0) + pod_cpu
        alloc_mem = state["allocated_mem"].get(nid, 0.0) + pod_mem

        # Utilization ratios after placing the pod
        cap_cpu = node["cpu_capacity"]
        cap_mem = node["mem_capacity"]
        u_cpu = alloc_cpu / cap_cpu if cap_cpu > 0 else 0.0
        u_mem = alloc_mem / cap_mem if cap_mem > 0 else 0.0

        # Resource imbalance (skew)
        imbalance = abs(u_cpu - u_mem)

        # Hourly cost of the node
        cost = node["cost_per_hour"]

        # Lexicographic key: (is_inactive, imbalance, cost)
        key = (is_inactive, imbalance, cost)

        if best_key is None or key < best_key:
            best_key = key
            best_node_id = nid

    # Assuming feasible_nodes is non‑empty as per problem statement.
    return best_node_id