"""
Stage 2: Diversified Perspectives for PFSP (Arm C)
==================================================
Defines 20 distinct conceptual perspectives for generating the diversified Arm C pool.
Zero leakage: Does NOT copy historical winners from previous experiments.
"""

from typing import List, Dict, Any

AMAURA_PERSPECTIVES_PFSP: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Palmer Slope Index with Machine Variance Weighting",
        "category": "Slope Heuristic",
        "prompt": "Design a PFSP algorithm based on Palmer's slope index, but weight each machine's contribution inversely by its processing time variance. Explain how this mitigates slope distortion caused by erratic machine loads."
    },
    {
        "id": 2,
        "name": "Bottleneck Machine Centering & Idle Time Minimization",
        "category": "Bottleneck Perspective",
        "prompt": "Design a flow shop heuristic that explicitly identifies the machine with the highest total workload (the bottleneck machine). Schedule jobs to minimize front-idle time leading into the bottleneck and back-idle time trailing it."
    },
    {
        "id": 3,
        "name": "NEH with Accelerated Partial Makespan Bounds",
        "category": "Insertion Heuristic",
        "prompt": "Design an NEH-style constructive algorithm that uses lower-bounding techniques (e.g. Taillard's machine-based lower bounds) to quickly reject poor insertion slots before computing full completion paths."
    },
    {
        "id": 4,
        "name": "Two-Machine Reduction & Johnson's Rule Decomposition",
        "category": "Decomposition",
        "prompt": "Design a Campbell-Dudek-Smith (CDS) variant that creates m-1 artificial two-machine subproblems, applies Johnson's Rule to each, and selects the permutation with the best full m-machine makespan."
    },
    {
        "id": 5,
        "name": "Iterated Greedy with Temperature-Cooling Acceptance",
        "category": "Local Search",
        "prompt": "Design a bounded Iterated Greedy (IG) algorithm: initialize with a greedy ordering, repeatedly remove d=3 jobs at random, reconstruct greedily via NEH insertion, and accept modifications using a simulated annealing temperature criterion."
    },
    {
        "id": 6,
        "name": "Front-Back Profile Asymmetry (Gupta Heuristic)",
        "category": "Profile Heuristic",
        "prompt": "Design an algorithm based on Gupta's heuristic: assess whether each job's processing load is concentrated on early machines (to be scheduled first) or late machines (to be scheduled last), using sign-weighted machine differences."
    },
    {
        "id": 7,
        "name": "Machine Idle-Time & Job Waiting Penalty Minimization",
        "category": "Scheduling Theory",
        "prompt": "Design a constructive heuristic that tracks both machine idle time and job waiting time at each step. Choose the next job to schedule that minimizes the sum of cumulative machine starvation and job buffer delay."
    },
    {
        "id": 8,
        "name": "Adaptive Tie-Breaking in NEH Insertion",
        "category": "Insertion Heuristic",
        "prompt": "Design an NEH insertion heuristic with intelligent tie-breaking: when two insertion positions yield the exact same makespan, break ties by selecting the position that minimizes machine idle time on the last machine."
    },
    {
        "id": 9,
        "name": "Adjacent Pairwise Interchange (1-Opt Local Descent)",
        "category": "Local Search",
        "prompt": "Design an algorithm that generates an initial profile-sorted permutation and executes a bounded adjacent pairwise interchange (bubble-sort style descent) until a local minimum or iteration cap is reached."
    },
    {
        "id": 10,
        "name": "Skewness & Bimodal Workload Partitioning",
        "category": "Workload Profiling",
        "prompt": "Design a flow shop heuristic that analyzes whether job sizes are bimodal. Group jobs into 'anchor' jobs (consistently large) and 'filler' jobs (small/transient), interleaving them to prevent continuous queue buildup on middle machines."
    },
    {
        "id": 11,
        "name": "U-Shaped Load Balancing for Asymmetric Factories",
        "category": "Structural Analysis",
        "prompt": "Design a scheduling heuristic specifically tailored for U-shaped machine workloads (where machine 1 and machine m are heavy, while intermediate machines are light). Focus job ordering on fast clearing of machine 1."
    },
    {
        "id": 12,
        "name": "Multi-Pass Stochastic NEH with Perturbed Priorities",
        "category": "Diversification Perspective",
        "prompt": "Design an algorithm that runs 3 fast randomized NEH passes: add random multiplicative noise (0.9 to 1.1) to the initial total-time sorting, construct sequences, and retain the best makespan."
    },
    {
        "id": 13,
        "name": "Critical Path Machine Slack Minimization",
        "category": "Critical Path Analysis",
        "prompt": "Design a flow shop algorithm that computes the critical path of the schedule after scheduling each job. Prioritize subsequent jobs that add operations to non-critical machine slack rather than extending the critical path."
    },
    {
        "id": 14,
        "name": "Variable Neighborhood Search (Insert and Swap)",
        "category": "Local Search",
        "prompt": "Design a lightweight Variable Neighborhood Search (VNS) with two neighborhoods: single-job relocation (insert) and job-pair swap. Alternate neighborhoods when one gets stuck in a local minimum."
    },
    {
        "id": 15,
        "name": "Skeptical Failure-Mode Analysis on NEH Starvation",
        "category": "Skeptical Perspective",
        "prompt": "Analyze where standard NEH fails: specifically when the largest total-time job has an abnormally huge first operation that stalls the entire pipeline. Design a correction that penalizes high first-machine processing times during initial job sorting."
    },
    {
        "id": 16,
        "name": "Lagrangian Relaxation Lower Bound Guidance",
        "category": "Mathematical Programming",
        "prompt": "Design a heuristic inspired by Lagrangian relaxation of machine capacity constraints: compute machine shadow prices based on cumulative machine load and order jobs to balance shadow price consumption."
    },
    {
        "id": 17,
        "name": "High Aspect Ratio Pipelining (N >> M)",
        "category": "Pipelining Perspective",
        "prompt": "Design an algorithm optimized for high aspect ratio flow shops (many jobs N, few machines M). Structure the sequence to establish a steady-state fluid pipeline as quickly as possible, ignoring tail effects."
    },
    {
        "id": 18,
        "name": "Square Aspect Ratio Coordination (N ~= M)",
        "category": "Pipelining Perspective",
        "prompt": "Design an algorithm optimized for square flow shops where machine count M is comparable to job count N. Treat the problem as a 2D diagonal wavefront clearance problem."
    },
    {
        "id": 19,
        "name": "Block Insertion (Window-Based NEH)",
        "category": "Insertion Heuristic",
        "prompt": "Design an algorithm that inserts jobs in small blocks of 2 jobs simultaneously into the current partial sequence, evaluating combined placement to account for pairwise synergy."
    },
    {
        "id": 20,
        "name": "Hybrid Beam Search with Width K=2",
        "category": "Hybrid Composition",
        "prompt": "Design a lightweight Beam Search for PFSP: at each constructive step, maintain the top K=2 partial candidate sequences, expand both, and prune back to K=2 using partial completion makespan."
    }
]
