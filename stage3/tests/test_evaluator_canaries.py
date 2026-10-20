"""
Unit Tests: Evaluator Red-Teaming Canary Suite & Defensive Copying
==================================================================
Verifies:
1. All 14 canaries in canaries.py pass.
2. Evaluator defensive copy protects dataset from in-place mutations.
3. K3 triangle sanity check prevents invalid initial candidates.
4. Bounded penalty formula correctly bounds chromatic score sum.
"""

from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.canaries import run_all_canaries


def test_canary_suite_14_of_14_pass():
    evaluator = GraphColoringEvaluator()
    sample_dataset = [{"adj": [[1, 2], [0, 2], [0, 1]]}]
    report = run_all_canaries(evaluator, sample_dataset)
    assert report["all_passed"], f"Canaries failed: {report['results']}"
    assert report["passed_canaries"] == 14


def test_evaluator_defensive_copy():
    # Malicious candidate tries to mutate adj in-place
    code_mutator = """
def color_graph(adj: list[list[int]]) -> list[int]:
    adj.clear()  # Attempt to wipe dataset
    return []
"""
    evaluator = GraphColoringEvaluator()
    original_adj = [[1, 2], [0, 2], [0, 1]]
    dataset = [{"adj": [list(r) for r in original_adj]}]

    res = evaluator.evaluate_code(code_mutator, dataset)
    # The dataset itself must remain completely unmutated
    assert len(dataset[0]["adj"]) == 3
    assert dataset[0]["adj"] == original_adj


def test_evaluator_worst_case_penalty_calculation():
    dataset = [
        {"adj": [[1, 2], [0, 2], [0, 1]]},     # 3 vertices
        {"adj": [[1], [0]]},                   # 2 vertices
        {"adj": [[1, 2, 3], [0], [0], [0]]}    # 4 vertices
    ]
    # Sum of vertices = 3 + 2 + 4 = 9. Penalty = 9 + 1 = 10
    bound = GraphColoringEvaluator.compute_worst_case_penalty(dataset)
    assert bound == 10
