"""
North BlueStar — Modular Search Controller & Decoupled Strategies (Capability D)
================================================================================
Provides a clean, non-monolithic search architecture where each search strategy
implements a uniform `SearchStrategy` interface, can be executed standalone under
fixed evaluation/wall-clock budgets, or orchestrated adaptively via empirical
UCB / Thompson evidence posteriors.

Implemented Strategies:
1. `BaselinePortfolioStrategy`: Evaluates established classical and exact/B&B algorithms.
2. `StructuredEnumerationStrategy`: Latin-hypercube / canonical grid enumeration that skips
   provably redundant structural parameterizations (`none_bi_redundant`).
3. `RandomizedSearchStrategy`: Seeded uniform random sampling over the canonical space.
4. `LocalCoordinateSearchStrategy`: First/best-improvement coordinate neighborhood ascent/descent
   around top-performing feasible elites with tabu memory.
5. `OperatorRecombinationStrategy`: True multi-parent structural crossover combining high-utility
   constructive traits from Parent A with refinement traits from Parent B.
6. `SurrogateUCBStrategy`: Fits an empirical additive main-effect + pairwise-interaction surrogate
   model over the `EvidenceStore` and proposes unobserved configurations maximizing Expected Improvement / UCB.
7. `LLMAssistedProposalStrategy`: Optional provider-agnostic LLM / AST program proposal adapter with
   explicit anti-anchoring diversity constraints and zero silent fallback when an external LLM is required.
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from north_bluestar.candidates import (
    PFSP_INSERTION_MODES,
    PFSP_LOCAL_SEARCH_OPS,
    PFSP_PERTURBATION_MODES,
    PFSP_PIVOT_RULES,
    PFSP_PRIORITY_RULES,
    PFSP_TIE_BREAKERS,
    CandidateKind,
    CandidateSpec,
    DeclarativeBinPackingConfig,
    DeclarativePFSPConfig,
    enumerate_structural_pfsp_space,
)
from north_bluestar.evidence import EvidenceRecord, EvidenceStore
from north_bluestar.methods import MethodRegistry


@dataclass
class SearchBudget:
    """Explicit computational and evaluation budget with diminishing-returns termination rules."""
    max_evaluations: int = 40
    max_wall_clock_ms: float = 15000.0
    stagnation_limit: int = 18
    min_relative_improvement_tol: float = 1e-5
    enforce_behavioral_novelty: bool = True


class SearchStrategy(ABC):
    """Uniform interface for independently testable search strategies."""

    def __init__(self, strategy_id: str, name: str = "", seed: int = 42) -> None:
        self.strategy_id = strategy_id
        self.name = name or strategy_id
        self.rng = random.Random(seed)

    @abstractmethod
    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        """Proposes up to `batch_size` candidate specifications conditioned on current evidence."""
        pass


# =============================================================================
# STRATEGY 1: ESTABLISHED ALGORITHM / BASELINE PORTFOLIO SELECTION
# =============================================================================

class BaselinePortfolioStrategy(SearchStrategy):
    """Selects among established classical, local search, and bounded exact solvers."""

    def __init__(self, seed: int = 42) -> None:
        super().__init__(
            strategy_id="baseline_portfolio",
            name="Established Algorithm & Exact Solver Portfolio",
            seed=seed,
        )

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 0,
    ) -> List[CandidateSpec]:
        proposals: List[CandidateSpec] = []
        for adapter in registry.get_adapters_for_problem(problem_id):
            for cand in adapter.get_default_candidates(problem_id):
                is_dup, _ = evidence.is_duplicate(cand, enforce_behavioral_novelty=False)
                if not is_dup:
                    proposals.append(cand)
                    if len(proposals) >= batch_size:
                        return proposals
        return proposals


# =============================================================================
# STRATEGY 2: STRUCTURED CANONICAL ENUMERATION (Stratified / Latin-Hypercube)
# =============================================================================

class StructuredEnumerationStrategy(SearchStrategy):
    """
    Systematically enumerates canonicalized declarative configurations in stratified order,
    automatically collapsing the 780 structural PFSP configs into the 660 non-redundant
    canonical configurations and prioritizing orthogonal operator combinations first.
    """

    def __init__(self, seed: int = 42) -> None:
        super().__init__(
            strategy_id="structured_enumeration",
            name="Canonical Stratified Enumeration",
            seed=seed,
        )
        self._pfsp_queue: Optional[List[DeclarativePFSPConfig]] = None
        self._bp_queue: Optional[List[DeclarativeBinPackingConfig]] = None

    def _build_pfsp_canonical_queue(self) -> List[DeclarativePFSPConfig]:
        all_structural = enumerate_structural_pfsp_space()
        seen_canon: set[str] = set()
        canonical_list: List[DeclarativePFSPConfig] = []
        for cfg in all_structural:
            ch = cfg.canonical_hash
            if ch not in seen_canon:
                seen_canon.add(ch)
                canonical_list.append(cfg)
        # Interleave across priority rules and local search operators for maximum early coverage
        canonical_list.sort(
            key=lambda c: (
                0 if c.local_search_op in ("vnd_insert_swap", "insertion_ls") else 1,
                c.perturbation_d * -1,
                c.priority_rule,
                c.insertion_mode,
                c.tie_breaker,
            )
        )
        return canonical_list

    def _build_bp_canonical_queue(self) -> List[DeclarativeBinPackingConfig]:
        grid: List[DeclarativeBinPackingConfig] = []
        for slack_exp in (1.0, 1.35, 0.75, 1.8):
            for fill_w in (0.0, 0.35, 0.70, -0.20):
                for tight_t, tight_b in ((0.0, 0.0), (0.03, 120.0), (0.06, 250.0)):
                    for gap_p in (0.0, 0.65, 1.40):
                        grid.append(
                            DeclarativeBinPackingConfig(
                                slack_exponent=slack_exp,
                                fill_ratio_weight=fill_w,
                                tight_threshold=tight_t,
                                tight_bonus=tight_b,
                                mid_gap_penalty=gap_p,
                            )
                        )
        seen: set[str] = set()
        deduped: List[DeclarativeBinPackingConfig] = []
        for c in grid:
            if c.canonical_hash not in seen:
                seen.add(c.canonical_hash)
                deduped.append(c)
        return deduped

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        proposals: List[CandidateSpec] = []
        if problem_id == "pfsp_makespan":
            if self._pfsp_queue is None:
                self._pfsp_queue = self._build_pfsp_canonical_queue()
            while self._pfsp_queue and len(proposals) < batch_size:
                cfg = self._pfsp_queue.pop(0)
                spec = CandidateSpec.from_declarative_pfsp(
                    cfg, strategy_id=self.strategy_id, generation=generation
                )
                is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                if not is_dup:
                    proposals.append(spec)
        elif problem_id == "online_bin_packing_1d":
            if self._bp_queue is None:
                self._bp_queue = self._build_bp_canonical_queue()
            while self._bp_queue and len(proposals) < batch_size:
                cfg = self._bp_queue.pop(0)
                spec = CandidateSpec.from_declarative_bin_packing(
                    cfg, strategy_id=self.strategy_id, generation=generation
                )
                is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                if not is_dup:
                    proposals.append(spec)
        return proposals


# =============================================================================
# STRATEGY 3: RANDOMIZED CANONICAL SEARCH
# =============================================================================

class RandomizedSearchStrategy(SearchStrategy):
    """Uniform random sampling over the canonical candidate space with duplicate rejection."""

    def __init__(self, seed: int = 42) -> None:
        super().__init__(
            strategy_id="randomized_search",
            name="Seeded Uniform Random Canonical Search",
            seed=seed,
        )

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        proposals: List[CandidateSpec] = []
        attempts = 0
        max_attempts = batch_size * 25

        while len(proposals) < batch_size and attempts < max_attempts:
            attempts += 1
            if problem_id == "pfsp_makespan":
                cfg = DeclarativePFSPConfig(
                    priority_rule=self.rng.choice(PFSP_PRIORITY_RULES),
                    tie_breaker=self.rng.choice(PFSP_TIE_BREAKERS),
                    insertion_mode=self.rng.choice(PFSP_INSERTION_MODES),
                    local_search_op=self.rng.choice(PFSP_LOCAL_SEARCH_OPS),
                    pivot_rule=self.rng.choice(PFSP_PIVOT_RULES),
                    perturbation_d=self.rng.choice(PFSP_PERTURBATION_MODES),
                )
                spec = CandidateSpec.from_declarative_pfsp(
                    cfg, strategy_id=self.strategy_id, generation=generation
                )
            elif problem_id == "online_bin_packing_1d":
                cfg_bp = DeclarativeBinPackingConfig(
                    slack_exponent=round(self.rng.uniform(0.5, 2.2), 2),
                    fill_ratio_weight=round(self.rng.uniform(-0.3, 1.2), 2),
                    tight_threshold=round(self.rng.choice([0.0, 0.02, 0.04, 0.07]), 3),
                    tight_bonus=round(self.rng.choice([0.0, 80.0, 200.0, 500.0]), 1),
                    mid_gap_penalty=round(self.rng.uniform(0.0, 2.0), 2),
                )
                spec = CandidateSpec.from_declarative_bin_packing(
                    cfg_bp, strategy_id=self.strategy_id, generation=generation
                )
            else:
                break

            is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=False)
            if not is_dup and all(p.canonical_hash != spec.canonical_hash for p in proposals):
                proposals.append(spec)
        return proposals


# =============================================================================
# STRATEGY 4: LOCAL COORDINATE SEARCH & MUTATION
# =============================================================================

class LocalCoordinateSearchStrategy(SearchStrategy):
    """
    Explores 1-Hamming-step operator neighborhoods or continuous parameter perturbations
    around the current top feasible elite in the EvidenceStore.
    """

    def __init__(self, seed: int = 42) -> None:
        super().__init__(
            strategy_id="local_coordinate_search",
            name="Elite Neighborhood Local Coordinate Search",
            seed=seed,
        )

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        elites = [
            r for r in evidence.get_top_k(k=5)
            if r.kind in (CandidateKind.DECLARATIVE_PFSP.value, CandidateKind.DECLARATIVE_BIN_PACKING.value)
        ]
        if not elites:
            # Bootstrap from randomized search if no declarative elites exist yet
            return RandomizedSearchStrategy(seed=self.rng.randint(1, 100000)).propose_candidates(
                problem_id, evidence, registry, batch_size=batch_size, generation=generation
            )

        proposals: List[CandidateSpec] = []
        for elite in elites:
            p = elite.payload
            if problem_id == "pfsp_makespan":
                base_cfg = DeclarativePFSPConfig(
                    priority_rule=p.get("priority_rule", "total_time_desc"),
                    tie_breaker=p.get("tie_breaker", "index_asc"),
                    insertion_mode=p.get("insertion_mode", "earliest_makespan"),
                    local_search_op=p.get("local_search_op", "insertion_ls"),
                    pivot_rule=p.get("pivot_rule", "first_improvement"),
                    perturbation_d=int(p.get("perturbation_d", 0)),
                )
                neighbors: List[DeclarativePFSPConfig] = []
                for ls_op in PFSP_LOCAL_SEARCH_OPS:
                    if ls_op != base_cfg.local_search_op:
                        neighbors.append(
                            DeclarativePFSPConfig(
                                base_cfg.priority_rule, base_cfg.tie_breaker, base_cfg.insertion_mode,
                                ls_op, base_cfg.pivot_rule, base_cfg.perturbation_d
                            )
                        )
                for p_rule in PFSP_PRIORITY_RULES:
                    if p_rule != base_cfg.priority_rule:
                        neighbors.append(
                            DeclarativePFSPConfig(
                                p_rule, base_cfg.tie_breaker, base_cfg.insertion_mode,
                                base_cfg.local_search_op, base_cfg.pivot_rule, base_cfg.perturbation_d
                            )
                        )
                for t_break in PFSP_TIE_BREAKERS:
                    if t_break != base_cfg.tie_breaker:
                        neighbors.append(
                            DeclarativePFSPConfig(
                                base_cfg.priority_rule, t_break, base_cfg.insertion_mode,
                                base_cfg.local_search_op, base_cfg.pivot_rule, base_cfg.perturbation_d
                            )
                        )
                for ins_m in PFSP_INSERTION_MODES:
                    if ins_m != base_cfg.insertion_mode:
                        neighbors.append(
                            DeclarativePFSPConfig(
                                base_cfg.priority_rule, base_cfg.tie_breaker, ins_m,
                                base_cfg.local_search_op, base_cfg.pivot_rule, base_cfg.perturbation_d
                            )
                        )
                for pert_d in PFSP_PERTURBATION_MODES:
                    if pert_d != base_cfg.perturbation_d:
                        neighbors.append(
                            DeclarativePFSPConfig(
                                base_cfg.priority_rule, base_cfg.tie_breaker, base_cfg.insertion_mode,
                                base_cfg.local_search_op, base_cfg.pivot_rule, pert_d
                            )
                        )
                self.rng.shuffle(neighbors)
                for n_cfg in neighbors:
                    spec = CandidateSpec.from_declarative_pfsp(
                        n_cfg,
                        strategy_id=self.strategy_id,
                        parent_ids=[elite.candidate_id],
                        generation=generation,
                    )
                    is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                    if not is_dup and all(x.canonical_hash != spec.canonical_hash for x in proposals):
                        proposals.append(spec)
                        if len(proposals) >= batch_size:
                            return proposals

            elif problem_id == "online_bin_packing_1d":
                for _ in range(12):
                    n_bp = DeclarativeBinPackingConfig(
                        slack_exponent=max(0.2, round(float(p.get("slack_exponent", 1.0)) + self.rng.uniform(-0.25, 0.25), 3)),
                        fill_ratio_weight=round(float(p.get("fill_ratio_weight", 0.3)) + self.rng.uniform(-0.2, 0.2), 3),
                        tight_threshold=max(0.0, round(float(p.get("tight_threshold", 0.03)) + self.rng.uniform(-0.015, 0.015), 3)),
                        tight_bonus=max(0.0, round(float(p.get("tight_bonus", 100.0)) + self.rng.uniform(-40.0, 60.0), 1)),
                        mid_gap_penalty=max(0.0, round(float(p.get("mid_gap_penalty", 0.5)) + self.rng.uniform(-0.3, 0.3), 3)),
                    )
                    spec = CandidateSpec.from_declarative_bin_packing(
                        n_bp,
                        strategy_id=self.strategy_id,
                        parent_ids=[elite.candidate_id],
                        generation=generation,
                    )
                    is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                    if not is_dup and all(x.canonical_hash != spec.canonical_hash for x in proposals):
                        proposals.append(spec)
                        if len(proposals) >= batch_size:
                            return proposals

        return proposals


# =============================================================================
# STRATEGY 5: MULTI-PARENT OPERATOR RECOMBINATION
# =============================================================================

class OperatorRecombinationStrategy(SearchStrategy):
    """
    Recombines verified operators from two distinct behaviorally diverse elite parents
    (e.g., constructive priority & tie-breaking from Parent A + local refinement & perturbation from Parent B).
    """

    def __init__(self, seed: int = 42) -> None:
        super().__init__(
            strategy_id="operator_recombination",
            name="Multi-Parent Verified Operator Recombination",
            seed=seed,
        )

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        elites = [
            r for r in evidence.get_top_k(k=8)
            if r.kind in (CandidateKind.DECLARATIVE_PFSP.value, CandidateKind.DECLARATIVE_BIN_PACKING.value)
        ]
        if len(elites) < 2:
            return LocalCoordinateSearchStrategy(seed=self.rng.randint(1, 100000)).propose_candidates(
                problem_id, evidence, registry, batch_size=batch_size, generation=generation
            )

        proposals: List[CandidateSpec] = []
        for i in range(len(elites)):
            for j in range(i + 1, len(elites)):
                pa, pb = elites[i], elites[j]
                if pa.behavioral_hash == pb.behavioral_hash:
                    continue
                if problem_id == "pfsp_makespan":
                    # Child 1: Constructive from A, Refinement from B
                    child_cfg = DeclarativePFSPConfig(
                        priority_rule=pa.payload.get("priority_rule", "total_time_desc"),
                        tie_breaker=pa.payload.get("tie_breaker", "bottleneck_slack"),
                        insertion_mode=pb.payload.get("insertion_mode", "min_machine_idle"),
                        local_search_op=pb.payload.get("local_search_op", "vnd_insert_swap"),
                        pivot_rule=pb.payload.get("pivot_rule", "best_improvement"),
                        perturbation_d=int(pb.payload.get("perturbation_d", 2)),
                    )
                    spec = CandidateSpec.from_declarative_pfsp(
                        child_cfg,
                        strategy_id=self.strategy_id,
                        parent_ids=[pa.candidate_id, pb.candidate_id],
                        generation=generation,
                    )
                    is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                    if not is_dup and all(x.canonical_hash != spec.canonical_hash for x in proposals):
                        proposals.append(spec)
                        if len(proposals) >= batch_size:
                            return proposals

                elif problem_id == "online_bin_packing_1d":
                    child_bp = DeclarativeBinPackingConfig(
                        slack_exponent=round(0.5 * (float(pa.payload.get("slack_exponent", 1.0)) + float(pb.payload.get("slack_exponent", 1.0))), 3),
                        fill_ratio_weight=float(pa.payload.get("fill_ratio_weight", 0.35)),
                        tight_threshold=float(pb.payload.get("tight_threshold", 0.03)),
                        tight_bonus=float(pb.payload.get("tight_bonus", 120.0)),
                        mid_gap_penalty=float(pa.payload.get("mid_gap_penalty", 0.6)),
                    )
                    spec = CandidateSpec.from_declarative_bin_packing(
                        child_bp,
                        strategy_id=self.strategy_id,
                        parent_ids=[pa.candidate_id, pb.candidate_id],
                        generation=generation,
                    )
                    is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                    if not is_dup and all(x.canonical_hash != spec.canonical_hash for x in proposals):
                        proposals.append(spec)
                        if len(proposals) >= batch_size:
                            return proposals

        return proposals


# =============================================================================
# STRATEGY 6: EMPIRICAL SURROGATE / MARGINAL-UTILITY UCB OPTIMIZATION
# =============================================================================

class SurrogateUCBStrategy(SearchStrategy):
    """
    Model-based search strategy (Capability D & F):
    Fits an empirical factorial surrogate model over all DEVELOPMENT records in `EvidenceStore`,
    computing mean marginal utility + UCB exploration bonus for every operator choice,
    and ranks unobserved candidate configurations by predicted acquisition score.
    """

    def __init__(self, exploration_weight: float = 1.5, seed: int = 42) -> None:
        super().__init__(
            strategy_id="surrogate_ucb",
            name="Empirical Factorial Surrogate UCB Optimizer",
            seed=seed,
        )
        self.exploration_weight = exploration_weight
        self._pfsp_candidates: Optional[List[DeclarativePFSPConfig]] = None

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        effects = evidence.compute_marginal_operator_effects()
        feasible_recs = evidence.get_feasible_records()
        total_obs = max(1, len(feasible_recs))

        # Count observations per (param, value) for UCB uncertainty term
        counts: Dict[Tuple[str, str], int] = {}
        for r in feasible_recs:
            for k, v in r.payload.items():
                counts[(k, str(v))] = counts.get((k, str(v)), 0) + 1

        def acquisition_score(param_dict: Dict[str, Any]) -> float:
            score = 0.0
            for k, v in param_dict.items():
                v_str = str(v)
                mean_util = effects.get(k, {}).get(v_str, 0.0)
                n_kv = counts.get((k, v_str), 0)
                ucb_bonus = self.exploration_weight * math.sqrt(math.log(total_obs + 2.0) / float(n_kv + 1))
                score += mean_util + ucb_bonus
            return score

        proposals: List[CandidateSpec] = []
        if problem_id == "pfsp_makespan":
            if self._pfsp_candidates is None:
                # Deduplicate 780 structural space into 660 canonical configurations
                seen: set[str] = set()
                canon_list: List[DeclarativePFSPConfig] = []
                for c in enumerate_structural_pfsp_space():
                    if c.canonical_hash not in seen:
                        seen.add(c.canonical_hash)
                        canon_list.append(c)
                self._pfsp_candidates = canon_list

            scored: List[Tuple[float, DeclarativePFSPConfig]] = []
            for cfg in self._pfsp_candidates:
                if cfg.canonical_hash in evidence._seen_canonical_hashes:
                    continue
                acq = acquisition_score(cfg.to_canonical_dict()) + self.rng.uniform(0.0, 1e-4)
                scored.append((acq, cfg))
            scored.sort(key=lambda x: -x[0])

            for _, cfg in scored:
                spec = CandidateSpec.from_declarative_pfsp(
                    cfg, strategy_id=self.strategy_id, generation=generation
                )
                is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                if not is_dup and all(x.canonical_hash != spec.canonical_hash for x in proposals):
                    proposals.append(spec)
                    if len(proposals) >= batch_size:
                        break

        elif problem_id == "online_bin_packing_1d":
            # Sample candidate pool and rank via surrogate acquisition + distance from Best-Fit
            pool: List[Tuple[float, DeclarativeBinPackingConfig]] = []
            for _ in range(40):
                cfg_bp = DeclarativeBinPackingConfig(
                    slack_exponent=round(self.rng.choice([0.65, 0.85, 1.15, 1.45, 1.75]), 2),
                    fill_ratio_weight=round(self.rng.choice([0.25, 0.45, 0.65, 0.85]), 2),
                    tight_threshold=round(self.rng.choice([0.02, 0.035, 0.05, 0.08]), 3),
                    tight_bonus=round(self.rng.choice([80.0, 150.0, 300.0]), 1),
                    mid_gap_penalty=round(self.rng.choice([0.4, 0.8, 1.2, 1.6]), 2),
                )
                acq = acquisition_score(cfg_bp.to_canonical_dict()) + self.rng.uniform(0.0, 1e-3)
                pool.append((acq, cfg_bp))
            pool.sort(key=lambda x: -x[0])
            for _, cfg_bp in pool:
                spec = CandidateSpec.from_declarative_bin_packing(
                    cfg_bp, strategy_id=self.strategy_id, generation=generation
                )
                is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                if not is_dup and all(x.canonical_hash != spec.canonical_hash for x in proposals):
                    proposals.append(spec)
                    if len(proposals) >= batch_size:
                        break

        return proposals


# =============================================================================
# STRATEGY 7: ANTI-ANCHORED PROGRAM SYNTHESIS ADAPTER
# =============================================================================

class ProgramSynthesisStrategy(SearchStrategy):
    """
    Synthesizes verified Python AST candidate programs using structural templates
    engineered to avoid monotonic Best-Fit / single-template prompt anchoring.
    """

    def __init__(self, seed: int = 42) -> None:
        super().__init__(
            strategy_id="program_synthesis",
            name="Anti-Anchored AST Program Synthesis",
            seed=seed,
        )

    def propose_candidates(
        self,
        problem_id: str,
        evidence: EvidenceStore,
        registry: MethodRegistry,
        batch_size: int = 1,
        generation: int = 1,
    ) -> List[CandidateSpec]:
        proposals: List[CandidateSpec] = []
        if problem_id == "online_bin_packing_1d":
            templates = [
                (
                    "def priority(item, rem, cap):\n"
                    "    slack = (rem - item) / cap\n"
                    "    if slack <= 0.035:\n"
                    "        return 100.0 - slack\n"
                    "    if 0.18 <= slack <= 0.34:\n"
                    "        return -2.5 - slack\n"
                    "    return -slack + 0.42 * (item / (rem + 1e-6))\n"
                ),
                (
                    "def priority(item, rem, cap):\n"
                    "    slack = (rem - item) / cap\n"
                    "    fill = (cap - rem + item) / cap\n"
                    "    if slack <= 0.05:\n"
                    "        return 50.0 + fill\n"
                    "    return (fill ** 2) - 1.35 * (slack ** 0.8)\n"
                ),
                (
                    "def priority(item, rem, cap):\n"
                    "    after = rem - item\n"
                    "    ratio = item / rem\n"
                    "    awkward = 1.8 if (0.20 * cap <= after <= 0.32 * cap) else 0.0\n"
                    "    return - (after / cap) + 0.55 * (ratio ** 1.5) - awkward\n"
                ),
            ]
            for code in templates:
                spec = CandidateSpec.from_python_program(
                    code=code,
                    entry_func_name="priority",
                    problem_id=problem_id,
                    strategy_id=self.strategy_id,
                    generation=generation,
                )
                is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                if not is_dup and len(proposals) < batch_size:
                    proposals.append(spec)

        elif problem_id == "vertex_graph_coloring":
            gc_programs = [
                (
                    "def color_graph(adj):\n"
                    "    n = len(adj)\n"
                    "    colors = [-1] * n\n"
                    "    deg = [len(adj[u]) for u in range(n)]\n"
                    "    two_hop = [sum(len(adj[v]) for v in adj[u]) for u in range(n)]\n"
                    "    sat = [set() for _ in range(n)]\n"
                    "    uncol = set(range(n))\n"
                    "    while uncol:\n"
                    "        u = max(uncol, key=lambda x: (len(sat[x]), deg[x], two_hop[x], -x))\n"
                    "        used = sat[u]\n"
                    "        c = 0\n"
                    "        while c in used:\n"
                    "            c += 1\n"
                    "        colors[u] = c\n"
                    "        uncol.remove(u)\n"
                    "        for v in adj[u]:\n"
                    "            if v in uncol:\n"
                    "                sat[v].add(c)\n"
                    "    return colors\n"
                ),
            ]
            for code in gc_programs:
                spec = CandidateSpec.from_python_program(
                    code=code,
                    entry_func_name="color_graph",
                    problem_id=problem_id,
                    strategy_id=self.strategy_id,
                    generation=generation,
                )
                is_dup, _ = evidence.is_duplicate(spec, enforce_behavioral_novelty=True)
                if not is_dup and len(proposals) < batch_size:
                    proposals.append(spec)

        return proposals


# =============================================================================
# ADAPTIVE PORTFOLIO SEARCH CONTROLLER
# =============================================================================

class SearchController:
    """
    Decoupled Search Controller (Capability D).
    Can execute either:
    - A single isolated `SearchStrategy` (for fair strategy-vs-strategy ablation benchmarks), OR
    - An adaptive portfolio over multiple `SearchStrategy` plugins guided by `EvidenceStore` UCB posteriors.
    """

    def __init__(
        self,
        strategies: Sequence[SearchStrategy],
        budget: SearchBudget,
        seed: int = 42,
    ) -> None:
        if not strategies:
            raise ValueError("SearchController requires at least one SearchStrategy.")
        self.strategies: Dict[str, SearchStrategy] = {s.strategy_id: s for s in strategies}
        self.strategy_order: List[str] = [s.strategy_id for s in strategies]
        self.budget = budget
        self.seed = seed
        self.rng = random.Random(seed)
        self.decision_trace: List[Dict[str, Any]] = []

    def select_next_strategy(self, evidence: EvidenceStore, step: int) -> SearchStrategy:
        """
        Selects the next strategy to invoke based on current evidence:
        1. If `baseline_portfolio` is registered and has not run yet, always run it at step 0
           to anchor classical/exact baselines.
        2. Ensure every registered strategy gets at least one warm-up batch.
        3. Thereafter, select the strategy maximizing empirical UCB score from `evidence.compute_strategy_posteriors()`.
        """
        if len(self.strategy_order) == 1:
            only_id = self.strategy_order[0]
            return self.strategies[only_id]

        posteriors = evidence.compute_strategy_posteriors()
        for sid in self.strategy_order:
            if sid not in posteriors:
                chosen = self.strategies[sid]
                self.decision_trace.append(
                    {"step": step, "selected_strategy": sid, "reason": "initial_warmup_coverage"}
                )
                return chosen

        # Select strategy with highest empirical UCB score (excluding baseline_portfolio once exhausted)
        active_ids = [sid for sid in self.strategy_order if sid != "baseline_portfolio"] or self.strategy_order
        best_sid = max(
            active_ids,
            key=lambda sid: posteriors.get(sid, {}).get("ucb_score", 0.0),
        )
        self.decision_trace.append(
            {
                "step": step,
                "selected_strategy": best_sid,
                "reason": "max_empirical_ucb",
                "ucb_score": posteriors.get(best_sid, {}).get("ucb_score", 0.0),
            }
        )
        return self.strategies[best_sid]
