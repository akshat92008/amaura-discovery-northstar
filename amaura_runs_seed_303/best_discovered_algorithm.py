# Discovered by Amaura Engine
# Generation: 15, ID: fab16680
# Fitness: 58.2544, Raw Score: 59.7493
# Mutation Type: ast_constant_perturbation

def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # Discovered adaptive frequency-recency decay policy
    alpha = 1.909
    beta = 0.338
    return (float(frequency) ** alpha) / ((float(recency) + 1.323) ** beta)
