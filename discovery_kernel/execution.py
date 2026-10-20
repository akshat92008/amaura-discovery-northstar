"""
Discovery Kernel v0.1: Isolated Execution Layer
==============================================
Provides process-isolated execution for candidate methods with hard timeout
enforcement via OS signal termination (SIGTERM -> SIGKILL).
Enforces declarative constraint validation, separates validity from scoring,
and ensures a failed candidate cannot corrupt subsequent evaluations.
"""

from dataclasses import dataclass, field
import multiprocessing
import os
import signal
import sys
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

from discovery_kernel.method_adapter import MethodAdapter, ExecutionStatus
from discovery_kernel.problem_spec import ConstraintRule


@dataclass
class EvaluationResult:
    """Complete evaluation outcome for a single instance."""
    method_id: str
    method_version: str
    instance_id: str
    is_valid: bool
    status: ExecutionStatus
    objective_metric: str
    objective_score: Optional[float] = None
    raw_score: Optional[float] = None
    runtime_ms: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def _worker_process_entrypoint(
    adapter: MethodAdapter,
    instance: Any,
    queue: Any
) -> None:
    """
    Entrypoint executed inside a fresh OS process.
    Runs the candidate adapter's solve method and posts result to IPC queue.
    """
    t0 = time.perf_counter()
    try:
        # Enforce CPU time resource limit as backstop if supported on platform
        try:
            import resource
            # Soft limit 10s, hard limit 15s
            resource.setrlimit(resource.RLIMIT_CPU, (10, 15))
        except Exception:
            pass

        context = {}
        output = adapter.solve(instance, context=context)
        diag = context.get("diagnostics") or getattr(adapter, "last_diagnostics", {}) or {}
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        queue.put({
            "success": True,
            "output": output,
            "runtime_ms": elapsed_ms,
            "diagnostics": diag
        })
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        queue.put({
            "success": False,
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "runtime_ms": elapsed_ms
        })


class ExecutionSupervisor:
    """
    Supervises method execution in an isolated OS process.
    Guarantees hard termination on timeout and strict constraint validation.
    """
    def __init__(
        self,
        timeout_sec: float = 5.0,
        max_memory_mb: Optional[float] = None
    ):
        self.timeout_sec = max(0.1, timeout_sec)
        self.max_memory_mb = max_memory_mb

    def execute_and_evaluate(
        self,
        adapter: MethodAdapter,
        instance: Any,
        instance_id: str,
        evaluator_fn: Callable[[Any, Any], float],
        constraints: List[ConstraintRule],
        objective_metric: str = "makespan"
    ) -> EvaluationResult:
        """
        Executes an adapter on an instance in an isolated process, validates constraints,
        and computes the objective score.
        """
        t0 = time.perf_counter()
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()

        proc = ctx.Process(
            target=_worker_process_entrypoint,
            args=(adapter, instance, queue)
        )
        proc.start()
        worker_pid = proc.pid

        # Wait up to timeout_sec
        proc.join(timeout=self.timeout_sec)

        # Handle Timeout: worker is still running
        if proc.is_alive():
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

            wall_ms = (time.perf_counter() - t0) * 1000.0
            return EvaluationResult(
                method_id=adapter.method_id,
                method_version=adapter.version,
                instance_id=instance_id,
                is_valid=False,
                status=ExecutionStatus.TIMEOUT,
                objective_metric=objective_metric,
                objective_score=None,
                runtime_ms=wall_ms,
                error_message=(
                    f"TimeoutError: Execution exceeded timeout of {self.timeout_sec:.2f}s "
                    f"in isolated process (PID {worker_pid} terminated)"
                )
            )

        # Retrieve result payload from queue
        payload = None
        try:
            if not queue.empty():
                payload = queue.get_nowait()
        except Exception:
            pass

        try:
            queue.close()
        except Exception:
            pass

        wall_ms = (time.perf_counter() - t0) * 1000.0

        # Handle abnormal process exit (e.g. segfault, unhandled signal)
        if payload is None:
            return EvaluationResult(
                method_id=adapter.method_id,
                method_version=adapter.version,
                instance_id=instance_id,
                is_valid=False,
                status=ExecutionStatus.EXCEPTION,
                objective_metric=objective_metric,
                objective_score=None,
                runtime_ms=wall_ms,
                error_message=f"ProcessError: Worker process (PID {worker_pid}) exited unexpectedly with code {proc.exitcode}"
            )

        # Handle runtime exception inside worker
        if not payload.get("success"):
            err_type = payload.get("error_type", "UnknownError")
            err_msg = payload.get("error_msg", "Unknown error")
            return EvaluationResult(
                method_id=adapter.method_id,
                method_version=adapter.version,
                instance_id=instance_id,
                is_valid=False,
                status=ExecutionStatus.EXCEPTION,
                objective_metric=objective_metric,
                objective_score=None,
                runtime_ms=payload.get("runtime_ms", wall_ms),
                error_message=f"{err_type}: {err_msg}"
            )

        # Output produced successfully: validate against constraints
        output = payload.get("output")
        validation_errors: List[str] = []
        for c in constraints:
            ok, reason = c.check(instance, output)
            if not ok:
                validation_errors.append(f"[{c.name}] {reason}")

        if validation_errors:
            return EvaluationResult(
                method_id=adapter.method_id,
                method_version=adapter.version,
                instance_id=instance_id,
                is_valid=False,
                status=ExecutionStatus.VALIDATION_ERROR,
                objective_metric=objective_metric,
                objective_score=None,
                runtime_ms=payload.get("runtime_ms", wall_ms),
                validation_errors=validation_errors,
                error_message=f"Constraint validation failed: {'; '.join(validation_errors)}"
            )

        # All constraints satisfied: compute score via common problem evaluator
        try:
            score = float(evaluator_fn(instance, output))
        except Exception as e:
            return EvaluationResult(
                method_id=adapter.method_id,
                method_version=adapter.version,
                instance_id=instance_id,
                is_valid=False,
                status=ExecutionStatus.EXCEPTION,
                objective_metric=objective_metric,
                objective_score=None,
                runtime_ms=payload.get("runtime_ms", wall_ms),
                error_message=f"EvaluatorError: {type(e).__name__}: {str(e)}"
            )

        return EvaluationResult(
            method_id=adapter.method_id,
            method_version=adapter.version,
            instance_id=instance_id,
            is_valid=True,
            status=ExecutionStatus.SUCCESS,
            objective_metric=objective_metric,
            objective_score=score,
            raw_score=score,
            runtime_ms=payload.get("runtime_ms", wall_ms),
            error_message=None,
            diagnostics=payload.get("diagnostics", {})
        )
