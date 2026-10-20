"""
Experiment #11 Evaluator: Deterministic Scale-Aware PFSP Evaluator
==================================================================
Key updates over Exp #10:
- Calibrated scale-aware timeout formula: T(n, m) = 1000.0 + 2.0 * (n * m) ms.
  Accounts for BOTH job count n and machine count m.
  Example: (50, 15) -> 2500 ms limit (avoids false-positive timeout of ~1030ms).
  Example: (100, 10) -> 3000 ms limit (avoids false-positive timeout of ~1600ms).
- Hard SIGALRM interrupt at 10 seconds to catch true infinite loops.
- Permutation validation: exactly 0..n-1.
- Exact O(n * m) DP makespan computation.
"""

import ast
import os
import signal
import sys
import time
from typing import Dict, Any, List, Optional, Tuple


class TimeoutException(Exception):
    pass


def _alarm_handler(signum, frame):
    raise TimeoutException("SIGALRM hard process execution interrupt triggered.")


class PFSPEvaluator:
    def __init__(
        self,
        scale_aware_base_ms: float = 1000.0,
        scale_aware_per_nm_ms: float = 2.0,
        sigalrm_interrupt_sec: int = 10
    ):
        self.scale_aware_base_ms = scale_aware_base_ms
        self.scale_aware_per_nm_ms = scale_aware_per_nm_ms
        self.sigalrm_interrupt_sec = sigalrm_interrupt_sec

    def static_ast_check(self, code_str: str) -> Tuple[bool, Optional[str]]:
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, f"SyntaxError in candidate code: {e}"

        has_schedule_fn = False
        allowed_modules = {"math", "random", "typing", "collections", "itertools", "heapq", "copy"}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "schedule_flowshop":
                has_schedule_fn = True

            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in allowed_modules:
                        return False, f"Forbidden import: {alias.name}. Only {allowed_modules} allowed."
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod not in allowed_modules:
                        return False, f"Forbidden import from {node.module}. Only {allowed_modules} allowed."

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "open", "__import__", "compile"}:
                        return False, f"Forbidden built-in call: {node.func.id}."
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in {"system", "popen", "spawn"}:
                        return False, f"Forbidden attribute call: {node.func.attr}."

        if not has_schedule_fn:
            return False, "Candidate code must define a function named 'schedule_flowshop(times)'."

        return True, None

    @staticmethod
    def compute_makespan(times: List[List[int]], perm: List[int]) -> int:
        n = len(times)
        if n == 0 or len(perm) == 0:
            return 0
        m = len(times[0])
        completion = [0] * m
        for job_idx in perm:
            job_times = times[job_idx]
            completion[0] += job_times[0]
            for k in range(1, m):
                completion[k] = (completion[k] if completion[k] > completion[k - 1] else completion[k - 1]) + job_times[k]
        return completion[-1]

    def evaluate_solver_code(
        self,
        code_str: str,
        instances: List[Dict[str, Any]],
        extract_behavior: bool = True
    ) -> Dict[str, Any]:
        is_safe, error_msg = self.static_ast_check(code_str)
        if not is_safe:
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": error_msg
            }

        exec_globals = {}
        try:
            compiled = compile(code_str, "<candidate_solver>", "exec")
            exec(compiled, exec_globals)
        except Exception as e:
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": f"Compilation/Execution setup error: {e}"
            }

        solver_fn = exec_globals.get("schedule_flowshop")
        if not callable(solver_fn):
            return {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": "'schedule_flowshop' is not callable."
            }

        total_makespan = 0
        instance_makespans: List[int] = []
        behavior_signature: List[List[int]] = []
        start_time_all = time.perf_counter()

        for idx, inst in enumerate(instances):
            times_matrix = inst["times"]
            n = inst["n"]
            m = inst["m"]

            # Scale-aware limit: T(n, m) = base + per_nm * (n * m)
            timeout_ms = self.scale_aware_base_ms + (self.scale_aware_per_nm_ms * (n * m))

            if hasattr(signal, "SIGALRM"):
                signal.signal(signal.SIGALRM, _alarm_handler)
                signal.alarm(self.sigalrm_interrupt_sec)

            t0 = time.perf_counter()
            try:
                perm = solver_fn(times_matrix)
            except TimeoutException:
                if hasattr(signal, "SIGALRM"):
                    signal.alarm(0)
                return {
                    "is_valid": False,
                    "total_makespan": 999999,
                    "mean_makespan": 999999.0,
                    "instance_makespans": [],
                    "behavior_signature": [],
                    "runtime_ms": (time.perf_counter() - start_time_all) * 1000.0,
                    "error": f"Hard Timeout (SIGALRM {self.sigalrm_interrupt_sec}s exceeded) on instance #{idx+1} (n={n}, m={m})"
                }
            except Exception as e:
                if hasattr(signal, "SIGALRM"):
                    signal.alarm(0)
                return {
                    "is_valid": False,
                    "total_makespan": 999999,
                    "mean_makespan": 999999.0,
                    "instance_makespans": [],
                    "behavior_signature": [],
                    "runtime_ms": (time.perf_counter() - start_time_all) * 1000.0,
                    "error": f"Runtime Exception on instance #{idx+1}: {e}"
                }
            finally:
                if hasattr(signal, "SIGALRM"):
                    signal.alarm(0)

            t_elapsed_ms = (time.perf_counter() - t0) * 1000.0

            if t_elapsed_ms > timeout_ms:
                return {
                    "is_valid": False,
                    "total_makespan": 999999,
                    "mean_makespan": 999999.0,
                    "instance_makespans": [],
                    "behavior_signature": [],
                    "runtime_ms": (time.perf_counter() - start_time_all) * 1000.0,
                    "error": f"Scale-aware Timeout: instance #{idx+1} took {t_elapsed_ms:.1f}ms > limit {timeout_ms:.1f}ms (n={n}, m={m})"
                }

            if not isinstance(perm, (list, tuple)) or len(perm) != n:
                return {
                    "is_valid": False,
                    "total_makespan": 999999,
                    "mean_makespan": 999999.0,
                    "instance_makespans": [],
                    "behavior_signature": [],
                    "runtime_ms": (time.perf_counter() - start_time_all) * 1000.0,
                    "error": f"Invalid return type or length on instance #{idx+1}: expected list of length {n}, got {type(perm)} of length {len(perm) if hasattr(perm, '__len__') else 'N/A'}"
                }

            if sorted(perm) != list(range(n)):
                return {
                    "is_valid": False,
                    "total_makespan": 999999,
                    "mean_makespan": 999999.0,
                    "instance_makespans": [],
                    "behavior_signature": [],
                    "runtime_ms": (time.perf_counter() - start_time_all) * 1000.0,
                    "error": f"Invalid permutation on instance #{idx+1}: missing or duplicate jobs in schedule."
                }

            ms = self.compute_makespan(times_matrix, perm)
            total_makespan += ms
            instance_makespans.append(ms)
            if extract_behavior:
                behavior_signature.append(list(perm))

        total_runtime_ms = (time.perf_counter() - start_time_all) * 1000.0
        return {
            "is_valid": True,
            "total_makespan": total_makespan,
            "mean_makespan": round(total_makespan / len(instances), 2),
            "instance_makespans": instance_makespans,
            "behavior_signature": behavior_signature,
            "runtime_ms": round(total_runtime_ms, 2),
            "error": None
        }
