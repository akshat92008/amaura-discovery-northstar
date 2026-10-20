def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """
    Given an incoming item and the remaining_capacity of a candidate open bin,
    compute a priority score (float). The item will be placed into the
    feasible bin with the HIGHEST priority score.
    """
    # Remaining space after placing the item
    leftover = remaining_capacity - item
    
    # Normalize leftover as fraction of bin capacity
    leftover_frac = leftover / bin_capacity
    
    # Item size as fraction of bin capacity
    item_frac = item / bin_capacity
    
    # Current fill level before placing item
    fill_before = 1.0 - (remaining_capacity / bin_capacity)
    
    # Fill level after placing item
    fill_after = 1.0 - leftover_frac
    
    # Core: Best Fit (negative leftover) - tighter fits are better
    base_score = -leftover_frac
    
    # Strong reward for near-perfect fits (leftover < 5% of bin)
    # These essentially close the bin efficiently
    if leftover_frac < 0.05:
        perfect_bonus = 3.0 * (0.05 - leftover_frac) / 0.05
    else:
        perfect_bonus = 0.0
    
    # Reward for fits that bring bin to high utilization (>85%)
    if fill_after > 0.85:
        high_util_bonus = (fill_after - 0.85) * 2.0
    else:
        high_util_bonus = 0.0
    
    # Penalty for leaving awkward gaps that are hard to fill
    # Gaps between 15%-45% are problematic (too big to ignore, hard to fill)
    if 0.15 <= leftover_frac <= 0.45:
        # Quadratic penalty centered around 0.3 (worst case gap)
        gap_center = 0.3
        gap_penalty = 1.5 * (1.0 - ((leftover_frac - gap_center) / 0.15) ** 2)
        gap_penalty = max(0.0, gap_penalty)
    else:
        gap_penalty = 0.0
    
    # Prefer bins that are already more filled (use existing bins efficiently)
    # This helps consolidate items into fewer bins
    fill_bonus = fill_before * 0.2
    
    # Small bonus for item-to-bin ratio alignment
    # If item fills a nice fraction of the bin, reward it
    alignment_bonus = 0.0
    for fraction in [0.5, 1.0/3.0, 0.25, 2.0/3.0, 0.75]:
        if abs(item_frac - fraction) < 0.03:
            alignment_bonus = 0.1
            break
    
    return base_score + perfect_bonus + high_util_bonus - gap_penalty + fill_bonus + alignment_bonus