# Discovered by Amaura Engine
# Generation: 13, ID: 02f615d4
# Fitness: 56.9299, Raw Score: 60.6080
# Mutation Type: ast_constant_perturbation

def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # Discovered adaptive frequency-recency decay policy
    alpha = 1.402
    beta = 0.386
    return (float(frequency) ** alpha) / ((float(recency) + 0.91) ** beta)
