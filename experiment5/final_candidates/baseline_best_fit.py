def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    """Standard Best Fit: choose feasible bin with least remaining space."""
    best_idx = -1
    min_rem = float("inf")
    for i, rem in enumerate(bin_remaining):
        if rem >= item - 1e-6 and rem < min_rem:
            min_rem = rem
            best_idx = i
    return best_idx
