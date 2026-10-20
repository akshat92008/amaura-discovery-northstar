"""
Base Abstractions for Benchmark Problem Domains
===============================================
Defines the standard interface for problem domains in Search Strategy Benchmark V1.
Every domain evaluates candidate heuristic functions inside a fixed, deterministic algorithm skeleton.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DomainEvaluationResult:
    is_valid: bool
    raw_score: float
    avg_score: float
    per_instance_scores: List[float] = field(default_factory=list)
    relative_gap: float = 0.0  # (score - baseline) / baseline, lower is better (< 0 means beats baseline)
    beats_baseline: bool = False
    error_message: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    runtime_ms: float = 0.0


class ProblemDomain(ABC):
    """
    Abstract interface for a problem family (e.g. Bin Packing, Graph Coloring, PFSP).
    Provides access to train/test splits, baseline scores, and deterministic candidate evaluation.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the problem domain."""
        pass

    @property
    @abstractmethod
    def function_name(self) -> str:
        """Name of the target heuristic function to be discovered."""
        pass

    @property
    @abstractmethod
    def function_signature(self) -> str:
        """Python function signature docstring/interface definition."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Domain-specific prompt instructions and constraints."""
        pass

    @property
    @abstractmethod
    def canonical_seeds(self) -> List[Dict[str, Any]]:
        """List of initial seeds: dicts with 'name', 'code', 'description'."""
        pass

    @abstractmethod
    def evaluate(self, code: str, split: str = "train") -> DomainEvaluationResult:
        """
        Evaluates a candidate heuristic code string on the specified dataset split ('train' or 'test').
        Returns DomainEvaluationResult with explicit validity, scores, and diagnostics.
        """
        pass

    @abstractmethod
    def get_baseline_scores(self, split: str = "train") -> Dict[str, float]:
        """Returns baseline raw scores on the specified split."""
        pass

    @abstractmethod
    def compute_relative_gap(self, raw_score: float, split: str = "train") -> float:
        """Computes normalized relative gap vs the primary classical baseline."""
        pass
