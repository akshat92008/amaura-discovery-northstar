"""
Bin Packing Problem Domain for Search Strategy Benchmark V1
===========================================================
Online 1D Bin Packing with priority function heuristic.
Skeleton: DeterministicBinPackingSimulator.
Baseline: Best-Fit heuristic.
"""

import json
import math
import os
import time
from typing import Dict, Any, List, Optional

from benchmark_v1.src.domains.base import ProblemDomain, DomainEvaluationResult
from stage3.src.sandbox import check_ast_security, sanitize_and_compile, sanitize_exception_name, SAFE_BUILTINS
from stage4.src.simulator import (
    DeterministicBinPackingSimulator,
    best_fit_priority,
    first_fit_priority,
    worst_fit_priority
)


class BinPackingDomain(ProblemDomain):
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "bin_packing")
        self.data_dir = data_dir
        self.simulator = DeterministicBinPackingSimulator(bin_capacity=100.0)

        # Load datasets
        with open(os.path.join(self.data_dir, "train.json"), "r", encoding="utf-8") as f:
            self.train_data = json.load(f)
        with open(os.path.join(self.data_dir, "test.json"), "r", encoding="utf-8") as f:
            self.test_data = json.load(f)

        self.pilot_val_data = []
        pilot_val_path = os.path.join(self.data_dir, "pilot_validation.json")
        if os.path.exists(pilot_val_path):
            with open(pilot_val_path, "r", encoding="utf-8") as f:
                self.pilot_val_data = json.load(f)

        self.train_streams = [s["items"] for s in self.train_data]
        self.test_streams = [s["items"] for s in self.test_data]
        self.pilot_val_streams = [s["items"] for s in self.pilot_val_data] if self.pilot_val_data else self.test_streams

        # Compute baseline scores
        self._baselines = {
            "train": self._compute_baselines(self.train_streams),
            "test": self._compute_baselines(self.test_streams),
            "pilot_val": self._compute_baselines(self.pilot_val_streams)
        }
        self._train_bf_rhos = self.simulator.evaluate_streams(self.train_streams, best_fit_priority).get("stream_excess_ratios", [])
        self._test_bf_rhos = self.simulator.evaluate_streams(self.test_streams, best_fit_priority).get("stream_excess_ratios", [])
        self._pilot_val_bf_rhos = self.simulator.evaluate_streams(self.pilot_val_streams, best_fit_priority).get("stream_excess_ratios", [])

    def _compute_baselines(self, streams: List[List[float]]) -> Dict[str, float]:
        bf_res = self.simulator.evaluate_streams(streams, best_fit_priority)
        ff_res = self.simulator.evaluate_streams(streams, first_fit_priority)
        wf_res = self.simulator.evaluate_streams(streams, worst_fit_priority)
        return {
            "best_fit": bf_res["mean_excess_ratio"],
            "first_fit": ff_res["mean_excess_ratio"],
            "worst_fit": wf_res["mean_excess_ratio"]
        }

    @property
    def name(self) -> str:
        return "bin_packing"

    @property
    def function_name(self) -> str:
        return "priority"

    @property
    def function_signature(self) -> str:
        return (
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    \"\"\"Assigns priority score to placing item into a bin. Higher priority is chosen first.\"\"\""
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert algorithm designer specializing in online combinatorial optimization.\n"
            "Keep internal reasoning concise (under 100 words). Immediately produce the complete python function.\n"
            "Your task is to design an online 1D bin packing priority heuristic in pure Python.\n\n"
            "Interface:\n"
            "```python\n"
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "```\n"
            "Rules:\n"
            "1. Output higher priority for bins where placing the item produces better overall packing.\n"
            "2. Objective is to minimize the normalized excess ratio rho = (bins_used - L1) / L1.\n"
            "3. Allowed libraries: `math` only.\n"
            "4. Return ONLY valid Python inside a ```python ``` markdown block."
        )

    @property
    def canonical_seeds(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "best_fit",
                "code": (
                    "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                    "    # Best Fit: minimize leftover space after placement\n"
                    "    return -(remaining_capacity - item)\n"
                ),
                "description": "Places item into the feasible open bin with least remaining space."
            },
            {
                "name": "worst_fit",
                "code": (
                    "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                    "    # Worst Fit: maximize leftover space after placement\n"
                    "    return remaining_capacity - item\n"
                ),
                "description": "Places item into the feasible open bin with most remaining space."
            },
            {
                "name": "first_fit",
                "code": (
                    "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                    "    # First Fit: equal priority across all feasible open bins\n"
                    "    return 0.0\n"
                ),
                "description": "Places item into the first feasible open bin encountered."
            },
            {
                "name": "almost_worst_fit",
                "code": (
                    "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                    "    # Almost Worst Fit\n"
                    "    rem = remaining_capacity - item\n"
                    "    return rem if rem < 0.8 * bin_capacity else -rem\n"
                ),
                "description": "Balances large leftover space with avoiding near-empty bins."
            }
        ]

    def get_baseline_scores(self, split: str = "train") -> Dict[str, float]:
        return self._baselines.get(split, self._baselines["train"])

    def compute_relative_gap(self, raw_score: float, split: str = "train") -> float:
        bf_score = self.get_baseline_scores(split)["best_fit"]
        if bf_score <= 0.0:
            return 0.0
        # Relative gap vs Best-Fit: (score - BF) / BF
        return round((raw_score - bf_score) / bf_score, 6)

    def evaluate(self, code: str, split: str = "train") -> DomainEvaluationResult:
        if split == "train":
            streams = self.train_streams
        elif split == "pilot_val":
            streams = self.pilot_val_streams
        else:
            streams = self.test_streams
        t0 = time.perf_counter()

        # AST Safety Check
        is_safe, error_msg = check_ast_security(code, required_func="priority")
        if not is_safe:
            penalty_score = 1.0
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=penalty_score,
                avg_score=penalty_score,
                per_instance_scores=[penalty_score] * len(streams),
                relative_gap=self.compute_relative_gap(penalty_score, split),
                beats_baseline=False,
                error_message=error_msg,
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        # Compile and execute safely in-process
        exec_globals = {"__builtins__": SAFE_BUILTINS, "math": __import__("math")}
        try:
            compiled = sanitize_and_compile(code, "<candidate_binpacking_priority>")
            exec(compiled, exec_globals)
            priority_fn = exec_globals["priority"]
            sim_res = self.simulator.evaluate_streams(streams, priority_fn)
        except Exception as e:
            penalty_score = 1.0
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=penalty_score,
                avg_score=penalty_score,
                per_instance_scores=[penalty_score] * len(streams),
                relative_gap=self.compute_relative_gap(penalty_score, split),
                beats_baseline=False,
                error_message=f"Execution error: {sanitize_exception_name(e)}",
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        total_runtime_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        mean_rho = sim_res["mean_excess_ratio"]
        stream_rhos = sim_res.get("stream_excess_ratios", [])
        rel_gap = self.compute_relative_gap(mean_rho, split)
        bf_score = self.get_baseline_scores(split)["best_fit"]
        beats_bf = bool(mean_rho < bf_score - 1e-6)

        # Build diagnostics for Arm E
        worst_stream_idx = -1
        max_excess = -float("inf")
        if split == "train":
            bf_rhos = self._train_bf_rhos
        elif split == "pilot_val":
            bf_rhos = self._pilot_val_bf_rhos
        else:
            bf_rhos = self._test_bf_rhos
        for idx in range(len(stream_rhos)):
            diff = stream_rhos[idx] - bf_rhos[idx]
            if diff > max_excess:
                max_excess = diff
                worst_stream_idx = idx

        diagnostics = {
            "mean_excess_ratio": round(mean_rho, 6),
            "best_fit_mean": round(bf_score, 6),
            "stream_excess_ratios": stream_rhos,
            "worst_instance_idx": worst_stream_idx,
            "worst_instance_rho": stream_rhos[worst_stream_idx] if worst_stream_idx >= 0 else None,
            "worst_instance_bf": bf_rhos[worst_stream_idx] if worst_stream_idx >= 0 else None,
            "diagnostic_summary": (
                f"Overall Mean Excess Ratio: {mean_rho:.4f} (Best-Fit baseline: {bf_score:.4f}, Gap: {rel_gap * 100:+.2f}%).\n"
                f"Worst Stream #{worst_stream_idx}: Produced excess ratio {stream_rhos[worst_stream_idx]:.4f} vs Best-Fit's {bf_rhos[worst_stream_idx]:.4f} "
                f"(+{stream_rhos[worst_stream_idx] - bf_rhos[worst_stream_idx]:.4f} excess).\n"
                f"Failure Analysis: Loose priority for large remaining capacities leaves underfilled bins.\n"
                f"Refinement Directive: Tighten remaining space threshold to strongly penalize leftover space."
            )
        }

        return DomainEvaluationResult(
            is_valid=True,
            raw_score=round(mean_rho, 6),
            avg_score=round(mean_rho, 6),
            per_instance_scores=stream_rhos,
            relative_gap=rel_gap,
            beats_baseline=beats_bf,
            error_message=None,
            diagnostics=diagnostics,
            runtime_ms=total_runtime_ms
        )
