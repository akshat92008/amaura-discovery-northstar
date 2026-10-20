"""
North BlueStar — Execution & Verification Supervisor (Capability E)
===================================================================
Provides dependable evaluation with:
- True OS-level subprocess isolation for untrusted / program-synthesis candidates.
- Actual termination (`proc.kill()` / `SIGKILL`) of timed-out worker processes (eliminating the
  zombie background thread defect in `ThreadPoolExecutor`).
-Explicit Threat Model declaration (never claiming arbitrary hostile root-exploit containment
  when running in standard POSIX user-space subprocesses without microVM/seccomp-bpf).
- Resource accounting (wall-clock runtime_ms, worker process termination status).
- Independent verification of solutions and repeatability verification across re-runs.
"""

from __future__ import annotations

import copy
import multiprocessing as mp
import os
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from north_bluestar.candidates import CandidateKind, CandidateSpec
from north_bluestar.methods import MethodRegistry
from north_bluestar.problem import (
    AggregateEvaluationOutcome,
    InstanceEvaluationOutcome,
    ProblemInstance,
    ProblemSpecification,
    SolutionStatus,
    SplitType,
)


class ThreatModelLevel(str, Enum):
    TRUSTED_DECLARATIVE_IN_PROCESS = "TRUSTED_DECLARATIVE_IN_PROCESS"
    POSIX_SUBPROCESS_AST_RESTRICTED = "POSIX_SUBPROCESS_AST_RESTRICTED"


@dataclass(frozen=True)
class IsolationThreatModel:
    """
    Explicit security and isolation declaration for North BlueStar's execution supervisor.
    Never claims arbitrary hostile-code containment beyond what the active OS isolation mechanism guarantees.
    """
    level: ThreatModelLevel
    enforces_ast_allowlist: bool
    enforces_os_process_boundary: bool
    enforces_sigkill_on_timeout: bool
    guarantees: Tuple[str, ...]
    non_guarantees: Tuple[str, ...]


DEFAULT_SUBPROCESS_THREAT_MODEL = IsolationThreatModel(
    level=ThreatModelLevel.POSIX_SUBPROCESS_AST_RESTRICTED,
    enforces_ast_allowlist=True,
    enforces_os_process_boundary=True,
    enforces_sigkill_on_timeout=True,
    guarantees=(
        "Timed-out worker processes are forcibly terminated via OS SIGKILL (`proc.kill()`), preventing runaway CPU starvation.",
        "Input problem instances are deep-copied before execution so in-place mutation cannot corrupt benchmark data.",
        "Python program candidates undergo AST static analysis blocking imports of os/sys/subprocess/socket and dunder introspection.",
        "Every candidate output is validated by an independent host-process verifier before objective scoring.",
    ),
    non_guarantees=(
        "Does NOT claim containment against kernel zero-days or arbitrary native code execution without an external container/nsjail/Firecracker microVM boundary.",
    ),
)


class FailureCategory(str, Enum):
    NONE = "NONE"
    SYNTAX_OR_AST_REJECTED = "SYNTAX_OR_AST_REJECTED"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    TIMEOUT_SIGKILL = "TIMEOUT_SIGKILL"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
    CONSTRAINT_INFEASIBLE = "CONSTRAINT_INFEASIBLE"
    NON_DETERMINISTIC = "NON_DETERMINISTIC"


@dataclass
class VerificationReport:
    """Result of independent verification and repeatability audit on a candidate."""
    candidate_id: str
    split: SplitType
    outcome: AggregateEvaluationOutcome
    failure_category: FailureCategory
    worker_killed_count: int = 0
    is_repeatable: bool = True
    repeatability_max_drift: float = 0.0
    threat_model_level: str = ThreatModelLevel.POSIX_SUBPROCESS_AST_RESTRICTED.value
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def _subprocess_worker_entry(
    candidate: CandidateSpec,
    instance: ProblemInstance,
    result_comm: Any,
    max_memory_mb: int = 1024,
    cpu_timeout_sec: int = 10,
) -> None:
    """
    Isolated worker target executed in a separate OS process with hard OS resource limits (P0 2.3).
    Compiles the candidate via a fresh MethodRegistry and runs it on a defensive copy of `instance`.
    """
    def _send(data: Dict[str, Any]) -> None:
        try:
            if hasattr(result_comm, "send"):
                result_comm.send(data)
                result_comm.close()
            elif hasattr(result_comm, "put"):
                result_comm.put(data)
        except Exception:
            pass

    try:
        # Enforce OS-level resource containment limits (P0 2.3)
        try:
            import resource
            # CPU time limit: soft = cpu_timeout_sec, hard = cpu_timeout_sec + 2
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_timeout_sec, cpu_timeout_sec + 2))
            if hasattr(resource, "RLIMIT_CORE"):
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            if hasattr(resource, "RLIMIT_FSIZE"):
                resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
            if hasattr(resource, "RLIMIT_NOFILE"):
                resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            if hasattr(resource, "RLIMIT_NPROC"):
                try:
                    _, cur_hard = resource.getrlimit(resource.RLIMIT_NPROC)
                    limit = min(2048, cur_hard) if cur_hard > 0 else 2048
                    resource.setrlimit(resource.RLIMIT_NPROC, (limit, limit))
                except (ValueError, OSError):
                    pass
            if hasattr(resource, "RLIMIT_AS"):
                try:
                    limit_bytes = max_memory_mb * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
                except (ValueError, OSError) as as_err:
                    if sys.platform.startswith("linux") and os.geteuid() == 0:
                        raise RuntimeError(f"Failed to set RLIMIT_AS on Linux: {as_err}") from as_err
        except Exception as lim_err:
            _send({
                "ok": False,
                "solution": None,
                "runtime_ms": 0.0,
                "error": f"ResourceLimitError: Failed to set OS resource limits: {lim_err}",
                "traceback": "",
            })
            return

        reg = MethodRegistry.create_default_registry()
        adapter = reg.get(candidate.method_id)
        runner = adapter.compile_runner(candidate)
        t0 = time.perf_counter()
        sol = runner(copy.deepcopy(instance))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _send({"ok": True, "solution": sol, "runtime_ms": elapsed_ms, "error": None})
    except Exception as exc:
        _send(
            {
                "ok": False,
                "solution": None,
                "runtime_ms": 0.0,
                "error": f"{type(exc).__name__}: {str(exc)}",
                "traceback": traceback.format_exc(),
            }
        )


class ExecutionSupervisor:
    """
    Dependable evaluation and verification layer (Capability E).
    - Runs `PYTHON_PROGRAM` candidates (or any candidate when `force_subprocess=True`) in a separate OS process
      with hard `SIGKILL` enforcement on timeout.
    - Runs verified declarative operator compositions (`DECLARATIVE_PFSP`, `DECLARATIVE_BIN_PACKING`, `VERIFIED_BASELINE`)
      with defensive deep-copied inputs and independent host-side constraint verification.
    """

    def __init__(
        self,
        registry: MethodRegistry,
        default_timeout_ms: float = 400.0,
        force_subprocess_for_all: bool = False,
    ) -> None:
        self.registry = registry
        self.default_timeout_ms = default_timeout_ms
        self.force_subprocess_for_all = force_subprocess_for_all
        self.threat_model = DEFAULT_SUBPROCESS_THREAT_MODEL
        self.total_evaluations: int = 0
        self.total_instance_runs: int = 0
        self.total_wall_clock_ms: float = 0.0
        self.total_sigkills: int = 0

    def _run_single_instance_subprocess(
        self,
        candidate: CandidateSpec,
        instance: ProblemInstance,
        timeout_ms: float,
    ) -> Tuple[Any, float, Optional[str], bool]:
        """
        Executes `candidate` on `instance` in a dedicated OS subprocess.
        If execution exceeds `timeout_ms`, sends `SIGKILL` (`proc.kill()`) and joins immediately.
        Returns: (solution, runtime_ms, error_message, timed_out)
        """
        ctx = mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_subprocess_worker_entry, args=(candidate, instance, child_conn))
        proc.daemon = True
        t0 = time.perf_counter()
        proc.start()
        # Close child connection in parent process immediately
        child_conn.close()

        timeout_sec = max(0.02, timeout_ms / 1000.0)
        proc.join(timeout=timeout_sec)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if proc.is_alive():
            # True OS-level termination of runaway worker
            try:
                proc.kill()
            except Exception:
                if proc.pid is not None:
                    try:
                        os.kill(proc.pid, signal.SIGKILL)
                    except OSError:
                        pass
            proc.join(timeout=0.5)
            self.total_sigkills += 1
            parent_conn.close()
            return None, elapsed_ms, f"Process killed via SIGKILL after exceeding {timeout_ms:.1f}ms timeout", True

        # Retrieve worker outcome with bounded poll (REL-1)
        payload = None
        try:
            if parent_conn.poll(0.5):
                payload = parent_conn.recv()
        except Exception:
            pass
        finally:
            parent_conn.close()

        if payload is not None:
            if payload.get("ok"):
                return payload.get("solution"), float(payload.get("runtime_ms", elapsed_ms)), None, False
            return None, elapsed_ms, str(payload.get("error", "Unknown worker error")), False

        if proc.exitcode != 0:
            return None, elapsed_ms, f"Worker process exited abnormally with code {proc.exitcode}", False
        return None, elapsed_ms, "Worker process produced no output", False

    def evaluate_candidate_on_split(
        self,
        problem: ProblemSpecification,
        candidate: CandidateSpec,
        split: SplitType = SplitType.DEVELOPMENT,
        baseline_mean_obj: Optional[float] = None,
        baseline_mean_runtime_ms: Optional[float] = None,
        verify_repeatability: bool = False,
        caller: str = "ExecutionSupervisor",
    ) -> VerificationReport:
        """
        Evaluates a candidate across all instances in `split` (guarded by `problem.firewall`),
        validates every output via `problem.validate_solution`, checks theoretical bounds,
        and optionally verifies exact repeatability across a second pass.
        """
        # 1. Request instances through the SplitFirewall (raises SplitAccessViolationError if FINAL_HOLDOUT is sealed)
        instances = problem.firewall.get_instances(split, caller=caller, candidate_id=candidate.candidate_id)
        timeout_ms = problem.default_timeout_ms or self.default_timeout_ms

        # Any candidate with search, iterative loops, or untrusted code runs in killable subprocess (P0 2.2)
        has_iterative_search = False
        if candidate.kind == CandidateKind.DECLARATIVE_PFSP:
            cfg_dict = candidate.payload.get("config", {})
            if isinstance(cfg_dict, dict):
                has_iterative_search = (
                    cfg_dict.get("local_search_op", "none") != "none"
                    or int(cfg_dict.get("perturbation_d", 0)) > 0
                )
        use_subproc = self.force_subprocess_for_all or (candidate.kind == CandidateKind.PYTHON_PROGRAM) or has_iterative_search
        if candidate.kind not in (
            CandidateKind.DECLARATIVE_PFSP,
            CandidateKind.DECLARATIVE_BIN_PACKING,
            CandidateKind.VERIFIED_BASELINE,
        ):
            use_subproc = True

        # Pre-check compilation & AST safety before running instances
        in_proc_runner = None
        try:
            adapter = self.registry.get(candidate.method_id)
            if not use_subproc:
                in_proc_runner = adapter.compile_runner(candidate)
            else:
                # For isolated candidates, validate AST statically in parent without executing code (P1.27)
                if hasattr(adapter, "validate_ast_safety"):
                    code = candidate.payload.get("code", "")
                    entry = candidate.payload.get("entry_func_name", "")
                    ok, err = adapter.validate_ast_safety(code, entry)
                    if not ok:
                        raise ValueError(f"AST Safety Rejection: {err}")
        except Exception as comp_exc:
            err_msg = f"{type(comp_exc).__name__}: {str(comp_exc)}"
            cat = (
                FailureCategory.SYNTAX_OR_AST_REJECTED
                if ("SyntaxError" in err_msg or "AST Safety" in err_msg)
                else FailureCategory.COMPILATION_ERROR
            )
            empty_outcome = problem.aggregate_outcomes(
                split=split,
                outcomes=[
                    problem.evaluate_solution_on_instance(
                        inst, None, runtime_ms=0.0, error_message=err_msg, timed_out=False
                    )
                    for inst in instances
                ],
                baseline_mean_objective=baseline_mean_obj,
                baseline_mean_runtime_ms=baseline_mean_runtime_ms,
            )
            return VerificationReport(
                candidate_id=candidate.candidate_id,
                split=split,
                outcome=empty_outcome,
                failure_category=cat,
                worker_killed_count=0,
                is_repeatable=True,
                threat_model_level=self.threat_model.level.value,
                diagnostics={"compilation_error": err_msg},
            )

        outcomes: List[InstanceEvaluationOutcome] = []
        killed_count = 0
        t_eval_start = time.perf_counter()

        for inst in instances:
            self.total_instance_runs += 1
            if use_subproc:
                sol, rt_ms, err_msg, timed_out = self._run_single_instance_subprocess(
                    candidate, inst, timeout_ms=timeout_ms
                )
                if timed_out:
                    killed_count += 1
            else:
                t0 = time.perf_counter()
                try:
                    sol = in_proc_runner(copy.deepcopy(inst))
                    rt_ms = (time.perf_counter() - t0) * 1000.0
                    err_msg = None
                    timed_out = rt_ms > timeout_ms
                    if timed_out:
                        err_msg = f"Execution exceeded {timeout_ms:.1f}ms budget ({rt_ms:.1f}ms)"
                except Exception as run_exc:
                    rt_ms = (time.perf_counter() - t0) * 1000.0
                    sol = None
                    err_msg = f"{type(run_exc).__name__}: {str(run_exc)}"
                    timed_out = False

            inst_outcome = problem.evaluate_solution_on_instance(
                instance=inst,
                solution=sol,
                runtime_ms=rt_ms,
                error_message=err_msg,
                timed_out=timed_out,
            )
            outcomes.append(inst_outcome)

        self.total_evaluations += 1
        self.total_wall_clock_ms += (time.perf_counter() - t_eval_start) * 1000.0

        agg = problem.aggregate_outcomes(
            split=split,
            outcomes=outcomes,
            baseline_mean_objective=baseline_mean_obj,
            baseline_mean_runtime_ms=baseline_mean_runtime_ms,
        )

        # Determine primary failure category if not fully feasible
        fail_cat = FailureCategory.NONE
        if not agg.is_fully_feasible:
            statuses = [o.status for o in outcomes]
            if SolutionStatus.TIMEOUT in statuses:
                fail_cat = FailureCategory.TIMEOUT_SIGKILL
            elif SolutionStatus.EXECUTION_ERROR in statuses:
                fail_cat = FailureCategory.RUNTIME_EXCEPTION
            else:
                fail_cat = FailureCategory.CONSTRAINT_INFEASIBLE

        # Optional repeatability check on the first 2 instances (P0.1: isolation-preserving)
        is_repeatable = True
        max_drift = 0.0
        if verify_repeatability and agg.is_fully_feasible and len(instances) > 0:
            probe_count = min(2, len(instances))
            for idx in range(probe_count):
                inst = instances[idx]
                try:
                    if use_subproc:
                        sol_2, rt_2, err_2, timed_out_2 = self._run_single_instance_subprocess(
                            candidate, inst, timeout_ms=timeout_ms
                        )
                        if err_2 is not None or timed_out_2:
                            is_repeatable = False
                            fail_cat = FailureCategory.NON_DETERMINISTIC
                            continue
                        out_2 = problem.evaluate_solution_on_instance(inst, sol_2, runtime_ms=rt_2)
                    else:
                        sol_2 = in_proc_runner(copy.deepcopy(inst)) if in_proc_runner else None
                        out_2 = problem.evaluate_solution_on_instance(inst, sol_2, runtime_ms=0.0)

                    obj_1 = outcomes[idx].objective_value
                    obj_2 = out_2.objective_value
                    if (not out_2.is_feasible) or obj_1 is None or obj_2 is None:
                        is_repeatable = False
                        fail_cat = FailureCategory.NON_DETERMINISTIC
                    else:
                        drift = abs(obj_1 - obj_2)
                        if drift > max_drift:
                            max_drift = drift
                        if drift > 1e-6:
                            is_repeatable = False
                            fail_cat = FailureCategory.NON_DETERMINISTIC
                except Exception:
                    is_repeatable = False
                    fail_cat = FailureCategory.NON_DETERMINISTIC

        threat_lvl = (
            ThreatModelLevel.POSIX_SUBPROCESS_AST_RESTRICTED.value
            if use_subproc
            else ThreatModelLevel.TRUSTED_DECLARATIVE_IN_PROCESS.value
        )

        return VerificationReport(
            candidate_id=candidate.candidate_id,
            split=split,
            outcome=agg,
            failure_category=fail_cat,
            worker_killed_count=killed_count,
            is_repeatable=is_repeatable,
            repeatability_max_drift=max_drift,
            threat_model_level=threat_lvl,
        )
