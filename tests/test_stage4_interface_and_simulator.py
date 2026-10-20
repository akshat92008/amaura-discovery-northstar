"""
Stage 4 Interface & Simulator Unit Tests
========================================
Validates the canonical priority function interface:
    def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float

Tests:
1. Feasible placements and capacity updates.
2. No feasible placement triggers opening a new bin.
3. Exact fits (remaining_capacity == item).
4. Empty bin handling (remaining_capacity == bin_capacity).
5. Full bin handling (remaining_capacity == 0).
6. Deterministic tie-breaking (First-Found among identical priority scores).
7. Classical heuristics: Best-Fit, Worst-Fit, First-Fit.
8. Robust error handling (exceptions, NaN, non-numeric outputs) without silent Best-Fit masking.
"""

import math
import pytest
from typing import List, Tuple, Callable, Any, Optional


class DeterministicBinPackingSimulator:
    """
    Reference simulator enforcing the canonical Stage 4 interface.
    
    Interface:
        priority(item: float, remaining_capacity: float, bin_capacity: float) -> float
        
    Arguments:
        item: Size of incoming item (0 < item <= bin_capacity).
        remaining_capacity: Available capacity in the candidate open bin (0 <= rem <= bin_capacity).
        bin_capacity: Fixed maximum capacity of every bin (e.g. 100.0).
        
    Tie-breaking:
        Strictly First-Found. If multiple feasible bins yield the identical maximum
        priority score, the lowest index (earliest opened) bin is chosen.
        
    New bin trigger:
        Opened if no open bin has remaining_capacity >= item, or if priority returns -inf.
    """
    def __init__(self, bin_capacity: float = 100.0, tolerance: float = 1e-6):
        self.bin_capacity = float(bin_capacity)
        self.tolerance = tolerance

    def pack_stream(
        self,
        items: List[float],
        priority_fn: Callable[[float, float, float], float],
        strict_errors: bool = True
    ) -> Tuple[int, List[float], int]:
        """
        Packs a stream of items.
        
        Returns:
            (bins_used, open_bins_remaining_capacities, lower_bound_L1)
            
        Raises:
            ValueError if item <= 0 or item > bin_capacity.
            RuntimeError if priority_fn raises an unhandled exception or returns NaN (when strict_errors=True).
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

                    if math.isnan(p):
                        if strict_errors:
                            raise RuntimeError(f"Candidate returned NaN on item={item}, rem={rem}")
                        p = -float("inf")

                    # Strictly greater ensures deterministic First-Found tie breaking
                    if p > best_priority:
                        best_priority = p
                        best_bin_idx = idx

            if best_bin_idx >= 0 and best_priority > -float("inf"):
                open_bins[best_bin_idx] = round(open_bins[best_bin_idx] - item, 8)
            else:
                # Open a new bin with capacity remaining = bin_capacity - item
                open_bins.append(round(self.bin_capacity - item, 8))

        total_weight = sum(items)
        l1 = math.ceil(total_weight / self.bin_capacity) if items else 0
        return len(open_bins), open_bins, l1


# ---------------------------------------------------------------------------
# Canonical Baseline Heuristics
# ---------------------------------------------------------------------------

def best_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """Best-Fit: Minimize leftover space after placement."""
    space_after = remaining_capacity - item
    return -space_after


def worst_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """Worst-Fit: Maximize leftover space after placement."""
    space_after = remaining_capacity - item
    return space_after


def first_fit_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    """First-Fit: All feasible bins return 0.0; tie-breaker picks first open bin."""
    return 0.0


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

def test_canonical_signature_arguments():
    """Verify argument order and semantics."""
    seen_args = []
    def spy_priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
        seen_args.append((item, remaining_capacity, bin_capacity))
        return -remaining_capacity

    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    # First item 40 opens bin 1 (rem=60)
    # Second item 30 evaluates against bin 1 (item=30, rem=60, cap=100)
    bins_used, open_bins, l1 = sim.pack_stream([40.0, 30.0], spy_priority)
    
    assert bins_used == 1
    assert len(seen_args) == 1
    item_arg, rem_arg, cap_arg = seen_args[0]
    assert item_arg == 30.0
    assert rem_arg == 60.0
    assert cap_arg == 100.0
    assert open_bins[0] == 30.0
    assert l1 == 1


def test_feasible_placement_and_capacity_update():
    """Items are packed into feasible bins and remaining capacity decrements correctly."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    bins_used, open_bins, l1 = sim.pack_stream([50.0, 30.0, 15.0], best_fit_priority)
    assert bins_used == 1
    assert open_bins[0] == 5.0
    assert l1 == 1


def test_no_feasible_placement_opens_new_bin():
    """When open bins cannot accommodate the item, a new bin is opened."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    bins_used, open_bins, l1 = sim.pack_stream([60.0, 70.0], best_fit_priority)
    assert bins_used == 2
    assert open_bins == [40.0, 30.0]
    assert l1 == 2  # ceil(130/100) = 2


def test_exact_fit_reaches_zero_remaining():
    """Exact fit results in remaining_capacity == 0.0 (full bin)."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    bins_used, open_bins, l1 = sim.pack_stream([40.0, 60.0], best_fit_priority)
    assert bins_used == 1
    assert open_bins[0] == 0.0
    assert l1 == 1

    # Following item must open a new bin because bin 0 has 0.0 capacity
    bins_used, open_bins, l1 = sim.pack_stream([40.0, 60.0, 10.0], best_fit_priority)
    assert bins_used == 2
    assert open_bins == [0.0, 90.0]
    assert l1 == 2


def test_empty_stream():
    """Empty stream produces 0 bins and lower bound 0."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    bins_used, open_bins, l1 = sim.pack_stream([], best_fit_priority)
    assert bins_used == 0
    assert open_bins == []
    assert l1 == 0


def test_deterministic_tie_breaking_first_found():
    """First-Fit returns 0.0 for all feasible bins; simulator must pick bin 0."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    # Stream: 30 into bin 0 (rem=70), 30 into bin 1 (rem=70) via two new bins
    # Let's force two open bins with identical remaining capacity
    def open_two_bins(item, rem, cap):
        # Always return -inf to force opening new bins
        return -float("inf")

    # Open two bins with 40 each (both have rem=60)
    bins_used, open_bins, _ = sim.pack_stream([40.0, 40.0], open_two_bins)
    assert bins_used == 2
    assert open_bins == [60.0, 60.0]

    # Now pack item 20 with First-Fit (returns 0.0 for both). Must pick bin 0.
    def pack_third(item, rem, cap):
        return 0.0

    # Test via full stream
    bins_used, open_bins, _ = sim.pack_stream([40.0, 40.0, 20.0], first_fit_priority)
    # Item 1 -> bin 0 (rem=60)
    # Item 2: bin 0 has rem=60 (fits, score 0). It goes into bin 0!
    # So stream [40, 40, 20] in First-Fit packs all into bin 0 (40+40+20 = 100)!
    assert bins_used == 1
    assert open_bins == [0.0]


def test_tie_breaking_multiple_open_bins():
    """Verify tie-breaking selects earliest index when multiple bins exist."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    # Pack [60, 60] -> bin 0 (rem=40), bin 1 (rem=40)
    # Next item 10 fits in both (rem=40 >= 10). Both return 0.0 under First-Fit.
    # Must choose bin 0.
    bins_used, open_bins, _ = sim.pack_stream([60.0, 60.0, 10.0], first_fit_priority)
    assert bins_used == 2
    assert open_bins[0] == 30.0  # 40 - 10
    assert open_bins[1] == 40.0  # unchanged


def test_best_fit_vs_worst_fit():
    """Verify Best-Fit picks tighter bin, Worst-Fit picks looser bin."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    # Bins open: bin 0 has rem=30, bin 1 has rem=50.
    # We can create this by packing [70, 50] -> bin 0 (rem=30), bin 1 (rem=50).
    stream = [70.0, 50.0, 20.0]
    
    # Best-Fit: item 20 can go to bin 0 (space_after=10) or bin 1 (space_after=30).
    # Best-Fit picks space_after=10 (bin 0).
    bins_bf, open_bf, _ = sim.pack_stream(stream, best_fit_priority)
    assert bins_bf == 2
    assert open_bf[0] == 10.0  # 30 - 20
    assert open_bf[1] == 50.0  # unchanged

    # Worst-Fit: picks space_after=30 (bin 1).
    bins_wf, open_wf, _ = sim.pack_stream(stream, worst_fit_priority)
    assert bins_wf == 2
    assert open_wf[0] == 30.0  # unchanged
    assert open_wf[1] == 30.0  # 50 - 20


def test_invalid_item_bounds():
    """Negative, zero, or oversized items raise ValueError."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)
    with pytest.raises(ValueError, match="positive"):
        sim.pack_stream([0.0], best_fit_priority)

    with pytest.raises(ValueError, match="positive"):
        sim.pack_stream([-5.0], best_fit_priority)

    with pytest.raises(ValueError, match="exceeds bin capacity"):
        sim.pack_stream([100.5], best_fit_priority)


def test_error_handling_no_silent_best_fit_fallback():
    """Exceptions or NaN inside priority_fn must raise RuntimeError in strict mode."""
    sim = DeterministicBinPackingSimulator(bin_capacity=100.0)

    def buggy_priority(item, rem, cap):
        raise ZeroDivisionError("division by zero")

    with pytest.raises(RuntimeError, match="Candidate raised exception"):
        sim.pack_stream([50.0, 30.0], buggy_priority, strict_errors=True)

    def nan_priority(item, rem, cap):
        return float("nan")

    with pytest.raises(RuntimeError, match="Candidate returned NaN"):
        sim.pack_stream([50.0, 30.0], nan_priority, strict_errors=True)
