"""
Stage 4 Sandboxed Evaluator & AST Security Validator
====================================================
Evaluates candidates strictly on the supplied dataset with zero leakage:
1. Static AST analysis (anti-reward-hacking, forbidden modules, signature validation, top-level statement restrictions).
2. Restricted global execution environment.
3. True OS Process Isolation with resource limits and enforceable process termination.
4. Strict error rejection: exceptions, NaNs, Infs, timeouts return is_valid=False and fitness=inf.
5. NEVER silently masks errors with Best-Fit.
"""

import ast
import math
import multiprocessing
import os
import signal
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable, Tuple

from stage4.src.simulator import DeterministicBinPackingSimulator


FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "urllib", "requests", "shutil",
    "pathlib", "importlib", "builtins", "__builtin__", "pickle"
}


@dataclass
class Stage4EvaluationResult:
    is_valid: bool
    fitness: float  # mean normalized excess ratio rho_bar (lower is better, inf if invalid)
    mean_excess_ratio: float
    pooled_excess_ratio: float
    total_bins: int
    total_l1: int
    runtime_ms: float
    passed_streams: int
    total_streams: int
    error_message: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None



def _isolated_evaluation_worker(
    code: str,
    func_name: str,
    streams: List[List[float]],
    bin_capacity: float,
    result_queue: Any
):
    """
    Executes in a separate OS process with restricted environment and resource limits.
    """
    try:
        # Enforce resource limits (SEC-5: fail closed on errors if supported)
        try:
            import resource
            # CPU time: 5s soft, 10s hard
            resource.setrlimit(resource.RLIMIT_CPU, (5, 10))
            # Core dump: 0
            if hasattr(resource, "RLIMIT_CORE"):
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # File size limit: 1 MB
            if hasattr(resource, "RLIMIT_FSIZE"):
                resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
            # Open files limit: 64
            if hasattr(resource, "RLIMIT_NOFILE"):
                resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            # Max memory: 512 MB (if supported by OS)
            if hasattr(resource, "RLIMIT_AS"):
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
                except (ValueError, OSError):
                    pass
        except Exception as lim_exc:
            result_queue.put({"success": False, "error": f"ResourceLimitError: {lim_exc}"})
            return

        from amaura_exec.safe_exec import create_safe_namespace
        safe_globals = create_safe_namespace()
        safe_locals: Dict[str, Any] = {}

        # Execute code in isolated worker process
        exec(code, safe_globals, safe_locals)
        func = safe_locals.get(func_name) or safe_globals.get(func_name)
        if func is None:
            result_queue.put({"success": False, "error": f"Function '{func_name}' not found after compilation"})
            return

        simulator = DeterministicBinPackingSimulator(bin_capacity=bin_capacity)
        res = simulator.evaluate_streams(streams, func, strict_errors=True)
        result_queue.put({"success": True, "result": res})
    except Exception as e:
        result_queue.put({"success": False, "error": f"{type(e).__name__}: {str(e)}"})


class Stage4Evaluator:
    """
    Decoupled, leak-free evaluator with true process isolation.
    Evaluates candidate functions strictly against the provided streams.
    """
    def __init__(
        self,
        bin_capacity: float = 100.0,
        timeout_sec: float = 2.0
    ):
        self.bin_capacity = bin_capacity
        self.timeout_sec = timeout_sec
        self.simulator = DeterministicBinPackingSimulator(bin_capacity=bin_capacity)

    def validate_ast(self, code: str, expected_func: str = "priority") -> Tuple[bool, Optional[str]]:
        """Static AST inspection for security, interface conformance, and structural restrictions."""
        from amaura_exec.ast_validator import validate_candidate_ast
        return validate_candidate_ast(code, expected_func_name=expected_func, expected_param_count=3)

    def compile_function(self, code: str, func_name: str = "priority") -> Tuple[Optional[Callable], Optional[str]]:
        """Compiles code in a restricted dictionary for local inspection."""
        from amaura_exec.safe_exec import create_safe_namespace
        safe_globals = create_safe_namespace()
        safe_locals: Dict[str, Any] = {}
        try:
            exec(code, safe_globals, safe_locals)
            func = safe_locals.get(func_name) or safe_globals.get(func_name)
            if func is None:
                return None, f"Function '{func_name}' not found after compilation"
            return func, None
        except Exception as e:
            return None, f"Compilation failed: {type(e).__name__}: {str(e)}"

    def evaluate_candidate(
        self,
        code: str,
        streams: List[List[float]],
        func_name: str = "priority"
    ) -> Stage4EvaluationResult:
        """
        Evaluates a candidate priority function using enforceable process isolation.
        Terminates the worker process hard if it exceeds timeout_sec.
        Fails closed on any error, returning is_valid=False and fitness=inf.
        """
        t0 = time.perf_counter()

        # 1. AST Validation
        ast_ok, ast_err = self.validate_ast(code, expected_func=func_name)
        if not ast_ok:
            return Stage4EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                mean_excess_ratio=float("inf"),
                pooled_excess_ratio=float("inf"),
                total_bins=0,
                total_l1=0,
                runtime_ms=(time.perf_counter() - t0) * 1000.0,
                passed_streams=0,
                total_streams=len(streams),
                error_message=f"AST Validation Error: {ast_err}"
            )

        # 2. Process-Isolated Execution
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        proc = ctx.Process(
            target=_isolated_evaluation_worker,
            args=(code, func_name, streams, self.bin_capacity, queue)
        )
        proc.start()
        worker_pid = proc.pid

        # Wait up to timeout_sec for process to complete
        proc.join(timeout=self.timeout_sec)

        if proc.is_alive():
            # Hard termination: SIGTERM then SIGKILL to prevent lingering worker processes
            try:
                proc.terminate()
                proc.join(timeout=0.2)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=0.2)
            except Exception:
                pass

            try:
                queue.close()
            except Exception:
                pass

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return Stage4EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                mean_excess_ratio=float("inf"),
                pooled_excess_ratio=float("inf"),
                total_bins=0,
                total_l1=0,
                runtime_ms=elapsed_ms,
                passed_streams=0,
                total_streams=len(streams),
                error_message=f"TimeoutError: Execution exceeded {self.timeout_sec}s in isolated process (PID {worker_pid} terminated)"
            )

        # Retrieve result from queue (REL-1: use bounded timeout get to prevent queue race)
        res_data = None
        try:
            res_data = queue.get(timeout=0.5)
        except Exception:
            pass

        try:
            queue.close()
        except Exception:
            pass

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if res_data is None:
            return Stage4EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                mean_excess_ratio=float("inf"),
                pooled_excess_ratio=float("inf"),
                total_bins=0,
                total_l1=0,
                runtime_ms=elapsed_ms,
                passed_streams=0,
                total_streams=len(streams),
                error_message=f"ProcessError: Worker process (PID {worker_pid}) exited unexpectedly with code {proc.exitcode}"
            )

        if not res_data.get("success"):
            return Stage4EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                mean_excess_ratio=float("inf"),
                pooled_excess_ratio=float("inf"),
                total_bins=0,
                total_l1=0,
                runtime_ms=elapsed_ms,
                passed_streams=0,
                total_streams=len(streams),
                error_message=f"Execution Failed: {res_data.get('error')}"
            )

        res = res_data["result"]
        return Stage4EvaluationResult(
            is_valid=True,
            fitness=res["mean_excess_ratio"],
            mean_excess_ratio=res["mean_excess_ratio"],
            pooled_excess_ratio=res["pooled_excess_ratio"],
            total_bins=res["total_bins"],
            total_l1=res["total_l1"],
            runtime_ms=elapsed_ms,
            passed_streams=res["num_streams"],
            total_streams=len(streams),
            error_message=None,
            diagnostics=res.get("diagnostics")
        )
