def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """Simple Natural Greedy: pick the first uncolored vertex."""
    return uncolored[0]
