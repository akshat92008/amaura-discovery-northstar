"""
Experiment #12: Prompt Templates for Targeted Refinement vs Independent Best-of-N
================================================================================
Conditions:
- Condition A (Independent Best-of-N): 15 distinct conceptual prompt perspectives.
- Condition R (Targeted Refinement):
    - Generation Phase (Calls 1-10): First 10 prompt angles from Condition A.
    - Refinement Phase (Calls 11-15): 5 targeted refinement objectives starting from the SAME frozen parent:
        1. Simplification (remove unnecessary complexity, preserve/improve quality)
        2. Bottleneck Analysis (address machine idle time and critical stage delays)
        3. Generalization (improve robustness across varying problem dimensions without overfitting)
        4. Bounded Local Improvement (bounded perturbation/swap pass with strict iteration cap)
        5. Independent Critical Review (skeptical algorithm researcher audit and principled modification)
"""

import ast
import re
from typing import Dict, Any, List, Optional, Tuple


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
1. Pure Python 3 only. Only standard library modules `math`, `random`, `typing`, `collections`, `itertools`, `heapq`, `copy` may be imported. No other imports are permitted.
2. Computational Budget: Your algorithm must execute fast (<50 ms per instance, with instances up to n=120 jobs, m=20 machines).
   - Any local search or improvement loop MUST have an explicit iteration cap scaled by problem size:
     `max_iter = max(2, min(8, 150 // max(n, 1)))` or at most 10,000 total makespan evaluations.
   - Do NOT run unbounded nested loops over all pairs.
   - Unbounded while-loops or unbounded neighborhood scans are strictly forbidden.
3. Output must be ONLY executable Python code inside a ```python ... ``` block.
"""

# 15 distinct conceptual prompt perspectives for Condition A (and Condition R Gen Phase 0-9)
INDEPENDENT_PROMPT_ANGLES: List[Tuple[str, str]] = [
    (
        "Bottleneck-Focused Heuristic",
        "Identify the bottleneck machines (stages with highest total processing load or variance) and design a heuristic that prioritizes scheduling jobs to minimize idle waiting time and queue buildup on those critical bottleneck stages."
    ),
    (
        "Machine-Load-Focused Heuristic",
        "Compute cumulative processing loads across early, middle, and late machine stages. Sequence jobs to balance the front-to-back workload flow and eliminate starvation on upstream and downstream machines."
    ),
    (
        "Constructive Greedy Insertion Approach",
        "Design a constructive insertion algorithm that ranks jobs by a priority metric (e.g., total processing time, front/back machine skew) and iteratively inserts each job into the partial schedule at the position that minimizes partial makespan."
    ),
    (
        "Johnson-Inspired Composite Heuristic",
        "Generalize Johnson's 2-machine optimal rule to m machines by aggregating machines into artificial two-machine virtual stages (e.g., early stages vs late stages) and sorting jobs by their relative stage affinities."
    ),
    (
        "Idle-Time Minimization Heuristic",
        "Construct the schedule by evaluating the exact idle time incurred on all intermediate machines when appending candidate jobs, selecting jobs that minimize cumulative machine dead-time."
    ),
    (
        "Critical-Path-Inspired Approach",
        "Analyze the potential critical path of operations through the flow shop grid. Prioritize jobs whose operations are most likely to lie on the critical path to shrink the bounding makespan envelope."
    ),
    (
        "Multi-Start Constructive Search",
        "Generate a small set (e.g. 2 to 4) of candidate initial permutations using complementary ranking criteria (e.g. descending total time, slope index, bottleneck affinity), construct schedules for each, and return the permutation with the lowest makespan."
    ),
    (
        "Flowtime-Aware Heuristic",
        "Order jobs to minimize total completion times and work-in-progress inventory, leveraging the empirical correlation between low mean flowtime and compact overall makespan."
    ),
    (
        "Hybrid Constructive Dispatching",
        "Combine static job characteristics (total processing time, machine slope) with dynamic schedule state (current machine completion times) in a composite index to dispatch jobs sequentially."
    ),
    (
        "Stochastic Ordering with Deterministic Tie-Breaking",
        "Use a randomized priority sampling mechanism with deterministic probability weighting based on processing time distributions, followed by deterministic insertion placement."
    ),
    (
        "Slope-Based Index Heuristic",
        "Calculate a slope index for each job measuring whether processing times trend upward or downward across machines from stage 0 to stage m-1. Sort jobs with descending slopes early and ascending slopes late."
    ),
    (
        "Machine-Correlation-Aware Heuristic",
        "Identify pairs of adjacent machines with strong processing time correlation. Order jobs to synchronize handover between correlated stages and avoid blocking."
    ),
    (
        "Position-Dependent Weighting Approach",
        "Apply position-dependent weights that place heavier emphasis on early machines for jobs placed early in the schedule, and heavier emphasis on late machines for jobs placed late in the schedule."
    ),
    (
        "Constructive Heuristic with Bounded Neighborhood Polish",
        "Build a solid initial schedule using a priority insertion rule, then apply a strictly bounded neighborhood polish (testing limited adjacent swaps with max_iter = max(2, min(8, 150 // max(n, 1)))) to improve makespan without exceeding runtime limits."
    ),
    (
        "Unrestricted Novel Algorithmic Approach",
        "Explore an original, novel combinatorial heuristic that combines structural properties of the processing time matrix into an efficient, deterministic sequence generator."
    )
]


def get_condition_a_prompt(call_idx: int) -> str:
    angle_name, angle_desc = INDEPENDENT_PROMPT_ANGLES[call_idx % len(INDEPENDENT_PROMPT_ANGLES)]
    return f"""{PROBLEM_DESCRIPTION}

Exploration Focus: {angle_name}
{angle_desc}

Implement `schedule_flowshop(times)` adhering strictly to the computational budget and signature rules.
Return ONLY valid Python code inside a ```python ... ``` block.
"""


def get_condition_r_generation_prompt(call_idx: int) -> str:
    # First 10 calls use the first 10 prompt angles from Condition A
    return get_condition_a_prompt(call_idx)


# 5 Distinct Targeted Refinement Objectives for Condition R Phase 2
REFINEMENT_OBJECTIVES = [
    {
        "name": "Simplification & Efficiency Polish",
        "instruction": (
            "Analyze the parent algorithm and identify any unnecessary complexity, redundant evaluations, "
            "inefficient loops, or over-complicated logic. "
            "Your objective: Simplify the code, eliminate redundant work, and optimize the algorithmic flow "
            "so that it executes cleaner and faster while preserving or improving solution makespan. "
            "Do NOT add new heavy loops."
        )
    },
    {
        "name": "Bottleneck & Idle-Time Hardening",
        "instruction": (
            "Analyze where the parent algorithm is likely losing performance on flow shop instances. "
            "Focus specifically on machine idle time, queue buildup, and bottleneck stages where jobs wait "
            "for previous operations to clear. "
            "Your objective: Modify the parent algorithm's job ordering or insertion tie-breaking mechanism "
            "to specifically protect bottleneck machines and reduce machine starvation."
        )
    },
    {
        "name": "Generalization & Scale Robustness",
        "instruction": (
            "Inspect the parent algorithm for potential brittleness or implicit assumptions that work only on specific "
            "instance sizes (e.g. small n). "
            "Your objective: Modify the parent algorithm to generalize robustly across diverse, unseen problem dimensions "
            "(varying from n=20 to n=120 jobs, and m=5 to m=20 machines). "
            "Ensure dynamic scaling of any loops (e.g. max_iter = max(2, min(8, 150 // max(n, 1)))) so the logic stays "
            "scalable, effective, and well within runtime limits on all problem sizes."
        )
    },
    {
        "name": "Bounded Local Improvement Polish",
        "instruction": (
            "Identify one concrete algorithmic weakness in the parent algorithm's final schedule. "
            "Your objective: Add a strictly bounded, highly focused local improvement pass (such as a restricted "
            "adjacent-swap scan or single-job relocate pass on the most critical jobs). "
            "STRICT CONSTRAINT: You MUST bound the loop with `max_iter = max(2, min(8, 150 // max(n, 1)))` or at most "
            "200 total makespan evaluations. Do NOT add unbounded loops or O(n^3) scans."
        )
    },
    {
        "name": "Independent Critical Review & Principled Modification",
        "instruction": (
            "Act as a skeptical senior algorithm researcher reviewing the parent implementation. "
            "Critically scrutinize the mathematical logic, the priority weighting formula, and the tie-breaking rules. "
            "Identify any mathematically flawed assumptions or missed opportunities in how jobs are prioritized. "
            "Your objective: Propose and implement a concrete modification ONLY if you have a defensible, principled "
            "theoretical reason that it will improve makespan performance. Do not make arbitrary or cosmetic changes."
        )
    }
]


def get_condition_r_refinement_prompt(
    parent_cand: Dict[str, Any],
    refinement_idx: int
) -> str:
    clean_parent = clean_code_for_prompt(parent_cand["code"], max_chars=3000)
    parent_score = parent_cand["development_score"]
    parent_cid = parent_cand["candidate_id"]
    parent_time = parent_cand.get("runtime_ms", 0.0)

    ref_spec = REFINEMENT_OBJECTIVES[refinement_idx % len(REFINEMENT_OBJECTIVES)]
    ref_name = ref_spec["name"]
    ref_instruction = ref_spec["instruction"]

    return f"""{PROBLEM_DESCRIPTION}

======================================================================
TARGETED REFINEMENT TASK (Condition R — Refinement #{refinement_idx+1}/5)
======================================================================
You are provided with a high-performing parent algorithm discovered during the generation phase.
- Parent Candidate ID: {parent_cid}
- Parent Development Total Makespan: {parent_score}
- Parent Total Execution Runtime: {parent_time:.1f} ms across 30 instances

[PARENT SOURCE CODE]
```python
{clean_parent}
```

REFINEMENT OBJECTIVE: {ref_name}
{ref_instruction}

Refinement Requirements:
1. Start directly from the parent algorithm's design and refine it according to the objective above.
2. The refined code must be self-contained and implement `def schedule_flowshop(times: list[list[int]]) -> list[int]:`.
3. Adhere strictly to the computational budget (fast execution, loop bounding max_iter = max(2, min(8, 150 // max(n, 1)))).
4. Output ONLY the refined Python code inside a ```python ... ``` block.
"""
