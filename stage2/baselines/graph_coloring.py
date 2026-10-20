"""
Stage 2: Graph Coloring Baselines
=================================
Pre-registered, reproducible implementations of classical heuristics:
1. DSATUR (Brélaz, 1979)
2. RLF (Recursive Largest First, Leighton, 1979)
3. TabuCol (Hertz & de Werra, 1987)
"""

import math
import random
from typing import List, Dict, Any, Tuple, Set


def dsatur_code() -> str:
    return '''def color_graph(adj: list[list[int]]) -> list[int]:
    """
    DSATUR Algorithm (Brélaz, 1979):
    At each step, select uncolored vertex with maximum saturation degree.
    Ties broken by maximum degree in uncolored subgraph.
    Assign smallest feasible color (First-Fit).
    """
    n = len(adj)
    if n == 0:
        return []
    colors = [-1] * n
    saturation = [0] * n
    neighbor_colors = [set() for _ in range(n)]
    uncolored = set(range(n))

    while uncolored:
        best_v = None
        best_key = (-1, -1)
        for v in uncolored:
            sat = saturation[v]
            uncolored_deg = len(set(adj[v]) & uncolored)
            key = (sat, uncolored_deg)
            if key > best_key:
                best_key = key
                best_v = v

        used = neighbor_colors[best_v]
        c = 0
        while c in used:
            c += 1
        colors[best_v] = c
        uncolored.remove(best_v)

        for u in adj[best_v]:
            if c not in neighbor_colors[u]:
                neighbor_colors[u].add(c)
                saturation[u] += 1

    return colors
'''


def rlf_code() -> str:
    return '''def color_graph(adj: list[list[int]]) -> list[int]:
    """
    Recursive Largest First (RLF, Leighton 1979):
    Extracts maximal independent sets (color classes) iteratively.
    For each color class:
      1. Choose vertex with max degree in remaining uncolored subgraph.
      2. Greedily add vertices that share maximum neighbors with already-incompatible uncolored vertices.
    """
    n = len(adj)
    if n == 0:
        return []
    colors = [-1] * n
    uncolored = set(range(n))
    c = 0

    while uncolored:
        # Pick vertex with max degree in uncolored subgraph
        best_v = max(uncolored, key=lambda v: len(set(adj[v]) & uncolored))
        C = [best_v]
        U1 = set(adj[best_v]) & uncolored
        U2 = uncolored - {best_v} - U1

        while U2:
            # Pick u in U2 maximizing edges to U1
            best_u = max(U2, key=lambda u: (len(set(adj[u]) & U1), -len(set(adj[u]) & U2)))
            C.append(best_u)
            U2.remove(best_u)
            new_u1 = set(adj[best_u]) & U2
            U1.update(new_u1)
            U2 -= new_u1

        for v in C:
            colors[v] = c
            uncolored.remove(v)
        c += 1

    return colors
'''


def tabucol_code() -> str:
    return '''def color_graph(adj: list[list[int]]) -> list[int]:
    """
    TabuCol (Hertz & de Werra, 1987):
    Tabu Search for Graph Coloring.
    1. Initialize valid coloring using DSATUR.
    2. Try to reduce color count k = k_best - 1.
    3. Run bounded Tabu Search minimizing edge conflicts.
    4. If 0 conflicts achieved, record new best valid coloring and decrement k.
    5. Terminate when target is reached, or max iterations exhausted.
    """
    import random

    n = len(adj)
    if n == 0:
        return []

    # 1. Initial valid coloring via fast DSATUR
    colors = [-1] * n
    saturation = [0] * n
    neighbor_colors = [set() for _ in range(n)]
    uncolored = set(range(n))

    while uncolored:
        best_v = None
        best_key = (-1, -1)
        for v in uncolored:
            key = (saturation[v], len(set(adj[v]) & uncolored))
            if key > best_key:
                best_key = key
                best_v = v

        used = neighbor_colors[best_v]
        c = 0
        while c in used:
            c += 1
        colors[best_v] = c
        uncolored.remove(best_v)

        for u in adj[best_v]:
            if c not in neighbor_colors[u]:
                neighbor_colors[u].add(c)
                saturation[u] += 1

    best_valid_colors = list(colors)
    k_current = len(set(best_valid_colors))
    if k_current <= 2:
        return best_valid_colors

    rng = random.Random(42)

    # 2. Try to find a valid coloring with k = k_current - 1
    target_k = k_current - 1
    max_k_attempts = 2  # Limit k reduction attempts for runtime bound

    while target_k >= 2 and max_k_attempts > 0:
        max_k_attempts -= 1
        # Map any vertex with color >= target_k to random color in [0, target_k - 1]
        curr_colors = [c if c < target_k else rng.randint(0, target_k - 1) for c in best_valid_colors]

        # Count initial conflicts
        # gamma[v][c] = number of neighbors of v with color c
        gamma = [[0] * target_k for _ in range(n)]
        conflicts = 0
        for u in range(n):
            for v in adj[u]:
                gamma[u][curr_colors[v]] += 1
            if curr_colors[u] < target_k:
                conflicts += gamma[u][curr_colors[u]]
        conflicts //= 2  # each edge counted twice

        if conflicts == 0:
            best_valid_colors = list(curr_colors)
            target_k -= 1
            continue

        # Tabu Search parameters
        tabu_tenure = [[0] * target_k for _ in range(n)]
        max_iterations = min(400, 10 * n)
        current_iter = 0

        while current_iter < max_iterations and conflicts > 0:
            current_iter += 1

            # Identify conflicting vertices
            conflicting_nodes = [u for u in range(n) if gamma[u][curr_colors[u]] > 0]
            if not conflicting_nodes:
                break

            best_delta = float('inf')
            best_moves = []

            for u in conflicting_nodes:
                old_c = curr_colors[u]
                current_cost = gamma[u][old_c]
                for new_c in range(target_k):
                    if new_c == old_c:
                        continue
                    delta = gamma[u][new_c] - current_cost
                    is_tabu = tabu_tenure[u][new_c] > current_iter
                    aspiration = (conflicts + delta < 0)  # aspiration criterion: improves global best

                    if not is_tabu or aspiration:
                        if delta < best_delta:
                            best_delta = delta
                            best_moves = [(u, new_c)]
                        elif delta == best_delta:
                            best_moves.append((u, new_c))

            if not best_moves:
                # All candidate moves are tabu; pick any conflicting vertex and change color
                u = rng.choice(conflicting_nodes)
                new_c = (curr_colors[u] + rng.randint(1, target_k - 1)) % target_k
                delta = gamma[u][new_c] - gamma[u][curr_colors[u]]
            else:
                u, new_c = rng.choice(best_moves)
                delta = best_delta

            # Apply move
            old_c = curr_colors[u]
            curr_colors[u] = new_c
            conflicts += delta

            # Update gamma table for neighbors
            for v in adj[u]:
                gamma[v][old_c] -= 1
                gamma[v][new_c] += 1

            # Set tabu tenure
            tenure = rng.randint(5, 10) + int(0.6 * conflicts)
            tabu_tenure[u][old_c] = current_iter + tenure

            if conflicts == 0:
                best_valid_colors = list(curr_colors)
                target_k -= 1
                break

    return best_valid_colors
'''


GRAPH_COLORING_BASELINES = {
    "dsatur": {
        "name": "DSATUR (Brélaz, 1979)",
        "code": dsatur_code()
    },
    "rlf": {
        "name": "Recursive Largest First (RLF, Leighton 1979)",
        "code": rlf_code()
    },
    "tabucol": {
        "name": "TabuCol (Hertz & de Werra, 1987)",
        "code": tabucol_code()
    }
}
