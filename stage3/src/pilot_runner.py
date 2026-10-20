"""
Stage 3: Experimental Pilot Study Orchestrator
==============================================
Executes the pre-registered 3-trial pilot study (T_pilot = 3):
- 3 Paired Trials x 3 Arms (A, B, C) = 9 trial runs = 900 candidate generation calls.
- Enforces strict slot accounting: exactly 100 slots per arm per trial.
- Tests technical hidden firewall: verifies access to hidden.json is blocked.
- Records best-so-far development curves at checkpoints k in {1, 5, 10, 20, 50, 100}.
- Evaluates selected winners out-of-sample on the 24 pilot benchmark instances (pilot.json).
- Checks all 4 pre-registered N-modification criteria.
- Computes empirical variance s_Delta and power planning estimate for T_main.
- Transitions state machine: IMPLEMENTATION_VERIFIED -> PILOT_READY -> PILOT_RUNNING -> PILOT_COMPLETE.
"""

import json
import math
import os
import sys
import time
from typing import Dict, Any, List

import numpy as np

from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.lineage import LineageTracker
from stage3.src.llm_client import Stage3LLMClient
from stage3.src.search_curves import compute_best_so_far_curve, analyze_trial_trajectories
from stage3.src.search_engine import Stage3SearchEngine
from stage3.src.state_machine import StateMachine, ExperimentState


def run_pilot():
    print("=" * 80, flush=True)
    print("AMAURA LABS — STAGE 3 EXPERIMENTAL PILOT STUDY", flush=True)
    print("=" * 80, flush=True)

    config_path = "stage3/config.json"
    with open(config_path) as f:
        config = json.load(f)

    # 1. State Machine Initialization & Transitions
    sm = StateMachine(
        state_file=config["paths"]["state_file"],
        audit_log_path=config["paths"]["audit_log"]
    )
    current_state = sm.get_current_state()
    print(f"Current State Machine State: {current_state.value}", flush=True)

    if current_state != ExperimentState.IMPLEMENTATION_VERIFIED:
        raise RuntimeError(f"Cannot start pilot: State is '{current_state.value}', expected 'IMPLEMENTATION_VERIFIED'.")

    sm.transition_to(ExperimentState.PILOT_READY, "Implementation audit complete. Ready for pilot.")
    sm.transition_to(ExperimentState.PILOT_RUNNING, "Starting Stage 3 pilot study (3 paired trials).")
    print(f"State Machine transitioned to: {sm.get_current_state().value}", flush=True)

    # 2. Technical Hidden Firewall Verification Probe
    print("\n--- Verifying Technical Hidden Firewall ---", flush=True)
    hidden_probe_blocked = False
    try:
        sm.access_hidden_dataset("pilot_firewall_probe")
    except PermissionError as e:
        hidden_probe_blocked = True
        print(f"Firewall successfully blocked access: {e}", flush=True)

    if not hidden_probe_blocked:
        raise RuntimeError("FATAL SECURITY BREACH: Hidden firewall failed to block access during PILOT_RUNNING!")

    # 3. Load Benchmarks
    dev_path = config["benchmarks"]["graph_coloring"]["dev"]
    pilot_bench_path = config["benchmarks"]["graph_coloring"]["pilot"]

    with open(dev_path) as f:
        dev_dataset = json.load(f)
    with open(pilot_bench_path) as f:
        pilot_dataset = json.load(f)

    print(f"Loaded Development Benchmark: {len(dev_dataset)} instances from {dev_path}", flush=True)
    print(f"Loaded Pilot Evaluation Benchmark: {len(pilot_dataset)} instances from {pilot_bench_path}", flush=True)

    # 4. Initialize Core Components
    evaluator = GraphColoringEvaluator()
    lineage_path = config["paths"]["candidates_log"]
    lineage_tracker = LineageTracker(lineage_path)

    llm_client = Stage3LLMClient(
        model=config["model"],
        base_url=config["api_base_url"],
        api_key=config.get("api_key"),
        cost_per_m_input=3.00,
        cost_per_m_output=15.00,
        mock_mode=config.get("mock_mode", False),
        timeout=120
    )

    search_engine = Stage3SearchEngine(
        config=config,
        llm_client=llm_client,
        evaluator=evaluator,
        lineage_tracker=lineage_tracker
    )

    # 5. Execute 3 Paired Trials
    trials_results = []
    pilot_start_time = time.perf_counter()

    for trial_id in range(1, 4):
        trial_seed = 30300 + trial_id
        print(f"\n{'='*40}\nSTARTING PILOT TRIAL {trial_id} / 3 (Seed: {trial_seed})\n{'='*40}", flush=True)

        t_trial_start = time.perf_counter()

        # ---------------------------------------------------------------------
        # ARM A: Independent Best-of-100
        # ---------------------------------------------------------------------
        print(f"\n[Trial {trial_id}] Running Arm A: Independent Best-of-100...", flush=True)
        t_a_start = time.perf_counter()
        arm_a_out = search_engine.run_arm_a(trial_id, dev_dataset, trial_seed)
        t_a_dur = time.perf_counter() - t_a_start
        print(f"[Trial {trial_id}] Arm A Completed in {t_a_dur:.1f}s. Valid: {arm_a_out['valid_candidates_count']}/100. Best Dev Score: {arm_a_out['selected_dev_score']}", flush=True)

        # ---------------------------------------------------------------------
        # ARM B: Blind Iterative Search
        # ---------------------------------------------------------------------
        print(f"\n[Trial {trial_id}] Running Arm B: Blind Iterative Search...", flush=True)
        t_b_start = time.perf_counter()
        arm_b_out = search_engine.run_arm_b(trial_id, dev_dataset, trial_seed)
        t_b_dur = time.perf_counter() - t_b_start
        print(f"[Trial {trial_id}] Arm B Completed in {t_b_dur:.1f}s. Valid: {arm_b_out['valid_candidates_count']}/100. Selected Dev Score: {arm_b_out['selected_dev_score']}", flush=True)

        # ---------------------------------------------------------------------
        # ARM C: Amaura Execution-Driven Search
        # ---------------------------------------------------------------------
        print(f"\n[Trial {trial_id}] Running Arm C: Amaura Adaptive Search...", flush=True)
        t_c_start = time.perf_counter()
        arm_c_out = search_engine.run_arm_c(trial_id, dev_dataset, trial_seed)
        t_c_dur = time.perf_counter() - t_c_start
        print(f"[Trial {trial_id}] Arm C Completed in {t_c_dur:.1f}s. Valid: {arm_c_out['valid_candidates_count']}/100. Best Dev Score: {arm_c_out['selected_dev_score']}", flush=True)

        # ---------------------------------------------------------------------
        # Out-of-Sample Evaluation on Pilot Benchmark (pilot.json)
        # ---------------------------------------------------------------------
        print(f"\n[Trial {trial_id}] Evaluating Selected Winners on Pilot Benchmark (24 graphs)...", flush=True)

        def eval_winner_out_of_sample(cand_code):
            if not cand_code:
                return None, None, False
            ev = evaluator.evaluate_code(cand_code, pilot_dataset)
            return ev["total_colors"], ev["avg_colors"], ev["is_valid"]

        a_pilot_score, a_pilot_avg, a_pilot_valid = eval_winner_out_of_sample(arm_a_out.get("selected_candidate_code"))
        b_pilot_score, b_pilot_avg, b_pilot_valid = eval_winner_out_of_sample(arm_b_out.get("selected_candidate_code"))
        c_pilot_score, c_pilot_avg, c_pilot_valid = eval_winner_out_of_sample(arm_c_out.get("selected_candidate_code"))

        print(f"[Trial {trial_id}] Pilot Scores — Arm A: {a_pilot_score} | Arm B: {b_pilot_score} | Arm C: {c_pilot_score}", flush=True)

        # ---------------------------------------------------------------------
        # Budget Checkpoint Curves (k in 1, 5, 10, 20, 50, 100)
        # ---------------------------------------------------------------------
        trajectories = analyze_trial_trajectories(
            trial_id=trial_id,
            cands_a=arm_a_out["candidates"],
            cands_b=arm_b_out["candidates"],
            cands_c=arm_c_out["candidates"]
        )

        trial_record = {
            "trial_id": trial_id,
            "seed": trial_seed,
            "duration_sec": round(time.perf_counter() - t_trial_start, 2),
            "arm_a": {
                "status": arm_a_out["status"],
                "selected_candidate_id": arm_a_out["selected_candidate_id"],
                "dev_score": arm_a_out["selected_dev_score"],
                "pilot_score": a_pilot_score,
                "pilot_avg_colors": a_pilot_avg,
                "pilot_valid": a_pilot_valid,
                "valid_count": arm_a_out["valid_candidates_count"],
                "duration_sec": round(t_a_dur, 2)
            },
            "arm_b": {
                "status": arm_b_out["status"],
                "selected_candidate_id": arm_b_out["selected_candidate_id"],
                "dev_score": arm_b_out["selected_dev_score"],
                "pilot_score": b_pilot_score,
                "pilot_avg_colors": b_pilot_avg,
                "pilot_valid": b_pilot_valid,
                "valid_count": arm_b_out["valid_candidates_count"],
                "duration_sec": round(t_b_dur, 2)
            },
            "arm_c": {
                "status": arm_c_out["status"],
                "selected_candidate_id": arm_c_out["selected_candidate_id"],
                "dev_score": arm_c_out["selected_dev_score"],
                "pilot_score": c_pilot_score,
                "pilot_avg_colors": c_pilot_avg,
                "pilot_valid": c_pilot_valid,
                "valid_count": arm_c_out["valid_candidates_count"],
                "duration_sec": round(t_c_dur, 2)
            },
            "checkpoints": trajectories
        }
        trials_results.append(trial_record)

    total_pilot_runtime = time.perf_counter() - pilot_start_time

    # 6. Pilot Metrics & Objective Failure Criteria Evaluation
    print("\n" + "=" * 80, flush=True)
    print("PILOT ANALYSIS & DIAGNOSTICS", flush=True)
    print("=" * 80, flush=True)

    # All candidate records across pilot from candidates.jsonl
    with open(lineage_path) as f:
        all_pilot_cands = [json.loads(line) for line in f]

    total_slots = len(all_pilot_cands)
    valid_slots = sum(1 for c in all_pilot_cands if c["validity"])
    fail_rate = (total_slots - valid_slots) / total_slots if total_slots > 0 else 0.0

    # Score spread on dev set
    dev_scores = [c["development_score"] for c in all_pilot_cands if c["validity"] and c["development_score"] is not None]
    if dev_scores:
        mean_score = float(np.mean(dev_scores))
        std_score = float(np.std(dev_scores))
        cv = std_score / mean_score if mean_score > 0 else 0.0
        min_score = min(dev_scores)
        max_score = max(dev_scores)
        rel_range = (max_score - min_score) / mean_score if mean_score > 0 else 0.0
        # Saturation check: fraction of valid candidates achieving min score
        min_count = sum(1 for s in dev_scores if s == min_score)
        saturation_pct = min_count / len(dev_scores)
    else:
        mean_score, std_score, cv, min_score, max_score, rel_range, saturation_pct = 0, 0, 0, 0, 0, 0, 0

    print(f"Total Slots: {total_slots} | Valid: {valid_slots} ({valid_slots/total_slots:.1%}) | Failure Rate: {fail_rate:.1%}", flush=True)
    print(f"Dev Score Distribution: Mean={mean_score:.1f}, Std={std_score:.1f}, CV={cv:.4f}, Range=[{min_score}, {max_score}] (Rel Range={rel_range:.4f})", flush=True)
    print(f"Benchmark Saturation: {saturation_pct:.1%} of valid candidates achieved identical minimum score", flush=True)

    # Check 4 Objective N-modification criteria
    crit_1_fail_rate = fail_rate > 0.40
    crit_2_eval_infeasible = (total_pilot_runtime / 3.0) > 300.0  # > 5 min per trial
    crit_3_lack_spread = (cv < 0.005) or (rel_range < 0.01)
    crit_4_saturation = saturation_pct > 0.90

    n_change_recommended = any([crit_1_fail_rate, crit_2_eval_infeasible, crit_3_lack_spread, crit_4_saturation])

    print("\n--- Pre-Registered N=100 Invariant Audit ---", flush=True)
    print(f"1. Generation Failure Rate > 40%:      {crit_1_fail_rate} (actual: {fail_rate:.1%})", flush=True)
    print(f"2. Evaluator Time > 5 min/trial:        {crit_2_eval_infeasible} (actual: {total_pilot_runtime/3.0:.1f}s)", flush=True)
    print(f"3. Inability to obtain score spread:    {crit_3_lack_spread} (actual CV: {cv:.4f}, range: {rel_range:.4f})", flush=True)
    print(f"4. Benchmark Saturation > 90%:          {crit_4_saturation} (actual: {saturation_pct:.1%})", flush=True)
    print(f"N Modification Triggered:               {n_change_recommended} -> N remains FROZEN at 100", flush=True)

    # 7. Variance of Paired Differences and Power Planning
    # Paired trial-level differences on Pilot out-of-sample scores
    pilot_deltas = []
    dev_deltas = []
    for t in trials_results:
        if t["arm_c"]["status"] == "VALID" and t["arm_a"]["status"] == "VALID":
            c_p = t["arm_c"]["pilot_score"]
            a_p = t["arm_a"]["pilot_score"]
            c_d = t["arm_c"]["dev_score"]
            a_d = t["arm_a"]["dev_score"]
            if c_p is not None and a_p is not None:
                pilot_deltas.append(c_p - a_p)
            if c_d is not None and a_d is not None:
                dev_deltas.append(c_d - a_d)

    print(f"\nPaired Differences (C - A) on Pilot Set: {pilot_deltas}", flush=True)
    print(f"Paired Differences (C - A) on Dev Set:   {dev_deltas}", flush=True)

    if len(pilot_deltas) >= 2:
        s_delta = float(np.std(pilot_deltas, ddof=1))
    elif len(dev_deltas) >= 2:
        s_delta = float(np.std(dev_deltas, ddof=1))
    else:
        s_delta = 1.0  # Fallback default

    # Power planning formula: T_planned = ceil(7.849 * s_delta^2 / 1.0^2)
    delta_practical = 1.0
    t_raw_planned = math.ceil((7.849 * (s_delta ** 2)) / (delta_practical ** 2))
    # Pre-registered bounds: T_min = 20 <= T_main <= T_max = 40, default = 30
    t_bounded = max(20, min(40, t_raw_planned))

    print(f"\nSample Variance s_Delta = {s_delta:.4f}", flush=True)
    print(f"Raw Power-Planned T = {t_raw_planned}", flush=True)
    print(f"Bounded Main Experiment T_main = {t_bounded} (Bounds: [20, 40], Default Target: 30)", flush=True)

    # 8. Telemetry & Cost
    pilot_summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": config["model"],
        "t_pilot_trials": 3,
        "total_runtime_sec": round(total_pilot_runtime, 2),
        "total_calls": llm_client.total_calls,
        "total_input_tokens": llm_client.total_input_tokens,
        "total_output_tokens": llm_client.total_output_tokens,
        "total_cost_usd": round(llm_client.total_cost, 4),
        "firewall_verification": {
            "probe_attempted": True,
            "access_blocked": hidden_probe_blocked
        },
        "slot_accounting": {
            "total_slots": total_slots,
            "valid_slots": valid_slots,
            "failure_rate": round(fail_rate, 4)
        },
        "score_distribution": {
            "mean": round(mean_score, 2),
            "std": round(std_score, 2),
            "cv": round(cv, 4),
            "min": min_score,
            "max": max_score,
            "rel_range": round(rel_range, 4),
            "saturation_rate": round(saturation_pct, 4)
        },
        "n_modification_criteria": {
            "crit_1_fail_rate_gt_40pct": crit_1_fail_rate,
            "crit_2_eval_gt_5min": crit_2_eval_infeasible,
            "crit_3_cv_lt_0005": crit_3_lack_spread,
            "crit_4_saturation_gt_90pct": crit_4_saturation,
            "n_modified": False,
            "frozen_n": 100
        },
        "power_planning": {
            "pilot_differences_pilot_set": pilot_deltas,
            "pilot_differences_dev_set": dev_deltas,
            "s_delta": round(s_delta, 4),
            "delta_practical": delta_practical,
            "t_raw_planned": t_raw_planned,
            "t_bounded_final": t_bounded
        },
        "trials": trials_results
    }

    # Save Results
    os.makedirs("stage3/results", exist_ok=True)
    with open("stage3/results/pilot_results.json", "w") as f:
        json.dump(pilot_summary, f, indent=2)

    # 9. Transition State Machine to PILOT_COMPLETE
    sm.transition_to(ExperimentState.PILOT_COMPLETE, "Pilot study completed successfully. Metrics recorded.")
    print(f"\nFinal State Machine State: {sm.get_current_state().value}", flush=True)
    print("Pilot results saved to stage3/results/pilot_results.json", flush=True)
    return pilot_summary


if __name__ == "__main__":
    run_pilot()
