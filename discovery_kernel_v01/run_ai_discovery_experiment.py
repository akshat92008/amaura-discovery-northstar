"""
North BlueStar: AI Discovery Pilot Experiment Runner (2026-10-19)
================================================================
Orchestrates:
1. Development evaluation of 4 conventional baselines & selection of Primary Baseline.
2. Arm A: 12 independent candidate proposals via local Ollama (zero feedback).
3. Arm B: 12 evidence-guided candidate proposals via local Ollama (3 rounds of 4 with feedback).
4. Freezing of Primary Baseline, Champion A, and Champion B.
5. Quarantined holdout evaluation on 30 untouched instances.
6. Paired relative improvement statistics, 95% bootstrap CIs, and discovery gate testing.
7. Machine-readable outputs: run_records.jsonl, development_results.json, final_results.json.
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

from discovery_kernel.problem_spec import ProblemSpecification, ObjectiveDirection, DatasetReference, ConstraintRule
from discovery_kernel.method_adapter import (
    MethodAdapter, MethodMetadata, PFSPNEHAdapter, PFSPNEHLSAdapter, PFSPFunctionAdapter
)
from discovery_kernel.pfsp_declarative import (
    PFSPDeclarativeAdapter, validate_config, canonicalize_config, solve_declarative
)
from discovery_kernel.generator import PFSPCandidateGenerator, ProposalResult
from discovery_kernel.execution import ExecutionSupervisor
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    calc_makespan_and_flow_ref,
    solve_v2_anytime_bounded,
    iterated_greedy_solve
)
from benchmark_v1.src.domains.pfsp_full_algorithm import validate_permutation


EXPERIMENT_DIR = os.path.join(REPO_ROOT, "discovery_kernel_v01", "results", "ai_discovery_pilot_20261019")
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")


def solve_iterated_greedy_top(pts: List[List[int]]) -> List[int]:
    return iterated_greedy_solve(pts, d=4, max_iter=20)


def solve_candidate_2_bounded_top(pts: List[List[int]]) -> List[int]:
    return solve_v2_anytime_bounded(pts, max_evals=200)


def validate_perm_top(instance: Dict[str, Any], solution: Any) -> Tuple[bool, Optional[str]]:
    times = instance["times"] if isinstance(instance, dict) else instance
    n = len(times)
    return validate_permutation(solution, n)


def pfsp_evaluator_top(instance: Dict[str, Any], solution: Any) -> float:
    times = instance["times"] if isinstance(instance, dict) else instance
    return float(calc_makespan_ref(times, solution))


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
    """Computes paired relative improvement g_i and 95% bootstrap confidence interval."""
    assert len(baseline_makespans) == len(candidate_makespans)
    n = len(baseline_makespans)

    g_vals = [
        (b - c) / b for b, c in zip(baseline_makespans, candidate_makespans)
    ]
    mean_g = float(sum(g_vals) / n)
    sorted_g = sorted(g_vals)
    median_g = float(sorted_g[n // 2] if n % 2 != 0 else (sorted_g[n // 2 - 1] + sorted_g[n // 2]) / 2)
    std_g = float(math.sqrt(sum((x - mean_g) ** 2 for x in g_vals) / (n - 1))) if n > 1 else 0.0

    wins = sum(1 for g in g_vals if g > 1e-9)
    ties = sum(1 for g in g_vals if abs(g) <= 1e-9)
    losses = sum(1 for g in g_vals if g < -1e-9)

    # Bootstrap resampling
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
    print("NORTH BLUESTAR: AI DISCOVERY PILOT (PFSP)")
    print("Protocol: Evidence-Guided Search (Arm B) vs Independent Best-of-N (Arm A)")
    print("=" * 80)

    # 1. Load Datasets
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

    print(f"Loaded {len(dev_instances)} Development Instances (SHA-256: {dev_hash[:16]}...)")
    print(f"Loaded {len(holdout_instances)} Sealed Holdout Instances (SHA-256: {holdout_hash[:16]}...)")

    run_records_path = os.path.join(EXPERIMENT_DIR, "run_records.jsonl")
    records_file = open(run_records_path, "w", encoding="utf-8")

    def log_record(event_type: str, data: Dict[str, Any]):
        rec = {
            "timestamp": time.time(),
            "event_type": event_type,
            **data
        }
        records_file.write(json.dumps(rec) + "\n")
        records_file.flush()

    log_record("EXPERIMENT_INITIALIZED", {
        "dev_instances": len(dev_instances),
        "dev_hash": dev_hash,
        "holdout_instances": len(holdout_instances),
        "holdout_hash": holdout_hash,
        "model": "qwen2.5-coder:1.5b",
        "provider": "ollama/local",
        "billing_cost_usd": 0.0
    })
    supervisor = ExecutionSupervisor(timeout_sec=4.0, max_memory_mb=512.0)

    # =========================================================================
    # PHASE 1: Conventional Baselines Evaluation on Development Data
    # =========================================================================
    print("\n--- PHASE 1: Evaluating Conventional Baselines on Development Data ---")

    baseline_adapters = {
        "neh_classical": PFSPNEHAdapter(version="1.0.0"),
        "neh_ls_insertion": PFSPNEHLSAdapter(version="1.0.0"),
        "iterated_greedy": PFSPFunctionAdapter(
            method_id="iterated_greedy",
            solve_func=solve_iterated_greedy_top,
            description="Iterated Greedy metaheuristic (d=4, max_iter=20)"
        ),
        "candidate_2_bounded": PFSPFunctionAdapter(
            method_id="candidate_2_bounded",
            solve_func=solve_candidate_2_bounded_top,
            description="Historical Candidate #2 V2 Anytime Bounded (max_evals=200)"
        )
    }

    baseline_dev_results = {}
    for b_id, adapter in baseline_adapters.items():
        makespans = []
        runtimes = []
        valid_all = True
        for inst in dev_instances:
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

            log_record("BASELINE_DEV_INSTANCE_EVALUATED", {
                "method_id": b_id,
                "instance_id": inst["id"],
                "makespan": cmax,
                "runtime_ms": res.runtime_ms,
                "is_valid": res.is_valid
            })

        mean_ms = sum(makespans) / len(makespans)
        mean_rt = sum(runtimes) / len(runtimes)
        baseline_dev_results[b_id] = {
            "method_id": b_id,
            "description": adapter.metadata.description,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt,
            "valid_all": valid_all,
            "makespans": makespans
        }
        print(f"  {b_id:<22} Mean Dev Makespan: {mean_ms:.2f} | Mean Runtime: {mean_rt:.2f} ms")

    # Select Primary Baseline (lowest mean dev makespan)
    primary_baseline_id = min(baseline_dev_results.keys(), key=lambda k: baseline_dev_results[k]["mean_makespan"])
    primary_baseline_score = baseline_dev_results[primary_baseline_id]["mean_makespan"]
    print(f"\n>> FROZEN PRIMARY BASELINE: '{primary_baseline_id}' (Mean Dev Makespan: {primary_baseline_score:.2f})")

    log_record("PRIMARY_BASELINE_FROZEN", {
        "primary_baseline_id": primary_baseline_id,
        "mean_dev_makespan": primary_baseline_score,
        "all_baselines": {k: v["mean_makespan"] for k, v in baseline_dev_results.items()}
    })

    # =========================================================================
    # PHASE 2: Candidate Generation & Development Evaluation
    # =========================================================================
    generator = PFSPCandidateGenerator(model="qwen2.5-coder:1.5b")

    # Helper evaluation function
    seen_recipes: Dict[str, str] = {}  # recipe_hash -> proposal_id

    def evaluate_candidate_on_dev(proposal_id: str, cfg: Dict[str, Any], rationale: str) -> Dict[str, Any]:
        adapter = PFSPDeclarativeAdapter(method_id=proposal_id, config=cfg, rationale=rationale)
        makespans = []
        runtimes = []
        all_valid = True
        error_msg = None

        for inst in dev_instances:
            res = supervisor.execute_and_evaluate(
                adapter=adapter,
                instance=inst,
                instance_id=inst["id"],
                evaluator_fn=pfsp_evaluator_top,
                constraints=[PFSP_CONSTRAINT],
                objective_metric="makespan"
            )
            if not res.is_valid:
                all_valid = False
                error_msg = res.error_message or "Invalid permutation"
            cmax = int(res.objective_score) if res.is_valid and res.objective_score is not None else 9999999
            makespans.append(cmax)
            runtimes.append(res.runtime_ms)

            log_record("CANDIDATE_DEV_INSTANCE_EVALUATED", {
                "proposal_id": proposal_id,
                "instance_id": inst["id"],
                "makespan": cmax,
                "runtime_ms": res.runtime_ms,
                "is_valid": res.is_valid
            })

        mean_ms = sum(makespans) / len(makespans) if all_valid else float("inf")
        mean_rt = sum(runtimes) / len(runtimes)
        return {
            "all_valid": all_valid,
            "error_msg": error_msg,
            "makespans": makespans,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt
        }

    # -------------------------------------------------------------------------
    # Arm A: Independent Best-of-12
    # -------------------------------------------------------------------------
    print("\n--- PHASE 2A: Arm A — Independent Best-of-12 Generation ---")
    arm_a_proposals: List[Dict[str, Any]] = []

    for i in range(1, 13):
        prop_id = f"arm_a_prop_{i:02d}"
        print(f"  Generating {prop_id}...", end="", flush=True)
        prop_res = generator.generate_independent_candidate(proposal_id=prop_id, temperature=0.7)

        is_duplicate = False
        duplicate_of = None
        if prop_res.is_valid_spec and prop_res.recipe_hash:
            if prop_res.recipe_hash in seen_recipes:
                is_duplicate = True
                duplicate_of = seen_recipes[prop_res.recipe_hash]
            else:
                seen_recipes[prop_res.recipe_hash] = prop_id

        eval_summary = None
        if prop_res.is_valid_spec and prop_res.sanitized_config:
            eval_summary = evaluate_candidate_on_dev(
                proposal_id=prop_id,
                cfg=prop_res.sanitized_config,
                rationale=prop_res.parsed_proposal.get("rationale", "")
            )
            score_str = f"{eval_summary['mean_makespan']:.2f}" if eval_summary["all_valid"] else "INVALID"
        else:
            score_str = f"MALFORMED: {prop_res.validation_error}"

        prop_record = {
            "proposal_id": prop_id,
            "arm": "arm_a",
            "round_idx": 0,
            "is_valid_spec": prop_res.is_valid_spec,
            "validation_error": prop_res.validation_error,
            "recipe_hash": prop_res.recipe_hash,
            "is_syntactic_duplicate": is_duplicate,
            "duplicate_of": duplicate_of,
            "prompt_tokens": prop_res.prompt_tokens,
            "completion_tokens": prop_res.completion_tokens,
            "latency_sec": prop_res.latency_sec,
            "raw_response": prop_res.raw_response,
            "config": prop_res.sanitized_config,
            "rationale": prop_res.parsed_proposal.get("rationale", "") if prop_res.parsed_proposal else "",
            "eval_summary": eval_summary
        }
        arm_a_proposals.append(prop_record)

        log_record("CANDIDATE_PROPOSAL_GENERATED", {
            "proposal_id": prop_id,
            "arm": "arm_a",
            "is_valid_spec": prop_res.is_valid_spec,
            "recipe_hash": prop_res.recipe_hash,
            "mean_makespan": eval_summary["mean_makespan"] if eval_summary else None,
            "latency_sec": prop_res.latency_sec
        })

        print(f" Done ({prop_res.latency_sec:.1f}s) | Score: {score_str} | Duplicate: {is_duplicate}")

    # Select Champion A (lowest mean dev makespan among valid proposals)
    valid_arm_a = [p for p in arm_a_proposals if p["is_valid_spec"] and p["eval_summary"] and p["eval_summary"]["all_valid"]]
    if not valid_arm_a:
        raise RuntimeError("Arm A produced zero valid candidates!")
    champion_a = min(valid_arm_a, key=lambda p: p["eval_summary"]["mean_makespan"])
    print(f"\n>> FROZEN CHAMPION A: '{champion_a['proposal_id']}' (Mean Dev Makespan: {champion_a['eval_summary']['mean_makespan']:.2f})")

    # -------------------------------------------------------------------------
    # Arm B: Evidence-Guided Search (3 Rounds x 4 Proposals)
    # -------------------------------------------------------------------------
    print("\n--- PHASE 2B: Arm B — Evidence-Guided Search (3 Rounds x 4 Proposals) ---")
    arm_b_proposals: List[Dict[str, Any]] = []
    round_feedback = ""

    for round_idx in range(1, 4):
        print(f"\n  === Arm B Round {round_idx} / 3 ===")
        round_props = []

        for p_idx in range(1, 5):
            prop_num = (round_idx - 1) * 4 + p_idx
            prop_id = f"arm_b_prop_{prop_num:02d}"
            print(f"    Generating {prop_id}...", end="", flush=True)

            prop_res = generator.generate_guided_candidate(
                proposal_id=prop_id,
                round_idx=round_idx,
                feedback_summary=round_feedback,
                temperature=0.7
            )

            is_duplicate = False
            duplicate_of = None
            if prop_res.is_valid_spec and prop_res.recipe_hash:
                if prop_res.recipe_hash in seen_recipes:
                    is_duplicate = True
                    duplicate_of = seen_recipes[prop_res.recipe_hash]
                else:
                    seen_recipes[prop_res.recipe_hash] = prop_id

            eval_summary = None
            if prop_res.is_valid_spec and prop_res.sanitized_config:
                eval_summary = evaluate_candidate_on_dev(
                    proposal_id=prop_id,
                    cfg=prop_res.sanitized_config,
                    rationale=prop_res.parsed_proposal.get("rationale", "")
                )
                score_str = f"{eval_summary['mean_makespan']:.2f}" if eval_summary["all_valid"] else "INVALID"
            else:
                score_str = f"MALFORMED: {prop_res.validation_error}"

            prop_record = {
                "proposal_id": prop_id,
                "arm": "arm_b",
                "round_idx": round_idx,
                "is_valid_spec": prop_res.is_valid_spec,
                "validation_error": prop_res.validation_error,
                "recipe_hash": prop_res.recipe_hash,
                "is_syntactic_duplicate": is_duplicate,
                "duplicate_of": duplicate_of,
                "prompt_tokens": prop_res.prompt_tokens,
                "completion_tokens": prop_res.completion_tokens,
                "latency_sec": prop_res.latency_sec,
                "raw_response": prop_res.raw_response,
                "config": prop_res.sanitized_config,
                "rationale": prop_res.parsed_proposal.get("rationale", "") if prop_res.parsed_proposal else "",
                "eval_summary": eval_summary
            }
            arm_b_proposals.append(prop_record)
            round_props.append(prop_record)

            log_record("CANDIDATE_PROPOSAL_GENERATED", {
                "proposal_id": prop_id,
                "arm": "arm_b",
                "round_idx": round_idx,
                "is_valid_spec": prop_res.is_valid_spec,
                "recipe_hash": prop_res.recipe_hash,
                "mean_makespan": eval_summary["mean_makespan"] if eval_summary else None,
                "latency_sec": prop_res.latency_sec
            })

            print(f" Done ({prop_res.latency_sec:.1f}s) | Score: {score_str} | Duplicate: {is_duplicate}")

        # Build feedback summary for subsequent round
        valid_so_far = [p for p in arm_b_proposals if p["is_valid_spec"] and p["eval_summary"] and p["eval_summary"]["all_valid"]]
        if valid_so_far:
            best_so_far = min(valid_so_far, key=lambda p: p["eval_summary"]["mean_makespan"])
            feedback_lines = [
                f"Completed Rounds: {round_idx} / 3. Total proposals evaluated: {len(arm_b_proposals)}.",
                f"Best Candidate So Far: {best_so_far['proposal_id']} with Mean Makespan {best_so_far['eval_summary']['mean_makespan']:.2f}.",
                f"Best Config Recipe: {json.dumps(best_so_far['config'])}",
                "Recent Round Results:"
            ]
            for rp in round_props:
                if rp["is_valid_spec"] and rp["eval_summary"] and rp["eval_summary"]["all_valid"]:
                    feedback_lines.append(
                        f"- {rp['proposal_id']}: Mean Makespan {rp['eval_summary']['mean_makespan']:.2f} | "
                        f"initial_order={rp['config']['initial_order']}, criterion={rp['config']['construction_criterion']}, "
                        f"local_search={rp['config']['local_search']}"
                    )
                else:
                    feedback_lines.append(f"- {rp['proposal_id']}: FAILED ({rp.get('validation_error') or 'execution error'})")
            round_feedback = "\n".join(feedback_lines)

    # Select Champion B
    valid_arm_b = [p for p in arm_b_proposals if p["is_valid_spec"] and p["eval_summary"] and p["eval_summary"]["all_valid"]]
    if not valid_arm_b:
        raise RuntimeError("Arm B produced zero valid candidates!")
    champion_b = min(valid_arm_b, key=lambda p: p["eval_summary"]["mean_makespan"])
    print(f"\n>> FROZEN CHAMPION B: '{champion_b['proposal_id']}' (Mean Dev Makespan: {champion_b['eval_summary']['mean_makespan']:.2f})")

    # Save development results and freeze manifest
    dev_results_payload = {
        "metadata": {
            "timestamp": time.time(),
            "problem": "PFSP",
            "dev_instances_count": len(dev_instances),
            "dev_instances_hash": dev_hash,
            "primary_baseline_id": primary_baseline_id,
            "champion_a_id": champion_a["proposal_id"],
            "champion_b_id": champion_b["proposal_id"]
        },
        "baselines": baseline_dev_results,
        "arm_a_proposals": arm_a_proposals,
        "arm_b_proposals": arm_b_proposals,
        "frozen_selection": {
            "primary_baseline": {
                "id": primary_baseline_id,
                "mean_dev_makespan": primary_baseline_score
            },
            "champion_a": {
                "id": champion_a["proposal_id"],
                "recipe_hash": champion_a["recipe_hash"],
                "mean_dev_makespan": champion_a["eval_summary"]["mean_makespan"],
                "config": champion_a["config"],
                "rationale": champion_a["rationale"]
            },
            "champion_b": {
                "id": champion_b["proposal_id"],
                "recipe_hash": champion_b["recipe_hash"],
                "mean_dev_makespan": champion_b["eval_summary"]["mean_makespan"],
                "config": champion_b["config"],
                "rationale": champion_b["rationale"]
            }
        }
    }

    dev_results_path = os.path.join(EXPERIMENT_DIR, "development_results.json")
    with open(dev_results_path, "w", encoding="utf-8") as f:
        json.dump(dev_results_payload, f, indent=2)

    log_record("DEVELOPMENT_PHASE_FROZEN", dev_results_payload["frozen_selection"])

    # =========================================================================
    # PHASE 3: Quarantined Holdout Evaluation (30 Fresh Instances)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: EVALUATING FROZEN CANDIDATES & BASELINES ON 30 HOLDOUT INSTANCES")
    print("=" * 80)

    # Adapters for final evaluation
    eval_target_adapters = {
        primary_baseline_id: baseline_adapters[primary_baseline_id],
        "champion_a": PFSPDeclarativeAdapter(
            method_id=champion_a["proposal_id"],
            config=champion_a["config"],
            rationale=champion_a["rationale"]
        ),
        "champion_b": PFSPDeclarativeAdapter(
            method_id=champion_b["proposal_id"],
            config=champion_b["config"],
            rationale=champion_b["rationale"]
        )
    }
    # Also evaluate all other baselines on holdout for full scientific disclosure
    for b_id, adp in baseline_adapters.items():
        if b_id != primary_baseline_id:
            eval_target_adapters[b_id] = adp

    holdout_outcomes: Dict[str, Dict[str, Any]] = {}

    for name, adapter in eval_target_adapters.items():
        makespans = []
        runtimes = []
        valid_all = True
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

            log_record("HOLDOUT_INSTANCE_EVALUATED", {
                "target_name": name,
                "method_id": adapter.method_id,
                "instance_id": inst["id"],
                "makespan": cmax,
                "runtime_ms": res.runtime_ms,
                "is_valid": res.is_valid
            })

        mean_ms = sum(makespans) / len(makespans)
        mean_rt = sum(runtimes) / len(runtimes)
        holdout_outcomes[name] = {
            "name": name,
            "method_id": adapter.method_id,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt,
            "valid_all": valid_all,
            "makespans": makespans,
            "runtimes_ms": runtimes
        }
        print(f"  Holdout {name:<22}: Mean Makespan = {mean_ms:.2f} | Mean Runtime = {mean_rt:.2f} ms | Valid = {valid_all}")

    # =========================================================================
    # PHASE 4: Statistical Analysis & Discovery Gate Verification
    # =========================================================================
    print("\n--- PHASE 4: Statistical Analysis & Discovery Gate Verification ---")

    primary_b_makespans = holdout_outcomes[primary_baseline_id]["makespans"]
    champ_a_makespans = holdout_outcomes["champion_a"]["makespans"]
    champ_b_makespans = holdout_outcomes["champion_b"]["makespans"]

    # 1. Champion A vs Primary Baseline
    stats_a_vs_base = bootstrap_relative_ci(primary_b_makespans, champ_a_makespans, seed=42)
    # 2. Champion B vs Primary Baseline
    stats_b_vs_base = bootstrap_relative_ci(primary_b_makespans, champ_b_makespans, seed=42)
    # 3. Champion B vs Champion A (Search Strategy Comparison)
    stats_b_vs_a = bootstrap_relative_ci(champ_a_makespans, champ_b_makespans, seed=42)

    # Discovery gate evaluation for Champion A
    gate_a_passed = (
        holdout_outcomes["champion_a"]["valid_all"] and
        stats_a_vs_base["mean_relative_improvement"] >= 0.010 and
        stats_a_vs_base["ci_lower_95"] > 0.0
    )

    # Discovery gate evaluation for Champion B
    gate_b_passed = (
        holdout_outcomes["champion_b"]["valid_all"] and
        stats_b_vs_base["mean_relative_improvement"] >= 0.010 and
        stats_b_vs_base["ci_lower_95"] > 0.0
    )

    print("\nResults vs Primary Baseline:")
    print(f"  Champion A ({champion_a['proposal_id']}):")
    print(f"    Mean Relative Improvement g: {stats_a_vs_base['mean_relative_improvement']*100:+.3f}%")
    print(f"    95% Bootstrap CI: [{stats_a_vs_base['ci_lower_95']*100:+.3f}%, {stats_a_vs_base['ci_upper_95']*100:+.3f}%]")
    print(f"    Wins / Ties / Losses: {stats_a_vs_base['wins']} / {stats_a_vs_base['ties']} / {stats_a_vs_base['losses']}")
    print(f"    Preregistered 1.0% Gate Met: {gate_a_passed}")

    print(f"\n  Champion B ({champion_b['proposal_id']}):")
    print(f"    Mean Relative Improvement g: {stats_b_vs_base['mean_relative_improvement']*100:+.3f}%")
    print(f"    95% Bootstrap CI: [{stats_b_vs_base['ci_lower_95']*100:+.3f}%, {stats_b_vs_base['ci_upper_95']*100:+.3f}%]")
    print(f"    Wins / Ties / Losses: {stats_b_vs_base['wins']} / {stats_b_vs_base['ties']} / {stats_b_vs_base['losses']}")
    print(f"    Preregistered 1.0% Gate Met: {gate_b_passed}")

    print(f"\nSearch Strategy Comparison (Arm B vs Arm A):")
    print(f"  Mean Relative Improvement (B vs A): {stats_b_vs_a['mean_relative_improvement']*100:+.3f}%")
    print(f"  95% Bootstrap CI: [{stats_b_vs_a['ci_lower_95']*100:+.3f}%, {stats_b_vs_a['ci_upper_95']*100:+.3f}%]")
    print(f"  Wins / Ties / Losses (B vs A): {stats_b_vs_a['wins']} / {stats_b_vs_a['ties']} / {stats_b_vs_a['losses']}")

    # Save final results
    final_results_payload = {
        "metadata": {
            "timestamp": time.time(),
            "problem": "PFSP",
            "holdout_instances_count": len(holdout_instances),
            "holdout_instances_hash": holdout_hash,
            "primary_baseline_id": primary_baseline_id,
            "champion_a_id": champion_a["proposal_id"],
            "champion_b_id": champion_b["proposal_id"]
        },
        "holdout_outcomes": holdout_outcomes,
        "statistical_tests": {
            "champion_a_vs_primary_baseline": stats_a_vs_base,
            "champion_b_vs_primary_baseline": stats_b_vs_base,
            "champion_b_vs_champion_a": stats_b_vs_a
        },
        "discovery_gate": {
            "threshold_relative_improvement": 0.010,
            "champion_a_gate_passed": gate_a_passed,
            "champion_b_gate_passed": gate_b_passed
        }
    }

    final_results_path = os.path.join(EXPERIMENT_DIR, "final_results.json")
    with open(final_results_path, "w", encoding="utf-8") as f:
        json.dump(final_results_payload, f, indent=2)

    log_record("FINAL_EVALUATION_COMPLETED", {
        "gate_a_passed": gate_a_passed,
        "gate_b_passed": gate_b_passed,
        "stats_a_vs_base": {k: stats_a_vs_base[k] for k in ["mean_relative_improvement", "ci_lower_95", "ci_upper_95", "wins", "losses"]},
        "stats_b_vs_base": {k: stats_b_vs_base[k] for k in ["mean_relative_improvement", "ci_lower_95", "ci_upper_95", "wins", "losses"]},
        "stats_b_vs_a": {k: stats_b_vs_a[k] for k in ["mean_relative_improvement", "ci_lower_95", "ci_upper_95", "wins", "losses"]}
    })

    records_file.close()
    print("\nSaved run records to:", run_records_path)
    print("Saved development results to:", dev_results_path)
    print("Saved final results to:", final_results_path)
    print("\n" + "=" * 80)
    print("EXPERIMENT RUN COMPLETE.")
    print("=" * 80)


if __name__ == "__main__":
    main()
