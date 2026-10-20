# Discovered by Amaura Engine
# Generation: 0, ID: e42bc86a
# Fitness: 6.6839, Raw Score: 58.7167
# Mutation Type: seed_best_fit

def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    # Best Fit: pack into bin with least remaining space
    return -remaining_capacity
