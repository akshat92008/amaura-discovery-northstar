"""
Main Experiment Orchestrator for Search Strategy Benchmark V1
=============================================================
Runs pilot and confirmatory experimental grids across domains, arms, budgets, and width/depth allocations.
Enforces strictly paired random seeds, budget accounting, and test-set firewalls.
Computes inferential statistics, generates plots, and outputs structured reports.
"""

import argparse
import json
import math
import os
import sys
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import numpy as np

from benchmark_v1.src.engine.runner import BenchmarkRunner, TrialConfig
from benchmark_v1.src.analysis.stats import (
    compute_paired_wilcoxon,
    apply_holm_bonferroni,
    compute_bootstrap_ci,
    compute_descriptive_stats,
    compute_power_simulation,
    aggregate_curves
)


import concurrent.futures


def _worker_execute_trial(args) -> Dict[str, Any]:
    config, results_dir = args
    runner = BenchmarkRunner(results_dir=results_dir)
    return runner.execute_trial(config)


class ExperimentOrchestrator:
    def __init__(self, mode: str = "pilot", results_dir: Optional[str] = None, workers: Optional[int] = None):
        self.mode = mode
        if results_dir is None:
            results_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "results",
                mode
            )
        self.results_dir = results_dir
        self.runner = BenchmarkRunner(results_dir=self.results_dir)
        self.workers = workers or min(os.cpu_count() or 4, 7)
        os.makedirs(self.results_dir, exist_ok=True)

    def run_benchmark_grid(
        self,
        domains: List[str],
        arms: List[str],
        budgets: List[int],
        widths: List[int],
        num_trials: int,
        base_seed: int = 10001,
        generator_type: str = "simulated"
    ) -> Dict[str, Any]:
        """
        Executes paired experimental grid in parallel across CPU cores:
        For each (domain, budget, width) condition:
          For trial_idx in 0..num_trials-1:
            seed = base_seed + trial_idx
            Run each arm with this identical seed.
        """
        print(f"\n=======================================================", flush=True)
        print(f"STARTING BENCHMARK GRID [{self.mode.upper()}]", flush=True)
        print(f"Domains: {domains}", flush=True)
        print(f"Arms: {arms}", flush=True)
        print(f"Budgets: {budgets}", flush=True)
        print(f"Widths: {widths}", flush=True)
        print(f"Trials per cell: {num_trials}", flush=True)
        print(f"Parallel Workers: {self.workers}", flush=True)
        print(f"Generator: {generator_type}", flush=True)
        print(f"Results Directory: {self.results_dir}", flush=True)
        print(f"=======================================================\n", flush=True)

        configs: List[TrialConfig] = []
        trial_id = 0

        for domain in domains:
            for budget in budgets:
                for width in widths:
                    for t_idx in range(num_trials):
                        seed = base_seed + t_idx * 7919
                        for arm in arms:
                            trial_id += 1
                            configs.append(TrialConfig(
                                trial_id=trial_id,
                                domain_name=domain,
                                arm_name=arm,
                                total_budget=budget,
                                num_trajectories=width,
                                seed=seed,
                                generator_type=generator_type
                            ))

        total_runs = len(configs)
        completed = 0
        t_start = time.time()
        all_results: List[Dict[str, Any]] = []

        if self.workers <= 1:
            print(f"Running sequentially on single thread (no multiprocessing)...", flush=True)
            for cfg in configs:
                res = self.runner.execute_trial(cfg)
                all_results.append(res)
                completed += 1
                dom = res["domain"]
                b = res["total_budget"]
                w = res["num_trajectories"]
                arm = res["arm"]
                tgap = res["generalization_test"]["test_rel_gap"]
                beats = res["generalization_test"]["test_beats_baseline"]
                el = res["elapsed_sec"]
                print(
                    f"[{completed:04d}/{total_runs:04d}] {dom:<14} b={b} w={w} {arm:<18} -> "
                    f"Test Gap: {tgap*100:+.2f}% | Beats: {beats} ({el:.1f}s)",
                    flush=True
                )
        else:
            print(f"Dispatching {total_runs} total runs across {self.workers} worker processes...", flush=True)
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.workers) as executor:
                tasks = {
                    executor.submit(_worker_execute_trial, (cfg, self.results_dir)): cfg
                    for cfg in configs
                }
                for fut in concurrent.futures.as_completed(tasks):
                    res = fut.result()
                    all_results.append(res)
                    completed += 1
                    dom = res["domain"]
                    b = res["total_budget"]
                    w = res["num_trajectories"]
                    arm = res["arm"]
                    tgap = res["generalization_test"]["test_rel_gap"]
                    beats = res["generalization_test"]["test_beats_baseline"]
                    el = res["elapsed_sec"]
                    print(
                        f"[{completed:04d}/{total_runs:04d}] {dom:<14} b={b} w={w} {arm:<18} -> "
                        f"Test Gap: {tgap*100:+.2f}% | Beats: {beats} ({el:.1f}s)",
                        flush=True
                    )

        total_time = round(time.time() - t_start, 2)
        print(f"\nAll {completed} runs completed in {total_time}s.", flush=True)

        # Analyze and summarize results
        summary = self.analyze_and_report(all_results, domains, arms, budgets, widths, num_trials)
        return summary

    def analyze_and_report(
        self,
        results: List[Dict[str, Any]],
        domains: List[str],
        arms: List[str],
        budgets: List[int],
        widths: List[int],
        num_trials: int
    ) -> Dict[str, Any]:
        """
        Computes paired statistics, Wilcoxon tests, Holm-Bonferroni corrections,
        and generates best-so-far curve plots.
        """
        analysis: Dict[str, Any] = {
            "mode": self.mode,
            "num_trials": num_trials,
            "domains": domains,
            "arms": arms,
            "budgets": budgets,
            "widths": widths,
            "cells": {}
        }

        plots_dir = os.path.join(self.results_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)

        for domain in domains:
            for budget in budgets:
                for width in widths:
                    cell_key = f"{domain}_b{budget}_w{width}"
                    cell_results = [
                        r for r in results
                        if r["domain"] == domain and r["total_budget"] == budget and r["num_trajectories"] == width
                    ]

                    # Organize by arm and seed
                    by_arm: Dict[str, List[Dict[str, Any]]] = {a: [] for a in arms}
                    for r in cell_results:
                        by_arm[r["arm"]].append(r)

                    # Extract Arm A (control)
                    control_runs = by_arm.get("arm_a_best_of_n", [])
                    assert len(control_runs) == num_trials, f"Expected {num_trials} control runs, got {len(control_runs)}"

                    cell_summary: Dict[str, Any] = {
                        "arms": {},
                        "paired_comparisons_vs_control": {}
                    }

                    # Descriptive stats per arm
                    for arm in arms:
                        runs = by_arm[arm]
                        test_gaps = [r["generalization_test"]["test_rel_gap"] for r in runs]
                        train_gaps = [r["selection"]["train_rel_gap"] for r in runs]
                        beats_cnt = sum(1 for r in runs if r["generalization_test"]["test_beats_baseline"])

                        curves = [r["best_so_far_curve"] for r in runs]
                        agg_curve = aggregate_curves(curves)

                        cell_summary["arms"][arm] = {
                            "test_relative_gap": compute_descriptive_stats(test_gaps),
                            "train_relative_gap": compute_descriptive_stats(train_gaps),
                            "generalization_beat_baseline_rate": round(beats_cnt / len(runs), 4),
                            "best_so_far_curve": agg_curve
                        }

                    # Paired inferential statistics vs Arm A
                    p_values = []
                    feedback_arms = [a for a in arms if a != "arm_a_best_of_n"]
                    comparison_records = []

                    for arm in feedback_arms:
                        arm_runs = by_arm[arm]
                        # Pair by trial index
                        diffs = [
                            arm_runs[i]["generalization_test"]["test_rel_gap"] - control_runs[i]["generalization_test"]["test_rel_gap"]
                            for i in range(num_trials)
                        ]
                        stat, raw_p = compute_paired_wilcoxon(diffs)
                        ci_low, ci_high = compute_bootstrap_ci(diffs, n_resamples=10000)
                        mean_diff = round(float(np.mean(diffs)), 6)
                        median_diff = round(float(np.median(diffs)), 6)

                        p_values.append(raw_p)
                        comparison_records.append({
                            "arm": arm,
                            "mean_paired_difference": mean_diff,
                            "median_paired_difference": median_diff,
                            "ci_95": [ci_low, ci_high],
                            "wilcoxon_stat": stat,
                            "raw_p_value": raw_p,
                            "diffs": diffs
                        })

                    # Apply Holm-Bonferroni correction
                    adj_p_values = apply_holm_bonferroni(p_values)
                    for idx, rec in enumerate(comparison_records):
                        rec["holm_adjusted_p_value"] = adj_p_values[idx]
                        rec["significant_at_05"] = bool(adj_p_values[idx] < 0.05)
                        rec["practically_meaningful"] = bool(rec["median_paired_difference"] <= -0.01 and adj_p_values[idx] < 0.05)
                        cell_summary["paired_comparisons_vs_control"][rec["arm"]] = rec

                    analysis["cells"][cell_key] = cell_summary

                    # Generate plot for this cell
                    self._generate_cell_plot(domain, budget, width, cell_summary, plots_dir)

        # Write analysis summary JSON
        summary_path = os.path.join(self.results_dir, "benchmark_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2)

        # Generate markdown report
        self._generate_markdown_report(analysis)
        return analysis

    def _generate_cell_plot(
        self,
        domain: str,
        budget: int,
        width: int,
        cell_summary: Dict[str, Any],
        plots_dir: str
    ):
        """Generates convergence curve plot comparing all arms in this cell."""
        plt.figure(figsize=(9, 5))
        colors = {
            "arm_a_best_of_n": "#2b5c8f",
            "arm_b_refinement": "#d95f02",
            "arm_c_evolution": "#7570b3",
            "arm_d_multi_island": "#e7298a",
            "arm_e_evidence": "#1b9e77"
        }
        labels = {
            "arm_a_best_of_n": "Arm A (Best-of-N)",
            "arm_b_refinement": "Arm B (Refinement)",
            "arm_c_evolution": "Arm C (Evolution)",
            "arm_d_multi_island": "Arm D (Multi-Island)",
            "arm_e_evidence": "Arm E (Evidence)"
        }

        for arm, color in colors.items():
            if arm in cell_summary["arms"]:
                med_curve = cell_summary["arms"][arm]["best_so_far_curve"]["median"]
                if med_curve:
                    x = list(range(1, len(med_curve) + 1))
                    plt.plot(x, med_curve, label=labels.get(arm, arm), color=color, linewidth=2)

        plt.title(f"{domain.upper()} (Budget: {budget}, Width: {width} trajs) - Best-So-Far Training Convergence")
        plt.xlabel("Candidate Proposals")
        plt.ylabel("Training Score (Lower is Better)")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend(loc="upper right")
        plt.tight_layout()

        plot_path = os.path.join(plots_dir, f"curve_{domain}_b{budget}_w{width}.png")
        plt.savefig(plot_path, dpi=150)
        plt.close()

    def _generate_markdown_report(self, analysis: Dict[str, Any]):
        """Generates structured scientific report for the run."""
        lines = [
            f"# Benchmark V1 Scientific Results Report ({analysis['mode'].upper()})",
            f"**Trials per condition:** {analysis['num_trials']}",
            "",
            "## 1. Summary of Paired Statistical Comparisons vs. Arm A (Control)",
            "",
            "| Domain | Budget | Width | Arm | Mean Diff (Δ) | Median Diff | 95% Bootstrap CI | Raw p | Holm p | Meaningful? |",
            "|---|---|---|---|---|---|---|---|---|---|"
        ]

        for cell_key, cell in analysis["cells"].items():
            parts = cell_key.split("_")
            dom = parts[0] + ("_" + parts[1] if parts[1] not in ["b128", "b512"] else "")
            budg = [p for p in parts if p.startswith("b")][0].replace("b", "")
            wid = [p for p in parts if p.startswith("w")][0].replace("w", "")

            for arm, comp in cell["paired_comparisons_vs_control"].items():
                ci_str = f"[{comp['ci_95'][0]:+.4f}, {comp['ci_95'][1]:+.4f}]"
                m_str = "YES" if comp["practically_meaningful"] else "NO"
                lines.append(
                    f"| {dom} | {budg} | {wid} | {arm} | {comp['mean_paired_difference']*100:+.2f}% | "
                    f"{comp['median_paired_difference']*100:+.2f}% | {ci_str} | "
                    f"{comp['raw_p_value']:.4f} | {comp['holm_adjusted_p_value']:.4f} | **{m_str}** |"
                )

        lines.extend([
            "",
            "## 2. Generalization Test Gap by Arm (Mean ± Std)",
            "",
            "| Condition | Arm A (Control) | Arm B (Refinement) | Arm C (Evolution) | Arm D (Multi-Island) | Arm E (Evidence) |",
            "|---|---|---|---|---|---|"
        ])

        for cell_key, cell in analysis["cells"].items():
            row = [f"| {cell_key} "]
            for arm in ["arm_a_best_of_n", "arm_b_refinement", "arm_c_evolution", "arm_d_multi_island", "arm_e_evidence"]:
                if arm in cell["arms"]:
                    st = cell["arms"][arm]["test_relative_gap"]
                    row.append(f"| {st['mean']*100:+.2f}% ± {st['std']*100:.2f}% ")
                else:
                    row.append("| N/A ")
            row.append("|")
            lines.append("".join(row))

        report_path = os.path.join(self.results_dir, "report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report written to: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="pilot", choices=["pilot", "confirmatory"])
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--budgets", nargs="+", type=int, default=[128])
    parser.add_argument("--widths", nargs="+", type=int, default=[1, 4, 8])
    parser.add_argument("--domains", nargs="+", type=str, default=["bin_packing", "graph_coloring", "pfsp"])
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (1 for strictly sequential)")
    parser.add_argument("--generator", type=str, default="simulated", choices=["simulated", "live_llm"])
    parser.add_argument("--results-dir", type=str, default=None, help="Explicit directory for outputs")
    args = parser.parse_args()

    orchestrator = ExperimentOrchestrator(mode=args.mode, results_dir=args.results_dir, workers=args.workers)
    arms = ["arm_a_best_of_n", "arm_b_refinement", "arm_c_evolution", "arm_d_multi_island", "arm_e_evidence"]
    orchestrator.run_benchmark_grid(
        domains=args.domains,
        arms=arms,
        budgets=args.budgets,
        widths=args.widths,
        num_trials=args.trials,
        generator_type=args.generator
    )
