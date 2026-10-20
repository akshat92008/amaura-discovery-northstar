"""
Experiment #9: PFSP Deterministic Evaluator & Security Sandbox
==============================================================
Target Interface:
    def schedule_flowshop(times: list[list[int]]) -> list[int]

Implements:
- 1D Dynamic Programming makespan computation O(n * m)
- Strict AST static security analysis
- Strict dynamic execution sandbox with SAFE_BUILTINS and restricted imports
- OS-level signal.SIGALRM hard interrupt timer
- Soft runtime budget (50 ms) and hard timeout limit (300 ms) per instance
- Strict permutation validity verification
"""

import ast
import math
import random
import signal
import time
from typing import List, Sequence, Tuple, Dict, Any, Optional, Set


def _alarm_timeout_handler(signum, frame):
    raise TimeoutError("Per-instance execution timed out (hard hang / infinite loop)")


def safe_import(name, *args, **kwargs):
    if name in {"math", "random"}:
        return __import__(name)
    raise ImportError(f"Import of '{name}' is strictly forbidden. Only 'math' and 'random' are permitted.")


SAFE_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "float": float,
    "int": int,
    "round": round,
    "bool": bool,
    "len": len,
    "range": range,
    "sum": sum,
    "pow": pow,
    "list": list,
    "tuple": tuple,
    "set": set,
    "dict": dict,
    "enumerate": enumerate,
    "sorted": sorted,
    "any": any,
    "all": all,
    "zip": zip,
    "reversed": reversed,
    "print": lambda *args, **kwargs: None,
    "__import__": safe_import,
}


def static_security_check(code: str) -> Tuple[bool, Optional[str]]:
    """
    Analyzes Python AST to block dangerous constructs before compilation:
    - DISALLOW unauthorized module imports (only pure 'math' and 'random' permitted)
    - DISALLOW dynamic code execution, file system, subprocess, networking
    - VERIFY required function signature `def schedule_flowshop(times)`
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    has_solver_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in {"math", "random"}:
                    return False, f"Security violation: Import '{alias.name}' is forbidden. Only 'math' and 'random' are permitted."
        if isinstance(node, ast.ImportFrom):
            if node.module not in {"math", "random"}:
                return False, f"Security violation: Import from '{node.module}' is forbidden. Only 'math' and 'random' are permitted."
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval", "exec", "open", "__import__", "globals", "locals", "getattr", "setattr", "compile"
            }:
                return False, f"Security violation: Forbidden call '{node.func.id}'."
        if isinstance(node, ast.FunctionDef) and node.name == "schedule_flowshop":
            has_solver_func = True
            if len(node.args.args) < 1:
                return False, "Signature error: 'schedule_flowshop' must accept (times)."

    if not has_solver_func:
        return False, "Missing required function definition: 'def schedule_flowshop(times: list[list[int]]) -> list[int]:'"

    return True, None


def compute_makespan(times: Sequence[Sequence[int]], perm: Sequence[int]) -> int:
    """
    Computes exact makespan C_max for a permutation schedule in O(n * m)
    using 1D DP recurrence.
    """
    n = len(perm)
    m = len(times[0])
    dp = [0] * m
    for job in perm:
        dp[0] += times[job][0]
        for k in range(1, m):
            if dp[k - 1] > dp[k]:
                dp[k] = dp[k - 1] + times[job][k]
            else:
                dp[k] = dp[k] + times[job][k]
    return dp[m - 1]


def validate_permutation(n: int, perm: Any) -> Tuple[bool, Optional[str]]:
    """Validates that perm is a valid permutation of [0, 1, ..., n-1]."""
    if not isinstance(perm, (list, tuple)):
        return False, f"Output is type {type(perm).__name__}, expected list."
    if len(perm) != n:
        return False, f"Permutation length {len(perm)} != number of jobs {n}."
    
    seen = set()
    for idx, job in enumerate(perm):
        if not isinstance(job, (int, float)) or int(job) != job:
            return False, f"Element at index {idx} is not an integer: {job}."
        job_int = int(job)
        if job_int < 0 or job_int >= n:
            return False, f"Job index {job_int} out of range [0, {n-1}]."
        if job_int in seen:
            return False, f"Duplicate job index {job_int} found."
        seen.add(job_int)

    return True, None


class PFSPEvaluator:
    def __init__(self, per_instance_soft_limit_ms: float = 50.0, per_instance_hard_limit_ms: float = 300.0):
        self.soft_limit_ms = per_instance_soft_limit_ms
        self.hard_limit_ms = per_instance_hard_limit_ms

    def evaluate_solver_code(
        self,
        code: str,
        benchmark_instances: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Safely compiles and evaluates candidate solver code on a list of instances.
        Each instance is a dict: {'id': str, 'n': int, 'm': int, 'times': list[list[int]]}.
        
        Returns:
            {
                'is_valid': bool,
                'total_makespan': int,
                'mean_makespan': float,
                'instance_makespans': list[int],
                'behavior_signature': list[list[int]], # list of permutations
                'runtime_ms': float,
                'error': Optional[str]
            }
        """
        # Step 1: Static AST Security Check
        is_clean, err = static_security_check(code)
        if not is_clean:
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": f"Security / Static Check Failed: {err}"
            }

        # Step 2: Sandbox Compilation
        local_scope = {}
        try:
            exec(code, {"__builtins__": SAFE_BUILTINS, "math": math, "random": random}, local_scope)
            func = local_scope["schedule_flowshop"]
        except Exception as e:
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": f"Compilation Error: {type(e).__name__}: {e}"
            }

        # Step 3: Sanity check on minimal instance (3 jobs, 2 machines)
        prev_handler = signal.signal(signal.SIGALRM, _alarm_timeout_handler)
        try:
            sample_times = [[3, 2], [1, 5], [4, 1]]
            signal.alarm(1)
            test_perm = func([list(row) for row in sample_times])
            signal.alarm(0)
            valid, err = validate_permutation(3, test_perm)
            if not valid:
                return {
                    "is_valid": False,
                    "total_makespan": 999999,
                    "mean_makespan": 999999.0,
                    "instance_makespans": [],
                    "behavior_signature": [],
                    "runtime_ms": 0.0,
                    "error": f"Sanity check failed on (3x2): {err}"
                }
        except TimeoutError:
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 1000.0,
                "error": "Timeout Exceeded on minimal sanity check (infinite loop)"
            }
        except Exception as e:
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": f"Runtime Error on sanity check: {type(e).__name__}: {e}"
            }
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)

        # Step 4: Full Benchmark Evaluation
        total_makespan = 0
        instance_makespans = []
        behavior_signature = []
        start_eval_time = time.perf_counter()

        prev_handler = signal.signal(signal.SIGALRM, _alarm_timeout_handler)
        try:
            for idx, inst in enumerate(benchmark_instances):
                times_copy = [list(row) for row in inst["times"]]
                n = inst["n"]

                t0 = time.perf_counter()
                try:
                    signal.alarm(1)  # 1 second hard kill for unbounded loops
                    perm = func(times_copy)
                except TimeoutError:
                    return {
                        "is_valid": False,
                        "total_makespan": 999999,
                        "mean_makespan": 999999.0,
                        "instance_makespans": [],
                        "behavior_signature": [],
                        "runtime_ms": 1000.0,
                        "error": f"Timeout Exceeded (Hard hang) on instance {idx} ({inst.get('id', 'unknown')}, N={n})"
                    }
                except Exception as e:
                    return {
                        "is_valid": False,
                        "total_makespan": 999999,
                        "mean_makespan": 999999.0,
                        "instance_makespans": [],
                        "behavior_signature": [],
                        "runtime_ms": 0.0,
                        "error": f"Solver exception on instance {idx} ({inst.get('id', 'unknown')}): {type(e).__name__}: {e}"
                    }
                finally:
                    signal.alarm(0)

                inst_time_ms = (time.perf_counter() - t0) * 1000.0
                if inst_time_ms > self.hard_limit_ms:
                    return {
                        "is_valid": False,
                        "total_makespan": 999999,
                        "mean_makespan": 999999.0,
                        "instance_makespans": [],
                        "behavior_signature": [],
                        "runtime_ms": round(inst_time_ms, 2),
                        "error": f"Hard Timeout Exceeded: instance took {inst_time_ms:.1f}ms > limit {self.hard_limit_ms}ms"
                    }

                # Validate permutation
                valid, err = validate_permutation(n, perm)
                if not valid:
                    return {
                        "is_valid": False,
                        "total_makespan": 999999,
                        "mean_makespan": 999999.0,
                        "instance_makespans": [],
                        "behavior_signature": [],
                        "runtime_ms": 0.0,
                        "error": f"Invalid permutation on instance {idx}: {err}"
                    }

                # Compute makespan
                c_max = compute_makespan(inst["times"], perm)
                total_makespan += c_max
                instance_makespans.append(c_max)
                behavior_signature.append([int(x) for x in perm])

            total_runtime_ms = (time.perf_counter() - start_eval_time) * 1000.0
            mean_makespan = total_makespan / len(benchmark_instances) if benchmark_instances else 0.0

            return {
                "is_valid": True,
                "total_makespan": total_makespan,
                "mean_makespan": round(mean_makespan, 2),
                "instance_makespans": instance_makespans,
                "behavior_signature": behavior_signature,
                "runtime_ms": round(total_runtime_ms, 2),
                "error": None
            }
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)
