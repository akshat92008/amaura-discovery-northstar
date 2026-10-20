"""
Experiment #2: Objective Online 1D Bin Packing Evaluator
=========================================================
Fully isolated, zero-leakage, deterministic benchmark for LLM algorithm discovery.
"""

import ast
import concurrent.futures
import math
import random
import time
from typing import List, Tuple, Dict, Any, Optional


def safe_import(name, *args, **kwargs):
    if name == "math":
        return math
    raise ImportError(f"Import of '{name}' is forbidden. Only 'math' is permitted.")


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
    "print": lambda *args, **kwargs: None,
    "__import__": safe_import,
}


def static_security_check(code: str) -> Tuple[bool, Optional[str]]:
    """
    Strict sandbox static analysis:
    - DISALLOW unauthorized module imports (only pure 'math' permitted)
    - DISALLOW dangerous builtins, file/network access, dynamic execution
    - VERIFY required function signature
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    has_priority_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "math":
                    return False, f"Security violation: Import '{alias.name}' is forbidden. Only 'math' is permitted."
        if isinstance(node, ast.ImportFrom):
            if node.module != "math":
                return False, f"Security violation: Import from '{node.module}' is forbidden. Only 'math' is permitted."
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "open", "__import__", "globals", "locals", "getattr", "setattr"}:
                return False, f"Security violation: Forbidden call '{node.func.id}'."
        if isinstance(node, ast.FunctionDef) and node.name == "priority":
            has_priority_func = True
            if len(node.args.args) < 3:
                return False, "Signature error: 'priority' must accept (item, remaining_capacity, bin_capacity)."

    if not has_priority_func:
        return False, "Missing required function definition: 'def priority(item, remaining_capacity, bin_capacity):'"

    return True, None


class BinPackingBenchmark:
    """
    Evaluates candidate priority functions on Online 1D Bin Packing.
    Items arrive sequentially and must be immediately assigned to a feasible open bin
    or a new bin must be opened.
    """

    def __init__(self, bin_capacity: float = 100.0):
        self.bin_capacity = bin_capacity
        self.dev_dataset = self._create_dev_dataset(seed=42)
        self.hidden_dataset = self._create_hidden_dataset(seed=9999)

    def _create_dev_dataset(self, seed: int) -> List[List[float]]:
        """Development set seen during search loop (25 instances, N=100, U(10, 80))."""
        rng = random.Random(seed)
        instances = []
        for _ in range(25):
            items = [round(rng.uniform(10.0, 80.0), 2) for _ in range(100)]
            instances.append(items)
        return instances

    def _create_hidden_dataset(self, seed: int) -> Dict[str, List[List[float]]]:
        """Completely hidden test set evaluated ONLY after discovery finishes."""
        rng = random.Random(seed)
        hidden = {}

        # 1. Uniform distribution (30 instances, N=150)
        unif = []
        for _ in range(30):
            items = [round(rng.uniform(10.0, 80.0), 2) for _ in range(150)]
            unif.append(items)
        hidden["uniform"] = unif

        # 2. Skewed Weibull (shape 1.8, scale 42.0) (30 instances, N=150)
        weib = []
        for _ in range(30):
            items = []
            for _ in range(150):
                val = 42.0 * ((-math.log(1.0 - rng.random())) ** (1.0 / 1.8))
                val = max(10.0, min(85.0, val))
                items.append(round(val, 2))
            weib.append(items)
        hidden["weibull"] = weib

        # 3. Bimodal distribution (50% small 10-25, 50% large 60-85) (30 instances, N=150)
        bimod = []
        for _ in range(30):
            items = []
            for _ in range(150):
                if rng.random() < 0.5:
                    items.append(round(rng.uniform(10.0, 25.0), 2))
                else:
                    items.append(round(rng.uniform(60.0, 85.0), 2))
            bimod.append(items)
        hidden["bimodal"] = bimod

        # 4. Triplet Partitions (triplets summing to bin_capacity=100) (30 instances, N=150)
        triplets = []
        for _ in range(30):
            items = []
            for _ in range(50):
                a = round(rng.uniform(20.0, 35.0), 2)
                b = round(rng.uniform(25.0, 40.0), 2)
                c = round(100.0 - a - b, 2)
                items.extend([a, b, c])
            rng.shuffle(items)
            triplets.append(items)
        hidden["triplets"] = triplets

        return hidden

    def simulate(self, func: Any, items: List[float]) -> Tuple[int, int]:
        """Simulate packing items using the candidate's priority scoring function."""
        open_bins: List[float] = []

        for item in items:
            best_bin_idx = -1
            best_priority = -float("inf")

            for idx, rem in enumerate(open_bins):
                if rem >= item - 1e-6:
                    p = float(func(item, rem, self.bin_capacity))
                    if math.isnan(p) or math.isinf(p):
                        raise ValueError(f"Priority returned non-finite value: {p}")
                    if p > best_priority:
                        best_priority = p
                        best_bin_idx = idx

            if best_bin_idx >= 0:
                open_bins[best_bin_idx] -= item
            else:
                open_bins.append(self.bin_capacity - item)

        lower_bound = math.ceil(sum(items) / self.bin_capacity)
        return len(open_bins), lower_bound

    def evaluate_code(
        self, code: str, dataset_type: str = "dev", hidden_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate code against dev or hidden dataset.
        Returns: {is_valid, excess_pct, avg_bins, total_bins, lower_bound, runtime_ms, error}
        """
        # Static check
        is_clean, err = static_security_check(code)
        if not is_clean:
            return {"is_valid": False, "excess_pct": float("inf"), "avg_bins": 0, "total_bins": 0, "lower_bound": 0, "runtime_ms": 0.0, "error": err}

        # Safe compilation
        local_scope = {}
        try:
            exec(code, {"__builtins__": SAFE_BUILTINS, "math": math}, local_scope)
            func = local_scope["priority"]
        except Exception as e:
            return {"is_valid": False, "excess_pct": float("inf"), "avg_bins": 0, "total_bins": 0, "lower_bound": 0, "runtime_ms": 0.0, "error": f"Compilation Error: {e}"}

        # Sanity check with sample input
        try:
            test_val = float(func(20.0, 50.0, self.bin_capacity))
            if math.isnan(test_val) or math.isinf(test_val):
                return {"is_valid": False, "excess_pct": float("inf"), "avg_bins": 0, "total_bins": 0, "lower_bound": 0, "runtime_ms": 0.0, "error": f"Sanity check returned non-finite score {test_val}"}
        except Exception as e:
            return {"is_valid": False, "excess_pct": float("inf"), "avg_bins": 0, "total_bins": 0, "lower_bound": 0, "runtime_ms": 0.0, "error": f"Runtime Error on test call: {type(e).__name__}: {e}"}

        # Select dataset
        if dataset_type == "dev":
            instances = self.dev_dataset
        elif dataset_type == "hidden":
            if hidden_category:
                instances = self.hidden_dataset.get(hidden_category, [])
            else:
                instances = [inst for cat in self.hidden_dataset.values() for inst in cat]
        else:
            return {"is_valid": False, "excess_pct": float("inf"), "avg_bins": 0, "total_bins": 0, "lower_bound": 0, "runtime_ms": 0.0, "error": "Invalid dataset type"}

        start_t = time.perf_counter()
        total_bins = 0
        total_lb = 0

        for inst in instances:
            try:
                bins, lb = self.simulate(func, inst)
                total_bins += bins
                total_lb += lb
            except Exception as e:
                return {"is_valid": False, "excess_pct": float("inf"), "avg_bins": 0, "total_bins": 0, "lower_bound": 0, "runtime_ms": 0.0, "error": f"Simulation Error: {type(e).__name__}: {e}"}

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        avg_bins = total_bins / len(instances)
        # Normalized excess percentage over theoretical minimum
        excess_pct = ((total_bins / max(1, total_lb)) - 1.0) * 100.0

        return {
            "is_valid": True,
            "excess_pct": round(excess_pct, 4),
            "avg_bins": round(avg_bins, 2),
            "total_bins": total_bins,
            "lower_bound": total_lb,
            "runtime_ms": round(elapsed_ms, 2),
            "error": None
        }
