def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """
    Given an incoming item and the remaining_capacity of a candidate open bin,
    compute a priority score (float). The item will be placed into the
    feasible bin with the HIGHEST priority score.
    """
    import math
    
    # Remaining space after placing item
    leftover = remaining_capacity - item
    
    # Utilization after placement (how full the bin becomes)
    fill_ratio = (bin_capacity - leftover) / bin_capacity
    
    # Penalize "awkward" leftover gaps that are hard to fill
    # A leftover near 0 is great (bin nearly full)
    # A leftover that's a significant fraction is bad if it's too small to be useful
    # but large enough to waste space
    
    # Normalize leftover
    leftover_ratio = leftover / bin_capacity
    
    # Penalty for creating a gap that's hard to fill:
    # Small gaps (< ~10% of capacity) are fine - bin is nearly full
    # Large gaps (> ~50% of capacity) are okay - still room for more items
    # Medium gaps (~20-40%) are worst - might be hard to fill exactly
    
    # Use a smooth penalty: penalize gaps in the "awkward" middle range
    # The ideal is leftover = 0 (perfect fit) or leftover large enough to be useful
    
    # Primary score: prefer bins where item fits tightly (Best Fit style)
    # but also consider whether leftover is "useful"
    
    # Penalty inspired by: gaps near 1/3 or 1/4 of bin are hardest to fill
    # because they need specific item sizes
    awkward_penalty = 0.0
    if leftover_ratio > 0.01:  # not a near-perfect fit
        # Penalize if leftover is in a range that's hard to fill
        # (too small for most items but not negligible)
        # Use a sinusoidal penalty that peaks at awkward fractions
        awkward_penalty = math.exp(-((leftover_ratio - 0.25) ** 2) / (2 * 0.1 ** 2)) * 0.3
        awkward_penalty += math.exp(-((leftover_ratio - 0.15) ** 2) / (2 * 0.08 ** 2)) * 0.2
    
    # Main priority: higher fill ratio is better, minus awkward penalty
    score = fill_ratio - awkward_penalty
    
    return score