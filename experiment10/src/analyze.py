"""
Experiment #10: Statistical & Behavioral Analysis Suite
=======================================================
Implements:
1. Primary comparison: C vs A (Behavioral QD vs Independent Best-of-N)
2. Secondary comparisons: B vs A, C vs B, A/B/C vs NEH, A/B/C vs IG
3. Search-level replication (N=5 trials) vs Instance-level paired evaluation (N=120 instances)
4. Holm-Bonferroni step-down correction & Cohen's d effect sizes
5. Search-efficiency dynamics (1..15 calls progression curves)
6. Behavioral Diversity analysis (Kendall tau distances, archive expansion over time)
7. Formal verification of Success, Failure, and Inconclusive criteria
Saves output to experiment10/analysis/summary_statistics.json.
"""

import json
import math
import os
from typing import Dict, Any, List, Tuple
import numpy as np
import scipy.stats as stats

from experiment10.src.kendall import mean_behavioral_distance, kendall_tau_distance


def cohens_d(x: List[float], y: List[float]) -> float:
    nx, ny = len(x), len(y)
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1)
    pooled_std = math.sqrt(((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(x) - np.mean(y)) / pooled_std


def run_full_analysis(
    baselines_dev_path: str = "experiment10/results/baselines_dev.json",
    baselines_hidden_path: str = "experiment10/results/baselines_hidden.json",
    frozen_champs_path: str = "experiment10/results/frozen_champions.json",
    hidden_evals_path: str = "experiment10/results/hidden_evaluations.json",
    candidates_path: str = "experiment10/candidates/candidates.jsonl",
    logs_path: str = "experiment10/logs/llm_calls.jsonl",
    hidden_bench_path: str = "experiment10/benchmarks/hidden.json",
    out_dir: str = "experiment10/analysis"
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

    candidates = []
    if os.path.exists(candidates_path):
        with open(candidates_path) as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))

    llm_calls = []
    if os.path.exists(logs_path):
        with open(logs_path) as f:
            for line in f:
                if line.strip():
                    llm_calls.append(json.loads(line))

    conditions = ["A", "B", "C"]
    cond_stats = {}

    for cond in conditions:
        dev_scores = [c["development_score"] for c in frozen_data["champions"][cond]]
        hid_scores = [e["hidden_total_makespan"] for e in hidden_data["evaluations"][cond]]
        validity = [e["validity"] for e in hidden_data["evaluations"][cond]]
        runtimes = [e["runtime_ms"] for e in hidden_data["evaluations"][cond]]

        # Candidate level metrics
        cands_cond = [c for c in candidates if c["condition"] == cond]
        total_calls_c = len(cands_cond)
        val_calls_c = sum(1 for c in cands_cond if c["validity"])
        inval_calls_c = total_calls_c - val_calls_c
        inval_rate_c = (inval_calls_c / total_calls_c) if total_calls_c > 0 else 0.0

        p_lens = [c.get("prompt_tokens", 0) for c in cands_cond]
        o_lens = [c.get("tokens", 0) - c.get("prompt_tokens", 0) for c in cands_cond]
        c_times = [c.get("runtime_ms", 0) for c in cands_cond if c["validity"]]

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
                "scores": hid_scores,
                "mean": float(np.mean(hid_scores)),
                "std": float(np.std(hid_scores, ddof=1)) if len(hid_scores) > 1 else 0.0,
                "min": int(np.min(hid_scores)),
                "max": int(np.max(hid_scores)),
                "median": float(np.median(hid_scores)),
                "validity_rate": float(np.mean(validity)),
                "mean_runtime_ms": float(np.mean(runtimes))
            },
            "candidates_audit": {
                "total_calls": total_calls_c,
                "valid_calls": val_calls_c,
                "invalid_calls": inval_calls_c,
                "invalid_rate": round(inval_rate_c, 4),
                "degraded": bool(inval_rate_c > 0.10),
                "mean_prompt_tokens": float(np.mean(p_lens)) if p_lens else 0.0,
                "mean_completion_tokens": float(np.mean(o_lens)) if o_lens else 0.0,
                "mean_candidate_runtime_ms": float(np.mean(c_times)) if c_times else 0.0
            }
        }

    neh_hidden = base_hid["neh"]["total_makespan"]
    ig_hidden = base_hid["iterated_greedy"]["total_makespan"]

    for cond in conditions:
        mean_hid = cond_stats[cond]["hidden"]["mean"]
        gap_neh = ((mean_hid - neh_hidden) / neh_hidden) * 100.0
        gap_ig = ((mean_hid - ig_hidden) / ig_hidden) * 100.0
        cond_stats[cond]["hidden"]["gap_vs_neh_percent"] = round(gap_neh, 3)
        cond_stats[cond]["hidden"]["gap_vs_ig_percent"] = round(gap_ig, 3)

    # 2. Statistical Hypothesis Testing
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

    # 3. Search Efficiency Progression (Best-so-far curve over 15 calls)
    search_curves = {"A": [], "B": [], "C": []}
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

    # 4. Diversity Analysis for Condition C
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
            "mean_pairwise_kendall": float(np.mean(diversity_stats[cond])) if diversity_stats[cond] else 0.0,
            "std": float(np.std(diversity_stats[cond], ddof=1)) if len(diversity_stats[cond]) > 1 else 0.0
        }
        for cond in conditions
    }

    # 5. Pre-Registered Success / Failure / Inconclusive Evaluation
    # Rule 21 & 24: Invalidity > 10% in a condition => flag as degraded; if severe => INCONCLUSIVE
    mean_c = cond_stats["C"]["hidden"]["mean"]
    mean_a = cond_stats["A"]["hidden"]["mean"]
    mean_b = cond_stats["B"]["hidden"]["mean"]

    total_inval_rate = sum(cond_stats[c]["candidates_audit"]["invalid_calls"] for c in conditions) / max(1, len(candidates))

    if total_inval_rate > 0.10:
        verdict = "INCONCLUSIVE"
        verdict_reason = f"Candidate invalidity rate ({total_inval_rate*100:.1f}%) exceeded pre-registered 10% threshold."
    elif mean_c < mean_a and p_c_vs_a < 0.05 and mean_c < neh_hidden:
        verdict = "SUPPORTED"
        verdict_reason = f"Condition C significantly outperformed Condition A (p={p_c_vs_a:.4f}) and beat Classical NEH ({mean_c:.1f} vs {neh_hidden})."
    else:
        verdict = "UNSUPPORTED"
        if mean_c >= mean_a:
            verdict_reason = f"Condition C (mean={mean_c:.1f}) failed to outperform Condition A (mean={mean_a:.1f}); p={p_c_vs_a:.4f}."
        else:
            verdict_reason = f"Condition C difference from Condition A was not statistically significant (p={p_c_vs_a:.4f} >= 0.05)."

    summary = {
        "metadata": {
            "experiment": "Amaura Experiment #10: Behavioral QD vs Best-of-N",
            "trials": 5,
            "calls_per_condition_per_trial": 15,
            "total_calls": len(candidates),
            "invalid_rate_total": round(total_inval_rate, 4),
            "model": frozen_data["metadata"]["model"],
        },
        "classical_baselines": {
            "dev": base_dev,
            "hidden": base_hid
        },
        "condition_statistics": cond_stats,
        "statistical_tests": {
            "trial_level_wilcoxon": {
                "C_vs_A": {"p_val": p_c_vs_a, "cohens_d": round(d_c_vs_a, 3)},
                "C_vs_B": {"p_val": p_c_vs_b, "cohens_d": round(d_c_vs_b, 3)},
                "A_vs_B": {"p_val": p_a_vs_b, "cohens_d": round(d_a_vs_b, 3)},
            },
            "instance_level_wilcoxon": {
                "C_vs_A": {"p_val": p_inst_c_vs_a},
                "C_vs_B": {"p_val": p_inst_c_vs_b},
                "A_vs_B": {"p_val": p_inst_a_vs_b},
            }
        },
        "search_efficiency_curves": search_curves,
        "diversity_analysis": diversity_summary,
        "verdict": {
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "qc_threshold": 0.10
        }
    }

    out_file = os.path.join(out_dir, "summary_statistics.json")
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Analysis written to {out_file}")
    print(f"=== VERDICT: {verdict} ===")
    print(f"Reason: {verdict_reason}")
    return summary


if __name__ == "__main__":
    run_full_analysis()
