# Discovered by Amaura Engine
# Generation: 0, ID: 4d975b69
# Fitness: 58.5893, Raw Score: 59.6000
# Mutation Type: seed_lfu

def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # LFU: lower frequency = lower score = evicted
    return float(frequency)
