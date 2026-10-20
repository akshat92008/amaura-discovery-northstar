"""
North BlueStar — Evidence Store & Empirical Learning Engine (Capability F)
==========================================================================
Maintains an auditable, SHA-256 hash-chained evidence store of every candidate evaluation,
and extracts structured empirical knowledge to guide future search decisions:
1. Full candidate identity (structural_hash, canonical_hash, behavioral_hash), method_id,
   strategy_id, parent lineage, split, feasibility, objective score, optimality gap, runtime, and failure category.
2. Marginal Operator Contribution Analyzer: estimates the empirical objective delta and win-rate
   of individual declarative operators (e.g., `insertion_ls`, `vnd_insert_swap`, `min_machine_idle`,
   `bottleneck_slack`) from observed evidence.
3. Strategy Thompson / UCB Empirical Posterior: updates strategy selection weights based on
   verified novelty rate, feasibility rate, and objective improvement rate per unit of runtime budget.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from north_bluestar.candidates import CandidateKind, CandidateSpec
from north_bluestar.execution import FailureCategory, VerificationReport
from north_bluestar.problem import OptimizationDirection, SplitType


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable, hash-chained audit record of a single candidate evaluation event."""
    sequence_index: int
    candidate_id: str
    kind: str
    problem_id: str
    method_id: str
    strategy_id: str
    split: str
    generation: int
    parent_ids: Tuple[str, ...]
    structural_hash: str
    canonical_hash: str
    behavioral_hash: Optional[str]
    payload: Dict[str, Any]
    is_feasible: bool
    is_proven_optimal: bool
    mean_objective: Optional[float]
    std_objective: Optional[float]
    mean_optimality_gap_pct: Optional[float]
    total_runtime_ms: float
    mean_runtime_ms: float
    measured_improvement_vs_baseline_pct: Optional[float]
    failure_category: str
    failure_summary: Optional[str]
    worker_killed_count: int
    is_repeatable: bool
    prev_record_hash: str
    record_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_index": self.sequence_index,
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "problem_id": self.problem_id,
            "method_id": self.method_id,
            "strategy_id": self.strategy_id,
            "split": self.split,
            "generation": self.generation,
            "parent_ids": list(self.parent_ids),
            "structural_hash": self.structural_hash,
            "canonical_hash": self.canonical_hash,
            "behavioral_hash": self.behavioral_hash,
            "payload": self.payload,
            "is_feasible": self.is_feasible,
            "is_proven_optimal": self.is_proven_optimal,
            "mean_objective": self.mean_objective,
            "std_objective": self.std_objective,
            "mean_optimality_gap_pct": self.mean_optimality_gap_pct,
            "total_runtime_ms": self.total_runtime_ms,
            "mean_runtime_ms": self.mean_runtime_ms,
            "measured_improvement_vs_baseline_pct": self.measured_improvement_vs_baseline_pct,
            "failure_category": self.failure_category,
            "failure_summary": self.failure_summary,
            "worker_killed_count": self.worker_killed_count,
            "is_repeatable": self.is_repeatable,
            "prev_record_hash": self.prev_record_hash,
            "record_hash": self.record_hash,
        }


class EvidenceStore:
    """
    Append-only, cryptographically hash-chained evidence store with empirical learning analytics.
    """

    def __init__(self, direction: OptimizationDirection = OptimizationDirection.MINIMIZE) -> None:
        self.direction = direction
        self.records: List[EvidenceRecord] = []
        self._seen_structural_hashes: set[str] = set()
        self._seen_canonical_hashes: set[str] = set()
        self._seen_behavioral_hashes: set[str] = set()
        self.duplicate_rejections_structural: int = 0
        self.duplicate_rejections_canonical: int = 0
        self.duplicate_rejections_behavioral: int = 0

    def is_duplicate(
        self, candidate: CandidateSpec, enforce_behavioral_novelty: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks whether `candidate` is a structural, semantic-canonical, or behavioral duplicate
        of a previously evaluated candidate on DEVELOPMENT.
        """
        if candidate.structural_hash in self._seen_structural_hashes:
            self.duplicate_rejections_structural += 1
            return True, f"duplicate_structural_hash:{candidate.structural_hash}"
        if candidate.canonical_hash in self._seen_canonical_hashes:
            self.duplicate_rejections_canonical += 1
            return True, f"duplicate_canonical_hash:{candidate.canonical_hash}"
        if (
            enforce_behavioral_novelty
            and candidate.behavioral_hash is not None
            and candidate.behavioral_hash in self._seen_behavioral_hashes
        ):
            self.duplicate_rejections_behavioral += 1
            return True, f"duplicate_behavioral_hash:{candidate.behavioral_hash}"
        return False, None

    def append(self, candidate: CandidateSpec, report: VerificationReport) -> EvidenceRecord:
        seq_idx = len(self.records)
        prev_hash = self.records[-1].record_hash if self.records else "0" * 64
        out = report.outcome

        if report.split == SplitType.DEVELOPMENT:
            self._seen_structural_hashes.add(candidate.structural_hash)
            self._seen_canonical_hashes.add(candidate.canonical_hash)
            if candidate.behavioral_hash is not None:
                self._seen_behavioral_hashes.add(candidate.behavioral_hash)

        body = {
            "sequence_index": seq_idx,
            "candidate_id": candidate.candidate_id,
            "kind": candidate.kind.value,
            "problem_id": candidate.problem_id,
            "method_id": candidate.method_id,
            "strategy_id": candidate.strategy_id,
            "split": report.split.value,
            "generation": candidate.generation,
            "parent_ids": list(candidate.parent_ids),
            "structural_hash": candidate.structural_hash,
            "canonical_hash": candidate.canonical_hash,
            "behavioral_hash": candidate.behavioral_hash,
            "payload": candidate.payload,
            "is_feasible": out.is_fully_feasible,
            "is_proven_optimal": out.is_proven_split_optimal,
            "mean_objective": out.mean_objective,
            "std_objective": out.std_objective,
            "mean_optimality_gap_pct": out.mean_optimality_gap_pct,
            "total_runtime_ms": out.total_runtime_ms,
            "mean_runtime_ms": out.mean_runtime_ms,
            "measured_improvement_vs_baseline_pct": out.measured_improvement_vs_baseline_pct,
            "failure_category": report.failure_category.value,
            "failure_summary": out.failure_summary,
            "worker_killed_count": report.worker_killed_count,
            "is_repeatable": report.is_repeatable,
            "prev_record_hash": prev_hash,
        }
        rec_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()

        record = EvidenceRecord(
            sequence_index=seq_idx,
            candidate_id=candidate.candidate_id,
            kind=candidate.kind.value,
            problem_id=candidate.problem_id,
            method_id=candidate.method_id,
            strategy_id=candidate.strategy_id,
            split=report.split.value,
            generation=candidate.generation,
            parent_ids=tuple(candidate.parent_ids),
            structural_hash=candidate.structural_hash,
            canonical_hash=candidate.canonical_hash,
            behavioral_hash=candidate.behavioral_hash,
            payload=dict(candidate.payload),
            is_feasible=out.is_fully_feasible,
            is_proven_optimal=out.is_proven_split_optimal,
            mean_objective=out.mean_objective,
            std_objective=out.std_objective,
            mean_optimality_gap_pct=out.mean_optimality_gap_pct,
            total_runtime_ms=out.total_runtime_ms,
            mean_runtime_ms=out.mean_runtime_ms,
            measured_improvement_vs_baseline_pct=out.measured_improvement_vs_baseline_pct,
            failure_category=report.failure_category.value,
            failure_summary=out.failure_summary,
            worker_killed_count=report.worker_killed_count,
            is_repeatable=report.is_repeatable,
            prev_record_hash=prev_hash,
            record_hash=rec_hash,
        )
        self.records.append(record)
        return record

    def verify_hash_chain(self) -> bool:
        """Verifies cryptographic integrity of the entire append-only evidence chain."""
        prev = "0" * 64
        for idx, rec in enumerate(self.records):
            if rec.sequence_index != idx or rec.prev_record_hash != prev:
                return False
            d = rec.to_dict()
            claimed = d.pop("record_hash")
            recomputed = hashlib.sha256(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()
            if claimed != recomputed:
                return False
            prev = claimed
        return True

    def get_feasible_records(self, split: SplitType = SplitType.DEVELOPMENT) -> List[EvidenceRecord]:
        valid = [
            r for r in self.records
            if r.split == split.value and r.is_feasible and r.is_repeatable and r.mean_objective is not None
        ]
        reverse = self.direction == OptimizationDirection.MAXIMIZE
        return sorted(
            valid,
            key=lambda r: (
                float(r.mean_objective) * (-1.0 if reverse else 1.0),
                r.mean_runtime_ms,
                r.candidate_id,
            ),
        )

    def get_top_k(self, k: int = 5, split: SplitType = SplitType.DEVELOPMENT) -> List[EvidenceRecord]:
        return self.get_feasible_records(split=split)[:k]

    def get_diversity_summary(self, split: SplitType = SplitType.DEVELOPMENT) -> Dict[str, Any]:
        split_recs = [r for r in self.records if r.split == split.value]
        feasible_recs = [r for r in split_recs if r.is_feasible]
        unique_struct = len({r.structural_hash for r in feasible_recs})
        unique_canon = len({r.canonical_hash for r in feasible_recs})
        unique_behav = len({r.behavioral_hash for r in feasible_recs if r.behavioral_hash is not None})
        n_feas = len(feasible_recs)
        return {
            "total_evaluated": len(split_recs),
            "feasible_count": n_feas,
            "unique_structural_hashes": unique_struct,
            "unique_canonical_hashes": unique_canon,
            "unique_behavioral_phenotypes": unique_behav,
            "behavioral_diversity_ratio": round(unique_behav / max(1, n_feas), 4),
            "duplicate_rejections": {
                "structural": self.duplicate_rejections_structural,
                "canonical": self.duplicate_rejections_canonical,
                "behavioral": self.duplicate_rejections_behavioral,
            },
        }

    def compute_marginal_operator_effects(
        self, split: SplitType = SplitType.DEVELOPMENT
    ) -> Dict[str, Dict[str, float]]:
        """
        Empirical Learning Mechanism 1:
        Computes the marginal objective improvement (relative to global mean objective)
        for each parameter value in declarative candidate payloads.
        Used by `SurrogateUCBStrategy` and `OperatorRecombinationStrategy` to prioritize
        operators backed by empirical evidence.
        """
        feasible = self.get_feasible_records(split=split)
        if not feasible:
            return {}

        all_objs = [float(r.mean_objective) for r in feasible if r.mean_objective is not None]
        global_mean = sum(all_objs) / len(all_objs)

        buckets: Dict[str, Dict[str, List[float]]] = {}
        for r in feasible:
            if r.mean_objective is None:
                continue
            for param_name, param_val in r.payload.items():
                if param_name in ("code", "raw_variant_tag"):
                    continue
                key_val = str(param_val)
                buckets.setdefault(param_name, {}).setdefault(key_val, []).append(float(r.mean_objective))

        effects: Dict[str, Dict[str, float]] = {}
        for param_name, val_map in buckets.items():
            effects[param_name] = {}
            for val_str, scores in val_map.items():
                mean_v = sum(scores) / len(scores)
                # Positive marginal utility means BETTER than global mean
                if self.direction == OptimizationDirection.MINIMIZE:
                    utility = global_mean - mean_v
                else:
                    utility = mean_v - global_mean
                effects[param_name][val_str] = round(utility, 6)
        return effects

    def compute_strategy_posteriors(self) -> Dict[str, Dict[str, float]]:
        """
        Empirical Learning Mechanism 2:
        Computes per-strategy empirical performance metrics:
        - attempts
        - feasibility_rate
        - behavioral_novelty_rate
        - best_objective
        - mean_improvement_pct
        - ucb_score (used by the SearchController to allocate remaining budget dynamically)
        """
        dev_recs = [r for r in self.records if r.split == SplitType.DEVELOPMENT.value]
        total_n = max(1, len(dev_recs))
        by_strat: Dict[str, List[EvidenceRecord]] = {}
        for r in dev_recs:
            by_strat.setdefault(r.strategy_id, []).append(r)

        stats: Dict[str, Dict[str, float]] = {}
        for strat_id, recs in by_strat.items():
            n_s = len(recs)
            feas = [r for r in recs if r.is_feasible and r.mean_objective is not None]
            feas_rate = len(feas) / float(n_s)
            unique_b = len({r.behavioral_hash for r in feas if r.behavioral_hash})
            novelty_rate = unique_b / float(max(1, len(feas)))
            imps = [
                float(r.measured_improvement_vs_baseline_pct)
                for r in feas
                if r.measured_improvement_vs_baseline_pct is not None
            ]
            max_imp = max(imps) if imps else 0.0
            mean_imp = (sum(imps) / len(imps)) if imps else 0.0
            # Empirical reward combines verified improvement over baseline, feasibility, and behavioral diversity
            reward = (0.50 * max(0.0, max_imp) + 0.30 * (feas_rate * 10.0) + 0.20 * (novelty_rate * 10.0))
            exploration_bonus = math.sqrt(2.0 * math.log(total_n + 1.0) / float(n_s))
            stats[strat_id] = {
                "attempts": float(n_s),
                "feasibility_rate": round(feas_rate, 4),
                "behavioral_novelty_rate": round(novelty_rate, 4),
                "max_improvement_pct": round(max_imp, 4),
                "mean_improvement_pct": round(mean_imp, 4),
                "ucb_score": round(reward + 2.5 * exploration_bonus, 4),
            }
        return stats
