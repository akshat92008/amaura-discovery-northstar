"""
Unit tests for Candidate, Archive, and End-to-End Discovery Loop
"""

import pytest
from amaura.config import DiscoveryConfig
from amaura.engine.candidate import Candidate
from amaura.engine.archive import IslandArchive
from amaura.engine.discovery import DiscoveryEngine


def test_candidate_hashing_and_compilation():
    code = (
        "def priority(item: float, rem: float, cap: float) -> float:\n"
        "    return -rem\n"
    )
    cand = Candidate(code=code, function_name="priority")
    func = cand.compile_function()
    assert callable(func)
    assert func(10.0, 40.0, 100.0) == -40.0
    assert len(cand.code_hash) == 12


def test_island_archive_and_migration():
    archive = IslandArchive(num_islands=3, capacity_per_island=4)
    # Add dummy candidates
    for i in range(12):
        c = Candidate(
            code=f"def priority(item, rem, cap):\n    return {i}\n",
            function_name="priority",
            island_id=i % 3,
            fitness=float(12 - i),
            is_valid=True
        )
        archive.add(c)

    best = archive.get_best()
    assert best is not None
    assert best.fitness == 1.0  # lowest fitness is best

    # Test migration
    archive.migrate(count=1)
    # Ensure islands still have candidates
    for isl in archive.islands.values():
        assert len(isl) > 0


def test_end_to_end_discovery_loop(tmp_path):
    config = DiscoveryConfig(
        problem="bin_packing",
        generations=6,
        num_islands=2,
        population_size=6,
        train_instances=5,
        test_instances=8,
        generalization_instances=5,
        seed=123,
        output_dir=str(tmp_path)
    )
    engine = DiscoveryEngine(config)
    best = engine.run()

    assert best is not None
    assert best.is_valid
    assert len(engine.history) == 6
    assert engine.human_baseline is not None

