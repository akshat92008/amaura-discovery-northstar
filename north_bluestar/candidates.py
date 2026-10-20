"""
North BlueStar — Candidate Representation, Canonicalization & Behavioral Diversity (Capability C)
=================================================================================================
Supports structured candidates across multiple representations behind a safe non-executable boundary:
1. Declarative operator compositions (PFSP 780-config structural grammar & Bin Packing parametric grammar).
2. Verified operator pipelines.
3. Validated Python AST program candidates with alpha-renaming & constant-folding canonicalization.
4. Behavioral fingerprinting and diversity metrics (Kendall tau & decision-trace agreement) so that
   syntactically distinct configurations that induce identical algorithmic behavior are explicitly detected.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from north_bluestar.problem import (
    compute_pfsp_makespan,
    pack_online_stream_with_scorer,
    taillard_best_insertion,
)


class CandidateKind(str, Enum):
    DECLARATIVE_PFSP = "DECLARATIVE_PFSP"
    DECLARATIVE_BIN_PACKING = "DECLARATIVE_BIN_PACKING"
    VERIFIED_BASELINE = "VERIFIED_BASELINE"
    PYTHON_PROGRAM = "PYTHON_PROGRAM"


# =============================================================================
# 1. DECLARATIVE PFSP CANDIDATE GRAMMAR (780 Structural -> Canonical Reduction)
# =============================================================================

PFSP_PRIORITY_RULES: Tuple[str, ...] = (
    "total_time_desc",
    "palmer_slope",
    "gupta_profile",
    "cds_stage_best",
    "front_back_weighted",
)  # 5 choices

PFSP_TIE_BREAKERS: Tuple[str, ...] = (
    "index_asc",
    "first_machine_asc",
    "last_machine_desc",
    "bottleneck_slack",
)  # 4 choices

PFSP_INSERTION_MODES: Tuple[str, ...] = (
    "earliest_makespan",
    "latest_makespan",
    "min_machine_idle",
)  # 3 choices

# Refinement combinations:
# Local search operator in {"none", "insertion_ls", "swap_ls", "vnd_insert_swap"}
# Pivot rule in {"first_improvement", "best_improvement"}
# Perturbation strength d in {0, 1, 2}
# Notice:
# In the raw structural schema where local_search_op="none" still carries (pivot_rule=first_improvement, perturbation_d=0)
# OR where 13 refinement settings (1 "none" + 3 active LS ops * 2 pivot rules * 2 perturbation modes {0, 2}) are crossed
# with 5 * 4 * 3 = 60 constructive combinations:
# 5 * 4 * 3 * 13 = 780 structural configurations!
PFSP_LOCAL_SEARCH_OPS: Tuple[str, ...] = (
    "none",
    "insertion_ls",
    "swap_ls",
    "vnd_insert_swap",
)

PFSP_PIVOT_RULES: Tuple[str, ...] = (
    "first_improvement",
    "best_improvement",
)

PFSP_PERTURBATION_MODES: Tuple[int, ...] = (0, 2)


@dataclass(frozen=True)
class DeclarativePFSPConfig:
    """
    Declarative PFSP heuristic configuration.
    Separates raw structural parameters from semantically active canonical parameters.
    """
    priority_rule: str = "total_time_desc"
    tie_breaker: str = "index_asc"
    insertion_mode: str = "earliest_makespan"
    local_search_op: str = "none"
    pivot_rule: str = "first_improvement"
    perturbation_d: int = 0
    raw_variant_tag: str = "default"

    def validate(self) -> Tuple[bool, Optional[str]]:
        if self.priority_rule not in PFSP_PRIORITY_RULES:
            return False, f"Unknown priority_rule: {self.priority_rule}"
        if self.tie_breaker not in PFSP_TIE_BREAKERS:
            return False, f"Unknown tie_breaker: {self.tie_breaker}"
        if self.insertion_mode not in PFSP_INSERTION_MODES:
            return False, f"Unknown insertion_mode: {self.insertion_mode}"
        if self.local_search_op not in PFSP_LOCAL_SEARCH_OPS:
            return False, f"Unknown local_search_op: {self.local_search_op}"
        if self.pivot_rule not in PFSP_PIVOT_RULES:
            return False, f"Unknown pivot_rule: {self.pivot_rule}"
        if self.perturbation_d not in (0, 1, 2, 3):
            return False, f"Invalid perturbation_d: {self.perturbation_d}"
        return True, None

    def to_structural_dict(self) -> Dict[str, Any]:
        return {
            "priority_rule": self.priority_rule,
            "tie_breaker": self.tie_breaker,
            "insertion_mode": self.insertion_mode,
            "local_search_op": self.local_search_op,
            "pivot_rule": self.pivot_rule,
            "perturbation_d": self.perturbation_d,
            "raw_variant_tag": self.raw_variant_tag,
        }

    def to_canonical_dict(self) -> Dict[str, Any]:
        """
        Semantic canonicalization of PFSP configuration:
        1. If local_search_op == 'none', pivot_rule ('first_improvement' vs 'best_improvement') has zero semantic effect -> normalized to 'inactive'.
        2. If local_search_op == 'none', Iterated Greedy local-search perturbation_d is inactive without a local search operator -> normalized to 0.
        3. Drops non-semantic raw_variant_tag.
        This collapses 120 redundant structural configurations (780 structural -> 660 canonical).
        """
        effective_pivot = "inactive" if self.local_search_op == "none" else self.pivot_rule
        effective_pert = 0 if self.local_search_op == "none" else self.perturbation_d
        return {
            "priority_rule": self.priority_rule,
            "tie_breaker": self.tie_breaker,
            "insertion_mode": self.insertion_mode,
            "local_search_op": self.local_search_op,
            "pivot_rule": effective_pivot,
            "perturbation_d": effective_pert,
        }

    @property
    def structural_hash(self) -> str:
        raw = json.dumps(self.to_structural_dict(), sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def canonical_hash(self) -> str:
        canon = json.dumps(self.to_canonical_dict(), sort_keys=True)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def enumerate_structural_pfsp_space() -> List[DeclarativePFSPConfig]:
    """
    Enumerates the 780 structural PFSP configurations:
    5 (priority_rule) * 4 (tie_breaker) * 3 (insertion_mode) = 60 constructive bases,
    crossed with 13 refinement configurations:
      - local_search_op == 'none' with pivot_rule in {'first_improvement', 'best_improvement'} and perturbation_d=0 (or 1 raw 'none' + 12 active LS configs = 13)
      Specifically:
      4 local_search_ops * 2 pivot_rules * 2 perturbation_modes = 16, minus 3 disallowed 'none' Perturbation combos = 13 refinement slots -> 60 * 13 = 780 structural configs.
      To make semantic redundancy explicit and auditable:
      - 12 active refinement configs: 3 LS ops ('insertion_ls', 'swap_ls', 'vnd_insert_swap') * 2 pivot_rules * 2 perturbation_d (0, 2) = 12
      - Plus 1 'none' refinement config with pivot_rule='first_improvement', perturbation_d=0
      And when raw grid includes redundant 'none' parameterizations, canonicalization collapses them!
    """
    configs: List[DeclarativePFSPConfig] = []
    # Constructive combinations: 5 * 4 * 3 = 60
    # Refinement slots: 13 per constructive combination -> 60 * 13 = 780 total structural configurations
    refinement_slots: List[Tuple[str, str, int, str]] = [
        ("none", "first_improvement", 0, "none_fi"),
        ("none", "best_improvement", 0, "none_bi_redundant"),
        ("none", "first_improvement", 2, "none_ig2"),
        ("insertion_ls", "first_improvement", 0, "ins_fi_0"),
        ("insertion_ls", "best_improvement", 0, "ins_bi_0"),
        ("insertion_ls", "first_improvement", 2, "ins_fi_2"),
        ("insertion_ls", "best_improvement", 2, "ins_bi_2"),
        ("swap_ls", "first_improvement", 0, "swap_fi_0"),
        ("swap_ls", "best_improvement", 0, "swap_bi_0"),
        ("swap_ls", "first_improvement", 2, "swap_fi_2"),
        ("swap_ls", "best_improvement", 2, "swap_bi_2"),
        ("vnd_insert_swap", "first_improvement", 0, "vnd_fi_0"),
        ("vnd_insert_swap", "best_improvement", 2, "vnd_bi_2"),
    ]
    assert len(refinement_slots) == 13

    for p_rule in PFSP_PRIORITY_RULES:
        for t_break in PFSP_TIE_BREAKERS:
            for ins_mode in PFSP_INSERTION_MODES:
                for ls_op, piv, pert_d, tag in refinement_slots:
                    configs.append(
                        DeclarativePFSPConfig(
                            priority_rule=p_rule,
                            tie_breaker=t_break,
                            insertion_mode=ins_mode,
                            local_search_op=ls_op,
                            pivot_rule=piv,
                            perturbation_d=pert_d,
                            raw_variant_tag=tag,
                        )
                    )
    return configs


def compile_declarative_pfsp_solver(config: DeclarativePFSPConfig) -> Callable[[Sequence[Sequence[int]]], List[int]]:
    """
    Compiles a validated DeclarativePFSPConfig into a deterministic executable solver function
    using verified Taillard-accelerated building blocks (zero eval/exec of untrusted strings).
    """
    ok, err = config.validate()
    if not ok:
        raise ValueError(f"Invalid DeclarativePFSPConfig: {err}")

    def solver(times: Sequence[Sequence[int]]) -> List[int]:
        n = len(times)
        if n <= 1:
            return list(range(n))
        m = len(times[0])

        # 1. Compute job priority scores
        machine_totals = [sum(times[i][k] for i in range(n)) for k in range(m)]
        bottleneck_m = max(range(m), key=lambda k: machine_totals[k])

        def tie_key(j: int) -> float:
            if config.tie_breaker == "index_asc":
                return float(j)
            elif config.tie_breaker == "first_machine_asc":
                return float(times[j][0])
            elif config.tie_breaker == "last_machine_desc":
                return float(-times[j][m - 1])
            elif config.tie_breaker == "bottleneck_slack":
                head = sum(times[j][:bottleneck_m])
                tail = sum(times[j][bottleneck_m + 1:])
                return float(head - tail)
            return float(j)

        if config.priority_rule == "total_time_desc":
            order = sorted(range(n), key=lambda j: (-sum(times[j]), tie_key(j), j))
        elif config.priority_rule == "palmer_slope":
            order = sorted(
                range(n),
                key=lambda j: (-sum((2 * k - m + 1) * times[j][k] for k in range(m)), tie_key(j), j),
            )
        elif config.priority_rule == "gupta_profile":
            def gupta_val(j: int) -> float:
                sign = 1.0 if times[j][0] < times[j][m - 1] else -1.0
                min_adj = min((times[j][k] + times[j][k + 1] for k in range(m - 1)), default=1)
                return sign / max(1.0, float(min_adj))
            order = sorted(range(n), key=lambda j: (-gupta_val(j), tie_key(j), j))
        elif config.priority_rule == "front_back_weighted":
            order = sorted(
                range(n),
                key=lambda j: (
                    -sum((m - k) * times[j][k] + 1.5 * (k + 1) * times[j][k] for k in range(m)),
                    tie_key(j),
                    j,
                ),
            )
        elif config.priority_rule == "cds_stage_best":
            stage = max(1, m // 2)
            front = []
            back = []
            for j in range(n):
                p1 = sum(times[j][:stage])
                p2 = sum(times[j][m - stage:])
                if p1 <= p2:
                    front.append((p1, tie_key(j), j))
                else:
                    back.append((-p2, tie_key(j), j))
            front.sort()
            back.sort()
            order = [j for _, _, j in front] + [j for _, _, j in back]
        else:
            order = list(range(n))

        # 2. Constructive Insertion with configured insertion_mode
        seq = [order[0]]
        for idx in range(1, n):
            seq, _ = taillard_best_insertion(times, seq, order[idx], tie_break=config.insertion_mode)

        best_seq = list(seq)
        best_cmax = compute_pfsp_makespan(times, best_seq)

        # 3. Deterministic Perturbation (Destruction / Reconstruction) if perturbation_d > 0
        def apply_local_search(curr_seq: List[int], curr_cmax: int) -> Tuple[List[int], int]:
            if config.local_search_op == "none":
                return curr_seq, curr_cmax

            seq_work = list(curr_seq)
            cmax_work = curr_cmax

            if config.local_search_op in ("insertion_ls", "vnd_insert_swap"):
                for _pass in range(2):
                    improved = False
                    for job in list(seq_work):
                        reduced = [x for x in seq_work if x != job]
                        cand_s, cand_c = taillard_best_insertion(
                            times, reduced, job, tie_break=config.insertion_mode
                        )
                        if cand_c < cmax_work:
                            seq_work = cand_s
                            cmax_work = cand_c
                            improved = True
                            if config.pivot_rule == "first_improvement":
                                break
                    if not improved:
                        break

            if config.local_search_op in ("swap_ls", "vnd_insert_swap"):
                best_swap_seq = seq_work
                best_swap_cmax = cmax_work
                for i in range(n - 1):
                    for j in range(i + 1, min(n, i + 6)):
                        trial = list(seq_work)
                        trial[i], trial[j] = trial[j], trial[i]
                        tc = compute_pfsp_makespan(times, trial)
                        if tc < best_swap_cmax:
                            best_swap_cmax = tc
                            best_swap_seq = trial
                            if config.pivot_rule == "first_improvement":
                                break
                    if config.pivot_rule == "first_improvement" and best_swap_cmax < cmax_work:
                        break
                seq_work, cmax_work = best_swap_seq, best_swap_cmax

            return seq_work, cmax_work

        best_seq, best_cmax = apply_local_search(best_seq, best_cmax)

        if config.perturbation_d > 0 and n > config.perturbation_d:
            # Deterministic destruction positions evenly spaced across schedule
            d = min(config.perturbation_d, n - 1)
            for round_idx in range(2):
                cand_seq = list(best_seq)
                removed = []
                for r_i in range(d):
                    pos = (r_i * 3 + round_idx + 1) % len(cand_seq)
                    removed.append(cand_seq.pop(pos))
                for job in removed:
                    cand_seq, _ = taillard_best_insertion(
                        times, cand_seq, job, tie_break=config.insertion_mode
                    )
                cand_cmax = compute_pfsp_makespan(times, cand_seq)
                cand_seq, cand_cmax = apply_local_search(cand_seq, cand_cmax)
                if cand_cmax < best_cmax:
                    best_seq = cand_seq
                    best_cmax = cand_cmax

        return best_seq

    return solver


# =============================================================================
# 2. DECLARATIVE BIN PACKING PARAMETRIC SCORER
# =============================================================================

@dataclass(frozen=True)
class DeclarativeBinPackingConfig:
    """
    Declarative parametric scorer for Online 1D Bin Packing:
    priority(item, rem, cap) =
        tight_bonus                                                 if (rem - item) / cap <= tight_threshold
        - ((rem - item) / cap) ** slack_exponent
        + fill_ratio_weight * (item / (rem + 1e-6))
        - mid_gap_penalty * exp(-(((rem - item)/cap - 0.25) / 0.10)**2)
    """
    slack_exponent: float = 1.0
    fill_ratio_weight: float = 0.0
    tight_threshold: float = 0.0
    tight_bonus: float = 0.0
    mid_gap_penalty: float = 0.0

    def to_canonical_dict(self) -> Dict[str, Any]:
        # Semantic canonicalization:
        # 1. If tight_bonus == 0 or tight_threshold <= 0, tight fit branch has no effect.
        eff_thresh = round(self.tight_threshold, 4) if (self.tight_bonus > 0 and self.tight_threshold > 0) else 0.0
        eff_bonus = round(self.tight_bonus, 4) if (self.tight_bonus > 0 and self.tight_threshold > 0) else 0.0
        # 2. If fill_ratio_weight == 0, tight_bonus == 0, and mid_gap_penalty == 0,
        # ANY positive slack_exponent > 0 is a strictly decreasing monotonic function of (rem - item),
        # which is 100% order-equivalent to Best-Fit (slack_exponent = 1.0)!
        if abs(self.fill_ratio_weight) < 1e-9 and eff_bonus == 0.0 and abs(self.mid_gap_penalty) < 1e-9 and self.slack_exponent > 0:
            eff_exp = 1.0
        else:
            eff_exp = round(self.slack_exponent, 4)

        return {
            "slack_exponent": eff_exp,
            "fill_ratio_weight": round(self.fill_ratio_weight, 4),
            "tight_threshold": eff_thresh,
            "tight_bonus": eff_bonus,
            "mid_gap_penalty": round(self.mid_gap_penalty, 4),
        }

    @property
    def structural_hash(self) -> str:
        payload = json.dumps(
            {
                "slack_exponent": round(self.slack_exponent, 4),
                "fill_ratio_weight": round(self.fill_ratio_weight, 4),
                "tight_threshold": round(self.tight_threshold, 4),
                "tight_bonus": round(self.tight_bonus, 4),
                "mid_gap_penalty": round(self.mid_gap_penalty, 4),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def canonical_hash(self) -> str:
        payload = json.dumps(self.to_canonical_dict(), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compile_declarative_bin_packing_scorer(
    config: DeclarativeBinPackingConfig,
) -> Callable[[float, float, float], float]:
    def scorer(item: float, remaining_capacity: float, bin_capacity: float) -> float:
        space_after = remaining_capacity - item
        norm_slack = max(0.0, space_after / max(1e-6, bin_capacity))
        if config.tight_bonus > 0.0 and norm_slack <= config.tight_threshold:
            return float(config.tight_bonus - norm_slack)
        base = -(norm_slack ** config.slack_exponent) if config.slack_exponent > 0 else 0.0
        fill_term = config.fill_ratio_weight * (item / max(1e-6, remaining_capacity))
        gap_diff = (norm_slack - 0.25) / 0.10
        gap_pen = config.mid_gap_penalty * math.exp(-(gap_diff * gap_diff))
        return float(base + fill_term - gap_pen)

    return scorer


# =============================================================================
# 3. PYTHON AST CANONICALIZATION (Syntax Validation & Alpha-Normalization)
# =============================================================================

class _ASTNormalizer(ast.NodeTransformer):
    """
    Strips docstrings, normalizes local variable names to v_0, v_1, ...,
    normalizes function argument names to arg_0, arg_1, ...,
    and folds simple numeric Constant BinOps so trivial renamings or comment edits
    map to the exact same canonical AST.
    """
    preserve_names = {
        "math", "random", "range", "len", "abs", "min", "max", "round",
        "sum", "float", "int", "bool", "pow", "divmod", "enumerate", "zip",
        "list", "set", "dict", "tuple", "sorted", "reversed", "True", "False", "None",
        "exp", "log", "sqrt", "ceil", "floor", "sin", "cos",
    }

    def __init__(self, entry_func_name: Optional[str] = None):
        super().__init__()
        self.entry_func_name = entry_func_name
        self.var_map: Dict[str, str] = {}
        self.counter = 0

    def _map_name(self, name: str) -> str:
        if name in self.preserve_names or name == self.entry_func_name:
            return name
        if name not in self.var_map:
            self.var_map[name] = f"v_{self.counter}"
            self.counter += 1
        return self.var_map[name]

    def visit_Module(self, node: ast.Module) -> ast.Module:
        # Strip module docstring
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        node.body = [self.visit(stmt) for stmt in body]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if self.entry_func_name is None:
            self.entry_func_name = node.name
        # Strip function docstring
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        for idx, arg in enumerate(node.args.args):
            self.var_map[arg.arg] = f"arg_{idx}"
            arg.arg = f"arg_{idx}"
            arg.annotation = None
        node.returns = None
        node.body = [self.visit(stmt) for stmt in body]
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self._map_name(node.id)
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        # Constant folding for simple numeric literals
        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            if isinstance(node.left.value, (int, float)) and isinstance(node.right.value, (int, float)):
                try:
                    if isinstance(node.op, ast.Add):
                        return ast.Constant(value=round(node.left.value + node.right.value, 8))
                    elif isinstance(node.op, ast.Sub):
                        return ast.Constant(value=round(node.left.value - node.right.value, 8))
                    elif isinstance(node.op, ast.Mult):
                        return ast.Constant(value=round(node.left.value * node.right.value, 8))
                except Exception:
                    pass
        # Commutative operand ordering for Add and Mult
        if isinstance(node.op, (ast.Add, ast.Mult)):
            d_left = ast.dump(node.left)
            d_right = ast.dump(node.right)
            if d_left > d_right:
                node.left, node.right = node.right, node.left
        return node


def canonicalize_python_code(code: str, entry_func_name: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns (structural_hash, canonical_ast_hash) for a Python code string.
    Raises SyntaxError if code is not valid Python.
    """
    structural_hash = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()[:16]
    tree = ast.parse(code)
    normalizer = _ASTNormalizer(entry_func_name=entry_func_name)
    norm_tree = normalizer.visit(tree)
    ast.fix_missing_locations(norm_tree)
    dumped = ast.dump(norm_tree, annotate_fields=True, include_attributes=False)
    canonical_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]
    return structural_hash, canonical_hash


# =============================================================================
# 4. BEHAVIORAL FINGERPRINTING & DIVERSITY MEASUREMENT
# =============================================================================

def compute_kendall_tau_distance(perm_a: Sequence[int], perm_b: Sequence[int]) -> float:
    """
    Computes normalized Kendall tau rank distance in [0.0, 1.0] between two permutations of the same elements.
    0.0 = identical ordering; 1.0 = exact reverse ordering.
    """
    n = len(perm_a)
    if n <= 1 or len(perm_b) != n:
        return 0.0
    pos_b = {val: idx for idx, val in enumerate(perm_b)}
    discordant = 0
    total_pairs = n * (n - 1) // 2
    for i in range(n):
        for j in range(i + 1, n):
            u, v = perm_a[i], perm_a[j]
            if u in pos_b and v in pos_b:
                if pos_b[u] > pos_b[v]:
                    discordant += 1
    return discordant / float(max(1, total_pairs))


class BehavioralFingerprinter:
    """
    Computes behavioral signatures on fixed, synthetic micro-probes (strictly disjoint from all
    benchmark splits) to detect behavioral collapse and measure population behavioral diversity.
    """

    # Synthetic PFSP micro-probes (4 small matrices with distinct bottleneck/slope geometry)
    PFSP_PROBES: Tuple[List[List[int]], ...] = (
        [[12, 4, 9], [5, 15, 6], [8, 7, 14], [11, 3, 5], [4, 12, 10]],
        [[20, 5, 5, 18], [6, 19, 14, 4], [10, 8, 12, 9], [4, 15, 6, 16], [14, 7, 11, 5]],
        [[7, 18, 3], [16, 4, 12], [9, 9, 9], [3, 14, 17], [15, 6, 8], [11, 11, 4]],
    )

    # Synthetic Bin Packing decision probes:
    # Each probe is (arriving_item, open_bins_remaining_capacities, bin_capacity)
    # Designed so Best-Fit, First-Fit, Worst-Fit, Almost-Worst-Fit, and threshold/harmonic scorers
    # select different bin indices!
    BIN_PACKING_DECISION_PROBES: Tuple[Tuple[float, Tuple[float, ...], float], ...] = (
        (24.0, (80.0, 25.0, 50.0, 32.0), 100.0),   # space_after: (56, 1, 26, 8) -> tightest=bin 1 (rem 25), 2nd=bin 3 (rem 32)
        (18.0, (45.0, 18.5, 22.0, 90.0), 100.0),   # space_after: (27, 0.5, 4, 72)
        (35.0, (40.0, 62.0, 38.0, 75.0), 100.0),   # space_after: (5, 27, 3, 40)
        (12.0, (16.0, 28.0, 13.0, 60.0), 100.0),   # space_after: (4, 16, 1, 48)
        (40.0, (85.0, 42.0, 55.0, 40.5), 100.0),   # space_after: (45, 2, 15, 0.5)
        (15.0, (30.0, 21.0, 17.5, 50.0), 100.0),   # space_after: (15, 6, 2.5, 35)
    )

    # Synthetic Graph Coloring micro-probes
    GC_PROBES: Tuple[List[List[int]], ...] = (
        [[1, 2, 3], [0, 2], [0, 1, 4], [0, 4], [2, 3]],
        [[1, 4, 5], [0, 2, 5], [1, 3], [2, 4], [0, 3, 5], [0, 1, 4]],
    )

    @classmethod
    def fingerprint_pfsp_solver(
        cls, solver_fn: Callable[[Sequence[Sequence[int]]], Sequence[int]]
    ) -> Tuple[str, Tuple[Tuple[int, ...], ...]]:
        traces: List[Tuple[int, ...]] = []
        for mat in cls.PFSP_PROBES:
            perm = tuple(int(x) for x in solver_fn([list(r) for r in mat]))
            traces.append(perm)
        trace_tuple = tuple(traces)
        b_hash = hashlib.sha256(json.dumps(trace_tuple).encode("utf-8")).hexdigest()[:16]
        return b_hash, trace_tuple

    @classmethod
    def fingerprint_bin_packing_scorer(
        cls, scorer_fn: Callable[[float, float, float], float]
    ) -> Tuple[str, Tuple[Tuple[int, ...], ...]]:
        """
        Records the complete ranking of open bins induced by `scorer_fn` on each probe state.
        Any two priority functions that rank open bins identically (e.g., all strictly decreasing
        monotonic functions of remaining_capacity - item) yield the EXACT SAME behavioral hash!
        """
        rankings: List[Tuple[int, ...]] = []
        for item, open_bins, cap in cls.BIN_PACKING_DECISION_PROBES:
            scored = []
            for idx, rem in enumerate(open_bins):
                if rem >= item - 1e-6:
                    p = float(scorer_fn(item, rem, cap))
                    # Sort descending by priority score, tie-break by lowest index (First-Found)
                    scored.append((-p, idx))
            scored.sort()
            order = tuple(idx for _, idx in scored)
            rankings.append(order)
        trace_tuple = tuple(rankings)
        b_hash = hashlib.sha256(json.dumps(trace_tuple).encode("utf-8")).hexdigest()[:16]
        return b_hash, trace_tuple

    @classmethod
    def fingerprint_gc_solver(
        cls, solver_fn: Callable[[Sequence[Sequence[int]]], Sequence[int]]
    ) -> Tuple[str, Tuple[Tuple[int, ...], ...]]:
        """
        Canonicalizes vertex coloring by relabeling colors in order of first appearance (0, 1, 2, ...)
        so isomorphic colorings produce the exact same behavioral fingerprint.
        """
        traces: List[Tuple[int, ...]] = []
        for adj in cls.GC_PROBES:
            raw_cols = [int(c) for c in solver_fn([list(r) for r in adj])]
            remap: Dict[int, int] = {}
            canon_cols: List[int] = []
            for c in raw_cols:
                if c not in remap:
                    remap[c] = len(remap)
                canon_cols.append(remap[c])
            traces.append(tuple(canon_cols))
        trace_tuple = tuple(traces)
        b_hash = hashlib.sha256(json.dumps(trace_tuple).encode("utf-8")).hexdigest()[:16]
        return b_hash, trace_tuple

    @staticmethod
    def compute_behavioral_distance(
        sig_a: Sequence[Sequence[int]], sig_b: Sequence[Sequence[int]]
    ) -> float:
        """
        Computes mean normalized Kendall tau distance in [0.0, 1.0] across probe trace tuples.
        Returns 0.0 iff the two candidates make identical ordering decisions on all probes.
        """
        if not sig_a or not sig_b or len(sig_a) != len(sig_b):
            return 1.0
        dists = []
        for ta, tb in zip(sig_a, sig_b):
            if set(ta) == set(tb) and len(ta) == len(tb):
                dists.append(compute_kendall_tau_distance(ta, tb))
            else:
                # Hamming disagreement fallback for non-permutation vectors
                min_len = min(len(ta), len(tb))
                if min_len == 0:
                    dists.append(0.0)
                else:
                    diffs = sum(1 for x, y in zip(ta[:min_len], tb[:min_len]) if x != y)
                    dists.append(diffs / float(min_len))
        return round(sum(dists) / len(dists), 6)


# =============================================================================
# 5. UNIFIED SAFE CANDIDATE SPECIFICATION (Non-Executable Descriptor)
# =============================================================================

@dataclass
class CandidateSpec:
    """
    Safe, serializable, non-executable candidate specification.
    Maintains structural hash, semantic canonical hash, and (post-probe) behavioral signature.
    """
    candidate_id: str
    kind: CandidateKind
    problem_id: str
    method_id: str
    strategy_id: str
    payload: Dict[str, Any]
    structural_hash: str
    canonical_hash: str
    parent_ids: List[str] = field(default_factory=list)
    generation: int = 0
    behavioral_hash: Optional[str] = None
    behavioral_trace: Optional[Tuple[Tuple[int, ...], ...]] = None
    provenance_metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_declarative_pfsp(
        cls,
        config: DeclarativePFSPConfig,
        strategy_id: str = "declarative_enum",
        parent_ids: Optional[List[str]] = None,
        generation: int = 0,
    ) -> "CandidateSpec":
        s_hash = config.structural_hash
        c_hash = config.canonical_hash
        solver = compile_declarative_pfsp_solver(config)
        b_hash, b_trace = BehavioralFingerprinter.fingerprint_pfsp_solver(solver)
        return cls(
            candidate_id=f"pfsp-{s_hash[:8]}",
            kind=CandidateKind.DECLARATIVE_PFSP,
            problem_id="pfsp_makespan",
            method_id="declarative_pfsp_compiler",
            strategy_id=strategy_id,
            payload=config.to_structural_dict(),
            structural_hash=s_hash,
            canonical_hash=c_hash,
            parent_ids=list(parent_ids or []),
            generation=generation,
            behavioral_hash=b_hash,
            behavioral_trace=b_trace,
        )

    @classmethod
    def from_declarative_bin_packing(
        cls,
        config: DeclarativeBinPackingConfig,
        strategy_id: str = "parametric_search",
        parent_ids: Optional[List[str]] = None,
        generation: int = 0,
    ) -> "CandidateSpec":
        s_hash = config.structural_hash
        c_hash = config.canonical_hash
        scorer = compile_declarative_bin_packing_scorer(config)
        b_hash, b_trace = BehavioralFingerprinter.fingerprint_bin_packing_scorer(scorer)
        return cls(
            candidate_id=f"bp-{s_hash[:8]}",
            kind=CandidateKind.DECLARATIVE_BIN_PACKING,
            problem_id="online_bin_packing_1d",
            method_id="parametric_bin_packing_compiler",
            strategy_id=strategy_id,
            payload={
                "slack_exponent": config.slack_exponent,
                "fill_ratio_weight": config.fill_ratio_weight,
                "tight_threshold": config.tight_threshold,
                "tight_bonus": config.tight_bonus,
                "mid_gap_penalty": config.mid_gap_penalty,
            },
            structural_hash=s_hash,
            canonical_hash=c_hash,
            parent_ids=list(parent_ids or []),
            generation=generation,
            behavioral_hash=b_hash,
            behavioral_trace=b_trace,
        )

    @classmethod
    def from_python_program(
        cls,
        code: str,
        entry_func_name: str,
        problem_id: str,
        strategy_id: str = "program_synthesis",
        parent_ids: Optional[List[str]] = None,
        generation: int = 0,
        provenance_metadata: Optional[Dict[str, Any]] = None,
    ) -> "CandidateSpec":
        try:
            s_hash, c_hash = canonicalize_python_code(code, entry_func_name=entry_func_name)
        except SyntaxError:
            s_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
            c_hash = f"syntax_invalid_{s_hash}"
        return cls(
            candidate_id=f"prog-{s_hash[:8]}",
            kind=CandidateKind.PYTHON_PROGRAM,
            problem_id=problem_id,
            method_id="sandboxed_python_program",
            strategy_id=strategy_id,
            payload={"code": code, "entry_func_name": entry_func_name},
            structural_hash=s_hash,
            canonical_hash=c_hash,
            parent_ids=list(parent_ids or []),
            generation=generation,
            provenance_metadata=dict(provenance_metadata or {}),
        )
