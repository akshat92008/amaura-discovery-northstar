# Discovered by Amaura Engine
# Generation: 12, ID: d4231f8f
# Fitness: 58.4157, Raw Score: 60.3893
# Mutation Type: ast_cache_decay_injection

def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # Discovered adaptive frequency-recency decay policy
    alpha = 1.38
    beta = 0.41
    return (float(frequency) ** alpha) / ((float(recency) + 1.0) ** beta)
