"""
PFSP Full Algorithm Domain: Autonomous Discovery Interface
===========================================================
Interface:
def solve(processing_times: list[list[int]]) -> list[int]:

Allows candidate to implement arbitrary deterministic algorithms:
- Alternative sorting heuristics
- Insertion procedures
- Local search over permutations
- Hybrids / composite heuristics

Outer evaluator calculates schedule makespan C_max and verifies permutation validity.
"""

import copy
import json
import math
import os
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

import signal
from stage3.src.sandbox import check_ast_security, sanitize_and_compile, sanitize_exception_name, SAFE_BUILTINS, _sigalrm_handler, SandboxTimeoutException


def validate_permutation(perm: Any, n: int) -> Tuple[bool, Optional[str]]:
    """Strictly validates that perm is a valid permutation of [0, 1, ..., n-1]."""
    if not isinstance(perm, (list, tuple)):
        return False, f"Output must be a list, got {type(perm).__name__}"
    if len(perm) != n:
        return False, f"Permutation length {len(perm)} does not match number of jobs {n}"
    for x in perm:
        if isinstance(x, bool) or not isinstance(x, int):
            return False, f"Permutation contains non-integer element: {x} (type {type(x).__name__})"
        if x < 0 or x >= n:
            return False, f"Job index {x} out of range [0, {n-1}]"
    if len(set(perm)) != n:
        return False, f"Permutation contains duplicate job IDs (unique: {len(set(perm))}, expected: {n})"
    return True, None


def calc_makespan(times: List[List[int]], perm: List[int]) -> int:
    """Computes exact makespan C_max of permutation on processing times matrix (n jobs x m machines)."""
    if not times or not perm:
        return 0
    m = len(times[0])
    completion = [0] * m
    for job in perm:
        completion[0] += times[job][0]
        for c in range(1, m):
            left = completion[c - 1]
            top = completion[c]
            completion[c] = (left if left > top else top) + times[job][c]
    return completion[-1]


# Standard Classical Baselines
def neh_solve(processing_times: List[List[int]]) -> List[int]:
    """Nawaz-Enscore-Ham (NEH 1983) Heuristic."""
    n = len(processing_times)
    if n == 0:
        return []
    m = len(processing_times[0])

    def calc_partial(seq):
        dp = [0] * m
        for j in seq:
            dp[0] += processing_times[j][0]
            for c in range(1, m):
                dp[c] = (dp[c - 1] if dp[c - 1] > dp[c] else dp[c]) + processing_times[j][c]
        return dp[-1]

    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)
    seq = [order[0]]
    for i in range(1, n):
        job = order[i]
        best_pos = 0
        best_val = float("inf")
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            c = calc_partial(cand)
            if c < best_val:
                best_val = c
                best_pos = pos
        seq.insert(best_pos, job)
    return seq


def neh_ls_solve(processing_times: List[List[int]]) -> List[int]:
    """NEH followed by single-pass insertion local search."""
    seq = neh_solve(processing_times)
    n = len(processing_times)
    cur_cmax = calc_makespan(processing_times, seq)

    for i in range(n):
        job = seq.pop(i)
        best_pos = i
        best_cmax = cur_cmax
        for pos in range(n):
            cand = seq[:pos] + [job] + seq[pos:]
            c = calc_makespan(processing_times, cand)
            if c < best_cmax:
                best_cmax = c
                best_pos = pos
        seq.insert(best_pos, job)
        cur_cmax = best_cmax
    return seq


def natural_order_solve(processing_times: List[List[int]]) -> List[int]:
    """Natural Order: [0, 1, ..., n-1]."""
    return list(range(len(processing_times)))


class PFSPFullAlgorithmDomain:
    """
    Problem domain for discovering full PFSP scheduling algorithms.
    """
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "pfsp")
        self.data_dir = data_dir

        with open(os.path.join(self.data_dir, "train.json"), "r", encoding="utf-8") as f:
            self.train_data = json.load(f)
        with open(os.path.join(self.data_dir, "test.json"), "r", encoding="utf-8") as f:
            self.test_data = json.load(f)

        # Baseline evaluation (train computed dynamically, test baselines pre-computed)
        self.baselines = {
            "train": self._evaluate_all_baselines(self.train_data),
            "test": {
                "neh": {"total_makespan": 176409, "mean_makespan": 4900.25},
                "neh_ls": {"total_makespan": 176145, "mean_makespan": 4892.92},
                "natural": {"total_makespan": 176820, "mean_makespan": 4911.67}
            }
        }

    def _evaluate_all_baselines(self, instances: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = {}
        for b_name, b_fn in [("neh", neh_solve), ("neh_ls", neh_ls_solve), ("natural", natural_order_solve)]:
            scores = []
            schedules = []
            for inst in instances:
                times = inst["times"]
                perm = b_fn(times)
                cmax = calc_makespan(times, perm)
                scores.append(cmax)
                schedules.append(perm)
            results[b_name] = {
                "total_makespan": sum(scores),
                "mean_makespan": sum(scores) / len(scores),
                "scores": scores,
                "schedules": schedules
            }
        return results

    @property
    def name(self) -> str:
        return "pfsp_full_algorithm"

    @property
    def function_name(self) -> str:
        return "solve"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert operations research scientist and algorithm designer specializing in combinatorial scheduling optimization.\n"
            "Keep internal reasoning concise (under 150 words). Immediately produce the complete, self-contained Python function `solve`.\n\n"
            "Your task is to design a high-performance Permutation Flow-Shop Scheduling (PFSP) algorithm in pure Python.\n\n"
            "Problem Definition:\n"
            "Given n jobs and m machines, each job j must be processed on machine 0, machine 1, ..., machine m-1 in that exact order.\n"
            "Job j takes times[j][c] time units on machine c.\n"
            "All machines process jobs in the identical permutation sequence (permutation flow shop).\n"
            "The objective is to find a permutation of job indices [0, 1, ..., n-1] that minimizes the makespan C_max (completion time of the last job on the last machine).\n\n"
            "Interface:\n"
            "```python\n"
            "def solve(processing_times: list[list[int]]) -> list[int]:\n"
            "```\n\n"
            "Parameters:\n"
            "- `processing_times: list[list[int]]`: 2D matrix of dimensions n x m.\n"
            "  `n = len(processing_times)` (number of jobs, e.g. 20 to 120).\n"
            "  `m = len(processing_times[0])` (number of machines, e.g. 5 to 15).\n"
            "  `processing_times[j][c]` is the processing time of job j on machine c.\n\n"
            "Returns:\n"
            "- `list[int]`: a valid permutation of integers `[0, 1, ..., n-1]` specifying the job processing sequence.\n\n"
            "Rules:\n"
            "1. Output MUST be a valid permutation of integers containing each index from 0 to n-1 exactly once.\n"
            "2. Do NOT hardcode instance-specific answers; your algorithm must be a general procedure solving arbitrary PFSP instances.\n"
            "3. Allowed standard libraries: `math`, `random`, `collections`, `itertools`, `heapq`, `copy`. Do NOT use unauthorized libraries.\n"
            "4. Keep execution fast and efficient (under 2 seconds per instance).\n"
            "5. Return ONLY valid Python inside a ```python ``` markdown block."
        )

    def get_user_prompt(self, proposal_idx: int) -> str:
        return (
            f"Design an innovative, highly effective scheduling algorithm `solve` for Permutation Flow-Shop Scheduling (variant {proposal_idx}).\n\n"
            "Baseline Reference (Nawaz-Enscore-Ham / NEH 1983):\n"
            "```python\n"
            "def solve(processing_times: list[list[int]]) -> list[int]:\n"
            "    n = len(processing_times)\n"
            "    if n == 0:\n"
            "        return []\n"
            "    m = len(processing_times[0])\n"
            "    \n"
            "    def calc_partial(seq):\n"
            "        dp = [0] * m\n"
            "        for j in seq:\n"
            "            dp[0] += processing_times[j][0]\n"
            "            for c in range(1, m):\n"
            "                dp[c] = (dp[c-1] if dp[c-1] > dp[c] else dp[c]) + processing_times[j][c]\n"
            "        return dp[-1]\n"
            "        \n"
            "    order = sorted(range(n), key=lambda j: sum(processing_times[j]), reverse=True)\n"
            "    seq = [order[0]]\n"
            "    for i in range(1, n):\n"
            "        job = order[i]\n"
            "        best_pos, best_val = 0, float('inf')\n"
            "        for pos in range(len(seq) + 1):\n"
            "            cand = seq[:pos] + [job] + seq[pos:]\n"
            "            c = calc_partial(cand)\n"
            "            if c < best_val:\n"
            "                best_val = c\n"
            "                best_pos = pos\n"
            "        seq.insert(best_pos, job)\n"
            "    return seq\n"
            "```\n\n"
            "Can you innovate beyond standard NEH?\n"
            "Consider:\n"
            "- Multi-criteria initial orderings (e.g. Palmer slope indices, machine idle penalties, machine workload variance).\n"
            "- Lookahead insertion evaluations or tie-breaking mechanisms.\n"
            "- Post-insertion local search (e.g. pairwise exchange or insertion refinement).\n"
            "- Novel composite constructive heuristics.\n\n"
            "Output the complete Python code for `solve`."
        )

    def evaluate_candidate(
        self,
        code_str: str,
        on_test: bool = False,
        per_instance_timeout_sec: float = 4.0,
        total_timeout_sec: float = 40.0
    ) -> Dict[str, Any]:
        """Evaluates candidate code with AST security, compilation, execution, and validation."""
        t0 = time.time()
        is_safe, error_msg = check_ast_security(code_str, required_func=self.function_name)
        if not is_safe:
            return {
                "is_valid": False,
                "error": error_msg,
                "total_makespan": None,
                "mean_makespan": None,
                "relative_gap": None,
                "beats_neh": False,
                "runtime_sec": round(time.time() - t0, 3),
                "per_instance_makespans": [],
                "schedules": []
            }

        try:
            code_obj = sanitize_and_compile(code_str, filename="<pfsp_candidate>")
            import typing
            namespace = {
                "__builtins__": SAFE_BUILTINS,
                "math": math,
                "random": __import__("random"),
                "collections": __import__("collections"),
                "itertools": __import__("itertools"),
                "heapq": __import__("heapq"),
                "copy": __import__("copy"),
                "typing": typing,
                "List": list,
                "Dict": dict,
                "Tuple": tuple,
                "Set": set,
                "Optional": typing.Optional,
                "Any": typing.Any,
                "Union": typing.Union,
                "Callable": typing.Callable,
            }
            exec(code_obj, namespace)
            cand_fn = namespace.get(self.function_name)
            if not callable(cand_fn):
                return {
                    "is_valid": False,
                    "error": f"Function '{self.function_name}' is not callable",
                    "total_makespan": None,
                    "mean_makespan": None,
                    "relative_gap": None,
                    "beats_neh": False,
                    "runtime_sec": round(time.time() - t0, 3),
                    "per_instance_makespans": [],
                    "schedules": []
                }
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Compilation error: {sanitize_exception_name(e)}",
                "total_makespan": None,
                "mean_makespan": None,
                "relative_gap": None,
                "beats_neh": False,
                "runtime_sec": round(time.time() - t0, 3),
                "per_instance_makespans": [],
                "schedules": []
            }

        instances = self.test_data if on_test else self.train_data
        baseline_neh = self.baselines["test"]["neh"]["total_makespan"] if on_test else self.baselines["train"]["neh"]["total_makespan"]

        cmaxes = []
        schedules = []

        for inst_idx, inst in enumerate(instances):
            times = inst["times"]
            n = len(times)

            # Defensive copy so candidate cannot alter instance times
            times_copy = [list(row) for row in times]

            prev_handler = None
            if hasattr(signal, "SIGALRM"):
                prev_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
                signal.setitimer(signal.ITIMER_REAL, per_instance_timeout_sec)

            t_inst_0 = time.time()
            try:
                perm = cand_fn(times_copy)
            except SandboxTimeoutException:
                return {
                    "is_valid": False,
                    "error": f"Timeout on instance {inst_idx} ({inst['id']}): exceeded limit {per_instance_timeout_sec}s (SIGALRM)",
                    "total_makespan": None,
                    "mean_makespan": None,
                    "relative_gap": None,
                    "beats_neh": False,
                    "runtime_sec": round(time.time() - t0, 3),
                    "per_instance_makespans": [],
                    "schedules": []
                }
            except Exception as e:
                return {
                    "is_valid": False,
                    "error": f"Runtime error on instance {inst_idx} ({inst['id']}): {sanitize_exception_name(e)}",
                    "total_makespan": None,
                    "mean_makespan": None,
                    "relative_gap": None,
                    "beats_neh": False,
                    "runtime_sec": round(time.time() - t0, 3),
                    "per_instance_makespans": [],
                    "schedules": []
                }
            finally:
                if hasattr(signal, "SIGALRM") and prev_handler is not None:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, prev_handler)

            inst_duration = time.time() - t_inst_0
            if inst_duration > per_instance_timeout_sec:
                return {
                    "is_valid": False,
                    "error": f"Timeout on instance {inst_idx} ({inst['id']}): took {inst_duration:.2f}s > {per_instance_timeout_sec}s",
                    "total_makespan": None,
                    "mean_makespan": None,
                    "relative_gap": None,
                    "beats_neh": False,
                    "runtime_sec": round(time.time() - t0, 3),
                    "per_instance_makespans": [],
                    "schedules": []
                }

            if time.time() - t0 > total_timeout_sec:
                return {
                    "is_valid": False,
                    "error": f"Total execution timeout exceeded ({total_timeout_sec}s)",
                    "total_makespan": None,
                    "mean_makespan": None,
                    "relative_gap": None,
                    "beats_neh": False,
                    "runtime_sec": round(time.time() - t0, 3),
                    "per_instance_makespans": [],
                    "schedules": []
                }

            # Validate permutation
            is_valid_perm, perm_err = validate_permutation(perm, n)
            if not is_valid_perm:
                return {
                    "is_valid": False,
                    "error": f"Invalid permutation on instance {inst_idx} ({inst['id']}): {perm_err}",
                    "total_makespan": None,
                    "mean_makespan": None,
                    "relative_gap": None,
                    "beats_neh": False,
                    "runtime_sec": round(time.time() - t0, 3),
                    "per_instance_makespans": [],
                    "schedules": []
                }

            cmax = calc_makespan(times, perm)
            cmaxes.append(cmax)
            schedules.append(perm)

        total_cmax = sum(cmaxes)
        mean_cmax = total_cmax / len(cmaxes)
        rel_gap = (total_cmax - baseline_neh) / float(baseline_neh)

        return {
            "is_valid": True,
            "error": None,
            "total_makespan": total_cmax,
            "mean_makespan": round(mean_cmax, 2),
            "relative_gap": round(rel_gap, 6),
            "beats_neh": bool(total_cmax < baseline_neh),
            "runtime_sec": round(time.time() - t0, 3),
            "per_instance_makespans": cmaxes,
            "schedules": schedules
        }
