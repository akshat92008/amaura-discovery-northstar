"""
Experiment #9: Kendall-Tau Permutation Distance Implementation
==============================================================
Implements the exact mathematical definition of Kendall-Tau rank distance
for permutations of n elements without chained comparisons.
"""

from typing import List, Sequence


def kendall_tau_distance(p1: Sequence[int], p2: Sequence[int]) -> float:
    """
    Computes the normalized Kendall-Tau distance between two permutations p1 and p2.
    
    Formula:
        Number of discordant pairs / (n * (n - 1) / 2)
        
    Result is strictly in [0.0, 1.0]:
        0.0 = identical permutation order
        1.0 = completely reversed permutation order
    """
    n = len(p1)
    if n <= 1:
        return 0.0

    if len(p2) != n:
        raise ValueError(f"Permutations must have identical lengths: {len(p1)} != {len(p2)}")

    # 1. Construct position map for p2: pos2[job] = index of job in p2
    pos2 = {job: idx for idx, job in enumerate(p2)}
    
    # 2. Construct position map for p1: pos1[job] = index of job in p1
    pos1 = {job: idx for idx, job in enumerate(p1)}

    # Ensure all elements in p1 exist in p2
    if set(pos1.keys()) != set(pos2.keys()):
        raise ValueError("Permutations must contain the exact same set of elements.")

    # 3. Iterate through every unordered pair of jobs (a, b)
    jobs = list(pos1.keys())
    discordant_count = 0

    for i in range(n):
        job_a = jobs[i]
        for j in range(i + 1, n):
            job_b = jobs[j]
            # Determine order relation in p1
            a_before_b_in_p1 = (pos1[job_a] < pos1[job_b])
            # Determine order relation in p2
            a_before_b_in_p2 = (pos2[job_a] < pos2[job_b])

            # Check discordance without chained comparisons
            if a_before_b_in_p1 != a_before_b_in_p2:
                discordant_count += 1

    total_pairs = n * (n - 1) // 2
    return float(discordant_count) / float(total_pairs)


def mean_behavioral_distance(
    sig1: List[List[int]], 
    sig2: List[List[int]]
) -> float:
    """
    Computes the mean Kendall-Tau distance between two algorithms across
    a benchmark suite of K instances.
    sig1[k] is the output permutation of algorithm 1 on instance k.
    sig2[k] is the output permutation of algorithm 2 on instance k.
    """
    if len(sig1) != len(sig2):
        raise ValueError(f"Signatures must have identical instance counts: {len(sig1)} != {len(sig2)}")
    if not sig1:
        return 0.0

    total_dist = 0.0
    for p1, p2 in zip(sig1, sig2):
        total_dist += kendall_tau_distance(p1, p2)
    return total_dist / float(len(sig1))
