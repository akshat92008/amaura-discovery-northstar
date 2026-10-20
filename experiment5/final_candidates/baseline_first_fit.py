def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    """Standard First Fit: choose first feasible bin."""
    for i, rem in enumerate(bin_remaining):
        if rem >= item - 1e-6:
            return i
    return -1
