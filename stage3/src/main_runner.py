"""
Stage 3: Sequential Main Experiment Orchestrator (T_main = 30 Paired Trials)
=============================================================================
CRITICAL: FROZEN SCIENTIFIC PROTOCOL (Revision 4.3) — STRICTLY SEQUENTIAL EXECUTION.
Concurrency = 1. Exactly one LLM generation request in flight at any moment.

Execution Model:
- T_main = 30 Paired Trials x 3 Arms (A, B, C) = 90 trial runs = 9,000 candidate-generation slots.
- 100 sequential candidate slots per arm per trial.
- Arm A: 100 sequential candidate calls (Independent Best-of-100).
- Arm B: 10 generations x 10 sequential candidate calls (Blind Iterative Search).
  * Strict generational barrier between generations.
  * Candidate i never sees candidate j in the same generation.
- Arm C: 10 generations x 10 sequential candidate calls (Amaura Adaptive Search).
  * Strict generational barrier between generations.
  * Identical frozen 5-field structured JSON feedback packet from prior generation.
- Model: nvidia/nvidia/nemotron-3-super-120b-a12b via local OmniRoute proxy.
- Temperature: 0.7, Max Tokens: 4096.
- Retries = 0, Replacements = 0 (1 candidate slot consumed per attempt).
- Technical Hidden Firewall: strictly blocks hidden.json until selections frozen.
- Checkpointing:
  * After EVERY candidate: logged to stage3/candidates/main_candidates.jsonl.
  * After EVERY generation: state updated.
  * After EVERY trial: checkpoint persisted to stage3/checkpoints/trial_{t:02d}/.
  * Restartable without duplicating slots.
- Post-Experiment:
  * Transitions: MAIN_RUNNING -> SELECTIONS_FROZEN -> HIDDEN_RUNNING -> ANALYSIS_COMPLETE.
  * Hidden Evaluation: 200 instances (hidden.json).
  * Full preregistered analysis (Wilcoxon, 10,000 bootstrap CI, McNemar, S_penalty = 19,001).
  * Compiles certified report: stage3/audit/03_stage3_final_report.md.
"""

import hashlib
import json
import math
import os
import sys
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


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def run_main_experiment():
    print("=" * 80, flush=True)
    print("AMAURA LABS — STAGE 3 MAIN EXPERIMENT (SEQUENTIAL EXECUTION, CONCURRENCY = 1)", flush=True)
    print("=" * 80, flush=True)

    config_path = "stage3/config.json"
    with open(config_path) as f:
        config = json.load(f)

    # -------------------------------------------------------------------------
    # 1. PREFLIGHT INTEGRITY & HASH AUDIT
    # -------------------------------------------------------------------------
    print("\n--- [PREFLIGHT 1/5] Verifying Benchmark Manifest Hashes ---", flush=True)
    with open("stage3/benchmarks/manifest.json") as f:
        b_manifest = json.load(f)

    dev_path = config["benchmarks"]["graph_coloring"]["dev"]
    hidden_path = config["benchmarks"]["graph_coloring"]["hidden"]
    dev_hash = sha256_file(dev_path)
    hidden_hash = sha256_file(hidden_path)

    expected_dev_hash = b_manifest["files"]["graph_coloring_dev"]["sha256"]
    expected_hidden_hash = b_manifest["files"]["graph_coloring_hidden"]["sha256"]
    assert dev_hash == expected_dev_hash, f"Dev benchmark hash mismatch! {dev_hash} != {expected_dev_hash}"
    assert hidden_hash == expected_hidden_hash, f"Hidden benchmark hash mismatch! {hidden_hash} != {expected_hidden_hash}"
    print(f"  [PASS] Dev Benchmark Hash:    {dev_hash}", flush=True)
    print(f"  [PASS] Hidden Benchmark Hash: {hidden_hash}", flush=True)

    print("\n--- [PREFLIGHT 2/5] Verifying Prompt Manifest Hashes ---", flush=True)
    with open("stage3/prompts/manifest.json") as f:
        p_manifest = json.load(f)

    expert_p_file = config["prompts"]["expert_gc"]
    blind_p_file = config["prompts"]["blind_select"]
    expert_hash = sha256_file(expert_p_file)
    blind_hash = sha256_file(blind_p_file)

    assert expert_hash == p_manifest["expert_prompt_gc"]["sha256"], "Expert prompt hash mismatch!"
    assert blind_hash == p_manifest["blind_select_prompt"]["sha256"], "Blind select prompt hash mismatch!"
    print(f"  [PASS] Expert Prompt Hash:       {expert_hash}", flush=True)
    print(f"  [PASS] Blind Select Prompt Hash: {blind_hash}", flush=True)

    # -------------------------------------------------------------------------
    # 2. STATE MACHINE TRANSITION & TECHNICAL HIDDEN FIREWALL PROBE
    # -------------------------------------------------------------------------
    print("\n--- [PREFLIGHT 3/5] State Machine & Technical Hidden Firewall ---", flush=True)
    sm = StateMachine(
        state_file=config["paths"]["state_file"],
        audit_log_path=config["paths"]["audit_log"]
    )
    curr_state = sm.get_current_state()
    print(f"  Initial State Machine State: {curr_state.value}", flush=True)

    if curr_state == ExperimentState.PILOT_COMPLETE:
        sm.transition_to(ExperimentState.PROTOCOL_FROZEN, "Pilot complete and audited. Protocol frozen for main experiment.")
    curr_state = sm.get_current_state()

    if curr_state == ExperimentState.PROTOCOL_FROZEN:
        sm.transition_to(ExperimentState.MAIN_RUNNING, "Starting main experiment: 30 paired trials across Arms A, B, and C sequentially.")
    print(f"  Active State Machine State: {sm.get_current_state().value}", flush=True)

    # Probe firewall in MAIN_RUNNING (must raise PermissionError)
    try:
        sm.access_hidden_dataset("preflight_firewall_probe")
        raise RuntimeError("FATAL SECURITY BREACH: Firewall failed to block hidden access in MAIN_RUNNING!")
    except PermissionError as e:
        print(f"  [PASS] Hidden Firewall Active: {e}", flush=True)

    # -------------------------------------------------------------------------
    # 3. LOAD DEVELOPMENT BENCHMARK (40 instances)
    # -------------------------------------------------------------------------
    print("\n--- [PREFLIGHT 4/5] Loading Development Benchmark ---", flush=True)
    with open(dev_path) as f:
        dev_dataset = json.load(f)
    print(f"  [PASS] Loaded {len(dev_dataset)} Development Graphs from {dev_path}", flush=True)

    # -------------------------------------------------------------------------
    # 4. INITIALIZE COMPONENTS (CONCURRENCY = 1, MAX_WORKERS = 1)
    # -------------------------------------------------------------------------
    print("\n--- [PREFLIGHT 5/5] Initializing Sequential Components ---", flush=True)
    evaluator = GraphColoringEvaluator()
    main_lineage_path = "stage3/candidates/main_candidates.jsonl"
    os.makedirs(os.path.dirname(main_lineage_path), exist_ok=True)
    lineage_tracker = LineageTracker(main_lineage_path)

    llm_client = Stage3LLMClient(
        model=config["model"],
        base_url=config["api_base_url"],
        api_key=config.get("api_key"),
        cost_per_m_input=3.00,
        cost_per_m_output=15.00,
        mock_mode=False,
        timeout=180
    )

    # STRICTLY SEQUENTIAL ENGINE: max_workers = 1
    search_engine = Stage3SearchEngine(
        config=config,
        llm_client=llm_client,
        evaluator=evaluator,
        lineage_tracker=lineage_tracker,
        max_workers=1
    )

    # -------------------------------------------------------------------------
    # FINAL PREFLIGHT SUMMARY (MANDATORY PRINT)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("FINAL PREFLIGHT SUMMARY", flush=True)
    print("=" * 80, flush=True)
    print(f"  * T = 30 paired trials", flush=True)
    print(f"  * N = 100 candidate slots per arm per trial (9,000 slots total)", flush=True)
    print(f"  * sequential mode = TRUE", flush=True)
    print(f"  * concurrency = 1 (exactly one LLM request in flight at any moment)", flush=True)
    print(f"  * retries = 0 (zero retries, zero replacements)", flush=True)
    print(f"  * replacements = 0", flush=True)
    print(f"  * hidden firewall = ACTIVE (blocks hidden.json until selections frozen)", flush=True)
    print(f"  * model ID: {config['model']}", flush=True)
    print(f"  * dev benchmark hash:    {dev_hash}", flush=True)
    print(f"  * hidden benchmark hash: {hidden_hash}", flush=True)
    print(f"  * expert prompt hash:    {expert_hash}", flush=True)
    print(f"  * blind select hash:     {blind_hash}", flush=True)
    print("=" * 80, flush=True)

    # -------------------------------------------------------------------------
    # 5. EXECUTE 30 PAIRED TRIALS SEQUENTIALLY (T = 1..30)
    # -------------------------------------------------------------------------
    checkpoints_base_dir = "stage3/checkpoints"
    os.makedirs(checkpoints_base_dir, exist_ok=True)
    selections_path = "stage3/results/selections.json"
    os.makedirs(os.path.dirname(selections_path), exist_ok=True)

    trials_records: List[Dict[str, Any]] = []
    main_start_time = time.perf_counter()

    for trial_id in range(1, 31):
        trial_seed = 30300 + trial_id
        trial_ckpt_dir = os.path.join(checkpoints_base_dir, f"trial_{trial_id:02d}")
        os.makedirs(trial_ckpt_dir, exist_ok=True)
        trial_rec_path = os.path.join(trial_ckpt_dir, f"trial_{trial_id:02d}_record.json")
        trial_status_path = os.path.join(trial_ckpt_dir, "status.txt")

        # Checkpoint resumption check:
        if os.path.exists(trial_rec_path) and os.path.exists(trial_status_path):
            with open(trial_status_path) as sf:
                if sf.read().strip() == "COMPLETED":
                    with open(trial_rec_path) as rf:
                        existing_rec = json.load(rf)
                    trials_records.append(existing_rec)
                    print(f"\n[Trial {trial_id:02d}/30] Found completed checkpoint. Resumed without re-run.", flush=True)
                    continue

        print(f"\n{'='*70}\nSTARTING MAIN EXPERIMENT TRIAL {trial_id:02d} / 30 (Seed: {trial_seed})\n{'='*70}", flush=True)
        t_trial_start = time.perf_counter()

        # Arm A: Independent Best-of-100 (100 sequential calls)
        print(f"\n[Trial {trial_id:02d}] Running Arm A: Independent Best-of-100 (100 sequential calls)...", flush=True)
        t_a0 = time.perf_counter()
        arm_a_out = search_engine.run_arm_a(trial_id, dev_dataset, trial_seed)
        t_a_dur = time.perf_counter() - t_a0
        print(f"[Trial {trial_id:02d}] Arm A Complete ({t_a_dur:.1f}s). Valid: {arm_a_out['valid_candidates_count']}/100. Best Dev Score: {arm_a_out['selected_dev_score']}", flush=True)

        # Arm B: Blind Iterative Search (10 gens x 10 sequential calls)
        print(f"\n[Trial {trial_id:02d}] Running Arm B: Blind Iterative Search (10 gens x 10 sequential calls)...", flush=True)
        t_b0 = time.perf_counter()
        arm_b_out = search_engine.run_arm_b(trial_id, dev_dataset, trial_seed)
        t_b_dur = time.perf_counter() - t_b0
        print(f"[Trial {trial_id:02d}] Arm B Complete ({t_b_dur:.1f}s). Valid: {arm_b_out['valid_candidates_count']}/100. Selected Dev Score: {arm_b_out['selected_dev_score']}", flush=True)

        # Arm C: Amaura Adaptive Search (10 gens x 10 sequential calls with frozen feedback)
        print(f"\n[Trial {trial_id:02d}] Running Arm C: Amaura Adaptive Search (10 gens x 10 sequential calls)...", flush=True)
        t_c0 = time.perf_counter()
        arm_c_out = search_engine.run_arm_c(trial_id, dev_dataset, trial_seed)
        t_c_dur = time.perf_counter() - t_c0
        print(f"[Trial {trial_id:02d}] Arm C Complete ({t_c_dur:.1f}s). Valid: {arm_c_out['valid_candidates_count']}/100. Best Dev Score: {arm_c_out['selected_dev_score']}", flush=True)

        # Compute best-so-far search curves at checkpoints k in {1, 5, 10, 20, 50, 100}
        trajectories = analyze_trial_trajectories(
            trial_id=trial_id,
            cands_a=arm_a_out["candidates"],
            cands_b=arm_b_out["candidates"],
            cands_c=arm_c_out["candidates"]
        )

        trial_rec = {
            "trial_id": trial_id,
            "seed": trial_seed,
            "duration_sec": round(time.perf_counter() - t_trial_start, 2),
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
            "checkpoints": trajectories
        }
        trials_records.append(trial_rec)

        # Persist trial checkpoint atomically
        tmp_rec_p = trial_rec_path + ".tmp"
        with open(tmp_rec_p, "w") as f:
            json.dump(trial_rec, f, indent=2)
        os.replace(tmp_rec_p, trial_rec_path)

        with open(trial_status_path, "w") as f:
            f.write("COMPLETED\n")

        # Persist selections file after every trial
        selections_payload = [
            {
                "trial_id": t["trial_id"],
                "seed": t["seed"],
                "arm_a": {"status": t["arm_a"]["status"], "selected_id": t["arm_a"]["selected_candidate_id"], "dev_score": t["arm_a"]["dev_score"]},
                "arm_b": {"status": t["arm_b"]["status"], "selected_id": t["arm_b"]["selected_candidate_id"], "dev_score": t["arm_b"]["dev_score"]},
                "arm_c": {"status": t["arm_c"]["status"], "selected_id": t["arm_c"]["selected_candidate_id"], "dev_score": t["arm_c"]["dev_score"]}
            }
            for t in trials_records
        ]
        with open(selections_path, "w") as f:
            json.dump(selections_payload, f, indent=2)

        t_elapsed = time.perf_counter() - main_start_time
        avg_trial_time = t_elapsed / len(trials_records)
        est_rem_sec = avg_trial_time * (30 - len(trials_records))
        print(f"\n--- TRIAL {trial_id:02d}/30 FINISHED ({trial_rec['duration_sec']:.1f}s). Total Elapsed: {t_elapsed/60:.1f}m. Est Remaining: {est_rem_sec/3600:.2f}h ---", flush=True)
        print(f"    Scores: Arm A = {trial_rec['arm_a']['dev_score']} | Arm B = {trial_rec['arm_b']['dev_score']} | Arm C = {trial_rec['arm_c']['dev_score']}", flush=True)

    total_generation_time = time.perf_counter() - main_start_time
    print(f"\nALL 30 TRIALS GENERATED in {total_generation_time/3600:.2f} hours!", flush=True)

    # Audit total candidates logged in main_candidates.jsonl
    with open(main_lineage_path) as f:
        total_main_cands = sum(1 for _ in f)
    print(f"Audit verification: {total_main_cands} total candidates logged in {main_lineage_path} (Expected: 9,000).", flush=True)
    assert total_main_cands == 9000, f"Expected 9,000 candidates, found {total_main_cands}!"

    # -------------------------------------------------------------------------
    # 6. TRANSITION: MAIN_RUNNING -> SELECTIONS_FROZEN
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("FREEZING WINNER SELECTIONS PRIOR TO HIDDEN EVALUATION", flush=True)
    print("=" * 80, flush=True)
    sm.transition_to(
        ExperimentState.SELECTIONS_FROZEN,
        "All 30 paired trials complete. Freezing winner selections prior to hidden evaluation."
    )
    print(f"State Machine transitioned to: {sm.get_current_state().value}", flush=True)

    # -------------------------------------------------------------------------
    # 7. TRANSITION: SELECTIONS_FROZEN -> HIDDEN_RUNNING
    # -------------------------------------------------------------------------
    sm.transition_to(
        ExperimentState.HIDDEN_RUNNING,
        "Selections frozen. Opening technical hidden firewall for evaluation."
    )
    print(f"State Machine transitioned to: {sm.get_current_state().value}", flush=True)

    # -------------------------------------------------------------------------
    # 8. EVALUATE WINNERS ON 200 HIDDEN BENCHMARK INSTANCES
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("HIDDEN BENCHMARK EVALUATION (200 GRAPHS)", flush=True)
    print("=" * 80, flush=True)

    hidden_dataset = sm.access_hidden_dataset("main_hidden_evaluator")
    print(f"Successfully loaded Hidden Benchmark: {len(hidden_dataset)} graphs", flush=True)

    for t in trials_records:
        t_id = t["trial_id"]
        for arm_key in ["arm_a", "arm_b", "arm_c"]:
            arm_data = t[arm_key]
            if arm_data["status"] == "VALID" and arm_data.get("selected_candidate_code"):
                res_hidden = evaluator.evaluate_code(arm_data["selected_candidate_code"], hidden_dataset)
                arm_data["hidden_score"] = res_hidden["total_colors"]
                arm_data["hidden_avg_colors"] = res_hidden["avg_colors"]
                arm_data["hidden_valid"] = res_hidden["is_valid"]
                arm_data["hidden_runtime_ms"] = res_hidden["runtime_ms"]
            else:
                arm_data["hidden_score"] = None
                arm_data["hidden_avg_colors"] = None
                arm_data["hidden_valid"] = False
                arm_data["hidden_runtime_ms"] = 0.0

        print(f"Trial {t_id:02d} Hidden Scores — Arm A: {t['arm_a']['hidden_score']} | Arm B: {t['arm_b']['hidden_score']} | Arm C: {t['arm_c']['hidden_score']}", flush=True)

    # -------------------------------------------------------------------------
    # 9. RUN PREREGISTERED STATISTICAL ANALYSIS (analyze.py)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("PREREGISTERED STATISTICAL ANALYSIS & HYPOTHESIS TESTING", flush=True)
    print("=" * 80, flush=True)

    stats_report = run_full_stage3_analysis(
        experiment_results=trials_records,
        penalty_score=19001,
        n_bootstrap=10000,
        seed=303
    )

    decision_str = stats_report.get("final_classification", stats_report.get("final_decision", "UNKNOWN"))
    print(f"FINAL DECISION: {decision_str}", flush=True)

    # -------------------------------------------------------------------------
    # 10. TRANSITION: HIDDEN_RUNNING -> ANALYSIS_COMPLETE
    # -------------------------------------------------------------------------
    sm.transition_to(
        ExperimentState.ANALYSIS_COMPLETE,
        f"Statistical analysis complete. Final decision: {decision_str}"
    )
    print(f"State Machine transitioned to: {sm.get_current_state().value}", flush=True)

    # -------------------------------------------------------------------------
    # 11. COMPILE RESULTS JSON & CERTIFIED MARKDOWN REPORT
    # -------------------------------------------------------------------------
    final_payload = {
        "metadata": {
            "experiment": "Amaura Labs Stage 3 Main Experiment",
            "protocol_version": "Revision 4.3",
            "execution_mode": "SEQUENTIAL (concurrency = 1)",
            "model": config["model"],
            "T_main": 30,
            "N_slots": 100,
            "total_slots": 9000,
            "total_calls": llm_client.total_calls,
            "total_input_tokens": llm_client.total_input_tokens,
            "total_output_tokens": llm_client.total_output_tokens,
            "total_tokens": llm_client.total_input_tokens + llm_client.total_output_tokens,
            "total_cost_usd": round(llm_client.total_cost, 4),
            "total_runtime_sec": round(time.perf_counter() - main_start_time, 2),
            "total_runtime_hours": round((time.perf_counter() - main_start_time) / 3600.0, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "statistical_analysis": stats_report,
        "trials": [
            {
                "trial_id": t["trial_id"],
                "seed": t["seed"],
                "duration_sec": t["duration_sec"],
                "arm_a": {k: v for k, v in t["arm_a"].items() if k != "selected_candidate_code"},
                "arm_b": {k: v for k, v in t["arm_b"].items() if k != "selected_candidate_code"},
                "arm_c": {k: v for k, v in t["arm_c"].items() if k != "selected_candidate_code"},
                "checkpoints": t["checkpoints"]
            }
            for t in trials_records
        ]
    }

    results_path = "stage3/results/main_results.json"
    with open(results_path, "w") as f:
        json.dump(final_payload, f, indent=2)
    print(f"Results JSON saved to: {results_path}", flush=True)

    report_path = "stage3/audit/03_stage3_final_report.md"
    compile_final_report(final_payload, report_path)
    print(f"Certified Final Report compiled at: {report_path}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STAGE 3 MAIN EXPERIMENT COMPLETED AND CERTIFIED", flush=True)
    print("=" * 80, flush=True)
    return final_payload


def compile_final_report(data: Dict[str, Any], output_path: str):
    meta = data["metadata"]
    stats_res = data.get("statistical_analysis", {})
    pri = stats_res.get("primary_comparison_C_vs_A", {}).get("continuous_dual_valid", {})
    rel = stats_res.get("primary_comparison_C_vs_A", {}).get("binary_reliability", {})
    imp = stats_res.get("primary_comparison_C_vs_A", {}).get("bounded_imputation_sensitivity", {})
    sec = stats_res.get("secondary_comparison_C_vs_B", {}).get("continuous_dual_valid", {})
    adj_p_map = stats_res.get("holm_bonferroni_summary", {}).get("adjusted_p_values", {})
    trials = data.get("trials", [])

    final_dec = stats_res.get("final_classification", stats_res.get("final_decision", "UNKNOWN"))
    p_valid_c = rel.get("Arm_C_valid_rate", 0.0)
    p_valid_a = rel.get("Arm_A_valid_rate", 0.0)
    t_total = stats_res.get("T_trials", len(trials))

    c_table = rel.get("contingency_table", {})
    c_valid_cnt = c_table.get("Arm_C_valid_Arm_A_valid", 0) + c_table.get("Arm_C_valid_Arm_A_fail", 0)
    a_valid_cnt = c_table.get("Arm_C_valid_Arm_A_valid", 0) + c_table.get("Arm_C_fail_Arm_A_valid", 0)
    c_fail_cnt = t_total - c_valid_cnt
    a_fail_cnt = t_total - a_valid_cnt

    rd_val = rel.get("risk_difference_fail_x_minus_y", 0.0)
    rd_ci = rel.get("risk_difference_95_ci", ["N/A", "N/A"])
    mcnemar_p = rel.get("mcnemar_exact_p_value", "N/A")
    rel_fail = rel.get("reliability_failure_triggered", False)

    ci_95 = pri.get("bootstrap_ci_95", ["N/A", "N/A"])
    ci_imp_95 = imp.get("imputed_bootstrap_ci_95", ["N/A", "N/A"])
    sec_ci_95 = sec.get("bootstrap_ci_95", ["N/A", "N/A"])

    report = f"""# AMAURA LABS STAGE 3: CERTIFIED FINAL REPORT
**Domain:** Minimum Vertex Graph Coloring
**Model:** `{meta['model']}`
**Protocol Revision:** Revision 4.3 (Frozen Pre-Registration)
**Execution Mode:** Strictly Sequential (Concurrency = 1, Exactly One In-Flight Request)
**Design:** $T = 30$ Paired Trials $\\times$ 3 Arms $\\times$ $N = 100$ Slots (9,000 Total Candidate Slots)
**Total Wall-Clock Time:** {meta['total_runtime_hours']:.2f} hours ({meta['total_runtime_sec']:.1f} s)
**Total Inference Calls:** {meta['total_calls']:,}
**Total Tokens:** {meta['total_tokens']:,} (Input: {meta['total_input_tokens']:,}, Output: {meta['total_output_tokens']:,})
**Total Inference Cost:** ${meta['total_cost_usd']:.2f}

---

## 1. EXECUTIVE SUMMARY & FINAL DECISION

**Final Preregistered Decision:** `{final_dec}`

### Primary Continuous Endpoint (C vs A on Dual-Valid Trials)
- **Dual-Validity Gate ($P(\\text{{valid}}) \\ge 90\\%$ for both arms):**
  - Arm C Validity: **{p_valid_c:.1%}** ({c_valid_cnt}/{t_total})
  - Arm A Validity: **{p_valid_a:.1%}** ({a_valid_cnt}/{t_total})
  - Gate Passed: `{pri.get('dual_valid_rate', 0.0) >= 0.9}`
- **Dual-Valid Paired Difference $\\Delta_t = \\text{{Score}}_{{C,t}} - \\text{{Score}}_{{A,t}}$:**
  - Dual-Valid Trials Count: **{pri.get('T_dual_valid', 0)} / {t_total}**
  - Mean Paired Difference $\\mathbb{{E}}[\\Delta]$: **{pri.get('mean_delta', 'N/A')} colors**
  - Median Paired Difference: **{pri.get('median_delta', 'N/A')} colors**
  - 95% Bootstrap CI: **[{ci_95[0]}, {ci_95[1]}]**
  - Two-Sided Paired Wilcoxon $p$-value: **{pri.get('wilcoxon_raw_p', 'N/A')}**
  - Holm-Bonferroni Adjusted $p$-value: **{adj_p_map.get('C_vs_A', 'N/A')}**
  - Practical Criterion Met (CI upper bound $< -1.0$ color): `{pri.get('practical_criterion_met', False)}`

### Binary Reliability Endpoint
- Arm C Failures: {c_fail_cnt} | Arm A Failures: {a_fail_cnt}
- Risk Difference $\\text{{RD}} = P(\\text{{Fail}}_C) - P(\\text{{Fail}}_A)$: {rd_val:.4f} (95% CI: [{rd_ci[0]}, {rd_ci[1]}])
- Exact Two-Sided McNemar $p$-value: {mcnemar_p}
- Reliability Failure Triggered: `{rel_fail}`

### Worst-Case Bounded-Imputation Sensitivity Analysis ($S_{{penalty}} = 19,001$)
- Imputed Mean Difference $\\mathbb{{E}}[\\Delta_{{imputed}}]$: **{imp.get('imputed_mean_delta', 'N/A')} colors**
- Imputed 95% Bootstrap CI: **[{ci_imp_95[0]}, {ci_imp_95[1]}]**
- Imputed Paired Wilcoxon $p$-value: **{imp.get('imputed_wilcoxon_raw_p', 'N/A')}**

---

## 2. TRIAL-BY-TRIAL RESULTS (T = 1..30)

| Trial | Seed | Arm A Dev | Arm A Hidden | Arm B Dev | Arm B Hidden | Arm C Dev | Arm C Hidden | $\\Delta_{{C-A}}$ (Hidden) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for t in trials:
        t_id = t["trial_id"]
        seed = t["seed"]
        a_dev = t["arm_a"]["dev_score"] if t["arm_a"]["dev_score"] is not None else "FAIL"
        a_hid = t["arm_a"].get("hidden_score") if t["arm_a"].get("hidden_score") is not None else "FAIL"
        b_dev = t["arm_b"]["dev_score"] if t["arm_b"]["dev_score"] is not None else "FAIL"
        b_hid = t["arm_b"].get("hidden_score") if t["arm_b"].get("hidden_score") is not None else "FAIL"
        c_dev = t["arm_c"]["dev_score"] if t["arm_c"]["dev_score"] is not None else "FAIL"
        c_hid = t["arm_c"].get("hidden_score") if t["arm_c"].get("hidden_score") is not None else "FAIL"

        if t["arm_a"].get("hidden_score") is not None and t["arm_c"].get("hidden_score") is not None:
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
- Holm-Bonferroni Adjusted $p$-value: **{adj_p_map.get('C_vs_B', 'N/A')}**

---

## 4. SCIENTIFIC AUDIT PROVENANCE

1. **Deterministic Lineage:** All 9,000 generated candidate codes, prompts, seeds, latency records, and token usages are immutably logged in `stage3/candidates/main_candidates.jsonl`.
2. **Technical Firewall Integrity:** The 200 hidden benchmark instances were technically blocked via `PermissionError` until all 30 trial selections were frozen in `SELECTIONS_FROZEN`.
3. **Strictly Sequential:** Concurrency = 1. Zero batching, zero concurrent requests, zero hidden retries or replacements.
4. **State Machine Audit:** State transitions logged in `stage3/audit/audit_log.jsonl`.
"""
    with open(output_path, "w") as f:
        f.write(report)


if __name__ == "__main__":
    run_main_experiment()
