def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """
    Welsh-Powell Algorithm (Largest First, 1967):
    Select uncolored vertex with highest original degree.
    """
    best_v = uncolored[0]
    best_deg = -1
    for v in uncolored:
        if degrees[v] > best_deg:
            best_deg = degrees[v]
            best_v = v
    return best_v
