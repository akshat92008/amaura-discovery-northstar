"""
Stage 2: Deterministic PFSP Evaluator
====================================
Target Interface:
    def schedule_flowshop(times: list[list[int]]) -> list[int]

Features:
- AST security validation via stage2.src.sandbox.check_ast_security.
- Defensive copy of processing times matrix so solver cannot mutate benchmarks.
- Pre-execution sanity check on small 3x2 matrix.
- Permutation validation (must be exact permutation of range(n)).
- Exact O(n * m) makespan computation via dynamic programming.
- Scale-aware timeout formula: T(n, m) = base_ms + per_nm_ms * (n * m).
- Strict per-instance timeout using signal.alarm to catch infinite loops.
- Deterministic scoring: total makespan across dataset.
- Preregistered penalty for invalid/timeout candidates: 999,999 makespan.
"""

import math
import os
import signal
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

from stage2.src.sandbox import (
    check_ast_security,
    sanitize_and_compile,
    SAFE_BUILTINS,
    ALLOWED_MODULES,
    SandboxTimeoutException,
    _sigalrm_handler
)


class PFSPEvaluator:
    def __init__(
        self,
        scale_aware_base_ms: float = 300.0,
        scale_aware_per_nm_ms: float = 1.0,
        hard_sigalrm_sec: int = 5
    ):
        self.scale_aware_base_ms = scale_aware_base_ms
        self.scale_aware_per_nm_ms = scale_aware_per_nm_ms
        self.hard_sigalrm_sec = hard_sigalrm_sec

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
                if completion[k - 1] > completion[k]:
                    completion[k] = completion[k - 1] + job_times[k]
                else:
                    completion[k] = completion[k] + job_times[k]
        return completion[-1]

    def validate_permutation(self, n: int, perm: Any) -> Tuple[bool, Optional[str]]:
        if not isinstance(perm, (list, tuple)):
            return False, f"Output is type '{type(perm).__name__}', expected list[int]."

        if len(perm) != n:
            return False, f"Output length {len(perm)} != number of jobs {n}."

        try:
            perm_ints = [int(x) for x in perm]
        except (ValueError, TypeError):
            return False, "Permutation contains non-integer elements."

        if set(perm_ints) != set(range(n)):
            return False, f"Output is not a valid permutation of range({n})."

        return True, None

    @staticmethod
    def compute_instance_penalty(instance: Dict[str, Any]) -> int:
        """
        Instance-normalized penalty:
        Calculates an upper bound strictly greater than any valid makespan
        for this instance (2 * sum of all processing times).
        """
        times_mat = instance.get("times", [])
        if not times_mat:
            return 1
        inst_sum = sum(sum(int(x) for x in row) for row in times_mat)
        return max(1, inst_sum * 2)

    def compute_dataset_penalty(self, dataset: List[Dict[str, Any]]) -> Tuple[int, float]:
        """
        Computes the total and average penalty across the dataset.
        Guarantees that an invalid/crashing candidate will always have total_makespan
        strictly worse than any valid candidate, regardless of dataset size.
        """
        if not dataset:
            return 999999, 999999.0
        total = sum(self.compute_instance_penalty(inst) for inst in dataset)
        return total, round(total / len(dataset), 2)

    def evaluate_code(self, code_str: str, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        pen_total, pen_avg = self.compute_dataset_penalty(dataset)
        is_safe, error_msg = check_ast_security(code_str, required_func="schedule_flowshop")
        if not is_safe:
            return {
                "is_valid": False,
                "total_makespan": pen_total,
                "avg_makespan": pen_avg,
                "scores": [],
                "runtime_ms": 0.0,
                "error": error_msg
            }

        exec_globals: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
        for mod_name in ALLOWED_MODULES:
            try:
                exec_globals[mod_name] = __import__(mod_name)
            except ImportError:
                pass

        try:
            compiled = sanitize_and_compile(code_str, "<candidate_pfsp>")
            exec(compiled, exec_globals)
            solver_fn = exec_globals["schedule_flowshop"]
        except Exception as e:
            return {
                "is_valid": False,
                "total_makespan": pen_total,
                "avg_makespan": pen_avg,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Compilation/Execution Error: {type(e).__name__}: {e}"
            }

        # Sanity check on small 3x2 matrix
        has_sigalrm = hasattr(signal, "SIGALRM") and os.name != "nt"
        prev_handler = None
        if has_sigalrm:
            prev_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
            signal.setitimer(signal.ITIMER_REAL, 1.0, 0.5)
        try:
            test_times = [[10, 5], [2, 8], [7, 3]]
            test_perm = solver_fn([list(r) for r in test_times])
            is_valid_sanity, err_sanity = self.validate_permutation(3, test_perm)
            if not is_valid_sanity:
                return {
                    "is_valid": False,
                    "total_makespan": pen_total,
                    "avg_makespan": pen_avg,
                    "scores": [],
                    "runtime_ms": 0.0,
                    "error": f"Sanity check failed on 3x2 matrix: {err_sanity}"
                }
        except SandboxTimeoutException:
            return {
                "is_valid": False,
                "total_makespan": pen_total,
                "avg_makespan": pen_avg,
                "scores": [],
                "runtime_ms": 0.0,
                "error": "Timeout Exceeded on 3x2 sanity check (infinite loop)"
            }
        except Exception as e:
            return {
                "is_valid": False,
                "total_makespan": pen_total,
                "avg_makespan": pen_avg,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Runtime Exception during sanity check: {type(e).__name__}: {e}"
            }
        finally:
            if has_sigalrm:
                signal.setitimer(signal.ITIMER_REAL, 0)
                if prev_handler is not None:
                    signal.signal(signal.SIGALRM, prev_handler)

        total_makespan = 0
        scores: List[int] = []
        eval_start_time = time.perf_counter()

        has_sigalrm = hasattr(signal, "SIGALRM") and os.name != "nt"

        for idx, instance in enumerate(dataset):
            times_mat = instance["times"]
            n = len(times_mat)
            m = len(times_mat[0])
            times_copy = [list(row) for row in times_mat]

            # Timeout limit for this instance
            instance_limit_ms = self.scale_aware_base_ms + self.scale_aware_per_nm_ms * (n * m)
            instance_limit_sec = max(1, int(instance_limit_ms / 1000.0) + 1)
            alarm_sec = min(instance_limit_sec, self.hard_sigalrm_sec)

            prev_handler = None
            if has_sigalrm:
                prev_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
                signal.setitimer(signal.ITIMER_REAL, float(alarm_sec), 0.5)

            t0 = time.perf_counter()
            try:
                result_perm = solver_fn(times_copy)
            except SandboxTimeoutException:
                return {
                    "is_valid": False,
                    "total_makespan": pen_total,
                    "avg_makespan": pen_avg,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Timeout Exceeded (SIGALRM): instance {idx} ({n}x{m}) exceeded {alarm_sec}s hard limit"
                }
            except Exception as e:
                return {
                    "is_valid": False,
                    "total_makespan": pen_total,
                    "avg_makespan": pen_avg,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Solver exception on instance {idx} ({n}x{m}): {type(e).__name__}"
                }
            finally:
                if has_sigalrm:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    if prev_handler is not None:
                        signal.signal(signal.SIGALRM, prev_handler)

            inst_duration_ms = (time.perf_counter() - t0) * 1000.0
            if inst_duration_ms > instance_limit_ms * 2.0:
                return {
                    "is_valid": False,
                    "total_makespan": pen_total,
                    "avg_makespan": pen_avg,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Soft Timeout Exceeded: instance {idx} took {inst_duration_ms:.1f}ms > limit {instance_limit_ms:.1f}ms"
                }

            is_valid, val_err = self.validate_permutation(n, result_perm)
            if not is_valid:
                return {
                    "is_valid": False,
                    "total_makespan": pen_total,
                    "avg_makespan": pen_avg,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Invalid permutation on instance {idx}: {val_err}"
                }

            cmax = self.compute_makespan(times_mat, result_perm)
            total_makespan += cmax
            scores.append(cmax)

        total_runtime_ms = (time.perf_counter() - eval_start_time) * 1000.0
        avg_makespan = total_makespan / len(dataset) if dataset else 0.0

        return {
            "is_valid": True,
            "total_makespan": total_makespan,
            "avg_makespan": round(avg_makespan, 2),
            "scores": scores,
            "runtime_ms": round(total_runtime_ms, 2),
            "error": None
        }
