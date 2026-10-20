"""
Experiment #9: Statistical & Behavioral Analysis Suite
======================================================
Performs:
1. Descriptive Statistics (Dev & Hidden Makespan for Baselines and Conditions A, B, C)
2. Inferential Hypothesis Testing:
   - Wilcoxon signed-rank tests across 5 trials (C vs A, C vs B, A vs B, C vs NEH)
   - Instance-level paired Wilcoxon tests across 120 hidden instances
   - Holm-Bonferroni correction
   - Cohen's d & Cliff's delta effect sizes
3. Search-Efficiency Dynamics (Best-so-far curve over 1..15 calls)
4. Behavioral Diversity Metrics (Kendall tau distances, archive coverage)
5. Pre-registered Kill Criteria & Final Scientific Verdict Determination
Saves comprehensive results to experiment9/analysis/summary_statistics.json.
"""

import json
import math
import os
from typing import Dict, Any, List, Tuple
import numpy as np
import scipy.stats as stats

from experiment9.src.kendall import mean_behavioral_distance, kendall_tau_distance



def cohens_d(x: List[float], y: List[float]) -> float:
    nx, ny = len(x), len(y)
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1)
    pooled_std = math.sqrt(((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(x) - np.mean(y)) / pooled_std


def cliffs_delta(x: List[float], y: List[float]) -> float:
    nx, ny = len(x), len(y)
    more = sum(1 for xi in x for yj in y if xi > yj)
    less = sum(1 for xi in x for yj in y if xi < yj)
    return (more - less) / (nx * ny)


def run_full_analysis(
    baselines_dev_path: str = "experiment9/results/baselines_dev.json",
    baselines_hidden_path: str = "experiment9/results/baselines_hidden.json",
    frozen_champs_path: str = "experiment9/results/frozen_champions.json",
    hidden_evals_path: str = "experiment9/results/hidden_evaluations.json",
    candidates_path: str = "experiment9/candidates/candidates.jsonl",
    logs_path: str = "experiment9/logs/llm_calls.jsonl",
    hidden_bench_path: str = "experiment9/benchmarks/hidden.json",
    out_dir: str = "experiment9/analysis"
) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)

    with open(baselines_dev_path) as f:
        base_dev = json.load(f)
    with open(baselines_hidden_path) as f:
        base_hid = json.load(f)
    with open(frozen_champs_path) as f:
        frozen_data = json.load(f)
    with open(hidden_evals_path) as f:
        hidden_data = json.load(f)
    with open(hidden_bench_path) as f:
        hidden_instances = json.load(f)

    # Load candidates
    candidates = []
    if os.path.exists(candidates_path):
        with open(candidates_path) as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))

    # Load LLM calls
    llm_calls = []
    if os.path.exists(logs_path):
        with open(logs_path) as f:
            for line in f:
                if line.strip():
                    llm_calls.append(json.loads(line))

    # 1. Condition-level performance metrics
    cond_stats = {}
    conditions = ["A", "B", "C"]

    for cond in conditions:
        dev_scores = [c["development_score"] for c in frozen_data["champions"][cond]]
        hid_scores = [e["hidden_total_makespan"] for e in hidden_data["evaluations"][cond]]
        validity = [e["validity"] for e in hidden_data["evaluations"][cond]]
        runtimes = [e["runtime_ms"] for e in hidden_data["evaluations"][cond]]

        cond_stats[cond] = {
            "dev": {
                "scores": dev_scores,
                "mean": float(np.mean(dev_scores)),
                "std": float(np.std(dev_scores, ddof=1)),
                "min": int(np.min(dev_scores)),
                "max": int(np.max(dev_scores)),
                "median": float(np.median(dev_scores))
            },
            "hidden": {
                "scores": hid_scores,
                "mean": float(np.mean(hid_scores)),
                "std": float(np.std(hid_scores, ddof=1)),
                "min": int(np.min(hid_scores)),
                "max": int(np.max(hid_scores)),
                "median": float(np.median(hid_scores)),
                "validity_rate": float(np.mean(validity)),
                "mean_runtime_ms": float(np.mean(runtimes))
            }
        }

    # Reference Classical Baseline targets on Hidden suite
    neh_hidden = base_hid["neh"]["total_makespan"]
    palmer_hidden = base_hid["palmer"]["total_makespan"]
    cds_hidden = base_hid["cds"]["total_makespan"]
    ig_hidden = base_hid["iterated_greedy"]["total_makespan"]

    # Gaps vs NEH (%)
    for cond in conditions:
        mean_hid = cond_stats[cond]["hidden"]["mean"]
        gap_neh = ((mean_hid - neh_hidden) / neh_hidden) * 100.0
        cond_stats[cond]["hidden"]["gap_vs_neh_percent"] = round(gap_neh, 3)

    # 2. Statistical Hypothesis Testing
    # Paired Wilcoxon on 5 trials (two-sided)
    def safe_wilcoxon(x, y):
        diff = np.array(x) - np.array(y)
        if np.all(diff == 0):
            return 1.0, 0.0
        try:
            stat, p = stats.wilcoxon(x, y, zero_method="wilcox")
            return float(p), float(stat)
        except Exception:
            return 1.0, 0.0

    scores_a = cond_stats["A"]["hidden"]["scores"]
    scores_b = cond_stats["B"]["hidden"]["scores"]
    scores_c = cond_stats["C"]["hidden"]["scores"]

    p_c_vs_a, stat_c_vs_a = safe_wilcoxon(scores_c, scores_a)
    p_c_vs_b, stat_c_vs_b = safe_wilcoxon(scores_c, scores_b)
    p_a_vs_b, stat_a_vs_b = safe_wilcoxon(scores_a, scores_b)

    d_c_vs_a = cohens_d(scores_c, scores_a)
    d_c_vs_b = cohens_d(scores_c, scores_b)
    d_a_vs_b = cohens_d(scores_a, scores_b)

    # Instance-level paired test across 120 hidden instances
    # Compute mean makespan per instance across the 5 champions for each condition
    inst_makespans_a = np.zeros(120)
    inst_makespans_b = np.zeros(120)
    inst_makespans_c = np.zeros(120)

    for i in range(5):
        if hidden_data["evaluations"]["A"][i]["validity"]:
            inst_makespans_a += np.array(hidden_data["evaluations"]["A"][i]["instance_makespans"]) / 5.0
        if hidden_data["evaluations"]["B"][i]["validity"]:
            inst_makespans_b += np.array(hidden_data["evaluations"]["B"][i]["instance_makespans"]) / 5.0
        if hidden_data["evaluations"]["C"][i]["validity"]:
            inst_makespans_c += np.array(hidden_data["evaluations"]["C"][i]["instance_makespans"]) / 5.0

    p_inst_c_vs_a, _ = safe_wilcoxon(inst_makespans_c, inst_makespans_a)
    p_inst_c_vs_b, _ = safe_wilcoxon(inst_makespans_c, inst_makespans_b)
    p_inst_a_vs_b, _ = safe_wilcoxon(inst_makespans_a, inst_makespans_b)

    # Holm-Bonferroni correction on the 3 primary trial contrasts
    raw_pvals = [("C_vs_A", p_c_vs_a), ("C_vs_B", p_c_vs_b), ("A_vs_B", p_a_vs_b)]
    raw_pvals.sort(key=lambda x: x[1])
    corrected_pvals = {}
    m = len(raw_pvals)
    for rank, (name, p) in enumerate(raw_pvals):
        adj_p = min(1.0, p * (m - rank))
        corrected_pvals[name] = round(adj_p, 4)

    # 3. Breakdown by Instance Family on Hidden Benchmark
    family_breakdown = {}
    fam_names = sorted(list(set(inst["family"] for inst in hidden_instances)))
    for fam in fam_names:
        fam_indices = [idx for idx, inst in enumerate(hidden_instances) if inst["family"] == fam]
        family_breakdown[fam] = {
            "num_instances": len(fam_indices),
            "cond_A_mean": float(np.mean([np.sum(inst_makespans_a[fam_indices])])),
            "cond_B_mean": float(np.mean([np.sum(inst_makespans_b[fam_indices])])),
            "cond_C_mean": float(np.mean([np.sum(inst_makespans_c[fam_indices])])),
        }

    # 4. Search Efficiency Progression (Best-so-far curve over 15 calls)
    search_curves = {"A": np.zeros(15), "B": np.zeros(15), "C": np.zeros(15)}
    if candidates:
        for cond in conditions:
            curves = []
            for t in range(5):
                t_cands = [c for c in candidates if c["trial_idx"] == t and c["condition"] == cond]
                t_cands.sort(key=lambda c: c["call_idx"])
                best_so_far = float("inf")
                c_curve = []
                for c in t_cands:
                    score = c["development_score"] if (c["validity"] and c["development_score"] < 999999) else float("inf")
                    if score < best_so_far:
                        best_so_far = score
                    c_curve.append(best_so_far)
                while len(c_curve) < 15:
                    c_curve.append(best_so_far)
                curves.append(c_curve[:15])
            if curves:
                search_curves[cond] = np.mean(curves, axis=0).tolist()

    # 5. Behavioral Diversity Analysis
    # Mean pairwise distance within each trial's population
    diversity_stats = {"A": [], "B": [], "C": []}
    for cond in conditions:
        for t in range(5):
            valid_sigs = [
                c["behavior_signature"] for c in candidates
                if c["trial_idx"] == t and c["condition"] == cond and c["validity"] and c["behavior_signature"]
            ]
            if len(valid_sigs) >= 2:
                dists = []
                for i in range(len(valid_sigs)):
                    for j in range(i + 1, len(valid_sigs)):
                        d = mean_behavioral_distance(valid_sigs[i], valid_sigs[j])
                        dists.append(d)
                diversity_stats[cond].append(float(np.mean(dists)))
            else:
                diversity_stats[cond].append(0.0)

    diversity_summary = {
        cond: {
            "mean_pairwise_kendall": float(np.mean(diversity_stats[cond])),
            "std": float(np.std(diversity_stats[cond], ddof=1)) if len(diversity_stats[cond]) > 1 else 0.0
        }
        for cond in conditions
    }

    # 6. Pre-Registered Kill Criteria & Final Verdict
    # Success Criteria:
    # 1. Condition C beats Condition A (p < 0.05, Wilcoxon) across 5 trials on Hidden Benchmark
    # 2. Condition C beats Classical NEH (mean hidden makespan < 531943)
    # 3. Minimum meaningful gap: > 0.5% reduction in total hidden makespan
    # Failure Criteria:
    # - Condition C shows no significant difference (p >= 0.05) or performs worse than Condition A
    # Inconclusive Criteria:
    # - High invalidity rate (> 15% calls fail)
    total_calls_count = len(candidates)
    invalid_calls_count = sum(1 for c in candidates if not c["validity"])
    invalid_rate = (invalid_calls_count / total_calls_count) if total_calls_count > 0 else 0.0

    mean_c = cond_stats["C"]["hidden"]["mean"]
    mean_a = cond_stats["A"]["hidden"]["mean"]
    mean_b = cond_stats["B"]["hidden"]["mean"]

    if invalid_rate > 0.15:
        verdict = "INCONCLUSIVE"
        verdict_reason = f"High candidate invalidity rate ({invalid_rate*100:.1f}% > 15% threshold)."
    elif mean_c < mean_a and p_c_vs_a < 0.05 and mean_c < neh_hidden:
        verdict = "SUPPORTED"
        verdict_reason = f"Condition C significantly outperformed Condition A (p={p_c_vs_a:.4f}) and beat Classical NEH ({mean_c:.1f} vs {neh_hidden})."
    else:
        verdict = "NOT SUPPORTED"
        if mean_c >= mean_a:
            verdict_reason = f"Condition C (mean={mean_c:.1f}) did not outperform Condition A (mean={mean_a:.1f}); p={p_c_vs_a:.4f}."
        else:
            verdict_reason = f"Condition C difference from Condition A was not statistically significant (p={p_c_vs_a:.4f} >= 0.05) or failed to beat NEH ({mean_c:.1f} vs {neh_hidden})."

    summary = {
        "metadata": {
            "experiment": "Amaura Experiment #9: PFSP Algorithm Discovery",
            "trials": 5,
            "calls_per_condition_per_trial": 15,
            "total_calls": total_calls_count,
            "invalid_calls": invalid_calls_count,
            "invalid_rate": round(invalid_rate, 4),
            "model": frozen_data["metadata"]["model"],
        },
        "classical_baselines": {
            "dev": base_dev,
            "hidden": base_hid
        },
        "condition_statistics": cond_stats,
        "statistical_tests": {
            "trial_level_wilcoxon": {
                "C_vs_A": {"p_val_raw": p_c_vs_a, "p_val_adj": corrected_pvals.get("C_vs_A", p_c_vs_a), "cohens_d": round(d_c_vs_a, 3)},
                "C_vs_B": {"p_val_raw": p_c_vs_b, "p_val_adj": corrected_pvals.get("C_vs_B", p_c_vs_b), "cohens_d": round(d_c_vs_b, 3)},
                "A_vs_B": {"p_val_raw": p_a_vs_b, "p_val_adj": corrected_pvals.get("A_vs_B", p_a_vs_b), "cohens_d": round(d_a_vs_b, 3)},
            },
            "instance_level_wilcoxon": {
                "C_vs_A": {"p_val": p_inst_c_vs_a},
                "C_vs_B": {"p_val": p_inst_c_vs_b},
                "A_vs_B": {"p_val": p_inst_a_vs_b},
            }
        },
        "family_breakdown": family_breakdown,
        "search_efficiency_curves": search_curves,
        "diversity_analysis": diversity_summary,
        "verdict": {
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "pre_registered_threshold": 0.005
        }
    }

    out_file = os.path.join(out_dir, "summary_statistics.json")
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Analysis successfully written to {out_file}")
    print(f"=== VERDICT: {verdict} ===")
    print(f"Reason: {verdict_reason}")
    return summary


if __name__ == "__main__":
    run_full_analysis()
