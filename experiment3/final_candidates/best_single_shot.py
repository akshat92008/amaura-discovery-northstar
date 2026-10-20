def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """
    Given an incoming item and the remaining_capacity of a candidate open bin,
    compute a priority score (float). The item will be placed into the
    feasible bin with the HIGHEST priority score.
    """
    import math
    
    # Remaining space after placing the item
    leftover = remaining_capacity - item
    
    # Best Fit: prefer bins that leave the least leftover space
    # But we add enhancements to handle edge cases better
    
    # Normalize leftover as fraction of bin capacity
    leftover_frac = leftover / bin_capacity
    
    # Base score: negative leftover (best fit heuristic)
    # Higher score = less leftover = tighter fit
    base_score = -leftover_frac
    
    # Bonus for near-perfect fits (leftover very small)
    # This strongly rewards bins that get nearly filled
    if leftover_frac < 0.1:
        bonus = (0.1 - leftover_frac) * 5.0
    else:
        bonus = 0.0
    
    # Penalty for bins that would leave an awkward medium gap
    # Medium gaps (0.1 to 0.3) are hard to fill efficiently
    if 0.1 <= leftover_frac <= 0.3:
        penalty = (leftover_frac - 0.1) * 0.5
    else:
        penalty = 0.0
    
    # Additional: prefer bins that are more filled overall
    # (remaining_capacity is small relative to bin_capacity)
    fill_level = 1.0 - (remaining_capacity / bin_capacity)
    fill_bonus = fill_level * 0.3
    
    return base_score + bonus - penalty + fill_bonus