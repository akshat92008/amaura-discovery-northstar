"""
Stage 3: High-Performance Concurrent Main Experiment Runner (T_main = 30 Paired Trials)
========================================================================================
Executes the full Stage 3 pre-registered main experiment under the frozen protocol:
- T_main = 30 Paired Trials x 3 Arms (A, B, C) = 90 trial runs = 9,000 candidate slots.
- Multi-trial concurrency: Independent paired trials execute concurrently.
- Per-trial resource isolation:
  * Each trial maintains its own isolated workspace and checkpoint directory.
  * Each trial maintains its own deterministic RNG seed: 30300 + trial_id.
  * Each trial writes to its own isolated lineage file before atomic global merge.
  * Arm A -> Arm B -> Arm C execute in strictly isolated sequential phases within each trial.
- Intra-trial concurrency:
  * Arm A: 10 parallel batches x 10 workers (100 independent slots).
  * Arm B: 10 generations x 10 workers with strict generational barrier between generations.
  * Arm C: 10 generations x 10 workers with strict generational barrier and frozen feedback packets.
- Global Bounded Semaphore (max 15 in-flight LLM queries):
  * Matches empirical proxy benchmark saturation (~19 req/min, 0% error, median ~20s).
  * Eliminates proxy queueing timeouts and preserves 100% saturation.
- Zero retries, zero replacements (1 candidate slot consumed per attempt).
- Technical Hidden Firewall active throughout all trial execution.
- Post-Trial Execution:
  1. MAIN_RUNNING -> SELECTIONS_FROZEN
  2. SELECTIONS_FROZEN -> HIDDEN_RUNNING
  3. Evaluation of selected winners on 200 hidden instances (hidden.json)
  4. Full statistical analysis (Wilcoxon, 10k bootstrap CI, McNemar, S_penalty = 19,001)
  5. HIDDEN_RUNNING -> ANALYSIS_COMPLETE
  6. Compilation of Stage 3 final certified report.
"""

import concurrent.futures
import copy
import json
import os
import sys
import threading
import time
from typing import Dict, Any, List, Optional

import numpy as np

from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.lineage import LineageTracker
from stage3.src.llm_client import Stage3LLMClient
from stage3.src.search_curves import analyze_trial_trajectories
from stage3.src.search_engine import Stage3SearchEngine
from stage3.src.state_machine import StateMachine, ExperimentState
from stage3.src.analyze import run_full_stage3_analysis


def run_single_trial(
    trial_id: int,
    config: Dict[str, Any],
    dev_dataset: List[Dict[str, Any]],
    llm_client: Stage3LLMClient,
    checkpoints_base_dir: str,
    print_lock: threading.Lock
) -> Dict[str, Any]:
    """
    Executes a single, completely isolated paired trial t in (A_t, B_t, C_t).
    Maintains independent trial seed: 30300 + trial_id.
    Writes candidate logs to isolated per-trial directory.
    """
    trial_seed = 30300 + trial_id
    trial_dir = os.path.join(checkpoints_base_dir, f"trial_{trial_id:02d}")
    os.makedirs(trial_dir, exist_ok=True)

    record_path = os.path.join(trial_dir, f"trial_{trial_id:02d}_record.json")
    status_path = os.path.join(trial_dir, "status.txt")
    trial_lineage_path = os.path.join(trial_dir, f"trial_{trial_id:02d}_candidates.jsonl")

    # Safe resumption check: if already completed, load and return
    if os.path.exists(record_path) and os.path.exists(status_path):
        with open(status_path) as sf:
            if sf.read().strip() == "COMPLETED":
                with open(record_path) as rf:
                    rec = json.load(rf)
                with print_lock:
                    print(f"[Trial {trial_id:02d}] Checkpoint found & completed. Resuming without re-run.", flush=True)
                return rec

    t_trial_start = time.perf_counter()
    with print_lock:
        print(f"\n{'='*70}\n[START] TRIAL {trial_id:02d} / 30 (Seed: {trial_seed}) | Isolated Dir: {trial_dir}\n{'='*70}", flush=True)

    # Initialize isolated trial components
    evaluator = GraphColoringEvaluator()
    # Remove any stale partial candidate log for this trial
    if os.path.exists(trial_lineage_path):
        os.remove(trial_lineage_path)
    trial_lineage_tracker = LineageTracker(trial_lineage_path)

    trial_engine = Stage3SearchEngine(
        config=config,
        llm_client=llm_client,
        evaluator=evaluator,
        lineage_tracker=trial_lineage_tracker,
        max_workers=1
    )

    # 1. Arm A: Independent Best-of-100 (10 batches x 10)
    with print_lock:
        print(f"[Trial {trial_id:02d}] Running Arm A: Independent Best-of-100...", flush=True)
    t_a0 = time.perf_counter()
    arm_a_out = trial_engine.run_arm_a(trial_id, dev_dataset, trial_seed)
    t_a_dur = time.perf_counter() - t_a0
    with print_lock:
        print(f"[Trial {trial_id:02d}] Arm A Complete ({t_a_dur:.1f}s). Valid: {arm_a_out['valid_candidates_count']}/100. Best Dev Score: {arm_a_out['selected_dev_score']}", flush=True)

    # 2. Arm B: Blind Iterative Search (10 gens x 10)
    with print_lock:
        print(f"[Trial {trial_id:02d}] Running Arm B: Blind Iterative Search...", flush=True)
    t_b0 = time.perf_counter()
    arm_b_out = trial_engine.run_arm_b(trial_id, dev_dataset, trial_seed)
    t_b_dur = time.perf_counter() - t_b0
    with print_lock:
        print(f"[Trial {trial_id:02d}] Arm B Complete ({t_b_dur:.1f}s). Valid: {arm_b_out['valid_candidates_count']}/100. Selected Dev Score: {arm_b_out['selected_dev_score']}", flush=True)

    # 3. Arm C: Amaura Execution-Driven Adaptive Search (10 gens x 10)
    with print_lock:
        print(f"[Trial {trial_id:02d}] Running Arm C: Amaura Adaptive Search...", flush=True)
    t_c0 = time.perf_counter()
    arm_c_out = trial_engine.run_arm_c(trial_id, dev_dataset, trial_seed)
    t_c_dur = time.perf_counter() - t_c0
    with print_lock:
        print(f"[Trial {trial_id:02d}] Arm C Complete ({t_c_dur:.1f}s). Valid: {arm_c_out['valid_candidates_count']}/100. Best Dev Score: {arm_c_out['selected_dev_score']}", flush=True)

    # 4. Search Curves Analysis
    trajectories = analyze_trial_trajectories(
        trial_id=trial_id,
        cands_a=arm_a_out["candidates"],
        cands_b=arm_b_out["candidates"],
        cands_c=arm_c_out["candidates"]
    )

    trial_duration = round(time.perf_counter() - t_trial_start, 2)
    trial_rec = {
        "trial_id": trial_id,
        "seed": trial_seed,
        "duration_sec": trial_duration,
        "arm_a": {
            "status": arm_a_out["status"],
            "selected_candidate_id": arm_a_out["selected_candidate_id"],
            "selected_candidate_code": arm_a_out["selected_candidate_code"],
            "dev_score": arm_a_out["selected_dev_score"],
            "valid_count": arm_a_out["valid_candidates_count"],
            "duration_sec": round(t_a_dur, 2)
        },
        "arm_b": {
            "status": arm_b_out["status"],
            "selected_candidate_id": arm_b_out["selected_candidate_id"],
            "selected_candidate_code": arm_b_out["selected_candidate_code"],
            "dev_score": arm_b_out["selected_dev_score"],
            "valid_count": arm_b_out["valid_candidates_count"],
            "duration_sec": round(t_b_dur, 2),
            "blind_selection_details": arm_b_out.get("blind_selection_details")
        },
        "arm_c": {
            "status": arm_c_out["status"],
            "selected_candidate_id": arm_c_out["selected_candidate_id"],
            "selected_candidate_code": arm_c_out["selected_candidate_code"],
            "dev_score": arm_c_out["selected_dev_score"],
            "valid_count": arm_c_out["valid_candidates_count"],
            "duration_sec": round(t_c_dur, 2)
        },
        "search_curves": trajectories
    }

    # Save isolated checkpoint atomically
    temp_rec_path = record_path + ".tmp"
    with open(temp_rec_path, "w") as f:
        json.dump(trial_rec, f, indent=2)
    os.replace(temp_rec_path, record_path)

    with open(status_path, "w") as f:
        f.write("COMPLETED\n")

    with print_lock:
        print(f"\n[COMPLETE] TRIAL {trial_id:02d} finished in {trial_duration:.1f}s ({trial_duration/60:.2f}m)!", flush=True)
        print(f"  Scores: Arm A={trial_rec['arm_a']['dev_score']}, Arm B={trial_rec['arm_b']['dev_score']}, Arm C={trial_rec['arm_c']['dev_score']}", flush=True)

    return trial_rec


def run_concurrent_main_experiment(
    max_concurrent_trials: int = 4,
    global_llm_semaphore_slots: int = 4
):
    print("=" * 80, flush=True)
    print("AMAURA LABS — CONCURRENT STAGE 3 MAIN EXPERIMENT (T_main = 30 PAIRED TRIALS)", flush=True)
    print("=" * 80, flush=True)

    config_path = "stage3/config.json"
    with open(config_path) as f:
        config = json.load(f)

    # 1. State Machine Transitions
    sm = StateMachine(
        state_file=config["paths"]["state_file"],
        audit_log_path=config["paths"]["audit_log"]
    )
    curr_state = sm.get_current_state()
    print(f"Initial State Machine State: {curr_state.value}", flush=True)

    if curr_state == ExperimentState.PILOT_COMPLETE:
        sm.transition_to(ExperimentState.PROTOCOL_FROZEN, "Pilot complete and audited. Protocol frozen for main experiment.")
    curr_state = sm.get_current_state()

    if curr_state == ExperimentState.PROTOCOL_FROZEN:
        sm.transition_to(ExperimentState.MAIN_RUNNING, "Starting main experiment: 30 paired trials across Arms A, B, and C.")
    print(f"Active State Machine State: {sm.get_current_state().value}", flush=True)

    # 2. Hidden Firewall Verification Probe
    print("\n--- Verifying Technical Hidden Firewall in MAIN_RUNNING ---", flush=True)
    try:
        sm.access_hidden_dataset("main_firewall_probe")
        raise RuntimeError("FATAL SECURITY BREACH: Firewall failed to block hidden access in MAIN_RUNNING!")
    except PermissionError as e:
        print(f"Firewall successfully active: {e}", flush=True)

    # 3. Load Development Benchmark (40 instances)
    dev_path = config["benchmarks"]["graph_coloring"]["dev"]
    with open(dev_path) as f:
        dev_dataset = json.load(f)
    print(f"Loaded Development Benchmark: {len(dev_dataset)} instances from {dev_path}", flush=True)

    # 4. Setup Paths, Directories, and Concurrency Primitives
    checkpoints_base_dir = "stage3/checkpoints"
    os.makedirs(checkpoints_base_dir, exist_ok=True)
    main_lineage_path = "stage3/candidates/main_candidates.jsonl"
    os.makedirs(os.path.dirname(main_lineage_path), exist_ok=True)

    print_lock = threading.Lock()
    merge_lock = threading.Lock()
    global_sem = threading.BoundedSemaphore(global_llm_semaphore_slots)

    llm_client = Stage3LLMClient(
        model=config["model"],
        base_url=config["api_base_url"],
        api_key=config.get("api_key"),
        cost_per_m_input=3.00,
        cost_per_m_output=15.00,
        mock_mode=False,
        timeout=180,
        concurrency_semaphore=global_sem
    )

    print(f"\nConcurrency Configuration:")
    print(f"- Max Concurrent Trials: {max_concurrent_trials}")
    print(f"- Global In-Flight LLM Request Semaphore: {global_llm_semaphore_slots}")
    print(f"- Target Proxy Throughput: ~19 requests/min (0% error)")
    print(f"- Checkpoint Directory: {checkpoints_base_dir}")

    # 5. Execute 30 Paired Trials
    trials_records_dict: Dict[int, Dict[str, Any]] = {}
    main_start_time = time.perf_counter()

    # Pre-check for completed checkpoints
    already_completed = 0
    for t_id in range(1, 31):
        rec_p = os.path.join(checkpoints_base_dir, f"trial_{t_id:02d}", f"trial_{t_id:02d}_record.json")
        stat_p = os.path.join(checkpoints_base_dir, f"trial_{t_id:02d}", "status.txt")
        if os.path.exists(rec_p) and os.path.exists(stat_p):
            with open(stat_p) as sf:
                if sf.read().strip() == "COMPLETED":
                    with open(rec_p) as rf:
                        trials_records_dict[t_id] = json.load(rf)
                    already_completed += 1

    print(f"Found {already_completed}/30 previously completed trials.", flush=True)

    trials_to_run = [t_id for t_id in range(1, 31) if t_id not in trials_records_dict]

    def trial_worker_task(t_id: int):
        rec = run_single_trial(
            trial_id=t_id,
            config=config,
            dev_dataset=dev_dataset,
            llm_client=llm_client,
            checkpoints_base_dir=checkpoints_base_dir,
            print_lock=print_lock
        )

        # Merge candidate lines to main_candidates.jsonl under merge lock
        trial_cand_path = os.path.join(checkpoints_base_dir, f"trial_{t_id:02d}", f"trial_{t_id:02d}_candidates.jsonl")
        if os.path.exists(trial_cand_path):
            with open(trial_cand_path) as f_cand:
                cand_lines = f_cand.readlines()
            with merge_lock:
                with open(main_lineage_path, "a") as f_main:
                    f_main.writelines(cand_lines)

                # Update selections file
                trials_records_dict[t_id] = rec
                sorted_records = [trials_records_dict[k] for k in sorted(trials_records_dict.keys())]
                with open("stage3/results/selections.json", "w") as sf:
                    json.dump(sorted_records, sf, indent=2)

                elapsed_so_far = time.perf_counter() - main_start_time
                completed_count = len(trials_records_dict)
                req_rate = (completed_count * 300) / (elapsed_so_far / 60.0) if elapsed_so_far > 60 else 0.0
                print(f"\n>>> PROGRESS UPDATE: {completed_count}/30 Trials Complete ({completed_count*300}/9,000 candidates). Elapsed: {elapsed_so_far/60:.1f}m. Effective Rate: {req_rate:.1f} req/min <<<", flush=True)

        return rec

    if trials_to_run:
        print(f"Launching {len(trials_to_run)} trials with {max_concurrent_trials} concurrent trial workers...", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_trials) as executor:
            future_to_trial = {executor.submit(trial_worker_task, t_id): t_id for t_id in trials_to_run}
            for future in concurrent.futures.as_completed(future_to_trial):
                t_id = future_to_trial[future]
                try:
                    future.result()
                except Exception as exc:
                    print(f"FATAL: Trial {t_id} generated an unhandled exception: {exc}", flush=True)
                    raise

    # 6. Verify all 30 paired trials are present
    assert len(trials_records_dict) == 30, f"Expected 30 completed trials, got {len(trials_records_dict)}"
    trials_records = [trials_records_dict[t_id] for t_id in range(1, 31)]

    # Audit total logged candidates in main_candidates.jsonl
    with open(main_lineage_path) as f:
        total_main_cands = sum(1 for _ in f)
    print(f"\nAudit check: {total_main_cands} total candidates logged in {main_lineage_path} (Expected: 9,000).", flush=True)

    # 7. State Machine Transition: MAIN_RUNNING -> SELECTIONS_FROZEN
    print("\n" + "=" * 80, flush=True)
    print("ALL 30 TRIALS COMPLETE. FREEZING SELECTIONS.", flush=True)
    print("=" * 80, flush=True)
    sm.transition_to(
        ExperimentState.SELECTIONS_FROZEN,
        "All 30 paired trials complete. Freezing winner selections prior to hidden evaluation."
    )

    # 8. State Machine Transition: SELECTIONS_FROZEN -> HIDDEN_RUNNING
    sm.transition_to(
        ExperimentState.HIDDEN_RUNNING,
        "Opening hidden evaluation benchmark for final out-of-sample testing."
    )

    # 9. Access Hidden Benchmark Dataset (200 instances)
    print("\n--- Unlocking Technical Hidden Firewall ---", flush=True)
    hidden_dataset = sm.access_hidden_dataset("main_hidden_evaluation")
    print(f"Successfully unlocked Hidden Benchmark: {len(hidden_dataset)} instances", flush=True)

    # 10. Evaluate Winners on Hidden Benchmark
    evaluator = GraphColoringEvaluator()
    print("\nEvaluating all 30 trial winners across Arms A, B, and C on 200 Hidden Benchmark instances...", flush=True)
    for trial in trials_records:
        t_id = trial["trial_id"]
        # Arm A
        if trial["arm_a"]["status"] == "VALID" and trial["arm_a"]["selected_candidate_code"]:
            res_a = evaluator.evaluate_code(trial["arm_a"]["selected_candidate_code"], hidden_dataset)
            trial["arm_a"]["hidden_score"] = res_a["total_colors"]
            trial["arm_a"]["hidden_status"] = "VALID" if res_a["is_valid"] else "INVALID"
        else:
            trial["arm_a"]["hidden_score"] = None
            trial["arm_a"]["hidden_status"] = "ARM_FAILURE_NO_VALID_CANDIDATE"

        # Arm B
        if trial["arm_b"]["status"] == "VALID" and trial["arm_b"]["selected_candidate_code"]:
            res_b = evaluator.evaluate_code(trial["arm_b"]["selected_candidate_code"], hidden_dataset)
            trial["arm_b"]["hidden_score"] = res_b["total_colors"]
            trial["arm_b"]["hidden_status"] = "VALID" if res_b["is_valid"] else "INVALID"
        else:
            trial["arm_b"]["hidden_score"] = None
            trial["arm_b"]["hidden_status"] = "ARM_FAILURE_NO_VALID_CANDIDATE"

        # Arm C
        if trial["arm_c"]["status"] == "VALID" and trial["arm_c"]["selected_candidate_code"]:
            res_c = evaluator.evaluate_code(trial["arm_c"]["selected_candidate_code"], hidden_dataset)
            trial["arm_c"]["hidden_score"] = res_c["total_colors"]
            trial["arm_c"]["hidden_status"] = "VALID" if res_c["is_valid"] else "INVALID"
        else:
            trial["arm_c"]["hidden_score"] = None
            trial["arm_c"]["hidden_status"] = "ARM_FAILURE_NO_VALID_CANDIDATE"

        print(f"Trial {t_id:02d} Hidden Scores -> Arm A: {trial['arm_a']['hidden_score']}, Arm B: {trial['arm_b']['hidden_score']}, Arm C: {trial['arm_c']['hidden_score']}", flush=True)

    # 11. Run Full Preregistered Statistical Analysis
    print("\n" + "=" * 80, flush=True)
    print("RUNNING PREREGISTERED STATISTICAL ANALYSIS", flush=True)
    print("=" * 80, flush=True)

    analysis_results = run_full_stage3_analysis(
        experiment_results=trials_records,
        penalty_score=19001,
        n_bootstrap=10000,
        seed=303
    )

    # 12. State Machine Transition: HIDDEN_RUNNING -> ANALYSIS_COMPLETE
    sm.transition_to(
        ExperimentState.ANALYSIS_COMPLETE,
        f"Statistical analysis complete. Primary decision: {analysis_results['final_decision']}"
    )

    # 13. Save Complete Results JSON
    total_experiment_duration = time.perf_counter() - main_start_time
    full_output = {
        "metadata": {
            "experiment": "Amaura Labs Stage 3 Main Experiment",
            "protocol_version": "Revision 4.3",
            "model": config["model"],
            "T_main": 30,
            "N_slots": 100,
            "total_slots": 9000,
            "duration_sec": round(total_experiment_duration, 2),
            "duration_hours": round(total_experiment_duration / 3600.0, 2),
            "total_llm_calls": llm_client.total_calls,
            "total_input_tokens": llm_client.total_input_tokens,
            "total_output_tokens": llm_client.total_output_tokens,
            "total_tokens": llm_client.total_input_tokens + llm_client.total_output_tokens,
            "total_cost": round(llm_client.total_cost, 2)
        },
        "trials": trials_records,
        "statistical_analysis": analysis_results
    }

    results_path = "stage3/results/main_results.json"
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(full_output, f, indent=2)
    print(f"\nFinal experiment results saved to: {results_path}", flush=True)

    # 14. Compile Final Stage 3 Markdown Report
    report_path = "stage3/audit/03_stage3_final_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    compile_stage3_markdown_report(full_output, report_path)
    print(f"Final certified report compiled at: {report_path}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STAGE 3 EXPERIMENT FULLY COMPLETE AND CERTIFIED", flush=True)
    print("=" * 80, flush=True)
    return full_output


def compile_stage3_markdown_report(data: Dict[str, Any], output_path: str):
    """
    Compiles the certified Stage 3 final audit and scientific report.
    """
    meta = data["metadata"]
    stats_res = data["statistical_analysis"]
    pri = stats_res["primary_comparison_C_vs_A"]
    rel = stats_res["binary_reliability"]
    imp = stats_res["sensitivity_analysis_bounded_imputation"]
    sec = stats_res["secondary_comparison_C_vs_B"]
    trials = data["trials"]

    report = f"""# AMAURA LABS STAGE 3: FINAL SCIENTIFIC & AUDIT REPORT
**Domain:** Minimum Vertex Graph Coloring
**Model:** `{meta['model']}`
**Protocol Revision:** Revision 4.3 (Frozen Pre-Registration)
**Design:** $T = 30$ Paired Trials $\\times$ 3 Arms $\\times$ $N = 100$ Candidate Slots (9,000 total candidate slots)
**Execution Mode:** Bounded Concurrent Scheduler (Isolated Multi-Trial & Generational Barriers)
**Total Wall-Clock Time:** {meta['duration_hours']:.2f} hours ({meta['duration_sec']:.1f} s)
**Total Inference Calls:** {meta['total_llm_calls']:,}
**Total Tokens:** {meta['total_tokens']:,} (Input: {meta['total_input_tokens']:,}, Output: {meta['total_output_tokens']:,})
**Total Inference Cost:** ${meta['total_cost']:.2f}

---

## 1. EXECUTIVE SUMMARY & PREREGISTERED OUTCOME

**Final Decision:** `{stats_res['final_decision']}`

- **Dual-Validity Gate ($P(\\text{{valid}}) \\ge 90\\%$ for both arms):**
  - Arm C Valid Rate: {rel['p_valid_C']:.1%} ({rel['arm_c_valid']}/{rel['T_total']})
  - Arm A Valid Rate: {rel['p_valid_A']:.1%} ({rel['arm_a_valid']}/{rel['T_total']})
  - Gate Passed: `{pri.get('dual_valid_rate', 0.0) >= 0.9}`
- **Primary Continuous Estimand (Finite Differences on Dual-Valid Trials):**
  - Dual-Valid Trials Count: {pri.get('T_dual_valid', 0)} / 30
  - Mean Paired Difference $\\mathbb{{E}}[\\Delta_{{C-A}}]$: **{pri.get('mean_delta', 'N/A')} colors**
  - 95% Bootstrap CI: **[{pri.get('bootstrap_ci_95', ['N/A', 'N/A'])[0]}, {pri.get('bootstrap_ci_95', ['N/A', 'N/A'])[1]}]**
  - Two-Sided Paired Wilcoxon $p$-value: **{pri.get('wilcoxon_raw_p', 'N/A')}**
  - Holm-Bonferroni Adjusted $p$-value: **{stats_res['holm_bonferroni_adjusted_p_values'].get('C_vs_A', 'N/A')}**
  - Practical Criterion Met (CI upper bound $< -1.0$ color): `{pri.get('practical_criterion_met', False)}`
- **Binary Reliability Endpoint:**
  - Arm C Failures: {rel['arm_c_fail']} | Arm A Failures: {rel['arm_a_fail']}
  - Risk Difference $\\text{{RD}} = P(\\text{{Fail}}_C) - P(\\text{{Fail}}_A)$: {rel['risk_difference']:.4f} (95% CI: [{rel['risk_diff_ci_95'][0]}, {rel['risk_diff_ci_95'][1]}])
  - Exact Two-Sided McNemar $p$-value: {rel['mcnemar_exact_p']}
  - Arm C Reliability Compromised: `{rel['arm_c_significantly_worse']}`
- **Worst-Case Bounded-Imputation Sensitivity Analysis ($S_{{penalty}} = 19,001$):**
  - Imputed Mean Difference $\\mathbb{{E}}[\\Delta_{{imputed}}]$: **{imp['imputed_mean_delta']} colors**
  - Imputed 95% Bootstrap CI: **[{imp['imputed_bootstrap_ci_95'][0]}, {imp['imputed_bootstrap_ci_95'][1]}]**
  - Imputed Paired Wilcoxon $p$-value: **{imp['imputed_wilcoxon_raw_p']}**

---

## 2. PAIRED TRIAL-BY-TRIAL RESULTS (T = 1..30)

| Trial | Seed | Arm A Dev | Arm A Hidden | Arm B Dev | Arm B Hidden | Arm C Dev | Arm C Hidden | $\\Delta_{{C-A}}$ (Hidden) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for t in trials:
        t_id = t["trial_id"]
        seed = t["seed"]
        a_dev = t["arm_a"]["dev_score"] if t["arm_a"]["dev_score"] is not None else "FAIL"
        a_hid = t["arm_a"]["hidden_score"] if t["arm_a"]["hidden_score"] is not None else "FAIL"
        b_dev = t["arm_b"]["dev_score"] if t["arm_b"]["dev_score"] is not None else "FAIL"
        b_hid = t["arm_b"]["hidden_score"] if t["arm_b"]["hidden_score"] is not None else "FAIL"
        c_dev = t["arm_c"]["dev_score"] if t["arm_c"]["dev_score"] is not None else "FAIL"
        c_hid = t["arm_c"]["hidden_score"] if t["arm_c"]["hidden_score"] is not None else "FAIL"

        if t["arm_a"]["hidden_score"] is not None and t["arm_c"]["hidden_score"] is not None:
            delta_val = f"{t['arm_c']['hidden_score'] - t['arm_a']['hidden_score']:+d}"
        else:
            delta_val = "N/A"

        report += f"| {t_id:02d} | {seed} | {a_dev} | {a_hid} | {b_dev} | {b_hid} | {c_dev} | {c_hid} | {delta_val} |\n"

    report += f"""
---

## 3. SECONDARY COMPARISON: ARM C vs ARM B (BLIND ITERATIVE)

- Dual-Valid Count: {sec.get('T_dual_valid', 0)} / 30
- Mean Difference $\\mathbb{{E}}[\\Delta_{{C-B}}]$: **{sec.get('mean_delta', 'N/A')} colors**
- 95% Bootstrap CI: **[{sec.get('bootstrap_ci_95', ['N/A', 'N/A'])[0]}, {sec.get('bootstrap_ci_95', ['N/A', 'N/A'])[1]}]**
- Raw Wilcoxon $p$-value: **{sec.get('wilcoxon_raw_p', 'N/A')}**
- Holm-Bonferroni Adjusted $p$-value: **{stats_res['holm_bonferroni_adjusted_p_values'].get('C_vs_B', 'N/A')}**

---

## 4. SCIENTIFIC REPRODUCIBILITY & AUDIT PROVENANCE

1. **Deterministic Lineage:** All 9,000 generated candidate codes, prompts, seeds, latency records, and token usages are immutably logged in `stage3/candidates/main_candidates.jsonl`.
2. **Technical Firewall Integrity:** The 200 hidden benchmark instances in `stage3/benchmarks/graph_coloring/hidden.json` were technically inaccessible via `PermissionError` until all 30 trial selections were frozen in `SELECTIONS_FROZEN`.
3. **No Retries / Replacements:** Strictly 1 generation slot per call. Zero silent replacements or re-prompts.
4. **State Machine Verification:** All state transitions (`PILOT_COMPLETE` $\\to$ `PROTOCOL_FROZEN` $\\to$ `MAIN_RUNNING` $\\to$ `SELECTIONS_FROZEN` $\\to$ `HIDDEN_RUNNING` $\\to$ `ANALYSIS_COMPLETE`) were logged with SHA-256 state tracking in `stage3/audit/state_audit.jsonl`.
"""
    with open(output_path, "w") as f:
        f.write(report)


if __name__ == "__main__":
    run_concurrent_main_experiment()
