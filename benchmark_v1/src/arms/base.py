"""
Base Classes and Interfaces for Search Strategy Arms
===================================================
Defines the standard representation for candidates, trajectory accounting, and search arms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple

from benchmark_v1.src.domains.base import ProblemDomain, DomainEvaluationResult


@dataclass
class SearchCandidate:
    candidate_id: str
    code: str
    description: str
    arm_name: str
    trajectory_id: int
    proposal_index: int
    parent_ids: List[str] = field(default_factory=list)
    generation: int = 0
    hypothesis: Optional[str] = None
    is_seed: bool = False
    train_eval: Optional[DomainEvaluationResult] = None
    test_eval: Optional[DomainEvaluationResult] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def code_hash(self) -> str:
        return hashlib.sha256(self.code.strip().encode("utf-8")).hexdigest()[:16]


@dataclass
class TrajectoryProgress:
    trajectory_id: int
    arm_name: str
    total_proposals: int
    best_candidate: SearchCandidate
    best_train_score: float
    best_train_rel_gap: float
    proposals_history: List[SearchCandidate] = field(default_factory=list)
    best_so_far_curve: List[float] = field(default_factory=list)  # best train score after each proposal
    best_so_far_rel_gap_curve: List[float] = field(default_factory=list)


class SearchGenerator(ABC):
    """Abstract interface for proposing candidate heuristic code."""
    @abstractmethod
    def generate_independent(
        self,
        domain: ProblemDomain,
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        """Proposes independent candidate with zero feedback. Returns (code, description, hypothesis)."""
        pass

    @abstractmethod
    def generate_refinement(
        self,
        domain: ProblemDomain,
        champion: SearchCandidate,
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        """Proposes refinement of champion. Returns (code, description, hypothesis)."""
        pass

    @abstractmethod
    def generate_variation(
        self,
        domain: ProblemDomain,
        parents: List[SearchCandidate],
        population: List[SearchCandidate],
        trajectory_id: int,
        proposal_idx: int,
        seed: int,
        island_id: Optional[int] = None
    ) -> Tuple[str, str, Optional[str]]:
        """Proposes mutation or crossover. Returns (code, description, hypothesis)."""
        pass

    @abstractmethod
    def generate_evidence_guided(
        self,
        domain: ProblemDomain,
        champion: SearchCandidate,
        diagnostics: Dict[str, Any],
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        """Proposes evidence-guided improvement based on instance failure analysis. Returns (code, description, hypothesis)."""
        pass


class SearchArm(ABC):
    """
    Abstract base class for all experimental search arms.
    Enforces strict proposal counting: every proposal attempt is evaluated and logged.
    """
    def __init__(self, name: str, domain: ProblemDomain, generator: SearchGenerator):
        self.name = name
        self.domain = domain
        self.generator = generator

    @abstractmethod
    def run_trajectory(
        self,
        trajectory_id: int,
        proposal_budget: int,
        initial_seeds: List[Dict[str, Any]],
        rng_seed: int
    ) -> TrajectoryProgress:
        """
        Runs one independent trajectory of search under strict proposal_budget.
        Returns TrajectoryProgress with full candidate history and best-so-far curve.
        """
        pass
