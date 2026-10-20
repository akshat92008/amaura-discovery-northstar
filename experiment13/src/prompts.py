"""
Experiment #13 Prompts: 15 High-Entropy Diverse Conceptual Perspectives
========================================================================
Each candidate receives a distinct conceptual perspective for Kubernetes-style
cloud pod scheduling on heterogeneous nodes.

Prompt Angles:
1. Aggressive Node Consolidation (Bin Packing)
2. Resource Ratio Balance & Stranded Capacity Elimination
3. Complementary Vector Alignment (Dot Product / Cosine Alignment)
4. Cost-Gradient & Price-Performance Efficiency
5. Multi-Dimensional Residual Volume Minimization
6. Largest-Resource-First Prioritization & Tight Packing
7. Dominant Resource Fairness & Slack Conservation
8. Active-Node Saturation with Imbalance Damping
9. Convex Penalty on Node Activation
10. Anti-Correlated Workload Matching
11. Bottleneck-Resistant Threshold Packing
12. Normalized Multi-Resource Best-Fit Decreasing
13. Elastic Cluster Footprint Minimization
14. Geometric Mean Utilization Maximization
15. Novel Unrestricted Hybrid Scheduling Policy
"""

from typing import Dict, Any, List


PROMPT_PERSPECTIVES = [
    {
        "id": 1,
        "name": "Aggressive Node Consolidation",
        "description": "Maximize pod packing into the minimum number of active nodes. Heavily prioritize placing pods on already active nodes with the highest current utilization before opening any new node."
    },
    {
        "id": 2,
        "name": "Resource Ratio Balance & Stranded Capacity Elimination",
        "description": "Focus intensely on matching the CPU-to-Memory ratio of the node. Placing a pod must minimize |u_cpu - u_mem| so that no capacity is stranded."
    },
    {
        "id": 3,
        "name": "Complementary Vector Alignment",
        "description": "Treat pod demand and node remaining capacity as 2D vectors. Score nodes by cosine similarity or dot-product alignment between the pod resource vector and remaining node vector."
    },
    {
        "id": 4,
        "name": "Cost-Gradient & Price-Performance Efficiency",
        "description": "Account for node hourly cost rates ($/hr). Favor nodes that provide the highest capacity per dollar, prioritizing fully utilizing cheaper per-unit nodes first."
    },
    {
        "id": 5,
        "name": "Multi-Dimensional Residual Volume Minimization",
        "description": "A classic vector bin packing perspective: select the feasible node that minimizes the resulting normalized residual space (product or weighted sum of remaining CPU and remaining Memory fractions)."
    },
    {
        "id": 6,
        "name": "Largest-Resource-First Prioritization & Tight Packing",
        "description": "Sort or prioritize pending pods by their dominant resource demand (LPT rule). Pack the largest, most constrained pods first into tightly fitting nodes."
    },
    {
        "id": 7,
        "name": "Dominant Resource Fairness & Slack Conservation",
        "description": "Analyze which resource (CPU or Memory) is the cluster-wide bottleneck. Conserve slack along the bottleneck dimension while greedily packing along the abundant dimension."
    },
    {
        "id": 8,
        "name": "Active-Node Saturation with Imbalance Damping",
        "description": "Saturate already active nodes up to 90-95% capacity, but apply a non-linear damping penalty if adding the pod causes severe CPU/memory skew."
    },
    {
        "id": 9,
        "name": "Convex Penalty on Node Activation",
        "description": "Model the decision as an optimization problem where turning on a new idle node incurs an enormous step penalty, strictly forcing placement on active nodes whenever possible."
    },
    {
        "id": 10,
        "name": "Anti-Correlated Workload Matching",
        "description": "Explicitly pair high-CPU/low-mem pods with low-CPU/high-mem pods on the same node to achieve near-perfect 1.0/1.0 resource saturation."
    },
    {
        "id": 11,
        "name": "Bottleneck-Resistant Threshold Packing",
        "description": "Use threshold-based placement: if an active node can accommodate the pod without exceeding an imbalance threshold of 0.15, pack it immediately; otherwise evaluate secondary nodes."
    },
    {
        "id": 12,
        "name": "Normalized Multi-Resource Best-Fit Decreasing",
        "description": "Order pending pods by Euclidean norm sqrt(cpu^2 + (mem/4)^2). Place each pod on the node that minimizes Euclidean distance to full saturation."
    },
    {
        "id": 13,
        "name": "Elastic Cluster Footprint Minimization",
        "description": "Emulate cloud autoscaling behavior: treat the cluster as elastic where idle nodes cost zero. Optimize strictly to keep the active node count as small as possible."
    },
    {
        "id": 14,
        "name": "Geometric Mean Utilization Maximization",
        "description": "Score feasible nodes by the geometric mean of resulting CPU utilization and Memory utilization: sqrt(u_cpu * u_mem), heavily favoring balanced high utilization."
    },
    {
        "id": 15,
        "name": "Novel Unrestricted Hybrid Scheduling Policy",
        "description": "Combine the best aspects of vector bin packing, active-node bonuses, and dynamic pod queue reordering into an elegant, unconstrained novel scheduling heuristic."
    }
]


BASE_PROBLEM_SPEC = """
### DOMAIN: Kubernetes-Style Cloud Pod Scheduling Simulation

You are designing an autonomous scheduling policy for placing container pods onto worker nodes in a cloud cluster.

#### Entities:
1. `pod`: A dictionary describing the pod to schedule:
   - `pod["id"]`: int (unique ID)
   - `pod["cpu"]`: float (CPU cores requested, e.g. 2.0)
   - `pod["mem"]`: float (Memory in GB requested, e.g. 8.0)

2. `feasible_nodes`: A list of candidate worker nodes that currently have enough remaining CPU and Memory to fit this pod:
   Each node dict contains:
   - `node["id"]`: int (unique ID)
   - `node["type"]`: str (e.g. "standard_m", "compute_opt", "mem_opt")
   - `node["cpu_capacity"]`: float (total node CPU cores, e.g. 16.0)
   - `node["mem_capacity"]`: float (total node Memory in GB, e.g. 64.0)
   - `node["cost_per_hour"]`: float (hourly rate, e.g. 0.80)

3. `state`: Current cluster state snapshot:
   - `state["allocated_cpu"][node_id]`: float (currently allocated CPU cores on this node)
   - `state["allocated_mem"][node_id]`: float (currently allocated Memory GB on this node)
   - `state["remaining_cpu"][node_id]`: float (available CPU cores on this node)
   - `state["remaining_mem"][node_id]`: float (available Memory GB on this node)
   - `state["active_node_ids"]`: list of node IDs that currently have at least 1 pod placed on them
   - `state["placed_pods_count"][node_id]`: int (number of pods currently running on this node)

4. `pending_pods` (for optional `select_pod`):
   - list of all remaining pod dicts waiting to be scheduled.

---

### OBJECTIVE FUNCTION (Lower Cost is Better):
Total Cluster Cost = Sum_{j in Active Nodes} [ cost_j * (1.0 + 0.2 * |u_cpu_j - u_mem_j|) ] + 1000.0 * N_unscheduled

Where:
- `Active Nodes` are ONLY nodes that have >= 1 pod placed on them. Unused nodes cost $0.00!
- `u_cpu_j = (allocated_cpu) / cpu_capacity` (utilization ratio 0.0 to 1.0)
- `u_mem_j = (allocated_mem) / mem_capacity` (utilization ratio 0.0 to 1.0)
- `|u_cpu_j - u_mem_j|` is the resource imbalance (skew). If CPU is 90% full but Memory is only 10% full, the imbalance is 0.80, which penalizes cost!
- `N_unscheduled` is the count of pods that could not fit. (Huge 1000.0 penalty).

### KEY SCHEDULING INSIGHTS:
1. **Node Consolidation is King**: Placing pods onto an ALREADY ACTIVE node avoids turning on an idle node (saving the entire base hourly rate of that node).
2. **Balance Avoids Stranded Resources**: Matching CPU and memory demands prevents a node from filling up CPU while leaving 50 GB of memory stranded and unusable.
3. **Pod Ordering Matters**: Scheduling larger or more constrained pods first (LPT / vector norm) prevents fragmentation.

---

### REQUIRED PYTHON INTERFACE:
You must provide a valid standalone Python function:
```python
def select_node(pod: dict, feasible_nodes: list[dict], state: dict) -> int:
    # Returns the node_id of the chosen node from feasible_nodes
    ...
```

Optionally, you can also define:
```python
def select_pod(pending_pods: list[dict], nodes: list[dict], state: dict) -> int:
    # Returns the pod_id of the next pod to schedule from pending_pods
    ...
```
(If `select_pod` is omitted, the simulator defaults to FIFO order).

### CONSTRAINTS:
- Output must be enclosed in ```python ... ``` blocks.
- Only pure Python standard libraries: `math`, `random`, `collections`, `itertools`, `heapq`, `copy`.
- No file I/O, no network, no shell calls.
- Logic must be efficient (sub-millisecond per pod decision).
"""


def get_prompt_for_angle(angle_idx: int) -> str:
    spec = PROMPT_PERSPECTIVES[angle_idx % len(PROMPT_PERSPECTIVES)]
    return f"""{BASE_PROBLEM_SPEC}

---
### YOUR SPECIFIC CONCEPTUAL ANGLE: Perspective #{spec['id']} — {spec['name']}
{spec['description']}

Incorporate this conceptual angle directly into your `select_node` (and optionally `select_pod`) implementation.
Synthesize the complete Python code now:
"""
