"""
Discovery Kernel v0.1: Deterministic Experiment Controller
==========================================================
Coordinates development-phase method selection, enforces evaluation budgets,
guarantees immutable selection freezing, and executes strictly isolated final
evaluation against holdout benchmarks.
"""

from dataclasses import dataclass, field, asdict
import hashlib
import json
import os
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

from discovery_kernel.problem_spec import ProblemSpecification, ObjectiveDirection
from discovery_kernel.method_adapter import MethodAdapter, ExecutionStatus
from discovery_kernel.execution import ExecutionSupervisor, EvaluationResult
from discovery_kernel.evidence_store import EvidenceStore


class ControllerStateError(RuntimeError):
    """Raised when an operation violates controller phase sequencing."""
    pass


class BudgetExhaustedError(RuntimeError):
    """Raised when development evaluation exceeds defined resource limits."""
    pass


@dataclass(frozen=True)
class FrozenSelection:
    """
    Immutable representation of a frozen method selection.
    Must be created and persisted before any access to holdout evaluation data.
    """
    champion_method_id: str
    champion_version: str
    champion_dev_score: float
    objective_metric: str
    objective_direction: str
    problem_spec_fingerprint: str
    dev_rankings: List[Dict[str, Any]]
    selection_timestamp: str
    dev_evidence_hash: str
    is_frozen: bool = True


@dataclass
class FinalEvaluationReport:
    """Outcome of holdout benchmark evaluation on frozen selection."""
    champion_method_id: str
    champion_version: str
    champion_eval_score: float
    baseline_eval_scores: Dict[str, float]
    relative_gap: float
    beats_baseline: bool
    instance_scores: List[float]
    eval_instance_count: int
    valid_instance_count: int
    all_instances_valid: bool
    matched_instance_count: int
    total_runtime_ms: float
    evaluation_timestamp: str
    matched_champion_score: Optional[float] = None
    matched_baseline_score: Optional[float] = None
    matched_relative_gap: Optional[float] = None
    per_instance_details: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "COMPLETED"


class DeterministicController:
    """
    Deterministic method comparison and holdout-isolated evaluation controller.
    Enforces the two-phase workflow:
    Phase 1 (Development): compare candidate methods, select champion, freeze selection.
    Phase 2 (Confirmatory): evaluate frozen selection on holdout benchmark.
    """
    def __init__(
        self,
        problem_spec: ProblemSpecification,
        evidence_store: EvidenceStore,
        evaluator_fn: Callable[[Any, Any], float],
        base_dir: Optional[str] = None,
        supervisor: Optional[ExecutionSupervisor] = None
    ):
        self.problem_spec = problem_spec
        self.evidence_store = evidence_store
        self.evaluator_fn = evaluator_fn
        self.base_dir = base_dir

        # Validate spec on initialization
        self.spec_fingerprint = self.problem_spec.validate(
            verify_data_files=True,
            base_dir=self.base_dir
        )

        timeout = self.problem_spec.resource_limits.max_runtime_sec_per_instance
        self.supervisor = supervisor or ExecutionSupervisor(timeout_sec=timeout)

        self.phase = "INITIALIZED"
        self._frozen_selection: Optional[FrozenSelection] = None

    def _resolve_path(self, rel_or_abs: str) -> str:
        if self.base_dir and not os.path.isabs(rel_or_abs):
            return os.path.join(self.base_dir, rel_or_abs)
        return rel_or_abs

    def _load_instances(self, filepath: str) -> List[Dict[str, Any]]:
        resolved = self._resolve_path(filepath)
        with open(resolved, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    @staticmethod
    def _extract_instance_id(inst: Any, idx: int, prefix: str = "inst") -> str:
        """Extracts consistent instance ID regardless of domain schema."""
        if isinstance(inst, dict):
            if "id" in inst and inst["id"] is not None:
                return str(inst["id"])
            if "stream_id" in inst and inst["stream_id"] is not None:
                return f"stream_{inst['stream_id']}"
        return f"{prefix}_{idx:04d}"

    def run_development_phase(
        self,
        methods: List[MethodAdapter],
        instance_limit: Optional[int] = None
    ) -> FrozenSelection:
        """
        Executes Phase 1: Evaluates candidate methods strictly on development instances,
        compares objective scores and validity, selects champion, and freezes selection.
        """
        if self.phase != "INITIALIZED":
            raise ControllerStateError(
                f"Cannot start development phase in state '{self.phase}'. Must be 'INITIALIZED'."
            )

        self.phase = "DEVELOPMENT"
        dev_instances = self._load_instances(self.problem_spec.development_dataset.file_path)
        if instance_limit is not None and instance_limit > 0:
            dev_instances = dev_instances[:instance_limit]

        max_evals = self.problem_spec.resource_limits.max_evaluations
        max_total_sec = self.problem_spec.resource_limits.max_total_runtime_sec
        t_phase_start = time.perf_counter()

        eval_count = 0
        method_stats: Dict[str, Dict[str, Any]] = {}

        for method in methods:
            mid = method.method_id
            method_stats[mid] = {
                "method_id": mid,
                "version": method.version,
                "scores": [],
                "valid_count": 0,
                "invalid_count": 0,
                "timeout_count": 0,
                "exception_count": 0,
                "total_runtime_ms": 0.0,
                "validation_errors": []
            }

            for idx, inst in enumerate(dev_instances):
                inst_id = self._extract_instance_id(inst, idx, "dev")
                inst_fp = hashlib.sha256(json.dumps(inst, sort_keys=True).encode()).hexdigest()[:16]

                # Resource budget check
                if eval_count >= max_evals:
                    raise BudgetExhaustedError(
                        f"Evaluation budget reached ({max_evals} evaluations). Halting development phase."
                    )
                if (time.perf_counter() - t_phase_start) > max_total_sec:
                    raise BudgetExhaustedError(
                        f"Total runtime limit reached ({max_total_sec}s). Halting development phase."
                    )

                eval_res = self.supervisor.execute_and_evaluate(
                    adapter=method,
                    instance=inst,
                    instance_id=inst_id,
                    evaluator_fn=self.evaluator_fn,
                    constraints=self.problem_spec.constraints,
                    objective_metric=self.problem_spec.objective_metric
                )
                eval_count += 1

                # Log event to evidence store
                self.evidence_store.log_evaluation(
                    phase="development",
                    problem_id=self.problem_spec.problem_id,
                    spec_sha256=self.spec_fingerprint,
                    method_id=method.method_id,
                    method_version=method.version,
                    instance_id=inst_id,
                    instance_fingerprint=inst_fp,
                    status=eval_res.status.value,
                    is_valid=eval_res.is_valid,
                    objective_metric=eval_res.objective_metric,
                    objective_score=eval_res.objective_score,
                    runtime_ms=eval_res.runtime_ms,
                    validation_errors=eval_res.validation_errors,
                    error_message=eval_res.error_message
                )

                s = method_stats[mid]
                s["total_runtime_ms"] += eval_res.runtime_ms
                if eval_res.is_valid and eval_res.objective_score is not None:
                    s["valid_count"] += 1
                    s["scores"].append(eval_res.objective_score)
                else:
                    s["invalid_count"] += 1
                    if eval_res.status == ExecutionStatus.TIMEOUT:
                        s["timeout_count"] += 1
                    elif eval_res.status == ExecutionStatus.EXCEPTION:
                        s["exception_count"] += 1
                    if eval_res.validation_errors:
                        s["validation_errors"].extend(eval_res.validation_errors)

        # Rank candidates
        rankings = []
        num_instances = len(dev_instances)
        for mid, s in method_stats.items():
            is_fully_valid = (s["valid_count"] == num_instances and s["invalid_count"] == 0)
            mean_score = sum(s["scores"]) / len(s["scores"]) if s["scores"] else None
            rankings.append({
                "method_id": mid,
                "version": s["version"],
                "is_fully_valid": is_fully_valid,
                "valid_count": s["valid_count"],
                "total_count": num_instances,
                "mean_score": round(mean_score, 4) if mean_score is not None else None,
                "total_runtime_ms": round(s["total_runtime_ms"], 2),
                "timeout_count": s["timeout_count"],
                "exception_count": s["exception_count"],
                "validation_errors": s["validation_errors"][:5]
            })

        # Sorting rule:
        # 1. Fully valid methods beat invalid/failing methods (disqualification of invalid candidates)
        # 2. Objective direction: MINIMIZE (lower is better) or MAXIMIZE (higher is better)
        # 3. Tie breaker: total runtime (faster is better)
        # 4. Deterministic tie breaker: method_id
        direction = self.problem_spec.objective_direction

        def sort_key(item):
            valid_rank = 0 if item["is_fully_valid"] else 1
            score = item["mean_score"]
            if score is None:
                score_rank = float("inf")
            elif direction == ObjectiveDirection.MINIMIZE:
                score_rank = score
            else:
                score_rank = -score
            # Deterministic tie-breaking: strictly method_id. Never use runtime_ms for ranking.
            return (valid_rank, score_rank, item["method_id"])

        rankings.sort(key=sort_key)

        champion_item = rankings[0] if rankings else None
        if not champion_item or not champion_item["is_fully_valid"]:
            champion_id = "NONE"
            champion_version = "0.0.0"
            champion_score = float("inf") if direction == ObjectiveDirection.MINIMIZE else float("-inf")
        else:
            champion_id = champion_item["method_id"]
            champion_version = champion_item["version"]
            champion_score = champion_item["mean_score"]

        # Compute hash of development evidence
        evidence_str = json.dumps(rankings, sort_keys=True)
        dev_evidence_hash = hashlib.sha256(evidence_str.encode()).hexdigest()

        frozen = FrozenSelection(
            champion_method_id=champion_id,
            champion_version=champion_version,
            champion_dev_score=champion_score,
            objective_metric=self.problem_spec.objective_metric,
            objective_direction=direction.value,
            problem_spec_fingerprint=self.spec_fingerprint,
            dev_rankings=rankings,
            selection_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            dev_evidence_hash=dev_evidence_hash
        )

        # Record dev summary in Evidence Store
        dev_summary = {
            "experiment_id": self.problem_spec.experiment_id,
            "problem_id": self.problem_spec.problem_id,
            "spec_fingerprint": self.spec_fingerprint,
            "objective_direction": direction.value,
            "objective_metric": self.problem_spec.objective_metric,
            "champion_method_id": champion_id,
            "champion_version": champion_version,
            "champion_dev_score": champion_score,
            "dev_instances_evaluated": num_instances,
            "total_evaluations": eval_count,
            "selection_frozen_at": frozen.selection_timestamp,
            "rankings": rankings
        }
        self.evidence_store.record_selection(dev_summary)

        self._frozen_selection = frozen
        self.phase = "SELECTION_FROZEN"
        return frozen

    def run_final_evaluation_phase(
        self,
        frozen_selection: FrozenSelection,
        champion_adapter: MethodAdapter,
        baseline_adapters: List[MethodAdapter],
        instance_limit: Optional[int] = None
    ) -> FinalEvaluationReport:
        """
        Executes Phase 2: Confirmatory evaluation on unsealed holdout benchmark.
        Strictly requires frozen selection and verified state.
        """
        if self.phase != "SELECTION_FROZEN":
            raise ControllerStateError(
                f"Cannot execute final evaluation in state '{self.phase}'. Selection must be frozen first."
            )

        if not frozen_selection.is_frozen:
            raise ControllerStateError("Provided selection is not frozen.")

        if frozen_selection.champion_method_id != champion_adapter.method_id:
            raise ControllerStateError(
                f"Champion adapter method_id '{champion_adapter.method_id}' does not match "
                f"frozen champion '{frozen_selection.champion_method_id}'"
            )

        if frozen_selection.problem_spec_fingerprint != self.spec_fingerprint:
            raise ControllerStateError(
                "Frozen selection problem specification fingerprint does not match controller spec."
            )

        self.phase = "FINAL_EVALUATION"
        eval_instances = self._load_instances(self.problem_spec.evaluation_dataset.file_path)
        if instance_limit is not None and instance_limit > 0:
            eval_instances = eval_instances[:instance_limit]

        # 1. Evaluate Champion
        # Track per-instance results for matched comparison
        champ_res_map: Dict[str, EvaluationResult] = {}
        champ_scores: List[float] = []
        champ_runtime_ms = 0.0

        for idx, inst in enumerate(eval_instances):
            inst_id = self._extract_instance_id(inst, idx, "eval")
            inst_fp = hashlib.sha256(json.dumps(inst, sort_keys=True).encode()).hexdigest()[:16]

            eval_res = self.supervisor.execute_and_evaluate(
                adapter=champion_adapter,
                instance=inst,
                instance_id=inst_id,
                evaluator_fn=self.evaluator_fn,
                constraints=self.problem_spec.constraints,
                objective_metric=self.problem_spec.objective_metric
            )
            champ_res_map[inst_id] = eval_res
            self.evidence_store.log_evaluation(
                phase="final_evaluation",
                problem_id=self.problem_spec.problem_id,
                spec_sha256=self.spec_fingerprint,
                method_id=champion_adapter.method_id,
                method_version=champion_adapter.version,
                instance_id=inst_id,
                instance_fingerprint=inst_fp,
                status=eval_res.status.value,
                is_valid=eval_res.is_valid,
                objective_metric=eval_res.objective_metric,
                objective_score=eval_res.objective_score,
                runtime_ms=eval_res.runtime_ms,
                validation_errors=eval_res.validation_errors,
                error_message=eval_res.error_message
            )
            champ_runtime_ms += eval_res.runtime_ms
            if eval_res.is_valid and eval_res.objective_score is not None:
                champ_scores.append(eval_res.objective_score)

        champ_mean_score = sum(champ_scores) / len(champ_scores) if champ_scores else float("inf")

        # 2. Evaluate Baselines
        baseline_res_map: Dict[str, Dict[str, EvaluationResult]] = {}
        baseline_scores: Dict[str, float] = {}

        for b_adapter in baseline_adapters:
            b_id = b_adapter.method_id
            baseline_res_map[b_id] = {}
            b_scores: List[float] = []

            for idx, inst in enumerate(eval_instances):
                inst_id = self._extract_instance_id(inst, idx, "eval")
                inst_fp = hashlib.sha256(json.dumps(inst, sort_keys=True).encode()).hexdigest()[:16]

                eval_res = self.supervisor.execute_and_evaluate(
                    adapter=b_adapter,
                    instance=inst,
                    instance_id=inst_id,
                    evaluator_fn=self.evaluator_fn,
                    constraints=self.problem_spec.constraints,
                    objective_metric=self.problem_spec.objective_metric
                )
                baseline_res_map[b_id][inst_id] = eval_res
                self.evidence_store.log_evaluation(
                    phase="final_evaluation",
                    problem_id=self.problem_spec.problem_id,
                    spec_sha256=self.spec_fingerprint,
                    method_id=b_adapter.method_id,
                    method_version=b_adapter.version,
                    instance_id=inst_id,
                    instance_fingerprint=inst_fp,
                    status=eval_res.status.value,
                    is_valid=eval_res.is_valid,
                    objective_metric=eval_res.objective_metric,
                    objective_score=eval_res.objective_score,
                    runtime_ms=eval_res.runtime_ms,
                    validation_errors=eval_res.validation_errors,
                    error_message=eval_res.error_message
                )
                if eval_res.is_valid and eval_res.objective_score is not None:
                    b_scores.append(eval_res.objective_score)

            b_mean = sum(b_scores) / len(b_scores) if b_scores else float("inf")
            baseline_scores[b_id] = round(b_mean, 4)

        # 3. Compute matched instance comparison
        primary_b_id = baseline_adapters[0].method_id if baseline_adapters else None
        primary_b_map = baseline_res_map.get(primary_b_id, {}) if primary_b_id else {}

        matched_champ_scores: List[float] = []
        matched_base_scores: List[float] = []
        per_instance_details: List[Dict[str, Any]] = []

        for idx, inst in enumerate(eval_instances):
            inst_id = self._extract_instance_id(inst, idx, "eval")
            c_res = champ_res_map.get(inst_id)
            b_res = primary_b_map.get(inst_id)

            inst_detail = {
                "instance_id": inst_id,
                "champion_status": c_res.status.value if c_res else "NOT_RUN",
                "champion_is_valid": c_res.is_valid if c_res else False,
                "champion_score": c_res.objective_score if c_res else None,
                "champion_runtime_ms": round(c_res.runtime_ms, 2) if c_res else 0.0,
                "primary_baseline_score": b_res.objective_score if b_res else None,
                "primary_baseline_status": b_res.status.value if b_res else "NOT_RUN"
            }
            per_instance_details.append(inst_detail)

            if (c_res and c_res.is_valid and c_res.objective_score is not None and
                b_res and b_res.is_valid and b_res.objective_score is not None):
                matched_champ_scores.append(c_res.objective_score)
                matched_base_scores.append(b_res.objective_score)

        direction = self.problem_spec.objective_direction
        num_eval = len(eval_instances)
        num_valid = len(champ_scores)
        all_valid = bool(num_valid == num_eval)

        # Overall relative gap
        primary_baseline_score = baseline_scores.get(primary_b_id, champ_mean_score) if primary_b_id else champ_mean_score
        if primary_baseline_score > 0:
            rel_gap = (champ_mean_score - primary_baseline_score) / primary_baseline_score
        else:
            rel_gap = 0.0

        if direction == ObjectiveDirection.MINIMIZE:
            beats_baseline = bool(champ_mean_score < primary_baseline_score - 1e-9)
        else:
            beats_baseline = bool(champ_mean_score > primary_baseline_score + 1e-9)

        # Matched relative gap
        if matched_champ_scores and matched_base_scores:
            m_champ_mean = sum(matched_champ_scores) / len(matched_champ_scores)
            m_base_mean = sum(matched_base_scores) / len(matched_base_scores)
            m_gap = (m_champ_mean - m_base_mean) / m_base_mean if m_base_mean > 0 else 0.0
        else:
            m_champ_mean = None
            m_base_mean = None
            m_gap = None

        final_report = FinalEvaluationReport(
            champion_method_id=champion_adapter.method_id,
            champion_version=champion_adapter.version,
            champion_eval_score=round(champ_mean_score, 4),
            baseline_eval_scores=baseline_scores,
            relative_gap=round(rel_gap, 6),
            beats_baseline=beats_baseline,
            instance_scores=[round(s, 4) for s in champ_scores],
            eval_instance_count=num_eval,
            valid_instance_count=num_valid,
            all_instances_valid=all_valid,
            matched_instance_count=len(matched_champ_scores),
            matched_champion_score=round(m_champ_mean, 4) if m_champ_mean is not None else None,
            matched_baseline_score=round(m_base_mean, 4) if m_base_mean is not None else None,
            matched_relative_gap=round(m_gap, 6) if m_gap is not None else None,
            total_runtime_ms=round(champ_runtime_ms, 2),
            evaluation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            per_instance_details=per_instance_details
        )

        self.evidence_store.record_final_evaluation(asdict(final_report))
        self.evidence_store.generate_manifest()

        self.phase = "FINAL_EVALUATION_COMPLETE"
        return final_report
