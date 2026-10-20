"""
Stage 3: Deterministic Benchmark Generator
==========================================
Generates 4 strictly separated splits for Graph Coloring (8 structural families):
- pilot.json:  24 instances (3 per family, N in [40, 70])
- dev.json:    40 instances (5 per family, N in [45, 75])
- hidden.json: 200 instances (25 per family, N in [50, 95])
- sealed.json: 40 instances (5 per family, N in [50, 95])

Guarantees:
- Master seed = 303 (fresh, zero overlap with Stage 2).
- Strictly disjoint topological edge signatures across all splits.
- Dynamic verification that sum(|V_i|) + 1 <= 19,001 across the 200 hidden graphs.
- Generates manifest.json with SHA-256 hashes.
"""

import hashlib
import json
import os
import random
from typing import List, Dict, Any, Tuple, Set, Optional


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# =========================================================================
# GRAPH COLORING GENERATORS
# =========================================================================

def gen_erdos_renyi(n: int, p: float, rng: random.Random) -> Dict[str, Any]:
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                adj[i].append(j)
                adj[j].append(i)
    return {"family": "erdos_renyi", "num_vertices": n, "adj": adj}


def gen_geometric(n: int, radius: float, rng: random.Random) -> Dict[str, Any]:
    pts = [(rng.random(), rng.random()) for _ in range(n)]
    adj = [[] for _ in range(n)]
    r2 = radius * radius
    for i in range(n):
        for j in range(i + 1, n):
            dx = pts[i][0] - pts[j][0]
            dy = pts[i][1] - pts[j][1]
            if dx * dx + dy * dy <= r2:
                adj[i].append(j)
                adj[j].append(i)
    return {"family": "geometric", "num_vertices": n, "adj": adj}


def gen_barabasi_albert(n: int, m: int, rng: random.Random) -> Dict[str, Any]:
    adj = [[] for _ in range(n)]
    m = max(1, min(m, n - 1))
    for i in range(m):
        for j in range(i + 1, m):
            adj[i].append(j)
            adj[j].append(i)

    repeated_nodes = []
    for i in range(m):
        repeated_nodes.extend([i] * (m - 1))

    for source in range(m, n):
        targets = set()
        while len(targets) < m and len(targets) < source:
            chosen = rng.choice(repeated_nodes) if repeated_nodes else rng.randint(0, source - 1)
            targets.add(chosen)
        for target in targets:
            adj[source].append(target)
            adj[target].append(source)
            repeated_nodes.append(source)
            repeated_nodes.append(target)
    return {"family": "scale_free", "num_vertices": n, "adj": adj}


def gen_mycielski_like(n: int, base_density: float, rng: random.Random) -> Dict[str, Any]:
    base_n = max(5, n // 3)
    base_adj = [[] for _ in range(base_n)]
    for i in range(base_n):
        for j in range(i + 1, base_n):
            if rng.random() < base_density:
                base_adj[i].append(j)
                base_adj[j].append(i)

    adj = [[] for _ in range(n)]
    for i in range(min(base_n, n)):
        for j in base_adj[i]:
            if j < n:
                adj[i].append(j)

    for i in range(base_n, min(2 * base_n, n)):
        orig = i - base_n
        for nb in base_adj[orig]:
            if nb < n:
                adj[i].append(nb)
                adj[nb].append(i)

    if 2 * base_n < n:
        hub = 2 * base_n
        for i in range(base_n, min(2 * base_n, n)):
            adj[hub].append(i)
            adj[i].append(hub)

    for i in range(2 * base_n + 1, n):
        target = rng.randint(0, i - 1)
        adj[i].append(target)
        adj[target].append(i)

    for i in range(n):
        adj[i] = sorted(list(set(adj[i])))
    return {"family": "mycielski", "num_vertices": n, "adj": adj}


def gen_small_world(n: int, k: int, p: float, rng: random.Random) -> Dict[str, Any]:
    adj = [set() for _ in range(n)]
    k = max(2, min(k, n - 1))
    for i in range(n):
        for j in range(1, k // 2 + 1):
            target = (i + j) % n
            adj[i].add(target)
            adj[target].add(i)

    for i in range(n):
        for j in range(1, k // 2 + 1):
            if rng.random() < p:
                target = (i + j) % n
                if target in adj[i]:
                    adj[i].remove(target)
                    adj[target].remove(i)
                    new_target = rng.randint(0, n - 1)
                    while new_target == i or new_target in adj[i]:
                        new_target = rng.randint(0, n - 1)
                    adj[i].add(new_target)
                    adj[new_target].add(i)

    return {"family": "small_world", "num_vertices": n, "adj": [sorted(list(nb)) for nb in adj]}


def gen_bipartite_bridges(n: int, internal_p: float, bridge_p: float, rng: random.Random) -> Dict[str, Any]:
    n1 = n // 2
    adj = [[] for _ in range(n)]
    for i in range(n1):
        for j in range(i + 1, n1):
            if rng.random() < internal_p:
                adj[i].append(j)
                adj[j].append(i)
    for i in range(n1, n):
        for j in range(i + 1, n):
            if rng.random() < internal_p:
                adj[i].append(j)
                adj[j].append(i)
    for i in range(n1):
        for j in range(n1, n):
            if rng.random() < bridge_p:
                adj[i].append(j)
                adj[j].append(i)
    return {"family": "bipartite_bridges", "num_vertices": n, "adj": adj}


def gen_regular(n: int, d: int, rng: random.Random) -> Dict[str, Any]:
    d = min(d, n - 1)
    if (n * d) % 2 != 0:
        d = d - 1 if d > 1 else d + 1
    base_adj = [set() for _ in range(n)]
    for i in range(n):
        for j in range(1, d // 2 + 1):
            target = (i + j) % n
            base_adj[i].add(target)
            base_adj[target].add(i)
    if d % 2 == 1:
        half = n // 2
        for i in range(half):
            target = (i + half) % n
            base_adj[i].add(target)
            base_adj[target].add(i)

    perm = list(range(n))
    rng.shuffle(perm)
    adj = [set() for _ in range(n)]
    for u in range(n):
        pu = perm[u]
        for v in base_adj[u]:
            pv = perm[v]
            adj[pu].add(pv)

    return {"family": "regular", "num_vertices": n, "adj": [sorted(list(nb)) for nb in adj]}


def gen_clustered_partition(n: int, num_clusters: int, in_p: float, out_p: float, rng: random.Random) -> Dict[str, Any]:
    cluster_size = n // num_clusters
    adj = [[] for _ in range(n)]
    clusters = []
    for c in range(num_clusters):
        start = c * cluster_size
        end = n if c == num_clusters - 1 else (c + 1) * cluster_size
        clusters.append(list(range(start, end)))

    for cluster in clusters:
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                if rng.random() < in_p:
                    u, v = cluster[i], cluster[j]
                    adj[u].append(v)
                    adj[v].append(u)

    for c1 in range(num_clusters):
        for c2 in range(c1 + 1, num_clusters):
            for u in clusters[c1]:
                for v in clusters[c2]:
                    if rng.random() < out_p:
                        adj[u].append(v)
                        adj[v].append(u)
    return {"family": "clustered_partition", "num_vertices": n, "adj": adj}


def get_graph_signature(g: Dict[str, Any]) -> Tuple[int, Tuple]:
    n = g["num_vertices"]
    edges = []
    for u in range(n):
        for v in g["adj"][u]:
            if u < v:
                edges.append((u, v))
    return (n, tuple(edges))


def build_graph_coloring_split(
    count_per_family: int,
    n_min: int,
    n_max: int,
    rng: random.Random,
    seen_signatures: Optional[Set[Tuple[int, Tuple]]] = None,
    prefix_id: str = "gc"
) -> List[Dict[str, Any]]:
    if seen_signatures is None:
        seen_signatures = set()

    graphs = []
    inst_id = 0
    families = [
        ("erdos_renyi", lambda: gen_erdos_renyi(rng.randint(n_min, n_max), rng.uniform(0.18, 0.42), rng)),
        ("geometric", lambda: gen_geometric(rng.randint(n_min, n_max), rng.uniform(0.20, 0.32), rng)),
        ("scale_free", lambda: gen_barabasi_albert(rng.randint(n_min, n_max), rng.randint(2, 4), rng)),
        ("mycielski", lambda: gen_mycielski_like(rng.randint(n_min, n_max), rng.uniform(0.20, 0.35), rng)),
        ("small_world", lambda: gen_small_world(rng.randint(n_min, n_max), rng.choice([4, 6, 8]), rng.uniform(0.15, 0.30), rng)),
        ("bipartite_bridges", lambda: gen_bipartite_bridges(rng.randint(n_min, n_max), rng.uniform(0.20, 0.40), rng.uniform(0.02, 0.05), rng)),
        ("regular", lambda: gen_regular(rng.randint(n_min, n_max), rng.choice([4, 6, 8]), rng)),
        ("clustered_partition", lambda: gen_clustered_partition(rng.randint(n_min, n_max), rng.choice([3, 4]), rng.uniform(0.35, 0.50), rng.uniform(0.02, 0.05), rng))
    ]

    for fam_name, fn in families:
        for _ in range(count_per_family):
            for _attempt in range(1000):
                g = fn()
                sig = get_graph_signature(g)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    break
            g["id"] = f"{prefix_id}_{inst_id:04d}"
            graphs.append(g)
            inst_id += 1

    return graphs


def generate_all_benchmarks(
    base_dir: str = "stage3/benchmarks",
    seed: int = 303
) -> Dict[str, Any]:
    rng = random.Random(seed)
    gc_dir = os.path.join(base_dir, "graph_coloring")
    os.makedirs(gc_dir, exist_ok=True)

    manifest: Dict[str, Any] = {
        "generator_seed": seed,
        "files": {}
    }

    seen_signatures: Set[Tuple[int, Tuple]] = set()

    # 1. Pilot split: 24 instances (3 per family, N in [40, 70])
    pilot = build_graph_coloring_split(3, 40, 70, rng, seen_signatures, prefix_id="pilot")
    # 2. Dev split: 40 instances (5 per family, N in [45, 75])
    dev = build_graph_coloring_split(5, 45, 75, rng, seen_signatures, prefix_id="dev")
    # 3. Hidden split: 200 instances (25 per family, N in [50, 95])
    hidden = build_graph_coloring_split(25, 50, 95, rng, seen_signatures, prefix_id="hidden")
    # 4. Sealed reserve split: 40 instances (5 per family, N in [50, 95])
    sealed = build_graph_coloring_split(5, 50, 95, rng, seen_signatures, prefix_id="sealed")

    # Dynamic verification of mathematical worst-case bound
    total_hidden_vertices = sum(len(g["adj"]) for g in hidden)
    s_penalty = total_hidden_vertices + 1
    assert s_penalty <= 19001, f"Penalty violation: total hidden vertices {total_hidden_vertices} + 1 > 19,001"
    manifest["total_hidden_vertices"] = total_hidden_vertices
    manifest["s_penalty_verified"] = s_penalty

    splits = {
        "graph_coloring_pilot": (os.path.join(gc_dir, "pilot.json"), pilot),
        "graph_coloring_dev": (os.path.join(gc_dir, "dev.json"), dev),
        "graph_coloring_hidden": (os.path.join(gc_dir, "hidden.json"), hidden),
        "graph_coloring_sealed": (os.path.join(gc_dir, "sealed.json"), sealed),
    }

    for key, (path, data) in splits.items():
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        manifest["files"][key] = {
            "path": path,
            "count": len(data),
            "sha256": sha256_file(path)
        }

    manifest_path = os.path.join(base_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    m = generate_all_benchmarks()
    print("Stage 3 Benchmarks Generated Successfully (Seed 303):")
    print(f"  Verified S_penalty: {m['s_penalty_verified']} (Total hidden vertices: {m['total_hidden_vertices']})")
    for k, v in m["files"].items():
        print(f"  {k:<25}: {v['count']:3d} instances | SHA-256: {v['sha256'][:16]}...")
