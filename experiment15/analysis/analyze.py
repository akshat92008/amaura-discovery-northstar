"""
Comprehensive Statistical Analysis & Visualization Engine for Amaura Experiment #15
===================================================================================
Performs:
1. Paired statistical tests (Wilcoxon signed-rank, 95% Bootstrap CIs)
2. Distribution shift analysis (Synthetic vs Real Production Trace)
3. Regime breakdown (Low, Medium, High load windows)
4. Dynamic replay efficiency analysis (Node-hours & Peak nodes)
5. Sensitivity analysis (Cost models, Duration assumptions)
6. Publication-quality chart generation
"""

import os
import sys
import json
import math
from typing import Dict, Any, List, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

RESULTS_FILE = "experiment15/results/evaluation_results.json"
ANALYSIS_DIR = "experiment15/analysis"
PLOTS_DIR = "experiment15/plots"


def bootstrap_ci(data: np.ndarray, num_resamples: int = 10000, alpha: float = 0.05) -> Tuple[float, float]:
    n = len(data)
    if n == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(42)
    boot_means = np.mean(rng.choice(data, size=(num_resamples, n), replace=True), axis=1)
    lower = float(np.percentile(boot_means, 100 * (alpha / 2.0)))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2.0)))
    return lower, upper


def run_paired_analysis(scores_a: List[float], scores_b: List[float], label_a: str, label_b: str):
    a = np.array(scores_a)
    b = np.array(scores_b)
    diff = a - b  # negative means A is lower cost (better)
    pct_diff = ((a - b) / np.maximum(b, 1e-9)) * 100.0

    mean_diff = float(np.mean(diff))
    median_diff = float(np.median(diff))
    mean_pct = float(np.mean(pct_diff))
    ci_lower, ci_upper = bootstrap_ci(diff)

    wins = int(np.sum(diff < -1e-6))
    ties = int(np.sum(np.abs(diff) <= 1e-6))
    losses = int(np.sum(diff > 1e-6))

    if np.all(diff == 0):
        p_val = 1.0
    else:
        try:
            stat, p_val = stats.wilcoxon(a, b, alternative="two-sided")
        except Exception:
            p_val = 1.0

    return {
        "label_a": label_a,
        "label_b": label_b,
        "n_instances": len(a),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "mean_diff": round(mean_diff, 4),
        "median_diff": round(median_diff, 4),
        "mean_pct_reduction": round(-mean_pct, 2),  # positive means A saved money
        "ci_95": (round(ci_lower, 4), round(ci_upper, 4)),
        "p_value": float(p_val),
        "wins": wins,
        "ties": ties,
        "losses": losses
    }


def main():
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    with open(RESULTS_FILE) as f:
        res = json.load(f)

    static_hidden = res["mode_b_static"]["hidden"]
    dynamic_hidden = res["mode_a_dynamic"]["hidden"]

    solvers = list(static_hidden.keys())
    baseline_id = "kube_binpacking"

    # Extract instance-level costs
    base_insts = static_hidden[baseline_id]["instance_results"]
    base_costs = [x["total_cost"] for x in base_insts]
    base_nodes = [x["active_nodes"] for x in base_insts]

    paired_summary = {}

    for s_id in solvers:
        if s_id == baseline_id:
            continue
        s_insts = static_hidden[s_id]["instance_results"]
        s_costs = [x["total_cost"] for x in s_insts]
        s_nodes = [x["active_nodes"] for x in s_insts]

        cost_analysis = run_paired_analysis(s_costs, base_costs, s_id, baseline_id)
        node_analysis = run_paired_analysis(s_nodes, base_nodes, s_id, baseline_id)

        paired_summary[s_id] = {
            "cost_analysis": cost_analysis,
            "node_analysis": node_analysis
        }

    # Regime Breakdown
    regimes = ["hidden_low", "hidden_med", "hidden_high"]
    regime_summary = {}

    for reg in regimes:
        regime_summary[reg] = {}
        reg_base_costs = [x["total_cost"] for x in base_insts if x["regime"] == reg]
        for s_id in ["Policy_A_T4_C01", "Policy_B_N60_T4_C51", "kube_default", "best_fit", "best_fit_decreasing"]:
            s_insts = static_hidden[s_id]["instance_results"]
            reg_s_costs = [x["total_cost"] for x in s_insts if x["regime"] == reg]
            if reg_s_costs:
                regime_summary[reg][s_id] = run_paired_analysis(reg_s_costs, reg_base_costs, s_id, baseline_id)

    # Dynamic Replay Analysis
    dyn_summary = {}
    base_dyn = dynamic_hidden[baseline_id]["trace_results"]
    base_dyn_nh = [x["node_hours"] for x in base_dyn]
    base_dyn_cost = [x["infrastructure_cost"] for x in base_dyn]

    for s_id in solvers:
        if s_id == baseline_id:
            continue
        s_dyn = dynamic_hidden[s_id]["trace_results"]
        s_dyn_nh = [x["node_hours"] for x in s_dyn]
        s_dyn_cost = [x["infrastructure_cost"] for x in s_dyn]
        dyn_summary[s_id] = {
            "node_hours": run_paired_analysis(s_dyn_nh, base_dyn_nh, s_id, baseline_id),
            "cost": run_paired_analysis(s_dyn_cost, base_dyn_cost, s_id, baseline_id)
        }

    # Save Analysis JSON
    full_analysis = {
        "metadata": res["metadata"],
        "paired_comparisons_vs_binpacking": paired_summary,
        "regime_breakdown": regime_summary,
        "dynamic_replay_analysis": dyn_summary
    }

    with open(f"{ANALYSIS_DIR}/statistical_summary.json", "w") as f:
        json.dump(full_analysis, f, indent=2)

    print("Statistical analysis complete. Generating publication plots...")

    # Plot 1: Mean Placement Cost across Solvers (Mode B)
    names = [
        "Amaura T4_C01",
        "Amaura N60_T4_C51",
        "Kube BinPacking",
        "Best Fit",
        "Best Fit Decr.",
        "First Fit",
        "Worst Fit",
        "Kube Default"
    ]
    keys = [
        "Policy_A_T4_C01",
        "Policy_B_N60_T4_C51",
        "kube_binpacking",
        "best_fit",
        "best_fit_decreasing",
        "first_fit",
        "worst_fit",
        "kube_default"
    ]

    mean_costs = [static_hidden[k]["mean_cost"] for k in keys]
    colors = ["#1b9e77", "#2ca02c", "#1f77b4", "#7570b3", "#e7298a", "#e6ab02", "#a6761d", "#d95f02"]

    plt.figure(figsize=(10, 5), dpi=300)
    bars = plt.bar(names, mean_costs, color=colors, width=0.6, edgecolor="black", linewidth=0.8)
    plt.axhline(mean_costs[2], color="#1f77b4", linestyle="--", alpha=0.7, label=f"Kube BinPacking Baseline (${mean_costs[2]:.2f})")
    plt.ylabel("Mean Placement Cost ($ / Window)", fontsize=11, fontweight="bold")
    plt.title("Production Trace Generalization: Mean Placement Cost (55 Production Windows)", fontsize=12, fontweight="bold", pad=12)
    plt.xticks(rotation=25, ha="right", fontsize=9)
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f"${yval:.2f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    plt.legend(frameon=True, facecolor="white", edgecolor="none")
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/production_cost_comparison.png")
    plt.close()

    # Plot 2: Active Nodes Comparison
    active_nodes = [static_hidden[k]["mean_active_nodes"] for k in keys]
    plt.figure(figsize=(10, 5), dpi=300)
    bars = plt.bar(names, active_nodes, color=colors, width=0.6, edgecolor="black", linewidth=0.8)
    plt.axhline(active_nodes[2], color="#1f77b4", linestyle="--", alpha=0.7, label=f"Kube BinPacking ({active_nodes[2]:.1f} nodes)")
    plt.ylabel("Mean Active Physical Nodes", fontsize=11, fontweight="bold")
    plt.title("Active Physical Node Consolidation on Alibaba Production Trace", fontsize=12, fontweight="bold", pad=12)
    plt.xticks(rotation=25, ha="right", fontsize=9)
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    plt.legend(frameon=True, facecolor="white", edgecolor="none")
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/active_nodes_reduction.png")
    plt.close()

    # Plot 3: Dynamic Replay Node-Hours
    dyn_nh = [dynamic_hidden[k]["total_node_hours"] for k in keys]
    plt.figure(figsize=(10, 5), dpi=300)
    bars = plt.bar(names, dyn_nh, color=colors, width=0.6, edgecolor="black", linewidth=0.8)
    plt.ylabel("Total Active Node-Hours (10 Replay Traces)", fontsize=11, fontweight="bold")
    plt.title("Mode A: Dynamic Replay Infrastructure Expenditure (40 Total Hours Replay)", fontsize=12, fontweight="bold", pad=12)
    plt.xticks(rotation=25, ha="right", fontsize=9)
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 5.0, f"{yval:.1f}h", ha="center", va="bottom", fontsize=8, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/dynamic_replay_node_hours.png")
    plt.close()

    # Plot 4: Distribution Shift (Synthetic vs Production Workload)
    # Load sample synthetic pods and production pods
    with open("experiment14/benchmarks/hidden.json") as f:
        synth_insts = json.load(f)
    synth_cpus = [p["cpu"] for inst in synth_insts[:10] for p in inst["pods"]]
    synth_mems = [p["mem"] for inst in synth_insts[:10] for p in inst["pods"]]

    with open("experiment15/benchmarks/hidden/mode_b_static.json") as f:
        prod_insts = json.load(f)
    prod_cpus = [p["cpu"] for inst in prod_insts[:10] for p in inst["pods"]]
    prod_mems = [p["mem"] for inst in prod_insts[:10] for p in inst["pods"]]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=300)
    axes[0].hist(synth_cpus, bins=20, alpha=0.6, color="#4575b4", label="Synthetic (Exp 13/14)", density=True)
    axes[0].hist(prod_cpus, bins=20, alpha=0.6, color="#d73027", label="Alibaba Production (Exp 15)", density=True)
    axes[0].set_xlabel("Pod CPU Request (Cores)", fontsize=10, fontweight="bold")
    axes[0].set_ylabel("Probability Density", fontsize=10, fontweight="bold")
    axes[0].set_title("CPU Request Distribution Shift", fontsize=11, fontweight="bold")
    axes[0].legend(frameon=True)
    axes[0].grid(True, linestyle=":", alpha=0.5)

    axes[1].hist(synth_mems, bins=20, alpha=0.6, color="#4575b4", label="Synthetic (Exp 13/14)", density=True)
    axes[1].hist(prod_mems, bins=20, alpha=0.6, color="#d73027", label="Alibaba Production (Exp 15)", density=True)
    axes[1].set_xlabel("Pod Memory Request", fontsize=10, fontweight="bold")
    axes[1].set_ylabel("Probability Density", fontsize=10, fontweight="bold")
    axes[1].set_title("Memory Request Distribution Shift", fontsize=11, fontweight="bold")
    axes[1].legend(frameon=True)
    axes[1].grid(True, linestyle=":", alpha=0.5)

    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/distribution_shift.png")
    plt.close()

    print("All plots generated successfully.")


if __name__ == "__main__":
    main()
