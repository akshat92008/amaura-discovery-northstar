"""
Unit & Correctness Tests for Candidate #2 Verification and Variants
===================================================================
Tests:
1. Reference makespan exactness
2. Exhaustive comparison of accelerated swap evaluation vs full makespan recomputation
3. Behavioral equivalence of Variant 0 and Variant 1 trajectories
4. Validity and monotonic non-degradation of Variant 2 (anytime bounded)
5. Validity and correctness of Variant 3 (accelerated insertion LS)
6. Permutation validation edge cases (duplicates, out of bounds, wrong types)
7. Trivial / edge-case inputs (empty, single job, single machine)
"""

import random
import pytest
from benchmark_v1.src.domains.pfsp_full_algorithm import validate_permutation
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    calc_makespan_and_flow_ref,
    solve_v0_original,
    solve_v1_exact_accel,
    solve_v2_anytime_bounded,
    solve_v3_insertion_ls,
    neh_solve,
    neh_ls_solve,
    iterated_greedy_solve
)


def test_reference_makespan_manual():
    # 3 jobs x 3 machines manual matrix
    times = [
        [3, 2, 2],  # job 0
        [2, 1, 4],  # job 1
        [4, 3, 1]   # job 2
    ]
    # Schedule: [0, 1, 2]
    # Machine 0: job 0 (0..3), job 1 (3..5), job 2 (5..9)
    # Machine 1: job 0 (3..5), job 1 (5..6), job 2 (9..12)
    # Machine 2: job 0 (5..7), job 1 (7..11), job 2 (12..13) -> C_max = 13
    assert calc_makespan_ref(times, [0, 1, 2]) == 13
    cmax, flow = calc_makespan_and_flow_ref(times, [0, 1, 2])
    assert cmax == 13
    # flow = C(0,2) + C(1,2) + C(2,2) = 7 + 11 + 13 = 31
    assert flow == 31


def test_exhaustive_swap_acceleration():
    """Verify that every single pair swap evaluation matches exact full recomputation."""
    rng = random.Random(1337)
    for n, m in [(8, 3), (12, 4), (20, 5)]:
        times = [[rng.randint(1, 50) for _ in range(m)] for _ in range(n)]
        seq = list(range(n))
        rng.shuffle(seq)

        # Precompute E and Q
        E = [[0] * m for _ in range(n)]
        dp = [0] * m
        for k in range(n):
            job = seq[k]
            pj = times[job]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            E[k] = list(dp)

        Q = [[0] * m for _ in range(n)]
        tail = [0] * m
        for k in range(n - 1, -1, -1):
            Q[k] = list(tail)
            job = seq[k]
            pj = times[job]
            tail[m-1] += pj[m-1]
            for c in range(m - 2, -1, -1):
                tail[c] = (tail[c+1] if tail[c+1] > tail[c] else tail[c]) + pj[c]

        for i in range(n):
            prefix_i = E[i-1] if i > 0 else [0] * m
            for j in range(i + 1, n):
                # Accelerated evaluation
                dp_local = list(prefix_i)
                job_i = seq[j]
                p_i = times[job_i]
                dp_local[0] += p_i[0]
                for c in range(1, m):
                    dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_i[c]

                for k in range(i + 1, j):
                    job_k = seq[k]
                    p_k = times[job_k]
                    dp_local[0] += p_k[0]
                    for c in range(1, m):
                        dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_k[c]

                job_j = seq[i]
                p_j = times[job_j]
                dp_local[0] += p_j[0]
                for c in range(1, m):
                    dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_j[c]

                accel_val = max(dp_local[c] + Q[j][c] for c in range(m))

                # Exact full recomputation
                swapped = list(seq)
                swapped[i], swapped[j] = swapped[j], swapped[i]
                exact_val = calc_makespan_ref(times, swapped)

                assert accel_val == exact_val, f"Mismatch at ({i}, {j}): accel={accel_val}, exact={exact_val}"


def test_v0_v1_trajectory_exactness():
    """Verify that Variant 0 and Variant 1 produce identical search results."""
    rng = random.Random(2026)
    for n, m in [(10, 4), (15, 5), (25, 6)]:
        times = [[rng.randint(5, 100) for _ in range(m)] for _ in range(n)]
        s0 = solve_v0_original(times)
        s1 = solve_v1_exact_accel(times)
        c0 = calc_makespan_ref(times, s0)
        c1 = calc_makespan_ref(times, s1)
        assert c0 == c1, f"Makespan mismatch on n={n}, m={m}: V0={c0}, V1={c1}"
        assert s0 == s1, f"Permutation mismatch on n={n}, m={m}"


def test_v2_anytime_bounded():
    """Verify Variant 2 under various evaluation budgets."""
    rng = random.Random(404)
    times = [[rng.randint(10, 80) for _ in range(5)] for _ in range(30)]
    
    # NEH baseline
    s_neh = neh_solve(times)
    c_neh = calc_makespan_ref(times, s_neh)

    for budget in [0, 50, 200, 1000]:
        s_v2 = solve_v2_anytime_bounded(times, max_evals=budget)
        is_valid, err = validate_permutation(s_v2, 30)
        assert is_valid, f"V2 produced invalid permutation under budget {budget}: {err}"
        c_v2 = calc_makespan_ref(times, s_v2)
        assert c_v2 <= c_neh, f"V2 degraded initial NEH makespan! c_v2={c_v2} > c_neh={c_neh}"


def test_v3_insertion_ls():
    """Verify Variant 3 validity and performance."""
    rng = random.Random(505)
    times = [[rng.randint(10, 80) for _ in range(4)] for _ in range(25)]
    s_neh = neh_solve(times)
    c_neh = calc_makespan_ref(times, s_neh)
    s_v3 = solve_v3_insertion_ls(times)
    is_valid, err = validate_permutation(s_v3, 25)
    assert is_valid, f"V3 invalid permutation: {err}"
    c_v3 = calc_makespan_ref(times, s_v3)
    assert c_v3 <= c_neh, f"V3 degraded NEH makespan: {c_v3} > {c_neh}"


def test_permutation_validation():
    assert validate_permutation([0, 1, 2], 3)[0] is True
    assert validate_permutation([0, 1], 3)[0] is False  # Length
    assert validate_permutation([0, 1, 1], 3)[0] is False  # Duplicate
    assert validate_permutation([0, 1, 3], 3)[0] is False  # Out of range
    assert validate_permutation([0, -1, 1], 3)[0] is False  # Negative
    assert validate_permutation("not a list", 3)[0] is False  # Type
    assert validate_permutation([0, True, 2], 3)[0] is False  # Bool in list


def test_edge_cases():
    assert solve_v0_original([]) == []
    assert solve_v1_exact_accel([]) == []
    assert solve_v2_anytime_bounded([]) == []
    assert solve_v3_insertion_ls([]) == []
    assert solve_v1_exact_accel([[5]]) == [0]
    assert solve_v2_anytime_bounded([[5]]) == [0]
