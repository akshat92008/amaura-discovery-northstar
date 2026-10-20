"""
Experiment #11: Prompt Templates for PFSP Search Conditions
===========================================================
Conditions:
- Condition A: Independent Search (5 distinct heuristic angles, zero memory)
- Condition C: Behavioral Quality-Diversity (Kendall-tau guided, stripped code, zero human labels)

Features:
- clean_code_for_prompt(): Strips docstrings, comments, and empty lines, enforces 3000-char cap.
- Explicit computational budget instructions: Dynamic loop bounding max_iter = max(2, min(8, 150 // max(n, 1)))
- Zero human taxonomy labels in Condition C.
"""

import ast
import re
from typing import Dict, Any, List, Optional


def clean_code_for_prompt(code: str, max_chars: int = 3000) -> str:
    """Strips docstrings, comments, empty lines, and enforces character cap to prevent prompt bloat."""
    if not code:
        return ""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)):
                    node.body[0] = ast.Pass()
        code_str = ast.unparse(tree)
    except Exception:
        code_str = code

    lines = []
    for line in code_str.splitlines():
        stripped = re.sub(r'#.*$', '', line).rstrip()
        if stripped:
            lines.append(stripped)
    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n    # ... (truncated for token economy)"
    return result


PROBLEM_DESCRIPTION = """
Permutation Flow Shop Scheduling (PFSP - Fm | prmu | C_max):
- There are n jobs and m machines.
- All jobs must be processed through machines 0, 1, ..., m-1 in that exact technological order.
- Processing times are given in a 2D matrix `times`, where `times[j][k]` is the processing time of job j on machine k (0 <= j < n, 0 <= k < m).
- The same job sequence (permutation) is used across all machines.
- A job cannot start on machine k until it finishes on machine k-1 AND machine k has completed any prior job.
- Goal: Find a job permutation (a list of job indices 0 to n-1) that minimizes the makespan C_max (completion time of the last job on the last machine).

Required Function Signature:
```python
def schedule_flowshop(times: list[list[int]]) -> list[int]:
    # Returns a valid permutation of list(range(len(times)))
```

Execution & Computational Budget Rules:
1. Pure Python 3 only. Only `math` and `random` may be imported. No other imports are permitted.
2. Computational Budget: Your algorithm must execute fast (<50 ms per instance, with instances up to n=120 jobs, m=20 machines).
   - Any local search or improvement loop MUST have an explicit iteration cap scaled by problem size:
     `max_iter = max(2, min(8, 150 // max(n, 1)))` or at most 10,000 total makespan evaluations.
   - Do NOT run unbounded nested loops over all pairs.
   - Unbounded while-loops or unbounded neighborhood scans are strictly forbidden.
3. Output must be ONLY executable Python code inside a ```python ... ``` block.
"""

CONDITION_A_ANGLES = [
    (
        "Constructive Greedy Insertion Approach",
        "Design a constructive algorithm that orders jobs by a priority metric (e.g., total processing time, front/back machine skew) and iteratively inserts each job into the partial schedule at the position that minimizes partial makespan or machine idle time."
    ),
    (
        "Machine Bottleneck & Cumulative Idle-Time Approach",
        "Design an algorithm that identifies the bottleneck machines (machines with highest cumulative load) and constructs a sequence that minimizes idle time on those critical stages and avoids queue buildup."
    ),
    (
        "Slope Index & Profile Matching Approach",
        "Design an algorithm that computes a multi-stage slope or trend index for each job (measuring whether processing requirements ramp up or down across the machine sequence) and sorts jobs to create a balanced production flow."
    ),
    (
        "Constructive Heuristic with Bounded Local Improvement",
        "Design an algorithm that first constructs an initial schedule using a fast priority rule, and then applies a fast, bounded local improvement pass (e.g., testing limited adjacent swaps or single-job relocations with max_iter = max(2, min(8, 150 // max(n, 1)))) to reduce makespan without exceeding runtime limits."
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


def get_condition_c_novelty_prompt(
    ref_elite: Dict[str, Any],
    avg_archive_distance: float
) -> str:
    c_ref = clean_code_for_prompt(ref_elite['code'])
    return f"""{PROBLEM_DESCRIPTION}

Current Reference Elite (Achieves Total Makespan: {ref_elite['development_score']}):
```python
{c_ref}
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
- Keep the code lean, fast (<50 ms per instance, bounded loops: max_iter = max(2, min(8, 150 // max(n, 1)))), and return a strictly valid permutation.

Provide ONLY the Python code in a ```python ... ``` block.
"""


def get_condition_c_bridge_prompt(
    elite1: Dict[str, Any],
    elite2: Dict[str, Any],
    pair_dist: float
) -> str:
    c1 = clean_code_for_prompt(elite1['code'])
    c2 = clean_code_for_prompt(elite2['code'])
    return f"""{PROBLEM_DESCRIPTION}

Archived Elite 1 (Total Makespan: {elite1['development_score']}):
```python
{c1}
```

Archived Elite 2 (Total Makespan: {elite2['development_score']}):
```python
{c2}
```

Behavioral Analysis:
These two algorithms occupy fundamentally different behavioral niches in our solution archive (normalized Kendall tau distance = {pair_dist:.3f}).
Elite 1 achieves total makespan {elite1['development_score']}, while Elite 2 achieves total makespan {elite2['development_score']}.

Your Task:
Synthesize a novel algorithm `def schedule_flowshop(times: list[list[int]]) -> list[int]:`
that discovers a new high-performing sequencing strategy:
- Synthesize an alternative approach that achieves a lower total makespan by exploring a distinct permutation structure that neither elite alone exploits.
- Ensure the solver executes fast (<50 ms per instance, bounded loops: max_iter = max(2, min(8, 150 // max(n, 1)))), and returns a strictly valid permutation.

Provide ONLY the Python code in a ```python ... ``` block.
"""
