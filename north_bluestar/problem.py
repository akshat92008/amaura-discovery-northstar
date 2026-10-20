"""
North BlueStar — Problem Formalization & Split Firewall (Capability A)
======================================================================
Provides formal, domain-agnostic interfaces for:
- Objective and optimization direction (MINIMIZE / MAXIMIZE).
- Hard feasibility constraints vs objective scoring (never conflating invalid solutions with numeric penalties).
- Input data, instance metadata, theoretical bounds, and cryptographic provenance.
- Evaluator, independent verifier, and classical baselines.
- Strict boundary firewall between DEVELOPMENT, VALIDATION, and FINAL_HOLDOUT splits.
- Explicit distinction between FEASIBLE vs INFEASIBLE and MEASURED_IMPROVEMENT vs PROVEN_OPTIMAL.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class OptimizationDirection(str, Enum):
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


class SplitType(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class LifecyclePhase(str, Enum):
    DEVELOPMENT_SEARCH = "DEVELOPMENT_SEARCH"
    VALIDATION_SELECTION = "VALIDATION_SELECTION"
    CHAMPIONS_FROZEN_HOLDOUT_UNSEALED = "CHAMPIONS_FROZEN_HOLDOUT_UNSEALED"


class SolutionStatus(str, Enum):
    PROVEN_OPTIMAL = "PROVEN_OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    TIMEOUT = "TIMEOUT"


class SplitAccessViolationError(PermissionError):
    """Raised when a search strategy or evaluator attempts to access FINAL_HOLDOUT before champions are frozen."""
    pass


@dataclass(frozen=True)
class ProblemInstance:
    """Immutable representation of a single problem instance with provenance and theoretical bound."""
    instance_id: str
    split: SplitType
    data: Dict[str, Any]
    provenance: str = "synthetic_deterministic"
    theoretical_bound: Optional[float] = None
    scale_factor: float = 1.0

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            {"id": self.instance_id, "split": self.split.value, "data": self.data},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ConstraintCheckResult:
    """Result of checking hard validity conditions on a candidate solution."""
    is_feasible: bool
    violations: List[str] = field(default_factory=list)
    checked_invariants: List[str] = field(default_factory=list)


@dataclass
class InstanceEvaluationOutcome:
    """
    Outcome of evaluating a solver on a single ProblemInstance.
    Invalid/infeasible solutions ALWAYS have objective_value=None so they can never invert rankings.
    """
    instance_id: str
    status: SolutionStatus
    is_feasible: bool
    is_proven_optimal: bool
    objective_value: Optional[float]
    theoretical_bound: Optional[float]
    optimality_gap_pct: Optional[float]
    runtime_ms: float
    solution: Any = None
    violations: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class AggregateEvaluationOutcome:
    """
    Aggregate outcome across a dataset split (DEVELOPMENT, VALIDATION, or FINAL_HOLDOUT).
    Explicitly separates feasibility, objective quality, proven optimality, and runtime efficiency.
    """
    split: SplitType
    is_fully_feasible: bool
    feasible_count: int
    total_count: int
    proven_optimal_count: int
    mean_objective: Optional[float]
    total_objective: Optional[float]
    std_objective: Optional[float]
    mean_optimality_gap_pct: Optional[float]
    total_runtime_ms: float
    mean_runtime_ms: float
    measured_improvement_vs_baseline_pct: Optional[float] = None
    runtime_speedup_vs_baseline: Optional[float] = None
    is_proven_split_optimal: bool = False
    instance_outcomes: List[InstanceEvaluationOutcome] = field(default_factory=list)
    failure_summary: Optional[str] = None


class SplitFirewall:
    """
    Enforces strict isolation between DEVELOPMENT, VALIDATION, and FINAL_HOLDOUT splits.
    FINAL_HOLDOUT cannot be accessed until freeze_champions() has been called with non-empty champion IDs.
    """
    def __init__(self, splits: Dict[SplitType, List[ProblemInstance]]):
        self._splits: Dict[SplitType, List[ProblemInstance]] = {
            k: list(v) for k, v in splits.items()
        }
        self.phase: LifecyclePhase = LifecyclePhase.DEVELOPMENT_SEARCH
        self.frozen_champion_ids: Optional[Tuple[str, ...]] = None
        self.access_log: List[Dict[str, Any]] = []
        self._split_hashes: Dict[SplitType, str] = {
            split: self._compute_split_hash(instances)
            for split, instances in self._splits.items()
        }

    @staticmethod
    def _compute_split_hash(instances: Sequence[ProblemInstance]) -> str:
        hashes = [inst.sha256 for inst in instances]
        serialized = json.dumps(hashes)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_split_hash(self, split: SplitType) -> str:
        return self._split_hashes.get(split, "")

    def advance_to_validation(self) -> None:
        if self.phase == LifecyclePhase.DEVELOPMENT_SEARCH:
            self.phase = LifecyclePhase.VALIDATION_SELECTION

    def freeze_champions(self, champion_ids: Sequence[str]) -> str:
        """Freezes selected champion IDs and unseals FINAL_HOLDOUT for one-shot verification."""
        if not champion_ids:
            raise ValueError("Cannot freeze empty champion_ids list.")
        if self.frozen_champion_ids is not None:
            raise RuntimeError("Champions have already been frozen; re-freezing is prohibited.")
        self.frozen_champion_ids = tuple(champion_ids)
        self.phase = LifecyclePhase.CHAMPIONS_FROZEN_HOLDOUT_UNSEALED
        payload = json.dumps(
            {
                "frozen_champions": list(self.frozen_champion_ids),
                "holdout_hash": self.get_split_hash(SplitType.FINAL_HOLDOUT),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get_instances(self, split: SplitType, caller: str = "unknown") -> List[ProblemInstance]:
        """Returns defensive copies of instances for the requested split if permitted by firewall state."""
        if split == SplitType.FINAL_HOLDOUT and self.phase != LifecyclePhase.CHAMPIONS_FROZEN_HOLDOUT_UNSEALED:
            self.access_log.append(
                {"split": split.value, "caller": caller, "phase": self.phase.value, "allowed": False}
            )
            raise SplitAccessViolationError(
                f"FIREWALL VIOLATION: Caller '{caller}' attempted to access FINAL_HOLDOUT during phase '{self.phase.value}'. "
                "Holdout evaluation is strictly forbidden prior to freeze_champions()."
            )

        # Verify cryptographic integrity before returning instances
        instances = self._splits.get(split, [])
        current_hash = self._compute_split_hash(instances)
        if current_hash != self._split_hashes.get(split, ""):
            raise ValueError(f"SPLIT TAMPERING DETECTED on {split.value}: SHA-256 mismatch.")

        self.access_log.append(
            {"split": split.value, "caller": caller, "phase": self.phase.value, "allowed": True}
        )
        return copy.deepcopy(instances)


class ProblemSpecification(ABC):
    """
    Formal interface describing an optimization or algorithm-discovery problem.
    Separates feasibility validation, objective calculation, theoretical bounds, and baselines.
    """
    def __init__(
        self,
        problem_id: str,
        name: str,
        direction: OptimizationDirection,
         firewall: SplitFirewall,
        default_timeout_ms: float = 500.0,
    ):
        self.problem_id = problem_id
        self.name = name
        self.direction = direction
        self.firewall = firewall
        self.default_timeout_ms = default_timeout_ms

    @abstractmethod
    def validate_solution(self, instance: ProblemInstance, solution: Any) -> ConstraintCheckResult:
        """Checks whether a candidate output satisfies all hard problem constraints."""
        pass

    @abstractmethod
    def compute_objective(self, instance: ProblemInstance, solution: Any) -> float:
        """Computes the exact scalar objective value for a validated feasible solution."""
        pass

    @abstractmethod
    def compute_theoretical_bound(self, instance: ProblemInstance) -> Optional[float]:
        """Computes a mathematical lower bound (for MINIMIZE) or upper bound (for MAXIMIZE)."""
        pass

    @abstractmethod
    def get_baselines(self) -> Dict[str, Callable[[ProblemInstance], Any]]:
        """Returns deterministic, verified baseline solvers for this problem."""
        pass

    def is_better(self, score_a: float, score_b: float, tol: float = 1e-9) -> bool:
        if self.direction == OptimizationDirection.MINIMIZE:
            return score_a < score_b - tol
        return score_a > score_b + tol

    def evaluate_solution_on_instance(
        self,
        instance: ProblemInstance,
        solution: Any,
        runtime_ms: float = 0.0,
        error_message: Optional[str] = None,
        timed_out: bool = False,
    ) -> InstanceEvaluationOutcome:
        """
        Evaluates a produced solution against constraints, objective, and optimality bound.
        Never assigns a numeric objective to an invalid, crashing, or timed-out candidate.
        """
        bound = instance.theoretical_bound
        if bound is None:
            bound = self.compute_theoretical_bound(instance)

        if timed_out:
            return InstanceEvaluationOutcome(
                instance_id=instance.instance_id,
                status=SolutionStatus.TIMEOUT,
                is_feasible=False,
                is_proven_optimal=False,
                objective_value=None,
                theoretical_bound=bound,
                optimality_gap_pct=None,
                runtime_ms=runtime_ms,
                solution=None,
                violations=["Execution exceeded instance timeout budget"],
                error_message=error_message or "TimeoutError",
            )

        if error_message is not None:
            return InstanceEvaluationOutcome(
                instance_id=instance.instance_id,
                status=SolutionStatus.EXECUTION_ERROR,
                is_feasible=False,
                is_proven_optimal=False,
                objective_value=None,
                theoretical_bound=bound,
                optimality_gap_pct=None,
                runtime_ms=runtime_ms,
                solution=None,
                violations=[error_message],
                error_message=error_message,
            )

        check = self.validate_solution(instance, solution)
        if not check.is_feasible:
            return InstanceEvaluationOutcome(
                instance_id=instance.instance_id,
                status=SolutionStatus.INFEASIBLE,
                is_feasible=False,
                is_proven_optimal=False,
                objective_value=None,
                theoretical_bound=bound,
                optimality_gap_pct=None,
                runtime_ms=runtime_ms,
                solution=None,
                violations=check.violations,
                error_message="; ".join(check.violations),
            )

        obj = float(self.compute_objective(instance, solution))
        if not math.isfinite(obj):
            return InstanceEvaluationOutcome(
                instance_id=instance.instance_id,
                status=SolutionStatus.INFEASIBLE,
                is_feasible=False,
                is_proven_optimal=False,
                objective_value=None,
                theoretical_bound=bound,
                optimality_gap_pct=None,
                runtime_ms=runtime_ms,
                solution=None,
                violations=[f"Non-finite objective value: {obj}"],
                error_message=f"Non-finite objective value: {obj}",
            )

        is_opt = False
        gap_pct: Optional[float] = None
        if bound is not None and math.isfinite(bound):
            if self.direction == OptimizationDirection.MINIMIZE:
                if obj < bound - 1e-6:
                    # Physical impossibility: solution claims better than mathematical lower bound
                    return InstanceEvaluationOutcome(
                        instance_id=instance.instance_id,
                        status=SolutionStatus.INFEASIBLE,
                        is_feasible=False,
                        is_proven_optimal=False,
                        objective_value=None,
                        theoretical_bound=bound,
                        optimality_gap_pct=None,
                        runtime_ms=runtime_ms,
                        solution=None,
                        violations=[f"Objective {obj} violates mathematical lower bound {bound}"],
                        error_message=f"Objective {obj} < lower bound {bound}",
                    )
                is_opt = abs(obj - bound) <= 1e-6
                gap_pct = ((obj - bound) / max(1e-9, abs(bound))) * 100.0
            else:
                if obj > bound + 1e-6:
                    return InstanceEvaluationOutcome(
                        instance_id=instance.instance_id,
                        status=SolutionStatus.INFEASIBLE,
                        is_feasible=False,
                        is_proven_optimal=False,
                        objective_value=None,
                        theoretical_bound=bound,
                        optimality_gap_pct=None,
                        runtime_ms=runtime_ms,
                        solution=None,
                        violations=[f"Objective {obj} violates mathematical upper bound {bound}"],
                        error_message=f"Objective {obj} > upper bound {bound}",
                    )
                is_opt = abs(bound - obj) <= 1e-6
                gap_pct = ((bound - obj) / max(1e-9, abs(bound))) * 100.0

        status = SolutionStatus.PROVEN_OPTIMAL if is_opt else SolutionStatus.FEASIBLE
        return InstanceEvaluationOutcome(
            instance_id=instance.instance_id,
            status=status,
            is_feasible=True,
            is_proven_optimal=is_opt,
            objective_value=round(obj, 6),
            theoretical_bound=round(bound, 6) if bound is not None else None,
            optimality_gap_pct=round(gap_pct, 4) if gap_pct is not None else None,
            runtime_ms=round(runtime_ms, 3),
            solution=solution,
            violations=[],
            error_message=None,
        )

    def aggregate_outcomes(
        self,
        split: SplitType,
        outcomes: List[InstanceEvaluationOutcome],
        baseline_mean_objective: Optional[float] = None,
        baseline_mean_runtime_ms: Optional[float] = None,
    ) -> AggregateEvaluationOutcome:
        total_count = len(outcomes)
        feasible_outcomes = [o for o in outcomes if o.is_feasible and o.objective_value is not None]
        feasible_count = len(feasible_outcomes)
        is_fully_feasible = (total_count > 0) and (feasible_count == total_count)
        proven_optimal_count = sum(1 for o in feasible_outcomes if o.is_proven_optimal)
        total_runtime = sum(o.runtime_ms for o in outcomes)
        mean_runtime = total_runtime / max(1, total_count)

        if not is_fully_feasible:
            failed = [o for o in outcomes if not o.is_feasible]
            first_err = failed[0].error_message if failed else "Empty dataset split"
            return AggregateEvaluationOutcome(
                split=split,
                is_fully_feasible=False,
                feasible_count=feasible_count,
                total_count=total_count,
                proven_optimal_count=proven_optimal_count,
                mean_objective=None,
                total_objective=None,
                std_objective=None,
                mean_optimality_gap_pct=None,
                total_runtime_ms=round(total_runtime, 3),
                mean_runtime_ms=round(mean_runtime, 3),
                measured_improvement_vs_baseline_pct=None,
                runtime_speedup_vs_baseline=None,
                is_proven_split_optimal=False,
                instance_outcomes=outcomes,
                failure_summary=f"Infeasible on {total_count - feasible_count}/{total_count} instances (e.g., {first_err})",
            )

        objs = [float(o.objective_value) for o in feasible_outcomes if o.objective_value is not None]
        total_obj = sum(objs)
        mean_obj = total_obj / len(objs)
        variance = sum((x - mean_obj) ** 2 for x in objs) / max(1, len(objs) - 1) if len(objs) > 1 else 0.0
        std_obj = math.sqrt(variance)

        gaps = [o.optimality_gap_pct for o in feasible_outcomes if o.optimality_gap_pct is not None]
        mean_gap = (sum(gaps) / len(gaps)) if gaps else None

        improvement_pct: Optional[float] = None
        if baseline_mean_objective is not None and abs(baseline_mean_objective) > 1e-9:
            if self.direction == OptimizationDirection.MINIMIZE:
                improvement_pct = ((baseline_mean_objective - mean_obj) / abs(baseline_mean_objective)) * 100.0
            else:
                improvement_pct = ((mean_obj - baseline_mean_objective) / abs(baseline_mean_objective)) * 100.0

        speedup: Optional[float] = None
        if baseline_mean_runtime_ms is not None and mean_runtime > 1e-6:
            speedup = baseline_mean_runtime_ms / mean_runtime

        return AggregateEvaluationOutcome(
            split=split,
            is_fully_feasible=True,
            feasible_count=feasible_count,
            total_count=total_count,
            proven_optimal_count=proven_optimal_count,
            mean_objective=round(mean_obj, 6),
            total_objective=round(total_obj, 6),
            std_objective=round(std_obj, 6),
            mean_optimality_gap_pct=round(mean_gap, 4) if mean_gap is not None else None,
            total_runtime_ms=round(total_runtime, 3),
            mean_runtime_ms=round(mean_runtime, 3),
            measured_improvement_vs_baseline_pct=round(improvement_pct, 4) if improvement_pct is not None else None,
            runtime_speedup_vs_baseline=round(speedup, 3) if speedup is not None else None,
            is_proven_split_optimal=(proven_optimal_count == total_count),
            instance_outcomes=outcomes,
            failure_summary=None,
        )


# =============================================================================
# CONCRETE DOMAIN 1: PERMUTATION FLOW-SHOP SCHEDULING (PFSP: Fm | prmu | Cmax)
# =============================================================================

def compute_pfsp_makespan(times: Sequence[Sequence[int]], perm: Sequence[int]) -> int:
    """Exact O(N * M) makespan calculation for Permutation Flow-Shop."""
    n = len(times)
    if n == 0 or len(perm) == 0:
        return 0
    m = len(times[0])
    completion = [0] * m
    for job_idx in perm:
        job_times = times[job_idx]
        completion[0] += job_times[0]
        for k in range(1, m):
            prev = completion[k - 1]
            curr = completion[k]
            completion[k] = (prev if prev > curr else curr) + job_times[k]
    return completion[-1]


def compute_taillard_lower_bound(times: Sequence[Sequence[int]]) -> int:
    """
    Taillard (1993) machine bottleneck lower bound for PFSP makespan:
    LB = max_{0 <= k < M} ( min_i sum_{l < k} p_{i,l} + sum_i p_{i,k} + min_i sum_{l > k} p_{i,l} )
     Also bounded below by max_i sum_{0 <= k < M} p_{i,k} (single-job completion lower bound).
    """
    n = len(times)
    if n == 0:
        return 0
    m = len(times[0])
    if m == 0:
        return 0

    max_machine_lb = 0
    for k in range(m):
        machine_load = sum(times[i][k] for i in range(n))
        head_min = min(sum(times[i][l] for l in range(k)) for i in range(n)) if k > 0 else 0
        tail_min = min(sum(times[i][l] for l in range(k + 1, m)) for i in range(n)) if k < m - 1 else 0
        lb_k = head_min + machine_load + tail_min
        if lb_k > max_machine_lb:
            max_machine_lb = lb_k

    max_job_lb = max(sum(times[i]) for i in range(n))
    return max(max_machine_lb, max_job_lb)


def taillard_best_insertion(
    times: Sequence[Sequence[int]],
    partial_seq: Sequence[int],
    job_to_insert: int,
    tie_break: str = "earliest_makespan",
) -> Tuple[List[int], int]:
    """
    Taillard (1990) O(k * M) accelerated insertion of `job_to_insert` into `partial_seq`.
    Returns (new_sequence, best_makespan).
    """
    k_len = len(partial_seq)
    if k_len == 0:
        cmax = sum(times[job_to_insert])
        return [job_to_insert], cmax

    m = len(times[0])
    # 1. Forward completion matrix e[r][mach]
    e = [[0] * m for _ in range(k_len)]
    for r, j_idx in enumerate(partial_seq):
        jt = times[j_idx]
        e[r][0] = (e[r - 1][0] if r > 0 else 0) + jt[0]
        for mach in range(1, m):
            prev_job = e[r - 1][mach] if r > 0 else 0
            prev_mach = e[r][mach - 1]
            e[r][mach] = (prev_job if prev_job > prev_mach else prev_mach) + jt[mach]

    # 2. Backward tail matrix q[r][mach]
    q = [[0] * m for _ in range(k_len + 1)]
    for r in range(k_len - 1, -1, -1):
        jt = times[partial_seq[r]]
        q[r][m - 1] = q[r + 1][m - 1] + jt[m - 1]
        for mach in range(m - 2, -1, -1):
            next_job = q[r + 1][mach]
            next_mach = q[r][mach + 1]
            q[r][mach] = (next_job if next_job > next_mach else next_mach) + jt[mach]

    # 3. Evaluate all k_len + 1 insertion positions in O(M) each
    best_pos = 0
    best_cmax = float("inf")
    best_idle = float("inf")
    jt_ins = times[job_to_insert]

    for pos in range(k_len + 1):
        f_vec = [0] * m
        prev_e0 = e[pos - 1][0] if pos > 0 else 0
        f_vec[0] = prev_e0 + jt_ins[0]
        idle_sum = 0
        for mach in range(1, m):
            prev_em = e[pos - 1][mach] if pos > 0 else 0
            if f_vec[mach - 1] > prev_em:
                idle_sum += f_vec[mach - 1] - prev_em
                f_vec[mach] = f_vec[mach - 1] + jt_ins[mach]
            else:
                f_vec[mach] = prev_em + jt_ins[mach]

        cmax_pos = 0
        for mach in range(m):
            val = f_vec[mach] + q[pos][mach]
            if val > cmax_pos:
                cmax_pos = val

        if cmax_pos < best_cmax:
            best_cmax = cmax_pos
            best_pos = pos
            best_idle = idle_sum
        elif cmax_pos == best_cmax:
            if tie_break == "latest_makespan":
                best_pos = pos
            elif tie_break == "min_machine_idle" and idle_sum < best_idle:
                best_pos = pos
                best_idle = idle_sum

    new_seq = list(partial_seq[:best_pos]) + [job_to_insert] + list(partial_seq[best_pos:])
    return new_seq, int(best_cmax)


def solve_pfsp_neh(times: Sequence[Sequence[int]]) -> List[int]:
    """Classical NEH (1983) constructive heuristic with Taillard acceleration."""
    n = len(times)
    if n <= 1:
        return list(range(n))
    order = sorted(range(n), key=lambda i: (-sum(times[i]), i))
    seq = [order[0]]
    for idx in range(1, n):
        seq, _ = taillard_best_insertion(times, seq, order[idx], tie_break="earliest_makespan")
    return seq


def solve_pfsp_neh_ls(times: Sequence[Sequence[int]], max_passes: int = 3) -> List[int]:
    """
    NEH-LS: Classical NEH followed by Taillard-accelerated Insertion Local Search.
    Iteratively removes each job and re-inserts it into its best position until local optimality or max_passes.
    """
    n = len(times)
    if n <= 1:
        return list(range(n))
    seq = solve_pfsp_neh(times)
    best_cmax = compute_pfsp_makespan(times, seq)

    for _ in range(max_passes):
        improved = False
        for job in list(seq):
            reduced = [j for j in seq if j != job]
            cand_seq, cand_cmax = taillard_best_insertion(times, reduced, job, tie_break="min_machine_idle")
            if cand_cmax < best_cmax:
                seq = cand_seq
                best_cmax = cand_cmax
                improved = True
        if not improved:
            break
    return seq


def solve_pfsp_palmer(times: Sequence[Sequence[int]]) -> List[int]:
    """Palmer (1965) slope index heuristic."""
    n = len(times)
    if n <= 1:
        return list(range(n))
    m = len(times[0])
    slopes = []
    for i in range(n):
        s_val = sum((2 * j - m + 1) * times[i][j] for j in range(m))
        slopes.append((-s_val, i))
    slopes.sort()
    return [i for _, i in slopes]


def solve_pfsp_cds(times: Sequence[Sequence[int]]) -> List[int]:
    """Campbell-Dudek-Smith (1970) multi-stage Johnson's Rule heuristic."""
    n = len(times)
    if n <= 1:
        return list(range(n))
    m = len(times[0])
    if m == 1:
        return list(range(n))

    best_seq: List[int] = list(range(n))
    best_cmax = compute_pfsp_makespan(times, best_seq)

    for stage in range(1, m):
        front_group = []
        back_group = []
        for i in range(n):
            p1 = sum(times[i][:stage])
            p2 = sum(times[i][m - stage:])
            if p1 <= p2:
                front_group.append((p1, i))
            else:
                back_group.append((p2, i))
        front_group.sort(key=lambda x: (x[0], x[1]))
        back_group.sort(key=lambda x: (-x[0], x[1]))
        cand_seq = [i for _, i in front_group] + [i for _, i in back_group]
        cmax = compute_pfsp_makespan(times, cand_seq)
        if cmax < best_cmax:
            best_cmax = cmax
            best_seq = cand_seq

    return best_seq


class PFSPProblem(ProblemSpecification):
    """Formal Permutation Flow-Shop Scheduling Problem (Fm | prmu | Cmax)."""
    def __init__(self, firewall: SplitFirewall, default_timeout_ms: float = 400.0):
        super().__init__(
            problem_id="pfsp_makespan",
            name="Permutation Flow-Shop Scheduling (Fm | prmu | Cmax)",
            direction=OptimizationDirection.MINIMIZE,
            firewall=firewall,
            default_timeout_ms=default_timeout_ms,
        )

    def validate_solution(self, instance: ProblemInstance, solution: Any) -> ConstraintCheckResult:
        times = instance.data.get("times", [])
        n = len(times)
        invariants = ["output_is_sequence", "length_equals_n_jobs", "elements_are_integers", "valid_bijection_0_to_n_minus_1"]
        if not isinstance(solution, (list, tuple)):
            return ConstraintCheckResult(False, [f"Expected list[int], got {type(solution).__name__}"], invariants)
        if len(solution) != n:
            return ConstraintCheckResult(False, [f"Permutation length {len(solution)} != {n} jobs"], invariants)
        try:
            ints = [int(x) for x in solution]
        except (ValueError, TypeError):
            return ConstraintCheckResult(False, ["Permutation contains non-integer job indices"], invariants)
        if set(ints) != set(range(n)):
            return ConstraintCheckResult(False, [f"Output is not a valid permutation of 0..{n-1}"], invariants)
        return ConstraintCheckResult(True, [], invariants)

    def compute_objective(self, instance: ProblemInstance, solution: Any) -> float:
        times = instance.data["times"]
        return float(compute_pfsp_makespan(times, [int(x) for x in solution]))

    def compute_theoretical_bound(self, instance: ProblemInstance) -> Optional[float]:
        times = instance.data.get("times", [])
        return float(compute_taillard_lower_bound(times))

    def get_baselines(self) -> Dict[str, Callable[[ProblemInstance], Any]]:
        return {
            "NEH": lambda inst: solve_pfsp_neh(inst.data["times"]),
            "NEH-LS": lambda inst: solve_pfsp_neh_ls(inst.data["times"]),
            "Palmer": lambda inst: solve_pfsp_palmer(inst.data["times"]),
            "CDS": lambda inst: solve_pfsp_cds(inst.data["times"]),
        }


# =============================================================================
# CONCRETE DOMAIN 2: ONLINE 1D BIN PACKING
# =============================================================================

def pack_online_stream_with_scorer(
    items: Sequence[float],
    bin_capacity: float,
    scorer_fn: Callable[[float, float, float], float],
    tolerance: float = 1e-6,
) -> List[List[float]]:
    """
    Packs arriving items online into bins using `scorer_fn(item, remaining_capacity, bin_capacity)`.
    Returns the explicit bin assignments `List[List[float]]` for independent feasibility verification.
    Raises RuntimeError on any exception or non-finite priority score.
    """
    bins: List[List[float]] = []
    remaining: List[float] = []

    for step, item in enumerate(items):
        if item <= 0 or item > bin_capacity + tolerance:
            raise ValueError(f"Invalid item weight {item} at index {step} (capacity={bin_capacity})")

        best_idx = -1
        best_score = -float("inf")
        for b_idx, rem in enumerate(remaining):
            if rem >= item - tolerance:
                score = float(scorer_fn(item, rem, bin_capacity))
                if not math.isfinite(score):
                    raise RuntimeError(f"Non-finite priority score {score} on item={item}, rem={rem}")
                if score > best_score:
                    best_score = score
                    best_idx = b_idx

        if best_idx >= 0 and best_score > -float("inf"):
            bins[best_idx].append(item)
            remaining[best_idx] = round(remaining[best_idx] - item, 8)
        else:
            bins.append([item])
            remaining.append(round(bin_capacity - item, 8))

    return bins


class OnlineBinPackingProblem(ProblemSpecification):
    """
    Formal Online 1D Bin Packing Problem.
    Objective: Minimize normalized excess ratio rho = (B - L1) / L1 (or bin count B), bounded below by 0.0 (when B == L1).
    """
    def __init__(self, firewall: SplitFirewall, bin_capacity: float = 100.0, default_timeout_ms: float = 400.0):
        super().__init__(
            problem_id="online_bin_packing_1d",
            name="Online 1D Bin Packing (L1 Excess Ratio)",
            direction=OptimizationDirection.MINIMIZE,
            firewall=firewall,
            default_timeout_ms=default_timeout_ms,
        )
        self.bin_capacity = float(bin_capacity)

    def validate_solution(self, instance: ProblemInstance, solution: Any) -> ConstraintCheckResult:
        """
        Independently verifies that `solution` (a list of bins, each a list of item weights)
        conserves all items in `instance.data['items']` and respects `bin_capacity` on every bin.
        """
        items = instance.data.get("items", [])
        cap = float(instance.data.get("bin_capacity", self.bin_capacity))
        invariants = ["bins_is_list_of_lists", "non_empty_bins", "bin_capacity_respected", "exact_item_multiset_conservation"]

        if not isinstance(solution, list):
            return ConstraintCheckResult(False, [f"Expected list of bins, got {type(solution).__name__}"], invariants)

        flattened: List[float] = []
        for b_idx, b in enumerate(solution):
            if not isinstance(b, (list, tuple)) or len(b) == 0:
                return ConstraintCheckResult(False, [f"Bin {b_idx} is empty or not a list"], invariants)
            b_sum = sum(float(x) for x in b)
            if b_sum > cap + 1e-5:
                return ConstraintCheckResult(
                    False, [f"Bin {b_idx} load {b_sum:.4f} exceeds capacity {cap:.4f}"], invariants
                )
            flattened.extend(round(float(x), 6) for x in b)

        expected_sorted = sorted(round(float(x), 6) for x in items)
        actual_sorted = sorted(flattened)
        if len(actual_sorted) != len(expected_sorted) or any(
            abs(a - b) > 1e-4 for a, b in zip(actual_sorted, expected_sorted)
        ):
            return ConstraintCheckResult(
                False,
                [f"Packed items ({len(actual_sorted)}) do not match input stream items ({len(expected_sorted)})"],
                invariants,
            )

        return ConstraintCheckResult(True, [], invariants)

    def compute_objective(self, instance: ProblemInstance, solution: Any) -> float:
        items = instance.data.get("items", [])
        cap = float(instance.data.get("bin_capacity", self.bin_capacity))
        l1 = max(1, math.ceil(sum(items) / cap))
        bins_used = len(solution)
        return (bins_used - l1) / float(l1)

    def compute_theoretical_bound(self, instance: ProblemInstance) -> Optional[float]:
        # Normalized excess ratio (B - L1) / L1 has theoretical lower bound 0.0 (achieved when B == L1)
        return 0.0

    def get_baselines(self) -> Dict[str, Callable[[ProblemInstance], Any]]:
        cap = self.bin_capacity
        return {
            "Best-Fit": lambda inst: pack_online_stream_with_scorer(
                inst.data["items"], float(inst.data.get("bin_capacity", cap)), lambda item, rem, c: -(rem - item)
            ),
            "First-Fit": lambda inst: pack_online_stream_with_scorer(
                inst.data["items"], float(inst.data.get("bin_capacity", cap)), lambda item, rem, c: 0.0
            ),
            "Worst-Fit": lambda inst: pack_online_stream_with_scorer(
                inst.data["items"], float(inst.data.get("bin_capacity", cap)), lambda item, rem, c: rem
            ),
            "Almost-Worst-Fit": lambda inst: pack_online_stream_with_scorer(
                inst.data["items"],
                float(inst.data.get("bin_capacity", cap)),
                lambda item, rem, c: (1000.0 - (rem - item)) if (rem - item) < 0.05 * c else (rem * 0.5),
            ),
        }


# =============================================================================
# CONCRETE DOMAIN 3: VERTEX GRAPH COLORING
# =============================================================================

def solve_gc_dsatur(adj: Sequence[Sequence[int]]) -> List[int]:
    """Brélaz (1979) DSATUR exact/heuristic vertex graph coloring."""
    n = len(adj)
    if n == 0:
        return []
    colors = [-1] * n
    degrees = [len(adj[u]) for u in range(n)]
    neighbor_colors: List[set[int]] = [set() for _ in range(n)]
    uncolored = set(range(n))

    while uncolored:
        # Select vertex with max saturation degree, tie-break by max degree, then lowest index
        best_u = max(uncolored, key=lambda u: (len(neighbor_colors[u]), degrees[u], -u))
        used = neighbor_colors[best_u]
        c = 0
        while c in used:
            c += 1
        colors[best_u] = c
        uncolored.remove(best_u)
        for v in adj[best_u]:
            if v in uncolored:
                neighbor_colors[v].add(c)
    return colors


def solve_gc_smallest_last(adj: Sequence[Sequence[int]]) -> List[int]:
    """Matula, Marble, Isaacson (1972) Smallest-Last ordering + greedy coloring."""
    n = len(adj)
    if n == 0:
        return []
    rem_deg = [len(adj[u]) for u in range(n)]
    active = set(range(n))
    peel_order: List[int] = []

    while active:
        u = min(active, key=lambda v: (rem_deg[v], v))
        peel_order.append(u)
        active.remove(u)
        for nb in adj[u]:
            if nb in active:
                rem_deg[nb] -= 1

    colors = [-1] * n
    for u in reversed(peel_order):
        used = {colors[nb] for nb in adj[u] if colors[nb] >= 0}
        c = 0
        while c in used:
            c += 1
        colors[u] = c
    return colors


class GraphColoringProblem(ProblemSpecification):
    """Formal Vertex Graph Coloring Problem (minimize chromatic number)."""
    def __init__(self, firewall: SplitFirewall, default_timeout_ms: float = 400.0):
        super().__init__(
            problem_id="vertex_graph_coloring",
            name="Vertex Graph Coloring (Chromatic Minimization)",
            direction=OptimizationDirection.MINIMIZE,
            firewall=firewall,
            default_timeout_ms=default_timeout_ms,
        )

    def validate_solution(self, instance: ProblemInstance, solution: Any) -> ConstraintCheckResult:
        adj = instance.data.get("adj", [])
        n = len(adj)
        invariants = ["output_is_list", "length_equals_vertices", "non_negative_integers", "no_monochromatic_edges"]
        if not isinstance(solution, (list, tuple)):
            return ConstraintCheckResult(False, [f"Expected list[int], got {type(solution).__name__}"], invariants)
        if len(solution) != n:
            return ConstraintCheckResult(False, [f"Color assignment length {len(solution)} != {n} vertices"], invariants)
        try:
            cols = [int(c) for c in solution]
        except (ValueError, TypeError):
            return ConstraintCheckResult(False, ["Colors must be integers"], invariants)
        if any(c < 0 for c in cols):
            return ConstraintCheckResult(False, ["Colors must be non-negative integers"], invariants)

        for u in range(n):
            cu = cols[u]
            for v in adj[u]:
                if u < v and cu == cols[v]:
                    return ConstraintCheckResult(
                        False, [f"Adjacent vertices ({u}, {v}) share color {cu}"], invariants
                    )
        return ConstraintCheckResult(True, [], invariants)

    def compute_objective(self, instance: ProblemInstance, solution: Any) -> float:
        if not solution:
            return 0.0
        return float(len(set(int(c) for c in solution)))

    def compute_theoretical_bound(self, instance: ProblemInstance) -> Optional[float]:
        adj = instance.data.get("adj", [])
        n = len(adj)
        if n == 0:
            return 0.0
        has_edge = any(len(neighbors) > 0 for neighbors in adj)
        if not has_edge:
            return 1.0
        # Check for triangle (K3) lower bound
        adj_sets = [set(neighbors) for neighbors in adj]
        for u in range(n):
            for v in adj[u]:
                if v > u and (adj_sets[u] & adj_sets[v]):
                    return 3.0
        return 2.0

    def get_baselines(self) -> Dict[str, Callable[[ProblemInstance], Any]]:
        return {
            "DSATUR": lambda inst: solve_gc_dsatur(inst.data["adj"]),
            "Smallest-Last": lambda inst: solve_gc_smallest_last(inst.data["adj"]),
        }
