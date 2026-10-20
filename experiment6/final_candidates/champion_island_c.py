def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """
    Args:
    - uncolored: list[int], non-empty list of remaining uncolored vertex IDs
    - adj: list[list[int]], graph adjacency list (adj[u] contains all neighbor IDs of vertex u)
    - colors: list[int], length |V|, colors[u] is the non-negative integer color assigned to vertex u, or -1 if uncolored
    - saturation: list[int], length |V|, saturation[u] is the number of distinct colors assigned to neighbors of vertex u
    - degrees: list[int], length |V|, degrees[u] is the original degree of vertex u

    Returns:
    - int: the vertex ID from `uncolored` that should be colored next.
    """
    uncolored_set = set(uncolored)
    
    best_vertex = None
    best_score = None
    
    for v in uncolored:
        sat_v = saturation[v]
        deg_v = degrees[v]
        
        # Count uncolored neighbors (future conflict potential)
        uncolored_neighbors = [u for u in adj[v] if u in uncolored_set]
        uncolored_deg = len(uncolored_neighbors)
        
        # Compute 2-hop saturation pressure: sum of saturations of uncolored neighbors
        # High value means coloring v will be hard for its neighbors
        neighbor_sat_sum = sum(saturation[u] for u in uncolored_neighbors)
        
        # Count distinct colors in 2-hop neighborhood that are already used
        two_hop_colors = set()
        for u in uncolored_neighbors:
            for w in adj[u]:
                if colors[w] >= 0:
                    two_hop_colors.add(colors[w])
        two_hop_sat = len(two_hop_colors)
        
        # Primary: highest saturation (DSATUR base)
        # Secondary: highest degree among uncolored neighbors (most constrained future)
        # Tertiary: highest 2-hop saturation pressure
        # We negate for min-heap style comparison (we want max)
        score = (sat_v, deg_v, two_hop_sat, neighbor_sat_sum)
        
        if best_score is None or score > best_score:
            best_score = score
            best_vertex = v
    
    return best_vertex