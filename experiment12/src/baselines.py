"""
Experiment #11: Classical Human Baselines for PFSP
==================================================
Implements:
1. Palmer's Slope Heuristic (1965)
2. Campbell-Dudek-Smith (CDS 1970)
3. Nawaz-Enscore-Ham (NEH 1983)
4. Bounded Iterated Greedy (Ruiz & Stutzle 2007)

Evaluates on Dev (30 instances) and Hidden (120 instances).
"""

import json
import os
import sys
from typing import Dict, Any, List

from experiment11.src.evaluator import PFSPEvaluator


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
            idx = rng.randrange(len(cand_seq))
            removed_jobs.append(cand_seq.pop(idx))

        for job in removed_jobs:
            best_pos = 0
            best_val = float("inf")
            for pos in range(len(cand_seq) + 1):
                test_seq = cand_seq[:pos] + [job] + cand_seq[pos:]
                c = calc_makespan(test_seq)
                eval_count += 1
                if c < best_val:
                    best_val = c
                    best_pos = pos
            cand_seq.insert(best_pos, job)

        cand_cmax = calc_makespan(cand_seq)
        eval_count += 1

        if cand_cmax < best_cmax:
            best_cmax = cand_cmax
            best_seq = list(cand_seq)
            current_seq = list(cand_seq)
        elif cand_cmax <= calc_makespan(current_seq) or rng.random() < math.exp((calc_makespan(current_seq) - cand_cmax) / max(temperature, 1e-4)):
            current_seq = list(cand_seq)

    return best_seq
'''


def run_baselines_evaluation():
    evaluator = PFSPEvaluator(scale_aware_base_ms=1000.0, scale_aware_per_nm_ms=2.0)

    with open("experiment11/benchmarks/dev.json") as f:
        dev_instances = json.load(f)

    with open("experiment11/benchmarks/hidden.json") as f:
        hidden_instances = json.load(f)

    baselines = {
        "palmer": palmer_code(),
        "cds": cds_code(),
        "neh": neh_code(),
        "iterated_greedy": iterated_greedy_code()
    }

    dev_results = {}
    print("Evaluating baselines on Development benchmark (30 instances)...")
    for name, code in baselines.items():
        res = evaluator.evaluate_solver_code(code, dev_instances)
        dev_results[name] = {
            "is_valid": res["is_valid"],
            "total_makespan": res["total_makespan"],
            "mean_makespan": res["mean_makespan"],
            "runtime_ms": res["runtime_ms"],
            "error": res["error"]
        }
        print(f"  [{name:15s}] Dev Total Makespan: {res['total_makespan']:8d} | Mean: {res['mean_makespan']:7.2f} | Time: {res['runtime_ms']:6.1f}ms")

    with open("experiment11/results/baselines_dev.json", "w") as f:
        json.dump(dev_results, f, indent=2)

    hidden_results = {}
    print("\nEvaluating baselines on Hidden benchmark (120 instances)...")
    for name, code in baselines.items():
        res = evaluator.evaluate_solver_code(code, hidden_instances)
        hidden_results[name] = {
            "is_valid": res["is_valid"],
            "total_makespan": res["total_makespan"],
            "mean_makespan": res["mean_makespan"],
            "runtime_ms": res["runtime_ms"],
            "error": res["error"]
        }
        print(f"  [{name:15s}] Hidden Total Makespan: {res['total_makespan']:8d} | Mean: {res['mean_makespan']:7.2f} | Time: {res['runtime_ms']:6.1f}ms")

    with open("experiment11/results/baselines_hidden.json", "w") as f:
        json.dump(hidden_results, f, indent=2)

    print("\nBaseline evaluations saved successfully!")


if __name__ == "__main__":
    run_baselines_evaluation()
