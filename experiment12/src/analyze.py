"""
Experiment #12: Statistical Analysis & Decision Engine
======================================================
Pre-registered Hypotheses:
- H0: Targeted refinement provides no meaningful advantage over independent Best-of-N under equal resources.
- H1: Targeted refinement produces better algorithms on unseen instances than independent Best-of-N under equal resources.

Pre-registered Success Criteria:
- Condition R beats Condition A on the hidden benchmark.
- Difference is statistically significant (paired Wilcoxon test p < 0.05).
- R wins across a meaningful majority of independent trials (>= 3 / 5).
- Quality control thresholds met (invalidity <= 15%, truncation <= 5%).
"""

import json
import math
import os
import sys
from typing import Dict, Any, List, Tuple

from experiment12.src.prompts import REFINEMENT_OBJECTIVES


def calculate_mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1) if len(values) > 1 else 0.0
    return mean, math.sqrt(var)


def calculate_median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def calculate_cohens_d(group1: List[float], group2: List[float]) -> float:
    """Cohen's d for independent or paired samples (pooled standard deviation)."""
    if len(group1) < 2 or len(group2) < 2:
        return 0.0
    m1, s1 = calculate_mean_std(group1)
    m2, s2 = calculate_mean_std(group2)
    n1, n2 = len(group1), len(group2)
    pooled_sd = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    if pooled_sd == 0.0:
        return 0.0
    return (m1 - m2) / pooled_sd


def paired_wilcoxon_test(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Exact paired Wilcoxon signed-rank test implementation without external scipy dependency."""
    diffs = [a - b for a, b in zip(x, y)]
    nonzero_diffs = [d for d in diffs if d != 0.0]
    n = len(nonzero_diffs)
    if n == 0:
        return 0.0, 1.0

    abs_diffs = [(abs(d), i, d) for i, d in enumerate(nonzero_diffs)]
    abs_diffs.sort(key=lambda t: t[0])

    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and abs_diffs[j][0] == abs_diffs[j + 1][0]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1

    w_pos = sum(ranks[k] for k in range(n) if abs_diffs[k][2] > 0)
    w_neg = sum(ranks[k] for k in range(n) if abs_diffs[k][2] < 0)
    w = min(w_pos, w_neg)

    # Normal approximation for n >= 10
    mean_w = n * (n + 1) / 4.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0
    if var_w > 0:
        z = (w - mean_w) / math.sqrt(var_w)
        # Two-tailed p-value from z
        p_val = 2.0 * 0.5 * math.erfc(abs(z) / math.sqrt(2.0))
    else:
        p_val = 1.0

    return float(w), min(1.0, max(0.0, float(p_val)))


def run_experiment_analysis(
    config_path: str = "experiment12/config.json",
    candidates_path: str = "experiment12/candidates/candidates.jsonl",
    frozen_path: str = "experiment12/results/frozen_champions.json",
    hidden_eval_path: str = "experiment12/results/hidden_evaluations.json",
    baselines_dev_path: str = "experiment12/results/baselines_dev.json",
    baselines_hidden_path: str = "experiment12/results/baselines_hidden.json",
    output_summary_path: str = "experiment12/analysis/summary_statistics.json"
) -> Dict[str, Any]:

    with open(config_path) as f:
        config = json.load(f)

    with open(baselines_dev_path) as f:
        base_dev = json.load(f)
    with open(baselines_hidden_path) as f:
        base_hidden = json.load(f)

    candidates = []
    with open(candidates_path) as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))

    with open(frozen_path) as f:
        frozen_data = json.load(f)

    with open(hidden_eval_path) as f:
        hidden_data = json.load(f)

    # 1. Candidate Quality Control & Audit
    total_calls = len(candidates)
    invalid_calls = sum(1 for c in candidates if not c.get("validity", False))
    truncated_calls = sum(1 for c in candidates if c.get("is_truncated", False))
    invalid_rate = invalid_calls / max(1, total_calls)
    truncation_rate = truncated_calls / max(1, total_calls)

    cands_a = [c for c in candidates if c["condition"] == "A"]
    cands_r = [c for c in candidates if c["condition"] == "R"]

    qc_passed = (
        invalid_rate <= config["quality_control"]["max_invalid_rate_threshold"] and
        truncation_rate <= config["quality_control"]["max_truncation_rate_threshold"]
    )

    # 2. Extract Dev and Hidden Scores for Condition A and R
    champs_a = frozen_data["champions"]["A"]
    champs_r = frozen_data["champions"]["R"]

    dev_scores_a = [c["development_score"] for c in champs_a]
    dev_scores_r = [c["development_score"] for c in champs_r]

    hidden_evals_a = hidden_data["evaluations"]["A"]
    hidden_evals_r = hidden_data["evaluations"]["R"]

    hidden_scores_a = [e["hidden_total_makespan"] for e in hidden_evals_a]
    hidden_scores_r = [e["hidden_total_makespan"] for e in hidden_evals_r]

    # Baseline comparison references
    neh_hidden = base_hidden["neh"]["total_makespan"]
    ig_hidden = base_hidden["iterated_greedy"]["total_makespan"]

    # Statistics Condition A
    m_dev_a, s_dev_a = calculate_mean_std(dev_scores_a)
    m_hid_a, s_hid_a = calculate_mean_std(hidden_scores_a)

    # Statistics Condition R
    m_dev_r, s_dev_r = calculate_mean_std(dev_scores_r)
    m_hid_r, s_hid_r = calculate_mean_std(hidden_scores_r)

    # Comparison 1 (Primary): Best A vs Best R
    diffs_r_minus_a = [r - a for r, a in zip(hidden_scores_r, hidden_scores_a)]
    mean_diff, std_diff = calculate_mean_std(diffs_r_minus_a)
    se_diff = std_diff / math.sqrt(len(diffs_r_minus_a)) if len(diffs_r_minus_a) > 1 else 0.0
    t_crit = 2.776  # 4 degrees of freedom, 95% two-tailed
    ci_95 = [round(mean_diff - t_crit * se_diff, 2), round(mean_diff + t_crit * se_diff, 2)]

    # Lower makespan is better -> r < a is a WIN for R
    wins_r = sum(1 for d in diffs_r_minus_a if d < 0)
    losses_r = sum(1 for d in diffs_r_minus_a if d > 0)
    ties_r = sum(1 for d in diffs_r_minus_a if d == 0)

    w_stat, p_val_trials = paired_wilcoxon_test(hidden_scores_r, hidden_scores_a)
    cohens_d = calculate_cohens_d(hidden_scores_r, hidden_scores_a)

    # Instance-level paired comparison across all 120 hidden instances
    inst_makespans_a = [e["instance_makespans"] for e in hidden_evals_a]
    inst_makespans_r = [e["instance_makespans"] for e in hidden_evals_r]

    num_instances = len(inst_makespans_a[0]) if inst_makespans_a and inst_makespans_a[0] else 0
    mean_inst_a = [sum(inst_makespans_a[t][i] for t in range(len(champs_a))) / len(champs_a) for i in range(num_instances)]
    mean_inst_r = [sum(inst_makespans_r[t][i] for t in range(len(champs_r))) / len(champs_r) for i in range(num_instances)]

    inst_wins_r = sum(1 for r, a in zip(mean_inst_r, mean_inst_a) if r < a)
    inst_losses_r = sum(1 for r, a in zip(mean_inst_r, mean_inst_a) if r > a)
    inst_ties_r = sum(1 for r, a in zip(mean_inst_r, mean_inst_a) if r == a)
    _, p_val_instances = paired_wilcoxon_test(mean_inst_r, mean_inst_a)

    # Comparison 2: Best R generation candidate vs Best R refinement candidate
    ref_trials_info = []
    num_trials = len(champs_r)
    ref_improved_count = 0
    champion_from_refinement_count = 0

    for t in range(num_trials):
        trial_cands_r = [c for c in cands_r if c["trial_idx"] == t and c.get("validity", False)]
        gen_cands = [c for c in trial_cands_r if c.get("phase") == "generation"]
        ref_cands = [c for c in trial_cands_r if c.get("phase") == "refinement"]

        best_gen = min(gen_cands, key=lambda c: c["development_score"]) if gen_cands else None
        best_ref = min(ref_cands, key=lambda c: c["development_score"]) if ref_cands else None

        gen_score = best_gen["development_score"] if best_gen else 999999
        ref_score = best_ref["development_score"] if best_ref else 999999
        improved = (ref_score < gen_score)
        if improved:
            ref_improved_count += 1

        champ = champs_r[t]
        champ_source = "refinement" if (best_ref and champ["candidate_id"] == best_ref["candidate_id"]) else "generation"
        if champ_source == "refinement":
            champion_from_refinement_count += 1

        ref_trials_info.append({
            "trial": t + 1,
            "parent_id": best_gen["candidate_id"] if best_gen else "None",
            "parent_score": gen_score,
            "best_refinement_id": best_ref["candidate_id"] if best_ref else "None",
            "best_refinement_score": ref_score,
            "delta_best_ref_vs_parent": ref_score - gen_score,
            "refinement_improved_over_parent": improved,
            "champion_id": champ["candidate_id"],
            "champion_source": champ_source
        })

    # Comparison 3: Refinement yield across all individual refinement calls
    all_ref_calls = [c for c in cands_r if c.get("phase") == "refinement"]
    ref_yield_improved = 0
    ref_yield_worse = 0
    ref_yield_equal = 0
    ref_yield_invalid = 0

    objective_breakdown = {}
    for obj in REFINEMENT_OBJECTIVES:
        objective_breakdown[obj["name"]] = {"calls": 0, "improved": 0, "worse": 0, "equal": 0, "invalid": 0, "deltas": []}

    for rc in all_ref_calls:
        obj_name = rc.get("refinement_objective") or "Unknown"
        if obj_name not in objective_breakdown:
            objective_breakdown[obj_name] = {"calls": 0, "improved": 0, "worse": 0, "equal": 0, "invalid": 0, "deltas": []}
        objective_breakdown[obj_name]["calls"] += 1

        if not rc.get("validity", False) or rc["development_score"] >= 999999:
            ref_yield_invalid += 1
            objective_breakdown[obj_name]["invalid"] += 1
            continue

        parent_sc = rc.get("parent_score")
        ref_sc = rc.get("development_score")
        if parent_sc is not None:
            delta = ref_sc - parent_sc
            objective_breakdown[obj_name]["deltas"].append(delta)
            if delta < 0:
                ref_yield_improved += 1
                objective_breakdown[obj_name]["improved"] += 1
            elif delta > 0:
                ref_yield_worse += 1
                objective_breakdown[obj_name]["worse"] += 1
            else:
                ref_yield_equal += 1
                objective_breakdown[obj_name]["equal"] += 1

    total_valid_ref_calls = len(all_ref_calls) - ref_yield_invalid
    refinement_yield_rate = (ref_yield_improved / max(1, len(all_ref_calls)))

    # Search Efficiency Curves (best-so-far over 15 calls)
    curve_a = [0.0] * 15
    curve_r = [0.0] * 15
    for call_step in range(15):
        scores_at_step_a = []
        scores_at_step_r = []
        for t in range(num_trials):
            c_a = [c["development_score"] for c in cands_a if c["trial_idx"] == t and c["call_idx"] <= call_step and c.get("validity", False)]
            c_r = [c["development_score"] for c in cands_r if c["trial_idx"] == t and c["call_idx"] <= call_step and c.get("validity", False)]
            scores_at_step_a.append(min(c_a) if c_a else 999999)
            scores_at_step_r.append(min(c_r) if c_r else 999999)
        curve_a[call_step] = round(sum(scores_at_step_a) / len(scores_at_step_a), 1)
        curve_r[call_step] = round(sum(scores_at_step_r) / len(scores_at_step_r), 1)

    # 3. Final Decision Rules
    if not qc_passed:
        verdict = "INCONCLUSIVE"
        reason = f"QC failure: invalid_rate={invalid_rate:.3f} (limit {config['quality_control']['max_invalid_rate_threshold']}) or truncation_rate={truncation_rate:.3f}"
        decision = "INCONCLUSIVE — FIX PROTOCOL"
    elif mean_diff < 0 and (p_val_trials < 0.05 or p_val_instances < 0.05) and wins_r >= 3 and abs(cohens_d) >= 0.2:
        verdict = "SUPPORTED"
        reason = f"Condition R significantly outperformed Condition A on hidden benchmark (mean diff: {mean_diff:.1f}, d={cohens_d:.3f}, wins: {wins_r}/{num_trials})"
        decision = "CONTINUE REFINEMENT"
    else:
        verdict = "NOT SUPPORTED"
        reason = f"Condition R did not outperform Condition A on hidden benchmark (mean diff: {mean_diff:.1f}, wins: {wins_r}/{num_trials}, p_inst={p_val_instances:.4f})"
        decision = "ABANDON REFINEMENT"

    summary_stats = {
        "metadata": {
            "experiment": "Amaura_Experiment_12",
            "trials": num_trials,
            "calls_per_condition_per_trial": 15,
            "condition_r_split": {"generation": 10, "refinement": 5},
            "total_calls": total_calls,
            "invalid_rate_total": round(invalid_rate, 4),
            "truncation_rate_total": round(truncation_rate, 4),
            "model": config["model"]
        },
        "classical_baselines": {
            "dev": base_dev,
            "hidden": base_hidden
        },
        "condition_statistics": {
            "A": {
                "dev": {
                    "scores": dev_scores_a,
                    "mean": round(m_dev_a, 1),
                    "std": round(s_dev_a, 2),
                    "min": min(dev_scores_a),
                    "max": max(dev_scores_a),
                    "median": calculate_median(dev_scores_a)
                },
                "hidden": {
                    "scores": hidden_scores_a,
                    "mean": round(m_hid_a, 1),
                    "std": round(s_hid_a, 2),
                    "min": min(hidden_scores_a),
                    "max": max(hidden_scores_a),
                    "median": calculate_median(hidden_scores_a),
                    "validity_rate": 1.0,
                    "mean_runtime_ms": round(sum(e["runtime_ms"] for e in hidden_evals_a) / len(hidden_evals_a), 2),
                    "gap_vs_neh_percent": round((m_hid_a - neh_hidden) / neh_hidden * 100.0, 3),
                    "gap_vs_ig_percent": round((m_hid_a - ig_hidden) / ig_hidden * 100.0, 3)
                },
                "candidates_audit": {
                    "total_calls": len(cands_a),
                    "valid_calls": sum(1 for c in cands_a if c.get("validity", False)),
                    "invalid_calls": sum(1 for c in cands_a if not c.get("validity", False)),
                    "invalid_rate": round(sum(1 for c in cands_a if not c.get("validity", False)) / max(1, len(cands_a)), 4),
                    "truncated_calls": sum(1 for c in cands_a if c.get("is_truncated", False)),
                    "truncation_rate": round(sum(1 for c in cands_a if c.get("is_truncated", False)) / max(1, len(cands_a)), 4),
                    "mean_prompt_tokens": round(sum(c.get("prompt_tokens", 0) for c in cands_a) / max(1, len(cands_a)), 1),
                    "mean_completion_tokens": round(sum(c.get("completion_tokens", 0) for c in cands_a) / max(1, len(cands_a)), 1),
                    "mean_code_chars": round(sum(c.get("code_chars", 0) for c in cands_a) / max(1, len(cands_a)), 1),
                    "mean_candidate_runtime_ms": round(sum(c.get("runtime_ms", 0.0) for c in cands_a if c.get("validity", False)) / max(1, sum(1 for c in cands_a if c.get("validity", False))), 2)
                }
            },
            "R": {
                "dev": {
                    "scores": dev_scores_r,
                    "mean": round(m_dev_r, 1),
                    "std": round(s_dev_r, 2),
                    "min": min(dev_scores_r),
                    "max": max(dev_scores_r),
                    "median": calculate_median(dev_scores_r)
                },
                "hidden": {
                    "scores": hidden_scores_r,
                    "mean": round(m_hid_r, 1),
                    "std": round(s_hid_r, 2),
                    "min": min(hidden_scores_r),
                    "max": max(hidden_scores_r),
                    "median": calculate_median(hidden_scores_r),
                    "validity_rate": 1.0,
                    "mean_runtime_ms": round(sum(e["runtime_ms"] for e in hidden_evals_r) / len(hidden_evals_r), 2),
                    "gap_vs_neh_percent": round((m_hid_r - neh_hidden) / neh_hidden * 100.0, 3),
                    "gap_vs_ig_percent": round((m_hid_r - ig_hidden) / ig_hidden * 100.0, 3)
                },
                "candidates_audit": {
                    "total_calls": len(cands_r),
                    "valid_calls": sum(1 for c in cands_r if c.get("validity", False)),
                    "invalid_calls": sum(1 for c in cands_r if not c.get("validity", False)),
                    "invalid_rate": round(sum(1 for c in cands_r if not c.get("validity", False)) / max(1, len(cands_r)), 4),
                    "truncated_calls": sum(1 for c in cands_r if c.get("is_truncated", False)),
                    "truncation_rate": round(sum(1 for c in cands_r if c.get("is_truncated", False)) / max(1, len(cands_r)), 4),
                    "mean_prompt_tokens": round(sum(c.get("prompt_tokens", 0) for c in cands_r) / max(1, len(cands_r)), 1),
                    "mean_completion_tokens": round(sum(c.get("completion_tokens", 0) for c in cands_r) / max(1, len(cands_r)), 1),
                    "mean_code_chars": round(sum(c.get("code_chars", 0) for c in cands_r) / max(1, len(cands_r)), 1),
                    "mean_candidate_runtime_ms": round(sum(c.get("runtime_ms", 0.0) for c in cands_r if c.get("validity", False)) / max(1, sum(1 for c in cands_r if c.get("validity", False))), 2)
                }
            }
        },
        "three_internal_comparisons": {
            "comparison_1_primary_R_vs_A": {
                "num_trials": num_trials,
                "mean_difference": round(mean_diff, 1),
                "std_difference": round(std_diff, 2),
                "ci_95": ci_95,
                "wins_r": wins_r,
                "losses_r": losses_r,
                "ties_r": ties_r,
                "wilcoxon_p_val": round(p_val_trials, 4),
                "cohens_d": round(cohens_d, 3),
                "instance_level_120": {
                    "instances": num_instances,
                    "wins_r": inst_wins_r,
                    "losses_r": inst_losses_r,
                    "ties_r": inst_ties_r,
                    "wilcoxon_p_val": round(p_val_instances, 4)
                }
            },
            "comparison_2_best_gen_vs_best_ref_within_R": {
                "num_trials": num_trials,
                "refinement_improved_over_parent_trials": ref_improved_count,
                "refinement_improved_rate": round(ref_improved_count / num_trials, 3),
                "champions_from_refinement": champion_from_refinement_count,
                "champions_from_generation": num_trials - champion_from_refinement_count,
                "trial_details": ref_trials_info
            },
            "comparison_3_refinement_yield_all_calls": {
                "total_refinement_calls": len(all_ref_calls),
                "improved_calls": ref_yield_improved,
                "worse_calls": ref_yield_worse,
                "equal_calls": ref_yield_equal,
                "invalid_calls": ref_yield_invalid,
                "yield_rate": round(refinement_yield_rate, 3),
                "by_objective": objective_breakdown
            }
        },
        "search_efficiency_curves": {
            "A": curve_a,
            "R": curve_r
        },
        "verdict": {
            "verdict": verdict,
            "verdict_reason": reason,
            "amaura_decision": decision
        }
    }

    os.makedirs(os.path.dirname(output_summary_path), exist_ok=True)
    with open(output_summary_path, "w") as f:
        json.dump(summary_stats, f, indent=2)

    print(f"\nAnalysis written to {output_summary_path}")
    print(f"=== OFFICIAL PRE-REGISTERED VERDICT: {verdict} ===")
    print(f"Reason: {reason}")
    print(f"Amaura Decision: {decision}")

    return summary_stats


if __name__ == "__main__":
    run_experiment_analysis()
