"""
Stage 2: Deterministic Benchmark Generator
==========================================
Generates 4 strictly separated splits for both core problems:
1. Graph Coloring (8 structural families)
2. PFSP (6 structural families)

Splits:
- pilot.json: Calibration, difficulty testing, pool spread, variance estimation
- dev.json: Used for Arm C and Arm D selection
- hidden.json: ~200 instances for final evaluation
- sealed.json: Sealed reserve partition (untouched during primary experiment)
"""

import hashlib
import json
import math
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
    # Creates triangle-free / high-chromatic structure
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
    n2 = n - n1
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

    # Permute vertex labels randomly to ensure distinct graph structures across runs
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
    seen_signatures: Optional[Set[Tuple[int, Tuple]]] = None
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
            # Ensure strictly unique graph instance across all splits
            for _attempt in range(500):
                g = fn()
                sig = get_graph_signature(g)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    break
            g["id"] = f"gc_{inst_id:04d}"
            graphs.append(g)
            inst_id += 1

    return graphs


# =========================================================================
# PFSP GENERATORS
# =========================================================================

def build_pfsp_split(count_per_family: int, rng: random.Random) -> List[Dict[str, Any]]:
    instances = []
    inst_id = 0
    families = [
        "taillard_uniform",
        "mach_corr",
        "job_corr",
        "bimodal",
        "high_ratio",
        "u_load"
    ]

    size_pairs = [
        (20, 5), (20, 10), (30, 5), (30, 10), (50, 5), (50, 10),
        (50, 15), (75, 10), (75, 15), (100, 10), (100, 15), (120, 10)
    ]

    for fam in families:
        for _ in range(count_per_family):
            n, m = rng.choice(size_pairs)
            times = []

            if fam == "taillard_uniform":
                times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]
            elif fam == "mach_corr":
                center_m = m // 2
                for _ in range(n):
                    row = [rng.randint(60, 150) if k == center_m or abs(k - center_m) <= 1 else rng.randint(5, 40) for k in range(m)]
                    times.append(row)
            elif fam == "job_corr":
                for _ in range(n):
                    job_base = rng.choice([10, 25, 50, 80, 120])
                    row = [max(1, int(rng.gauss(job_base, job_base * 0.2))) for _ in range(m)]
                    times.append(row)
            elif fam == "bimodal":
                for _ in range(n):
                    row = [rng.randint(5, 15) if rng.random() < 0.5 else rng.randint(85, 100) for _ in range(m)]
                    times.append(row)
            elif fam == "high_ratio":
                n_hi = max(80, n)
                m_lo = min(5, m)
                times = [[rng.randint(1, 99) for _ in range(m_lo)] for _ in range(n_hi)]
                n, m = n_hi, m_lo
            elif fam == "u_load":
                for _ in range(n):
                    row = [rng.randint(70, 140) if (k == 0 or k == m - 1) else rng.randint(5, 30) for k in range(m)]
                    times.append(row)
            else:
                times = [[rng.randint(1, 99) for _ in range(m)] for _ in range(n)]

            instances.append({
                "id": f"pfsp_{inst_id:04d}",
                "family": fam,
                "n": n,
                "m": m,
                "times": times
            })
            inst_id += 1

    return instances


# =========================================================================
# MASTER GENERATOR & MANIFEST
# =========================================================================

def generate_all_benchmarks(base_dir: str = "stage2/benchmarks", seed: int = 42) -> Dict[str, Any]:
    rng = random.Random(seed)
    os.makedirs(f"{base_dir}/graph_coloring", exist_ok=True)
    os.makedirs(f"{base_dir}/pfsp", exist_ok=True)

    manifest: Dict[str, Any] = {
        "generator_seed": seed,
        "files": {}
    }

    # 1. Graph Coloring Splits (strictly disjoint signatures across all 4 partitions)
    seen_gc_signatures: Set[Tuple[int, Tuple]] = set()
    gc_pilot = build_graph_coloring_split(3, 40, 70, rng, seen_gc_signatures)
    gc_dev = build_graph_coloring_split(5, 45, 75, rng, seen_gc_signatures)
    gc_hidden = build_graph_coloring_split(25, 50, 95, rng, seen_gc_signatures)
    gc_sealed = build_graph_coloring_split(5, 50, 95, rng, seen_gc_signatures)

    gc_files = {
        "graph_coloring_pilot": (f"{base_dir}/graph_coloring/pilot.json", gc_pilot),
        "graph_coloring_dev": (f"{base_dir}/graph_coloring/dev.json", gc_dev),
        "graph_coloring_hidden": (f"{base_dir}/graph_coloring/hidden.json", gc_hidden),
        "graph_coloring_sealed": (f"{base_dir}/graph_coloring/sealed.json", gc_sealed),
    }

    for key, (path, data) in gc_files.items():
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        manifest["files"][key] = {
            "path": path,
            "count": len(data),
            "sha256": sha256_file(path)
        }

    # 2. PFSP Splits
    # Pilot: 24 instances (4 per fam)
    # Dev: 36 instances (6 per fam)
    # Hidden: 204 instances (34 per fam)
    # Sealed: 36 instances (6 per fam)
    pfsp_pilot = build_pfsp_split(4, rng)
    pfsp_dev = build_pfsp_split(6, rng)
    pfsp_hidden = build_pfsp_split(34, rng)
    pfsp_sealed = build_pfsp_split(6, rng)

    pfsp_files = {
        "pfsp_pilot": (f"{base_dir}/pfsp/pilot.json", pfsp_pilot),
        "pfsp_dev": (f"{base_dir}/pfsp/dev.json", pfsp_dev),
        "pfsp_hidden": (f"{base_dir}/pfsp/hidden.json", pfsp_hidden),
        "pfsp_sealed": (f"{base_dir}/pfsp/sealed.json", pfsp_sealed),
    }

    for key, (path, data) in pfsp_files.items():
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        manifest["files"][key] = {
            "path": path,
            "count": len(data),
            "sha256": sha256_file(path)
        }

    manifest_path = f"{base_dir}/manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    m = generate_all_benchmarks()
    print("Stage 2 Benchmarks Generated Successfully:")
    for k, v in m["files"].items():
        print(f"  {k:<25}: {v['count']:3d} instances | SHA-256: {v['sha256'][:16]}...")
