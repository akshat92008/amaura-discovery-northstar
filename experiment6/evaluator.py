"""
Experiment #6: Graph Coloring Evaluator & Deterministic Benchmark Suite
========================================================================
Implements:
- Graph representation (adjacency list)
- Generator for diverse graph families (Erdős-Rényi, Geometric, Scale-Free, Mycielskian, Small-World, Bipartite, Regular)
- Deterministic simulation loop for sequential vertex coloring
- Sandboxed evaluation with static AST security analysis
- Dual hidden suites (Hidden-1 & Hidden-2)
- Human baselines: DSATUR (Brélaz, 1979), Welsh-Powell (1967), and Natural Greedy
"""

import ast
import math
import random
import time
from typing import List, Tuple, Dict, Any, Optional, Set


def safe_import(name, *args, **kwargs):
    if name == "math":
        return math
    raise ImportError(f"Import of '{name}' is forbidden. Only 'math' is permitted.")


SAFE_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "float": float,
    "int": int,
    "round": round,
    "bool": bool,
    "len": len,
    "range": range,
    "sum": sum,
    "pow": pow,
    "list": list,
    "tuple": tuple,
    "set": set,
    "dict": dict,
    "enumerate": enumerate,
    "sorted": sorted,
    "any": any,
    "all": all,
    "print": lambda *args, **kwargs: None,
    "__import__": safe_import,
}


def static_security_check(code: str) -> Tuple[bool, Optional[str]]:
    """
    Strict sandbox static analysis:
    - DISALLOW unauthorized module imports (only pure 'math' permitted)
    - DISALLOW dangerous builtins, file/network access, dynamic execution
    - VERIFY required function signature
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    has_choose_vertex_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "math":
                    return False, f"Security violation: Import '{alias.name}' is forbidden. Only 'math' is permitted."
        if isinstance(node, ast.ImportFrom):
            if node.module != "math":
                return False, f"Security violation: Import from '{node.module}' is forbidden. Only 'math' is permitted."
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval", "exec", "open", "__import__", "globals", "locals", "getattr", "setattr"
            }:
                return False, f"Security violation: Forbidden call '{node.func.id}'."
        if isinstance(node, ast.FunctionDef) and node.name == "choose_vertex":
            has_choose_vertex_func = True
            if len(node.args.args) < 5:
                return False, "Signature error: 'choose_vertex' must accept (uncolored, adj, colors, saturation, degrees)."

    if not has_choose_vertex_func:
        return False, "Missing required function definition: 'def choose_vertex(uncolored, adj, colors, saturation, degrees) -> int:'"

    return True, None


class Graph:
    """Simple undirected graph representation."""
    def __init__(self, num_vertices: int, edges: List[Tuple[int, int]]):
        self.num_vertices = num_vertices
        self.adj: List[List[int]] = [[] for _ in range(num_vertices)]
        edge_set: Set[Tuple[int, int]] = set()
        for u, v in edges:
            if u != v:
                p = (min(u, v), max(u, v))
                if p not in edge_set:
                    edge_set.add(p)
                    self.adj[u].append(v)
                    self.adj[v].append(u)
        for u in range(num_vertices):
            self.adj[u].sort()
        self.degrees: List[int] = [len(self.adj[u]) for u in range(num_vertices)]


# ---------------------------------------------------------------------------
# Graph Generators
# ---------------------------------------------------------------------------

def gen_erdos_renyi(n: int, p: float, rng: random.Random) -> Graph:
    edges = []
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                edges.append((u, v))
    return Graph(n, edges)


def gen_geometric(n: int, r: float, rng: random.Random) -> Graph:
    coords = [(rng.random(), rng.random()) for _ in range(n)]
    edges = []
    r_sq = r * r
    for u in range(n):
        for v in range(u + 1, n):
            dx = coords[u][0] - coords[v][0]
            dy = coords[u][1] - coords[v][1]
            if dx * dx + dy * dy <= r_sq:
                edges.append((u, v))
    return Graph(n, edges)


def gen_barabasi_albert(n: int, m: int, rng: random.Random) -> Graph:
    edges = []
    targets = list(range(m))
    repeated_nodes = []
    for i in range(m):
        for j in range(i + 1, m):
            edges.append((i, j))
            repeated_nodes.extend([i, j])

    source = m
    while source < n:
        unique_targets = set()
        while len(unique_targets) < m:
            t = rng.choice(repeated_nodes)
            unique_targets.add(t)
        for t in unique_targets:
            edges.append((source, t))
        repeated_nodes.extend(unique_targets)
        repeated_nodes.extend([source] * m)
        source += 1
    return Graph(n, edges)


def gen_mycielski_like(n: int, p: float, rng: random.Random) -> Graph:
    """Generates graphs with high chromatic number relative to local clique size."""
    # Base graph
    base_n = max(5, n // 2)
    base_edges = []
    for u in range(base_n):
        for v in range(u + 1, base_n):
            if rng.random() < p:
                base_edges.append((u, v))
    # Mycielski expansion
    edges = list(base_edges)
    for u in range(base_n):
        u_prime = base_n + u
        if u_prime < n:
            for v in range(base_n):
                if (min(u, v), max(u, v)) in [(min(a, b), max(a, b)) for a, b in base_edges]:
                    edges.append((u_prime, v))
    # Apex node
    apex = n - 1
    for u_prime in range(base_n, n - 1):
        edges.append((u_prime, apex))
    return Graph(n, edges)


def gen_small_world(n: int, k: int, p_rewire: float, rng: random.Random) -> Graph:
    """Watts-Strogatz small-world graph."""
    edges = set()
    for i in range(n):
        for j in range(1, k // 2 + 1):
            target = (i + j) % n
            edges.add((min(i, target), max(i, target)))

    rewired_edges = set()
    for u, v in edges:
        if rng.random() < p_rewire:
            new_v = rng.randrange(n)
            while new_v == u or (min(u, new_v), max(u, new_v)) in rewired_edges:
                new_v = rng.randrange(n)
            rewired_edges.add((min(u, new_v), max(u, new_v)))
        else:
            rewired_edges.add((u, v))
    return Graph(n, list(rewired_edges))


def gen_bipartite_bridges(n: int, p_in: float, p_out: float, rng: random.Random) -> Graph:
    """Two dense bipartite clusters connected with sparse cross-edges."""
    n1 = n // 2
    edges = []
    # Cross edges within bipartite partition
    for u in range(n1):
        for v in range(n1, n):
            if rng.random() < p_in:
                edges.append((u, v))
    # Random intra-cluster noise (violating strict 2-colorability)
    for u in range(n1):
        for v in range(u + 1, n1):
            if rng.random() < p_out:
                edges.append((u, v))
    for u in range(n1, n):
        for v in range(u + 1, n):
            if rng.random() < p_out:
                edges.append((u, v))
    return Graph(n, edges)


def gen_regular(n: int, d: int, rng: random.Random) -> Graph:
    """Approximate d-regular graph."""
    if (n * d) % 2 != 0:
        d = d - 1
    # Simple configuration model
    edges = set()
    for i in range(n):
        for j in range(1, d // 2 + 1):
            target = (i + j) % n
            edges.add((min(i, target), max(i, target)))
    return Graph(n, list(edges))


def gen_clustered_partition(n: int, num_clusters: int, p_in: float, p_out: float, rng: random.Random) -> Graph:
    """Partition with dense clusters and inter-cluster links."""
    cluster_size = n // num_clusters
    edges = []
    for u in range(n):
        c_u = u // cluster_size
        for v in range(u + 1, n):
            c_v = v // cluster_size
            p = p_in if c_u == c_v else p_out
            if rng.random() < p:
                edges.append((u, v))
    return Graph(n, edges)


# ---------------------------------------------------------------------------
# Benchmark Suite
# ---------------------------------------------------------------------------

class GraphColoringBenchmark:
    def __init__(self):
        self.dev_dataset = self._create_dev_dataset(seed=42)
        self.hidden1_dataset = self._create_hidden1_dataset(seed=9999)
        self.hidden2_dataset = self._create_hidden2_dataset(seed=77777)

    def _create_dev_dataset(self, seed: int) -> List[Graph]:
        rng = random.Random(seed)
        graphs = []
        # 10 Erdos-Renyi
        for _ in range(10):
            n = rng.randint(40, 70)
            p = rng.uniform(0.15, 0.40)
            graphs.append(gen_erdos_renyi(n, p, rng))
        # 8 Geometric
        for _ in range(8):
            n = rng.randint(40, 70)
            r = rng.uniform(0.22, 0.32)
            graphs.append(gen_geometric(n, r, rng))
        # 7 Scale-Free
        for _ in range(7):
            n = rng.randint(40, 70)
            m = rng.randint(2, 4)
            graphs.append(gen_barabasi_albert(n, m, rng))
        return graphs

    def _create_hidden1_dataset(self, seed: int) -> Dict[str, List[Graph]]:
        rng = random.Random(seed)
        hidden = {}

        # 1. Erdos-Renyi (30 graphs)
        er = []
        for _ in range(30):
            n = rng.randint(50, 90)
            p = rng.uniform(0.15, 0.45)
            er.append(gen_erdos_renyi(n, p, rng))
        hidden["erdos_renyi"] = er

        # 2. Geometric (30 graphs)
        geom = []
        for _ in range(30):
            n = rng.randint(50, 90)
            r = rng.uniform(0.20, 0.30)
            geom.append(gen_geometric(n, r, rng))
        hidden["geometric"] = geom

        # 3. Barabasi-Albert Scale-Free (30 graphs)
        ba = []
        for _ in range(30):
            n = rng.randint(50, 90)
            m = rng.randint(2, 5)
            ba.append(gen_barabasi_albert(n, m, rng))
        hidden["scale_free"] = ba

        # 4. Mycielski-like Triangle-Free (30 graphs)
        myc = []
        for _ in range(30):
            n = rng.randint(45, 80)
            p = rng.uniform(0.20, 0.35)
            myc.append(gen_mycielski_like(n, p, rng))
        hidden["mycielski"] = myc

        return hidden

    def _create_hidden2_dataset(self, seed: int) -> Dict[str, List[Graph]]:
        rng = random.Random(seed)
        hidden2 = {}

        # 1. Watts-Strogatz Small World (30 graphs, N=60..100)
        sw = []
        for _ in range(30):
            n = rng.randint(60, 100)
            k = rng.choice([4, 6, 8])
            p_rewire = rng.uniform(0.15, 0.35)
            sw.append(gen_small_world(n, k, p_rewire, rng))
        hidden2["small_world"] = sw

        # 2. Bipartite with Bridges (30 graphs)
        bip = []
        for _ in range(30):
            n = rng.randint(60, 100)
            p_in = rng.uniform(0.20, 0.40)
            p_out = rng.uniform(0.02, 0.08)
            bip.append(gen_bipartite_bridges(n, p_in, p_out, rng))
        hidden2["bipartite_bridges"] = bip

        # 3. Regular Graphs (30 graphs)
        reg = []
        for _ in range(30):
            n = rng.randint(60, 100)
            d = rng.choice([4, 6, 8])
            reg.append(gen_regular(n, d, rng))
        hidden2["regular"] = reg

        # 4. Clustered Partition (30 graphs)
        cp = []
        for _ in range(30):
            n = rng.randint(60, 100)
            num_c = rng.choice([3, 4, 5])
            p_in = rng.uniform(0.35, 0.60)
            p_out = rng.uniform(0.03, 0.08)
            cp.append(gen_clustered_partition(n, num_c, p_in, p_out, rng))
        hidden2["clustered_partition"] = cp

        return hidden2

    def simulate(self, func: Any, graph: Graph) -> int:
        """
        Simulate sequential first-fit coloring guided by candidate `choose_vertex`.
        Returns total number of colors used (lower is better).
        """
        n = graph.num_vertices
        adj = graph.adj
        degrees = graph.degrees

        uncolored = list(range(n))
        colors = [-1] * n
        saturation = [0] * n
        neighbor_colors = [set() for _ in range(n)]

        while uncolored:
            # Candidate chooses vertex
            v_chosen_raw = func(list(uncolored), adj, list(colors), list(saturation), degrees)
            try:
                v = int(v_chosen_raw)
            except Exception:
                raise TypeError(f"choose_vertex returned non-integer: {v_chosen_raw}")

            if v not in uncolored:
                raise ValueError(f"Chosen vertex {v} is not in uncolored set: {uncolored[:5]}...")

            # First-fit color assignment: find minimum available color
            used = neighbor_colors[v]
            c = 0
            while c in used:
                c += 1

            colors[v] = c
            uncolored.remove(v)

            # Update neighbors' saturation
            for u in adj[v]:
                if c not in neighbor_colors[u]:
                    neighbor_colors[u].add(c)
                    saturation[u] += 1

        total_colors = max(colors) + 1
        return total_colors

    def evaluate_code(
        self,
        code: str,
        dataset_type: str = "dev",
        suite: str = "hidden1",
        hidden_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate candidate `choose_vertex` function.
        """
        # Static security check
        is_clean, err = static_security_check(code)
        if not is_clean:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "excess_pct": float("inf"),
                "runtime_ms": 0.0,
                "error": err
            }

        # Compilation
        local_scope = {}
        try:
            exec(code, {"__builtins__": SAFE_BUILTINS, "math": math}, local_scope)
            func = local_scope["choose_vertex"]
        except Exception as e:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "excess_pct": float("inf"),
                "runtime_ms": 0.0,
                "error": f"Compilation Error: {e}"
            }

        # Sanity check with small triangle graph
        try:
            sample_adj = [[1, 2], [0, 2], [0, 1]]
            test_v = int(func([0, 1, 2], sample_adj, [-1, -1, -1], [0, 0, 0], [2, 2, 2]))
            if test_v not in {0, 1, 2}:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "excess_pct": float("inf"),
                    "runtime_ms": 0.0,
                    "error": f"Sanity check returned invalid vertex index: {test_v}"
                }
        except Exception as e:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "excess_pct": float("inf"),
                "runtime_ms": 0.0,
                "error": f"Runtime Error on test call: {type(e).__name__}: {e}"
            }

        # Select dataset
        if dataset_type == "dev":
            instances = self.dev_dataset
        elif dataset_type == "hidden":
            dataset_source = self.hidden1_dataset if suite == "hidden1" else self.hidden2_dataset
            if hidden_category:
                instances = dataset_source.get(hidden_category, [])
            else:
                instances = [g for cat in dataset_source.values() for g in cat]
        else:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "excess_pct": float("inf"),
                "runtime_ms": 0.0,
                "error": f"Invalid dataset_type: {dataset_type}"
            }

        start_t = time.perf_counter()
        total_colors = 0

        for g in instances:
            try:
                k = self.simulate(func, g)
                total_colors += k
            except Exception as e:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "excess_pct": float("inf"),
                    "runtime_ms": 0.0,
                    "error": f"Simulation Error: {type(e).__name__}: {e}"
                }

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        avg_colors = total_colors / len(instances)

        return {
            "is_valid": True,
            "total_colors": total_colors,
            "avg_colors": round(avg_colors, 2),
            "excess_pct": 0.0,  # Computed relative to DSATUR baseline externally
            "runtime_ms": round(elapsed_ms, 2),
            "error": None
        }


# ---------------------------------------------------------------------------
# Human Baseline Algorithms
# ---------------------------------------------------------------------------

DSATUR_CODE = '''def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """
    DSATUR Algorithm (Brélaz, 1979):
    Select vertex with maximum saturation degree.
    Ties broken by maximum degree in uncolored subgraph.
    """
    best_v = uncolored[0]
    best_sat = -1
    best_uncolored_deg = -1

    for v in uncolored:
        sat = saturation[v]
        if sat > best_sat:
            best_sat = sat
            uncolored_deg = sum(1 for u in adj[v] if colors[u] == -1)
            best_uncolored_deg = uncolored_deg
            best_v = v
        elif sat == best_sat:
            uncolored_deg = sum(1 for u in adj[v] if colors[u] == -1)
            if uncolored_deg > best_uncolored_deg:
                best_uncolored_deg = uncolored_deg
                best_v = v

    return best_v
'''

WELSH_POWELL_CODE = '''def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """
    Welsh-Powell Algorithm (Largest First, 1967):
    Select uncolored vertex with highest original degree.
    """
    best_v = uncolored[0]
    best_deg = -1
    for v in uncolored:
        if degrees[v] > best_deg:
            best_deg = degrees[v]
            best_v = v
    return best_v
'''

NATURAL_GREEDY_CODE = '''def choose_vertex(uncolored: list[int], adj: list[list[int]], colors: list[int], saturation: list[int], degrees: list[int]) -> int:
    """Simple Natural Greedy: pick the first uncolored vertex."""
    return uncolored[0]
'''
