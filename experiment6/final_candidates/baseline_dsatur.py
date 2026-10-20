def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """
    DSATUR Algorithm (Brélaz, 1979):
    Select vertex with maximum saturation degree.
    Ties broken by maximum degree in uncolored subgraph.
    """
    best_v = uncolored[0]
    best_sat = -1
    best_uncolored_deg = -1

    for v in uncolored:
        sat = saturation[v]
        if sat > best_sat:
            best_sat = sat
            uncolored_deg = sum(1 for u in adj[v] if colors[u] == -1)
            best_uncolored_deg = uncolored_deg
            best_v = v
        elif sat == best_sat:
            uncolored_deg = sum(1 for u in adj[v] if colors[u] == -1)
            if uncolored_deg > best_uncolored_deg:
                best_uncolored_deg = uncolored_deg
                best_v = v

    return best_v
