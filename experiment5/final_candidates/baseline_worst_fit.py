def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    """Standard Worst Fit: choose feasible bin with most remaining space."""
    best_idx = -1
    max_rem = -1.0
    for i, rem in enumerate(bin_remaining):
        if rem >= item - 1e-6 and rem > max_rem:
            max_rem = rem
            best_idx = i
    return best_idx
