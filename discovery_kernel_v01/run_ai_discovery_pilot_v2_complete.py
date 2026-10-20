"""
Completion script for North BlueStar: Corrected AI Discovery Pilot v2 (2026-10-20)
================================================================================
Resumes from the frozen state in run_records.jsonl:
1. Validates the 60 candidate proposals and frozen champions from run_records.jsonl.
2. Writes development_results.json.
3. Evaluates the 5 methods on the 30 sealed holdout instances:
   - reference_neh_ls (NEH-LS baseline)
   - classical_neh
   - iterated_greedy
   - champion_arm_a
   - champion_arm_b
4. Appends all HOLDOUT_INSTANCE_EVALUATED events to run_records.jsonl.
5. Computes paired relative improvements, 95% bootstrap CIs, and evaluates the Discovery Gate.
6. Writes final_results.json.
"""

import copy
import hashlib
import json
import math
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from discovery_kernel.problem_spec import ConstraintRule
from discovery_kernel.method_adapter import (
    MethodAdapter, MethodMetadata, PFSPNEHAdapter, PFSPNEHLSAdapter, PFSPFunctionAdapter
)
from discovery_kernel.pfsp_declarative import (
    PFSPDeclarativeAdapter, validate_config, canonicalize_config, solve_declarative
)
from discovery_kernel.execution import ExecutionSupervisor
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    calc_makespan_and_flow_ref,
    iterated_greedy_solve
)
from benchmark_v1.src.domains.pfsp_full_algorithm import (
    calc_makespan,
    validate_permutation,
    neh_solve,
    neh_ls_solve
)

EXPERIMENT_DIR = os.path.join(REPO_ROOT, "discovery_kernel_v01", "results", "ai_discovery_pilot_v2_20261020")
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")
DEV_RESULTS_PATH = os.path.join(EXPERIMENT_DIR, "development_results.json")
FINAL_RESULTS_PATH = os.path.join(EXPERIMENT_DIR, "final_results.json")
RUN_RECORDS_PATH = os.path.join(EXPERIMENT_DIR, "run_records.jsonl")
MODEL_NAME = "qwen2.5-coder:1.5b"


def validate_perm_top(instance: Dict[str, Any], solution: Any) -> Tuple[bool, Optional[str]]:
    times = instance["times"] if isinstance(instance, dict) else instance
    return validate_permutation(solution, len(times))


def pfsp_evaluator_top(instance: Dict[str, Any], solution: Any) -> float:
    times = instance["times"] if isinstance(instance, dict) else instance
    return float(calc_makespan_ref(times, solution))


def solve_ig_top(times: List[List[int]]) -> List[int]:
    return iterated_greedy_solve(times, d=4, max_iter=20)


PFSP_CONSTRAINT = ConstraintRule(
    name="valid_job_permutation",
    description="Solution must be a valid permutation of [0, ..., n-1]",
    validator=validate_perm_top
)


def bootstrap_relative_ci(
    baseline_makespans: List[int],
    candidate_makespans: List[int],
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 42
) -> Dict[str, Any]:
    assert len(baseline_makespans) == len(candidate_makespans)
    n = len(baseline_makespans)
    g_vals = [(b - c) / b for b, c in zip(baseline_makespans, candidate_makespans)]
    mean_g = float(sum(g_vals) / n)
    sorted_g = sorted(g_vals)
    median_g = float(sorted_g[n // 2] if n % 2 != 0 else (sorted_g[n // 2 - 1] + sorted_g[n // 2]) / 2)
    std_g = float(math.sqrt(sum((x - mean_g) ** 2 for x in g_vals) / (n - 1))) if n > 1 else 0.0

    wins = sum(1 for g in g_vals if g > 1e-9)
    ties = sum(1 for g in g_vals if abs(g) <= 1e-9)
    losses = sum(1 for g in g_vals if g < -1e-9)

    rng = random.Random(seed)
    boot_means = []
    for _ in range(n_resamples):
        sample = [g_vals[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    low_idx = int((alpha / 2.0) * n_resamples)
    high_idx = int((1.0 - alpha / 2.0) * n_resamples)
    ci_lower = float(boot_means[low_idx])
    ci_upper = float(boot_means[high_idx])

    return {
        "mean_relative_improvement": mean_g,
        "median_relative_improvement": median_g,
        "std_relative_improvement": std_g,
        "ci_lower_95": ci_lower,
        "ci_upper_95": ci_upper,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "n_instances": n,
        "individual_g": g_vals
    }


def main():
    print("=" * 80)
    print("NORTH BLUESTAR: AI DISCOVERY PILOT V2 - COMPLETION & HOLDOUT VERIFICATION")
    print("=" * 80)

    # 1. Load instances and verify hashes
    dev_path = os.path.join(DATA_DIR, "dev_instances.json")
    holdout_path = os.path.join(DATA_DIR, "holdout_instances.json")

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_instances = json.load(f)
    with open(holdout_path, "r", encoding="utf-8") as f:
        holdout_instances = json.load(f)

    with open(dev_path, "rb") as f:
        dev_hash = hashlib.sha256(f.read()).hexdigest()
    with open(holdout_path, "rb") as f:
        holdout_hash = hashlib.sha256(f.read()).hexdigest()

    print(f"Loaded {len(dev_instances)} Development Instances (SHA-256: {dev_hash})")
    print(f"Loaded {len(holdout_instances)} Sealed Holdout Instances (SHA-256: {holdout_hash})")

    # 2. Read run_records.jsonl
    if not os.path.exists(RUN_RECORDS_PATH):
        raise FileNotFoundError(f"Missing run_records.jsonl at {RUN_RECORDS_PATH}")

    with open(RUN_RECORDS_PATH, "r", encoding="utf-8") as f:
        existing_lines = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(existing_lines)} existing run records from {RUN_RECORDS_PATH}")

    # Parse baselines dev and proposals
    baseline_dev_results = {}
    arm_a_proposals = []
    arm_b_proposals = []
    champions_frozen_record = None

    for r in existing_lines:
        ev = r.get("event_type")
        if ev == "BASELINE_DEV_EVALUATED":
            baseline_dev_results[r["baseline_id"]] = {
                "mean_makespan": r["mean_makespan"],
                "mean_runtime_ms": r["mean_runtime_ms"],
                "all_valid": r["all_valid"]
            }
        elif ev == "CANDIDATE_PROPOSAL_GENERATED":
            if r.get("arm") == "arm_a":
                arm_a_proposals.append(r)
            elif r.get("arm") == "arm_b":
                arm_b_proposals.append(r)
        elif ev == "CHAMPIONS_FROZEN":
            champions_frozen_record = r

    if not champions_frozen_record:
        raise ValueError("CHAMPIONS_FROZEN record not found in run_records.jsonl!")

    print(f"\nArm A Proposals Loaded: {len(arm_a_proposals)}")
    print(f"Arm B Proposals Loaded: {len(arm_b_proposals)}")
    print(f"Baseline Dev Results: {baseline_dev_results}")

    champ_a_record = {
        "proposal_id": champions_frozen_record["champion_a_id"],
        "recipe_hash": champions_frozen_record["champion_a_hash"],
        "config": champions_frozen_record["champion_a_config"],
        "mean_makespan": champions_frozen_record["champion_a_dev_makespan"],
        "rationale": "Frozen Champion Arm A from run_records.jsonl"
    }

    champ_b_record = {
        "proposal_id": champions_frozen_record["champion_b_id"],
        "recipe_hash": champions_frozen_record["champion_b_hash"],
        "config": champions_frozen_record["champion_b_config"],
        "mean_makespan": champions_frozen_record["champion_b_dev_makespan"],
        "rationale": "Frozen Champion Arm B from run_records.jsonl"
    }

    primary_baseline_id = champions_frozen_record["reference_baseline_id"]
    print(f"\nChampion A: [{champ_a_record['proposal_id']}] Dev Makespan: {champ_a_record['mean_makespan']}")
    print(f"  Config A: {json.dumps(champ_a_record['config'])}")
    print(f"Champion B: [{champ_b_record['proposal_id']}] Dev Makespan: {champ_b_record['mean_makespan']}")
    print(f"  Config B: {json.dumps(champ_b_record['config'])}")
    print(f"Reference Baseline: [{primary_baseline_id}] Dev Makespan: {champions_frozen_record['reference_baseline_dev_makespan']}")

    # 3. Save development_results.json
    dev_results_payload = {
        "metadata": {
            "experiment": "ai_discovery_pilot_v2_20261020",
            "date": "2026-10-20",
            "model": MODEL_NAME,
            "provider": "ollama/local",
            "dev_instances_count": len(dev_instances),
            "dev_instances_hash": dev_hash,
            "total_arm_a_calls": len(arm_a_proposals),
            "total_arm_b_calls": len(arm_b_proposals)
        },
        "baselines_dev": baseline_dev_results,
        "arm_a_proposals": arm_a_proposals,
        "arm_b_proposals": arm_b_proposals,
        "champion_a": champ_a_record,
        "champion_b": champ_b_record
    }
    with open(DEV_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(dev_results_payload, f, indent=2)
    print(f"\nSaved development results to: {DEV_RESULTS_PATH}")

    # 4. Open run_records.jsonl in append mode
    records_file = open(RUN_RECORDS_PATH, "a", encoding="utf-8")

    def log_record(event_type: str, data: Dict[str, Any]):
        rec = {
            "timestamp": time.time(),
            "event_type": event_type,
            **data
        }
        records_file.write(json.dumps(rec) + "\n")
        records_file.flush()

    supervisor = ExecutionSupervisor(timeout_sec=5.0, max_memory_mb=512.0)

    # 5. PHASE 4: Sealed Holdout Evaluation on 30 Untouched Instances
    print("\n" + "=" * 80)
    print("PHASE 4: Sealed Holdout Evaluation on 30 Untouched Instances")
    print("=" * 80)

    holdout_eval_methods = {
        "reference_neh_ls": PFSPNEHLSAdapter(version="1.0.0"),
        "classical_neh": PFSPNEHAdapter(version="1.0.0"),
        "iterated_greedy": PFSPFunctionAdapter(
            method_id="iterated_greedy",
            solve_func=solve_ig_top,
            description="Iterated Greedy metaheuristic (d=4, max_iter=20)"
        ),
        "champion_arm_a": PFSPDeclarativeAdapter(
            method_id="champion_arm_a",
            config=champ_a_record["config"],
            rationale=champ_a_record["rationale"]
        ),
        "champion_arm_b": PFSPDeclarativeAdapter(
            method_id="champion_arm_b",
            config=champ_b_record["config"],
            rationale=champ_b_record["rationale"]
        )
    }

    holdout_results = {}
    for m_id, adapter in holdout_eval_methods.items():
        makespans = []
        runtimes = []
        evals_used_list = []
        term_conds = []
        valid_all = True
        print(f"  Evaluating [{m_id}] on 30 holdout instances...", end="", flush=True)

        for inst in holdout_instances:
            res = supervisor.execute_and_evaluate(
                adapter=adapter,
                instance=inst,
                instance_id=inst["id"],
                evaluator_fn=pfsp_evaluator_top,
                constraints=[PFSP_CONSTRAINT],
                objective_metric="makespan"
            )
            if not res.is_valid:
                valid_all = False
            cmax = int(res.objective_score) if res.is_valid and res.objective_score is not None else 9999999
            makespans.append(cmax)
            runtimes.append(res.runtime_ms)
            evals_used_list.append(res.diagnostics.get("evaluations_used", 0))
            term_conds.append(res.diagnostics.get("termination_condition", "unknown"))

            log_record("HOLDOUT_INSTANCE_EVALUATED", {
                "method_id": m_id,
                "instance_id": inst["id"],
                "makespan": cmax,
                "runtime_ms": res.runtime_ms,
                "is_valid": res.is_valid
            })

        mean_ms = sum(makespans) / len(makespans) if valid_all else float("inf")
        mean_rt = sum(runtimes) / len(runtimes)
        tot_evals = sum(evals_used_list)
        holdout_results[m_id] = {
            "all_valid": valid_all,
            "makespans": makespans,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt,
            "total_evaluations_used": tot_evals,
            "termination_conditions": term_conds
        }
        print(f" Mean C_max = {mean_ms:.2f}, Mean Runtime = {mean_rt:.2f} ms")

    # 6. PHASE 5: Statistical Comparison & Discovery Gate Verification
    print("\n" + "=" * 80)
    print("PHASE 5: Statistical Comparison & Discovery Gate Evaluation")
    print("=" * 80)

    base_ms = holdout_results["reference_neh_ls"]["makespans"]
    stats_a_vs_base = bootstrap_relative_ci(base_ms, holdout_results["champion_arm_a"]["makespans"])
    stats_b_vs_base = bootstrap_relative_ci(base_ms, holdout_results["champion_arm_b"]["makespans"])
    stats_b_vs_a = bootstrap_relative_ci(holdout_results["champion_arm_a"]["makespans"], holdout_results["champion_arm_b"]["makespans"])

    print("\n1. Arm A Champion vs NEH-LS Reference Baseline:")
    print(f"   Mean Relative Improvement: {stats_a_vs_base['mean_relative_improvement']*100:+.3f}%")
    print(f"   Median Relative Improvement: {stats_a_vs_base['median_relative_improvement']*100:+.3f}%")
    print(f"   95% Bootstrap CI: [{stats_a_vs_base['ci_lower_95']*100:+.3f}%, {stats_a_vs_base['ci_upper_95']*100:+.3f}%]")
    print(f"   Wins / Ties / Losses: {stats_a_vs_base['wins']} / {stats_a_vs_base['ties']} / {stats_a_vs_base['losses']}")

    print("\n2. Arm B Champion vs NEH-LS Reference Baseline:")
    print(f"   Mean Relative Improvement: {stats_b_vs_base['mean_relative_improvement']*100:+.3f}%")
    print(f"   Median Relative Improvement: {stats_b_vs_base['median_relative_improvement']*100:+.3f}%")
    print(f"   95% Bootstrap CI: [{stats_b_vs_base['ci_lower_95']*100:+.3f}%, {stats_b_vs_base['ci_upper_95']*100:+.3f}%]")
    print(f"   Wins / Ties / Losses: {stats_b_vs_base['wins']} / {stats_b_vs_base['ties']} / {stats_b_vs_base['losses']}")

    print("\n3. Arm B Champion vs Arm A Champion:")
    print(f"   Mean Relative Improvement (B over A): {stats_b_vs_a['mean_relative_improvement']*100:+.3f}%")
    print(f"   Median Relative Improvement: {stats_b_vs_a['median_relative_improvement']*100:+.3f}%")
    print(f"   95% Bootstrap CI: [{stats_b_vs_a['ci_lower_95']*100:+.3f}%, {stats_b_vs_a['ci_upper_95']*100:+.3f}%]")
    print(f"   Wins / Ties / Losses: {stats_b_vs_a['wins']} / {stats_b_vs_a['ties']} / {stats_b_vs_a['losses']}")

    # Preregistered Discovery Gate: >= 1.0% mean relative improvement and 95% CI lower bound > 0.0%
    gate_passed_a = (stats_a_vs_base["mean_relative_improvement"] >= 0.010 and stats_a_vs_base["ci_lower_95"] > 0.0)
    gate_passed_b = (stats_b_vs_base["mean_relative_improvement"] >= 0.010 and stats_b_vs_base["ci_lower_95"] > 0.0)

    print("\n" + "=" * 80)
    print(f"PREREGISTERED DISCOVERY GATE (Threshold: >= +1.000%, CI lower > 0.0%):")
    print(f"  Arm A: Mean = {stats_a_vs_base['mean_relative_improvement']*100:+.3f}%, CI Lower = {stats_a_vs_base['ci_lower_95']*100:+.3f}% -> Gate Passed: {gate_passed_a}")
    print(f"  Arm B: Mean = {stats_b_vs_base['mean_relative_improvement']*100:+.3f}%, CI Lower = {stats_b_vs_base['ci_lower_95']*100:+.3f}% -> Gate Passed: {gate_passed_b}")
    print("=" * 80)

    # Save final_results.json
    final_results_payload = {
        "metadata": {
            "experiment": "ai_discovery_pilot_v2_20261020",
            "date": "2026-10-20",
            "model": MODEL_NAME,
            "provider": "ollama/local",
            "holdout_instances_count": len(holdout_instances),
            "holdout_instances_hash": holdout_hash,
            "primary_baseline": primary_baseline_id,
            "discovery_gate_threshold_percent": 1.0
        },
        "holdout_methods": holdout_results,
        "statistical_tests": {
            "champion_a_vs_baseline": stats_a_vs_base,
            "champion_b_vs_baseline": stats_b_vs_base,
            "champion_b_vs_champion_a": stats_b_vs_a
        },
        "discovery_gate_verdict": {
            "arm_a_passed": gate_passed_a,
            "arm_b_passed": gate_passed_b
        }
    }
    with open(FINAL_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(final_results_payload, f, indent=2)
    print(f"\nSaved final results to: {FINAL_RESULTS_PATH}")

    log_record("EXPERIMENT_COMPLETED", {
        "gate_passed_a": gate_passed_a,
        "gate_passed_b": gate_passed_b,
        "champion_a_holdout_makespan": holdout_results["champion_arm_a"]["mean_makespan"],
        "champion_b_holdout_makespan": holdout_results["champion_arm_b"]["mean_makespan"],
        "baseline_holdout_makespan": holdout_results["reference_neh_ls"]["mean_makespan"],
        "a_relative_mean": stats_a_vs_base["mean_relative_improvement"],
        "b_relative_mean": stats_b_vs_base["mean_relative_improvement"]
    })

    records_file.close()
    print("\nExperiment execution complete. All records logged.")


if __name__ == "__main__":
    main()
