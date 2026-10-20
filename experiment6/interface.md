# Experiment #6: Candidate Interface Specification

**Domain:** Graph Coloring Dynamic Vertex Ordering Heuristic  
**Function Name:** `choose_vertex`

---

## 1. Function Signature

```python
def choose_vertex(
    uncolored: list[int],
    adj: list[list[int]],
    colors: list[int],
    saturation: list[int],
    degrees: list[int]
) -> int:
    """
    Select the next vertex from `uncolored` to be colored.

    Args:
        uncolored: list of int, vertex IDs currently uncolored (e.g. [0, 2, 5, 8])
        adj: list of list of int, graph adjacency list where adj[u] contains all neighbor IDs of vertex u
        colors: list of int, length |V|, colors[u] is the non-negative integer color assigned to vertex u,
                or -1 if vertex u is currently uncolored
        saturation: list of int, length |V|, saturation[u] is the number of distinct colors assigned to
                    the neighbors of vertex u
        degrees: list of int, length |V|, degrees[u] is the original degree (number of neighbors) of vertex u

    Returns:
        int: vertex ID from `uncolored` that should be colored next.
    """
```

---

## 2. Argument Specifications & Types

| Argument | Type | Description |
| :--- | :--- | :--- |
| `uncolored` | `list[int]` | Non-empty list of remaining uncolored vertex indices. Guaranteed to contain only valid indices in $\{0, \dots, |V|-1\}$. |
| `adj` | `list[list[int]]` | Undirected graph adjacency list. For every $v \in \text{adj}[u]$, $u \in \text{adj}[v]$. |
| `colors` | `list[int]` | Color assignments for all $|V|$ vertices. Initialized to `-1`. When colored, assigned minimum non-negative integer $\{0, 1, 2, \dots\}$. |
| `saturation` | `list[int]` | Dynamic saturation degree: $|\{ \text{colors}[v] \mid v \in \text{adj}[u] \text{ and } \text{colors}[v] \ge 0 \}|$. |
| `degrees` | `list[int]` | Static degree for each vertex: $\text{len}(\text{adj}[u])$. |

---

## 3. Evaluator Execution Loop

For each graph $G = (V, E)$:
1. Initialize `colors = [-1] * |V|`
2. Initialize `saturation = [0] * |V|`
3. Initialize `neighbor_colors = [set() for _ in range(|V|)]`
4. Initialize `uncolored = list(range(|V|))`
5. While `uncolored` is not empty:
   - Call `v = choose_vertex(list(uncolored), adj, list(colors), list(saturation), degrees)`
   - Verify `v in uncolored` (if not, raise `ValueError`)
   - Find minimum available color $c \ge 0$ not used by any colored neighbor of $v$:
     $$c = \min \{ k \in \mathbb{N}_0 \mid k \notin \text{neighbor\_colors}[v] \}$$
   - Assign `colors[v] = c`
   - Remove $v$ from `uncolored`
   - For each neighbor $u \in \text{adj}[v]$:
     - If $c \notin \text{neighbor\_colors}[u]$:
       - Add $c$ to $\text{neighbor\_colors}[u]$
       - Increment `saturation[u]` by 1
6. Return total colors used:
   $$\chi(G) = \max(\text{colors}) + 1$$

---

## 4. Validity Rules & Error Handling

- **Invalid Return:** If `choose_vertex` returns a vertex ID not in `uncolored`, or a non-integer, the candidate fails immediately with `excess_pct = inf`.
- **Runtime Exceptions:** Any unhandled exception or timeout (>1.0s per instance) fails the candidate with `excess_pct = inf`.
- **No Fallback:** Evaluator never replaces a failed candidate with DSATUR or random selection.
