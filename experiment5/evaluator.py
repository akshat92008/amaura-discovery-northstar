"""
Experiment #5: Rich-State Online 1D Bin Packing Evaluator
==========================================================
Provides the candidate algorithm with rich state:
- item: float (current item)
- bin_remaining: list[float] (all currently open bins)
- recent_items: list[float] (last up to 10 packed items)
- bin_capacity: float (bin size)

Returns bin index to place item, or -1 to open a new bin.
Fully isolated, zero-leakage, deterministic benchmark with dual hidden suites (Hidden-1 & Hidden-2).
"""

import ast
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
    "list": list,
    "tuple": tuple,
    "enumerate": enumerate,
    "sorted": sorted,
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

    has_choose_bin_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "math":
                    return False, f"Security violation: Import '{alias.name}' is forbidden. Only 'math' is permitted."
        if isinstance(node, ast.ImportFrom):
            if node.module != "math":
                return False, f"Security violation: Import from '{node.module}' is forbidden. Only 'math' is permitted."
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval", "exec", "open", "__import__", "globals", "locals", "getattr", "setattr"
            }:
                return False, f"Security violation: Forbidden call '{node.func.id}'."
        if isinstance(node, ast.FunctionDef) and node.name == "choose_bin":
            has_choose_bin_func = True
            if len(node.args.args) < 4:
                return False, "Signature error: 'choose_bin' must accept (item, bin_remaining, recent_items, bin_capacity)."

    if not has_choose_bin_func:
        return False, "Missing required function definition: 'def choose_bin(item, bin_remaining, recent_items, bin_capacity) -> int:'"

    return True, None


class RichBinPackingBenchmark:
    """
    Evaluates candidate `choose_bin` functions on Online 1D Bin Packing.
    Items arrive sequentially and candidate observes full open-bin state + recent item history.
    """

    def __init__(self, bin_capacity: float = 100.0):
        self.bin_capacity = bin_capacity
        self.dev_dataset = self._create_dev_dataset(seed=42)
        self.hidden1_dataset = self._create_hidden1_dataset(seed=9999)
        self.hidden2_dataset = self._create_hidden2_dataset(seed=77777)

    def _create_dev_dataset(self, seed: int) -> List[List[float]]:
        """Development set seen during search loop (25 instances, N=100, U(10, 80))."""
        rng = random.Random(seed)
        instances = []
        for _ in range(25):
            items = [round(rng.uniform(10.0, 80.0), 2) for _ in range(100)]
            instances.append(items)
        return instances

    def _create_hidden1_dataset(self, seed: int) -> Dict[str, List[List[float]]]:
        """Main hidden test set (120 instances across 4 families, N=150, exactly matching Exp #2-4)."""
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

    def _create_hidden2_dataset(self, seed: int) -> Dict[str, List[List[float]]]:
        """
        HIDDEN-2 test suite: Completely unseen second benchmark suite.
        Different seed (77777), larger sequence length (N=200), and 4 new distribution families:
        1. Heavy-Tailed Pareto (alpha=1.6, xm=12.0)
        2. Gaussian / Normal (mu=45.0, sigma=15.0)
        3. Small-Item Dominant (75% small [10, 30], 25% large [65, 85])
        4. Tight Adversarial Quads (4-tuples summing to 100.0)
        Total: 120 instances, N=200 (24,000 items).
        """
        rng = random.Random(seed)
        hidden2 = {}

        # 1. Heavy-Tailed Pareto (30 instances, N=200)
        pareto_list = []
        for _ in range(30):
            items = []
            for _ in range(200):
                # Pareto distribution: x = xm / (U ^ (1/alpha))
                u = max(1e-5, rng.random())
                val = 12.0 / (u ** (1.0 / 1.6))
                val = max(10.0, min(85.0, val))
                items.append(round(val, 2))
            pareto_list.append(items)
        hidden2["pareto"] = pareto_list

        # 2. Gaussian / Normal (30 instances, N=200)
        gauss_list = []
        for _ in range(30):
            items = []
            for _ in range(200):
                val = rng.gauss(45.0, 15.0)
                val = max(10.0, min(80.0, val))
                items.append(round(val, 2))
            gauss_list.append(items)
        hidden2["gaussian"] = gauss_list

        # 3. Small-Item Dominant (75% small, 25% large) (30 instances, N=200)
        small_dom = []
        for _ in range(30):
            items = []
            for _ in range(200):
                if rng.random() < 0.75:
                    items.append(round(rng.uniform(10.0, 30.0), 2))
                else:
                    items.append(round(rng.uniform(65.0, 85.0), 2))
            small_dom.append(items)
        hidden2["small_dominant"] = small_dom

        # 4. Tight Adversarial Quads (sets of 4 items summing to 100) (30 instances, N=200)
        quads = []
        for _ in range(30):
            items = []
            for _ in range(50):
                a = round(rng.uniform(15.0, 25.0), 2)
                b = round(rng.uniform(18.0, 28.0), 2)
                c = round(rng.uniform(20.0, 30.0), 2)
                d = round(100.0 - a - b - c, 2)
                if d < 10.0:
                    d = 10.0
                items.extend([a, b, c, d])
            rng.shuffle(items)
            quads.append(items)
        hidden2["quads"] = quads

        return hidden2

    def simulate(self, func: Any, items: List[float]) -> Tuple[int, int]:
        """
        Simulate packing items using candidate's rich-state `choose_bin` function.
        Returns: (total_open_bins, lower_bound).
        """
        open_bins: List[float] = []
        recent_items: List[float] = []

        for item in items:
            feasible_indices = [i for i, rem in enumerate(open_bins) if rem >= item - 1e-6]

            if len(open_bins) == 0:
                # Step 0: Open first bin
                open_bins.append(self.bin_capacity - item)
            elif len(feasible_indices) == 0:
                # No open bin can fit the item -> must open new bin
                open_bins.append(self.bin_capacity - item)
            else:
                # Candidate observes rich state
                chosen_idx_raw = func(item, list(open_bins), list(recent_items), self.bin_capacity)
                try:
                    chosen_idx = int(chosen_idx_raw)
                except Exception:
                    raise TypeError(f"choose_bin returned non-integer value: {chosen_idx_raw}")

                if chosen_idx == -1 or chosen_idx == len(open_bins):
                    # Candidate deliberately chooses to open a new bin
                    open_bins.append(self.bin_capacity - item)
                elif 0 <= chosen_idx < len(open_bins):
                    if open_bins[chosen_idx] >= item - 1e-6:
                        open_bins[chosen_idx] -= item
                    else:
                        raise ValueError(
                            f"Capacity Violation: chosen bin {chosen_idx} remaining space ({open_bins[chosen_idx]:.2f}) "
                            f"< item size ({item:.2f})"
                        )
                else:
                    raise IndexError(f"Index Out of Bounds: chosen index {chosen_idx} invalid for {len(open_bins)} bins")

            # Update recent history (sliding window of max 10)
            recent_items.append(item)
            if len(recent_items) > 10:
                recent_items.pop(0)

        lower_bound = math.ceil(sum(items) / self.bin_capacity)
        return len(open_bins), lower_bound

    def evaluate_code(
        self,
        code: str,
        dataset_type: str = "dev",
        suite: str = "hidden1",
        hidden_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate candidate `choose_bin` code.
        dataset_type: 'dev' or 'hidden'
        suite: 'hidden1' or 'hidden2'
        """
        # Static check
        is_clean, err = static_security_check(code)
        if not is_clean:
            return {
                "is_valid": False,
                "excess_pct": float("inf"),
                "avg_bins": 0,
                "total_bins": 0,
                "lower_bound": 0,
                "runtime_ms": 0.0,
                "error": err,
            }

        # Safe compilation
        local_scope = {}
        try:
            exec(code, {"__builtins__": SAFE_BUILTINS, "math": math}, local_scope)
            func = local_scope["choose_bin"]
        except Exception as e:
            return {
                "is_valid": False,
                "excess_pct": float("inf"),
                "avg_bins": 0,
                "total_bins": 0,
                "lower_bound": 0,
                "runtime_ms": 0.0,
                "error": f"Compilation Error: {e}",
            }

        # Sanity check with sample call
        try:
            sample_idx = int(func(25.0, [40.0, 70.0], [30.0, 15.0], self.bin_capacity))
            if sample_idx not in {-1, 0, 1, 2}:
                return {
                    "is_valid": False,
                    "excess_pct": float("inf"),
                    "avg_bins": 0,
                    "total_bins": 0,
                    "lower_bound": 0,
                    "runtime_ms": 0.0,
                    "error": f"Sanity check returned invalid index: {sample_idx}",
                }
        except Exception as e:
            return {
                "is_valid": False,
                "excess_pct": float("inf"),
                "avg_bins": 0,
                "total_bins": 0,
                "lower_bound": 0,
                "runtime_ms": 0.0,
                "error": f"Runtime Error on test call: {type(e).__name__}: {e}",
            }

        # Select dataset
        if dataset_type == "dev":
            instances = self.dev_dataset
        elif dataset_type == "hidden":
            dataset_source = self.hidden1_dataset if suite == "hidden1" else self.hidden2_dataset
            if hidden_category:
                instances = dataset_source.get(hidden_category, [])
            else:
                instances = [inst for cat in dataset_source.values() for inst in cat]
        else:
            return {
                "is_valid": False,
                "excess_pct": float("inf"),
                "avg_bins": 0,
                "total_bins": 0,
                "lower_bound": 0,
                "runtime_ms": 0.0,
                "error": f"Invalid dataset_type: {dataset_type}",
            }

        start_t = time.perf_counter()
        total_bins = 0
        total_lb = 0

        for inst in instances:
            try:
                bins, lb = self.simulate(func, inst)
                total_bins += bins
                total_lb += lb
            except Exception as e:
                return {
                    "is_valid": False,
                    "excess_pct": float("inf"),
                    "avg_bins": 0,
                    "total_bins": 0,
                    "lower_bound": 0,
                    "runtime_ms": 0.0,
                    "error": f"Simulation Error: {type(e).__name__}: {e}",
                }

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        avg_bins = total_bins / len(instances)
        excess_pct = ((total_bins / max(1, total_lb)) - 1.0) * 100.0

        return {
            "is_valid": True,
            "excess_pct": round(excess_pct, 4),
            "avg_bins": round(avg_bins, 2),
            "total_bins": total_bins,
            "lower_bound": total_lb,
            "runtime_ms": round(elapsed_ms, 2),
            "error": None,
        }


# Standard deterministic baselines adapted to the rich-state interface
BEST_FIT_CODE = '''def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    """Standard Best Fit: choose feasible bin with least remaining space."""
    best_idx = -1
    min_rem = float("inf")
    for i, rem in enumerate(bin_remaining):
        if rem >= item - 1e-6 and rem < min_rem:
            min_rem = rem
            best_idx = i
    return best_idx
'''

FIRST_FIT_CODE = '''def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    """Standard First Fit: choose first feasible bin."""
    for i, rem in enumerate(bin_remaining):
        if rem >= item - 1e-6:
            return i
    return -1
'''

WORST_FIT_CODE = '''def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    """Standard Worst Fit: choose feasible bin with most remaining space."""
    best_idx = -1
    max_rem = -1.0
    for i, rem in enumerate(bin_remaining):
        if rem >= item - 1e-6 and rem > max_rem:
            max_rem = rem
            best_idx = i
    return best_idx
'''
