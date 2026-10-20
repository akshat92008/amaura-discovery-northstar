"""
Discovery Kernel v0.1: Second-Domain Portability Pilot (Online 1D Bin Packing)
=============================================================================
Demonstrates domain-agnostic portability of Discovery Kernel v0.1:
1. Loads and validates ProblemSpecification for Online 1D Bin Packing against real repository datasets.
2. Evaluates Best-Fit, First-Fit, Worst-Fit, and 2 fault-injection doubles in process isolation.
3. Enforces declarative constraint validation (item coverage, capacity bounding, valid bin counts).
4. Selects Best-Fit as champion on development split and freezes selection.
5. Evaluates frozen champion vs First-Fit baseline on holdout benchmark.
6. Reconstructs and cryptographically verifies the entire decision from machine-readable records.
"""

import json
import math
import os
import sys
import time
from typing import Dict, Any

# Ensure repository root is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from discovery_kernel.problem_spec import (
    ObjectiveDirection,
    DatasetReference,
    ResourceLimits,
    ConstraintRule,
    BaselineMethod,
    ProblemSpecification,
    compute_file_sha256
)
from discovery_kernel.method_adapter import (
    BinPackingBestFitAdapter,
    BinPackingFirstFitAdapter,
    BinPackingWorstFitAdapter,
    InvalidCapacityBinPackingAdapter,
    MissingItemBinPackingAdapter,
    HangingAdapter,
    validate_bin_packing_solution,
    calc_bin_packing_excess_ratio
)
from discovery_kernel.execution import ExecutionSupervisor
from discovery_kernel.evidence_store import EvidenceStore, reconstruct_and_verify_selection
from discovery_kernel.controller import DeterministicController


def run_bin_packing_portability_pilot(
    results_dir: str,
    dev_limit: int = 5,
    eval_limit: int = 5,
    timeout_sec: float = 2.0
) -> Dict[str, Any]:
    """
    Executes the bin packing portability pilot and returns summary metrics.
    """
    dev_path = os.path.join(repo_root, "benchmark_v1", "data", "bin_packing", "train.json")
    eval_path = os.path.join(repo_root, "benchmark_v1", "data", "bin_packing", "test.json")

    dev_sha256 = compute_file_sha256(dev_path)
    eval_sha256 = compute_file_sha256(eval_path)

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_count = len(json.load(f))
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_count = len(json.load(f))

    # 1. Problem Specification
    def _bp_validator(instance, solution):
        return validate_bin_packing_solution(instance, solution, bin_capacity=100.0)

    bp_constraint = ConstraintRule(
        name="bin_packing_validity",
        description="Every item assigned exactly once; total weight in any bin <= 100.0",
        validator=_bp_validator
    )

    spec = ProblemSpecification(
        problem_id="online_1d_bin_packing",
        version="0.1.0-portability",
        objective_metric="excess_ratio",
        objective_direction=ObjectiveDirection.MINIMIZE,
        constraints=[bp_constraint],
        evaluator_name="bin_packing_excess_ratio_evaluator",
        development_dataset=DatasetReference(
            name="development",
            file_path=dev_path,
            sha256=dev_sha256,
            instance_count=dev_count
        ),
        evaluation_dataset=DatasetReference(
            name="evaluation",
            file_path=eval_path,
            sha256=eval_sha256,
            instance_count=eval_count
        ),
        resource_limits=ResourceLimits(
            max_runtime_sec_per_instance=timeout_sec,
            max_total_runtime_sec=60.0,
            max_evaluations=50
        ),
        baselines=[
            BaselineMethod("best_fit", "Best-Fit online heuristic minimizing leftover space"),
            BaselineMethod("first_fit", "First-Fit online heuristic placing in first feasible open bin"),
            BaselineMethod("worst_fit", "Worst-Fit online heuristic maximizing leftover space")
        ],
        experiment_id="EXP_PILOT_DK01_BINPACKING_20261019",
        provenance={
            "description": "Discovery Kernel v0.1 Second-Domain Portability Gate (Bin Packing)",
            "environment": "macOS / Python 3.13"
        }
    )

    # 2. Evidence Store
    store = EvidenceStore(results_dir, spec.experiment_id)

    # 3. Evaluator function
    def bin_packing_evaluator(instance, solution):
        return float(calc_bin_packing_excess_ratio(instance, solution, bin_capacity=100.0))

    # 4. Supervisor & Controller
    supervisor = ExecutionSupervisor(timeout_sec=timeout_sec)
    controller = DeterministicController(
        problem_spec=spec,
        evidence_store=store,
        evaluator_fn=bin_packing_evaluator,
        base_dir=repo_root,
        supervisor=supervisor
    )

    # 5. Method Candidates (3 Canonical Heuristics + 2 Fault Doubles)
    methods = [
        BinPackingBestFitAdapter(),
        BinPackingFirstFitAdapter(),
        BinPackingWorstFitAdapter(),
        InvalidCapacityBinPackingAdapter("fault_overcapacity"),
        MissingItemBinPackingAdapter("fault_missing_items")
    ]

    print("=" * 70)
    print("NORTH BLUESTAR — SECOND-DOMAIN PORTABILITY GATE (BIN PACKING)")
    print("=" * 70)
    print(f"Problem Spec ID:        {spec.problem_id}")
    print(f"Spec SHA-256:           {controller.spec_fingerprint}")
    print(f"Development Instances:  {dev_limit} (from {dev_count} total)")
    print(f"Evaluation Instances:   {eval_limit} (from {eval_count} total)")
    print(f"Declared Methods:       {[m.method_id for m in methods]}")
    print("-" * 70)

    # Phase 1: Development
    print("[PHASE 1] Running development phase...")
    t0_dev = time.perf_counter()
    frozen = controller.run_development_phase(methods, instance_limit=dev_limit)
    elapsed_dev = time.perf_counter() - t0_dev
    print(f"[PHASE 1] Completed in {elapsed_dev:.2f}s.")
    print(f"          Champion Selected: {frozen.champion_method_id} (Dev Score: {frozen.champion_dev_score:.6f})")
    print(f"          Frozen At:         {frozen.selection_timestamp}")
    print("          Rankings:")
    for r in frozen.dev_rankings:
        status_str = "VALID" if r["is_fully_valid"] else f"INVALID (fails: {r['timeout_count']} timeout, {r['exception_count']} exc)"
        print(f"            - {r['method_id']:<26} Mean Excess Ratio: {str(r['mean_score']):<10} Status: {status_str}")

    # Phase 2: Final Evaluation
    print("-" * 70)
    print("[PHASE 2] Unsealing holdout benchmark for frozen selection...")
    champ_adapter = BinPackingBestFitAdapter()
    baseline_adapter = BinPackingFirstFitAdapter()

    t0_eval = time.perf_counter()
    final_report = controller.run_final_evaluation_phase(
        frozen_selection=frozen,
        champion_adapter=champ_adapter,
        baseline_adapters=[baseline_adapter],
        instance_limit=eval_limit
    )
    elapsed_eval = time.perf_counter() - t0_eval
    print(f"[PHASE 2] Completed in {elapsed_eval:.2f}s.")
    print(f"          Champion Holdout Score: {final_report.champion_eval_score:.6f}")
    print(f"          Baseline Holdout Score: {final_report.baseline_eval_scores.get('first_fit'):.6f}")
    print(f"          Matched Relative Gap:   {final_report.matched_relative_gap * 100:+.4f}%")
    print(f"          Beats Baseline:         {final_report.beats_baseline}")
    print(f"          All Instances Valid:    {final_report.all_instances_valid} ({final_report.valid_instance_count}/{final_report.eval_instance_count})")

    # Reconstruction & Audit
    print("-" * 70)
    print("[AUDIT] Reconstructing experiment from raw records...")
    reconstruction = reconstruct_and_verify_selection(results_dir)
    print(f"          Reconstruction Verified: {reconstruction['verified']}")
    print(f"          Recorded Champion:       {reconstruction['recorded_champion']}")
    print(f"          Recomputed Champion:     {reconstruction['recomputed_champion']}")

    manifest_path = os.path.join(results_dir, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    print(f"          Generated Files:         {list(manifest['files'].keys())}")
    print("=" * 70)

    return {
        "spec_fingerprint": controller.spec_fingerprint,
        "frozen_selection": frozen,
        "final_report": final_report,
        "reconstruction": reconstruction,
        "manifest": manifest
    }


if __name__ == "__main__":
    out_dir = os.path.join(
        repo_root,
        "discovery_kernel_v01",
        "results",
        "portability_bin_packing_20261019"
    )
    run_bin_packing_portability_pilot(out_dir, dev_limit=5, eval_limit=5, timeout_sec=2.0)
