"""
Discovery Kernel v0.1: Method Adapter
=====================================
Defines the minimal common interface for candidate solvers, heuristics,
and generated algorithms. Isolates method-specific invocation logic and
records structured execution metadata.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Dict, Any, List, Optional, Callable, Tuple


class ExecutionStatus(str, Enum):
    """Execution status classification."""
    SUCCESS = "SUCCESS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EXCEPTION = "EXCEPTION"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"


@dataclass
class MethodMetadata:
    """Provenance and specification metadata for a candidate method."""
    method_id: str
    version: str
    description: str
    author: str = "Amaura Labs"
    parameters: Dict[str, Any] = field(default_factory=dict)
    source_code: Optional[str] = None


@dataclass
class MethodExecutionResult:
    """Outcome of a single instance execution."""
    method_id: str
    method_version: str
    instance_id: str
    status: ExecutionStatus
    raw_output: Any = None
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    runtime_ms: float = 0.0
    error_message: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class MethodAdapter(ABC):
    """
    Abstract Base Class for method adapters.
    Encapsulates invocation logic so diverse algorithm types present a uniform interface.
    """
    def __init__(self, metadata: MethodMetadata):
        self.metadata = metadata

    @property
    def method_id(self) -> str:
        return self.metadata.method_id

    @property
    def version(self) -> str:
        return self.metadata.version

    @abstractmethod
    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executes the algorithm on a single problem instance.
        Must return the raw solution object (e.g. list of job indices, bin assignments).
        """
        pass


# =========================================================================
# Concrete PFSP Method Adapters (Reusing Existing Verified Implementations)
# =========================================================================

class PFSPNEHAdapter(MethodAdapter):
    """Wraps classical Nawaz-Enscore-Ham (NEH 1983) constructive heuristic."""
    def __init__(self, version: str = "1.0.0"):
        super().__init__(MethodMetadata(
            method_id="neh_classical",
            version=version,
            description="Classical Nawaz-Enscore-Ham (1983) constructive makespan heuristic",
            author="Nawaz, Enscore, Ham"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        from benchmark_v1.src.domains.pfsp_full_algorithm import neh_solve
        times = instance["times"] if isinstance(instance, dict) else instance
        return neh_solve(times)


class PFSPNEHLSAdapter(MethodAdapter):
    """Wraps NEH followed by single-pass insertion local search."""
    def __init__(self, version: str = "1.0.0"):
        super().__init__(MethodMetadata(
            method_id="neh_ls_insertion",
            version=version,
            description="NEH constructive heuristic followed by single-pass insertion local search",
            author="Amaura Benchmark V1"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        from benchmark_v1.src.domains.pfsp_full_algorithm import neh_ls_solve
        times = instance["times"] if isinstance(instance, dict) else instance
        return neh_ls_solve(times)


class PFSPSPTAdapter(MethodAdapter):
    """Shortest Processing Time (SPT) naive heuristic: sorts jobs by total processing time ascending."""
    def __init__(self, version: str = "1.0.0"):
        super().__init__(MethodMetadata(
            method_id="spt_ascending",
            version=version,
            description="Naive heuristic sorting jobs by sum of machine processing times ascending",
            author="Amaura Benchmark V1"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        times = instance["times"] if isinstance(instance, dict) else instance
        n = len(times)
        return sorted(range(n), key=lambda j: sum(times[j]))


class PFSPFunctionAdapter(MethodAdapter):
    """Wraps an arbitrary Python callable with the signature solve(times) -> list[int]."""
    def __init__(
        self,
        method_id: str,
        solve_func: Callable[[List[List[int]]], List[int]],
        description: str = "Custom PFSP solver function",
        version: str = "1.0.0",
        source_code: Optional[str] = None
    ):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version=version,
            description=description,
            source_code=source_code
        ))
        self.solve_func = solve_func

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        times = instance["times"] if isinstance(instance, dict) else instance
        return self.solve_func(times)


# =========================================================================
# Test Doubles for Focused Unit and Fault-Injection Testing
# =========================================================================

class InvalidPermutationAdapter(MethodAdapter):
    """Test double that produces a malformed permutation (duplicate elements)."""
    def __init__(self, method_id: str = "test_invalid_output"):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version="0.0.1-test",
            description="Deliberately invalid test double returning duplicate job IDs"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        times = instance["times"] if isinstance(instance, dict) else instance
        n = len(times)
        # Duplicate 0 and omit 1
        return [0] * n


class HangingAdapter(MethodAdapter):
    """Test double that deliberately loops or sleeps past the timeout."""
    def __init__(self, method_id: str = "test_timeout_worker", sleep_sec: float = 30.0):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version="0.0.1-test",
            description="Deliberately non-terminating test double"
        ))
        self.sleep_sec = sleep_sec

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        time.sleep(self.sleep_sec)
        return [0]


class ExceptionAdapter(MethodAdapter):
    """Test double that deliberately raises an unhandled exception."""
    def __init__(self, method_id: str = "test_exception_worker"):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version="0.0.1-test",
            description="Deliberately failing test double raising RuntimeError"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        raise RuntimeError("Simulated internal worker crash for testing")


# =========================================================================
# Concrete Online 1D Bin Packing Method Adapters & Validation
# =========================================================================

def pack_items_with_priority(
    items: List[float],
    priority_fn: Callable[[float, float, float], float],
    bin_capacity: float = 100.0,
    tolerance: float = 1e-6
) -> List[int]:
    """
    Simulates online 1D bin packing using a priority function.
    Returns list of assigned bin indices for each item in arrival order.
    """
    open_bins: List[float] = []
    assignments: List[int] = []

    for item in items:
        best_bin_idx = -1
        best_priority = -float("inf")

        for idx, rem in enumerate(open_bins):
            if rem >= item - tolerance:
                p = float(priority_fn(item, rem, bin_capacity))
                if p > best_priority:
                    best_priority = p
                    best_bin_idx = idx

        if best_bin_idx >= 0 and best_priority > -float("inf"):
            assignments.append(best_bin_idx)
            open_bins[best_bin_idx] = round(open_bins[best_bin_idx] - item, 8)
        else:
            new_bin_idx = len(open_bins)
            assignments.append(new_bin_idx)
            open_bins.append(round(bin_capacity - item, 8))

    return assignments


def validate_bin_packing_solution(
    instance: Any,
    solution: Any,
    bin_capacity: float = 100.0,
    tolerance: float = 1e-6
) -> Tuple[bool, Optional[str]]:
    """
    Strictly validates a bin-packing solution:
    1. Must be a list or tuple of integer bin assignments.
    2. Length must exactly match number of items (every item assigned exactly once).
    3. All bin indices must be non-negative integers.
    4. Total weight in each bin cannot exceed bin_capacity.
    5. Produces valid bin count.
    """
    items = instance.get("items") if isinstance(instance, dict) else instance
    if not isinstance(items, (list, tuple)):
        return False, f"Invalid instance items type: {type(items).__name__}"

    capacity = float(instance.get("bin_capacity", bin_capacity)) if isinstance(instance, dict) else float(bin_capacity)

    assignments = solution
    if isinstance(solution, dict) and "bin_assignments" in solution:
        assignments = solution["bin_assignments"]

    if not isinstance(assignments, (list, tuple)):
        return False, f"Solution must be a list of bin assignments, got {type(assignments).__name__}"

    n_items = len(items)
    if len(assignments) != n_items:
        return False, f"Assignment count {len(assignments)} does not match item count {n_items}"

    bin_weights: Dict[int, float] = {}
    for i, b in enumerate(assignments):
        if isinstance(b, bool) or not isinstance(b, int):
            return False, f"Bin assignment for item {i} is not an integer: {b} (type {type(b).__name__})"
        if b < 0:
            return False, f"Bin index {b} for item {i} is negative"

        item_weight = float(items[i])
        bin_weights[b] = bin_weights.get(b, 0.0) + item_weight

    # Check capacity for each bin
    for b, total_w in bin_weights.items():
        if total_w > capacity + tolerance:
            return False, f"Bin {b} capacity exceeded: total weight {total_w:.4f} > capacity {capacity:.4f}"

    return True, None


def calc_bin_packing_excess_ratio(
    instance: Any,
    solution: Any,
    bin_capacity: float = 100.0
) -> float:
    """Computes normalized excess ratio rho = (bins_used - L1) / L1."""
    items = instance.get("items") if isinstance(instance, dict) else instance
    capacity = float(instance.get("bin_capacity", bin_capacity)) if isinstance(instance, dict) else float(bin_capacity)

    assignments = solution.get("bin_assignments", solution) if isinstance(solution, dict) else solution
    bins_used = len(set(assignments))
    total_weight = sum(items)
    l1 = math.ceil(total_weight / capacity) if capacity > 0 else 1
    return ((bins_used - l1) / float(l1)) if l1 > 0 else 0.0


class BinPackingBestFitAdapter(MethodAdapter):
    """Online 1D Bin Packing with Best-Fit priority heuristic."""
    def __init__(self, version: str = "1.0.0", bin_capacity: float = 100.0):
        super().__init__(MethodMetadata(
            method_id="best_fit",
            version=version,
            description="Online Best-Fit heuristic minimizing leftover space",
            author="Stage 4 Simulator"
        ))
        self.bin_capacity = bin_capacity

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        from stage4.src.simulator import best_fit_priority
        items = instance["items"] if isinstance(instance, dict) else instance
        cap = float(instance.get("bin_capacity", self.bin_capacity)) if isinstance(instance, dict) else self.bin_capacity
        return pack_items_with_priority(items, best_fit_priority, bin_capacity=cap)


class BinPackingFirstFitAdapter(MethodAdapter):
    """Online 1D Bin Packing with First-Fit priority heuristic."""
    def __init__(self, version: str = "1.0.0", bin_capacity: float = 100.0):
        super().__init__(MethodMetadata(
            method_id="first_fit",
            version=version,
            description="Online First-Fit heuristic placing item into first feasible open bin",
            author="Stage 4 Simulator"
        ))
        self.bin_capacity = bin_capacity

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        from stage4.src.simulator import first_fit_priority
        items = instance["items"] if isinstance(instance, dict) else instance
        cap = float(instance.get("bin_capacity", self.bin_capacity)) if isinstance(instance, dict) else self.bin_capacity
        return pack_items_with_priority(items, first_fit_priority, bin_capacity=cap)


class BinPackingWorstFitAdapter(MethodAdapter):
    """Online 1D Bin Packing with Worst-Fit priority heuristic."""
    def __init__(self, version: str = "1.0.0", bin_capacity: float = 100.0):
        super().__init__(MethodMetadata(
            method_id="worst_fit",
            version=version,
            description="Online Worst-Fit heuristic maximizing leftover space",
            author="Stage 4 Simulator"
        ))
        self.bin_capacity = bin_capacity

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        from stage4.src.simulator import worst_fit_priority
        items = instance["items"] if isinstance(instance, dict) else instance
        cap = float(instance.get("bin_capacity", self.bin_capacity)) if isinstance(instance, dict) else self.bin_capacity
        return pack_items_with_priority(items, worst_fit_priority, bin_capacity=cap)


class BinPackingFunctionAdapter(MethodAdapter):
    """Wraps an arbitrary custom priority function for Bin Packing."""
    def __init__(
        self,
        method_id: str,
        priority_fn: Callable[[float, float, float], float],
        description: str = "Custom priority function for bin packing",
        version: str = "1.0.0",
        bin_capacity: float = 100.0
    ):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version=version,
            description=description
        ))
        self.priority_fn = priority_fn
        self.bin_capacity = bin_capacity

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        items = instance["items"] if isinstance(instance, dict) else instance
        cap = float(instance.get("bin_capacity", self.bin_capacity)) if isinstance(instance, dict) else self.bin_capacity
        return pack_items_with_priority(items, self.priority_fn, bin_capacity=cap)


# =========================================================================
# Fault-Injection Test Doubles for Bin Packing
# =========================================================================

class InvalidCapacityBinPackingAdapter(MethodAdapter):
    """Test double that deliberately packs all items into a single bin, violating capacity."""
    def __init__(self, method_id: str = "fault_overcapacity_worker"):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version="0.0.1-test",
            description="Deliberately invalid test double packing all items into bin 0"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        items = instance["items"] if isinstance(instance, dict) else instance
        # Assign everything to bin 0 -> will exceed capacity 100.0
        return [0] * len(items)


class MissingItemBinPackingAdapter(MethodAdapter):
    """Test double that omits items from assignment (length mismatch)."""
    def __init__(self, method_id: str = "fault_missing_items_worker"):
        super().__init__(MethodMetadata(
            method_id=method_id,
            version="0.0.1-test",
            description="Deliberately invalid test double omitting half the items"
        ))

    def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
        items = instance["items"] if isinstance(instance, dict) else instance
        return [i for i in range(len(items) // 2)]
