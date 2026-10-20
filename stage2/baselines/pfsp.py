"""
Stage 2: PFSP Baselines
=======================
Pre-registered, reproducible implementations of classical heuristics:
1. NEH (Nawaz, Enscore, Ham 1983)
2. Iterated Greedy (Ruiz & Stützle 2007)
"""

from typing import Dict, Any


def neh_code() -> str:
    return '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    """
    Nawaz-Enscore-Ham (NEH, 1983) Heuristic:
    1. Order jobs by total processing time descending.
    2. Sequentially insert jobs into best partial position minimizing makespan.
    """
    n = len(times)
    if n == 0:
        return []
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

    total_times = [(sum(times[j]), j) for j in range(n)]
    total_times.sort(key=lambda x: (-x[0], x[1]))
    order = [j for _, j in total_times]

    current_seq = [order[0]]

    for i in range(1, n):
        job_to_insert = order[i]
        best_pos = 0
        best_val = float("inf")

        for pos in range(i + 1):
            cand = current_seq[:pos] + [job_to_insert] + current_seq[pos:]
            cmax = calc_partial_makespan(cand)
            if cmax < best_val:
                best_val = cmax
                best_pos = pos

        current_seq.insert(best_pos, job_to_insert)

    return current_seq
'''


def iterated_greedy_code() -> str:
    return '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    """
    Bounded Iterated Greedy (Ruiz & Stützle, 2007):
    1. Initial sequence via NEH.
    2. Destruction: remove d jobs at random.
    3. Construction: reinsert removed jobs using NEH insertion.
    4. Acceptance criterion: Metropolis condition with cooling.
    """
    import math
    import random

    n = len(times)
    if n == 0:
        return []
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

    # NEH Seed
    total_times = [(sum(times[j]), j) for j in range(n)]
    total_times.sort(key=lambda x: (-x[0], x[1]))
    order = [j for _, j in total_times]

    current_seq = [order[0]]
    for i in range(1, n):
        job = order[i]
        best_pos = 0
        best_val = float("inf")
        for pos in range(i + 1):
            cand = current_seq[:pos] + [job] + current_seq[pos:]
            cmax = calc_makespan(cand)
            if cmax < best_val:
                best_val = cmax
                best_pos = pos
        current_seq.insert(best_pos, job)

    best_seq = list(current_seq)
    best_cmax = calc_makespan(best_seq)

    # Iterated Greedy Destruction/Construction
    d = min(4, max(2, n // 5))
    max_evals = min(300, 10 * n)
    eval_count = 0
    temperature = 0.5 * (sum(total_times[j][0] for j in range(n)) / (n * m * 10)) + 1e-6
    rng = random.Random(42)

    while eval_count < max_evals:
        cand_seq = list(current_seq)
        removed_jobs = []
        for _ in range(d):
            if not cand_seq:
                break
            idx = rng.randint(0, len(cand_seq) - 1)
            removed_jobs.append(cand_seq.pop(idx))

        # Re-insertion
        for job in removed_jobs:
            best_pos = 0
            best_val = float("inf")
            for pos in range(len(cand_seq) + 1):
                trial_seq = cand_seq[:pos] + [job] + cand_seq[pos:]
                cmax = calc_makespan(trial_seq)
                eval_count += 1
                if cmax < best_val:
                    best_val = cmax
                    best_pos = pos
            cand_seq.insert(best_pos, job)

        cand_cmax = calc_makespan(cand_seq)
        eval_count += 1

        if cand_cmax < best_cmax:
            best_cmax = cand_cmax
            best_seq = list(cand_seq)
            current_seq = list(cand_seq)
        elif cand_cmax <= calc_makespan(current_seq):
            current_seq = list(cand_seq)
        else:
            diff = cand_cmax - calc_makespan(current_seq)
            prob = math.exp(-diff / temperature)
            if rng.random() < prob:
                current_seq = list(cand_seq)

    return best_seq
'''


PFSP_BASELINES = {
    "neh": {
        "name": "NEH (Nawaz, Enscore, Ham 1983)",
        "code": neh_code()
    },
    "iterated_greedy": {
        "name": "Iterated Greedy (Ruiz & Stützle 2007)",
        "code": iterated_greedy_code()
    }
}
