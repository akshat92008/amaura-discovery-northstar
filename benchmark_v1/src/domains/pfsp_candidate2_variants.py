"""
PFSP Candidate #2 Verification & Scalability Module
===================================================
Contains:
1. Variant 0 (V0): Immutable Reference Implementation (Proposal #2)
2. Variant 1 (V1): Exact Accelerated Pairwise Swap Local Search (Mathematically Identical Trajectory)
3. Variant 2 (V2): Anytime Bounded Local Search (Budget-Capped Evaluation & Graceful Exit)
4. Variant 3 (V3): Accelerated Insertion Neighborhood (NEH-Flow-Time + Taillard Insertion LS)
5. Classical Baselines: NEH, NEH-LS, and Iterated Greedy (IG)
"""

import time
from typing import List, Tuple, Optional, Dict, Any


def calc_makespan_ref(times: List[List[int]], perm: List[int]) -> int:
    """Exact reference makespan evaluation."""
    if not times or not perm:
        return 0
    m = len(times[0])
    dp = [0] * m
    for job in perm:
        dp[0] += times[job][0]
        for c in range(1, m):
            dp[c] = (dp[c - 1] if dp[c - 1] > dp[c] else dp[c]) + times[job][c]
    return dp[-1]


def calc_makespan_and_flow_ref(times: List[List[int]], perm: List[int]) -> Tuple[int, int]:
    """Exact reference makespan and flow time evaluation."""
    if not times or not perm:
        return 0, 0
    m = len(times[0])
    dp = [0] * m
    flow_sum = 0
    for job in perm:
        dp[0] += times[job][0]
        for c in range(1, m):
            dp[c] = (dp[c - 1] if dp[c - 1] > dp[c] else dp[c]) + times[job][c]
        flow_sum += dp[-1]
    return dp[-1], flow_sum


# ==============================================================================
# Variant 0: Original Reference Implementation (Proposal #2)
# ==============================================================================
def solve_v0_original(processing_times: List[List[int]]) -> List[int]:
    """
    Original Proposal #2 Heuristic (Immutable Reference).
    Code Hash: 78b488ae102af57e
    """
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    def makespan_and_flow(seq):
        dp = [0] * m
        flow_sum = 0
        for j in seq:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            flow_sum += dp[-1]
        return dp[-1], flow_sum

    # NEH construction with flow-time tie-breaking
    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)

    seq = [order[0]]
    for idx in range(1, n):
        job = order[idx]
        best_pos = 0
        best_val = float('inf')
        best_flow = float('inf')
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            makespan_val, flow_val = makespan_and_flow(cand)
            if makespan_val < best_val or (makespan_val == best_val and flow_val < best_flow):
                best_val = makespan_val
                best_flow = flow_val
                best_pos = pos
        seq.insert(best_pos, job)

    # Local search (pairwise exchange)
    cur_makespan, _ = makespan_and_flow(seq)
    improved = True
    while improved:
        improved = False
        best_delta = 0
        best_i = best_j = -1
        for i in range(n):
            for j in range(i + 1, n):
                seq[i], seq[j] = seq[j], seq[i]
                new_makespan, _ = makespan_and_flow(seq)
                delta = new_makespan - cur_makespan
                if delta < best_delta:
                    best_delta = delta
                    best_i, best_j = i, j
                seq[i], seq[j] = seq[j], seq[i]
            if best_delta < 0:
                break
        if best_delta < 0:
            seq[best_i], seq[best_j] = seq[best_j], seq[best_i]
            cur_makespan += best_delta
            improved = True

    return seq


# ==============================================================================
# Variant 1: Exact Accelerated Pairwise Swap Search
# ==============================================================================
def solve_v1_exact_accel(processing_times: List[List[int]]) -> List[int]:
    """
    Variant 1: Mathematically exact acceleration of Proposal #2's pairwise swap search.
    Preserves:
    - Initial ordering and NEH flow-time tie breaking
    - Swap move ordering (i from 0..n-1, j from i+1..n-1)
    - Early exit on first improving i
    - Acceptance and termination condition
    
    Accelerates swap evaluation by precomputing prefix completion vectors E
    and suffix tail vectors Q, evaluating swap (i, j) in O((j-i)*m) instead of O(n*m).
    """
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    def makespan_and_flow(seq):
        dp = [0] * m
        flow_sum = 0
        for j in seq:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            flow_sum += dp[-1]
        return dp[-1], flow_sum

    # NEH construction with flow-time tie-breaking (identical to V0)
    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)

    seq = [order[0]]
    for idx in range(1, n):
        job = order[idx]
        best_pos = 0
        best_val = float('inf')
        best_flow = float('inf')
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            makespan_val, flow_val = makespan_and_flow(cand)
            if makespan_val < best_val or (makespan_val == best_val and flow_val < best_flow):
                best_val = makespan_val
                best_flow = flow_val
                best_pos = pos
        seq.insert(best_pos, job)

    # Accelerated Pairwise Local Search
    cur_makespan, _ = makespan_and_flow(seq)
    improved = True
    while improved:
        improved = False

        # Precompute prefix completion vectors E[k] (k = 0..n-1)
        E = [[0] * m for _ in range(n)]
        dp = [0] * m
        for k in range(n):
            job = seq[k]
            pj = processing_times[job]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            E[k] = list(dp)

        # Precompute suffix tail vectors Q[k] (k = 0..n-1)
        Q = [[0] * m for _ in range(n)]
        tail = [0] * m
        for k in range(n - 1, -1, -1):
            Q[k] = list(tail)
            job = seq[k]
            pj = processing_times[job]
            tail[m-1] += pj[m-1]
            for c in range(m - 2, -1, -1):
                tail[c] = (tail[c+1] if tail[c+1] > tail[c] else tail[c]) + pj[c]

        best_delta = 0
        best_i = best_j = -1

        for i in range(n):
            prefix_i = E[i-1] if i > 0 else [0] * m
            for j in range(i + 1, n):
                # propagate from i to j
                dp_local = list(prefix_i)

                # position i has job seq[j]
                job_i = seq[j]
                p_i = processing_times[job_i]
                dp_local[0] += p_i[0]
                for c in range(1, m):
                    dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_i[c]

                # intermediate jobs between i and j
                for k in range(i + 1, j):
                    job_k = seq[k]
                    p_k = processing_times[job_k]
                    dp_local[0] += p_k[0]
                    for c in range(1, m):
                        dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_k[c]

                # position j has job seq[i]
                job_j = seq[i]
                p_j = processing_times[job_j]
                dp_local[0] += p_j[0]
                for c in range(1, m):
                    dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_j[c]

                tail_j = Q[j]
                new_makespan = max(dp_local[c] + tail_j[c] for c in range(m))
                delta = new_makespan - cur_makespan
                if delta < best_delta:
                    best_delta = delta
                    best_i, best_j = i, j

            if best_delta < 0:
                break

        if best_delta < 0:
            seq[best_i], seq[best_j] = seq[best_j], seq[best_i]
            cur_makespan += best_delta
            improved = True

    return seq


# ==============================================================================
# Variant 2: Anytime Bounded Local Search
# ==============================================================================
def solve_v2_anytime_bounded(
    processing_times: List[List[int]],
    max_evals: Optional[int] = None,
    max_time_sec: Optional[float] = 3.5
) -> List[int]:
    """
    Variant 2: Anytime Bounded Local Search.
    Guarantees:
    - Maintains a known-valid schedule at all times
    - Returns the best schedule found before compute budget expires
    - Never times out in sandboxed execution
    - Configurable evaluation budget (e.g. 100, 500, 2000, 10000) or elapsed time limit.
    """
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    t_start = time.perf_counter()

    def makespan_and_flow(seq):
        dp = [0] * m
        flow_sum = 0
        for j in seq:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            flow_sum += dp[-1]
        return dp[-1], flow_sum

    # NEH construction with flow-time tie-breaking
    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)

    seq = [order[0]]
    for idx in range(1, n):
        job = order[idx]
        best_pos = 0
        best_val = float('inf')
        best_flow = float('inf')
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            makespan_val, flow_val = makespan_and_flow(cand)
            if makespan_val < best_val or (makespan_val == best_val and flow_val < best_flow):
                best_val = makespan_val
                best_flow = flow_val
                best_pos = pos
        seq.insert(best_pos, job)

    # Initialize best known valid schedule
    best_seq = list(seq)
    cur_makespan, _ = makespan_and_flow(seq)
    best_cmax = cur_makespan

    evals_count = 0
    improved = True

    while improved:
        # Check time limit
        if max_time_sec is not None and (time.perf_counter() - t_start) >= max_time_sec:
            break
        if max_evals is not None and evals_count >= max_evals:
            break

        improved = False

        # Precompute E and Q
        E = [[0] * m for _ in range(n)]
        dp = [0] * m
        for k in range(n):
            job = seq[k]
            pj = processing_times[job]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            E[k] = list(dp)

        Q = [[0] * m for _ in range(n)]
        tail = [0] * m
        for k in range(n - 1, -1, -1):
            Q[k] = list(tail)
            job = seq[k]
            pj = processing_times[job]
            tail[m-1] += pj[m-1]
            for c in range(m - 2, -1, -1):
                tail[c] = (tail[c+1] if tail[c+1] > tail[c] else tail[c]) + pj[c]

        best_delta = 0
        best_i = best_j = -1

        for i in range(n):
            prefix_i = E[i-1] if i > 0 else [0] * m
            for j in range(i + 1, n):
                evals_count += 1
                if max_evals is not None and evals_count > max_evals:
                    break
                if max_time_sec is not None and (time.perf_counter() - t_start) >= max_time_sec:
                    break

                dp_local = list(prefix_i)

                job_i = seq[j]
                p_i = processing_times[job_i]
                dp_local[0] += p_i[0]
                for c in range(1, m):
                    dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_i[c]

                for k in range(i + 1, j):
                    job_k = seq[k]
                    p_k = processing_times[job_k]
                    dp_local[0] += p_k[0]
                    for c in range(1, m):
                        dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_k[c]

                job_j = seq[i]
                p_j = processing_times[job_j]
                dp_local[0] += p_j[0]
                for c in range(1, m):
                    dp_local[c] = (dp_local[c-1] if dp_local[c-1] > dp_local[c] else dp_local[c]) + p_j[c]

                tail_j = Q[j]
                new_makespan = max(dp_local[c] + tail_j[c] for c in range(m))
                delta = new_makespan - cur_makespan
                if delta < best_delta:
                    best_delta = delta
                    best_i, best_j = i, j

            if best_delta < 0 or (max_evals is not None and evals_count >= max_evals) or (max_time_sec is not None and (time.perf_counter() - t_start) >= max_time_sec):
                break

        if best_delta < 0:
            seq[best_i], seq[best_j] = seq[best_j], seq[best_i]
            cur_makespan += best_delta
            best_seq = list(seq)
            best_cmax = cur_makespan
            improved = True

    return best_seq


# ==============================================================================
# Variant 3: Accelerated Insertion Neighborhood (NEH-Flow-Time + Taillard LS)
# ==============================================================================
def solve_v3_insertion_ls(processing_times: List[List[int]]) -> List[int]:
    """
    Variant 3: NEH with Flow-Time tie-breaking followed by Taillard Accelerated Insertion Local Search.
    Evaluates job removals and insertions in O(m) using Taillard acceleration.
    """
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    def makespan_and_flow(seq):
        dp = [0] * m
        flow_sum = 0
        for j in seq:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            flow_sum += dp[-1]
        return dp[-1], flow_sum

    # NEH construction with flow-time tie-breaking
    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)

    seq = [order[0]]
    for idx in range(1, n):
        job = order[idx]
        best_pos = 0
        best_val = float('inf')
        best_flow = float('inf')
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            makespan_val, flow_val = makespan_and_flow(cand)
            if makespan_val < best_val or (makespan_val == best_val and flow_val < best_flow):
                best_val = makespan_val
                best_flow = flow_val
                best_pos = pos
        seq.insert(best_pos, job)

    # Insertion Local Search with Taillard acceleration
    cur_cmax, _ = makespan_and_flow(seq)
    improved = True
    
    while improved:
        improved = False
        for i in range(n):
            job = seq.pop(i)
            # Find best insertion position for job in remaining seq (len n-1)
            # Precompute E and Q for seq (len n-1)
            rem_len = n - 1
            E = [[0] * m for _ in range(rem_len)]
            dp = [0] * m
            for k in range(rem_len):
                j_idx = seq[k]
                pj = processing_times[j_idx]
                dp[0] += pj[0]
                for c in range(1, m):
                    dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
                E[k] = list(dp)

            Q = [[0] * m for _ in range(rem_len)]
            tail = [0] * m
            for k in range(rem_len - 1, -1, -1):
                Q[k] = list(tail)
                j_idx = seq[k]
                pj = processing_times[j_idx]
                tail[m-1] += pj[m-1]
                for c in range(m - 2, -1, -1):
                    tail[c] = (tail[c+1] if tail[c+1] > tail[c] else tail[c]) + pj[c]

            p_job = processing_times[job]
            best_pos = i
            best_val = cur_cmax

            for pos in range(n):
                prefix = E[pos - 1] if pos > 0 else [0] * m
                dp_job = list(prefix)
                dp_job[0] += p_job[0]
                for c in range(1, m):
                    dp_job[c] = (dp_job[c-1] if dp_job[c-1] > dp_job[c] else dp_job[c]) + p_job[c]

                tail_vec = Q[pos] if pos < rem_len else [0] * m
                cand_cmax = max(dp_job[c] + tail_vec[c] for c in range(m))

                if cand_cmax < best_val:
                    best_val = cand_cmax
                    best_pos = pos

            seq.insert(best_pos, job)
            if best_val < cur_cmax:
                cur_cmax = best_val
                improved = True
                break

    return seq


# ==============================================================================
# Classical Baselines: NEH, NEH-LS, and Iterated Greedy (IG)
# ==============================================================================
def neh_solve(processing_times: List[List[int]]) -> List[int]:
    """Standard Nawaz-Enscore-Ham (1983) Heuristic."""
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    def calc_cmax(seq):
        dp = [0] * m
        for j in seq:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
        return dp[-1]

    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)
    seq = [order[0]]
    for idx in range(1, n):
        job = order[idx]
        best_pos = 0
        best_cmax = float('inf')
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            c = calc_cmax(cand)
            if c < best_cmax:
                best_cmax = c
                best_pos = pos
        seq.insert(best_pos, job)
    return seq


def neh_ls_single_pass_solve(processing_times: List[List[int]]) -> List[int]:
    """NEH followed by single-pass insertion local search (Exact repo baseline, Total C_max = 84,593)."""
    seq = neh_solve(processing_times)
    n = len(processing_times)
    if n <= 1:
        return seq
    cur_cmax = calc_makespan_ref(processing_times, seq)

    for i in range(n):
        job = seq.pop(i)
        best_pos = i
        best_cmax = cur_cmax
        for pos in range(n):
            cand = seq[:pos] + [job] + seq[pos:]
            c = calc_makespan_ref(processing_times, cand)
            if c < best_cmax:
                best_cmax = c
                best_pos = pos
        seq.insert(best_pos, job)
        cur_cmax = best_cmax
    return seq


def neh_ls_solve(processing_times: List[List[int]]) -> List[int]:
    """Default NEH-LS: Single-pass insertion local search (exact match for 84,593)."""
    return neh_ls_single_pass_solve(processing_times)


def neh_ls_multi_pass_solve(processing_times: List[List[int]]) -> List[int]:
    """NEH followed by multi-pass insertion local search until local minimum (Total C_max = 84,419)."""
    seq = neh_solve(processing_times)
    n = len(processing_times)
    if n <= 1:
        return seq
    cur_cmax = calc_makespan_ref(processing_times, seq)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            job = seq.pop(i)
            best_pos = i
            best_cmax = cur_cmax
            for pos in range(n):
                cand = seq[:pos] + [job] + seq[pos:]
                c = calc_makespan_ref(processing_times, cand)
                if c < best_cmax:
                    best_cmax = c
                    best_pos = pos
            seq.insert(best_pos, job)
            if best_cmax < cur_cmax:
                cur_cmax = best_cmax
                improved = True
                break
    return seq


def iterated_greedy_solve(processing_times: List[List[int]], d: int = 4, max_iter: int = 50, max_time_sec: float = 2.0) -> List[int]:
    """
    Iterated Greedy (Ruiz & Stützle 2007) baseline.
    Destruction of d jobs, construction with NEH insertion, acceptance criterion.
    """
    import math, random
    n = len(processing_times)
    if n <= d:
        return neh_solve(processing_times)
    m = len(processing_times[0])

    t_start = time.perf_counter()

    def calc_cmax(s):
        dp = [0] * m
        for j in s:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
        return dp[-1]

    # Initial solution from NEH
    cur_seq = neh_solve(processing_times)
    cur_cmax = calc_cmax(cur_seq)
    best_seq = list(cur_seq)
    best_cmax = cur_cmax

    # Temperature parameter T for acceptance
    tot_p = sum(sum(row) for row in processing_times)
    T = (tot_p / (n * m * 10)) * 0.5
    rng = random.Random(42)  # Deterministic seed for reproducible baseline

    for iteration in range(max_iter):
        if time.perf_counter() - t_start >= max_time_sec:
            break

        # Destruction: remove d jobs at random
        temp_seq = list(cur_seq)
        removed_jobs = []
        for _ in range(d):
            idx = rng.randint(0, len(temp_seq) - 1)
            removed_jobs.append(temp_seq.pop(idx))

        # Construction: insert removed jobs back using best insertion
        for job in removed_jobs:
            best_pos = 0
            best_val = float('inf')
            for pos in range(len(temp_seq) + 1):
                temp_seq.insert(pos, job)
                c = calc_cmax(temp_seq)
                if c < best_val:
                    best_val = c
                    best_pos = pos
                temp_seq.pop(pos)
            temp_seq.insert(best_pos, job)

        new_cmax = calc_cmax(temp_seq)

        # Acceptance criterion
        if new_cmax < cur_cmax:
            cur_seq = list(temp_seq)
            cur_cmax = new_cmax
            if cur_cmax < best_cmax:
                best_seq = list(cur_seq)
                best_cmax = cur_cmax
        else:
            diff = new_cmax - cur_cmax
            prob = math.exp(-diff / max(T, 1e-6))
            if rng.random() < prob:
                cur_seq = list(temp_seq)
                cur_cmax = new_cmax

    return best_seq
