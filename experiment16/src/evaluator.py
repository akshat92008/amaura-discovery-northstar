"""
Experiment #16 Candidate Dynamic Evaluator
==========================================
Evaluates candidate scheduling policies on continuous dynamic workload traces:
1. AST validation and sandbox enforcement
2. Extraction of `select_node` (required) and `select_pod` (optional)
3. Dynamic event replay execution with scale-aware timeout
4. Calculation of dynamic infrastructure cost, node-hours, and placement feasibility
5. Optional static packing evaluation to verify static performance preservation
"""

import ast
import copy
import math
import os
import signal
import sys
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

sys.path.insert(0, os.path.abspath("."))

from experiment16.src.simulator import simulate_dynamic_replay, simulate_static_packing


class TimeoutException(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutException("Evaluation timed out via SIGALRM")


ALLOWED_MODULES = {
    "math": math,
    "random": __import__("random"),
    "collections": __import__("collections"),
    "itertools": __import__("itertools"),
    "heapq": __import__("heapq"),
    "typing": __import__("typing"),
    "copy": copy
}

FORBIDDEN_NAMES = {
    "open", "exec", "eval", "__import__", "globals", "locals", "getattr",
    "setattr", "delattr", "compile", "breakpoint", "input", "memoryview"
}


class PodSchedulingDynamicEvaluator:
    def __init__(
        self,
        scale_aware_base_ms: float = 2000.0,
        scale_aware_per_nm_ms: float = 1.0,
        sigalrm_interrupt_sec: int = 30
    ):
        self.scale_aware_base_ms = scale_aware_base_ms
        self.scale_aware_per_nm_ms = scale_aware_per_nm_ms
        self.sigalrm_interrupt_sec = sigalrm_interrupt_sec

    def check_ast_security(self, code_str: str) -> Tuple[bool, Optional[str]]:
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        has_select_node = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "select_node":
                has_select_node = True

            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in ALLOWED_MODULES:
                        return False, f"Disallowed import: {alias.name}"

            if isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod not in ALLOWED_MODULES:
                        return False, f"Disallowed import from: {node.module}"

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                    return False, f"Forbidden call: {node.func.id}"

            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return False, f"Forbidden dunder attribute access: {node.attr}"

        if not has_select_node:
            return False, "Missing required function: `def select_node(pod, feasible_nodes, state)`"

        return True, None

    def evaluate_solver_code_dynamic(
        self,
        code_str: str,
        dynamic_traces: List[Dict[str, Any]],
        static_instances: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a candidate policy across dynamic traces (primary) and optional static instances.
        """
        is_safe, error_msg = self.check_ast_security(code_str)
        if not is_safe:
            return {
                "is_valid": False,
                "error": error_msg,
                "total_cost": float("inf"),
                "node_hours": float("inf"),
                "unscheduled_total": 999999,
                "placement_feasibility": 0.0,
                "static_cost": float("inf"),
                "runtime_ms": 0.0
            }

        exec_globals: Dict[str, Any] = {}
        try:
            compiled = compile(code_str, "<candidate_policy>", "exec")
            exec(compiled, exec_globals)
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Exec error: {e}",
                "total_cost": float("inf"),
                "node_hours": float("inf"),
                "unscheduled_total": 999999,
                "placement_feasibility": 0.0,
                "static_cost": float("inf"),
                "runtime_ms": 0.0
            }

        select_node_fn = exec_globals.get("select_node")
        select_pod_fn = exec_globals.get("select_pod", None)

        if not callable(select_node_fn):
            return {
                "is_valid": False,
                "error": "select_node is not callable",
                "total_cost": float("inf"),
                "node_hours": float("inf"),
                "unscheduled_total": 999999,
                "placement_feasibility": 0.0,
                "static_cost": float("inf"),
                "runtime_ms": 0.0
            }

        total_cost_sum = 0.0
        total_node_hours_sum = 0.0
        total_unscheduled_sum = 0
        total_pods_sum = 0
        total_scheduled_sum = 0
        trace_results = []
        eval_start_time = time.perf_counter()

        # Dynamic Trace Evaluation
        for trace in dynamic_traces:
            trace_id = trace.get("trace_id", "dyn_trace")
            events_count = len(trace.get("events", []))
            nodes_count = len(trace.get("nodes", []))

            # Timeout setting
            timeout_ms = self.scale_aware_base_ms + self.scale_aware_per_nm_ms * (events_count * math.sqrt(max(1, nodes_count)))
            timeout_sec = max(5, int(timeout_ms / 1000.0) + 1)
            timeout_sec = min(timeout_sec, self.sigalrm_interrupt_sec)

            use_signal = (threading.current_thread() is threading.main_thread() and os.name != "nt")

            if use_signal:
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(timeout_sec)

            try:
                res = simulate_dynamic_replay(trace, select_node_fn, select_pod_fn)
            except TimeoutException:
                if use_signal:
                    signal.alarm(0)
                return {
                    "is_valid": False,
                    "error": f"Dynamic simulation timeout on {trace_id}",
                    "total_cost": float("inf"),
                    "node_hours": float("inf"),
                    "unscheduled_total": 999999,
                    "placement_feasibility": 0.0,
                    "static_cost": float("inf"),
                    "runtime_ms": (time.perf_counter() - eval_start_time) * 1000.0
                }
            except Exception as e:
                if use_signal:
                    signal.alarm(0)
                return {
                    "is_valid": False,
                    "error": f"Runtime error on {trace_id}: {e}",
                    "total_cost": float("inf"),
                    "node_hours": float("inf"),
                    "unscheduled_total": 999999,
                    "placement_feasibility": 0.0,
                    "static_cost": float("inf"),
                    "runtime_ms": (time.perf_counter() - eval_start_time) * 1000.0
                }
            finally:
                if use_signal:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            total_cost_sum += res["total_cost"]
            total_node_hours_sum += res["node_hours"]
            total_unscheduled_sum += res["unscheduled_count"]
            total_pods_sum += res["total_pods"]
            total_scheduled_sum += res["scheduled_count"]
            trace_results.append({
                "trace_id": trace_id,
                "cost": res["total_cost"],
                "node_hours": res["node_hours"],
                "unscheduled": res["unscheduled_count"],
                "peak_nodes": res["peak_active_nodes"]
            })

        # Static Windows Evaluation (if provided)
        static_cost_sum = 0.0
        if static_instances:
            for inst in static_instances:
                try:
                    s_res = simulate_static_packing(inst, select_node_fn, select_pod_fn)
                    static_cost_sum += s_res["total_cost"]
                except Exception:
                    static_cost_sum += 10000.0

        total_runtime_ms = (time.perf_counter() - eval_start_time) * 1000.0
        feasibility = total_scheduled_sum / total_pods_sum if total_pods_sum > 0 else 1.0

        return {
            "is_valid": True,
            "error": None,
            "total_cost": round(total_cost_sum, 4),
            "node_hours": round(total_node_hours_sum, 4),
            "unscheduled_total": total_unscheduled_sum,
            "placement_feasibility": round(feasibility, 4),
            "static_cost": round(static_cost_sum, 4) if static_instances else 0.0,
            "trace_results": trace_results,
            "runtime_ms": round(total_runtime_ms, 2)
        }
