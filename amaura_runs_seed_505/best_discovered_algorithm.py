# Discovered by Amaura Engine
# Generation: 0, ID: 0b53a9ee
# Fitness: 57.6472, Raw Score: 60.3947
# Mutation Type: seed_lfu

def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # LFU: lower frequency = lower score = evicted
    return float(frequency)
