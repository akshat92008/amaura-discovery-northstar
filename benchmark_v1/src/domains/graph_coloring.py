"""
Graph Coloring Problem Domain for Search Strategy Benchmark V1
==============================================================
Vertex Graph Coloring with priority-driven sequential vertex selection.
Skeleton: Deterministic MEX Coloring Engine.
Primary Baseline: DSATUR (Brélaz 1979).
Secondary Baselines: Welsh-Powell (1967), Natural Greedy First-Fit.
"""

import json
import math
import os
import time
from typing import Dict, Any, List, Optional, Set, Tuple

from benchmark_v1.src.domains.base import ProblemDomain, DomainEvaluationResult
from stage3.src.sandbox import check_ast_security, sanitize_and_compile, sanitize_exception_name, SAFE_BUILTINS


class GraphColoringSimulator:
    """
    Deterministic greedy sequential coloring engine.
    Uses candidate priority function to select the next vertex to color.
    Guarantees that valid colorings are always produced for valid priority functions.
    """
    @staticmethod
    def color_graph(adj: List[List[int]], priority_fn) -> Tuple[int, List[int]]:
        n = len(adj)
        if n == 0:
            return 0, []

        adj_sets = [set(adj[u]) for u in range(n)]
        degrees = [len(adj_sets[u]) for u in range(n)]
        colors = [-1] * n
        sat_colors: List[Set[int]] = [set() for _ in range(n)]
        uncolored: Set[int] = set(range(n))

        while uncolored:
            best_u = -1
            best_p = -float("inf")

            for u in uncolored:
                sat = len(sat_colors[u])
                uncolored_deg = sum(1 for v in adj_sets[u] if colors[v] == -1)
                p = float(priority_fn(degrees[u], sat, uncolored_deg, u))
                if not math.isfinite(p):
                    raise ValueError(f"Non-finite priority returned for vertex {u}: {p}")

                if p > best_p:
                    best_p = p
                    best_u = u

            # Assign lowest available color not used by any neighbor
            c = 0
            while c in sat_colors[best_u]:
                c += 1

            colors[best_u] = c
            uncolored.remove(best_u)

            # Update neighbors' saturation sets
            for v in adj_sets[best_u]:
                if colors[v] == -1:
                    sat_colors[v].add(c)

        total_colors = len(set(colors))
        return total_colors, colors


class GraphColoringDomain(ProblemDomain):
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "graph_coloring")
        self.data_dir = data_dir
        self.simulator = GraphColoringSimulator()

        with open(os.path.join(self.data_dir, "train.json"), "r", encoding="utf-8") as f:
            self.train_graphs = json.load(f)
        with open(os.path.join(self.data_dir, "test.json"), "r", encoding="utf-8") as f:
            self.test_graphs = json.load(f)

        self._train_dsatur_ref = [self.simulator.color_graph(g["adj"], lambda d, s, ud, v: s * 10000.0 + ud)[0] for g in self.train_graphs]
        self._test_dsatur_ref = [self.simulator.color_graph(g["adj"], lambda d, s, ud, v: s * 10000.0 + ud)[0] for g in self.test_graphs]

        self._baselines = {
            "train": self._compute_baselines(self.train_graphs, self._train_dsatur_ref),
            "test": self._compute_baselines(self.test_graphs, self._test_dsatur_ref)
        }

    def _compute_baselines(self, dataset: List[Dict[str, Any]], ds_scores: List[int]) -> Dict[str, float]:
        def wp_p(deg, sat, udeg, vid):
            return deg * 1.0

        def greedy_p(deg, sat, udeg, vid):
            return -vid * 1.0

        wp_scores = [self.simulator.color_graph(g["adj"], wp_p)[0] for g in dataset]
        gr_scores = [self.simulator.color_graph(g["adj"], greedy_p)[0] for g in dataset]

        return {
            "dsatur": sum(ds_scores) / len(dataset),
            "welsh_powell": sum(wp_scores) / len(dataset),
            "greedy": sum(gr_scores) / len(dataset),
            "dsatur_total": sum(ds_scores),
            "welsh_powell_total": sum(wp_scores)
        }

    @property
    def name(self) -> str:
        return "graph_coloring"

    @property
    def function_name(self) -> str:
        return "vertex_priority"

    @property
    def function_signature(self) -> str:
        return (
            "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
            "    \"\"\"Assigns priority score to uncolored vertex. Vertex with highest priority is colored next.\"\"\""
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert graph theorist and combinatorial optimization algorithm designer.\n"
            "Your task is to design a vertex priority policy function in pure Python for Vertex Graph Coloring.\n\n"
            "Interface:\n"
            "```python\n"
            "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
            "```\n"
            "Arguments:\n"
            "- `degree: int`: total degree of the vertex in the graph\n"
            "- `saturation: int`: number of distinct colors assigned to already colored neighbors\n"
            "- `uncolored_degree: int`: number of uncolored neighbors remaining\n"
            "- `vertex_id: int`: unique 0-indexed vertex identifier\n\n"
            "Rules:\n"
            "1. Higher priority selects that vertex to be colored next.\n"
            "2. Objective is to minimize total unique colors (chromatic number).\n"
            "3. Allowed libraries: `math` only.\n"
            "4. Return ONLY valid Python inside a ```python ``` markdown block."
        )

    @property
    def canonical_seeds(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "dsatur",
                "code": (
                    "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
                    "    # DSATUR (Brélaz 1979): maximize saturation degree, tie-break by uncolored degree\n"
                    "    return float(saturation * 10000.0 + uncolored_degree)\n"
                ),
                "description": "Standard DSATUR heuristic prioritizing maximal saturation."
            },
            {
                "name": "welsh_powell",
                "code": (
                    "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
                    "    # Welsh-Powell (1967): largest total degree first\n"
                    "    return float(degree)\n"
                ),
                "description": "Largest degree first static heuristic."
            },
            {
                "name": "uncolored_degree_first",
                "code": (
                    "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
                    "    # Dynamic Largest Uncolored Degree First\n"
                    "    return float(uncolored_degree * 10.0 + saturation)\n"
                ),
                "description": "Prioritizes vertices with highest number of uncolored neighbors."
            },
            {
                "name": "natural_greedy",
                "code": (
                    "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
                    "    # Natural Order Greedy First-Fit\n"
                    "    return float(-vertex_id)\n"
                ),
                "description": "Natural index order."
            }
        ]

    def get_baseline_scores(self, split: str = "train") -> Dict[str, float]:
        return self._baselines.get(split, self._baselines["train"])

    def compute_relative_gap(self, raw_score: float, split: str = "train") -> float:
        ds_score = self.get_baseline_scores(split)["dsatur"]
        if ds_score <= 0.0:
            return 0.0
        # Relative gap vs DSATUR: (score - DSATUR) / DSATUR
        return round((raw_score - ds_score) / ds_score, 6)

    def evaluate(self, code: str, split: str = "train") -> DomainEvaluationResult:
        dataset = self.train_graphs if split == "train" else self.test_graphs
        t0 = time.perf_counter()

        # AST Safety Check
        is_safe, error_msg = check_ast_security(code, required_func="vertex_priority")
        if not is_safe:
            worst_penalty = sum(g.get("num_vertices", 50) for g in dataset)
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=worst_penalty,
                avg_score=worst_penalty / len(dataset),
                per_instance_scores=[worst_penalty / len(dataset)] * len(dataset),
                relative_gap=self.compute_relative_gap(worst_penalty / len(dataset), split),
                beats_baseline=False,
                error_message=error_msg,
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        # Compile and execute
        exec_globals = {"__builtins__": SAFE_BUILTINS, "math": __import__("math")}
        try:
            compiled = sanitize_and_compile(code, "<candidate_gc_priority>")
            exec(compiled, exec_globals)
            priority_fn = exec_globals["vertex_priority"]
        except Exception as e:
            worst_penalty = sum(g.get("num_vertices", 50) for g in dataset)
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=worst_penalty,
                avg_score=worst_penalty / len(dataset),
                per_instance_scores=[worst_penalty / len(dataset)] * len(dataset),
                relative_gap=self.compute_relative_gap(worst_penalty / len(dataset), split),
                beats_baseline=False,
                error_message=f"Compilation/Import Error: {sanitize_exception_name(e)}",
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        scores: List[float] = []
        worst_graph_idx = -1
        max_excess_vs_dsatur = -float("inf")

        dsatur_ref = self._train_dsatur_ref if split == "train" else self._test_dsatur_ref

        try:
            for idx, g in enumerate(dataset):
                k, _ = self.simulator.color_graph(g["adj"], priority_fn)
                scores.append(float(k))
                diff_vs_ds = k - dsatur_ref[idx]
                if diff_vs_ds > max_excess_vs_dsatur:
                    max_excess_vs_dsatur = diff_vs_ds
                    worst_graph_idx = idx
        except Exception as e:
            worst_penalty = sum(g.get("num_vertices", 50) for g in dataset)
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=worst_penalty,
                avg_score=worst_penalty / len(dataset),
                per_instance_scores=[worst_penalty / len(dataset)] * len(dataset),
                relative_gap=self.compute_relative_gap(worst_penalty / len(dataset), split),
                beats_baseline=False,
                error_message=f"Execution Error on graph #{len(scores)}: {sanitize_exception_name(e)}",
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        total_runtime_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        avg_score = sum(scores) / len(scores)
        total_score = sum(scores)
        rel_gap = self.compute_relative_gap(avg_score, split)
        ds_score = self.get_baseline_scores(split)["dsatur"]
        beats_baseline = bool(avg_score < ds_score - 1e-6)

        # Build diagnostics for Arm E
        diagnostics = {
            "avg_colors": round(avg_score, 4),
            "dsatur_avg": round(ds_score, 4),
            "per_instance_scores": scores,
            "worst_instance_idx": worst_graph_idx,
            "worst_instance_colors": scores[worst_graph_idx] if worst_graph_idx >= 0 else None,
            "worst_instance_dsatur": dsatur_ref[worst_graph_idx] if worst_graph_idx >= 0 else None,
            "diagnostic_summary": (
                f"Overall Average Colors: {avg_score:.2f} (DSATUR baseline: {ds_score:.2f}, Gap: {rel_gap * 100:+.2f}%).\n"
                f"Worst Graph #{worst_graph_idx}: Used {scores[worst_graph_idx]:.0f} colors vs DSATUR's {dsatur_ref[worst_graph_idx]} colors "
                f"(+{scores[worst_graph_idx] - dsatur_ref[worst_graph_idx]:.0f} excess colors).\n"
                f"Failure Analysis: Low saturation weighting causes heuristic to prioritize degree over saturation, "
                f"forcing unnecessary color splits.\n"
                f"Refinement Directive: Increase non-linear weight on `saturation` relative to `degree` and `uncolored_degree`."
            )
        }

        return DomainEvaluationResult(
            is_valid=True,
            raw_score=total_score,
            avg_score=round(avg_score, 4),
            per_instance_scores=scores,
            relative_gap=rel_gap,
            beats_baseline=beats_baseline,
            error_message=None,
            diagnostics=diagnostics,
            runtime_ms=total_runtime_ms
        )
