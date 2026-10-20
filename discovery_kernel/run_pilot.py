"""
Discovery Kernel v0.1: End-to-End Integration Pilot Runner
=========================================================
Executes a bounded, fully isolated end-to-end integration pilot:
1. Loads and validates ProblemSpecification against cryptographic hashes.
2. Instantiates 5 candidate methods (3 real deterministic algorithms + 2 fault-injection test doubles).
3. Executes Phase 1 (Development): evaluates candidates, handles timeouts & invalid outputs, selects champion.
4. Freezes selection immutably before any access to holdout data.
5. Executes Phase 2 (Confirmatory): evaluates frozen champion and baseline on holdout benchmark.
6. Reconstructs and cryptographically verifies the entire decision from machine-readable records.
"""

import json
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
    PFSPNEHAdapter,
    PFSPNEHLSAdapter,
    PFSPSPTAdapter,
    InvalidPermutationAdapter,
    HangingAdapter
)
from discovery_kernel.execution import ExecutionSupervisor
from discovery_kernel.evidence_store import EvidenceStore, reconstruct_and_verify_selection
from discovery_kernel.controller import DeterministicController
from benchmark_v1.src.domains.pfsp_full_algorithm import (
    calc_makespan,
    validate_permutation
)


def run_integration_pilot(
    results_dir: str,
    dev_limit: int = 5,
    eval_limit: int = 5,
    timeout_sec: float = 1.0
) -> Dict[str, Any]:
    """
    Executes the integration pilot and returns summary metrics.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dev_path = os.path.join(repo_root, "benchmark_v1", "data", "pfsp", "train.json")
    eval_path = os.path.join(repo_root, "benchmark_v1", "data", "pfsp", "test.json")

    dev_sha256 = compute_file_sha256(dev_path)
    eval_sha256 = compute_file_sha256(eval_path)

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_count = len(json.load(f))
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_count = len(json.load(f))

    # 1. Problem Specification
    def _perm_validator(instance, solution):
        times = instance["times"] if isinstance(instance, dict) else instance
        return validate_permutation(solution, len(times))

    perm_constraint = ConstraintRule(
        name="permutation_validity",
        description="Solution must be a valid permutation of job indices [0, ..., n-1]",
        validator=_perm_validator
    )

    spec = ProblemSpecification(
        problem_id="pfsp_flowshop_scheduling",
        version="0.1.0-pilot",
        objective_metric="makespan",
        objective_direction=ObjectiveDirection.MINIMIZE,
        constraints=[perm_constraint],
        evaluator_name="taillard_makespan_evaluator",
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
            BaselineMethod("neh_classical", "Nawaz-Enscore-Ham (1983) Heuristic")
        ],
        experiment_id="EXP_PILOT_DK01_20261019",
        provenance={
            "description": "Discovery Kernel v0.1 Integration Pilot",
            "environment": "macOS / Python 3.13"
        }
    )

    # 2. Evidence Store
    store = EvidenceStore(results_dir, spec.experiment_id)

    # 3. Evaluator function
    def pfsp_evaluator(instance, solution):
        times = instance["times"] if isinstance(instance, dict) else instance
        return float(calc_makespan(times, solution))

    # 4. Supervisor & Controller
    supervisor = ExecutionSupervisor(timeout_sec=timeout_sec)
    controller = DeterministicController(
        problem_spec=spec,
        evidence_store=store,
        evaluator_fn=pfsp_evaluator,
        base_dir=repo_root,
        supervisor=supervisor
    )

    # 5. Method Candidates
    methods = [
        PFSPNEHAdapter(),
        PFSPNEHLSAdapter(),
        PFSPSPTAdapter(),
        InvalidPermutationAdapter("fault_invalid_permutation"),
        HangingAdapter("fault_hanging_worker", sleep_sec=10.0)
    ]

    print("=" * 70)
    print("NORTH BLUESTAR — DISCOVERY KERNEL V0.1 INTEGRATION PILOT")
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
    print(f"          Champion Selected: {frozen.champion_method_id} (Dev Score: {frozen.champion_dev_score:.2f})")
    print(f"          Frozen At:         {frozen.selection_timestamp}")
    print("          Rankings:")
    for r in frozen.dev_rankings:
        status_str = "VALID" if r["is_fully_valid"] else f"INVALID (fails: {r['timeout_count']} timeout, {r['exception_count']} exc)"
        print(f"            - {r['method_id']:<28} Mean Score: {str(r['mean_score']):<10} Status: {status_str}")

    # Phase 2: Final Evaluation
    print("-" * 70)
    print("[PHASE 2] Unsealing holdout benchmark for frozen selection...")
    champ_adapter = [m for m in methods if m.method_id == frozen.champion_method_id][0]
    baseline_adapter = PFSPNEHAdapter()

    t0_eval = time.perf_counter()
    final_report = controller.run_final_evaluation_phase(
        frozen_selection=frozen,
        champion_adapter=champ_adapter,
        baseline_adapters=[baseline_adapter],
        instance_limit=eval_limit
    )
    elapsed_eval = time.perf_counter() - t0_eval
    print(f"[PHASE 2] Completed in {elapsed_eval:.2f}s.")
    print(f"          Champion Holdout Score: {final_report.champion_eval_score:.2f}")
    print(f"          Baseline Holdout Score: {final_report.baseline_eval_scores.get('neh_classical'):.2f}")
    print(f"          Relative Gap:           {final_report.relative_gap * 100:+.4f}%")
    print(f"          Beats Baseline:         {final_report.beats_baseline}")

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
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "discovery_kernel_v01",
        "results",
        "pilot_20261019"
    )
    run_integration_pilot(out_dir, dev_limit=5, eval_limit=5, timeout_sec=1.5)
