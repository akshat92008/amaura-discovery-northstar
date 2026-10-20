"""
Bin Packing Domain: Representation B (Expanded Interface)
=========================================================
Interface:
def select_bin(item: float, open_bins: list, stream_history: list, bin_capacity: float) -> int:

Allows policy to inspect:
1. Arriving item.
2. Complete current state of all feasible open bins (bin_id, remaining_capacity, used_capacity, items_count).
3. Past item arrival history (stream_history).
No access to future items.
Outer simulator retains complete control over stream iteration and physical bin assignment.
"""

import copy
import json
import math
import os
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

from stage3.src.sandbox import check_ast_security, sanitize_and_compile, sanitize_exception_name, SAFE_BUILTINS


class StatefulBinPackingSimulator:
    """
    Outer simulator retaining control of stream iteration, item feeding, and bin state.
    Calls candidate `select_bin` policy for each arriving item.
    """
    def __init__(self, bin_capacity: float = 100.0, tolerance: float = 1e-6):
        self.bin_capacity = float(bin_capacity)
        self.tolerance = float(tolerance)

    def compute_l1(self, items: List[float], capacity: float) -> int:
        total_weight = sum(items)
        return int(math.ceil(total_weight / capacity))

    def pack_stream(
        self,
        items: List[float],
        select_bin_fn: Callable[[float, List[Dict[str, Any]], List[float], float], int],
        strict_errors: bool = True
    ) -> Tuple[int, List[Dict[str, Any]], int, float, List[int]]:
        """
        Packs a single stream of items using `select_bin_fn`.
        Returns:
            bins_used: int
            open_bins: List[Dict[str, Any]]
            l1: int
            rho: float
            decisions: List[int] (bin_id chosen for each item, or -1 for new bin)
        """
        open_bins: List[Dict[str, Any]] = []
        stream_history: List[float] = []
        decisions: List[int] = []
        next_bin_id = 0

        for item in items:
            feasible = [
                b for b in open_bins
                if b["remaining_capacity"] >= item - self.tolerance
            ]

            if not feasible:
                # No feasible open bin exists; simulator must open a new bin
                choice = -1
            else:
                # Pass defensive copies to prevent candidate from mutating simulator state
                exposed_bins = [
                    {
                        "bin_id": b["bin_id"],
                        "remaining_capacity": b["remaining_capacity"],
                        "used_capacity": b["used_capacity"],
                        "items_count": b["items_count"]
                    }
                    for b in feasible
                ]
                exposed_history = list(stream_history)

                try:
                    choice = select_bin_fn(item, exposed_bins, exposed_history, self.bin_capacity)
                    if not isinstance(choice, (int, float)):
                        raise TypeError(f"select_bin returned non-numeric type {type(choice).__name__}: {choice}")
                    choice = int(choice)
                except Exception as e:
                    if strict_errors:
                        raise RuntimeError(f"Candidate raised exception on item={item}: {e}") from e
                    choice = -1

            if choice == -1:
                # Open a new bin
                open_bins.append({
                    "bin_id": next_bin_id,
                    "remaining_capacity": round(self.bin_capacity - item, 8),
                    "used_capacity": round(item, 8),
                    "items_count": 1
                })
                decisions.append(-1)
                next_bin_id += 1
            else:
                # Verify chosen bin exists and has sufficient capacity
                target_bin = next((b for b in feasible if b["bin_id"] == choice), None)
                if target_bin is None:
                    if strict_errors:
                        raise ValueError(f"Candidate selected invalid or infeasible bin_id {choice} for item={item}")
                    # Fallback on non-strict: open new bin
                    open_bins.append({
                        "bin_id": next_bin_id,
                        "remaining_capacity": round(self.bin_capacity - item, 8),
                        "used_capacity": round(item, 8),
                        "items_count": 1
                    })
                    decisions.append(-1)
                    next_bin_id += 1
                else:
                    target_bin["remaining_capacity"] = round(target_bin["remaining_capacity"] - item, 8)
                    target_bin["used_capacity"] = round(target_bin["used_capacity"] + item, 8)
                    target_bin["items_count"] += 1
                    decisions.append(choice)

            stream_history.append(item)

        bins_used = len(open_bins)
        l1 = self.compute_l1(items, self.bin_capacity)
        rho = ((bins_used - l1) / float(l1)) if l1 > 0 else 0.0

        return bins_used, open_bins, l1, rho, decisions

    def evaluate_streams(
        self,
        streams: List[List[float]],
        select_bin_fn: Callable[[float, List[Dict[str, Any]], List[float], float], int],
        strict_errors: bool = True
    ) -> Dict[str, Any]:
        rhos: List[float] = []
        all_decisions: List[List[int]] = []
        total_bins = 0
        total_l1 = 0

        for items in streams:
            bins_used, _, l1, rho, decisions = self.pack_stream(items, select_bin_fn, strict_errors=strict_errors)
            rhos.append(rho)
            all_decisions.append(decisions)
            total_bins += bins_used
            total_l1 += l1

        mean_rho = sum(rhos) / len(rhos) if rhos else 0.0
        return {
            "mean_excess_ratio": mean_rho,
            "total_bins": total_bins,
            "total_l1": total_l1,
            "stream_excess_ratios": rhos,
            "all_decisions": all_decisions
        }


# Canonical Baselines for Representation B
def best_fit_select_bin(item: float, open_bins: List[Dict[str, Any]], stream_history: List[float], bin_capacity: float) -> int:
    """Best-Fit: select feasible bin with minimum remaining capacity after placement."""
    if not open_bins:
        return -1
    best_bin = min(open_bins, key=lambda b: (b["remaining_capacity"] - item, b["bin_id"]))
    return int(best_bin["bin_id"])


def first_fit_select_bin(item: float, open_bins: List[Dict[str, Any]], stream_history: List[float], bin_capacity: float) -> int:
    """First-Fit: select the first open feasible bin."""
    if not open_bins:
        return -1
    return int(open_bins[0]["bin_id"])


def worst_fit_select_bin(item: float, open_bins: List[Dict[str, Any]], stream_history: List[float], bin_capacity: float) -> int:
    """Worst-Fit: select feasible bin with maximum remaining capacity."""
    if not open_bins:
        return -1
    worst_bin = max(open_bins, key=lambda b: (b["remaining_capacity"], -b["bin_id"]))
    return int(worst_bin["bin_id"])


class BinPackingRepBDomain:
    """
    Representation B domain for online 1D bin packing.
    """
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "bin_packing")
        self.data_dir = data_dir
        self.simulator = StatefulBinPackingSimulator(bin_capacity=100.0)

        with open(os.path.join(self.data_dir, "train.json"), "r", encoding="utf-8") as f:
            self.train_data = json.load(f)
        with open(os.path.join(self.data_dir, "pilot_validation.json"), "r", encoding="utf-8") as f:
            self.val_data = json.load(f)

        self.train_streams = [s["items"] for s in self.train_data]
        self.val_streams = [s["items"] for s in self.val_data]

        # Baselines
        self.train_bf_res = self.simulator.evaluate_streams(self.train_streams, best_fit_select_bin)
        self.train_ff_res = self.simulator.evaluate_streams(self.train_streams, first_fit_select_bin)
        self.train_wf_res = self.simulator.evaluate_streams(self.train_streams, worst_fit_select_bin)

        self.val_bf_res = self.simulator.evaluate_streams(self.val_streams, best_fit_select_bin)
        self.val_ff_res = self.simulator.evaluate_streams(self.val_streams, first_fit_select_bin)
        self.val_wf_res = self.simulator.evaluate_streams(self.val_streams, worst_fit_select_bin)

        self.baselines = {
            "train": {
                "best_fit": self.train_bf_res["mean_excess_ratio"],
                "first_fit": self.train_ff_res["mean_excess_ratio"],
                "worst_fit": self.train_wf_res["mean_excess_ratio"],
            },
            "val": {
                "best_fit": self.val_bf_res["mean_excess_ratio"],
                "first_fit": self.val_ff_res["mean_excess_ratio"],
                "worst_fit": self.val_wf_res["mean_excess_ratio"],
            }
        }

    @property
    def name(self) -> str:
        return "bin_packing_rep_b"

    @property
    def function_name(self) -> str:
        return "select_bin"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert algorithm designer specializing in online combinatorial optimization.\n"
            "Keep internal reasoning concise (under 100 words). Immediately produce the complete python function.\n"
            "Your task is to design an online 1D bin packing decision policy in pure Python.\n\n"
            "Interface:\n"
            "```python\n"
            "def select_bin(item: float, open_bins: list, stream_history: list, bin_capacity: float) -> int:\n"
            "```\n"
            "Rules:\n"
            "1. `open_bins` contains all currently open bins that have sufficient remaining capacity to fit `item`.\n"
            "   Each element is a dict: {'bin_id': int, 'remaining_capacity': float, 'used_capacity': float, 'items_count': int}.\n"
            "2. `stream_history` is a list of previous items that arrived before this item in the current stream.\n"
            "3. Return the `bin_id` (int) of the chosen bin from `open_bins` to place the item, OR return -1 to open a new bin.\n"
            "4. Objective is to minimize the normalized excess ratio rho = (bins_used - L1) / L1 across item streams.\n"
            "5. Allowed libraries: `math` only. Do not use external libraries.\n"
            "6. Return ONLY valid Python inside a ```python ``` markdown block."
        )

    def get_user_prompt(self, proposal_idx: int) -> str:
        return (
            f"Design an innovative, high-performance online bin packing policy `select_bin` (variant {proposal_idx}).\n\n"
            "Baseline reference (Best-Fit):\n"
            "```python\n"
            "def select_bin(item: float, open_bins: list, stream_history: list, bin_capacity: float) -> int:\n"
            "    # Best-Fit: choose the feasible bin with the smallest remaining capacity\n"
            "    if not open_bins:\n"
            "        return -1\n"
            "    return min(open_bins, key=lambda b: (b['remaining_capacity'] - item, b['bin_id']))['bin_id']\n"
            "```\n\n"
            "Can you exploit the complete state of open bins or recent arrival history (e.g. bin fullness patterns, item size distribution, item frequency, or avoiding unusable residual gaps) to outperform Best-Fit?\n"
            "Output the complete Python code for `select_bin`."
        )

    def evaluate_candidate(self, code_str: str, on_validation: bool = False) -> Dict[str, Any]:
        """Evaluates candidate code with AST check, sandboxing, and execution."""
        t0 = time.time()
        is_safe, error_msg = check_ast_security(code_str, required_func=self.function_name)
        if not is_safe:
            return {
                "is_valid": False,
                "error": error_msg,
                "score": 1.0,
                "relative_gap": 1.0,
                "beats_baseline": False,
                "runtime_ms": round((time.time() - t0) * 1000, 2),
                "decision_disagreement_rate": None,
                "all_decisions": []
            }

        try:
            code_obj = sanitize_and_compile(code_str, filename="<rep_b_candidate>")
            namespace = {"__builtins__": SAFE_BUILTINS, "math": math}
            exec(code_obj, namespace)
            candidate_fn = namespace.get(self.function_name)
            if not callable(candidate_fn):
                return {
                    "is_valid": False,
                    "error": f"Function '{self.function_name}' is not callable",
                    "score": 1.0,
                    "relative_gap": 1.0,
                    "beats_baseline": False,
                    "runtime_ms": round((time.time() - t0) * 1000, 2),
                    "decision_disagreement_rate": None,
                    "all_decisions": []
                }
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Compilation error: {sanitize_exception_name(e)}",
                "score": 1.0,
                "relative_gap": 1.0,
                "beats_baseline": False,
                "runtime_ms": round((time.time() - t0) * 1000, 2),
                "decision_disagreement_rate": None,
                "all_decisions": []
            }

        streams = self.val_streams if on_validation else self.train_streams
        baseline_bf = self.baselines["val"]["best_fit"] if on_validation else self.baselines["train"]["best_fit"]
        bf_decisions = self.val_bf_res["all_decisions"] if on_validation else self.train_bf_res["all_decisions"]

        try:
            eval_res = self.simulator.evaluate_streams(streams, candidate_fn, strict_errors=True)
            score = eval_res["mean_excess_ratio"]
            cand_decisions = eval_res["all_decisions"]

            # Compute decision disagreement rate vs Best-Fit
            total_items = 0
            disagreements = 0
            for s_idx in range(len(streams)):
                bf_s = bf_decisions[s_idx]
                cd_s = cand_decisions[s_idx]
                for d_idx in range(min(len(bf_s), len(cd_s))):
                    total_items += 1
                    if bf_s[d_idx] != cd_s[d_idx]:
                        disagreements += 1

            disagreement_rate = (disagreements / total_items) if total_items > 0 else 0.0
            rel_gap = (score - baseline_bf) / baseline_bf

            return {
                "is_valid": True,
                "error": None,
                "score": round(score, 6),
                "relative_gap": round(rel_gap, 6),
                "beats_baseline": bool(score < baseline_bf - 1e-6),
                "stream_scores": [round(x, 6) for x in eval_res["stream_excess_ratios"]],
                "runtime_ms": round((time.time() - t0) * 1000, 2),
                "decision_disagreement_rate": round(disagreement_rate, 4),
                "total_bins": eval_res["total_bins"]
            }
        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Runtime execution error: {sanitize_exception_name(e)}",
                "score": 1.0,
                "relative_gap": 1.0,
                "beats_baseline": False,
                "runtime_ms": round((time.time() - t0) * 1000, 2),
                "decision_disagreement_rate": None,
                "all_decisions": []
            }
