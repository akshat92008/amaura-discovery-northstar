"""
Population and Quality-Diversity Archive
========================================
Maintains multi-island populations, Pareto frontier, and evolutionary lineage.
"""

from typing import List, Dict, Set, Optional, Tuple
from amaura.engine.candidate import Candidate


class IslandArchive:
    """
    Manages multi-island populations and an elite global archive.
    """

    def __init__(self, num_islands: int = 3, capacity_per_island: int = 8, elite_capacity: int = 10):
        self.num_islands = num_islands
        self.capacity_per_island = capacity_per_island
        self.elite_capacity = elite_capacity

        # Each island has its own subpopulation sorted by fitness (ascending)
        self.islands: Dict[int, List[Candidate]] = {i: [] for i in range(num_islands)}
        # Global elite archive across all generations
        self.elite_archive: List[Candidate] = []
        # Seen code hashes to enforce uniqueness
        self.seen_hashes: Set[str] = set()
        # All evaluated candidates history
        self.all_candidates: Dict[str, Candidate] = {}

    def is_known(self, candidate: Candidate) -> bool:
        """Check if identical code was already evaluated."""
        return candidate.code_hash in self.seen_hashes

    def add(self, candidate: Candidate) -> bool:
        """
        Add candidate to its assigned island and check for elite promotion.
        Returns True if accepted into population or elite archive.
        """
        self.seen_hashes.add(candidate.code_hash)
        self.all_candidates[candidate.id] = candidate

        if not candidate.is_valid:
            return False

        island = self.islands.setdefault(candidate.island_id, [])

        # Maintain sorted order by fitness (lower is better)
        island.append(candidate)
        island.sort(key=lambda c: c.fitness)
        if len(island) > self.capacity_per_island:
            island.pop()  # Evict worst performer on this island

        # Update global elite archive
        self._update_elite(candidate)
        return True

    def _update_elite(self, candidate: Candidate):
        """Update global top-N archive."""
        # Avoid duplicate code in elite
        existing = [c for c in self.elite_archive if c.code_hash == candidate.code_hash]
        if existing:
            return

        self.elite_archive.append(candidate)
        self.elite_archive.sort(key=lambda c: c.fitness)
        if len(self.elite_archive) > self.elite_capacity:
            self.elite_archive.pop()

    def get_best(self) -> Optional[Candidate]:
        """Return the single best discovered candidate."""
        if self.elite_archive:
            return self.elite_archive[0]
        # Fallback to islands
        all_cands = [c for isl in self.islands.values() for c in isl if c.is_valid]
        if all_cands:
            all_cands.sort(key=lambda c: c.fitness)
            return all_cands[0]
        return None

    def get_parents(self, island_id: int, count: int = 2) -> List[Candidate]:
        """
        Select parents from an island with tournament / rank bias.
        """
        island = self.islands.get(island_id, [])
        valid_cands = [c for c in island if c.is_valid]
        if not valid_cands:
            # Fallback to elite archive
            valid_cands = [c for c in self.elite_archive if c.is_valid]

        if not valid_cands:
            return []

        # Rank-biased selection: pick from top half with higher probability
        selected = []
        for _ in range(count):
            import random
            if len(valid_cands) >= 3 and random.random() < 0.75:
                # Pick from top half
                cand = random.choice(valid_cands[: max(1, len(valid_cands) // 2)])
            else:
                cand = random.choice(valid_cands)
            selected.append(cand)
        return selected

    def migrate(self, count: int = 1):
        """
        Ring migration: top candidates migrate to the adjacent island.
        Breaks local optima and spreads innovations.
        """
        if self.num_islands <= 1:
            return

        migrants: Dict[int, List[Candidate]] = {}
        for i in range(self.num_islands):
            island = self.islands.get(i, [])
            # Pick best candidates to migrate
            migrants[i] = island[:count]

        for i in range(self.num_islands):
            next_island_idx = (i + 1) % self.num_islands
            incoming = migrants[i]
            for cand in incoming:
                # Clone candidate metadata for target island
                cand_copy = Candidate(
                    code=cand.code,
                    function_name=cand.function_name,
                    generation=cand.generation,
                    island_id=next_island_idx,
                    parent_ids=[cand.id],
                    mutation_type=f"migrated_from_{i}",
                    fitness=cand.fitness,
                    raw_score=cand.raw_score,
                    train_score=cand.train_score,
                    test_score=cand.test_score,
                    generalization_score=cand.generalization_score,
                    runtime_ms=cand.runtime_ms,
                    is_valid=cand.is_valid,
                    passed_tests=cand.passed_tests,
                    total_tests=cand.total_tests
                )
                self.islands[next_island_idx].append(cand_copy)

            self.islands[next_island_idx].sort(key=lambda c: c.fitness)
            if len(self.islands[next_island_idx]) > self.capacity_per_island:
                self.islands[next_island_idx] = self.islands[next_island_idx][: self.capacity_per_island]

    def get_pareto_frontier(self) -> List[Tuple[float, float, str]]:
        """
        Returns list of (fitness, complexity_ast_nodes, candidate_id)
        representing Pareto-optimal solutions trading off performance vs simplicity.
        """
        candidates = [c for c in self.all_candidates.values() if c.is_valid]
        if not candidates:
            return []

        frontier = []
        for cand in candidates:
            is_dominated = False
            for other in candidates:
                if other.id == cand.id:
                    continue
                # other dominates cand if it has <= fitness (better/equal) and <= ast_nodes and at least one strictly better
                if (other.fitness <= cand.fitness and other.ast_nodes <= cand.ast_nodes) and (
                    other.fitness < cand.fitness or other.ast_nodes < cand.ast_nodes
                ):
                    is_dominated = True
                    break
            if not is_dominated:
                frontier.append((cand.fitness, cand.ast_nodes, cand.id))

        frontier.sort(key=lambda x: x[0])
        return frontier
