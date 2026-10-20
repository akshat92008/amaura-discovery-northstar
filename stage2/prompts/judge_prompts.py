"""
Stage 2: Execution-Blind Judge Prompts & Presentation Formatting
===============================================================
Enforces Section 3:
- The judge sees ONLY problem specification and candidate code.
- Zero execution results, zero benchmark scores, zero rankings, zero historical data.
- Standardized presentation of candidates under anonymous IDs (e.g. Option_01 .. Option_20).
"""

from typing import List, Dict, Any


def build_judge_prompt(
    problem_type: str,
    shuffled_candidates: List[Dict[str, Any]]
) -> str:
    """
    Constructs the prompt presenting anonymized candidate codes to the judge.
    shuffled_candidates: list of dicts with 'option_id' (e.g. Option_01) and 'code'.
    """
    if problem_type == "graph_coloring":
        problem_desc = (
            "PROBLEM: Vertex Graph Coloring\n"
            "TARGET: Minimize the total number of distinct colors assigned to vertices while ensuring "
            "no two adjacent vertices share the same color. Execution must be fast and scale to N=100 vertices.\n"
        )
    elif problem_type == "pfsp":
        problem_desc = (
            "PROBLEM: Permutation Flow Shop Scheduling (PFSP, Fm | prmu | C_max)\n"
            "TARGET: Minimize total makespan C_max across all machines for a set of N jobs and M machines. "
            "Execution must remain well bounded and avoid exponential combinatorial explosions.\n"
        )
    else:
        raise ValueError(f"Unknown problem_type: {problem_type}")

    options_text = []
    for cand in shuffled_candidates:
        opt_id = cand["option_id"]
        code = cand["code"]
        options_text.append(f"### {opt_id}\n```python\n{code}\n```\n")

    prompt = f"""You are a senior algorithmic peer-reviewer and combinatorial optimization judge.
{problem_desc}

Below are {len(shuffled_candidates)} candidate Python algorithms designed for this problem.
Your task is to critically analyze each candidate's algorithmic structure, computational complexity, heuristic principles, and likelihood of producing superior solutions across diverse, unseen problem instances.

EVALUATION CRITERIA:
1. Algorithmic Rigor: Does the heuristic use sound theoretical principles (e.g., dynamic tie-breaking, bottleneck mitigation, saturation tracking) rather than simplistic arbitrary rules?
2. Robustness across Distributions: Will the logic generalize well across dense, sparse, clustered, and asymmetric instances?
3. Computational Feasibility: Is the time complexity strictly polynomial and bounded so it does not time out?
4. Cleanliness and Correctness: Is the implementation free of edge-case bugs, infinite loops, or unhandled exceptions?

CANDIDATES FOR REVIEW:
{"".join(options_text)}

INSTRUCTIONS:
1. Provide a concise comparative rationale discussing the top contenders.
2. End your response with the exact line:
`SELECTED_CANDIDATE: Option_XX`
(where Option_XX is the exact label of the single best candidate you have chosen).
"""
    return prompt


JUDGE_SYSTEM_PROMPT = (
    "You are an impartial, highly rigorous expert judge in algorithm design and combinatorial optimization. "
    "Evaluate candidate algorithms purely based on their code, theoretical depth, and algorithmic potential. "
    "You must declare exactly one winning option using the required output format: `SELECTED_CANDIDATE: Option_XX`."
)
