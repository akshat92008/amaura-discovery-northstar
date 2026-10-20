"""
Experiment #13 Candidate Evaluator
==================================
Evaluates candidate scheduling policies:
1. AST validation and sandbox enforcement
2. Extraction of `select_node` (required) and `select_pod` (optional)
3. Execution on instance suite with scale-aware timeout
4. Comprehensive metric calculation
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

from experiment13.src.simulator import simulate_schedule


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


class PodSchedulingEvaluator:
    def __init__(
        self,
        scale_aware_base_ms: float = 1000.0,
        scale_aware_per_nm_ms: float = 1.0,
        sigalrm_interrupt_sec: int = 10
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

    def evaluate_solver_code(
        self,
        code_str: str,
        instances: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        is_safe, error_msg = self.check_ast_security(code_str)
        if not is_safe:
            return {
                "is_valid": False,
                "total_cost": 999999.0,
                "mean_cost": 999999.0,
                "instance_costs": [],
                "active_nodes_mean": 0.0,
                "unscheduled_total": 999,
                "runtime_ms": 0.0,
                "error": error_msg
            }

        exec_globals = {}
        try:
            compiled = compile(code_str, "<candidate_policy>", "exec")
            exec(compiled, exec_globals)
        except Exception as e:
            return {
                "is_valid": False,
                "total_cost": 999999.0,
                "mean_cost": 999999.0,
                "instance_costs": [],
                "active_nodes_mean": 0.0,
                "unscheduled_total": 999,
                "runtime_ms": 0.0,
                "error": f"Exec error: {e}"
            }

        select_node_fn = exec_globals.get("select_node")
        select_pod_fn = exec_globals.get("select_pod")

        if not callable(select_node_fn):
            return {
                "is_valid": False,
                "total_cost": 999999.0,
                "mean_cost": 999999.0,
                "instance_costs": [],
                "active_nodes_mean": 0.0,
                "unscheduled_total": 999,
                "runtime_ms": 0.0,
                "error": "select_node is not callable"
            }

        # Execute over instance suite
        t0 = time.perf_counter()
        instance_costs = []
        total_cost = 0.0
        unscheduled_total = 0
        active_nodes_total = 0

        is_main = (threading.current_thread() is threading.main_thread())
        old_handler = None
        if is_main:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self.sigalrm_interrupt_sec)

        try:
            for inst in instances:
                n_pods = inst["n_pods"]
                m_nodes = inst["m_nodes"]
                timeout_limit_ms = self.scale_aware_base_ms + self.scale_aware_per_nm_ms * (n_pods * m_nodes)

                inst_t0 = time.perf_counter()
                res = simulate_schedule(inst, select_node_fn=select_node_fn, select_pod_fn=select_pod_fn)
                inst_dur_ms = (time.perf_counter() - inst_t0) * 1000.0

                if inst_dur_ms > timeout_limit_ms:
                    if is_main:
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)
                    return {
                        "is_valid": False,
                        "total_cost": 999999.0,
                        "mean_cost": 999999.0,
                        "instance_costs": [],
                        "active_nodes_mean": 0.0,
                        "unscheduled_total": 999,
                        "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                        "error": f"Scale-aware timeout: {inst_dur_ms:.1f}ms > {timeout_limit_ms:.1f}ms on instance {inst['instance_id']}"
                    }

                cost = res["total_cost"]
                instance_costs.append(cost)
                total_cost += cost
                unscheduled_total += res["unscheduled_count"]
                active_nodes_total += res["active_nodes_count"]

            if is_main:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except TimeoutException:
            if is_main:
                signal.signal(signal.SIGALRM, old_handler)
            return {
                "is_valid": False,
                "total_cost": 999999.0,
                "mean_cost": 999999.0,
                "instance_costs": [],
                "active_nodes_mean": 0.0,
                "unscheduled_total": 999,
                "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                "error": f"SIGALRM interrupt after {self.sigalrm_interrupt_sec}s"
            }
        except Exception as e:
            if is_main:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return {
                "is_valid": False,
                "total_cost": 999999.0,
                "mean_cost": 999999.0,
                "instance_costs": [],
                "active_nodes_mean": 0.0,
                "unscheduled_total": 999,
                "runtime_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                "error": f"Runtime simulation error: {e}"
            }

        total_runtime_ms = (time.perf_counter() - t0) * 1000.0
        n_inst = len(instances)

        return {
            "is_valid": True,
            "total_cost": round(total_cost, 4),
            "mean_cost": round(total_cost / n_inst, 4),
            "instance_costs": instance_costs,
            "active_nodes_mean": round(active_nodes_total / n_inst, 2),
            "unscheduled_total": unscheduled_total,
            "runtime_ms": round(total_runtime_ms, 2),
            "error": None
        }
