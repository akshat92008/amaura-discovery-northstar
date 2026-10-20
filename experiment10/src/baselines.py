"""
Experiment #10: Classical Human Baselines for PFSP
==================================================
Implements:
1. Palmer's Slope Heuristic (1965)
2. Campbell-Dudek-Smith (CDS 1970)
3. Nawaz-Enscore-Ham (NEH 1983)
4. Bounded Iterated Greedy (Ruiz & Stutzle 2007)
"""

from typing import Sequence


def palmer_code() -> str:
    return '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    n = len(times)
    m = len(times[0])
    slopes = []
    for j in range(n):
        s_j = sum((2 * k + 1 - m) * times[j][k] for k in range(m))
        slopes.append((s_j, j))
    slopes.sort(key=lambda x: (-x[0], x[1]))
    return [j for _, j in slopes]
'''


def cds_code() -> str:
    return '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    n = len(times)
    m = len(times[0])
    if m == 1:
        return sorted(range(n), key=lambda j: times[j][0])

    def calc_makespan(perm):
        dp = [0] * m
        for job in perm:
            dp[0] += times[job][0]
            for k in range(1, m):
                if dp[k - 1] > dp[k]:
                    dp[k] = dp[k - 1] + times[job][k]
                else:
                    dp[k] = dp[k] + times[job][k]
        return dp[m - 1]

    best_perm = None
    best_cmax = float("inf")

    for r in range(1, m):
        u_list = []
        v_list = []
        for j in range(n):
            a_j = sum(times[j][k] for k in range(r))
            b_j = sum(times[j][k] for k in range(m - r, m))
            if a_j <= b_j:
                u_list.append((a_j, j))
            else:
                v_list.append((b_j, j))

        u_list.sort(key=lambda x: (x[0], x[1]))
        v_list.sort(key=lambda x: (-x[0], x[1]))
        cand_perm = [j for _, j in u_list] + [j for _, j in v_list]
        cmax = calc_makespan(cand_perm)
        if cmax < best_cmax:
            best_cmax = cmax
            best_perm = cand_perm

    return best_perm
'''


def neh_code() -> str:
    return '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    n = len(times)
    m = len(times[0])

    def calc_partial_makespan(perm):
        dp = [0] * m
        for job in perm:
            dp[0] += times[job][0]
            for k in range(1, m):
                if dp[k - 1] > dp[k]:
                    dp[k] = dp[k - 1] + times[job][k]
                else:
                    dp[k] = dp[k] + times[job][k]
        return dp[m - 1]

    totals = [(sum(times[j]), j) for j in range(n)]
    totals.sort(key=lambda x: (-x[0], x[1]))
    order = [j for _, j in totals]

    if n <= 1:
        return order

    c1 = [order[0], order[1]]
    c2 = [order[1], order[0]]
    curr_seq = c1 if calc_partial_makespan(c1) <= calc_partial_makespan(c2) else c2

    for i in range(2, n):
        job = order[i]
        best_cand = None
        best_ms = float("inf")
        for pos in range(i + 1):
            cand = curr_seq[:pos] + [job] + curr_seq[pos:]
            ms = calc_partial_makespan(cand)
            if ms < best_ms:
                best_ms = ms
                best_cand = cand
        curr_seq = best_cand

    return curr_seq
'''


def iterated_greedy_code() -> str:
    return '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    import math
    import random

    n = len(times)
    m = len(times[0])

    def calc_makespan(perm):
        dp = [0] * m
        for job in perm:
            dp[0] += times[job][0]
            for k in range(1, m):
                if dp[k - 1] > dp[k]:
                    dp[k] = dp[k - 1] + times[job][k]
                else:
                    dp[k] = dp[k] + times[job][k]
        return dp[m - 1]

    totals = [(sum(times[j]), j) for j in range(n)]
    totals.sort(key=lambda x: (-x[0], x[1]))
    order = [j for _, j in totals]

    if n <= 2:
        return order

    c1 = [order[0], order[1]]
    c2 = [order[1], order[0]]
    curr_seq = c1 if calc_makespan(c1) <= calc_makespan(c2) else c2

    for i in range(2, n):
        job = order[i]
        best_cand = None
        best_ms = float("inf")
        for pos in range(i + 1):
            cand = curr_seq[:pos] + [job] + curr_seq[pos:]
            ms = calc_makespan(cand)
            if ms < best_ms:
                best_ms = ms
                best_cand = cand
        curr_seq = best_cand

    max_iter = 15 if n <= 50 else (8 if n <= 80 else 4)
    d = min(4, max(1, n // 6))
    rng = random.Random(42)
    best_seq = list(curr_seq)
    best_ms = calc_makespan(best_seq)
    curr_ms = best_ms

    total_proc = sum(sum(times[j]) for j in range(n))
    temp = 0.5 * (total_proc / (n * m * 10.0))
    if temp < 1e-4:
        temp = 1.0

    for _ in range(max_iter):
        seq = list(curr_seq)
        remove_indices = sorted(rng.sample(range(len(seq)), d), reverse=True)
        removed_jobs = [seq.pop(idx) for idx in remove_indices]

        for r_job in removed_jobs:
            best_pos_cand = None
            best_pos_ms = float("inf")
            for pos in range(len(seq) + 1):
                cand = seq[:pos] + [r_job] + seq[pos:]
                ms = calc_makespan(cand)
                if ms < best_pos_ms:
                    best_pos_ms = ms
                    best_pos_cand = cand
            seq = best_pos_cand

        cand_ms = calc_makespan(seq)

        if cand_ms < curr_ms:
            curr_seq = list(seq)
            curr_ms = cand_ms
            if cand_ms < best_ms:
                best_seq = list(seq)
                best_ms = cand_ms
        else:
            diff = cand_ms - curr_ms
            prob = math.exp(-diff / temp)
            if rng.random() < prob:
                curr_seq = list(seq)
                curr_ms = cand_ms

    return best_seq
'''


BASELINES = {
    "palmer": palmer_code,
    "cds": cds_code,
    "neh": neh_code,
    "iterated_greedy": iterated_greedy_code,
}
