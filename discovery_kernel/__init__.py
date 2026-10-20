"""
Discovery Kernel v0.1: Public Interface
=======================================
North BlueStar method-agnostic experimental kernel.
"""

from discovery_kernel.problem_spec import (
    ObjectiveDirection,
    SpecificationValidationError,
    DatasetReference,
    ResourceLimits,
    ConstraintRule,
    BaselineMethod,
    ProblemSpecification,
    compute_file_sha256
)
from discovery_kernel.method_adapter import (
    ExecutionStatus,
    MethodMetadata,
    MethodExecutionResult,
    MethodAdapter,
    PFSPNEHAdapter,
    PFSPNEHLSAdapter,
    PFSPSPTAdapter,
    PFSPFunctionAdapter,
    InvalidPermutationAdapter,
    HangingAdapter,
    ExceptionAdapter,
    pack_items_with_priority,
    validate_bin_packing_solution,
    calc_bin_packing_excess_ratio,
    BinPackingBestFitAdapter,
    BinPackingFirstFitAdapter,
    BinPackingWorstFitAdapter,
    BinPackingFunctionAdapter,
    InvalidCapacityBinPackingAdapter,
    MissingItemBinPackingAdapter
)
from discovery_kernel.execution import (
    EvaluationResult,
    ExecutionSupervisor
)
from discovery_kernel.evidence_store import (
    EvidenceStore,
    reconstruct_and_verify_selection
)
from discovery_kernel.controller import (
    DeterministicController,
    FrozenSelection,
    FinalEvaluationReport,
    ControllerStateError,
    BudgetExhaustedError
)

__all__ = [
    "ObjectiveDirection",
    "SpecificationValidationError",
    "DatasetReference",
    "ResourceLimits",
    "ConstraintRule",
    "BaselineMethod",
    "ProblemSpecification",
    "compute_file_sha256",
    "ExecutionStatus",
    "MethodMetadata",
    "MethodExecutionResult",
    "MethodAdapter",
    "PFSPNEHAdapter",
    "PFSPNEHLSAdapter",
    "PFSPSPTAdapter",
    "PFSPFunctionAdapter",
    "InvalidPermutationAdapter",
    "HangingAdapter",
    "ExceptionAdapter",
    "pack_items_with_priority",
    "validate_bin_packing_solution",
    "calc_bin_packing_excess_ratio",
    "BinPackingBestFitAdapter",
    "BinPackingFirstFitAdapter",
    "BinPackingWorstFitAdapter",
    "BinPackingFunctionAdapter",
    "InvalidCapacityBinPackingAdapter",
    "MissingItemBinPackingAdapter",
    "EvaluationResult",
    "ExecutionSupervisor",
    "EvidenceStore",
    "reconstruct_and_verify_selection",
    "DeterministicController",
    "FrozenSelection",
    "FinalEvaluationReport",
    "ControllerStateError",
    "BudgetExhaustedError"
]
