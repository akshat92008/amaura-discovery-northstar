"""
Discovery Kernel v0.1: Declarative PFSP Candidate Adapter & Verified Solver
==========================================================================
Provides a restricted, declarative algorithm space for Permutation Flow-Shop
Scheduling (PFSP). Eliminates arbitrary code execution by composing verified,
deterministic algorithmic building blocks through a strict JSON specification.
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple, Union

from discovery_kernel.method_adapter import MethodAdapter, MethodMetadata
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    calc_makespan_and_flow_ref
)
from benchmark_v1.src.domains.pfsp_full_algorithm import validate_permutation


# =========================================================================
# Allowed Component Taxonomy & Resource Bounds
# =========================================================================

MIN_EVALUATION_BUDGET = 50
MAX_EVALUATION_BUDGET = 50000

INITIAL_ORDERS = [
    "total_processing_time_desc",
    "total_processing_time_asc",
    "first_machine_asc",
    "last_machine_desc",
    "weighted_profile_desc"
]

CONSTRUCTION_CRITERIA = [
    "makespan_only",
    "makespan_and_flow_time",
    "makespan_and_idle_time"
]

TIE_BREAKS = [
    "first_found",
    "last_found",
    "flow_time_min",
    "idle_time_min"
]

LOCAL_SEARCHES = [
    "none",
    "pairwise_swap",
    "single_pass_insertion",
    "multi_pass_insertion"
]

SEARCH_STRATEGIES = [
    "none",
    "first_improvement",
    "best_improvement"
]

ACCEPTANCE_RULES = [
    "none",
    "strictly_better_makespan",
    "better_makespan_or_flow"
]


# =========================================================================
# Validation and Canonicalization
# =========================================================================

def validate_config(raw_proposal: Any) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates a raw model proposal against the declarative component schema.
    Returns (is_valid, error_reason, sanitized_proposal).
    """
    if not isinstance(raw_proposal, dict):
        return False, "Proposal must be a JSON object", None

    if "rationale" not in raw_proposal or not isinstance(raw_proposal["rationale"], str):
        return False, "Proposal missing valid string 'rationale'", None

    if "config" not in raw_proposal or not isinstance(raw_proposal["config"], dict):
        return False, "Proposal missing valid object 'config'", None

    cfg = raw_proposal["config"]
    required_keys = [
        "initial_order", "construction_criterion", "tie_break",
        "local_search", "search_strategy", "acceptance_rule", "budget_evaluations"
    ]
    for k in required_keys:
        if k not in cfg:
            return False, f"Missing required config key: '{k}'", None

    # Validate enums (converting lists of len 1 if model generated a singleton list)
    sanitized_cfg = {}
    for k in ["initial_order", "construction_criterion", "tie_break", "local_search", "search_strategy", "acceptance_rule"]:
        val = cfg[k]
        if isinstance(val, list) and len(val) == 1:
            val = val[0]
        if not isinstance(val, str):
            return False, f"Config field '{k}' must be a string", None
        sanitized_cfg[k] = val

    budget = cfg["budget_evaluations"]
    if isinstance(budget, list) and len(budget) == 1:
        budget = budget[0]

    # Check allowed enum values
    if sanitized_cfg["initial_order"] not in INITIAL_ORDERS:
        return False, f"Invalid initial_order: '{sanitized_cfg['initial_order']}'", None

    if sanitized_cfg["construction_criterion"] not in CONSTRUCTION_CRITERIA:
        return False, f"Invalid construction_criterion: '{sanitized_cfg['construction_criterion']}'", None

    if sanitized_cfg["tie_break"] not in TIE_BREAKS:
        return False, f"Invalid tie_break: '{sanitized_cfg['tie_break']}'", None

    if sanitized_cfg["local_search"] not in LOCAL_SEARCHES:
        return False, f"Invalid local_search: '{sanitized_cfg['local_search']}'", None

    # Handle local_search == "none" normalization
    if sanitized_cfg["local_search"] == "none":
        sanitized_cfg["search_strategy"] = "none"
        sanitized_cfg["acceptance_rule"] = "none"
        sanitized_cfg["budget_evaluations"] = 0
    else:
        if sanitized_cfg["search_strategy"] not in ["first_improvement", "best_improvement"]:
            return False, f"Invalid search_strategy for local search: '{sanitized_cfg['search_strategy']}'", None
        if sanitized_cfg["acceptance_rule"] not in ["strictly_better_makespan", "better_makespan_or_flow"]:
            return False, f"Invalid acceptance_rule for local search: '{sanitized_cfg['acceptance_rule']}'", None

        # Validate budget
        if isinstance(budget, str) and budget == "single_pass":
            sanitized_cfg["budget_evaluations"] = "single_pass"
        elif isinstance(budget, (int, float)) and int(budget) == budget:
            budget_int = int(budget)
            if budget_int < MIN_EVALUATION_BUDGET or budget_int > MAX_EVALUATION_BUDGET:
                return False, f"budget_evaluations ({budget_int}) must be between {MIN_EVALUATION_BUDGET} and {MAX_EVALUATION_BUDGET} or 'single_pass'", None
            sanitized_cfg["budget_evaluations"] = budget_int
        else:
            return False, "Config field 'budget_evaluations' must be an integer or 'single_pass'", None

    sanitized_proposal = {
        "rationale": raw_proposal["rationale"].strip(),
        "config": sanitized_cfg
    }
    return True, None, sanitized_proposal


def canonicalize_config(config: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    """
    Produces canonical normalized config, sorted JSON string, and SHA-256 recipe_hash.
    """
    sorted_cfg = {k: config[k] for k in sorted(config.keys())}
    canonical_json = json.dumps(sorted_cfg, sort_keys=True, separators=(',', ':'))
    recipe_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    return sorted_cfg, canonical_json, recipe_hash


# =========================================================================
# Verified Algorithmic Building Blocks
# =========================================================================

def _compute_idle_time(times: List[List[int]], perm: List[int]) -> int:
    """Computes total machine idle time across all machines for schedule perm."""
    if not times or not perm:
        return 0
    m = len(times[0])
    dp = [0] * m
    total_idle = 0
    for job in perm:
        # Machine 0 never has idle time between jobs once started
        dp[0] += times[job][0]
        for c in range(1, m):
            if dp[c - 1] > dp[c]:
                total_idle += (dp[c - 1] - dp[c])
                dp[c] = dp[c - 1] + times[job][c]
            else:
                dp[c] += times[job][c]
    return total_idle


def _order_jobs(processing_times: List[List[int]], initial_order: str) -> List[int]:
    """Computes initial job permutation order according to selected rule."""
    n = len(processing_times)
    m = len(processing_times[0]) if n > 0 else 0

    if initial_order == "total_processing_time_desc":
        # NEH standard: sum processing times descending
        return sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)
    elif initial_order == "total_processing_time_asc":
        # SPT on total time: sum processing times ascending
        return sorted(range(n), key=lambda j: sum(processing_times[j]))
    elif initial_order == "first_machine_asc":
        # Johnson-like: machine 0 ascending
        return sorted(range(n), key=lambda j: processing_times[j][0])
    elif initial_order == "last_machine_desc":
        # Johnson-like: last machine descending
        return sorted(range(n), key=lambda j: processing_times[j][m - 1], reverse=True)
    elif initial_order == "weighted_profile_desc":
        # Palmer's slope index: sum_{k=0}^{m-1} (2k - m + 1) * p[j][k]
        weights = [2 * k - m + 1 for k in range(m)]
        return sorted(range(n), key=lambda j: sum(weights[k] * processing_times[j][k] for k in range(m)), reverse=True)
    else:
        return list(range(n))


def _evaluate_partial_schedule(
    times: List[List[int]],
    seq: List[int],
    criterion: str,
    tie_break: str
) -> Tuple[int, int, int]:
    """
    Evaluates a candidate partial schedule.
    Returns (primary_key, secondary_key, tertiary_key) for min-tuple comparison.
    """
    cmax, flow = calc_makespan_and_flow_ref(times, seq)

    if criterion == "makespan_only":
        primary = cmax
        if tie_break == "flow_time_min":
            secondary = flow
        elif tie_break == "idle_time_min":
            secondary = _compute_idle_time(times, seq)
        else:
            secondary = 0
    elif criterion == "makespan_and_flow_time":
        primary = cmax
        secondary = flow
    elif criterion == "makespan_and_idle_time":
        primary = cmax
        secondary = _compute_idle_time(times, seq)
    else:
        primary = cmax
        secondary = 0

    return (primary, secondary, 0)


def _is_candidate_better(
    c_cand: int,
    f_cand: int,
    times: List[List[int]],
    cand_seq: List[int],
    best_cmax: int,
    best_flow: int,
    best_idle: Optional[int],
    acceptance_rule: str,
    tie_break: str
) -> Tuple[bool, Optional[int]]:
    """
    Compares candidate neighbor against the best neighbor found so far in the neighborhood.
    Honours the declared tie-breaking policy explicitly.
    Returns (is_better, cand_idle).
    """
    cand_idle = None
    if c_cand < best_cmax:
        if tie_break == "idle_time_min":
            cand_idle = _compute_idle_time(times, cand_seq)
        return True, cand_idle

    if c_cand == best_cmax:
        if acceptance_rule == "better_makespan_or_flow":
            if f_cand < best_flow:
                if tie_break == "idle_time_min":
                    cand_idle = _compute_idle_time(times, cand_seq)
                return True, cand_idle
            elif f_cand > best_flow:
                return False, cand_idle
            # If both makespan and flow tie, apply tie_break
            if tie_break == "first_found":
                return False, cand_idle
            elif tie_break == "last_found":
                return True, cand_idle
            elif tie_break == "idle_time_min":
                cand_idle = _compute_idle_time(times, cand_seq)
                target_idle = best_idle if best_idle is not None else float("inf")
                return (cand_idle < target_idle), cand_idle
            return False, cand_idle

        # acceptance_rule == "strictly_better_makespan"
        if tie_break == "first_found":
            return False, cand_idle
        elif tie_break == "last_found":
            return True, cand_idle
        elif tie_break == "flow_time_min":
            return (f_cand < best_flow), cand_idle
        elif tie_break == "idle_time_min":
            cand_idle = _compute_idle_time(times, cand_seq)
            target_idle = best_idle if best_idle is not None else float("inf")
            return (cand_idle < target_idle), cand_idle

    return False, cand_idle


def solve_declarative(
    processing_times: List[List[int]],
    config: Dict[str, Any],
    return_diagnostics: bool = False
) -> Any:
    """
    Executes declarative PFSP algorithm configuration using verified components.
    Guaranteed to return a valid permutation of range(n).
    If return_diagnostics is True, returns (permutation, diagnostics_dict).
    """
    t0 = time.perf_counter()
    n = len(processing_times)
    if n == 0:
        diag = {
            "evaluations_used": 0,
            "budget_evaluations": 0,
            "termination_condition": "empty_instance",
            "completed_pass": True,
            "passes_completed": 0,
            "runtime_ms": 0.0,
            "initial_cmax": 0,
            "final_cmax": 0
        }
        return ([], diag) if return_diagnostics else []
    if n == 1:
        c1 = sum(processing_times[0])
        diag = {
            "evaluations_used": 0,
            "budget_evaluations": 0,
            "termination_condition": "single_job",
            "completed_pass": True,
            "passes_completed": 0,
            "runtime_ms": 0.0,
            "initial_cmax": c1,
            "final_cmax": c1
        }
        return ([0], diag) if return_diagnostics else [0]

    initial_order = config["initial_order"]
    construction_criterion = config["construction_criterion"]
    tie_break = config["tie_break"]
    local_search = config["local_search"]
    search_strategy = config.get("search_strategy", "none")
    acceptance_rule = config.get("acceptance_rule", "none")
    raw_budget = config.get("budget_evaluations", 0)

    # Determine effective budget evaluations for this instance
    if raw_budget == "single_pass":
        if local_search == "pairwise_swap":
            budget_evals = min(n - 1, MAX_EVALUATION_BUDGET)
        elif local_search in ["single_pass_insertion", "multi_pass_insertion"]:
            budget_evals = min(n * (n - 1), MAX_EVALUATION_BUDGET)
        else:
            budget_evals = 0
    else:
        budget_evals = min(int(raw_budget), MAX_EVALUATION_BUDGET)

    # 1. Job Ordering
    ordered_jobs = _order_jobs(processing_times, initial_order)

    # 2. Constructive Phase (NEH-style incremental insertion)
    j1, j2 = ordered_jobs[0], ordered_jobs[1]
    cand1 = [j1, j2]
    cand2 = [j2, j1]
    score1 = _evaluate_partial_schedule(processing_times, cand1, construction_criterion, tie_break)
    score2 = _evaluate_partial_schedule(processing_times, cand2, construction_criterion, tie_break)

    if score1 < score2 or (score1 == score2 and tie_break != "last_found"):
        current_seq = cand1
    else:
        current_seq = cand2

    for job in ordered_jobs[2:]:
        best_pos = 0
        best_score = None
        num_positions = len(current_seq) + 1

        # Determine evaluation order across positions
        positions = list(range(num_positions))
        if tie_break == "last_found":
            positions = list(reversed(positions))

        for pos in positions:
            cand = current_seq[:pos] + [job] + current_seq[pos:]
            score = _evaluate_partial_schedule(processing_times, cand, construction_criterion, tie_break)
            if best_score is None or score < best_score:
                best_score = score
                best_pos = pos

        current_seq.insert(best_pos, job)

    cur_cmax, cur_flow = calc_makespan_and_flow_ref(processing_times, current_seq)
    init_cmax = cur_cmax

    # If no local search, return constructed sequence
    if local_search == "none" or budget_evals <= 0:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        diag = {
            "evaluations_used": 0,
            "budget_evaluations": budget_evals,
            "termination_condition": "constructive_only",
            "completed_pass": True,
            "passes_completed": 0,
            "runtime_ms": round(elapsed_ms, 3),
            "initial_cmax": init_cmax,
            "final_cmax": cur_cmax
        }
        return (current_seq, diag) if return_diagnostics else current_seq

    # 3. Local Search Phase
    evals_used = 0
    cur_idle = _compute_idle_time(processing_times, current_seq) if tie_break == "idle_time_min" else None
    term_cond = "pass_complete"
    completed_pass = True
    passes_completed = 0

    def is_better_than_current(c_cand: int, f_cand: int) -> bool:
        if acceptance_rule == "strictly_better_makespan":
            return c_cand < cur_cmax
        elif acceptance_rule == "better_makespan_or_flow":
            return c_cand < cur_cmax or (c_cand == cur_cmax and f_cand < cur_flow)
        return False

    if local_search == "pairwise_swap":
        improved = True
        while improved and evals_used < budget_evals:
            improved = False
            best_swap = None
            best_swap_cmax = cur_cmax
            best_swap_flow = cur_flow
            best_swap_idle = cur_idle
            pass_budget_exhausted = False

            for i in range(n - 1):
                if evals_used >= budget_evals:
                    pass_budget_exhausted = True
                    break
                cand = current_seq.copy()
                cand[i], cand[i + 1] = cand[i + 1], cand[i]
                c_cand, f_cand = calc_makespan_and_flow_ref(processing_times, cand)
                evals_used += 1

                if is_better_than_current(c_cand, f_cand):
                    if search_strategy == "first_improvement":
                        current_seq = cand
                        cur_cmax, cur_flow = c_cand, f_cand
                        if tie_break == "idle_time_min":
                            cur_idle = _compute_idle_time(processing_times, current_seq)
                        improved = True
                        break
                    elif search_strategy == "best_improvement":
                        is_cand_better, cand_idle = _is_candidate_better(
                            c_cand, f_cand, processing_times, cand,
                            best_swap_cmax, best_swap_flow, best_swap_idle,
                            acceptance_rule, tie_break
                        )
                        if is_cand_better:
                            best_swap = cand
                            best_swap_cmax = c_cand
                            best_swap_flow = f_cand
                            best_swap_idle = cand_idle

            if pass_budget_exhausted:
                term_cond = "budget_exhausted"
                completed_pass = False
                break

            if search_strategy == "best_improvement" and best_swap is not None:
                current_seq = best_swap
                cur_cmax, cur_flow = best_swap_cmax, best_swap_flow
                cur_idle = best_swap_idle
                improved = True

            if improved:
                passes_completed += 1
            else:
                term_cond = "converged"
                completed_pass = True
                passes_completed += 1
                break

    elif local_search in ["single_pass_insertion", "multi_pass_insertion"]:
        max_passes = 1 if local_search == "single_pass_insertion" else 5
        for pass_idx in range(max_passes):
            improved_in_pass = False
            pass_budget_exhausted = False

            for i in range(n):
                if evals_used >= budget_evals:
                    pass_budget_exhausted = True
                    break
                job = current_seq[i]
                temp_seq = current_seq[:i] + current_seq[i + 1:]
                best_ins_pos = i
                best_ins_cmax = cur_cmax
                best_ins_flow = cur_flow
                best_ins_idle = cur_idle

                for j in range(n):
                    if j == i:
                        continue
                    if evals_used >= budget_evals:
                        pass_budget_exhausted = True
                        break
                    cand = temp_seq[:j] + [job] + temp_seq[j:]
                    c_cand, f_cand = calc_makespan_and_flow_ref(processing_times, cand)
                    evals_used += 1

                    if is_better_than_current(c_cand, f_cand):
                        if search_strategy == "first_improvement":
                            current_seq = cand
                            cur_cmax, cur_flow = c_cand, f_cand
                            if tie_break == "idle_time_min":
                                cur_idle = _compute_idle_time(processing_times, current_seq)
                            improved_in_pass = True
                            break
                        elif search_strategy == "best_improvement":
                            is_cand_better, cand_idle = _is_candidate_better(
                                c_cand, f_cand, processing_times, cand,
                                best_ins_cmax, best_ins_flow, best_ins_idle,
                                acceptance_rule, tie_break
                            )
                            if is_cand_better:
                                best_ins_pos = j
                                best_ins_cmax = c_cand
                                best_ins_flow = f_cand
                                best_ins_idle = cand_idle

                if search_strategy == "best_improvement" and best_ins_pos != i:
                    current_seq = temp_seq[:best_ins_pos] + [job] + temp_seq[best_ins_pos:]
                    cur_cmax, cur_flow = best_ins_cmax, best_ins_flow
                    cur_idle = best_ins_idle
                    improved_in_pass = True

                if pass_budget_exhausted:
                    break

            if pass_budget_exhausted:
                term_cond = "budget_exhausted"
                completed_pass = False
                break

            passes_completed += 1
            if not improved_in_pass:
                term_cond = "converged"
                completed_pass = True
                break
            else:
                if pass_idx == max_passes - 1:
                    term_cond = "pass_complete"
                    completed_pass = True

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    diag = {
        "evaluations_used": evals_used,
        "budget_evaluations": budget_evals,
        "termination_condition": term_cond,
        "completed_pass": completed_pass,
        "passes_completed": passes_completed,
        "runtime_ms": round(elapsed_ms, 3),
        "initial_cmax": init_cmax,
        "final_cmax": cur_cmax
    }
    return (current_seq, diag) if return_diagnostics else current_seq


# =========================================================================
# Declarative PFSP Method Adapter
# =========================================================================

class PFSPDeclarativeAdapter(MethodAdapter):
    """
    Method adapter wrapping a validated, canonical declarative PFSP algorithm configuration.
    """
    def __init__(
        self,
        method_id: str,
        config: Dict[str, Any],
        rationale: str = "",
        version: str = "1.0.0"
    ):
        sorted_cfg, canonical_json, recipe_hash = canonicalize_config(config)
        self.config = sorted_cfg
        self.rationale = rationale
        self.recipe_hash = recipe_hash
        self.last_diagnostics: Optional[Dict[str, Any]] = None

        super().__init__(MethodMetadata(
            method_id=method_id,
            version=version,
            description=f"Declarative PFSP: {rationale[:80]}",
            author="North BlueStar Candidate",
            parameters={
                "recipe_hash": recipe_hash,
                "config": sorted_cfg,
                "rationale": rationale
            },
            source_code=canonical_json
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        times = instance["times"] if isinstance(instance, dict) else instance
        seq, diag = solve_declarative(times, self.config, return_diagnostics=True)
        self.last_diagnostics = diag
        if isinstance(context, dict):
            context["diagnostics"] = diag
        return seq
