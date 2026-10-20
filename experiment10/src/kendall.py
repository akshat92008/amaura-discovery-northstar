"""
Experiment #10: Exact Normalized Kendall-Tau Permutation Distance
=================================================================
Calculates normalized Kendall-Tau distance between two permutations of n elements.
Formula:
    discordant_pairs / (n * (n - 1) / 2)
Guaranteed range: [0.0, 1.0].
"""

from typing import Sequence, List


def kendall_tau_distance(p1: Sequence[int], p2: Sequence[int]) -> float:
    n = len(p1)
    if n <= 1:
        return 0.0

    if len(p2) != n:
        raise ValueError(f"Permutations must have identical lengths: {len(p1)} != {len(p2)}")

    pos2 = {job: idx for idx, job in enumerate(p2)}
    pos1 = {job: idx for idx, job in enumerate(p1)}

    if set(pos1.keys()) != set(pos2.keys()):
        raise ValueError("Permutations must contain the exact same set of elements.")

    jobs = list(pos1.keys())
    discordant_count = 0

    for i in range(n):
        job_a = jobs[i]
        for j in range(i + 1, n):
            job_b = jobs[j]
            a_before_b_in_p1 = (pos1[job_a] < pos1[job_b])
            a_before_b_in_p2 = (pos2[job_a] < pos2[job_b])
            if a_before_b_in_p1 != a_before_b_in_p2:
                discordant_count += 1

    total_pairs = n * (n - 1) // 2
    return float(discordant_count) / float(total_pairs)


# Alias
normalized_kendall_tau = kendall_tau_distance


def mean_behavioral_distance(sig1: List[List[int]], sig2: List[List[int]]) -> float:
    if len(sig1) != len(sig2):
        raise ValueError(f"Signatures must have identical instance counts: {len(sig1)} != {len(sig2)}")
    if not sig1:
        return 0.0

    total_dist = 0.0
    for p1, p2 in zip(sig1, sig2):
        total_dist += kendall_tau_distance(p1, p2)
    return total_dist / float(len(sig1))
