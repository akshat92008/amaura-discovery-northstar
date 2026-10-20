"""
Stage 2: Timeout Regression Test Suite (Tests A through F)
=========================================================
Proves that SandboxTimeoutException(BaseException) properly interrupts:
- Test A: Unbounded loop (while True: pass)
- Test B: Unbounded loop inside try ... except Exception
- Test C: Unbounded loop inside try ... except (bare except)
- Test D: Normal candidate exception (raise ValueError)
- Test E: Known-good valid candidate
- Test F: Timeout candidate inside multiprocessing/subprocess worker execution path
"""

import multiprocessing
import os
import signal
import sys
import time
import pytest

from stage2.src.sandbox import (
    SandboxTimeoutException,
    _sigalrm_handler,
    check_ast_security
)
from stage2.src.evaluator_gc import GraphColoringEvaluator
from stage2.src.evaluator_pfsp import PFSPEvaluator


@pytest.fixture
def gc_evaluator():
    return GraphColoringEvaluator(scale_aware_base_ms=100.0, scale_aware_per_vertex_ms=1.0, hard_sigalrm_sec=1)


@pytest.fixture
def pfsp_evaluator():
    return PFSPEvaluator(scale_aware_base_ms=100.0, scale_aware_per_nm_ms=1.0, hard_sigalrm_sec=1)


@pytest.fixture
def sample_gc_dataset():
    # 3 small instances
    return [
        {"adj": [[1, 2], [0, 2], [0, 1]]},
        {"adj": [[1], [0, 2], [1, 3], [2]]},
        {"adj": [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]}
    ]


# ---------------------------------------------------------------------------
# Test A: Unbounded loop (while True: pass)
# ---------------------------------------------------------------------------
def test_a_unbounded_loop_timeout(gc_evaluator, sample_gc_dataset):
    code = """
def color_graph(adj: list[list[int]]) -> list[int]:
    while True:
        pass
    return [0] * len(adj)
"""
    t0 = time.time()
    res = gc_evaluator.evaluate_code(code, sample_gc_dataset)
    elapsed = time.time() - t0

    assert not res["is_valid"], "Candidate with while True must be marked invalid"
    assert res["total_colors"] == 999999, "Invalid candidate must receive 999,999 penalty"
    assert "Timeout" in res.get("error", ""), f"Error must indicate timeout, got: {res.get('error')}"
    assert elapsed < 5.0, f"Evaluator must return promptly upon timeout, took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Test B: Unbounded loop with try ... except Exception
# ---------------------------------------------------------------------------
def test_b_try_except_exception_does_not_swallow_timeout(gc_evaluator, sample_gc_dataset):
    code = """
def color_graph(adj: list[list[int]]) -> list[int]:
    try:
        while True:
            pass
    except Exception:
        pass
    return [0] * len(adj)
"""
    t0 = time.time()
    res = gc_evaluator.evaluate_code(code, sample_gc_dataset)
    elapsed = time.time() - t0

    assert not res["is_valid"], "Candidate wrapping while True in except Exception must be marked invalid"
    assert res["total_colors"] == 999999, "Must receive penalty score"
    assert elapsed < 5.0, f"Evaluator must return promptly without hanging, took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Test C: Unbounded loop with bare except:
# ---------------------------------------------------------------------------
def test_c_try_bare_except_evaluator_returns_and_penalizes(gc_evaluator, sample_gc_dataset):
    code = """
def color_graph(adj: list[list[int]]) -> list[int]:
    try:
        while True:
            pass
    except:
        pass
    return None
"""
    t0 = time.time()
    res = gc_evaluator.evaluate_code(code, sample_gc_dataset)
    elapsed = time.time() - t0

    assert not res["is_valid"], "Candidate with bare except must be marked invalid"
    assert res["total_colors"] == 999999, "Must receive penalty score"
    assert elapsed < 5.0, f"Evaluator must return promptly without hanging, took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Test D: Normal candidate exception (e.g. raise ValueError)
# ---------------------------------------------------------------------------
def test_d_normal_candidate_exception_handled_cleanly(gc_evaluator, sample_gc_dataset):
    code = """
def color_graph(adj: list[list[int]]) -> list[int]:
    raise ValueError("intentional test exception")
"""
    res = gc_evaluator.evaluate_code(code, sample_gc_dataset)
    assert not res["is_valid"], "Candidate raising exception must be marked invalid"
    assert res["total_colors"] == 999999
    assert "ValueError" in res.get("error", "")


# ---------------------------------------------------------------------------
# Test E: Known-good valid candidate
# ---------------------------------------------------------------------------
def test_e_known_good_candidate_succeeds(gc_evaluator, sample_gc_dataset):
    code = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    colors = [-1] * n
    for u in range(n):
        used = {colors[v] for v in adj[u] if colors[v] >= 0}
        c = 0
        while c in used:
            c += 1
        colors[u] = c
    return colors
"""
    res = gc_evaluator.evaluate_code(code, sample_gc_dataset)
    assert res["is_valid"], f"Known good greedy candidate must be valid, got: {res.get('error')}"
    assert res["total_colors"] < 100, f"Total colors must be a normal valid score, got: {res['total_colors']}"


# ---------------------------------------------------------------------------
# Test F: Timeout candidate inside multiprocessing/subprocess execution path
# ---------------------------------------------------------------------------
def _eval_worker(code, dataset, result_queue):
    evaluator = GraphColoringEvaluator(scale_aware_base_ms=50.0, scale_aware_per_vertex_ms=1.0, hard_sigalrm_sec=1)
    res = evaluator.evaluate_code(code, dataset)
    result_queue.put(res)


def test_f_worker_process_timeout_and_parent_survival(sample_gc_dataset):
    code = """
def color_graph(adj: list[list[int]]) -> list[int]:
    while True:
        pass
    return [0] * len(adj)
"""
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_eval_worker, args=(code, sample_gc_dataset, result_queue))
    t0 = time.time()
    p.start()
    p.join(timeout=5)

    assert not p.is_alive(), "Worker process must terminate without remaining orphaned"
    assert not result_queue.empty(), "Worker must return evaluation result"
    res = result_queue.get()
    assert not res["is_valid"], "Candidate must be marked invalid in worker"
    assert res["total_colors"] == 999999, "Must receive penalty"
    assert time.time() - t0 < 6.0, "Parent must survive without deadlock"
