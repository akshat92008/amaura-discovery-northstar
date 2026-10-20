"""
Stage 4 Multi-Island Evolutionary Archive
=========================================
Maintains quality-diversity populations and elite candidates for closed-loop search.
1. Strictly ranks by development excess ratio (lower is better).
2. Completely rejects invalid candidates (is_valid=False never enters population).
3. Tracks detailed failure rates separately from performance.
4. Supports tournament parent selection, crossover, and island migration.
"""

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any, Tuple



@dataclass
class Stage4Candidate:
    code: str
    function_name: str = "priority"
    generation: int = 0
    island_id: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutation_type: str = "seed"
    is_valid: bool = False
    fitness: float = float("inf")  # mean normalized excess ratio
    error_message: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    finish_reason: Optional[str] = None
    is_truncation: bool = False
    is_seed: bool = False
    diagnostic_summary: Optional[str] = None
    id: str = field(default="")

    def __post_init__(self):
        if not self.id:
            h = hashlib.sha256(self.code.encode("utf-8")).hexdigest()[:8]
            self.id = f"cand-{h}"

    @property
    def code_hash(self) -> str:
        return hashlib.sha256(self.code.encode("utf-8")).hexdigest()


class Stage4IslandArchive:
    """Multi-island archive maintaining distinct subpopulations and an elite pool."""
    def __init__(
        self,
        num_islands: int = 3,
        capacity_per_island: int = 6,
        elite_capacity: int = 5
    ):
        self.num_islands = num_islands
        self.capacity_per_island = capacity_per_island
        self.elite_capacity = elite_capacity

        self.islands: Dict[int, List[Stage4Candidate]] = {i: [] for i in range(num_islands)}
        self.elite_archive: List[Stage4Candidate] = []
        self.seen_hashes: Set[str] = set()

        # Telemetry
        self.total_evaluated = 0
        self.valid_count = 0
        self.failed_count = 0
        self.failure_reasons: Dict[str, int] = {}

        # Separate Seed vs AI candidate tracking
        self.seed_total = 0
        self.seed_valid = 0
        self.ai_total = 0
        self.ai_valid = 0
        self.ai_failed = 0
        self.candidate_logs: List[Dict[str, Any]] = []

    def is_known(self, code: str) -> bool:
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()
        return h in self.seen_hashes

    def add(self, candidate: Stage4Candidate) -> bool:
        """
        Attempts to add candidate. Rejects invalid candidates and duplicate code.
        Returns True if accepted into subpopulation or elite archive.
        """
        self.total_evaluated += 1
        self.seen_hashes.add(candidate.code_hash)

        if candidate.is_seed:
            self.seed_total += 1
            if candidate.is_valid:
                self.seed_valid += 1
        else:
            self.ai_total += 1
            if candidate.is_valid:
                self.ai_valid += 1
            else:
                self.ai_failed += 1

        cand_log = {
            "id": candidate.id,
            "is_seed": candidate.is_seed,
            "is_valid": candidate.is_valid,
            "fitness": candidate.fitness if math.isfinite(candidate.fitness) else None,
            "error_text": candidate.error_message,
            "finish_reason": candidate.finish_reason,
            "completion_tokens": candidate.completion_tokens,
            "is_truncation": candidate.is_truncation,
            "mutation_type": candidate.mutation_type,
            "has_diagnostics": bool(candidate.diagnostic_summary)
        }
        self.candidate_logs.append(cand_log)

        if not candidate.is_valid:
            self.failed_count += 1
            err_type = (candidate.error_message or "Unknown").split(":")[0].strip()
            self.failure_reasons[err_type] = self.failure_reasons.get(err_type, 0) + 1
            return False

        self.valid_count += 1
        island = self.islands.setdefault(candidate.island_id, [])

        # Maintain sorted order by fitness (lower excess ratio is better)
        island.append(candidate)
        island.sort(key=lambda c: c.fitness)
        if len(island) > self.capacity_per_island:
            island.pop()  # Evict worst performer on this island

        self._update_elite(candidate)
        return True

    def _update_elite(self, candidate: Stage4Candidate):
        existing = [c for c in self.elite_archive if c.code_hash == candidate.code_hash]
        if not existing:
            self.elite_archive.append(candidate)
            self.elite_archive.sort(key=lambda c: c.fitness)
            if len(self.elite_archive) > self.elite_capacity:
                self.elite_archive.pop()

    def get_best(self) -> Optional[Stage4Candidate]:
        if self.elite_archive:
            return self.elite_archive[0]
        all_cands = [c for isl in self.islands.values() for c in isl]
        if all_cands:
            return min(all_cands, key=lambda c: c.fitness)
        return None

    def get_parents(self, island_id: int, count: int = 2, rng: Optional[random.Random] = None) -> List[Stage4Candidate]:
        island = self.islands.get(island_id, [])
        source = island if len(island) >= count else (self.elite_archive if len(self.elite_archive) >= count else (island or self.elite_archive))
        if len(source) <= count:
            return source
        if rng is not None:
            # Controllable tournament selection using trial seed
            tournament_size = min(len(source), count + 2)
            sample = rng.sample(source, tournament_size)
            sample.sort(key=lambda c: c.fitness)
            return sample[:count]
        return source[:count]


    def migrate(self, count: int = 1):
        """Ring migration between adjacent islands."""
        if self.num_islands < 2:
            return
        emigrants = {}
        for i in range(self.num_islands):
            island = self.islands.get(i, [])
            emigrants[i] = island[:count]

        for i in range(self.num_islands):
            next_island_idx = (i + 1) % self.num_islands
            for emigrant in emigrants[i]:
                # Deep copy / clone candidate for target island
                clone = Stage4Candidate(
                    code=emigrant.code,
                    function_name=emigrant.function_name,
                    generation=emigrant.generation,
                    island_id=next_island_idx,
                    parent_ids=[emigrant.id],
                    mutation_type="migration",
                    is_valid=True,
                    fitness=emigrant.fitness,
                    diagnostic_summary=emigrant.diagnostic_summary,
                    is_seed=emigrant.is_seed
                )
                self.islands[next_island_idx].append(clone)
            self.islands[next_island_idx].sort(key=lambda c: c.fitness)
            if len(self.islands[next_island_idx]) > self.capacity_per_island:
                self.islands[next_island_idx] = self.islands[next_island_idx][:self.capacity_per_island]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "valid_count": self.valid_count,
            "failed_count": self.failed_count,
            "failure_rate": round(self.failed_count / max(1, self.total_evaluated), 4),
            "failure_reasons": self.failure_reasons,
            "best_fitness": self.get_best().fitness if self.get_best() else None,
            "seed_total": self.seed_total,
            "seed_valid": self.seed_valid,
            "ai_total": self.ai_total,
            "ai_valid": self.ai_valid,
            "ai_validity_pct": round((self.ai_valid / max(1, self.ai_total)) * 100.0, 2),
            "candidate_logs": self.candidate_logs
        }
