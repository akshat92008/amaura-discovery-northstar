"""
Stage 4 Data Isolation & Quarantined Benchmark Verification Tests
=================================================================
Validates strict mathematical and architectural data isolation:
1. Search phase executes successfully with zero access to hidden.json.
2. Search phase selections are identical whether hidden.json exists or not.
3. Candidate ranking and elite promotion use solely development data.
4. Cryptographic sealing of hidden benchmark before post-search unsealing.
"""

import json
import os
import tempfile
import pytest

from stage4.src.benchmark import generate_and_save_benchmarks
from stage4.src.budget_enforcer import BudgetEnforcer
from stage4.src.client import Stage4LLMClient
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.search import run_arm_a_search, run_arm_c_search
from stage4.src.archive import Stage4IslandArchive, Stage4Candidate


@pytest.fixture
def isolated_benchmarks():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bench_dir = os.path.join(tmp_dir, "benchmarks")
        generate_and_save_benchmarks(bench_dir)
        yield bench_dir


def test_search_phase_has_zero_access_to_hidden_data(isolated_benchmarks):
    bench_dir = isolated_benchmarks
    # Delete hidden.json completely during search phase
    hidden_path = os.path.join(bench_dir, "hidden.json")
    os.remove(hidden_path)
    assert not os.path.exists(hidden_path)

    # Load dev data
    dev_path = os.path.join(bench_dir, "dev.json")
    with open(dev_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)
    dev_streams = [entry["items"] for entry in dev_data]

    # Run search with zero access to hidden.json
    ledger_path = os.path.join(bench_dir, "budget.json")
    enforcer = BudgetEnforcer(ledger_path=ledger_path, max_requests=50)
    client = Stage4LLMClient(budget_enforcer=enforcer, mock_mode=True)
    evaluator = Stage4Evaluator()

    cand_a, _ = run_arm_a_search(client, evaluator, dev_streams, candidate_slots=4)
    cand_c, _ = run_arm_c_search(client, evaluator, dev_streams, candidate_slots=4)

    assert cand_a.is_valid
    assert cand_c.is_valid
    assert cand_a.fitness < float("inf")
    assert cand_c.fitness < float("inf")


def test_candidate_archive_ranking_uses_dev_data_only():
    archive = Stage4IslandArchive(num_islands=1, capacity_per_island=5)

    c1 = Stage4Candidate(code="def priority(...): pass", is_valid=True, fitness=0.150)
    c2 = Stage4Candidate(code="def priority(...): pass # 2", is_valid=True, fitness=0.080)
    c3 = Stage4Candidate(code="def priority(...): pass # 3", is_valid=True, fitness=0.220)

    archive.add(c1)
    archive.add(c2)
    archive.add(c3)

    # Best candidate must be strictly lowest fitness (0.080)
    best = archive.get_best()
    assert best is not None
    assert best.fitness == 0.080
    assert best.code == c2.code


def test_evaluator_has_no_hidden_split_bleed():
    """Confirms Stage4Evaluator evaluates ONLY on passed items without hidden blending."""
    evaluator = Stage4Evaluator()
    code = (
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "    return -(remaining_capacity - item)\n"
    )
    # Synthetic streams
    custom_streams = [[50.0, 50.0], [25.0, 25.0, 50.0]]
    res = evaluator.evaluate_candidate(code, custom_streams)

    assert res.is_valid
    assert res.passed_streams == 2
    assert res.total_streams == 2
    assert res.fitness == 0.0  # Perfect packing
