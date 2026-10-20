import math

def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """
    Given an incoming item and the remaining capacity of a candidate open bin,
    compute a priority score (float). The item will be placed into the
    feasible bin with the HIGHEST priority score.
    
    Priority is calculated as follows:
    - If the item fits exactly, it gets a score of 0.0.
    - If the item does not fit exactly but fits within half of the bin capacity,
      it gets a score of 1.0.
    - Otherwise, it gets a score proportional to how much space is left in the bin
      after placing the item.
    """
    if remaining_capacity >= item:
        return 0.0
    elif remaining_capacity + item <= bin_capacity / 2:
        return 1.0
    else:
        return (bin_capacity - remaining_capacity) / bin_capacity

# Example usage:
item_weight = 30.0
remaining_bin_space = 75.0
max_bin_capacity = 100.0
priority_score = priority(item_weight, remaining_bin_space, max_bin_capacity)
print(f"Priority score for item {item_weight} in bin with capacity {max_bin_capacity}: {priority_score}")