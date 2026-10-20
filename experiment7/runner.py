"""
Experiment #7: Full Solver Synthesis Orchestrator
=================================================
Executes:
1. Condition A: Human Baselines (Greedy, Welsh-Powell, DSATUR, RLF) on Dev and Hidden.
2. Condition B: Single-Shot LLM generation (diverse macro-paradigms, concise & complete).
3. Condition C: Iterative & Evolutionary Discovery (10 generations with diagnostic feedback).
4. Frozen Champion Hidden Evaluation (160 graphs across 8 families).
5. Comprehensive statistical analysis, generation progression, and macro-diversity tracking.
"""

import hashlib
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional
import numpy as np
import scipy.stats as stats

# Ensure local imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from experiment7.evaluator import (
    SolverEvaluator,
    NATURAL_GREEDY_CODE,
    WELSH_POWELL_CODE,
    DSATUR_CODE,
    RLF_CODE,
    Graph,
)
from experiment7.llm_client import SolverLLMClient
from experiment7.classifier import classify_macro_strategy


COMMON_REQUIREMENTS = """Requirements:
1. Focus on ONE coherent, effective macro-algorithmic strategy.
2. Keep the implementation clean, self-contained, and strictly under 120 lines of code.
3. It must execute rapidly (under 30 ms per graph). Do not write slow O(N^4) loops.
4. Ensure the function always terminates and returns `colors: list[int]` where len(colors) == len(adj), colors[u] >= 0, and adjacent vertices have different colors.
5. Return ONLY executable Python code inside a ```python ``` block.
"""


class Experiment7Runner:
    def __init__(self, output_dir: str = "experiment7"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.evaluator = SolverEvaluator(per_instance_budget_ms=50.0, per_instance_timeout_ms=300.0)
        self.client = SolverLLMClient()
        self.candidates_log_path = os.path.join(self.output_dir, "candidates.jsonl")
        self.lineage_path = os.path.join(self.output_dir, "lineage.json")
        self.results_csv_path = os.path.join(self.output_dir, "results.csv")
        self.all_candidates: List[Dict[str, Any]] = []

    def log_candidate(self, cand_record: Dict[str, Any]):
        """Persist candidate record to JSONL and memory."""
        self.all_candidates.append(cand_record)
        with open(self.candidates_log_path, "a") as f:
            f.write(json.dumps(cand_record) + "\n")

    # -----------------------------------------------------------------------
    # Phase 1: Condition A - Human Baselines
    # -----------------------------------------------------------------------
    def run_condition_a_baselines(self) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("PHASE 1: CONDITION A - HUMAN BASELINES EVALUATION")
        print("=" * 70)

        baselines = {
            "Greedy": NATURAL_GREEDY_CODE,
            "Welsh-Powell": WELSH_POWELL_CODE,
            "DSATUR": DSATUR_CODE,
            "RLF": RLF_CODE,
        }

        baseline_results = {}
        for name, code in baselines.items():
            dev_res = self.evaluator.evaluate_solver_code(code, dataset_type="dev")
            hidden_res = self.evaluator.evaluate_solver_code(code, dataset_type="hidden")
            classification = classify_macro_strategy(code)

            rec = {
                "name": name,
                "code": code,
                "classification": classification,
                "dev_total_colors": dev_res["total_colors"],
                "dev_avg_colors": dev_res["avg_colors"],
                "dev_runtime_ms": dev_res["runtime_ms"],
                "dev_scores": dev_res["scores"],
                "hidden_total_colors": hidden_res["total_colors"],
                "hidden_avg_colors": hidden_res["avg_colors"],
                "hidden_runtime_ms": hidden_res["runtime_ms"],
                "hidden_scores": hidden_res["scores"],
            }
            baseline_results[name] = rec
            print(f"  {name:15s} | Dev: {dev_res['total_colors']:4d} colors ({dev_res['runtime_ms']:6.1f}ms) | "
                  f"Hidden: {hidden_res['total_colors']:4d} colors ({hidden_res['runtime_ms']:6.1f}ms) | "
                  f"Strategy: {classification['primary_category']}")

        return baseline_results

    # -----------------------------------------------------------------------
    # Phase 2: Condition B - Single-Shot LLM Generation
    # -----------------------------------------------------------------------
    def run_condition_b_single_shot(self, baseline_scores: Dict[str, Any]) -> List[Dict[str, Any]]:
        print("\n" + "=" * 70)
        print("PHASE 2: CONDITION B - SINGLE-SHOT LLM GENERATION")
        print("=" * 70)

        dsatur_dev = baseline_scores["DSATUR"]["dev_total_colors"]
        rlf_dev = baseline_scores["RLF"]["dev_total_colors"]

        # 8 Prompts exploring distinct macro-algorithmic paradigms
        prompts = [
            # 1. Open unconstrained design
            (
                "single_shot_1_open",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"The objective is to minimize total colors used across diverse graph types.\n"
                f"You have complete macro-algorithmic freedom. Benchmark targets on dev: DSATUR = {dsatur_dev}, RLF = {rlf_dev}.\n"
                + COMMON_REQUIREMENTS
            ),
            # 2. Independent set extraction / RLF-style
            (
                "single_shot_2_indep_set",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Focus on an iterative independent set extraction paradigm (extracting maximal independent sets to form color classes),\n"
                f"optimizing which vertices are grouped together into the same color class to leave the remaining subgraph as easy to color as possible.\n"
                + COMMON_REQUIREMENTS
            ),
            # 3. Iterated Greedy / Multi-pass re-coloring
            (
                "single_shot_3_iterated_greedy",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Use a multi-pass iterated re-coloring strategy (similar to Culberson's Iterated Greedy),\n"
                f"where an initial coloring is constructed, vertices are reordered based on color classes or conflict statistics,\n"
                f"and re-colored over multiple fast passes to reduce the total number of colors.\n"
                + COMMON_REQUIREMENTS
            ),
            # 4. Saturation degree with local search / Kempe chains
            (
                "single_shot_4_dsatur_kempe",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Combine a fast constructive phase (such as saturation-degree ordering) with a local improvement phase,\n"
                f"such as Kempe chain color swaps or recoloring vertices belonging to the highest-numbered color classes to eliminate entire colors.\n"
                + COMMON_REQUIREMENTS
            ),
            # 5. Min-conflicts / repair local search
            (
                "single_shot_5_repair",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Implement a two-stage strategy: first, construct an initial coloring, then apply a fast conflict-repair or recoloring routine "
                f"focused on eliminating the rarest colors by redistributing their vertices to lower colors.\n"
                + COMMON_REQUIREMENTS
            ),
            # 6. Adaptive multi-heuristic selection
            (
                "single_shot_6_adaptive",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Inspect the graph structure (e.g. edge density, maximum degree) and adaptively select the best coloring strategy,\n"
                f"or run two complementary fast heuristics and return whichever uses fewer colors.\n"
                + COMMON_REQUIREMENTS
            ),
            # 7. Randomized restart with tie-break perturbation
            (
                "single_shot_7_random_restart",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Implement a fast randomized restart heuristic that introduces small stochastic tie-breaking into vertex selection,\n"
                f"runs 5 to 10 independent rapid coloring trials within a 30ms budget, and returns the trial using the fewest colors.\n"
                + COMMON_REQUIREMENTS
            ),
            # 8. Hybrid RLF + DSATUR
            (
                "single_shot_8_hybrid_rlf_dsatur",
                f"Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
                f"Design a hybrid algorithm combining the strengths of color-class extraction (RLF) with dynamic saturation-degree coloring (DSATUR).\n"
                + COMMON_REQUIREMENTS
            ),
        ]

        single_shot_candidates = []

        for cid, prompt_text in prompts:
            print(f"\n  Querying Claude for {cid}...")
            res = self.client.query(prompt_text, temperature=0.6, max_tokens=3200)
            if not res["success"] or not res["code"]:
                print(f"    [FAIL] Could not extract valid code: {res['error']}")
                cand_rec = {
                    "candidate_id": cid,
                    "phase": "single_shot",
                    "generation": 0,
                    "parent_id": "root",
                    "prompt": prompt_text,
                    "code": res.get("raw_text", ""),
                    "is_valid": False,
                    "error": res.get("error", "Code extraction failed"),
                    "dev_total_colors": 999999,
                    "dev_avg_colors": 999999.0,
                    "dev_runtime_ms": 0.0,
                    "macro_classification": {"primary_category": "failed_extraction", "detected_features": []},
                    "prompt_tokens": res.get("prompt_tokens", 0),
                    "completion_tokens": res.get("completion_tokens", 0),
                    "duration_ms": res.get("duration_ms", 0.0),
                }
                self.log_candidate(cand_rec)
                continue

            # Evaluate on Development set
            eval_res = self.evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
            classification = classify_macro_strategy(res["code"])

            cand_rec = {
                "candidate_id": cid,
                "phase": "single_shot",
                "generation": 0,
                "parent_id": "root",
                "prompt": prompt_text,
                "code": res["code"],
                "is_valid": eval_res["is_valid"],
                "error": eval_res.get("error"),
                "dev_total_colors": eval_res["total_colors"],
                "dev_avg_colors": eval_res["avg_colors"],
                "dev_runtime_ms": eval_res["runtime_ms"],
                "dev_scores": eval_res.get("scores", []),
                "macro_classification": classification,
                "prompt_tokens": res["prompt_tokens"],
                "completion_tokens": res["completion_tokens"],
                "duration_ms": res["duration_ms"],
            }
            self.log_candidate(cand_rec)
            single_shot_candidates.append(cand_rec)

            status = "VALID" if eval_res["is_valid"] else "INVALID"
            print(f"    [{status}] Dev: {eval_res['total_colors']} colors (DSATUR={dsatur_dev}, RLF={rlf_dev}) | "
                  f"Time: {eval_res['runtime_ms']:.1f}ms | Strategy: {classification['primary_category']}")
            if not eval_res["is_valid"]:
                print(f"      Validation Error: {eval_res.get('error')}")

        return single_shot_candidates

    # -----------------------------------------------------------------------
    # Phase 3: Condition C - Iterative & Evolutionary Discovery Loop
    # -----------------------------------------------------------------------
    def run_condition_c_evolution(
        self,
        initial_candidates: List[Dict[str, Any]],
        baseline_scores: Dict[str, Any],
        num_generations: int = 10
    ) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("PHASE 3: CONDITION C - ITERATIVE EVOLUTIONARY SEARCH WITH FEEDBACK")
        print("=" * 70)

        valid_initial = [c for c in initial_candidates if c["is_valid"]]
        if not valid_initial:
            print("  [ERROR] No valid candidates in initial pool. Aborting evolution.")
            return {}

        dsatur_dev = baseline_scores["DSATUR"]["dev_total_colors"]
        rlf_dev = baseline_scores["RLF"]["dev_total_colors"]

        # Track population and lineage
        population = sorted(valid_initial, key=lambda x: x["dev_total_colors"])[:6]
        best_so_far = population[0]
        generation_progression = [
            {
                "generation": 0,
                "best_candidate_id": best_so_far["candidate_id"],
                "best_dev_colors": best_so_far["dev_total_colors"],
                "best_strategy": best_so_far["macro_classification"]["primary_category"],
                "population_avg": round(float(np.mean([c["dev_total_colors"] for c in population])), 2),
                "num_improvements": 0,
            }
        ]

        print(f"\n  Gen 0 Best: {best_so_far['candidate_id']} ({best_so_far['dev_total_colors']} colors, {best_so_far['macro_classification']['primary_category']})")

        for gen in range(1, num_generations + 1):
            print(f"\n--- Generation {gen} / {num_generations} ---")
            gen_improvements = 0
            gen_candidates = []

            operators = [
                ("exploit", "Refine and optimize current champion with targeted credit feedback"),
                ("crossover", "Synthesize hybrid combining top complementary macro-strategies"),
                ("explore", "Explore radical new macro-algorithm designed to beat current champion"),
            ]

            for op_type, op_desc in operators:
                cand_id = f"gen{gen}_{op_type}_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:6]}"

                if op_type == "exploit":
                    parent = best_so_far
                    prompt = (
                        f"You are iteratively optimizing a complete graph coloring solver.\n"
                        f"Current Champion ({parent['candidate_id']}) achieved {parent['dev_total_colors']} total colors on the 40 development graphs.\n"
                        f"Human Baselines: DSATUR = {dsatur_dev} colors, RLF = {rlf_dev} colors.\n"
                        f"Current runtime: {parent['dev_runtime_ms']:.1f}ms.\n\n"
                        f"Current Champion Code:\n```python\n{parent['code']}\n```\n\n"
                        f"Task: Modify and refine this solver to use FEWER colors while keeping runtime strictly under 30ms per graph.\n"
                        f"Analyze where colors might be wasted and implement a concrete algorithmic improvement.\n"
                        + COMMON_REQUIREMENTS
                    )
                elif op_type == "crossover":
                    parent_a = population[0]
                    parent_b = population[1] if len(population) > 1 else population[0]
                    for p in population[1:]:
                        if p["macro_classification"]["primary_category"] != parent_a["macro_classification"]["primary_category"]:
                            parent_b = p
                            break

                    prompt = (
                        f"You are hybridizing two successful, distinct graph coloring strategies.\n"
                        f"Parent A ({parent_a['candidate_id']}, {parent_a['macro_classification']['primary_category']}): {parent_a['dev_total_colors']} colors.\n"
                        f"Parent B ({parent_b['candidate_id']}, {parent_b['macro_classification']['primary_category']}): {parent_b['dev_total_colors']} colors.\n"
                        f"Baselines: DSATUR = {dsatur_dev}, RLF = {rlf_dev}.\n\n"
                        f"Parent A Code:\n```python\n{parent_a['code']}\n```\n\n"
                        f"Parent B Code:\n```python\n{parent_b['code']}\n```\n\n"
                        f"Task: Synthesize a hybrid solver combining the complementary advantages of both approaches.\n"
                        f"Ensure it runs under 30ms per graph and reduces the total color count below {min(parent_a['dev_total_colors'], parent_b['dev_total_colors'])}.\n"
                        + COMMON_REQUIREMENTS
                    )
                else:  # explore
                    prompt = (
                        f"Current best solver achieves {best_so_far['dev_total_colors']} colors using a {best_so_far['macro_classification']['primary_category']} approach.\n"
                        f"Baselines: DSATUR = {dsatur_dev}, RLF = {rlf_dev}.\n"
                        f"Task: Propose a fundamentally DIFFERENT macro-algorithmic strategy to solve graph coloring.\n"
                        f"Explore an alternative paradigm (e.g. Iterated Greedy recoloring with largest-color-class ordering, or RLF with lookahead independent sets, or fast Kempe chain swaps).\n"
                        + COMMON_REQUIREMENTS
                    )

                res = self.client.query(prompt, temperature=0.6, max_tokens=3200)
                if not res["success"] or not res["code"]:
                    print(f"  [{cand_id}] Generation failed to produce code: {res.get('error')}")
                    continue

                eval_res = self.evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
                classification = classify_macro_strategy(res["code"])

                cand_rec = {
                    "candidate_id": cand_id,
                    "phase": "evolution",
                    "generation": gen,
                    "parent_id": best_so_far["candidate_id"] if op_type == "exploit" else "hybrid_or_explore",
                    "operator": op_type,
                    "prompt": prompt,
                    "code": res["code"],
                    "is_valid": eval_res["is_valid"],
                    "error": eval_res.get("error"),
                    "dev_total_colors": eval_res["total_colors"],
                    "dev_avg_colors": eval_res["avg_colors"],
                    "dev_runtime_ms": eval_res["runtime_ms"],
                    "dev_scores": eval_res.get("scores", []),
                    "macro_classification": classification,
                    "prompt_tokens": res["prompt_tokens"],
                    "completion_tokens": res["completion_tokens"],
                    "duration_ms": res["duration_ms"],
                }
                self.log_candidate(cand_rec)
                gen_candidates.append(cand_rec)

                if eval_res["is_valid"]:
                    delta = eval_res["total_colors"] - best_so_far["dev_total_colors"]
                    delta_str = f"{delta:+d}"
                    if eval_res["total_colors"] < best_so_far["dev_total_colors"]:
                        print(f"  [{cand_id}] *** IMPROVEMENT! *** Dev: {eval_res['total_colors']} ({delta_str}) | Strategy: {classification['primary_category']}")
                        best_so_far = cand_rec
                        gen_improvements += 1
                    else:
                        print(f"  [{cand_id}] Valid Dev: {eval_res['total_colors']} ({delta_str}) | Time: {eval_res['runtime_ms']:.1f}ms | Strategy: {classification['primary_category']}")
                else:
                    print(f"  [{cand_id}] INVALID: {eval_res.get('error')}")

            # Update population with valid candidates from this generation
            valid_gen = [c for c in gen_candidates if c["is_valid"]]
            population = sorted(population + valid_gen, key=lambda x: x["dev_total_colors"])[:6]

            generation_progression.append({
                "generation": gen,
                "best_candidate_id": best_so_far["candidate_id"],
                "best_dev_colors": best_so_far["dev_total_colors"],
                "best_strategy": best_so_far["macro_classification"]["primary_category"],
                "population_avg": round(float(np.mean([c["dev_total_colors"] for c in population])), 2),
                "num_improvements": gen_improvements,
            })
            print(f"  Gen {gen} Summary: Best = {best_so_far['dev_total_colors']} colors | Pop Avg = {generation_progression[-1]['population_avg']}")

        return {
            "champion": best_so_far,
            "progression": generation_progression,
            "final_population": population,
        }

    # -----------------------------------------------------------------------
    # Phase 4 & 5: Hidden Benchmark Evaluation & Statistical Analysis
    # -----------------------------------------------------------------------
    def run_hidden_evaluation_and_statistics(
        self,
        champion: Dict[str, Any],
        best_single_shot: Dict[str, Any],
        baseline_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("PHASE 4: FROZEN CHAMPION EVALUATION ON 160-GRAPH HIDDEN BENCHMARK")
        print("=" * 70)

        # 1. Evaluate Champion on Hidden Suite
        print(f"  Evaluating Development Champion: {champion['candidate_id']} ({champion['macro_classification']['primary_category']})...")
        champ_hidden_res = self.evaluator.evaluate_solver_code(champion["code"], dataset_type="hidden")
        print(f"    Champion Hidden Total: {champ_hidden_res['total_colors']} colors | Runtime: {champ_hidden_res['runtime_ms']:.1f}ms")

        # 2. Evaluate Best Single-Shot on Hidden Suite
        print(f"  Evaluating Best Single-Shot: {best_single_shot['candidate_id']} ({best_single_shot['macro_classification']['primary_category']})...")
        ss_hidden_res = self.evaluator.evaluate_solver_code(best_single_shot["code"], dataset_type="hidden")
        print(f"    Single-Shot Hidden Total: {ss_hidden_res['total_colors']} colors | Runtime: {ss_hidden_res['runtime_ms']:.1f}ms")

        # 3. Paired Statistical Comparisons across all 160 Hidden Graphs
        print("\n" + "=" * 70)
        print("PHASE 5: RIGOROUS PAIRED STATISTICAL ANALYSIS ON HIDDEN BENCHMARK")
        print("=" * 70)

        c_scores = np.array(champ_hidden_res["scores"])
        ss_scores = np.array(ss_hidden_res["scores"])
        dsatur_scores = np.array(baseline_results["DSATUR"]["hidden_scores"])
        rlf_scores = np.array(baseline_results["RLF"]["hidden_scores"])
        wp_scores = np.array(baseline_results["Welsh-Powell"]["hidden_scores"])
        greedy_scores = np.array(baseline_results["Greedy"]["hidden_scores"])

        def paired_analysis(cand: np.ndarray, base: np.ndarray, name: str) -> Dict[str, Any]:
            diff = cand - base  # negative means cand won
            n = len(diff)
            wins = int(np.sum(diff < 0))
            losses = int(np.sum(diff > 0))
            ties = int(np.sum(diff == 0))
            mean_diff = float(np.mean(diff))
            median_diff = float(np.median(diff))
            std_diff = float(np.std(diff, ddof=1)) if n > 1 else 0.0
            sem = std_diff / np.sqrt(n) if n > 0 else 0.0

            ci_half = stats.t.ppf(0.975, df=n - 1) * sem if n > 1 and std_diff > 0 else 0.0
            ci_low = mean_diff - ci_half
            ci_high = mean_diff + ci_half

            non_zero = diff[diff != 0]
            if len(non_zero) > 0:
                try:
                    w_res = stats.wilcoxon(non_zero, alternative="two-sided")
                    w_p = float(w_res.pvalue)
                except Exception:
                    w_p = 1.0
            else:
                w_p = 1.0

            # Permutation test (10,000 resamples)
            if len(non_zero) > 0:
                rng = np.random.RandomState(42)
                observed_stat = abs(mean_diff)
                signs = rng.choice([-1, 1], size=(10000, n))
                permuted_means = np.abs(np.mean(diff * signs, axis=1))
                perm_p = float(np.mean(permuted_means >= observed_stat))
            else:
                perm_p = 1.0

            # Cohen's d
            cohens_d = mean_diff / std_diff if std_diff > 0 else 0.0

            return {
                "comparison": name,
                "n": n,
                "cand_total": int(np.sum(cand)),
                "base_total": int(np.sum(base)),
                "net_diff": int(np.sum(diff)),
                "mean_diff": round(mean_diff, 4),
                "median_diff": round(median_diff, 4),
                "std_diff": round(std_diff, 4),
                "sem": round(sem, 4),
                "ci_95": [round(ci_low, 4), round(ci_high, 4)],
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "wilcoxon_p": float(w_p),
                "permutation_p": float(perm_p),
                "cohens_d": round(cohens_d, 4),
            }

        stats_vs_dsatur = paired_analysis(c_scores, dsatur_scores, "Champion vs DSATUR")
        stats_vs_rlf = paired_analysis(c_scores, rlf_scores, "Champion vs RLF")
        stats_vs_wp = paired_analysis(c_scores, wp_scores, "Champion vs Welsh-Powell")
        stats_vs_greedy = paired_analysis(c_scores, greedy_scores, "Champion vs Greedy")
        stats_champ_vs_ss = paired_analysis(c_scores, ss_scores, "Champion (Evolution) vs Best Single-Shot")

        all_stats = [stats_vs_dsatur, stats_vs_rlf, stats_vs_wp, stats_vs_greedy, stats_champ_vs_ss]
        for s in all_stats:
            print(f"  {s['comparison']:38s} | W={s['wins']:3d}, L={s['losses']:3d}, T={s['ties']:3d} | "
                  f"Net={s['net_diff']:+4d} | Mean={s['mean_diff']:+.4f} (95% CI: {s['ci_95']}) | "
                  f"Wilcoxon p={s['wilcoxon_p']:.4f} | Cohen's d={s['cohens_d']:+.3f}")

        # 4. Per-Family Breakdown for Champion vs DSATUR and RLF
        print("\n  Per-Family Breakdown for Champion on Hidden Benchmark (20 graphs per family):")
        family_results = {}
        graphs_by_fam = self.evaluator.suite.hidden_dataset

        start_idx = 0
        for fam, glist in graphs_by_fam.items():
            end_idx = start_idx + len(glist)
            c_fam = c_scores[start_idx:end_idx]
            d_fam = dsatur_scores[start_idx:end_idx]
            r_fam = rlf_scores[start_idx:end_idx]

            fam_vs_d = paired_analysis(c_fam, d_fam, f"{fam} vs DSATUR")
            fam_vs_r = paired_analysis(c_fam, r_fam, f"{fam} vs RLF")

            family_results[fam] = {
                "vs_dsatur": fam_vs_d,
                "vs_rlf": fam_vs_r,
            }
            print(f"    {fam:22s} | vs DSATUR: W={fam_vs_d['wins']:2d}, L={fam_vs_d['losses']:2d}, T={fam_vs_d['ties']:2d} (Net={fam_vs_d['net_diff']:+2d}, p={fam_vs_d['wilcoxon_p']:.4f}) | "
                  f"vs RLF: W={fam_vs_r['wins']:2d}, L={fam_vs_r['losses']:2d}, T={fam_vs_r['ties']:2d} (Net={fam_vs_r['net_diff']:+2d}, p={fam_vs_r['wilcoxon_p']:.4f})")
            start_idx = end_idx

        return {
            "champ_hidden": champ_hidden_res,
            "single_shot_hidden": ss_hidden_res,
            "paired_stats": {
                "vs_dsatur": stats_vs_dsatur,
                "vs_rlf": stats_vs_rlf,
                "vs_welsh_powell": stats_vs_wp,
                "vs_greedy": stats_vs_greedy,
                "champ_vs_single_shot": stats_champ_vs_ss,
            },
            "family_breakdown": family_results,
        }

    # -----------------------------------------------------------------------
    # Master Execution Routine
    # -----------------------------------------------------------------------
    def run_experiment_7(self):
        t0 = time.time()
        print("=" * 78)
        print("AMAURA EXPERIMENT #7: FULL SOLVER SYNTHESIS")
        print("Model: Claude Sonnet 4-6 | Domain: Graph Coloring | Interface: color_graph(adj)")
        print("=" * 78)

        # Clear candidates log if restarting
        if os.path.exists(self.candidates_log_path):
            os.remove(self.candidates_log_path)

        # 1. Condition A: Baselines
        baseline_results = self.run_condition_a_baselines()

        # 2. Condition B: Single-Shot LLM
        single_shot_candidates = self.run_condition_b_single_shot(baseline_results)
        valid_ss = [c for c in single_shot_candidates if c["is_valid"]]
        best_single_shot = min(valid_ss, key=lambda x: x["dev_total_colors"]) if valid_ss else None

        if not best_single_shot:
            print("CRITICAL FAILURE: No valid single-shot solver produced. Aborting.")
            return

        print(f"\n>>> Best Single-Shot Candidate: {best_single_shot['candidate_id']} ({best_single_shot['dev_total_colors']} colors, {best_single_shot['macro_classification']['primary_category']})")

        # 3. Condition C: Evolution
        evolution_results = self.run_condition_c_evolution(
            initial_candidates=single_shot_candidates,
            baseline_scores=baseline_results,
            num_generations=10
        )
        champion = evolution_results.get("champion", best_single_shot)
        progression = evolution_results.get("progression", [])

        print(f"\n>>> Final Frozen Champion: {champion['candidate_id']} ({champion['dev_total_colors']} dev colors, {champion['macro_classification']['primary_category']})")

        # 4. Hidden Evaluation & Statistical Analysis
        hidden_analysis = self.run_hidden_evaluation_and_statistics(
            champion=champion,
            best_single_shot=best_single_shot,
            baseline_results=baseline_results
        )

        total_elapsed = time.time() - t0

        # Save Lineage and Summary
        summary = {
            "experiment": "Experiment #7 - Full Solver Synthesis",
            "model": "antigravity/claude-sonnet-4-6",
            "total_runtime_seconds": round(total_elapsed, 2),
            "token_usage": {
                "total_calls": self.client.total_calls,
                "total_prompt_tokens": self.client.total_prompt_tokens,
                "total_completion_tokens": self.client.total_completion_tokens,
                "failed_calls": self.client.failed_calls,
            },
            "baseline_results": {
                k: {
                    "dev_total_colors": v["dev_total_colors"],
                    "dev_runtime_ms": v["dev_runtime_ms"],
                    "hidden_total_colors": v["hidden_total_colors"],
                    "hidden_runtime_ms": v["hidden_runtime_ms"],
                    "primary_category": v["classification"]["primary_category"],
                } for k, v in baseline_results.items()
            },
            "best_single_shot": {
                "candidate_id": best_single_shot["candidate_id"],
                "dev_total_colors": best_single_shot["dev_total_colors"],
                "hidden_total_colors": hidden_analysis["single_shot_hidden"]["total_colors"],
                "strategy": best_single_shot["macro_classification"]["primary_category"],
                "code": best_single_shot["code"],
            },
            "champion": {
                "candidate_id": champion["candidate_id"],
                "dev_total_colors": champion["dev_total_colors"],
                "hidden_total_colors": hidden_analysis["champ_hidden"]["total_colors"],
                "strategy": champion["macro_classification"]["primary_category"],
                "code": champion["code"],
            },
            "progression": progression,
            "hidden_statistical_analysis": hidden_analysis["paired_stats"],
            "family_breakdown": hidden_analysis["family_breakdown"],
        }

        summary_path = os.path.join(self.output_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n[OUTPUT] Saved experiment summary to {summary_path}")

        # Also write results.csv
        with open(self.results_csv_path, "w") as f:
            f.write("Algorithm,Dev_Total_Colors,Dev_Runtime_ms,Hidden_Total_Colors,Hidden_Runtime_ms,Strategy\n")
            for bname, bdata in summary["baseline_results"].items():
                f.write(f"Baseline_{bname},{bdata['dev_total_colors']},{bdata['dev_runtime_ms']},{bdata['hidden_total_colors']},{bdata['hidden_runtime_ms']},{bdata['primary_category']}\n")
            f.write(f"Best_Single_Shot_{summary['best_single_shot']['candidate_id']},{summary['best_single_shot']['dev_total_colors']},-,{summary['best_single_shot']['hidden_total_colors']},-,{summary['best_single_shot']['strategy']}\n")
            f.write(f"Champion_{summary['champion']['candidate_id']},{summary['champion']['dev_total_colors']},-,{summary['champion']['hidden_total_colors']},-,{summary['champion']['strategy']}\n")
        print(f"[OUTPUT] Saved results CSV to {self.results_csv_path}")

        print("\n" + "=" * 78)
        print("EXPERIMENT #7 RUNNER COMPLETED.")
        print("=" * 78)


if __name__ == "__main__":
    runner = Experiment7Runner()
    runner.run_experiment_7()
