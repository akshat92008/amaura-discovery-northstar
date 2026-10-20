def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    import math

    if not bin_remaining:
        return -1

    # Compute recent item statistics
    if recent_items:
        avg_recent = sum(recent_items) / len(recent_items)
        variance = sum((x - avg_recent) ** 2 for x in recent_items) / len(recent_items)
        std_recent = math.sqrt(variance) if variance > 0 else 0.0
    else:
        avg_recent = item
        std_recent = 0.0

    # Estimate future item size (use recent average as proxy)
    future_avg = avg_recent

    feasible = [(i, r) for i, r in enumerate(bin_remaining) if r >= item - 1e-6]

    if not feasible:
        return -1

    best_idx = -1
    best_score = float('inf')

    for i, remaining in feasible:
        leftover = remaining - item

        # Penalize bins where leftover is too small to fit future items
        # but not zero (wasted fragmentation)
        if leftover < 1e-6:
            # Perfect fit - very good
            fragmentation_penalty = 0.0
        else:
            # How well does leftover accommodate future items?
            # Ideal: leftover is a multiple of future_avg or at least >= future_avg
            if future_avg > 1e-6:
                # Prefer leftover that can fit at least one more item
                fits_future = leftover / future_avg
                # Penalize if leftover is too small to fit future avg item
                if leftover < future_avg - std_recent:
                    # Wasted space - high penalty
                    fragmentation_penalty = leftover / bin_capacity * 2.0
                else:
                    # Can fit future items - prefer tighter fit
                    # Score based on how close to ideal packing
                    ideal_leftover = (math.floor(fits_future)) * future_avg
                    waste = leftover - ideal_leftover
                    fragmentation_penalty = waste / bin_capacity
            else:
                fragmentation_penalty = leftover / bin_capacity

        # Primary: minimize leftover (best fit style)
        # Secondary: fragmentation awareness
        score = leftover / bin_capacity + fragmentation_penalty * 0.5

        if score < best_score:
            best_score = score
            best_idx = i

    # Decide whether to open a new bin
    # If best leftover is very small (near perfect fit) or we found a good bin, use it
    if best_idx >= 0:
        best_remaining = bin_remaining[best_idx]
        leftover = best_remaining - item
        # Open new bin if item is large and leftover would be wasteful
        # and we expect future large items
        if (future_avg > bin_capacity * 0.4 and
                leftover > bin_capacity * 0.3 and
                leftover < future_avg - std_recent * 0.5):
            return -1
        return best_idx

    return -1