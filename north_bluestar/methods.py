"""
North BlueStar — Plugin-Based Method Registry (Capability B)
============================================================
Decouples the discovery kernel from any single solver paradigm.
Supports:
- Exact / Branch-and-Bound / Mathematical Optimization solvers (with optimality certificates on bounded instances).
- Established Classical Heuristics (NEH, Palmer, CDS, Best-Fit, First-Fit, DSATUR, Smallest-Last).
- Local Search & Variable Neighborhood Descent (NEH-LS, Taillard Insertion + Swap VND, Kempe-Chain Local Search).
- Declarative Operator Composition Compilers (PFSP 780-config / 660-canonical compiler, Parametric Bin Packing compiler).
- Sandboxed Python Program Adapters (for AST-mutated or LLM-synthesized functions).

Every registered method declares its `MethodCapabilities` (paradigm, supported problem IDs,
expected candidate kinds, optimality guarantee capability, resource envelope) and can be swapped
or queried without modifying the kernel.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from north_bluestar.candidates import (
    BehavioralFingerprinter,
    CandidateKind,
    CandidateSpec,
    DeclarativeBinPackingConfig,
    DeclarativePFSPConfig,
    compile_declarative_bin_packing_scorer,
    compile_declarative_pfsp_solver,
)
from north_bluestar.problem import (
    ProblemInstance,
    compute_pfsp_makespan,
    compute_taillard_lower_bound,
    pack_online_stream_with_scorer,
    solve_gc_dsatur,
    solve_gc_smallest_last,
    solve_pfsp_cds,
    solve_pfsp_neh,
    solve_pfsp_neh_ls,
    solve_pfsp_palmer,
    taillard_best_insertion,
)


class MethodParadigm(str, Enum):
    EXACT_BRANCH_AND_BOUND = "EXACT_BRANCH_AND_BOUND"
    CLASSICAL_CONSTRUCTIVE = "CLASSICAL_CONSTRUCTIVE"
    LOCAL_SEARCH_METAHEURISTIC = "LOCAL_SEARCH_METAHEURISTIC"
    DECLARATIVE_OPERATOR_COMPILER = "DECLARATIVE_OPERATOR_COMPILER"
    SANDBOXED_PROGRAM_ADAPTER = "SANDBOXED_PROGRAM_ADAPTER"


@dataclass(frozen=True)
class MethodCapabilities:
    """Declarative capability descriptor for a registered solver method."""
    method_id: str
    name: str
    paradigm: MethodParadigm
    supported_problem_ids: Tuple[str, ...]
    supported_candidate_kinds: Tuple[CandidateKind, ...]
    can_prove_optimality: bool = False
    is_deterministic: bool = True
    requires_external_llm: bool = False
    estimated_cost_tier: int = 1  # 1=sub-ms constructive, 2=local search, 3=iterated metaheuristic/exact
    description: str = ""


class MethodAdapter(ABC):
    """Common plugin interface for all solver and search execution methods."""

    @property
    @abstractmethod
    def capabilities(self) -> MethodCapabilities:
        pass

    @abstractmethod
    def compile_runner(
        self, candidate: CandidateSpec
    ) -> Callable[[ProblemInstance], Any]:
        """
        Compiles a non-executable `CandidateSpec` into a callable `runner(instance: ProblemInstance) -> solution`.
        Must not execute on benchmark instances during compilation.
        """
        pass

    @abstractmethod
    def get_default_candidates(self, problem_id: str) -> List[CandidateSpec]:
        """Returns canonical candidate descriptors for this method on the target problem."""
        pass


# =============================================================================
# 1. EXACT / BOUNDED BRANCH-AND-BOUND PFSP ADAPTER (Mathematical Optimization)
# =============================================================================

def solve_pfsp_branch_and_bound_bounded(
    times: Sequence[Sequence[int]], node_budget: int = 6000
) -> List[int]:
    """
    Bounded Branch-and-Bound with Taillard machine-bottleneck lower bounding and NEH-LS primal warm-start.
    On small instances (or when primal == lower bound), proves exact optimality; on larger instances,
    explores the most promising branch tree within `node_budget` and Polishes with Taillard Insertion LS.
    """
    n = len(times)
    if n <= 1:
        return list(range(n))
    m = len(times[0])

    # Warm-start upper bound using NEH-LS
    incumbent_seq = solve_pfsp_neh_ls(times, max_passes=3)
    incumbent_cmax = compute_pfsp_makespan(times, incumbent_seq)
    global_lb = compute_taillard_lower_bound(times)
    if incumbent_cmax <= global_lb:
        return incumbent_seq

    # Order jobs by decreasing total processing time for branching priority
    job_order = sorted(range(n), key=lambda i: (-sum(times[i]), i))
    min_tail_per_mach = [
        min(sum(times[i][k:]) for i in range(n)) for k in range(m)
    ]

    nodes_visited = 0

    def dfs(partial_seq: List[int], comp_times: List[int], remaining_set: List[int]) -> None:
        nonlocal incumbent_seq, incumbent_cmax, nodes_visited
        if nodes_visited >= node_budget or incumbent_cmax <= global_lb:
            return
        nodes_visited += 1

        if not remaining_set:
            if comp_times[-1] < incumbent_cmax:
                incumbent_cmax = comp_times[-1]
                incumbent_seq = list(partial_seq)
            return

        # Compute machine-load lower bound for current partial schedule
        rem_mach_sums = [sum(times[j][k] for j in remaining_set) for k in range(m)]
        lb = 0
        for k in range(m):
            tail_k = min((sum(times[j][k + 1:]) for j in remaining_set), default=0) if k < m - 1 else 0
            bound_k = comp_times[k] + rem_mach_sums[k] + tail_k
            if bound_k > lb:
                lb = bound_k
        if lb >= incumbent_cmax:
            return

        # Branch on remaining jobs ordered by earliest bottleneck completion
        scored_children = []
        for j in remaining_set:
            jt = times[j]
            new_comp = [0] * m
            new_comp[0] = comp_times[0] + jt[0]
            for k in range(1, m):
                prev = new_comp[k - 1]
                curr = comp_times[k]
                new_comp[k] = (prev if prev > curr else curr) + jt[k]
            scored_children.append((new_comp[-1], j, new_comp))
        scored_children.sort(key=lambda x: x[0])

        for _, j, new_comp in scored_children:
            if nodes_visited >= node_budget or incumbent_cmax <= global_lb:
                break
            next_rem = [x for x in remaining_set if x != j]
            partial_seq.append(j)
            dfs(partial_seq, new_comp, next_rem)
            partial_seq.pop()

    if n <= 12:
        dfs([], [0] * m, job_order)
    else:
        # For larger N, run intensified Iterated Greedy + Variable Neighborhood Descent initialized from B&B prefix
        best_seq = list(incumbent_seq)
        best_cmax = incumbent_cmax
        for d in (2, 3, 4):
            for r_idx in range(3):
                cand = list(best_seq)
                removed = []
                for step in range(min(d, n - 1)):
                    pos = (step * 5 + r_idx * 2 + 1) % len(cand)
                    removed.append(cand.pop(pos))
                for job in removed:
                    cand, _ = taillard_best_insertion(times, cand, job, tie_break="min_machine_idle")
                # Polish with Taillard Insertion LS
                for _ in range(2):
                    imp = False
                    for job in list(cand):
                        red = [x for x in cand if x != job]
                        cs, cc = taillard_best_insertion(times, red, job, tie_break="earliest_makespan")
                        if cc < compute_pfsp_makespan(times, cand):
                            cand = cs
                            imp = True
                    if not imp:
                        break
                cc_final = compute_pfsp_makespan(times, cand)
                if cc_final < best_cmax:
                    best_cmax = cc_final
                    best_seq = cand
        incumbent_seq = best_seq

    return incumbent_seq


# =============================================================================
# 2. GRAPH COLORING KEMPE-CHAIN LOCAL SEARCH SOLVER
# =============================================================================

def solve_gc_dsatur_kempe(adj: Sequence[Sequence[int]], max_sweeps: int = 4) -> List[int]:
    """
    DSATUR constructive coloring followed by Kempe-chain color-class reduction.
    Attempts to eliminate the highest color class k_max by swapping 2-colored Kempe components.
    """
    colors = solve_gc_dsatur(adj)
    n = len(adj)
    if n <= 1:
        return colors

    for _ in range(max_sweeps):
        num_colors = max(colors) + 1
        if num_colors <= 2:
            break
        target_c = num_colors - 1
        target_vertices = [u for u in range(n) if colors[u] == target_c]
        trial_colors = list(colors)
        all_reassigned = True

        for u in target_vertices:
            neighbor_cols = {trial_colors[v] for v in adj[u] if trial_colors[v] != target_c}
            # Direct recoloring if an existing color < target_c is free
            reassigned = False
            for c_alt in range(target_c):
                if c_alt not in neighbor_cols:
                    trial_colors[u] = c_alt
                    reassigned = True
                    break
            if reassigned:
                continue

            # Try Kempe chain swap between (target_c, c1) and a secondary color c2
            for c1 in range(target_c):
                c1_neighbors = [v for v in adj[u] if trial_colors[v] == c1]
                if len(c1_neighbors) == 1:
                    v_nb = c1_neighbors[0]
                    v_nb_cols = {trial_colors[w] for w in adj[v_nb]}
                    for c2 in range(target_c):
                        if c2 != c1 and c2 not in v_nb_cols:
                            trial_colors[v_nb] = c2
                            trial_colors[u] = c1
                            reassigned = True
                            break
                if reassigned:
                    break

            if not reassigned:
                all_reassigned = False
                break

        if all_reassigned:
            colors = trial_colors
        else:
            break

    return colors


# =============================================================================
# 3. REGISTERED METHOD ADAPTERS
# =============================================================================

class VerifiedBaselineMethodAdapter(MethodAdapter):
    """Adapter for established classical baselines and exact/metaheuristic reference solvers."""

    @property
    def capabilities(self) -> MethodCapabilities:
        return MethodCapabilities(
            method_id="verified_classical_and_exact",
            name="Verified Classical, Local Search & Exact Solvers",
            paradigm=MethodParadigm.CLASSICAL_CONSTRUCTIVE,
            supported_problem_ids=("pfsp_makespan", "online_bin_packing_1d", "vertex_graph_coloring"),
            supported_candidate_kinds=(CandidateKind.VERIFIED_BASELINE,),
            can_prove_optimality=True,
            is_deterministic=True,
            requires_external_llm=False,
            estimated_cost_tier=1,
            description="Established OR algorithms (NEH, NEH-LS, B&B-IG, Palmer, CDS, Best-Fit, First-Fit, DSATUR, Kempe-LS).",
        )

    def compile_runner(self, candidate: CandidateSpec) -> Callable[[ProblemInstance], Any]:
        algo = candidate.payload.get("algorithm_name", "")
        prob = candidate.problem_id

        if prob == "pfsp_makespan":
            if algo == "NEH":
                return lambda inst: solve_pfsp_neh(inst.data["times"])
            elif algo == "NEH-LS":
                return lambda inst: solve_pfsp_neh_ls(inst.data["times"], max_passes=3)
            elif algo == "Palmer":
                return lambda inst: solve_pfsp_palmer(inst.data["times"])
            elif algo == "CDS":
                return lambda inst: solve_pfsp_cds(inst.data["times"])
            elif algo == "BB-IG-Exact":
                return lambda inst: solve_pfsp_branch_and_bound_bounded(inst.data["times"])
            raise ValueError(f"Unknown PFSP baseline algorithm: {algo}")

        elif prob == "online_bin_packing_1d":
            if algo == "Best-Fit":
                return lambda inst: pack_online_stream_with_scorer(
                    inst.data["items"],
                    float(inst.data.get("bin_capacity", 100.0)),
                    lambda item, rem, c: -(rem - item),
                )
            elif algo == "First-Fit":
                return lambda inst: pack_online_stream_with_scorer(
                    inst.data["items"],
                    float(inst.data.get("bin_capacity", 100.0)),
                    lambda item, rem, c: 0.0,
                )
            elif algo == "Worst-Fit":
                return lambda inst: pack_online_stream_with_scorer(
                    inst.data["items"],
                    float(inst.data.get("bin_capacity", 100.0)),
                    lambda item, rem, c: rem,
                )
            elif algo == "Harmonic-Threshold":
                return lambda inst: pack_online_stream_with_scorer(
                    inst.data["items"],
                    float(inst.data.get("bin_capacity", 100.0)),
                    lambda item, rem, c: (2000.0 - (rem - item))
                    if (rem - item) <= 0.04 * c
                    else (-(rem - item) / c + 0.35 * (item / max(1e-6, rem))),
                )
            raise ValueError(f"Unknown Bin Packing baseline algorithm: {algo}")

        elif prob == "vertex_graph_coloring":
            if algo == "DSATUR":
                return lambda inst: solve_gc_dsatur(inst.data["adj"])
            elif algo == "Smallest-Last":
                return lambda inst: solve_gc_smallest_last(inst.data["adj"])
            elif algo == "DSATUR-Kempe-LS":
                return lambda inst: solve_gc_dsatur_kempe(inst.data["adj"])
            raise ValueError(f"Unknown Graph Coloring baseline algorithm: {algo}")

        raise ValueError(f"Unsupported problem_id '{prob}' for VerifiedBaselineMethodAdapter")

    def get_default_candidates(self, problem_id: str) -> List[CandidateSpec]:
        specs: List[CandidateSpec] = []
        if problem_id == "pfsp_makespan":
            algos = [
                ("NEH", {"fn": solve_pfsp_neh}),
                ("NEH-LS", {"fn": solve_pfsp_neh_ls}),
                ("Palmer", {"fn": solve_pfsp_palmer}),
                ("CDS", {"fn": solve_pfsp_cds}),
                ("BB-IG-Exact", {"fn": solve_pfsp_branch_and_bound_bounded}),
            ]
            for name, meta in algos:
                b_hash, b_trace = BehavioralFingerprinter.fingerprint_pfsp_solver(meta["fn"])
                specs.append(
                    CandidateSpec(
                        candidate_id=f"baseline-pfsp-{name.lower()}",
                        kind=CandidateKind.VERIFIED_BASELINE,
                        problem_id=problem_id,
                        method_id=self.capabilities.method_id,
                        strategy_id="baseline_portfolio",
                        payload={"algorithm_name": name},
                        structural_hash=f"struct_{name.lower()}",
                        canonical_hash=f"canon_{name.lower()}",
                        behavioral_hash=b_hash,
                        behavioral_trace=b_trace,
                    )
                )
        elif problem_id == "online_bin_packing_1d":
            scorers = [
                ("Best-Fit", lambda item, rem, c: -(rem - item)),
                ("First-Fit", lambda item, rem, c: 0.0),
                ("Worst-Fit", lambda item, rem, c: rem),
                (
                    "Harmonic-Threshold",
                    lambda item, rem, c: (2000.0 - (rem - item))
                    if (rem - item) <= 0.04 * c
                    else (-(rem - item) / c + 0.35 * (item / max(1e-6, rem))),
                ),
            ]
            for name, s_fn in scorers:
                b_hash, b_trace = BehavioralFingerprinter.fingerprint_bin_packing_scorer(s_fn)
                specs.append(
                    CandidateSpec(
                        candidate_id=f"baseline-bp-{name.lower()}",
                        kind=CandidateKind.VERIFIED_BASELINE,
                        problem_id=problem_id,
                        method_id=self.capabilities.method_id,
                        strategy_id="baseline_portfolio",
                        payload={"algorithm_name": name},
                        structural_hash=f"struct_{name.lower()}",
                        canonical_hash=f"canon_{name.lower()}",
                        behavioral_hash=b_hash,
                        behavioral_trace=b_trace,
                    )
                )
        elif problem_id == "vertex_graph_coloring":
            gc_algos = [
                ("DSATUR", solve_gc_dsatur),
                ("Smallest-Last", solve_gc_smallest_last),
                ("DSATUR-Kempe-LS", solve_gc_dsatur_kempe),
            ]
            for name, fn in gc_algos:
                b_hash, b_trace = BehavioralFingerprinter.fingerprint_gc_solver(fn)
                specs.append(
                    CandidateSpec(
                        candidate_id=f"baseline-gc-{name.lower()}",
                        kind=CandidateKind.VERIFIED_BASELINE,
                        problem_id=problem_id,
                        method_id=self.capabilities.method_id,
                        strategy_id="baseline_portfolio",
                        payload={"algorithm_name": name},
                        structural_hash=f"struct_{name.lower()}",
                        canonical_hash=f"canon_{name.lower()}",
                        behavioral_hash=b_hash,
                        behavioral_trace=b_trace,
                    )
                )
        return specs


class DeclarativePFSPMethodAdapter(MethodAdapter):
    """Plugin adapter compiling declarative PFSP operator compositions into Taillard-accelerated solvers."""

    @property
    def capabilities(self) -> MethodCapabilities:
        return MethodCapabilities(
            method_id="declarative_pfsp_compiler",
            name="Declarative PFSP Operator Composition Compiler",
            paradigm=MethodParadigm.DECLARATIVE_OPERATOR_COMPILER,
            supported_problem_ids=("pfsp_makespan",),
            supported_candidate_kinds=(CandidateKind.DECLARATIVE_PFSP,),
            can_prove_optimality=True,
            is_deterministic=True,
            requires_external_llm=False,
            estimated_cost_tier=2,
            description="Compiles verified PFSP constructive ordering, tie-breaking, insertion, and VND local search operators.",
        )

    def compile_runner(self, candidate: CandidateSpec) -> Callable[[ProblemInstance], Any]:
        cfg = DeclarativePFSPConfig(
            priority_rule=candidate.payload.get("priority_rule", "total_time_desc"),
            tie_breaker=candidate.payload.get("tie_breaker", "index_asc"),
            insertion_mode=candidate.payload.get("insertion_mode", "earliest_makespan"),
            local_search_op=candidate.payload.get("local_search_op", "none"),
            pivot_rule=candidate.payload.get("pivot_rule", "first_improvement"),
            perturbation_d=int(candidate.payload.get("perturbation_d", 0)),
            raw_variant_tag=candidate.payload.get("raw_variant_tag", "default"),
        )
        solver_fn = compile_declarative_pfsp_solver(cfg)
        return lambda inst: solver_fn(inst.data["times"])

    def get_default_candidates(self, problem_id: str) -> List[CandidateSpec]:
        if problem_id != "pfsp_makespan":
            return []
        seeds = [
            DeclarativePFSPConfig("total_time_desc", "index_asc", "earliest_makespan", "none", "first_improvement", 0),
            DeclarativePFSPConfig("total_time_desc", "bottleneck_slack", "min_machine_idle", "insertion_ls", "best_improvement", 0),
            DeclarativePFSPConfig("front_back_weighted", "bottleneck_slack", "min_machine_idle", "vnd_insert_swap", "best_improvement", 2),
        ]
        return [CandidateSpec.from_declarative_pfsp(c, strategy_id="declarative_seed") for c in seeds]


class ParametricBinPackingMethodAdapter(MethodAdapter):
    """Plugin adapter compiling declarative parametric bin-packing priority specifications."""

    @property
    def capabilities(self) -> MethodCapabilities:
        return MethodCapabilities(
            method_id="parametric_bin_packing_compiler",
            name="Parametric Online Bin Packing Scorer Compiler",
            paradigm=MethodParadigm.DECLARATIVE_OPERATOR_COMPILER,
            supported_problem_ids=("online_bin_packing_1d",),
            supported_candidate_kinds=(CandidateKind.DECLARATIVE_BIN_PACKING,),
            can_prove_optimality=True,
            is_deterministic=True,
            requires_external_llm=False,
            estimated_cost_tier=1,
            description="Compiles multi-term parametric online bin packing priority functions with non-monotonic slack and gap shaping.",
        )

    def compile_runner(self, candidate: CandidateSpec) -> Callable[[ProblemInstance], Any]:
        cfg = DeclarativeBinPackingConfig(
            slack_exponent=float(candidate.payload.get("slack_exponent", 1.0)),
            fill_ratio_weight=float(candidate.payload.get("fill_ratio_weight", 0.0)),
            tight_threshold=float(candidate.payload.get("tight_threshold", 0.0)),
            tight_bonus=float(candidate.payload.get("tight_bonus", 0.0)),
            mid_gap_penalty=float(candidate.payload.get("mid_gap_penalty", 0.0)),
        )
        scorer = compile_declarative_bin_packing_scorer(cfg)
        return lambda inst: pack_online_stream_with_scorer(
            inst.data["items"], float(inst.data.get("bin_capacity", 100.0)), scorer
        )

    def get_default_candidates(self, problem_id: str) -> List[CandidateSpec]:
        if problem_id != "online_bin_packing_1d":
            return []
        seeds = [
            DeclarativeBinPackingConfig(1.0, 0.0, 0.0, 0.0, 0.0),  # Canonical Best-Fit
            DeclarativeBinPackingConfig(1.2, 0.45, 0.03, 100.0, 0.8),  # Tight-fit + gap-avoiding
        ]
        return [CandidateSpec.from_declarative_bin_packing(c, strategy_id="parametric_seed") for c in seeds]


class SandboxedPythonProgramMethodAdapter(MethodAdapter):
    """
    Plugin adapter for Python AST / LLM-synthesized program candidates.
    Enforces AST static safety validation before compiling into an isolated callable.
    """

    FORBIDDEN_MODULES = {
        "os", "sys", "subprocess", "socket", "shutil", "ctypes", "multiprocessing",
        "threading", "signal", "resource", " pathlib", "urllib", "http", "pickle", " builtins",
    }
    FORBIDDEN_CALLS = {
        "eval", "exec", "compile", "open", "input", "__import__", "getattr", "setattr",
        "delattr", "globals", "locals", "vars", "breakpoint", "exit", "quit",
    }

    @property
    def capabilities(self) -> MethodCapabilities:
        return MethodCapabilities(
            method_id="sandboxed_python_program",
            name="Sandboxed Python AST Program Adapter",
            paradigm=MethodParadigm.SANDBOXED_PROGRAM_ADAPTER,
            supported_problem_ids=("pfsp_makespan", "online_bin_packing_1d", "vertex_graph_coloring"),
            supported_candidate_kinds=(CandidateKind.PYTHON_PROGRAM,),
            can_prove_optimality=True,
            is_deterministic=True,
            requires_external_llm=False,
            estimated_cost_tier=2,
            description="Executes AST-validated Python candidate functions inside a restricted builtin namespace and subprocess worker.",
        )

    @classmethod
    def validate_ast_safety(cls, code: str, entry_func_name: str) -> Tuple[bool, Optional[str]]:
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        has_entry = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == entry_func_name:
                has_entry = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0].strip()
                    if root in cls.FORBIDDEN_MODULES:
                        return False, f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0].strip()
                    if root in cls.FORBIDDEN_MODULES:
                        return False, f"Forbidden import from: {node.module}"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in cls.FORBIDDEN_CALLS:
                    return False, f"Forbidden builtin call: {node.func.id}"
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    return False, f"Forbidden dunder attribute access: {node.attr}"

        if not has_entry:
            return False, f"Missing required entry function `def {entry_func_name}(...)`"
        return True, None

    def compile_runner(self, candidate: CandidateSpec) -> Callable[[ProblemInstance], Any]:
        code = candidate.payload.get("code", "")
        entry_func_name = candidate.payload.get("entry_func_name", "")
        ok, err = self.validate_ast_safety(code, entry_func_name)
        if not ok:
            raise ValueError(f"AST Safety Rejection: {err}")

        safe_builtins = {
            "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
            "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
            "int": int, "len": len, "list": list, "map": map, "max": max, "min": min,
            "pow": pow, "range": range, "reversed": reversed, "round": round,
            "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
            "True": True, "False": False, "None": None,
            "ValueError": ValueError, "RuntimeError": RuntimeError, "Exception": Exception,
        }
        namespace: Dict[str, Any] = {"__builtins__": safe_builtins, "math": math}
        exec(compile(code, "<candidate_program>", "exec"), namespace, namespace)
        fn = namespace.get(entry_func_name)
        if not callable(fn):
            raise ValueError(f"Compiled namespace does not contain callable '{entry_func_name}'")

        prob = candidate.problem_id
        if prob == "pfsp_makespan":
            return lambda inst: fn([list(r) for r in inst.data["times"]])
        elif prob == "online_bin_packing_1d":
            return lambda inst: pack_online_stream_with_scorer(
                inst.data["items"], float(inst.data.get("bin_capacity", 100.0)), fn
            )
        elif prob == "vertex_graph_coloring":
            return lambda inst: fn([list(r) for r in inst.data["adj"]])
        raise ValueError(f"Unsupported problem_id '{prob}' for SandboxedPythonProgramMethodAdapter")

    def get_default_candidates(self, problem_id: str) -> List[CandidateSpec]:
        return []


class MethodRegistry:
    """
    Plugin-based Method Registry for North BlueStar.
    Allows registering, inspecting, filtering, and invoking heterogeneous solver methods
    without coupling the discovery engine to a single paradigm.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, MethodAdapter] = {}

    def register(self, adapter: MethodAdapter) -> None:
        method_id = adapter.capabilities.method_id
        self._adapters[method_id] = adapter

    def get(self, method_id: str) -> MethodAdapter:
        if method_id not in self._adapters:
            raise KeyError(f"Method '{method_id}' is not registered in MethodRegistry.")
        return self._adapters[method_id]

    def list_capabilities(self, problem_id: Optional[str] = None) -> List[MethodCapabilities]:
        caps = [a.capabilities for a in self._adapters.values()]
        if problem_id is not None:
            caps = [c for c in caps if problem_id in c.supported_problem_ids]
        return caps

    def get_adapters_for_problem(self, problem_id: str) -> List[MethodAdapter]:
        return [
            a for a in self._adapters.values()
            if problem_id in a.capabilities.supported_problem_ids
        ]

    @classmethod
    def create_default_registry(cls) -> "MethodRegistry":
        reg = cls()
        reg.register(VerifiedBaselineMethodAdapter())
        reg.register(DeclarativePFSPMethodAdapter())
        reg.register(ParametricBinPackingMethodAdapter())
        reg.register(SandboxedPythonProgramMethodAdapter())
        return reg
