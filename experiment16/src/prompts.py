"""
Experiment #16 Master Prompt Pool: 60 Distinct Conceptual Perspectives
=======================================================================
A comprehensive, frozen library of 60 independent conceptual prompt perspectives
for dynamic cloud pod scheduling with continuous arrivals and departures.

CRITICAL ANTI-LEAKAGE COMPLIANCE:
- Zero mention of 'MostAllocated'
- Zero mention of 'T4_C01' or its dynamic failure
- Zero mention of the 2.5% gap from Experiment #15
- Zero mention of hidden trace identities or benchmarks
- Pure conceptual, mathematical, and architectural paradigms
"""

from typing import Dict, Any, List

PROMPT_PERSPECTIVES: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # Category 1: Workload Churn & Departure Dynamics (1 - 6)
    # -------------------------------------------------------------
    {
        "id": 1,
        "category": "Workload Churn & Departure Dynamics",
        "name": "Departure Synchrony Alignment",
        "description": "Group arriving workloads onto nodes with similar anticipated departure profiles. Minimizing the dispersion of termination times on an active node allows the node to reach zero occupancy cleanly without lingering stragglers."
    },
    {
        "id": 2,
        "category": "Workload Churn & Departure Dynamics",
        "name": "Transient Load Segregation",
        "description": "Distinguish between short-lived and long-lived workloads when duration hints exist. Segregating high-churn transient pods onto designated active nodes prevents them from keeping otherwise idle nodes alive."
    },
    {
        "id": 3,
        "category": "Workload Churn & Departure Dynamics",
        "name": "Churn Rate Damping",
        "description": "Evaluate the rate of event churn across the cluster. Place incoming pods so as to minimize the number of nodes undergoing simultaneous state transitions, dampening overall cluster churn."
    },
    {
        "id": 4,
        "category": "Workload Churn & Departure Dynamics",
        "name": "Node Turnover Minimization",
        "description": "Aim to minimize frequent activation-deactivation cycling of nodes. Favor placing pods on nodes that already have stable, high pod counts to sustain consistent utilization."
    },
    {
        "id": 5,
        "category": "Workload Churn & Departure Dynamics",
        "name": "Departure Coincidence Maximization",
        "description": "Heuristically pack pods whose lifespans are likely to end in the same temporal window onto the same host, maximizing the probability that multiple pods depart concurrently."
    },
    {
        "id": 6,
        "category": "Workload Churn & Departure Dynamics",
        "name": "Residual Lifetime Packing",
        "description": "Consider the estimated remaining residency of workloads. Placing a new workload on a host whose existing workloads are nearly finished prolongs host life unnecessarily; instead prefer hosts with substantial remaining tenancy."
    },

    # -------------------------------------------------------------
    # Category 2: Node Drainability & Evacuation Velocity (7 - 12)
    # -------------------------------------------------------------
    {
        "id": 7,
        "category": "Node Drainability & Evacuation Velocity",
        "name": "Drain Velocity Acceleration",
        "description": "Identify lightly loaded active nodes as candidate draining hosts. Avoid placing new workloads onto nodes with very few pods, allowing natural completions to drain those hosts to zero."
    },
    {
        "id": 8,
        "category": "Node Drainability & Evacuation Velocity",
        "name": "Asymmetric Host Polarization",
        "description": "Create a clear polarization among active hosts: keep a subset of hosts heavily loaded and saturated, while actively protecting low-occupancy hosts so they can empty out quickly."
    },
    {
        "id": 9,
        "category": "Node Drainability & Evacuation Velocity",
        "name": "Evacuation Barrier Protection",
        "description": "Establish an implicit barrier: hosts with occupancy below a critical threshold are treated as 'in evacuation' and rejected for new placements unless no other feasible active host exists."
    },
    {
        "id": 10,
        "category": "Node Drainability & Evacuation Velocity",
        "name": "Monotonic Host Emptying",
        "description": "Prioritize placements that do not reverse the downward trajectory of draining nodes. If a host's allocation has been declining, direct incoming traffic elsewhere."
    },
    {
        "id": 11,
        "category": "Node Drainability & Evacuation Velocity",
        "name": "Draining Probability Scoring",
        "description": "Score feasible nodes inversely by their likelihood of becoming idle in the near future. Hosts with small pod footprints have high idle probability and should not receive new pods."
    },
    {
        "id": 12,
        "category": "Node Drainability & Evacuation Velocity",
        "name": "Straggler Prevention Policy",
        "description": "Prevent the creation of 'single-pod hostage nodes' where one isolated container forces an entire 96-core server to remain active and billed."
    },

    # -------------------------------------------------------------
    # Category 3: Active-Node Preference & Hysteresis (13 - 18)
    # -------------------------------------------------------------
    {
        "id": 13,
        "category": "Active-Node Preference & Hysteresis",
        "name": "Steep Activation Barrier",
        "description": "Impose a very heavy penalty against activating any idle node. Every feasible currently-active node must be thoroughly saturated before any new node is considered."
    },
    {
        "id": 14,
        "category": "Active-Node Preference & Hysteresis",
        "name": "Hysteresis-Based Cluster Sizing",
        "description": "Implement scheduling hysteresis: resist turning on new nodes during temporary arrival surges, absorbing demand entirely within the currently active envelope."
    },
    {
        "id": 15,
        "category": "Active-Node Preference & Hysteresis",
        "name": "Two-Tier Lexicographic Preference",
        "description": "Strictly segregate candidate nodes into tier-1 (already active) and tier-2 (inactive). Optimize placement heuristics purely within tier-1; only evaluate tier-2 if tier-1 is empty."
    },
    {
        "id": 16,
        "category": "Active-Node Preference & Hysteresis",
        "name": "Activation Energy Step Function",
        "description": "Treat node activation as requiring an activation energy step. Measure the marginal cost of placing on an active node ($0 additional hourly base cost) versus an idle node (+$4.08/hr base cost)."
    },
    {
        "id": 17,
        "category": "Active-Node Preference & Hysteresis",
        "name": "Soft Hysteresis Utilization Buffer",
        "description": "Maintain active nodes in a high-utilization band (80%-95%) before allowing expansion to new hardware, preventing premature cluster scaling."
    },
    {
        "id": 18,
        "category": "Active-Node Preference & Hysteresis",
        "name": "Node Stickiness & Tenancy",
        "description": "Direct pods toward hosts with proven high tenancy and stability, reinforcing continuous utilization on a compact active working set."
    },

    # -------------------------------------------------------------
    # Category 4: Multi-Resource Balance & Skew Minimization (19 - 24)
    # -------------------------------------------------------------
    {
        "id": 19,
        "category": "Multi-Resource Balance & Skew Minimization",
        "name": "Post-Placement Skew Minimization",
        "description": "Evaluate the absolute difference between CPU utilization and Memory utilization |u_cpu - u_mem| resulting from placement, picking the node that achieves the lowest skew."
    },
    {
        "id": 20,
        "category": "Multi-Resource Balance & Skew Minimization",
        "name": "Vector Cosine Alignment",
        "description": "Treat pod requests (cpu, mem) and node capacities as 2D vectors. Place the pod on the active host whose current residual capacity vector best matches the pod request vector."
    },
    {
        "id": 21,
        "category": "Multi-Resource Balance & Skew Minimization",
        "name": "Dominant Resource Matching",
        "description": "Pair CPU-heavy pods with memory-heavy nodes and memory-heavy pods with CPU-heavy nodes to create balanced complementary utilization on each active machine."
    },
    {
        "id": 22,
        "category": "Multi-Resource Balance & Skew Minimization",
        "name": "Stranded Capacity Prevention",
        "description": "Compute the bottleneck resource on each host. Penalize choices that consume the scarce resource while leaving the abundant resource stranded and unusable."
    },
    {
        "id": 23,
        "category": "Multi-Resource Balance & Skew Minimization",
        "name": "Harmonic Mean Resource Efficiency",
        "description": "Score node capacity using the harmonic mean of available CPU and memory fractions, naturally discouraging severe dimensional imbalance."
    },
    {
        "id": 24,
        "category": "Multi-Resource Balance & Skew Minimization",
        "name": "Normalized Euclidean Residual Distance",
        "description": "Calculate Euclidean distance from current node state (u_cpu, u_mem) to the ideal balanced saturation point (1.0, 1.0). Minimize this distance across active nodes."
    },

    # -------------------------------------------------------------
    # Category 5: Temporal Locality & Lifecycle Heuristics (25 - 30)
    # -------------------------------------------------------------
    {
        "id": 25,
        "category": "Temporal Locality & Lifecycle Heuristics",
        "name": "Temporal Burst Clustering",
        "description": "Cluster pods arriving closely in time onto the same active hosts, exploiting temporal correlation under the hypothesis that burst arrivals often share operational lifespans."
    },
    {
        "id": 26,
        "category": "Temporal Locality & Lifecycle Heuristics",
        "name": "Arrival Epoch Grouping",
        "description": "Discretize time into arrival epochs. Pods arriving within the same epoch are directed to fill existing open active nodes before subsequent epochs initiate new allocations."
    },
    {
        "id": 27,
        "category": "Temporal Locality & Lifecycle Heuristics",
        "name": "Tenancy Density Maximization",
        "description": "Maximize the density of pods per active node-hour. Concentrating high pod counts onto active nodes maximizes the return on invested operational hours."
    },
    {
        "id": 28,
        "category": "Temporal Locality & Lifecycle Heuristics",
        "name": "Phase-Aware Lifecycle Routing",
        "description": "Track the apparent operational phase of active nodes (growing, plateau, draining). Route new pods exclusively to nodes in the growing or plateau phase."
    },
    {
        "id": 29,
        "category": "Temporal Locality & Lifecycle Heuristics",
        "name": "Active Age Prioritization",
        "description": "Favor placing pods on nodes that have been active longest and have established steady-state occupancy, avoiding newly opened hosts."
    },
    {
        "id": 30,
        "category": "Temporal Locality & Lifecycle Heuristics",
        "name": "Dynamic Lifetime Co-Allocation",
        "description": "When pod durations are known or predictable, pair pods such that their cumulative departure clears node capacity in uniform stages."
    },

    # -------------------------------------------------------------
    # Category 6: Dynamic Consolidation & Bin Packing (31 - 36)
    # -------------------------------------------------------------
    {
        "id": 31,
        "category": "Dynamic Consolidation & Bin Packing",
        "name": "Tightest Fit Consolidation",
        "description": "Among active nodes, choose the node with the smallest residual capacity that can still accommodate the pod, leaving larger contiguous blocks free elsewhere."
    },
    {
        "id": 32,
        "category": "Dynamic Consolidation & Bin Packing",
        "name": "Utilization Saturation Ranking",
        "description": "Rank active nodes in descending order of post-placement total utilization (u_cpu + u_mem). Pack pods into the most heavily utilized feasible node."
    },
    {
        "id": 33,
        "category": "Dynamic Consolidation & Bin Packing",
        "name": "Residual Volume Minimization",
        "description": "Measure residual multidimensional space (rem_cpu * rem_mem). Select the active node that minimizes remaining unallocated space after placement."
    },
    {
        "id": 34,
        "category": "Dynamic Consolidation & Bin Packing",
        "name": "Max-Utilization Satiation",
        "description": "Attempt to push already dense active nodes to 90%+ saturation, effectively 'closing' them as fully packed bins so newer arrivals don't fragment them."
    },
    {
        "id": 35,
        "category": "Dynamic Consolidation & Bin Packing",
        "name": "Geometric Packing Factor",
        "description": "Compute a geometric packing index combining normalized resource utilization and active status. Prefer nodes that maximize the geometric progression of density."
    },
    {
        "id": 36,
        "category": "Dynamic Consolidation & Bin Packing",
        "name": "Aggressive Active Compaction",
        "description": "Treat every active node as a compact bin. Maximize allocated core and memory count on the top-N active machines to keep the total active machine footprint minimal."
    },

    # -------------------------------------------------------------
    # Category 7: Online Algorithms & Competitive Analysis (37 - 42)
    # -------------------------------------------------------------
    {
        "id": 37,
        "category": "Online Algorithms & Competitive Analysis",
        "name": "Online Primal-Dual Cost Thresholding",
        "description": "Set dynamic shadow prices for node resources based on exponential utilization functions. Place the pod on the active node that minimizes total marginal shadow cost."
    },
    {
        "id": 38,
        "category": "Online Algorithms & Competitive Analysis",
        "name": "Competitive Reserve Factor",
        "description": "Maintain competitive ratio bounds against an offline optimal scheduler by penalizing under-utilized active hosts and prioritizing densely committed hosts."
    },
    {
        "id": 39,
        "category": "Online Algorithms & Competitive Analysis",
        "name": "Exponential Utilization Pricing",
        "description": "Apply convex cost scaling: resources on lightly loaded nodes have high marginal opportunity cost, while adding load to an already committed node has minimal marginal cost."
    },
    {
        "id": 40,
        "category": "Online Algorithms & Competitive Analysis",
        "name": "Adversarial Workload Hedging",
        "description": "Protect the cluster against adverse sudden arrivals by consolidating typical workloads onto dense hosts while preserving select hosts with flexible dual-resource headroom."
    },
    {
        "id": 41,
        "category": "Online Algorithms & Competitive Analysis",
        "name": "Greedy Online Min-Cost",
        "description": "Directly evaluate the immediate instantaneous increase in cluster billing rate for each candidate placement; choose the placement with minimal rate increase."
    },
    {
        "id": 42,
        "category": "Online Algorithms & Competitive Analysis",
        "name": "Worst-Case Residual Preservation",
        "description": "Ensure that placements do not leave tiny unusable resource slivers on multiple nodes. Preserve large usable resource envelopes on a minimal subset of hosts."
    },

    # -------------------------------------------------------------
    # Category 8: Queueing Theory & Workload Flow (43 - 48)
    # -------------------------------------------------------------
    {
        "id": 43,
        "category": "Queueing Theory & Workload Flow",
        "name": "Little's Law Workload Density",
        "description": "Exploit Little's Law (L = lambda * W): maximize the number of concurrent items in system per active server, thereby maximizing efficiency per billing interval."
    },
    {
        "id": 44,
        "category": "Queueing Theory & Workload Flow",
        "name": "Multi-Server Queue Consolidation",
        "description": "Model the cluster as an M/M/c system where 'c' (active servers) should be kept as small as possible while keeping arrival capacity feasible."
    },
    {
        "id": 45,
        "category": "Queueing Theory & Workload Flow",
        "name": "Service Rate Matching",
        "description": "Match incoming arrival velocity against the natural departure velocity of active hosts, funneling new arrivals to active hosts with ongoing capacity turnover."
    },
    {
        "id": 46,
        "category": "Queueing Theory & Workload Flow",
        "name": "Traffic Intensity Concentration",
        "description": "Concentrate traffic intensity onto a compact active core rather than spreading arrival load evenly across all available capacity."
    },
    {
        "id": 47,
        "category": "Queueing Theory & Workload Flow",
        "name": "Departure Flow Alignment",
        "description": "Align placements with expected departure flow, ensuring that as pods finish, remaining occupancy collapses toward zero rather than lingering at low levels."
    },
    {
        "id": 48,
        "category": "Queueing Theory & Workload Flow",
        "name": "Dynamic Flow Bottleneck Relief",
        "description": "Direct pods away from nodes experiencing resource bottlenecks (where one dimension is 100% full) toward nodes where both dimensions flow freely."
    },

    # -------------------------------------------------------------
    # Category 9: Utilization Thresholds & Safe Saturation (49 - 54)
    # -------------------------------------------------------------
    {
        "id": 49,
        "category": "Utilization Thresholds & Safe Saturation",
        "name": "Target Utilization Banding (75-95%)",
        "description": "Define a sweet spot target utilization band. Strongly prefer active nodes whose post-placement utilization falls within 75% to 95%, avoiding both under-utilization and over-saturation."
    },
    {
        "id": 50,
        "category": "Utilization Thresholds & Safe Saturation",
        "name": "Active Occupancy Quorum",
        "description": "Require active nodes to satisfy an occupancy quorum (e.g. at least 3-5 pods) before being considered stable. Steer new pods to help newer active nodes reach quorum."
    },
    {
        "id": 51,
        "category": "Utilization Thresholds & Safe Saturation",
        "name": "Headroom Reservation Buffer",
        "description": "Reserve a 5% CPU/Memory safety headroom on active machines to prevent placement failures, while packing the remaining 95% as densely as possible."
    },
    {
        "id": 52,
        "category": "Utilization Thresholds & Safe Saturation",
        "name": "Graduated Density Scoring",
        "description": "Apply piecewise linear scoring: reward utilization gains up to 90% heavily; apply neutral scoring between 90-98%; penalize only true saturation."
    },
    {
        "id": 53,
        "category": "Utilization Thresholds & Safe Saturation",
        "name": "Under-Utilization Evacuation Threshold",
        "description": "If an active node has utilization below 20%, penalize placing new pods on it so it can naturally drain to zero and shut down."
    },
    {
        "id": 54,
        "category": "Utilization Thresholds & Safe Saturation",
        "name": "Critical Saturation Locking",
        "description": "When an active node reaches 90% utilization on both CPU and Memory, treat it as ideally packed and prioritize packing the next active node."
    },

    # -------------------------------------------------------------
    # Category 10: Composite & Lexicographic Hybrid Strategies (55 - 60)
    # -------------------------------------------------------------
    {
        "id": 55,
        "category": "Composite & Lexicographic Hybrid Strategies",
        "name": "Lexicographic: Active > Utilization > Balance",
        "description": "Use a strict hierarchical tuple key: 1st priority: prefer already active nodes; 2nd priority: prefer higher post-placement utilization; 3rd priority: minimize resource skew."
    },
    {
        "id": 56,
        "category": "Composite & Lexicographic Hybrid Strategies",
        "name": "Lexicographic: Active > Residual Minimization > Cost",
        "description": "Hierarchy: 1st: active node filter; 2nd: minimize residual volume (rem_cpu + rem_mem); 3rd: break ties with lowest node hourly cost."
    },
    {
        "id": 57,
        "category": "Composite & Lexicographic Hybrid Strategies",
        "name": "Dual-Score Weighted Optimization",
        "description": "Formulate a composite score = alpha * utilization_score + beta * balance_score + gamma * active_bonus. Balance high packing density with dimensional symmetry."
    },
    {
        "id": 58,
        "category": "Composite & Lexicographic Hybrid Strategies",
        "name": "Adaptive Utilization-Skew Trade-Off",
        "description": "Adaptively weigh utilization density versus resource balance: when cluster load is low, prioritize density and drainability; when load is high, prioritize balance."
    },
    {
        "id": 59,
        "category": "Composite & Lexicographic Hybrid Strategies",
        "name": "Multi-Criteria Pareto Frontier",
        "description": "Identify Pareto-optimal feasible nodes across the two objectives of maximizing utilization density and minimizing resource skew, choosing the best compromise."
    },
    {
        "id": 60,
        "category": "Composite & Lexicographic Hybrid Strategies",
        "name": "Cost-Rate Minimization with Churn Awareness",
        "description": "Integrate hourly operational rate and expected node longevity: choose active nodes where placement achieves dense packing and high probability of clean host shutdown."
    }
]


def get_prompt_for_perspective(perspective: Dict[str, Any]) -> str:
    """
    Constructs an independent, self-contained prompt for a given conceptual perspective.
    Adheres strictly to zero-leakage constraints.
    """
    pid = perspective["id"]
    category = perspective["category"]
    name = perspective["name"]
    desc = perspective["description"]

    prompt = f"""### Context & Objective
You are tasked with designing an online cloud container/pod scheduling policy for a high-performance Kubernetes-like cluster.
In this environment, workloads (pods) arrive dynamically over time with asynchronous arrival and departure events.
- Pods require CPU cores (`pod['cpu']`) and Memory GB (`pod['mem']`). Some pods may include `pod['duration_sec']` if duration is known.
- Feasible nodes (`feasible_nodes`) have capacities `node['cpu_capacity']`, `node['mem_capacity']`, and hourly cost `node['cost_per_hour']`.
- Active nodes are those currently harboring one or more running pods (`state['active_node_ids']`).
- When all pods on a node finish and depart, the node becomes completely idle and immediately scales to zero (stops incurring operational cost).
- If a pod is placed on an idle node, that node becomes active and incurs operational cost for the entire duration it hosts workloads.
- The overarching goal is to MINIMIZE total cluster operational cost (active node-hours * cost_rate) while achieving 100% placement feasibility.

### Design Paradigm: Perspective #{pid} — {name}
**Theoretical Category:** {category}
**Core Conceptual Guideline:**
{desc}

### Mathematical & Algorithmic Requirements
Synthesize a Python function `select_node`:
```python
def select_node(pod: dict, feasible_nodes: list[dict], state: dict) -> int:
    \"\"\"
    pod: dict with keys:
        'id': int / str
        'cpu': float
        'mem': float
        'duration_sec': float (optional, default 3600.0 if not present)
    feasible_nodes: list of dicts, each with keys:
        'id': int / str
        'cpu_capacity': float
        'mem_capacity': float
        'cost_per_hour': float
    state: dict with cluster state snapshot:
        'allocated_cpu': dict mapping node_id -> float (current allocated CPU)
        'allocated_mem': dict mapping node_id -> float (current allocated Mem)
        'remaining_cpu': dict mapping node_id -> float
        'remaining_mem': dict mapping node_id -> float
        'active_node_ids': list of node_ids currently harboring running pods
        'placed_pods_count': dict mapping node_id -> int
        'sim_time': float (current simulation timestamp in seconds)

    Returns:
        chosen_node_id (must be an element of feasible_nodes)
    \"\"\"
```
Optionally, you may also define:
```python
def select_pod(pending_pods: list[dict], nodes: list[dict], state: dict) -> int:
    \"\"\"Optionally pick which pod from pending_pods to schedule first.\"\"\"
```

### Constraints & Engineering Rules
1. Return ONLY the chosen `node_id` from `feasible_nodes`.
2. Do not crash or raise exceptions. Guard against division by zero and empty collections.
3. Keep the decision logic fast: $O(|\\text{{feasible\\_nodes}}|)$ time complexity per pod. Precompute set lookups (e.g., `active_set = set(state['active_node_ids'])`) outside node iteration loops for speed.
4. Only standard Python libraries are allowed: `math`, `random`, `collections`, `itertools`, `heapq`, `copy`, `typing`.
5. Enclose all code within a single ```python ... ``` markdown block.
"""
    return prompt.strip()
