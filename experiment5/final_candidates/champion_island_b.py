def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    import math

    if not bin_remaining:
        return -1

    feasible = [(i, r) for i, r in enumerate(bin_remaining) if r >= item - 1e-6]
    if not feasible:
        return -1

    if recent_items:
        avg = sum(recent_items) / len(recent_items)
        std = math.sqrt(sum((x - avg)**2 for x in recent_items) / len(recent_items)) if len(recent_items) > 1 else avg * 0.2
    else:
        avg = item
        std = item * 0.2

    small_threshold = max(avg - 1.5 * std, bin_capacity * 0.04)
    orphan_lo = small_threshold
    orphan_hi = max(avg - 0.25 * std, small_threshold + 1e-6)

    best_idx = -1
    best_score = float('inf')

    for i, remaining in feasible:
        leftover = remaining - item

        if leftover < 1e-6:
            score = -1000.0
        elif leftover < small_threshold:
            score = leftover / bin_capacity
        elif orphan_lo <= leftover <= orphan_hi:
            score = 2.5 + leftover / bin_capacity
        else:
            n_fits = leftover / avg if avg > 1e-9 else 0
            fractional_waste = (n_fits - math.floor(n_fits)) * avg / bin_capacity
            score = 0.5 + fractional_waste * 1.2 + (leftover / bin_capacity) * 0.08

        if score < best_score:
            best_score = score
            best_idx = i

    if best_idx >= 0:
        leftover = bin_remaining[best_idx] - item
        in_orphan = orphan_lo <= leftover <= orphan_hi
        if in_orphan and item > bin_capacity * 0.25:
            return -1
        return best_idx

    return -1