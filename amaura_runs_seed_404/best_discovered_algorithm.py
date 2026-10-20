# Discovered by Amaura Engine
# Generation: 18, ID: cb1279d5
# Fitness: 58.7400, Raw Score: 60.3067
# Mutation Type: ast_cache_decay_injection

def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # Discovered adaptive frequency-recency decay policy
    alpha = 1.0
    beta = 0.33
    return (float(frequency) ** alpha) / ((float(recency) + 1.0) ** beta)
