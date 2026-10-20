"""
Experiment #14 Master Prompt Pool: 60 Distinct Conceptual Perspectives
=======================================================================
A comprehensive, frozen library of 60 independent conceptual prompt perspectives
for Kubernetes-style cloud pod scheduling simulation.
"""

from typing import Dict, Any, List

PROMPT_PERSPECTIVES: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # Category 1: Consolidation & Bin Packing (1 - 10)
    # -------------------------------------------------------------
    {
        "id": 1,
        "category": "Consolidation & Bin Packing",
        "name": "Aggressive Active Node Consolidation",
        "description": "Maximize pod packing into the absolute minimum number of active nodes. Heavily prioritize placing pods on already active nodes with the highest current utilization before opening any new node."
    },
    {
        "id": 2,
        "category": "Consolidation & Bin Packing",
        "name": "Resource Ratio Balance & Stranded Capacity Elimination",
        "description": "Focus intensely on matching the CPU-to-Memory ratio of the node. Placing a pod must minimize |u_cpu - u_mem| so that no capacity is stranded."
    },
    {
        "id": 3,
        "category": "Consolidation & Bin Packing",
        "name": "Multi-Dimensional Residual Volume Minimization",
        "description": "Select the feasible node that minimizes the resulting normalized residual space (product or sum of remaining CPU and Memory fractions)."
    },
    {
        "id": 4,
        "category": "Consolidation & Bin Packing",
        "name": "Best Fit Decreasing Euclidean Norm",
        "description": "Order pending pods by Euclidean norm sqrt(cpu^2 + (mem/4)^2). Place each pod on the node that minimizes Euclidean distance to full saturation."
    },
    {
        "id": 5,
        "category": "Consolidation & Bin Packing",
        "name": "MostAllocated Utilization Saturation",
        "description": "Emulate production Kubernetes MostAllocated plugin: score nodes by the sum of normalized CPU and memory utilization, giving huge bonuses to active nodes."
    },
    {
        "id": 6,
        "category": "Consolidation & Bin Packing",
        "name": "Threshold-Based Consolidation",
        "description": "If an active node can accommodate the pod without exceeding an imbalance threshold of 0.15, pack it immediately; otherwise evaluate secondary nodes."
    },
    {
        "id": 7,
        "category": "Consolidation & Bin Packing",
        "name": "Convex Active Node Step Penalty",
        "description": "Model the decision as an optimization problem where turning on a new idle node incurs an enormous step penalty, strictly forcing placement on active nodes whenever possible."
    },
    {
        "id": 8,
        "category": "Consolidation & Bin Packing",
        "name": "Stranded Capacity Surcharge",
        "description": "Calculate the monetary value of stranded resources if CPU reaches 100% while memory remains unused. Penalize node choices that strand expensive capacity."
    },
    {
        "id": 9,
        "category": "Consolidation & Bin Packing",
        "name": "Anti-Fragmentation Slack",
        "description": "Avoid creating fragmented slices of CPU (<1 core) or Memory (<2GB) on any active node that cannot fit future pods."
    },
    {
        "id": 10,
        "category": "Consolidation & Bin Packing",
        "name": "Peak Load Node Damping",
        "description": "Pack nodes up to 95% capacity, leaving a tiny safety buffer to absorb small variations, then lock the node as fully consolidated."
    },

    # -------------------------------------------------------------
    # Category 2: Vector & Geometric (11 - 20)
    # -------------------------------------------------------------
    {
        "id": 11,
        "category": "Vector & Geometric",
        "name": "Cosine Vector Alignment",
        "description": "Treat pod demand and node remaining capacity as 2D vectors. Score nodes by cosine similarity between the pod resource vector and remaining node capacity vector."
    },
    {
        "id": 12,
        "category": "Vector & Geometric",
        "name": "Dot-Product Capacity Match",
        "description": "Compute the dot product of the normalized pod demand vector with the normalized node allocation vector to maximize alignment."
    },
    {
        "id": 13,
        "category": "Vector & Geometric",
        "name": "Orthogonal Slack Preservation",
        "description": "Evaluate the orthogonal component of the pod request relative to node slack, preserving multidimensional balance."
    },
    {
        "id": 14,
        "category": "Vector & Geometric",
        "name": "Normalized Euclidean Distance to Saturation",
        "description": "Measure the Euclidean distance from the post-placement node state (u_cpu, u_mem) to the ideal saturation point (1.0, 1.0). Minimize this distance."
    },
    {
        "id": 15,
        "category": "Vector & Geometric",
        "name": "Angle-Distance Clustering",
        "description": "Cluster pods and nodes by their resource angle arctan2(mem, cpu). Place pods on nodes with complementary angular demand."
    },
    {
        "id": 16,
        "category": "Vector & Geometric",
        "name": "High-Dimensional Convex Hull",
        "description": "Approximate the 2D bounding box of workloads and pack nodes to fill the rectangular area with minimal unoccupied area."
    },
    {
        "id": 17,
        "category": "Vector & Geometric",
        "name": "Resource Plane Projection",
        "description": "Project pod CPU and memory requests onto the node capacity diagonal line u_cpu = u_mem. Select the node that minimizes projection deviation."
    },
    {
        "id": 18,
        "category": "Vector & Geometric",
        "name": "Dominant Vector Projection",
        "description": "Identify which resource axis is dominant for the pod and align it with the node that has surplus in that specific resource."
    },
    {
        "id": 19,
        "category": "Vector & Geometric",
        "name": "Dual-Axis Aspect Ratio Matching",
        "description": "Compute aspect ratio cpu/mem for pod and node. Minimize the difference between pod aspect ratio and residual node aspect ratio."
    },
    {
        "id": 20,
        "category": "Vector & Geometric",
        "name": "Polar Coordinate Saturation",
        "description": "Represent capacity in polar coordinates (radius = total utilization, theta = balance angle). Maximize radius while keeping theta close to 45 degrees."
    },

    # -------------------------------------------------------------
    # Category 3: Economic & Price-Performance (21 - 30)
    # -------------------------------------------------------------
    {
        "id": 21,
        "category": "Economic & Price-Performance",
        "name": "Cost-Gradient Efficiency",
        "description": "Account for node hourly cost rates ($/hr). Favor nodes that provide the highest capacity per dollar, prioritizing fully utilizing cheaper per-unit nodes first."
    },
    {
        "id": 22,
        "category": "Economic & Price-Performance",
        "name": "Price per Allocated Core",
        "description": "Calculate the effective hourly cost per allocated CPU core on each active node. Pack nodes that yield the lowest effective cost per core."
    },
    {
        "id": 23,
        "category": "Economic & Price-Performance",
        "name": "Marginal Activation Penalty",
        "description": "Enforce a strict hurdle rate: an idle node can only be opened if no active node can fit the pod, and among idle nodes, pick the cheapest node profile that fits."
    },
    {
        "id": 24,
        "category": "Economic & Price-Performance",
        "name": "Heterogeneous Class Preference",
        "description": "Place compute-heavy pods on compute-optimized nodes and memory-heavy pods on memory-optimized nodes to maximize resource purchasing efficiency."
    },
    {
        "id": 25,
        "category": "Economic & Price-Performance",
        "name": "Energy-Proportional Consolidation",
        "description": "Emulate energy-aware datacenter policies: keep server count minimal to minimize baseline electrical overhead."
    },
    {
        "id": 26,
        "category": "Economic & Price-Performance",
        "name": "Capacity-Weighted Cost Ranking",
        "description": "Rank nodes by cost / (cpu_cap * mem_cap), favoring dense, high-efficiency nodes over fragmented smaller nodes."
    },
    {
        "id": 27,
        "category": "Economic & Price-Performance",
        "name": "High-Density Cost Minimization",
        "description": "Pack pods into large nodes (32 core / 128 GB) first to amortize node overhead, avoiding scattering pods across multiple small nodes."
    },
    {
        "id": 28,
        "category": "Economic & Price-Performance",
        "name": "Tiered Node Tariff Ranking",
        "description": "Assign priority tiers to nodes based on their hourly cost efficiency. Saturate Tier 1 nodes before spilling into Tier 2 nodes."
    },
    {
        "id": 29,
        "category": "Economic & Price-Performance",
        "name": "Residual Amortization",
        "description": "Compute the financial depreciation of unutilized node capacity. Pick the node that leaves the lowest unamortized dollar value."
    },
    {
        "id": 30,
        "category": "Economic & Price-Performance",
        "name": "Cost-Penalty Lexicographic Sort",
        "description": "Sort feasible nodes: Tier 1 = active vs inactive, Tier 2 = node hourly cost, Tier 3 = utilization density."
    },

    # -------------------------------------------------------------
    # Category 4: Constraint & Slack Preservation (31 - 40)
    # -------------------------------------------------------------
    {
        "id": 31,
        "category": "Constraint & Slack Preservation",
        "name": "Bottleneck Resource Conservation",
        "description": "Determine which resource (CPU or Memory) is scarcer across the entire cluster. Conserve slack along the bottleneck dimension while greedily packing the abundant dimension."
    },
    {
        "id": 32,
        "category": "Constraint & Slack Preservation",
        "name": "Multi-Resource Dynamic Slack",
        "description": "Track the ratio of total remaining CPU to total remaining Memory. Guide placements to steer cluster-wide slack toward 1:4 parity."
    },
    {
        "id": 33,
        "category": "Constraint & Slack Preservation",
        "name": "Future Feasibility Margin",
        "description": "Preserve at least one high-capacity node with open headroom to guarantee that large monolithic pods arriving later will find a home."
    },
    {
        "id": 34,
        "category": "Constraint & Slack Preservation",
        "name": "High-Scarcity Resource Protection",
        "description": "When placing a small pod, avoid consuming the final sliver of a scarce resource on an otherwise high-capacity node."
    },
    {
        "id": 35,
        "category": "Constraint & Slack Preservation",
        "name": "Anti-Affinity Resource Pairing",
        "description": "Pair CPU-heavy pods with Memory-heavy pods on the same node to cancel out resource skews and achieve balanced 1.0/1.0 saturation."
    },
    {
        "id": 36,
        "category": "Constraint & Slack Preservation",
        "name": "Asymmetric Dimension Sizing",
        "description": "Weight CPU and Memory by their relative tightness across the cluster: weight_cpu = total_dem_cpu / total_cap_cpu."
    },
    {
        "id": 37,
        "category": "Constraint & Slack Preservation",
        "name": "Buffer Capacity Reservation",
        "description": "Keep exactly 5% buffer on active nodes to minimize fragmentation penalties while packing remaining space tightly."
    },
    {
        "id": 38,
        "category": "Constraint & Slack Preservation",
        "name": "Elastic Footprint Minimization",
        "description": "Emulate cloud autoscaling behavior: treat the cluster as elastic where idle nodes cost zero. Optimize strictly to keep active node count as small as possible."
    },
    {
        "id": 39,
        "category": "Constraint & Slack Preservation",
        "name": "Bimodal Size Separation",
        "description": "Segregate large monolithic pods onto dedicated high-capacity nodes, and pack small microservice pods into standard shared nodes."
    },
    {
        "id": 40,
        "category": "Constraint & Slack Preservation",
        "name": "High-Watermark Protection",
        "description": "Establish a high watermark of 90% utilization; do not open a new node until all active nodes have reached the high watermark."
    },

    # -------------------------------------------------------------
    # Category 5: Scheduling & Queue Prioritization (41 - 50)
    # -------------------------------------------------------------
    {
        "id": 41,
        "category": "Scheduling & Queue Prioritization",
        "name": "Normalized Cluster Demand LPT",
        "description": "Order pending pods by normalized demand (cpu / avg_cpu + mem / avg_mem). Schedule largest, most constrained pods first."
    },
    {
        "id": 42,
        "category": "Scheduling & Queue Prioritization",
        "name": "Largest Constrained Pod First",
        "description": "Sort pods by max(cpu / 16, mem / 64). Pack the most resource-constrained pods first before easy small pods."
    },
    {
        "id": 43,
        "category": "Scheduling & Queue Prioritization",
        "name": "Smallest Fill-In Packing",
        "description": "Schedule large pods first, but immediately interleave with tiny pods to fill remaining crevices on active nodes."
    },
    {
        "id": 44,
        "category": "Scheduling & Queue Prioritization",
        "name": "Dynamic Urgency Score",
        "description": "Assign higher scheduling urgency to pods that have the fewest feasible nodes in the cluster."
    },
    {
        "id": 45,
        "category": "Scheduling & Queue Prioritization",
        "name": "Bounded Lookahead Matching",
        "description": "Inspect the top 5 pending pods in the queue; pick the pod that best matches the available slack of the currently most-filled node."
    },
    {
        "id": 46,
        "category": "Scheduling & Queue Prioritization",
        "name": "High-Dimensional Knapsack Priority",
        "description": "Treat each node as a 2D knapsack; prioritize pods with the highest value-to-weight ratio."
    },
    {
        "id": 47,
        "category": "Scheduling & Queue Prioritization",
        "name": "Bimodal Dual-Queue Prioritization",
        "description": "Partition pods into 'Heavy' and 'Light'. Alternate between placing a Heavy pod and topping off with Light pods."
    },
    {
        "id": 48,
        "category": "Scheduling & Queue Prioritization",
        "name": "Maximum Aspect Ratio Pod First",
        "description": "Schedule extreme pods (very high CPU or very high Mem) first, followed by balanced pods to smooth out node utilization."
    },
    {
        "id": 49,
        "category": "Scheduling & Queue Prioritization",
        "name": "Slack-Ratio Sorting",
        "description": "Sort pending pods by the ratio cpu / (mem + 0.1) in descending order to pack high-compute pods into designated nodes."
    },
    {
        "id": 50,
        "category": "Scheduling & Queue Prioritization",
        "name": "Geometric Mean Pod Demand",
        "description": "Sort pending pods by sqrt(cpu * mem) in descending order to process large area workloads first."
    },

    # -------------------------------------------------------------
    # Category 6: Hybrid & Radical Perspectives (51 - 60)
    # -------------------------------------------------------------
    {
        "id": 51,
        "category": "Hybrid & Radical Perspectives",
        "name": "Lexicographic Dual-Constraint Ranking",
        "description": "Use a 3-tier tuple key: (is_inactive, imbalance_delta, node_hourly_cost). Strictly consolidate active nodes first, minimize skew second, minimize cost third."
    },
    {
        "id": 52,
        "category": "Hybrid & Radical Perspectives",
        "name": "Geometric Mean Utilization Maximization",
        "description": "Score feasible nodes by the geometric mean of resulting CPU utilization and Memory utilization: sqrt(u_cpu * u_mem), heavily favoring balanced high utilization."
    },
    {
        "id": 53,
        "category": "Hybrid & Radical Perspectives",
        "name": "Entropy-Maximizing Balanced Saturation",
        "description": "Maximize Shannon entropy of resource distributions across nodes to achieve dense, compact cluster packing."
    },
    {
        "id": 54,
        "category": "Hybrid & Radical Perspectives",
        "name": "Harmonic Mean Residual Slack",
        "description": "Score feasible nodes by the harmonic mean of remaining CPU and Memory, penalizing nodes that become severely depleted in only one resource."
    },
    {
        "id": 55,
        "category": "Hybrid & Radical Perspectives",
        "name": "Dynamic Penalty Relaxation",
        "description": "Allow temporary resource imbalance on a node if its total utilization exceeds 85%, acknowledging that high fill rate offsets minor skew."
    },
    {
        "id": 56,
        "category": "Hybrid & Radical Perspectives",
        "name": "Two-Phase Bounded Local Consolidation",
        "description": "Phase 1: Filter to active nodes. Phase 2: Pick node with minimal post-placement residual volume. If no active node fits, pick cheapest feasible inactive node."
    },
    {
        "id": 57,
        "category": "Hybrid & Radical Perspectives",
        "name": "Adaptive Threshold Squeeze",
        "description": "Adaptively tighten packing thresholds: as the number of active nodes grows, increase the bias toward cramming pods into existing active nodes."
    },
    {
        "id": 58,
        "category": "Hybrid & Radical Perspectives",
        "name": "Non-Linear Skew Damping",
        "description": "Apply a quadratic penalty (u_cpu - u_mem)^2 to strongly discourage severe resource skew while leaving mild imbalance unpenalized."
    },
    {
        "id": 59,
        "category": "Hybrid & Radical Perspectives",
        "name": "Reverse-Greedy Cluster Compaction",
        "description": "Identify the least-utilized active node and avoid scheduling pods on it, encouraging it to drain so it can be shut down."
    },
    {
        "id": 60,
        "category": "Hybrid & Radical Perspectives",
        "name": "Novel Unrestricted Multi-Resource Hybrid",
        "description": "Combine normalized LPT pod ordering with active-node lexicographic consolidation, quadratic skew damping, and cost-tiebreaking into an unrestricted novel policy."
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


def get_prompt_for_perspective(perspective: Dict[str, Any]) -> str:
    return f"""{BASE_PROBLEM_SPEC}

---
### YOUR SPECIFIC CONCEPTUAL ANGLE: Perspective #{perspective['id']} — {perspective['name']} ({perspective['category']})
{perspective['description']}

Incorporate this conceptual angle directly into your `select_node` (and optionally `select_pod`) implementation.
Synthesize the complete Python code now:
"""
