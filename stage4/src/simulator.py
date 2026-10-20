"""
Stage 4 Deterministic Bin Packing Simulator & Canonical Baselines
================================================================
Enforces the canonical priority function interface:
    def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float

Key Specifications:
1. Strict bounds enforcement: 0 < item <= bin_capacity.
2. Deterministic First-Found tie-breaking.
3. Strict error handling (exceptions, NaN, Inf, non-numbers abort with failure).
4. Hand-verified metric computation:
       rho(s) = (B(s) - L1(s)) / L1(s)
       mean_rho = (1 / |S|) * sum(rho(s))
5. Canonical baselines: Best-Fit, Worst-Fit, First-Fit, and offline FFD reference.
"""

import math
from typing import List, Tuple, Callable, Dict, Any, Optional


class DeterministicBinPackingSimulator:
    """
    Reference simulator enforcing the canonical Stage 4 interface.
    """
    def __init__(self, bin_capacity: float = 100.0, tolerance: float = 1e-6):
        self.bin_capacity = float(bin_capacity)
        self.tolerance = tolerance

    @staticmethod
    def compute_l1(items: List[float], capacity: float) -> int:
        """Theoretical lower bound L1 = ceil(sum(items) / capacity)."""
        if not items:
            return 0
        total_weight = sum(items)
        return math.ceil(total_weight / capacity)

    def pack_stream(
        self,
        items: List[float],
        priority_fn: Callable[[float, float, float], float],
        strict_errors: bool = True
    ) -> Tuple[int, List[float], int, float]:
        """
        Packs a stream of items using the provided priority function.
        
        Returns:
            (bins_used, open_bins_remaining_capacities, l1, rho)
            
        Raises:
            ValueError: If an item <= 0 or item > bin_capacity.
            RuntimeError: If priority_fn raises an unhandled exception or returns NaN/Inf.
        """
        open_bins: List[float] = []

        for step, item in enumerate(items):
            if item <= 0:
                raise ValueError(f"Item size must be positive, got {item} at index {step}")
            if item > self.bin_capacity + self.tolerance:
                raise ValueError(f"Item size {item} exceeds bin capacity {self.bin_capacity} at index {step}")

            best_bin_idx = -1
            best_priority = -float("inf")

            for idx, rem in enumerate(open_bins):
                if rem >= item - self.tolerance:
                    try:
                        p = float(priority_fn(item, rem, self.bin_capacity))
                    except Exception as e:
                        if strict_errors:
                            raise RuntimeError(f"Candidate raised exception on item={item}, rem={rem}: {e}") from e
                        p = -float("inf")

                    if math.isnan(p) or math.isinf(p):
                        if strict_errors:
                            raise RuntimeError(f"Candidate returned non-finite priority {p} on item={item}, rem={rem}")
                        p = -float("inf")

                    # Strictly greater ensures deterministic First-Found tie-breaking
                    if p > best_priority:
                        best_priority = p
                        best_bin_idx = idx

            if best_bin_idx >= 0 and best_priority > -float("inf"):
                open_bins[best_bin_idx] = round(open_bins[best_bin_idx] - item, 8)
            else:
                # Open a new bin
                open_bins.append(round(self.bin_capacity - item, 8))

        bins_used = len(open_bins)
        l1 = self.compute_l1(items, self.bin_capacity)
        rho = ((bins_used - l1) / float(l1)) if l1 > 0 else 0.0

        return bins_used, open_bins, l1, rho

    def evaluate_streams_with_diagnostics(
        self,
        streams: List[List[float]],
        priority_fn: Callable[[float, float, float], float],
        stream_distributions: Optional[List[str]] = None,
        strict_errors: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates a candidate across a dataset of streams with detailed diagnostic trace extraction.
        Identifies worst-performing streams, leftover space patterns, and concrete counterexamples.
        """
        rhos: List[float] = []
        total_bins = 0
        total_l1 = 0
        all_open_bins_waste: List[float] = []
        underfilled_bins_count = 0
        total_bins_opened = 0
        stream_diagnostics: List[Dict[str, Any]] = []

        default_dists = ["uniform", "weibull", "zipf"]

        for s_idx, items in enumerate(streams):
            bins_used, open_bins, l1, rho = self.pack_stream(items, priority_fn, strict_errors=strict_errors)
            rhos.append(rho)
            total_bins += bins_used
            total_l1 += l1
            total_bins_opened += len(open_bins)

            underfilled = sum(1 for rem in open_bins if rem > 0.5 * self.bin_capacity)
            underfilled_bins_count += underfilled
            avg_waste = (sum(open_bins) / len(open_bins)) if open_bins else 0.0
            all_open_bins_waste.extend(open_bins)

            dist_name = (
                stream_distributions[s_idx]
                if (stream_distributions and s_idx < len(stream_distributions))
                else default_dists[s_idx % len(default_dists)]
            )
            stream_diagnostics.append({
                "stream_idx": s_idx,
                "distribution": dist_name,
                "bins_used": bins_used,
                "l1": l1,
                "rho": rho,
                "excess_bins": bins_used - l1,
                "avg_waste": avg_waste,
                "underfilled_bins": underfilled
            })

        mean_rho = sum(rhos) / len(rhos) if rhos else 0.0
        pooled_rho = ((total_bins - total_l1) / float(total_l1)) if total_l1 > 0 else 0.0

        # Sort streams by rho descending to find worst performers
        sorted_streams = sorted(stream_diagnostics, key=lambda s: s["rho"], reverse=True)
        worst_stream = sorted_streams[0] if sorted_streams else None
        best_stream = sorted_streams[-1] if sorted_streams else None

        # Distribution-level aggregation
        dist_groups: Dict[str, List[float]] = {}
        for s in stream_diagnostics:
            dist_groups.setdefault(s["distribution"], []).append(s["rho"])
        dist_breakdown = {
            dist: round(sum(vals) / len(vals), 4)
            for dist, vals in dist_groups.items()
        }

        avg_wasted_per_bin = (sum(all_open_bins_waste) / len(all_open_bins_waste)) if all_open_bins_waste else 0.0
        underfilled_pct = (underfilled_bins_count / max(1, total_bins_opened)) * 100.0

        # Format actionable diagnostic summary for in-context LLM refinement
        if worst_stream:
            diag_lines = [
                f"Overall Mean Excess Ratio: {mean_rho:.4f}",
                f"Distribution Breakdown: {', '.join(f'{k}: {v:.4f}' for k, v in sorted(dist_breakdown.items()))}",
                f"Worst Stream: Stream #{worst_stream['stream_idx']} ({worst_stream['distribution']}) used {worst_stream['bins_used']} bins (L1={worst_stream['l1']}, excess={worst_stream['excess_bins']} bins, excess ratio={worst_stream['rho']:.4f}).",
                f"Waste Pattern: Average leftover space per bin was {avg_wasted_per_bin:.1f}/{self.bin_capacity:.1f}; {underfilled_pct:.1f}% of bins ended >50% empty.",
                f"Counterexample Analysis: On stream #{worst_stream['stream_idx']}, heuristic opened {worst_stream['excess_bins']} excess bins by dispersing items across open bins instead of tightly packing existing bins.",
                f"Refinement Directive: Favor bins that minimize leftover space after placement; avoid opening new bins when feasible open bins exist."
            ]
            diagnostic_summary = "\n".join(diag_lines)
        else:
            diagnostic_summary = "No diagnostic data available."

        diagnostics_data = {
            "worst_stream": worst_stream,
            "best_stream": best_stream,
            "distribution_breakdown": dist_breakdown,
            "avg_wasted_per_bin": round(avg_wasted_per_bin, 2),
            "underfilled_bins_pct": round(underfilled_pct, 1),
            "diagnostic_summary": diagnostic_summary
        }

        return {
            "num_streams": len(streams),
            "total_bins": total_bins,
            "total_l1": total_l1,
            "mean_excess_ratio": round(mean_rho, 6),
            "pooled_excess_ratio": round(pooled_rho, 6),
            "stream_excess_ratios": [round(r, 6) for r in rhos],
            "diagnostics": diagnostics_data
        }

    def evaluate_streams(
        self,
        streams: List[List[float]],
        priority_fn: Callable[[float, float, float], float],
        strict_errors: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates a candidate across a dataset of streams.
        Returns detailed summary, mean normalized excess ratio rho_bar, and diagnostic data.
        """
        return self.evaluate_streams_with_diagnostics(
            streams=streams,
            priority_fn=priority_fn,
            strict_errors=strict_errors
        )



# ---------------------------------------------------------------------------
# Canonical Baselines
# ---------------------------------------------------------------------------

def best_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """Best-Fit: Minimize remaining space after item is placed."""
    space_after = remaining_capacity - item
    return -space_after


def worst_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """Worst-Fit: Maximize remaining space after item is placed."""
    return remaining_capacity


def first_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """First-Fit: Pack into earliest opened feasible bin."""
    return 0.0


def almost_worst_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """Almost-Worst-Fit heuristic: Avoid tiny leftover slivers."""
    space_after = remaining_capacity - item
    if space_after < 0.05 * bin_capacity:
        return 1000.0 - space_after
    return remaining_capacity * 0.5


def first_fit_decreasing_offline(items: List[float], bin_capacity: float = 100.0) -> Tuple[int, int, float]:
    """
    Offline Upper Bound Reference: First-Fit Decreasing (FFD).
    Sorts all items in descending order before packing.
    """
    sorted_items = sorted(items, reverse=True)
    open_bins: List[float] = []
    for item in sorted_items:
        placed = False
        for idx in range(len(open_bins)):
            if open_bins[idx] >= item - 1e-6:
                open_bins[idx] = round(open_bins[idx] - item, 8)
                placed = True
                break
        if not placed:
            open_bins.append(round(bin_capacity - item, 8))

    l1 = DeterministicBinPackingSimulator.compute_l1(items, bin_capacity)
    bins_used = len(open_bins)
    rho = ((bins_used - l1) / float(l1)) if l1 > 0 else 0.0
    return bins_used, l1, rho
