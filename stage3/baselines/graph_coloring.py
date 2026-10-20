"""
Stage 3: Graph Coloring Baseline Implementations
================================================
Provides standard, battle-tested heuristic graph coloring algorithms:
1. Greedy (First-Fit natural order)
2. Welsh-Powell (Largest Degree First)
3. DSATUR (Degree of Saturation, Daniel Brélaz 1979)
4. Recursive Largest First (RLF, Frank Leighton 1979)
5. Iterated Greedy / Local Search (Culberson 1992)

Each implementation conforms to the standard evaluator interface:
    def color_graph(adj: list[list[int]]) -> list[int]
"""

from typing import List, Set


def greedy_first_fit(adj: List[List[int]]) -> List[int]:
    """Greedy First-Fit coloring with natural ordering."""
    n = len(adj)
    if n == 0:
        return []

    colors = [-1] * n
    for u in range(n):
        neighbor_colors: Set[int] = {colors[v] for v in adj[u] if colors[v] != -1}
        c = 0
        while c in neighbor_colors:
            c += 1
        colors[u] = c

    return colors


def welsh_powell(adj: List[List[int]]) -> List[int]:
    """Welsh-Powell (Largest Degree First) graph coloring."""
    n = len(adj)
    if n == 0:
        return []

    order = sorted(range(n), key=lambda u: len(adj[u]), reverse=True)
    colors = [-1] * n

    for u in order:
        neighbor_colors = {colors[v] for v in adj[u] if colors[v] != -1}
        c = 0
        while c in neighbor_colors:
            c += 1
        colors[u] = c

    return colors


def dsatur(adj: List[List[int]]) -> List[int]:
    """
    DSATUR (Degree of Saturation) algorithm by Daniel Brélaz (1979).
    Selects uncolored vertex with highest saturation degree (distinct colors among colored neighbors).
    Ties broken by uncolored degree.
    """
    n = len(adj)
    if n == 0:
        return []

    adj_sets = [set(adj[u]) for u in range(n)]
    colors = [-1] * n
    degrees = [len(adj_sets[u]) for u in range(n)]

    # sat_colors[u] is set of colors assigned to colored neighbors of u
    sat_colors: List[Set[int]] = [set() for _ in range(n)]
    uncolored_count = n

    while uncolored_count > 0:
        # Pick vertex with max saturation degree, tie-break by uncolored degree
        best_u = -1
        best_sat = -1
        best_deg = -1

        for u in range(n):
            if colors[u] == -1:
                sat = len(sat_colors[u])
                deg = degrees[u]
                if sat > best_sat or (sat == best_sat and deg > best_deg):
                    best_sat = sat
                    best_deg = deg
                    best_u = u

        # Assign lowest available color
        c = 0
        while c in sat_colors[best_u]:
            c += 1
        colors[best_u] = c
        uncolored_count -= 1

        # Update neighbors' saturation sets
        for v in adj_sets[best_u]:
            if colors[v] == -1:
                sat_colors[v].add(c)

    return colors


def recursive_largest_first(adj: List[List[int]]) -> List[int]:
    """
    Recursive Largest First (RLF) algorithm by Frank Leighton (1979).
    Colors the graph by constructing maximal independent sets one color at a time.
    """
    n = len(adj)
    if n == 0:
        return []

    adj_sets = [set(adj[u]) for u in range(n)]
    colors = [-1] * n
    uncolored = set(range(n))
    current_color = 0

    while uncolored:
        # Step 1: Select vertex in uncolored with maximum neighbors in uncolored
        first_v = max(uncolored, key=lambda u: len(adj_sets[u] & uncolored))
        mis = [first_v]
        uncolored.remove(first_v)

        # Candidates for same color: uncolored vertices not adjacent to any vertex in mis
        candidates = set(uncolored) - adj_sets[first_v]
        # Forbidden: uncolored vertices adjacent to vertices in mis
        forbidden = set(uncolored) & adj_sets[first_v]

        while candidates:
            # Pick vertex in candidates with maximum neighbors in forbidden
            next_v = max(candidates, key=lambda u: len(adj_sets[u] & forbidden))
            mis.append(next_v)
            uncolored.remove(next_v)
            candidates.remove(next_v)
            # Update forbidden and candidates
            new_forbidden = adj_sets[next_v] & uncolored
            forbidden |= new_forbidden
            candidates -= adj_sets[next_v]

        for u in mis:
            colors[u] = current_color
        current_color += 1

    return colors


def iterated_greedy(adj: List[List[int]], iterations: int = 20) -> List[int]:
    """
    Iterated Greedy (Culberson 1992):
    Permutes vertices grouped by color class and recolors with First-Fit.
    """
    n = len(adj)
    if n == 0:
        return []

    best_colors = dsatur(adj)
    best_k = len(set(best_colors))

    curr_colors = list(best_colors)

    for _ in range(iterations):
        # Group vertices by color
        classes: dict[int, list[int]] = {}
        for u, c in enumerate(curr_colors):
            classes.setdefault(c, []).append(u)

        # Order color classes in descending size
        sorted_classes = sorted(classes.values(), key=len, reverse=True)
        order = [u for cls in sorted_classes for u in cls]

        new_colors = [-1] * n
        for u in order:
            nbr_colors = {new_colors[v] for v in adj[u] if new_colors[v] != -1}
            c = 0
            while c in nbr_colors:
                c += 1
            new_colors[u] = c

        k = len(set(new_colors))
        if k < best_k:
            best_k = k
            best_colors = new_colors
        curr_colors = new_colors

    return best_colors


# Default solver alias
color_graph = dsatur
