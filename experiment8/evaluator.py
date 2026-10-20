"""
Experiment #7: Full Graph-Coloring Solver Evaluator & Benchmark Suite
=====================================================================
Target Interface:
    def color_graph(adj: list[list[int]]) -> list[int]

Implements:
- Graph generators across 8 diverse graph families.
- Deterministic development benchmark (40 graphs) and hidden benchmark (160 graphs).
- 4 Classical Human Baselines: Natural Greedy, Welsh-Powell (1967), DSATUR (Brélaz 1979), RLF (Leighton 1979).
- Strict AST security sandbox (blocks I/O, subprocess, networking; permits pure math and random).
- Per-instance strict runtime budget (50 ms) and validity checking.
"""

import ast
import math
import random
import signal
import time
from typing import List, Tuple, Dict, Any, Optional, Set


def _alarm_timeout_handler(signum, frame):
    raise TimeoutError("Per-graph execution timed out (hard hang/infinite loop)")



def safe_import(name, *args, **kwargs):
    if name in {"math", "random"}:
        return __import__(name)
    raise ImportError(f"Import of '{name}' is forbidden. Only 'math' and 'random' are permitted.")


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
    "zip": zip,
    "reversed": reversed,
    "print": lambda *args, **kwargs: None,
    "__import__": safe_import,
}


def static_security_check(code: str) -> Tuple[bool, Optional[str]]:
    """
    Strict sandbox static analysis for complete solver synthesis:
    - DISALLOW unauthorized module imports (only pure 'math' and 'random' permitted)
    - DISALLOW dangerous builtins, file/network access, dynamic execution
    - VERIFY required function signature `def color_graph(adj)`
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    has_solver_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in {"math", "random"}:
                    return False, f"Security violation: Import '{alias.name}' is forbidden. Only 'math' and 'random' are permitted."
        if isinstance(node, ast.ImportFrom):
            if node.module not in {"math", "random"}:
                return False, f"Security violation: Import from '{node.module}' is forbidden. Only 'math' and 'random' are permitted."
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval", "exec", "open", "__import__", "globals", "locals", "getattr", "setattr"
            }:
                return False, f"Security violation: Forbidden call '{node.func.id}'."
        if isinstance(node, ast.FunctionDef) and node.name == "color_graph":
            has_solver_func = True
            if len(node.args.args) < 1:
                return False, "Signature error: 'color_graph' must accept at least (adj)."

    if not has_solver_func:
        return False, "Missing required function definition: 'def color_graph(adj: list[list[int]]) -> list[int]:'"

    return True, None


class Graph:
    """Undirected graph representation."""
    def __init__(self, num_vertices: int, edges: List[Tuple[int, int]], family: str = "unknown"):
        self.num_vertices = num_vertices
        self.adj: List[List[int]] = [[] for _ in range(num_vertices)]
        self.family = family
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
        self.num_edges = len(edge_set)
        max_edges = num_vertices * (num_vertices - 1) // 2
        self.density = self.num_edges / max_edges if max_edges > 0 else 0.0


# ---------------------------------------------------------------------------
# Graph Generators across 8 Families
# ---------------------------------------------------------------------------

def gen_erdos_renyi(n: int, p: float, rng: random.Random) -> Graph:
    edges = []
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                edges.append((u, v))
    return Graph(n, edges, family="erdos_renyi")


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
    return Graph(n, edges, family="geometric")


def gen_barabasi_albert(n: int, m: int, rng: random.Random) -> Graph:
    edges = []
    for i in range(m):
        for j in range(i + 1, m):
            edges.append((i, j))
    repeated_nodes = []
    for u, v in edges:
        repeated_nodes.extend([u, v])

    source = m
    while source < n:
        unique_targets = set()
        while len(unique_targets) < m:
            t = rng.choice(repeated_nodes)
            unique_targets.add(t)
        for t in unique_targets:
            edges.append((source, t))
            repeated_nodes.append(t)
        repeated_nodes.extend([source] * m)
        source += 1
    return Graph(n, edges, family="scale_free")


def gen_mycielski_like(n: int, p: float, rng: random.Random) -> Graph:
    base_n = max(5, n // 2)
    base_edges = []
    for u in range(base_n):
        for v in range(u + 1, base_n):
            if rng.random() < p:
                base_edges.append((u, v))
    edges = list(base_edges)
    edge_set = set(base_edges)
    for u in range(base_n):
        u_prime = base_n + u
        if u_prime < n:
            for v in range(base_n):
                if (min(u, v), max(u, v)) in edge_set:
                    edges.append((u_prime, v))
    apex = n - 1
    for u_prime in range(base_n, n - 1):
        edges.append((u_prime, apex))
    return Graph(n, edges, family="mycielski")


def gen_small_world(n: int, k: int, p_rewire: float, rng: random.Random) -> Graph:
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
    return Graph(n, list(rewired_edges), family="small_world")


def gen_bipartite_bridges(n: int, p_in: float, p_out: float, rng: random.Random) -> Graph:
    n1 = n // 2
    edges = []
    for u in range(n1):
        for v in range(n1, n):
            if rng.random() < p_in:
                edges.append((u, v))
    for u in range(n1):
        for v in range(u + 1, n1):
            if rng.random() < p_out:
                edges.append((u, v))
    for u in range(n1, n):
        for v in range(u + 1, n):
            if rng.random() < p_out:
                edges.append((u, v))
    return Graph(n, edges, family="bipartite_bridges")


def gen_regular(n: int, d: int, rng: random.Random) -> Graph:
    if (n * d) % 2 != 0:
        d = d - 1
    edges = set()
    for i in range(n):
        for j in range(1, d // 2 + 1):
            target = (i + j) % n
            edges.add((min(i, target), max(i, target)))
    return Graph(n, list(edges), family="regular")


def gen_clustered_partition(n: int, num_clusters: int, p_in: float, p_out: float, rng: random.Random) -> Graph:
    cluster_size = n // num_clusters
    edges = []
    for u in range(n):
        c_u = u // cluster_size
        for v in range(u + 1, n):
            c_v = v // cluster_size
            p = p_in if c_u == c_v else p_out
            if rng.random() < p:
                edges.append((u, v))
    return Graph(n, edges, family="clustered_partition")


# ---------------------------------------------------------------------------
# Benchmark Suite Manager
# ---------------------------------------------------------------------------

class SolverBenchmarkSuite:
    def __init__(self, dev_seed: int = 1042, hidden_seed: int = 70099):
        self.dev_seed = dev_seed
        self.hidden_seed = hidden_seed
        self.dev_dataset = self._create_dev_dataset(dev_seed)
        self.hidden_dataset = self._create_hidden_dataset(hidden_seed)

    def _create_dev_dataset(self, seed: int) -> List[Graph]:
        rng = random.Random(seed)
        graphs = []
        # 5 graphs for each of the 8 families = 40 graphs (N: 40-75)
        for _ in range(5):
            graphs.append(gen_erdos_renyi(rng.randint(40, 75), rng.uniform(0.15, 0.45), rng))
        for _ in range(5):
            graphs.append(gen_geometric(rng.randint(40, 75), rng.uniform(0.18, 0.32), rng))
        for _ in range(5):
            graphs.append(gen_barabasi_albert(rng.randint(40, 75), rng.randint(2, 4), rng))
        for _ in range(5):
            graphs.append(gen_mycielski_like(rng.randint(40, 70), rng.uniform(0.20, 0.35), rng))
        for _ in range(5):
            graphs.append(gen_small_world(rng.randint(50, 75), rng.choice([4, 6, 8]), rng.uniform(0.15, 0.35), rng))
        for _ in range(5):
            graphs.append(gen_bipartite_bridges(rng.randint(50, 75), rng.uniform(0.20, 0.40), rng.uniform(0.02, 0.06), rng))
        for _ in range(5):
            graphs.append(gen_regular(rng.randint(50, 75), rng.choice([4, 6, 8]), rng))
        for _ in range(5):
            graphs.append(gen_clustered_partition(rng.randint(50, 75), rng.choice([3, 4, 5]), rng.uniform(0.35, 0.55), rng.uniform(0.03, 0.07), rng))
        return graphs

    def _create_hidden_dataset(self, seed: int) -> Dict[str, List[Graph]]:
        rng = random.Random(seed)
        hidden = {}
        # 20 graphs per family = 160 graphs (N: 50-95)
        hidden["erdos_renyi"] = [gen_erdos_renyi(rng.randint(50, 95), rng.uniform(0.15, 0.45), rng) for _ in range(20)]
        hidden["geometric"] = [gen_geometric(rng.randint(50, 95), rng.uniform(0.18, 0.30), rng) for _ in range(20)]
        hidden["scale_free"] = [gen_barabasi_albert(rng.randint(50, 95), rng.randint(2, 5), rng) for _ in range(20)]
        hidden["mycielski"] = [gen_mycielski_like(rng.randint(45, 80), rng.uniform(0.20, 0.35), rng) for _ in range(20)]
        hidden["small_world"] = [gen_small_world(rng.randint(60, 95), rng.choice([4, 6, 8]), rng.uniform(0.15, 0.35), rng) for _ in range(20)]
        hidden["bipartite_bridges"] = [gen_bipartite_bridges(rng.randint(60, 95), rng.uniform(0.20, 0.40), rng.uniform(0.02, 0.06), rng) for _ in range(20)]
        hidden["regular"] = [gen_regular(rng.randint(60, 95), rng.choice([4, 6, 8]), rng) for _ in range(20)]
        hidden["clustered_partition"] = [gen_clustered_partition(rng.randint(60, 95), rng.choice([3, 4, 5]), rng.uniform(0.35, 0.55), rng.uniform(0.03, 0.07), rng) for _ in range(20)]
        return hidden


# ---------------------------------------------------------------------------
# Evaluator Engine
# ---------------------------------------------------------------------------

class SolverEvaluator:
    def __init__(self, per_instance_budget_ms: float = 50.0, per_instance_timeout_ms: float = 300.0):
        self.per_instance_budget_ms = per_instance_budget_ms
        self.per_instance_timeout_ms = per_instance_timeout_ms
        self.suite = SolverBenchmarkSuite()

    def validate_coloring(self, graph: Graph, colors: Any) -> Tuple[bool, Optional[str], int]:
        """
        Validates coloring output:
        - Must be list of ints of length n.
        - Adjacent vertices must have distinct colors.
        - Returns (is_valid, error_msg, num_colors).
        """
        n = graph.num_vertices
        if not isinstance(colors, (list, tuple)):
            return False, f"Output is type '{type(colors).__name__}', expected list[int].", 999999
        if len(colors) != n:
            return False, f"Output length {len(colors)} != number of vertices {n}.", 999999

        for u in range(n):
            c_u = colors[u]
            if not isinstance(c_u, (int, float)) or int(c_u) != c_u or c_u < 0:
                return False, f"Vertex {u} has invalid color value: {c_u}.", 999999
            for v in graph.adj[u]:
                if colors[v] == c_u and u != v:
                    return False, f"Conflict: adjacent vertices {u} and {v} share color {c_u}.", 999999

        unique_colors = len(set(colors))
        return True, None, unique_colors

    def evaluate_solver_code(
        self,
        code: str,
        dataset_type: str = "dev",
        hidden_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compiles and evaluates complete solver code against selected benchmark.
        """
        is_clean, err = static_security_check(code)
        if not is_clean:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Security / Static Check Failed: {err}"
            }

        local_scope = {}
        try:
            exec(code, {"__builtins__": SAFE_BUILTINS, "math": math, "random": random}, local_scope)
            func = local_scope["color_graph"]
        except Exception as e:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Compilation Error: {type(e).__name__}: {e}"
            }

        # Sanity check with small triangle graph
        prev_handler = signal.signal(signal.SIGALRM, _alarm_timeout_handler)
        try:
            sample_adj = [[1, 2], [0, 2], [0, 1]]
            signal.alarm(1)
            test_c = func([list(row) for row in sample_adj])
            signal.alarm(0)
            if not isinstance(test_c, (list, tuple)) or len(test_c) != 3 or test_c[0] == test_c[1] or test_c[0] == test_c[2] or test_c[1] == test_c[2]:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "scores": [],
                    "runtime_ms": 0.0,
                    "error": f"Sanity check failed on K3: output was {test_c}"
                }
        except TimeoutError:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 1000.0,
                "error": "Timeout Exceeded on K3 sanity check (infinite loop)"
            }
        except Exception as e:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Runtime Error on sanity check: {type(e).__name__}: {e}"
            }
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)

        if dataset_type == "dev":
            graphs = self.suite.dev_dataset
        elif dataset_type == "hidden":
            if hidden_category:
                graphs = self.suite.hidden_dataset.get(hidden_category, [])
            else:
                graphs = [g for cat in self.suite.hidden_dataset.values() for g in cat]
        else:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Invalid dataset_type: {dataset_type}"
            }

        total_colors = 0
        scores = []
        start_eval_time = time.perf_counter()

        prev_handler = signal.signal(signal.SIGALRM, _alarm_timeout_handler)
        try:
            for idx, g in enumerate(graphs):
                # Defensive copy of adj so solver cannot mutate benchmark graph
                adj_copy = [list(row) for row in g.adj]
                t0 = time.perf_counter()
                try:
                    signal.alarm(1)  # 1 second hard kill for infinite loops
                    colors = func(adj_copy)
                except TimeoutError:
                    return {
                        "is_valid": False,
                        "total_colors": 999999,
                        "avg_colors": 999999.0,
                        "scores": [],
                        "runtime_ms": 1000.0,
                        "error": f"Timeout Exceeded (Hard hang/infinite loop) on graph {idx} ({g.family}, N={g.num_vertices})"
                    }
                except Exception as e:
                    return {
                        "is_valid": False,
                        "total_colors": 999999,
                        "avg_colors": 999999.0,
                        "scores": [],
                        "runtime_ms": 0.0,
                        "error": f"Solver exception on graph {idx} ({g.family}, N={g.num_vertices}): {type(e).__name__}: {e}"
                    }
                finally:
                    signal.alarm(0)
                inst_time_ms = (time.perf_counter() - t0) * 1000.0

                if inst_time_ms > self.per_instance_timeout_ms:
                    return {
                        "is_valid": False,
                        "total_colors": 999999,
                        "avg_colors": 999999.0,
                        "scores": [],
                        "runtime_ms": round(inst_time_ms, 2),
                        "error": f"Timeout Exceeded: instance took {inst_time_ms:.1f}ms > limit {self.per_instance_timeout_ms}ms on {g.family}"
                    }

                is_valid, err, k = self.validate_coloring(g, colors)
                if not is_valid:
                    return {
                        "is_valid": False,
                        "total_colors": 999999,
                        "avg_colors": 999999.0,
                        "scores": [],
                        "runtime_ms": 0.0,
                        "error": f"Invalid coloring on graph {idx} ({g.family}): {err}"
                    }

                total_colors += k
                scores.append(k)

            total_runtime_ms = (time.perf_counter() - start_eval_time) * 1000.0
            avg_colors = total_colors / len(graphs) if graphs else 0.0

            return {
                "is_valid": True,
                "total_colors": total_colors,
                "avg_colors": round(avg_colors, 3),
                "scores": scores,
                "runtime_ms": round(total_runtime_ms, 2),
                "avg_runtime_per_graph_ms": round(total_runtime_ms / len(graphs), 3),
                "error": None
            }
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)




# ---------------------------------------------------------------------------
# Classical Human Baseline Implementations
# ---------------------------------------------------------------------------

NATURAL_GREEDY_CODE = '''def color_graph(adj: list[list[int]]) -> list[int]:
    """Natural Greedy: colors vertices in index order using First-Fit."""
    n = len(adj)
    colors = [-1] * n
    for v in range(n):
        used = {colors[u] for u in adj[v] if colors[u] >= 0}
        c = 0
        while c in used:
            c += 1
        colors[v] = c
    return colors
'''

WELSH_POWELL_CODE = '''def color_graph(adj: list[list[int]]) -> list[int]:
    """Welsh-Powell (Largest First, 1967): order by descending degree, then First-Fit."""
    n = len(adj)
    degrees = [len(adj[v]) for v in range(n)]
    order = sorted(range(n), key=lambda v: degrees[v], reverse=True)
    colors = [-1] * n
    for v in order:
        used = {colors[u] for u in adj[v] if colors[u] >= 0}
        c = 0
        while c in used:
            c += 1
        colors[v] = c
    return colors
'''

DSATUR_CODE = '''def color_graph(adj: list[list[int]]) -> list[int]:
    """
    DSATUR Algorithm (Brélaz, 1979):
    At each step, select uncolored vertex with maximum saturation degree.
    Ties broken by maximum degree in uncolored subgraph.
    Assign smallest feasible color (First-Fit).
    """
    n = len(adj)
    colors = [-1] * n
    saturation = [0] * n
    neighbor_colors = [set() for _ in range(n)]
    uncolored = set(range(n))

    while uncolored:
        best_v = None
        best_key = (-1, -1)
        for v in uncolored:
            sat = saturation[v]
            uncolored_deg = len(set(adj[v]) & uncolored)
            key = (sat, uncolored_deg)
            if key > best_key:
                best_key = key
                best_v = v

        used = neighbor_colors[best_v]
        c = 0
        while c in used:
            c += 1
        colors[best_v] = c
        uncolored.remove(best_v)

        for u in adj[best_v]:
            if c not in neighbor_colors[u]:
                neighbor_colors[u].add(c)
                saturation[u] += 1

    return colors
'''

RLF_CODE = '''def color_graph(adj: list[list[int]]) -> list[int]:
    """
    Recursive Largest First (RLF, Leighton 1979):
    Extracts maximal independent sets (color classes) iteratively.
    For each color class:
      1. Choose vertex with max degree in remaining uncolored subgraph.
      2. Greedily add vertices that share maximum neighbors with already-incompatible uncolored vertices.
    """
    n = len(adj)
    colors = [-1] * n
    uncolored = set(range(n))
    c = 0

    while uncolored:
        # Pick vertex with max degree in uncolored subgraph
        best_v = max(uncolored, key=lambda v: len(set(adj[v]) & uncolored))
        C = [best_v]
        U1 = set(adj[best_v]) & uncolored
        U2 = uncolored - {best_v} - U1

        while U2:
            # Pick u in U2 maximizing edges to U1
            best_u = max(U2, key=lambda u: (len(set(adj[u]) & U1), -len(set(adj[u]) & U2)))
            C.append(best_u)
            U2.remove(best_u)
            new_u1 = set(adj[best_u]) & U2
            U1.update(new_u1)
            U2 -= new_u1

        for v in C:
            colors[v] = c
            uncolored.remove(v)
        c += 1

    return colors
'''
