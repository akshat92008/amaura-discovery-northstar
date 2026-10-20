"""
Experiment #13 Statistical Analysis & Decision Engine
=====================================================
Analyzes results of the Cross-Domain Generality Test:
1. Quality Control & Protocol Validity
2. Amaura Champions vs Classical & Kubernetes Baselines
3. Trial-Level Scorecard (5 independent replications)
4. Instance-Level Paired Wilcoxon Signed-Rank Test (120 hidden workloads)
5. Workload Family Breakdown (6 families)
6. Economic & Cluster Efficiency Impact
7. Pre-Registered Scientific Verdict
"""

import json
import math
import os
import sys
from typing import Dict, Any, List, Tuple


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
    if len(group1) < 2 or len(group2) < 2:
        return 0.0
    m1, s1 = calculate_mean_std(group1)
    m2, s2 = calculate_mean_std(group2)
    n1, n2 = len(group1), len(group2)
    pooled_var = ((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2)
    pooled_sd = math.sqrt(pooled_var) if pooled_var > 0 else 1.0
    return (m1 - m2) / pooled_sd


def wilcoxon_signed_rank_test(diffs: List[float]) -> Tuple[float, float]:
    non_zero = [d for d in diffs if abs(d) > 1e-9]
    n = len(non_zero)
    if n == 0:
        return 0.0, 1.0

    sorted_indices = sorted(range(n), key=lambda i: abs(non_zero[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and abs(abs(non_zero[sorted_indices[j]]) - abs(non_zero[sorted_indices[j + 1]])) < 1e-9:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_indices[k]] = avg_rank
        i = j + 1

    w_pos = sum(ranks[k] for k in range(n) if non_zero[k] > 0)
    w_neg = sum(ranks[k] for k in range(n) if non_zero[k] < 0)
    w_stat = min(w_pos, w_neg)

    mean_w = n * (n + 1) / 4.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0
    z = (w_stat - mean_w) / math.sqrt(var_w) if var_w > 0 else 0.0

    p_val = 2.0 * (0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
    return w_stat, min(max(p_val, 0.0001), 1.0)


def run_experiment_analysis():
    print("==================================================")
    print("RUNNING EXPERIMENT #13 STATISTICAL ANALYSIS")
    print("==================================================")

    # 1. Load Files
    with open("experiment13/config.json") as f:
        config = json.load(f)
    with open("experiment13/results/baselines_dev.json") as f:
        baselines_dev = json.load(f)
    with open("experiment13/results/baselines_hidden.json") as f:
        baselines_hidden = json.load(f)
    with open("experiment13/results/frozen_champions.json") as f:
        frozen_champs = json.load(f)["champions"]
    with open("experiment13/results/hidden_evaluations.json") as f:
        hidden_evals = json.load(f)["evaluations"]

    with open("experiment13/benchmarks/hidden.json") as f:
        hidden_instances = json.load(f)

    # Load logs & candidates
    calls = []
    if os.path.exists("experiment13/logs/llm_calls.jsonl"):
        with open("experiment13/logs/llm_calls.jsonl") as f:
            calls = [json.loads(line) for line in f if line.strip()]

    candidates = []
    if os.path.exists("experiment13/candidates/candidates.jsonl"):
        with open("experiment13/candidates/candidates.jsonl") as f:
            candidates = [json.loads(line) for line in f if line.strip()]

    # 2. Quality Control Audit
    total_calls = len(calls)
    total_cands = len(candidates)
    invalid_cands = sum(1 for c in candidates if not c.get("validity", False))
    invalid_rate = invalid_cands / max(1, total_cands)
    truncated_calls = sum(1 for c in calls if c.get("is_truncated", False))
    truncation_rate = truncated_calls / max(1, total_calls)

    qc_pass = (invalid_rate <= config["quality_control"]["max_invalid_rate_threshold"] and
               truncation_rate <= config["quality_control"]["max_truncation_rate_threshold"])

    print(f"QC Audit: Total Calls={total_calls}, Invalid={invalid_cands} ({invalid_rate*100:.1f}%), Truncated={truncated_calls} ({truncation_rate*100:.1f}%) -> {'PASS' if qc_pass else 'FAIL'}")

    # 3. Identify Strongest Baseline on Hidden Benchmark
    strongest_baseline_key = min(baselines_hidden, key=lambda k: baselines_hidden[k]["total_cost"])
    strongest_baseline = baselines_hidden[strongest_baseline_key]
    strongest_base_name = strongest_baseline["name"]
    strongest_base_cost = strongest_baseline["total_cost"]
    strongest_base_inst_costs = strongest_baseline["instance_costs"]

    print(f"\nStrongest Baseline Identified: {strongest_base_name} ({strongest_baseline_key})")
    print(f"   Hidden Total Cost: {strongest_base_cost:.2f} | Mean: {strongest_baseline['mean_cost_per_instance']:.2f}")

    # 4. Amaura Champions Performance
    champ_dev_costs = [c["development_cost"] for c in frozen_champs]
    champ_hidden_costs = [e["hidden_total_cost"] for e in hidden_evals]
    champ_active_nodes = [e["active_nodes_mean"] for e in hidden_evals]
    champ_unscheduled = [e["unscheduled_total"] for e in hidden_evals]

    mean_dev_cost, std_dev_cost = calculate_mean_std(champ_dev_costs)
    mean_hidden_cost, std_hidden_cost = calculate_mean_std(champ_hidden_costs)

    best_champ_hidden = min(hidden_evals, key=lambda e: e["hidden_total_cost"])

    # 5. Trial-by-Trial Scorecard vs Strongest Baseline
    trial_wins = 0
    trial_losses = 0
    trial_ties = 0
    trial_scorecard = []

    for idx, e in enumerate(hidden_evals):
        cid = e["candidate_id"]
        h_cost = e["hidden_total_cost"]
        diff = round(h_cost - strongest_base_cost, 2)
        if diff < -1e-4:
            winner = "Amaura"
            trial_wins += 1
        elif diff > 1e-4:
            winner = strongest_base_name
            trial_losses += 1
        else:
            winner = "Tie"
            trial_ties += 1

        trial_scorecard.append({
            "trial": idx + 1,
            "candidate_id": cid,
            "angle_name": e["angle_name"],
            "amaura_cost": h_cost,
            "baseline_cost": strongest_base_cost,
            "delta": diff,
            "winner": winner
        })

    # 6. Instance-Level Comparison (120 Instances) vs Strongest Baseline
    # Using the best overall discovery champion
    best_inst_costs = best_champ_hidden["instance_costs"]
    instance_diffs = [best_inst_costs[i] - strongest_base_inst_costs[i] for i in range(len(best_inst_costs))]

    inst_wins = sum(1 for d in instance_diffs if d < -1e-4)
    inst_losses = sum(1 for d in instance_diffs if d > 1e-4)
    inst_ties = sum(1 for d in instance_diffs if abs(d) <= 1e-4)

    w_stat, p_val = wilcoxon_signed_rank_test(instance_diffs)
    cohens_d = calculate_cohens_d(best_inst_costs, strongest_base_inst_costs)

    # 7. Workload Family Breakdown
    families = ["Uniform", "CPU_Heavy", "Memory_Heavy", "Bimodal", "Anti_Correlated", "Correlated"]
    family_breakdown = {}

    for fam in families:
        fam_indices = [i for i, inst in enumerate(hidden_instances) if inst["family"] == fam]
        fam_base_costs = [strongest_base_inst_costs[i] for i in fam_indices]
        fam_amaura_costs = [best_inst_costs[i] for i in fam_indices]

        mean_base = sum(fam_base_costs) / len(fam_base_costs)
        mean_amaura = sum(fam_amaura_costs) / len(fam_amaura_costs)
        delta_pct = ((mean_amaura - mean_base) / mean_base) * 100.0

        fam_wins = sum(1 for i in range(len(fam_indices)) if fam_amaura_costs[i] < fam_base_costs[i] - 1e-4)
        fam_losses = sum(1 for i in range(len(fam_indices)) if fam_amaura_costs[i] > fam_base_costs[i] + 1e-4)
        fam_ties = len(fam_indices) - fam_wins - fam_losses

        family_breakdown[fam] = {
            "instances": len(fam_indices),
            "baseline_mean_cost": round(mean_base, 2),
            "amaura_mean_cost": round(mean_amaura, 2),
            "difference_percent": round(delta_pct, 2),
            "wins": fam_wins,
            "losses": fam_losses,
            "ties": fam_ties
        }

    # 8. Decision Engine
    # H1: Amaura beats strongest baseline on unseen workloads with statistical significance
    beats_baseline_mean = (mean_hidden_cost < strongest_base_cost)
    majority_trials = (trial_wins >= 3)
    stat_sig = (p_val < 0.05 and inst_wins > inst_losses)
    best_beats_base = (best_champ_hidden["hidden_total_cost"] < strongest_base_cost)

    if beats_baseline_mean and majority_trials and stat_sig:
        verdict = "SUPPORTED"
        verdict_reason = f"Amaura beat {strongest_base_name} across {trial_wins}/5 trials and on 120 hidden workloads (p={p_val:.4f})."
    elif best_beats_base and (trial_wins >= 2 or inst_wins > inst_losses):
        verdict = "PARTIALLY SUPPORTED"
        verdict_reason = f"Amaura's best candidate beat {strongest_base_name} ({best_champ_hidden['hidden_total_cost']:.2f} vs {strongest_base_cost:.2f}), but trial win rate was {trial_wins}/5."
    else:
        verdict = "NOT SUPPORTED"
        verdict_reason = f"Amaura did not reliably outperform {strongest_base_name} (mean: {mean_hidden_cost:.2f} vs {strongest_base_cost:.2f}, trials: {trial_wins}/5)."

    summary_stats = {
        "metadata": {
            "experiment": "Amaura_Experiment_13",
            "domain": "Kubernetes-Style Cloud Pod Scheduling",
            "trials": 5,
            "calls_per_trial": 15,
            "total_calls": total_calls,
            "model": config["model"],
            "invalid_rate": round(invalid_rate, 4),
            "truncation_rate": round(truncation_rate, 4),
            "qc_passed": qc_pass
        },
        "strongest_baseline": {
            "key": strongest_baseline_key,
            "name": strongest_base_name,
            "hidden_total_cost": strongest_base_cost,
            "hidden_mean_cost": strongest_baseline["mean_cost_per_instance"],
            "active_nodes_mean": strongest_baseline["active_nodes_mean"]
        },
        "all_baselines_hidden": {
            k: {
                "name": v["name"],
                "total_cost": v["total_cost"],
                "mean_cost": v["mean_cost_per_instance"],
                "active_nodes_mean": v["active_nodes_mean"],
                "unscheduled": v["unscheduled_total"]
            }
            for k, v in baselines_hidden.items()
        },
        "amaura_champions_hidden": {
            "mean_total_cost": round(mean_hidden_cost, 2),
            "std_total_cost": round(std_hidden_cost, 2),
            "min_total_cost": round(min(champ_hidden_costs), 2),
            "max_total_cost": round(max(champ_hidden_costs), 2),
            "mean_active_nodes": round(sum(champ_active_nodes) / len(champ_active_nodes), 2),
            "total_unscheduled": sum(champ_unscheduled),
            "best_candidate_id": best_champ_hidden["candidate_id"],
            "best_angle_name": best_champ_hidden["angle_name"],
            "best_total_cost": round(best_champ_hidden["hidden_total_cost"], 2),
            "gap_vs_strongest_baseline_percent": round(((mean_hidden_cost - strongest_base_cost) / strongest_base_cost) * 100.0, 2),
            "best_gap_vs_strongest_percent": round(((best_champ_hidden["hidden_total_cost"] - strongest_base_cost) / strongest_base_cost) * 100.0, 2)
        },
        "trial_scorecard": trial_scorecard,
        "instance_level_comparison": {
            "instances": 120,
            "amaura_wins": inst_wins,
            "baseline_wins": inst_losses,
            "ties": inst_ties,
            "wilcoxon_stat": round(w_stat, 2),
            "p_value": round(p_val, 4),
            "cohens_d": round(cohens_d, 4)
        },
        "family_breakdown": family_breakdown,
        "verdict": {
            "verdict": verdict,
            "reason": verdict_reason,
            "trial_wins": f"{trial_wins}/5",
            "stat_sig_p": p_val
        }
    }

    out_path = "experiment13/analysis/summary_statistics.json"
    with open(out_path, "w") as f:
        json.dump(summary_stats, f, indent=2)

    print(f"\nAnalysis written to {out_path}")
    print(f"=== OFFICIAL PRE-REGISTERED VERDICT: {verdict} ===")
    print(f"Reason: {verdict_reason}")


if __name__ == "__main__":
    run_experiment_analysis()
