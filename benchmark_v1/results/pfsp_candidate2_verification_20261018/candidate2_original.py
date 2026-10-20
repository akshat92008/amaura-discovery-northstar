def solve(processing_times):
    """
    Permutation Flow-Shop Scheduling heuristic:
    - Construct initial solution using NEH with a composite initial order
      (total processing time descending) and tie-breaking by total flow time.
    - Apply iterative pairwise exchange local search until no improvement.
    Returns a permutation of job indices minimizing the makespan.
    """
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    # ----- helper functions -----
    def makespan_and_flow(seq):
        """Return (makespan, total_flow_time) for a given sequence."""
        dp = [0] * m
        flow_sum = 0
        for j in seq:
            pj = processing_times[j]
            dp[0] += pj[0]
            for c in range(1, m):
                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + pj[c]
            flow_sum += dp[-1]          # completion time of job j on last machine
        return dp[-1], flow_sum

    # ----- NEH construction -----
    # initial order: descending total processing time (can be extended with other criteria)
    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)

    seq = [order[0]]
    for idx in range(1, n):
        job = order[idx]
        best_pos = 0
        best_val = float('inf')
        best_flow = float('inf')
        # evaluate all insertion positions
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            makespan_val, flow_val = makespan_and_flow(cand)
            if makespan_val < best_val or (makespan_val == best_val and flow_val < best_flow):
                best_val = makespan_val
                best_flow = flow_val
                best_pos = pos
        seq.insert(best_pos, job)

    # ----- local search (pairwise exchange) -----
    cur_makespan, _ = makespan_and_flow(seq)
    improved = True
    while improved:
        improved = False
        best_delta = 0
        best_i = best_j = -1
        # examine all swaps
        for i in range(n):
            for j in range(i + 1, n):
                seq[i], seq[j] = seq[j], seq[i]
                new_makespan, _ = makespan_and_flow(seq)
                delta = new_makespan - cur_makespan
                if delta < best_delta:   # improvement (negative delta)
                    best_delta = delta
                    best_i, best_j = i, j
                # revert swap
                seq[i], seq[j] = seq[j], seq[i]
            if best_delta < 0:   # early exit if we already found an improving swap
                break
        if best_delta < 0:
            # apply the best improving swap
            seq[best_i], seq[best_j] = seq[best_j], seq[best_i]
            cur_makespan += best_delta   # update makespan
            improved = True

    return seq