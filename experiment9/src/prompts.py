"""
Experiment #9: Prompt Templates for PFSP Search Conditions
==========================================================
Conditions:
- Condition A: Independent Search (5 distinct heuristic angles, zero memory)
- Condition B: Naive Evolution (Exploitation Refinement & Crossover)
- Condition C: Behavioral Quality-Diversity (Phenotypic distance guidance, ZERO human taxonomic labels)
"""

from typing import Dict, Any, List, Optional
from experiment9.src.kendall import mean_behavioral_distance

PROBLEM_DESCRIPTION = """
Permutation Flow Shop Scheduling (PFSP - Fm | prmu | C_max):
- There are n jobs and m machines.
- All jobs must be processed through machines 0, 1, ..., m-1 in that exact order.
- Processing times are given in a 2D matrix `times`, where `times[j][k]` is the processing time of job j on machine k (0 <= j < n, 0 <= k < m).
- The same job sequence (permutation) is used across all machines.
- A job cannot start on machine k until it finishes on machine k-1 AND machine k has completed any prior job.
- Goal: Find a job permutation (a list of job indices 0 to n-1) that minimizes the makespan C_max (completion time of the last job on the last machine).

Required Function Signature:
```python
def schedule_flowshop(times: list[list[int]]) -> list[int]:
    # Returns a valid permutation of list(range(len(times)))
```

Execution Rules:
1. Pure Python 3 only.
2. Only `math` and `random` may be imported. No other imports are permitted.
3. Fast execution: The function must run well within 50 ms per instance (instances up to 100 jobs and 15 machines).
4. Output must be ONLY executable Python code inside a ```python ... ``` block.
"""

# Condition A prompt angles
CONDITION_A_ANGLES = [
    (
        "Constructive Greedy Insertion Approach",
        "Design a constructive algorithm that orders jobs by a priority metric (e.g., total processing time, front/back machine skew) and iteratively inserts each job into the partial schedule at the position that minimizes partial makespan or machine idle time."
    ),
    (
        "Machine Bottleneck & Cumulative Idle-Time Approach",
        "Design an algorithm that identifies the bottleneck machines (machines with the highest total processing loads) and constructs a sequence that minimizes idle time on those critical stages and avoids queue buildup."
    ),
    (
        "Slope Index & Profile Matching Approach",
        "Design an algorithm that computes a multi-stage slope or trend index for each job (measuring whether processing requirements ramp up or down across the machine sequence) and sorts jobs to create a balanced production flow."
    ),
    (
        "Constructive Heuristic with Bounded Local Improvement",
        "Design an algorithm that first constructs an initial schedule using a fast priority rule, and then applies a fast, bounded local improvement pass (e.g., testing limited adjacent swaps or single-job relocations with an early termination cap) to reduce makespan without exceeding runtime limits."
    ),
    (
        "Dynamic Composite Dispatching Approach",
        "Design an algorithm that iteratively selects the next job to append to the schedule using a composite scoring function that balances machine readiness, remaining processing times, and potential downstream blocking."
    ),
]


def get_condition_a_prompt(call_idx: int) -> str:
    angle_name, angle_desc = CONDITION_A_ANGLES[call_idx % len(CONDITION_A_ANGLES)]
    return f"""{PROBLEM_DESCRIPTION}

Exploration Focus: {angle_name}
{angle_desc}

Synthesize a complete, robust, and fast Python function `def schedule_flowshop(times: list[list[int]]) -> list[int]:`.
Provide ONLY the Python code in a ```python ... ``` block.
"""


def get_condition_b_refine_prompt(parent: Dict[str, Any]) -> str:
    return f"""{PROBLEM_DESCRIPTION}

Current Best Algorithm (Achieves Total Makespan: {parent['development_score']}):
```python
{parent['code']}
```

Optimization Goal:
The current best algorithm achieves a total makespan of {parent['development_score']} on our 30 development instances.
Your task is to refine and optimize this algorithm to achieve an even LOWER total makespan.
- Analyze the heuristic logic, tie-breaking criteria, weighting factors, or insertion order.
- Improve the scheduling decisions so machine idle time and makespan are reduced.
- Ensure the algorithm remains strictly valid, deterministic (or controlled pseudo-random), and fast (<50 ms per instance).

Synthesize the improved Python solver `def schedule_flowshop(times: list[list[int]]) -> list[int]:`.
Provide ONLY the Python code in a ```python ... ``` block.
"""


def get_condition_b_crossover_prompt(parent1: Dict[str, Any], parent2: Dict[str, Any]) -> str:
    return f"""{PROBLEM_DESCRIPTION}

Parent Algorithm 1 (Total Makespan: {parent1['development_score']}):
```python
{parent1['code']}
```

Parent Algorithm 2 (Total Makespan: {parent2['development_score']}):
```python
{parent2['code']}
```

Hybridization Goal:
These two algorithms represent the two strongest distinct strategies discovered so far.
Your task is to synthesize a superior hybrid algorithm that combines the best architectural ideas from both parents:
- Integrate their complementary mechanisms (e.g., combining a superior initial ordering with a more effective insertion or tie-breaking logic).
- Achieve a lower makespan than either parent while staying well within the runtime limit (<50 ms per instance).

Synthesize the hybrid Python solver `def schedule_flowshop(times: list[list[int]]) -> list[int]:`.
Provide ONLY the Python code in a ```python ... ``` block.
"""


def get_condition_c_novelty_prompt(
    ref_elite: Dict[str, Any],
    avg_archive_distance: float
) -> str:
    """
    Condition C Prompt: Guides toward phenotypic behavioral novelty.
    CRITICAL: Contains ZERO human-taxonomic labels.
    """
    return f"""{PROBLEM_DESCRIPTION}

Current Reference Elite (Achieves Total Makespan: {ref_elite['development_score']}):
```python
{ref_elite['code']}
```

Behavioral Analysis:
On our benchmark suite, this reference algorithm produces job sequences with a distinct scheduling pattern.
Its average normalized Kendall tau behavioral distance to other candidate solutions is {avg_archive_distance:.3f}.

Your Task:
Synthesize a complete Python solver `def schedule_flowshop(times: list[list[int]]) -> list[int]:`
that achieves a LOW total makespan while making FUNDAMENTALLY DIFFERENT sequencing decisions:
- The output permutations produced by your algorithm must systematically differ in job ordering (high Kendall tau distance from the reference schedule).
- Explore an entirely different computational heuristic for resolving machine bottlenecks, idle times, and job sequences.
- Do NOT simply make cosmetic tweaks, rename variables, or make minor parameter adjustments to the reference algorithm.
- Must execute fast (<50 ms per instance) and return a strictly valid permutation.

Provide ONLY the Python code in a ```python ... ``` block.
"""


def get_condition_c_bridge_prompt(
    elite1: Dict[str, Any],
    elite2: Dict[str, Any],
    pair_dist: float
) -> str:
    """
    Condition C Prompt: Bridges two behaviorally distant elites.
    CRITICAL: Contains ZERO human-taxonomic labels.
    """
    return f"""{PROBLEM_DESCRIPTION}

Archived Elite 1 (Total Makespan: {elite1['development_score']}):
```python
{elite1['code']}
```

Archived Elite 2 (Total Makespan: {elite2['development_score']}):
```python
{elite2['code']}
```

Behavioral Analysis:
These two algorithms occupy fundamentally different behavioral niches in our solution archive (normalized Kendall tau distance = {pair_dist:.3f}).
Elite 1 achieves total makespan {elite1['development_score']}, while Elite 2 achieves total makespan {elite2['development_score']}.

Your Task:
Synthesize a novel algorithm `def schedule_flowshop(times: list[list[int]]) -> list[int]:`
that discovers a new high-performing sequencing strategy:
- Synthesize an alternative approach that achieves a lower total makespan by exploring a distinct permutation structure that neither elite alone exploits.
- Ensure the solver executes fast (<50 ms per instance) and returns a strictly valid permutation.

Provide ONLY the Python code in a ```python ... ``` block.
"""
