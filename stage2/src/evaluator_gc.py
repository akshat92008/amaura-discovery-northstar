"""
Stage 2: Deterministic Graph Coloring Evaluator
==============================================
Target Interface:
    def color_graph(adj: list[list[int]]) -> list[int]

Features:
- AST security validation via stage2.src.sandbox.check_ast_security.
- Defensive copy of adjacency list so solver cannot mutate benchmark instances.
- Pre-execution sanity check on triangle graph K3.
- Precise chromatic validation (no adjacent vertices share color).
- Strict per-instance timeout using signal.alarm to prevent infinite loops.
- Deterministic scoring: total colors across dataset.
- Preregistered penalty for invalid/timeout candidates: 999,999 colors.
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


class GraphColoringEvaluator:
    def __init__(
        self,
        scale_aware_base_ms: float = 200.0,
        scale_aware_per_vertex_ms: float = 2.0,
        hard_sigalrm_sec: int = 5
    ):
        self.scale_aware_base_ms = scale_aware_base_ms
        self.scale_aware_per_vertex_ms = scale_aware_per_vertex_ms
        self.hard_sigalrm_sec = hard_sigalrm_sec

    def validate_coloring(self, adj: List[List[int]], colors: Any) -> Tuple[bool, Optional[str], int]:
        n = len(adj)
        if not isinstance(colors, (list, tuple)):
            return False, f"Output is type '{type(colors).__name__}', expected list[int].", 999999

        if len(colors) != n:
            return False, f"Output length {len(colors)} != number of vertices {n}.", 999999

        for u in range(n):
            c_u = colors[u]
            if not isinstance(c_u, int) or c_u < 0:
                return False, f"Vertex {u} has invalid color value: {c_u} (must be non-negative int).", 999999
            for v in adj[u]:
                if u != v and colors[v] == c_u:
                    return False, f"Color conflict: adjacent vertices {u} and {v} share color {c_u}.", 999999

        unique_colors = len(set(colors))
        return True, None, unique_colors

    def evaluate_code(self, code_str: str, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        is_safe, error_msg = check_ast_security(code_str, required_func="color_graph")
        if not is_safe:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": error_msg
            }

        # Build execution environment
        exec_globals: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
        for mod_name in ALLOWED_MODULES:
            try:
                exec_globals[mod_name] = __import__(mod_name)
            except ImportError:
                pass

        try:
            compiled = sanitize_and_compile(code_str, "<candidate_gc>")
            exec(compiled, exec_globals)
            solver_fn = exec_globals["color_graph"]
        except Exception as e:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Compilation/Execution Error: {type(e).__name__}: {e}"
            }

        # Sanity check with small triangle graph K3
        has_sigalrm = hasattr(signal, "SIGALRM") and os.name != "nt"
        prev_handler = None
        if has_sigalrm:
            prev_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
            signal.setitimer(signal.ITIMER_REAL, 1.0, 0.5)
        try:
            k3_adj = [[1, 2], [0, 2], [0, 1]]
            test_res = solver_fn([list(r) for r in k3_adj])
            is_valid_k3, err_k3, k3_colors = self.validate_coloring(k3_adj, test_res)
            if not is_valid_k3 or k3_colors != 3:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "scores": [],
                    "runtime_ms": 0.0,
                    "error": f"Sanity check failed on K3: {err_k3 or f'used {k3_colors} colors instead of 3'}"
                }
        except SandboxTimeoutException:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": "Timeout Exceeded on K3 sanity check (infinite loop)"
            }
        except Exception as e:
            return {
                "is_valid": False,
                "total_colors": 999999,
                "avg_colors": 999999.0,
                "scores": [],
                "runtime_ms": 0.0,
                "error": f"Runtime Exception during K3 sanity check: {type(e).__name__}: {e}"
            }
        finally:
            if has_sigalrm:
                signal.setitimer(signal.ITIMER_REAL, 0)
                if prev_handler is not None:
                    signal.signal(signal.SIGALRM, prev_handler)

        total_colors = 0
        scores: List[int] = []
        eval_start_time = time.perf_counter()

        has_sigalrm = hasattr(signal, "SIGALRM") and os.name != "nt"

        for idx, instance in enumerate(dataset):
            adj = instance["adj"]
            n = len(adj)
            adj_copy = [list(row) for row in adj]

            # Timeout limit for this instance
            instance_limit_ms = self.scale_aware_base_ms + self.scale_aware_per_vertex_ms * n
            instance_limit_sec = max(1, int(instance_limit_ms / 1000.0) + 1)
            alarm_sec = min(instance_limit_sec, self.hard_sigalrm_sec)

            prev_handler = None
            if has_sigalrm:
                prev_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
                signal.setitimer(signal.ITIMER_REAL, float(alarm_sec), 0.5)

            t0 = time.perf_counter()
            try:
                result_colors = solver_fn(adj_copy)
            except SandboxTimeoutException:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Timeout Exceeded (SIGALRM): instance {idx} (N={n}) exceeded {alarm_sec}s hard limit"
                }
            except Exception as e:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Solver exception on instance {idx} (N={n}): {type(e).__name__}"
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
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Soft Timeout Exceeded: instance {idx} took {inst_duration_ms:.1f}ms > limit {instance_limit_ms:.1f}ms"
                }

            is_valid, val_err, k = self.validate_coloring(adj, result_colors)
            if not is_valid:
                return {
                    "is_valid": False,
                    "total_colors": 999999,
                    "avg_colors": 999999.0,
                    "scores": [],
                    "runtime_ms": round((time.perf_counter() - eval_start_time) * 1000.0, 2),
                    "error": f"Invalid coloring on instance {idx}: {val_err}"
                }

            total_colors += k
            scores.append(k)

        total_runtime_ms = (time.perf_counter() - eval_start_time) * 1000.0
        avg_colors = total_colors / len(dataset) if dataset else 0.0

        return {
            "is_valid": True,
            "total_colors": total_colors,
            "avg_colors": round(avg_colors, 4),
            "scores": scores,
            "runtime_ms": round(total_runtime_ms, 2),
            "error": None
        }
