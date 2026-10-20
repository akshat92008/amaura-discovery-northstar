"""
Experiment #11: Comprehensive Statistical & Behavioral Analysis
===============================================================
Computes:
1. Primary Metric: Total Hidden PFSP Makespan (C vs A)
2. Search-level (N=5) and Instance-level (N=120) Paired Wilcoxon signed-rank tests
3. Effect sizes (Cohen's d) and 95% Confidence Intervals
4. Fairness audit (tokens, code size, runtimes, timeouts, truncations)
5. QD Archive behavioral diversity audit (Kendall tau metric)
6. Search efficiency curves across calls 1-15
7. Pre-registered Verdict determination (SUPPORTED, NOT SUPPORTED, INCONCLUSIVE)
8. Amaura Strategic Decision (CONTINUE QD, CHANGE QD, ABANDON QD, FIX PROTOCOL AND REPEAT)
"""

import json
import math
import os
import sys
from typing import Dict, Any, List, Tuple
import numpy as np
from scipy import stats

from experiment11.src.kendall import mean_behavioral_distance


def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def analyze_experiment11():
    config = load_json("experiment11/config.json")
    baselines_dev = load_json("experiment11/results/baselines_dev.json")
    baselines_hidden = load_json("experiment11/results/baselines_hidden.json")
    frozen_champs = load_json("experiment11/results/frozen_champions.json")
    hidden_evals = load_json("experiment11/results/hidden_evaluations.json")

    # Load candidates
    candidates = []
    with open("experiment11/candidates/candidates.jsonl") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line.strip()))

    # Load LLM calls
    llm_calls = []
    with open("experiment11/logs/llm_calls.jsonl") as f:
        for line in f:
            if line.strip():
                llm_calls.append(json.loads(line.strip()))

    conditions = ["A", "C"]
    num_trials = config.get("num_trials", 5)

    # ---------------------------------------------------------
    # 1. Condition Statistics (Dev and Hidden)
    # ---------------------------------------------------------
    cond_stats = {}
    for cond in conditions:
        dev_scores = [c["development_score"] for c in frozen_champs["champions"][cond]]
        hidden_recs = hidden_evals["evaluations"][cond]
        hidden_scores = [r["hidden_total_makespan"] for r in hidden_recs]
        valid_recs = [r for r in hidden_recs if r["validity"]]

        cond_candidates = [c for c in candidates if c["condition"] == cond]
        valid_cands = [c for c in cond_candidates if c["validity"] and c["development_score"] < 999999]
        truncated_cands = [c for c in cond_candidates if c.get("is_truncated", False)]

        cond_calls = [call for call in llm_calls if call["condition"] == cond]
        mean_p_tokens = np.mean([call["prompt_tokens"] for call in cond_calls]) if cond_calls else 0.0
        mean_c_tokens = np.mean([call["completion_tokens"] for call in cond_calls]) if cond_calls else 0.0
        mean_code_chars = np.mean([c.get("code_chars", len(c.get("code", ""))) for c in cond_candidates]) if cond_candidates else 0.0

        neh_hidden_ms = baselines_hidden["neh"]["total_makespan"]
        ig_hidden_ms = baselines_hidden["iterated_greedy"]["total_makespan"]

        cond_stats[cond] = {
            "dev": {
                "scores": dev_scores,
                "mean": float(np.mean(dev_scores)),
                "std": float(np.std(dev_scores, ddof=1)) if len(dev_scores) > 1 else 0.0,
                "min": int(np.min(dev_scores)),
                "max": int(np.max(dev_scores)),
                "median": float(np.median(dev_scores))
            },
            "hidden": {
                "scores": hidden_scores,
                "mean": float(np.mean(hidden_scores)),
                "std": float(np.std(hidden_scores, ddof=1)) if len(hidden_scores) > 1 else 0.0,
                "min": int(np.min(hidden_scores)),
                "max": int(np.max(hidden_scores)),
                "median": float(np.median(hidden_scores)),
                "validity_rate": len(valid_recs) / len(hidden_recs) if hidden_recs else 0.0,
                "mean_runtime_ms": float(np.mean([r["runtime_ms"] for r in hidden_recs])),
                "gap_vs_neh_percent": round(((np.mean(hidden_scores) - neh_hidden_ms) / neh_hidden_ms) * 100, 3),
                "gap_vs_ig_percent": round(((np.mean(hidden_scores) - ig_hidden_ms) / ig_hidden_ms) * 100, 3)
            },
            "candidates_audit": {
                "total_calls": len(cond_candidates),
                "valid_calls": len(valid_cands),
                "invalid_calls": len(cond_candidates) - len(valid_cands),
                "invalid_rate": round(1.0 - (len(valid_cands) / len(cond_candidates)), 4) if cond_candidates else 0.0,
                "truncated_calls": len(truncated_cands),
                "truncation_rate": round(len(truncated_cands) / len(cond_candidates), 4) if cond_candidates else 0.0,
                "mean_prompt_tokens": float(mean_p_tokens),
                "mean_completion_tokens": float(mean_c_tokens),
                "mean_code_chars": float(mean_code_chars),
                "mean_candidate_runtime_ms": float(np.mean([c["runtime_ms"] for c in valid_cands])) if valid_cands else 0.0
            }
        }

    # ---------------------------------------------------------
    # 2. Primary Hypothesis Test: C vs A
    # ---------------------------------------------------------
    scores_a = cond_stats["A"]["hidden"]["scores"]
    scores_c = cond_stats["C"]["hidden"]["scores"]

    # Trial-level Wilcoxon (N=5)
    diffs = [c - a for c, a in zip(scores_c, scores_a)]
    wins_c = sum(1 for d in diffs if d < 0)
    losses_c = sum(1 for d in diffs if d > 0)
    ties_c = sum(1 for d in diffs if d == 0)

    try:
        w_stat, p_val_trial = stats.wilcoxon(scores_c, scores_a, alternative="two-sided")
    except Exception:
        p_val_trial = 1.0

    mean_diff = float(np.mean(diffs))
    std_diff = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
    pooled_std = math.sqrt(0.5 * (cond_stats["A"]["hidden"]["std"]**2 + cond_stats["C"]["hidden"]["std"]**2)) if (cond_stats["A"]["hidden"]["std"] + cond_stats["C"]["hidden"]["std"]) > 0 else 1.0
    cohens_d = (cond_stats["C"]["hidden"]["mean"] - cond_stats["A"]["hidden"]["mean"]) / pooled_std if pooled_std > 0 else 0.0

    # 95% Confidence Interval for mean difference (Student's t, df=4)
    t_crit = stats.t.ppf(0.975, df=4)
    se_diff = std_diff / math.sqrt(num_trials) if std_diff > 0 else 0.0
    ci_95 = [round(mean_diff - t_crit * se_diff, 2), round(mean_diff + t_crit * se_diff, 2)]

    # Instance-level paired differences across 120 hidden instances
    # Compare pooled or trial-by-trial instance makespans
    inst_makespans_a = [r["instance_makespans"] for r in hidden_evals["evaluations"]["A"] if r["validity"]]
    inst_makespans_c = [r["instance_makespans"] for r in hidden_evals["evaluations"]["C"] if r["validity"]]

    inst_p_val = 1.0
    inst_wins_c = 0
    inst_losses_c = 0
    inst_ties_c = 0

    if inst_makespans_a and inst_makespans_c:
        # Use mean makespan per instance across trials
        mean_inst_a = np.mean(inst_makespans_a, axis=0)
        mean_inst_c = np.mean(inst_makespans_c, axis=0)
        try:
            _, inst_p_val = stats.wilcoxon(mean_inst_c, mean_inst_a, alternative="two-sided")
        except Exception:
            inst_p_val = 1.0

        for ca, cc in zip(mean_inst_a, mean_inst_c):
            if cc < ca:
                inst_wins_c += 1
            elif cc > ca:
                inst_losses_c += 1
            else:
                inst_ties_c += 1

    # ---------------------------------------------------------
    # 3. Search Efficiency Curves (Calls 1-15)
    # ---------------------------------------------------------
    search_curves = {}
    for cond in conditions:
        matrix = []
        for t_idx in range(num_trials):
            c_trial = [c for c in candidates if c["condition"] == cond and c["trial_idx"] == t_idx]
            c_trial.sort(key=lambda x: x["call_idx"])
            best_so_far = float("inf")
            trial_curve = []
            for c in c_trial:
                if c["validity"] and c["development_score"] < best_so_far:
                    best_so_far = c["development_score"]
                trial_curve.append(best_so_far)
            matrix.append(trial_curve)

        min_len = min(len(m) for m in matrix) if matrix else 0
        mean_curve = [round(float(np.mean([matrix[t][i] for t in range(num_trials)])), 1) for i in range(min_len)]
        search_curves[cond] = mean_curve

    # ---------------------------------------------------------
    # 4. QD Archive Diversity Analysis (Kendall tau)
    # ---------------------------------------------------------
    diversity_stats = {}
    for cond in conditions:
        trial_diversities = []
        for t_idx in range(num_trials):
            c_valid = [c for c in candidates if c["condition"] == cond and c["trial_idx"] == t_idx and c["validity"] and c["development_score"] < 999999]
            if len(c_valid) > 1:
                pw_dists = []
                for i in range(len(c_valid)):
                    for j in range(i + 1, len(c_valid)):
                        pw_dists.append(mean_behavioral_distance(c_valid[i]["behavior_signature"], c_valid[j]["behavior_signature"]))
                trial_diversities.append(float(np.mean(pw_dists)))
            else:
                trial_diversities.append(0.0)

        diversity_stats[cond] = {
            "mean_pairwise_kendall": float(np.mean(trial_diversities)),
            "std": float(np.std(trial_diversities, ddof=1)) if len(trial_diversities) > 1 else 0.0
        }

    # ---------------------------------------------------------
    # 5. Pre-registered Verdict & Decision Logic
    # ---------------------------------------------------------
    max_inv_thresh = config.get("quality_control", {}).get("max_invalid_rate_threshold", 0.15)
    max_trunc_thresh = config.get("quality_control", {}).get("max_truncation_rate_threshold", 0.05)

    tot_calls = len(candidates)
    tot_invalid = sum(1 for c in candidates if not c["validity"] or c["development_score"] >= 999999)
    tot_truncated = sum(1 for c in candidates if c.get("is_truncated", False))

    overall_inv_rate = tot_invalid / tot_calls if tot_calls > 0 else 0.0
    overall_trunc_rate = tot_truncated / tot_calls if tot_calls > 0 else 0.0

    validity_pass = (overall_inv_rate <= max_inv_thresh) and (overall_trunc_rate <= max_trunc_thresh)
    hidden_valid_a = cond_stats["A"]["hidden"]["validity_rate"] == 1.0
    hidden_valid_c = cond_stats["C"]["hidden"]["validity_rate"] == 1.0

    archive_functioning = diversity_stats["C"]["mean_pairwise_kendall"] >= 0.18

    # Primary Decision logic
    if not validity_pass or not hidden_valid_a or not hidden_valid_c:
        verdict = "INCONCLUSIVE"
        reasons = []
        if overall_inv_rate > max_inv_thresh:
            reasons.append(f"Candidate invalidity rate ({overall_inv_rate*100:.1f}%) exceeded threshold ({max_inv_thresh*100:.1f}%)")
        if overall_trunc_rate > max_trunc_thresh:
            reasons.append(f"Candidate truncation rate ({overall_trunc_rate*100:.1f}%) exceeded threshold ({max_trunc_thresh*100:.1f}%)")
        if not hidden_valid_a:
            reasons.append("Condition A champions encountered invalidity/timeouts on hidden benchmark")
        if not hidden_valid_c:
            reasons.append("Condition C champions encountered invalidity/timeouts on hidden benchmark")
        verdict_reason = "; ".join(reasons)
        amaura_decision = "FIX PROTOCOL AND REPEAT"

    elif mean_diff < 0 and wins_c > losses_c and archive_functioning:
        # Quality-Diversity wins
        if p_val_trial < 0.10 or inst_p_val < 0.05:
            verdict = "SUPPORTED"
            verdict_reason = f"Condition C significantly outperformed Condition A on hidden benchmark (mean diff: {mean_diff:.1f}, Cohen's d: {cohens_d:.2f}, wins: {wins_c}/{num_trials})"
            amaura_decision = "CONTINUE QD"
        else:
            verdict = "NOT SUPPORTED"
            verdict_reason = f"Condition C did not achieve statistical significance over Condition A (p={p_val_trial:.3f})"
            amaura_decision = "CHANGE QD"

    else:
        verdict = "NOT SUPPORTED"
        verdict_reason = f"Condition C did not outperform Condition A on hidden benchmark (mean diff: {mean_diff:.1f}, wins: {wins_c}/{num_trials})"
        amaura_decision = "ABANDON QD"

    # Assemble summary record
    summary = {
        "metadata": {
            "experiment": config.get("experiment_id", "Amaura_Experiment_11"),
            "trials": num_trials,
            "calls_per_condition_per_trial": config.get("calls_per_condition_per_trial", 15),
            "total_calls": tot_calls,
            "invalid_rate_total": round(overall_inv_rate, 4),
            "truncation_rate_total": round(overall_trunc_rate, 4),
            "model": config.get("model")
        },
        "classical_baselines": {
            "dev": baselines_dev,
            "hidden": baselines_hidden
        },
        "condition_statistics": cond_stats,
        "primary_hypothesis_test_C_vs_A": {
            "search_trials": {
                "num_trials": num_trials,
                "mean_difference": round(mean_diff, 2),
                "std_difference": round(std_diff, 2),
                "ci_95": ci_95,
                "wins_c": wins_c,
                "losses_c": losses_c,
                "ties_c": ties_c,
                "wilcoxon_p_val": round(float(p_val_trial), 4),
                "cohens_d": round(float(cohens_d), 3)
            },
            "instance_level_120": {
                "instances": 120,
                "wins_c": inst_wins_c,
                "losses_c": inst_losses_c,
                "ties_c": inst_ties_c,
                "wilcoxon_p_val": round(float(inst_p_val), 5)
            }
        },
        "search_efficiency_curves": search_curves,
        "diversity_analysis": diversity_stats,
        "verdict": {
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "amaura_decision": amaura_decision
        }
    }

    out_path = "experiment11/analysis/summary_statistics.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nAnalysis written to {out_path}")
    print(f"=== OFFICIAL PRE-REGISTERED VERDICT: {verdict} ===")
    print(f"Reason: {verdict_reason}")
    print(f"Amaura Decision: {amaura_decision}")
    return summary


if __name__ == "__main__":
    analyze_experiment11()
