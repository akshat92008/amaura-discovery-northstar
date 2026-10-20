"""
Experiment #8 Resumption and Completion Script
==============================================
Resumes Experiment #8 from the exact state in candidates.jsonl:
- Completes Trial 3 Condition B (calls 10-15)
- Completes Trial 3 Condition C (calls 1-15)
- Evaluates best candidates from all 3 trials across all 3 conditions on the 160 Hidden Graphs
- Evaluates Classical Baselines on the 160 Hidden Graphs
- Performs full statistical analysis and exports summary.json
"""

import hashlib
import json
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import scipy.stats as stats

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from experiment8.evaluator import (
    SolverEvaluator,
    NATURAL_GREEDY_CODE,
    WELSH_POWELL_CODE,
    DSATUR_CODE,
    RLF_CODE,
)
from experiment8.llm_client import SolverLLMClient
from experiment8.classifier import classify_macro_strategy
from experiment8.runner import COMMON_REQUIREMENTS, INDEPENDENT_PROMPTS


def resume_and_complete():
    output_dir = os.path.abspath("experiment8")
    candidates_log_path = os.path.join(output_dir, "candidates.jsonl")
    summary_json_path = os.path.join(output_dir, "summary.json")

    evaluator = SolverEvaluator(per_instance_budget_ms=50.0, per_instance_timeout_ms=300.0)
    client = SolverLLMClient()

    # 1. Load existing candidates
    existing_candidates = []
    with open(candidates_log_path, "r") as f:
        for line in f:
            existing_candidates.append(json.loads(line))
    print(f"Loaded {len(existing_candidates)} existing candidates from {candidates_log_path}.")

    def log_candidate(rec: Dict[str, Any]):
        with open(candidates_log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        existing_candidates.append(rec)

    # -----------------------------------------------------------------------
    # Part 1: Complete Trial 3 Condition B (calls 10-15)
    # -----------------------------------------------------------------------
    t3_b_cands = [c for c in existing_candidates if c["trial"] == 3 and c["condition"] == "Condition_B_Evolution"]
    t3_b_cands.sort(key=lambda x: x["call_index"])
    print(f"\n[Trial 3] Resuming Condition B from call {len(t3_b_cands) + 1}/15...")

    # Build active population from valid candidates
    population = [c for c in t3_b_cands if c["is_valid"]]
    population.sort(key=lambda x: x["dev_total_colors"])
    best_b_dev = population[0]["dev_total_colors"] if population else 999999
    print(f"  Current population size: {len(population)}, Current Best Dev: {best_b_dev}")

    # Determine which generations need to be run
    # Gen 1: calls 6, 7 (already done)
    # Gen 2: calls 8, 9 (already done)
    # Gen 3: calls 10, 11
    # Gen 4: calls 12, 13
    # Gen 5: calls 14, 15
    for call_counter in range(len(t3_b_cands) + 1, 16):
        gen = (call_counter - 6) // 2 + 1
        is_cross = (call_counter % 2 == 1)

        population.sort(key=lambda x: x["dev_total_colors"])
        if not is_cross:
            # Exploitation
            parent_a = population[0]
            cand_id = f"t3_condB_gen{gen}_exploit_{call_counter}"
            prompt = (
                f"You are iteratively refining a complete graph coloring solver.\n"
                f"Current Champion ({parent_a['candidate_id']}) achieved {parent_a['dev_total_colors']} total colors on dev benchmark.\n"
                f"Runtime: {parent_a['dev_runtime_ms']:.1f}ms. Strategy: {parent_a['macro_classification']['primary_category']}.\n\n"
                f"Code:\n```python\n{parent_a['code']}\n```\n\n"
                f"Task: Modify and optimize this solver to use FEWER colors while keeping runtime strictly under 30ms per graph.\n"
                + COMMON_REQUIREMENTS
            )
            parents = [parent_a["candidate_id"]]
            label = f"Gen{gen} Exploit"
        else:
            # Crossover
            parent_1 = population[0]
            parent_2 = population[1] if len(population) > 1 else population[0]
            for p in population[1:]:
                if p["macro_classification"]["primary_category"] != parent_1["macro_classification"]["primary_category"]:
                    parent_2 = p
                    break
            cand_id = f"t3_condB_gen{gen}_cross_{call_counter}"
            prompt = (
                f"You are hybridizing two distinct graph coloring strategies.\n"
                f"Parent 1 ({parent_1['candidate_id']}): {parent_1['dev_total_colors']} colors ({parent_1['macro_classification']['primary_category']}).\n"
                f"Parent 2 ({parent_2['candidate_id']}): {parent_2['dev_total_colors']} colors ({parent_2['macro_classification']['primary_category']}).\n\n"
                f"Parent 1 Code:\n```python\n{parent_1['code']}\n```\n\n"
                f"Parent 2 Code:\n```python\n{parent_2['code']}\n```\n\n"
                f"Task: Synthesize a hybrid solver combining the complementary strengths of both approaches to use fewer colors than {min(parent_1['dev_total_colors'], parent_2['dev_total_colors'])}.\n"
                + COMMON_REQUIREMENTS
            )
            parents = [parent_1["candidate_id"], parent_2["candidate_id"]]
            label = f"Gen{gen} Cross"

        print(f"    Call {call_counter:2d}/15 ({label}): Querying model...")
        res = client.query(prompt, temperature=0.6, max_tokens=3200)
        if not res["success"] or not res["code"]:
            print(f"      Call {call_counter:2d}/15 failed to extract code: {res.get('error')}")
            rec = {
                "candidate_id": cand_id, "trial": 3, "condition": "Condition_B_Evolution",
                "call_index": call_counter, "parent_ids": parents, "generation": gen,
                "is_valid": False, "dev_total_colors": 999999, "dev_runtime_ms": 0.0,
                "dev_scores": [], "error": res.get("error", "Code extraction failed"),
                "prompt_tokens": res.get("prompt_tokens", 0), "completion_tokens": res.get("completion_tokens", 0),
                "code": "", "macro_classification": {"primary_category": "failed"}
            }
            log_candidate(rec)
            continue

        eval_res = evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
        classification = classify_macro_strategy(res["code"])
        rec = {
            "candidate_id": cand_id, "trial": 3, "condition": "Condition_B_Evolution",
            "call_index": call_counter, "parent_ids": parents, "generation": gen,
            "is_valid": eval_res["is_valid"], "dev_total_colors": eval_res["total_colors"],
            "dev_runtime_ms": eval_res["runtime_ms"], "dev_scores": eval_res.get("scores", []),
            "error": eval_res.get("error"), "prompt_tokens": res["prompt_tokens"],
            "completion_tokens": res["completion_tokens"], "code": res["code"],
            "macro_classification": classification,
        }
        log_candidate(rec)

        if eval_res["is_valid"]:
            population.append(rec)
            if eval_res["total_colors"] < best_b_dev:
                print(f"      *** IMPROVEMENT! *** Dev = {eval_res['total_colors']} colors (was {best_b_dev}) | Strategy = {classification['primary_category']}")
                best_b_dev = eval_res["total_colors"]
            else:
                print(f"      Dev = {eval_res['total_colors']} colors | Best = {best_b_dev} | Strategy = {classification['primary_category']}")
        else:
            print(f"      INVALID: {eval_res.get('error')[:60]}")

    print(f"Trial 3 Condition B completed. Final Best Dev = {best_b_dev}")

    # -----------------------------------------------------------------------
    # Part 2: Complete Trial 3 Condition C (calls 1-15)
    # -----------------------------------------------------------------------
    t3_c_cands = [c for c in existing_candidates if c["trial"] == 3 and c["condition"] == "Condition_C_RandomParent"]
    print(f"\n[Trial 3] Running Condition C (Random-Parent Search, 15 calls)...")
    all_generated_pool = [c for c in t3_c_cands if c["is_valid"]]
    best_c_dev = min([c["dev_total_colors"] for c in all_generated_pool], default=999999)
    rng = random.Random(42 + 3)

    for call_idx in range(len(t3_c_cands) + 1, 16):
        if call_idx <= 5:
            # Init prompts
            prompt = INDEPENDENT_PROMPTS[call_idx - 1]
            cand_id = f"t3_condC_init{call_idx}_{hashlib.sha256(prompt.encode()).hexdigest()[:6]}"
            parents = []
            gen = 0
            label = "Init"
        else:
            gen = (call_idx - 6) // 2 + 1
            is_cross = (call_idx % 2 == 1)
            if not is_cross:
                # Random single parent mutation
                rand_parent = rng.choice(all_generated_pool)
                prompt = (
                    f"You are modifying an existing graph coloring solver.\n"
                    f"Previous Candidate Code:\n```python\n{rand_parent['code']}\n```\n\n"
                    f"Task: Modify and adjust this solver to minimize colors used.\n"
                    + COMMON_REQUIREMENTS
                )
                cand_id = f"t3_condC_gen{gen}_rand1_{call_idx}"
                parents = [rand_parent["candidate_id"]]
                label = f"Gen{gen} RandMut"
            else:
                # Random two-parent combination
                rp1 = rng.choice(all_generated_pool)
                rp2 = rng.choice(all_generated_pool)
                prompt = (
                    f"You are combining two previous graph coloring solvers.\n"
                    f"Candidate 1 Code:\n```python\n{rp1['code']}\n```\n\n"
                    f"Candidate 2 Code:\n```python\n{rp2['code']}\n```\n\n"
                    f"Task: Combine ideas from both solvers to create an effective coloring function.\n"
                    + COMMON_REQUIREMENTS
                )
                cand_id = f"t3_condC_gen{gen}_rand2_{call_idx}"
                parents = [rp1["candidate_id"], rp2["candidate_id"]]
                label = f"Gen{gen} RandCross"

        print(f"    Call {call_idx:2d}/15 ({label}): Querying model...")
        res = client.query(prompt, temperature=0.6, max_tokens=3200)
        if not res["success"] or not res["code"]:
            print(f"      Call {call_idx:2d}/15 failed to extract code: {res.get('error')}")
            rec = {
                "candidate_id": cand_id, "trial": 3, "condition": "Condition_C_RandomParent",
                "call_index": call_idx, "parent_ids": parents, "generation": gen,
                "is_valid": False, "dev_total_colors": 999999, "dev_runtime_ms": 0.0,
                "dev_scores": [], "error": res.get("error", "Code extraction failed"),
                "prompt_tokens": res.get("prompt_tokens", 0), "completion_tokens": res.get("completion_tokens", 0),
                "code": "", "macro_classification": {"primary_category": "failed"}
            }
            log_candidate(rec)
            continue

        eval_res = evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
        classification = classify_macro_strategy(res["code"])
        rec = {
            "candidate_id": cand_id, "trial": 3, "condition": "Condition_C_RandomParent",
            "call_index": call_idx, "parent_ids": parents, "generation": gen,
            "is_valid": eval_res["is_valid"], "dev_total_colors": eval_res["total_colors"],
            "dev_runtime_ms": eval_res["runtime_ms"], "dev_scores": eval_res.get("scores", []),
            "error": eval_res.get("error"), "prompt_tokens": res["prompt_tokens"],
            "completion_tokens": res["completion_tokens"], "code": res["code"],
            "macro_classification": classification,
        }
        log_candidate(rec)

        if eval_res["is_valid"]:
            all_generated_pool.append(rec)
            if eval_res["total_colors"] < best_c_dev:
                print(f"      *** IMPROVEMENT! *** Dev = {eval_res['total_colors']} colors (was {best_c_dev}) | Strategy = {classification['primary_category']}")
                best_c_dev = eval_res["total_colors"]
            else:
                print(f"      Dev = {eval_res['total_colors']} colors | Best = {best_c_dev} | Strategy = {classification['primary_category']}")
        else:
            print(f"      INVALID: {eval_res.get('error')[:60]}")

    print(f"Trial 3 Condition C completed. Final Best Dev = {best_c_dev}")

    # -----------------------------------------------------------------------
    # Part 3: Classical Baselines Evaluation on Hidden Benchmark
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("EVALUATING CLASSICAL BASELINES ON HIDDEN BENCHMARK (160 graphs)...")
    print("=" * 75)
    baselines = {
        "DSATUR": DSATUR_CODE,
        "RLF": RLF_CODE,
        "Welsh-Powell": WELSH_POWELL_CODE,
        "Natural-Greedy": NATURAL_GREEDY_CODE,
    }
    baseline_hidden_scores = {}
    for bname, bcode in baselines.items():
        h_res = evaluator.evaluate_solver_code(bcode, dataset_type="hidden")
        baseline_hidden_scores[bname] = h_res
        print(f"  {bname:15s} -> Hidden: {h_res['total_colors']:4d} colors (Runtime: {h_res['runtime_ms']:.1f}ms)")

    # -----------------------------------------------------------------------
    # Part 4: Frozen Hidden Benchmark Evaluation of All 3 Trials x 3 Conditions
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("EVALUATING TRIAL CHAMPIONS ON HIDDEN BENCHMARK (160 graphs)...")
    print("=" * 75)

    trial_results = []
    for t_idx in [1, 2, 3]:
        print(f"\n--- TRIAL {t_idx} ---")
        t_cands = [c for c in existing_candidates if c["trial"] == t_idx]

        # Best A
        cands_a = sorted([c for c in t_cands if c["condition"] == "Condition_A_Independent" and c["is_valid"]], key=lambda x: x["dev_total_colors"])
        best_a = cands_a[0]
        curve_a = []
        b_cur = 999999
        for c in sorted([c for c in t_cands if c["condition"] == "Condition_A_Independent"], key=lambda x: x["call_index"]):
            if c["is_valid"] and c["dev_total_colors"] < b_cur:
                b_cur = c["dev_total_colors"]
            curve_a.append(b_cur)

        # Best B
        cands_b = sorted([c for c in t_cands if c["condition"] == "Condition_B_Evolution" and c["is_valid"]], key=lambda x: x["dev_total_colors"])
        best_b = cands_b[0]
        curve_b = []
        b_cur = 999999
        for c in sorted([c for c in t_cands if c["condition"] == "Condition_B_Evolution"], key=lambda x: x["call_index"]):
            if c["is_valid"] and c["dev_total_colors"] < b_cur:
                b_cur = c["dev_total_colors"]
            curve_b.append(b_cur)

        # Best C
        cands_c = sorted([c for c in t_cands if c["condition"] == "Condition_C_RandomParent" and c["is_valid"]], key=lambda x: x["dev_total_colors"])
        best_c = cands_c[0]
        curve_c = []
        b_cur = 999999
        for c in sorted([c for c in t_cands if c["condition"] == "Condition_C_RandomParent"], key=lambda x: x["call_index"]):
            if c["is_valid"] and c["dev_total_colors"] < b_cur:
                b_cur = c["dev_total_colors"]
            curve_c.append(b_cur)

        # Evaluate on Hidden
        print(f"  Evaluating Best A ({best_a['candidate_id']}, dev={best_a['dev_total_colors']})...")
        hidden_a = evaluator.evaluate_solver_code(best_a["code"], dataset_type="hidden")
        print(f"  Evaluating Best B ({best_b['candidate_id']}, dev={best_b['dev_total_colors']})...")
        hidden_b = evaluator.evaluate_solver_code(best_b["code"], dataset_type="hidden")
        print(f"  Evaluating Best C ({best_c['candidate_id']}, dev={best_c['dev_total_colors']})...")
        hidden_c = evaluator.evaluate_solver_code(best_c["code"], dataset_type="hidden")

        print(f"  [Trial {t_idx} Results]")
        print(f"    Cond A (Independent):   Dev={best_a['dev_total_colors']} -> Hidden={hidden_a['total_colors']} ({best_a['macro_classification']['primary_category']})")
        print(f"    Cond B (Evolution):     Dev={best_b['dev_total_colors']} -> Hidden={hidden_b['total_colors']} ({best_b['macro_classification']['primary_category']})")
        print(f"    Cond C (Random-Parent): Dev={best_c['dev_total_colors']} -> Hidden={hidden_c['total_colors']} ({best_c['macro_classification']['primary_category']})")

        trial_results.append({
            "trial": t_idx,
            "best_a": {
                "candidate_id": best_a["candidate_id"], "dev_colors": best_a["dev_total_colors"],
                "hidden_colors": hidden_a["total_colors"], "hidden_runtime_ms": hidden_a["runtime_ms"],
                "strategy": best_a["macro_classification"]["primary_category"], "code": best_a["code"],
                "hidden_scores": hidden_a["scores"], "curve": curve_a,
            },
            "best_b": {
                "candidate_id": best_b["candidate_id"], "dev_colors": best_b["dev_total_colors"],
                "hidden_colors": hidden_b["total_colors"], "hidden_runtime_ms": hidden_b["runtime_ms"],
                "strategy": best_b["macro_classification"]["primary_category"], "code": best_b["code"],
                "hidden_scores": hidden_b["scores"], "curve": curve_b,
            },
            "best_c": {
                "candidate_id": best_c["candidate_id"], "dev_colors": best_c["dev_total_colors"],
                "hidden_colors": hidden_c["total_colors"], "hidden_runtime_ms": hidden_c["runtime_ms"],
                "strategy": best_c["macro_classification"]["primary_category"], "code": best_c["code"],
                "hidden_scores": hidden_c["scores"], "curve": curve_c,
            }
        })

    # -----------------------------------------------------------------------
    # Part 5: Aggregation & Paired Statistical Tests
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("CROSS-TRIAL AGGREGATION & STATISTICAL ANALYSIS")
    print("=" * 75)

    h_a = [t["best_a"]["hidden_colors"] for t in trial_results]
    h_b = [t["best_b"]["hidden_colors"] for t in trial_results]
    h_c = [t["best_c"]["hidden_colors"] for t in trial_results]

    d_a = [t["best_a"]["dev_colors"] for t in trial_results]
    d_b = [t["best_b"]["dev_colors"] for t in trial_results]
    d_c = [t["best_c"]["dev_colors"] for t in trial_results]

    print(f"\nCondition A (Independent)   Across 3 Trials: Hidden = {h_a} (Mean: {np.mean(h_a):.1f} ± {np.std(h_a, ddof=1):.1f}) | Dev = {d_a} (Mean: {np.mean(d_a):.1f})")
    print(f"Condition B (Evolution)     Across 3 Trials: Hidden = {h_b} (Mean: {np.mean(h_b):.1f} ± {np.std(h_b, ddof=1):.1f}) | Dev = {d_b} (Mean: {np.mean(d_b):.1f})")
    print(f"Condition C (Random-Parent) Across 3 Trials: Hidden = {h_c} (Mean: {np.mean(h_c):.1f} ± {np.std(h_c, ddof=1):.1f}) | Dev = {d_c} (Mean: {np.mean(d_c):.1f})")

    avg_curve_a = np.mean([t["best_a"]["curve"] for t in trial_results], axis=0).tolist()
    avg_curve_b = np.mean([t["best_b"]["curve"] for t in trial_results], axis=0).tolist()
    avg_curve_c = np.mean([t["best_c"]["curve"] for t in trial_results], axis=0).tolist()

    print("\nSearch-Efficiency Curves (Mean Best Dev Score after N calls):")
    print("Call:  " + "  ".join(f"{c:4d}" for c in range(1, 16)))
    print("Cond A:" + "  ".join(f"{score:4.1f}" for score in avg_curve_a))
    print("Cond B:" + "  ".join(f"{score:4.1f}" for score in avg_curve_b))
    print("Cond C:" + "  ".join(f"{score:4.1f}" for score in avg_curve_c))

    # Overall best candidates
    overall_best_a = min(trial_results, key=lambda t: t["best_a"]["hidden_colors"])["best_a"]
    overall_best_b = min(trial_results, key=lambda t: t["best_b"]["hidden_colors"])["best_b"]
    overall_best_c = min(trial_results, key=lambda t: t["best_c"]["hidden_colors"])["best_c"]

    def paired_stats(scores1: List[int], scores2: List[int], label: str) -> Dict[str, Any]:
        s1 = np.array(scores1)
        s2 = np.array(scores2)
        diff = s1 - s2
        n = len(diff)
        wins = int(np.sum(diff < 0))
        losses = int(np.sum(diff > 0))
        ties = int(np.sum(diff == 0))
        mean_diff = float(np.mean(diff))
        std_diff = float(np.std(diff, ddof=1)) if n > 1 else 0.0
        sem = std_diff / np.sqrt(n) if n > 0 else 0.0
        ci_half = stats.t.ppf(0.975, df=n - 1) * sem if n > 1 and std_diff > 0 else 0.0
        non_zero = diff[diff != 0]
        if len(non_zero) > 0:
            try:
                w_res = stats.wilcoxon(non_zero, alternative="two-sided")
                w_p = float(w_res.pvalue)
            except Exception:
                w_p = 1.0
        else:
            w_p = 1.0
        cohens_d = mean_diff / std_diff if std_diff > 0 else 0.0
        return {
            "comparison": label, "n": n, "cand1_total": int(np.sum(s1)), "cand2_total": int(np.sum(s2)),
            "net_diff": int(np.sum(diff)), "mean_diff": round(mean_diff, 4),
            "ci_95": [round(mean_diff - ci_half, 4), round(mean_diff + ci_half, 4)],
            "wins": wins, "losses": losses, "ties": ties, "wilcoxon_p": float(w_p), "cohens_d": round(cohens_d, 4),
        }

    stat_b_vs_a = paired_stats(overall_best_b["hidden_scores"], overall_best_a["hidden_scores"], "Evolution vs Independent")
    stat_b_vs_c = paired_stats(overall_best_b["hidden_scores"], overall_best_c["hidden_scores"], "Evolution vs Random-Parent")
    stat_a_vs_c = paired_stats(overall_best_a["hidden_scores"], overall_best_c["hidden_scores"], "Independent vs Random-Parent")
    stat_b_vs_dsatur = paired_stats(overall_best_b["hidden_scores"], baseline_hidden_scores["DSATUR"]["scores"], "Evolution vs DSATUR")
    stat_b_vs_rlf = paired_stats(overall_best_b["hidden_scores"], baseline_hidden_scores["RLF"]["scores"], "Evolution vs RLF")

    print("\nPaired Statistical Analysis on 160 Hidden Graphs:")
    for s in [stat_b_vs_a, stat_b_vs_c, stat_a_vs_c, stat_b_vs_dsatur, stat_b_vs_rlf]:
        print(f"  {s['comparison']:30s} | W={s['wins']:3d}, L={s['losses']:3d}, T={s['ties']:3d} | Net={s['net_diff']:+4d} | "
              f"Mean={s['mean_diff']:+.4f} (95% CI: {s['ci_95']}) | Wilcoxon p={s['wilcoxon_p']:.4f} | d={s['cohens_d']:+.3f}")

    # Family breakdown
    hidden_graphs = evaluator.suite.hidden_dataset
    families = sorted(list(hidden_graphs.keys()))
    family_breakdown = {}
    for fam in families:
        fam_g = hidden_graphs[fam]
        # slice scores for this family
        # The hidden dataset is built family by family
        fam_indices = []
        offset = 0
        for f_name, f_list in hidden_graphs.items():
            if f_name == fam:
                fam_indices = list(range(offset, offset + len(f_list)))
                break
            offset += len(f_list)

        family_breakdown[fam] = {
            "num_graphs": len(fam_indices),
            "cond_a": int(sum(overall_best_a["hidden_scores"][i] for i in fam_indices)),
            "cond_b": int(sum(overall_best_b["hidden_scores"][i] for i in fam_indices)),
            "cond_c": int(sum(overall_best_c["hidden_scores"][i] for i in fam_indices)),
            "dsatur": int(sum(baseline_hidden_scores["DSATUR"]["scores"][i] for i in fam_indices)),
            "rlf": int(sum(baseline_hidden_scores["RLF"]["scores"][i] for i in fam_indices)),
        }

    summary = {
        "experiment": "Experiment #8 — Evolution vs Equal-Budget Search",
        "model": "antigravity/claude-sonnet-4-6",
        "num_trials": 3,
        "calls_per_condition_per_trial": 15,
        "total_calls_all_trials": 135,
        "baseline_hidden_scores": {
            k: {"total_colors": v["total_colors"], "runtime_ms": v["runtime_ms"]}
            for k, v in baseline_hidden_scores.items()
        },
        "trial_results": trial_results,
        "search_efficiency_curves": {
            "avg_curve_independent_condA": avg_curve_a,
            "avg_curve_evolution_condB": avg_curve_b,
            "avg_curve_random_parent_condC": avg_curve_c,
        },
        "cross_trial_summary": {
            "hidden_mean_A_independent": float(np.mean(h_a)),
            "hidden_mean_B_evolution": float(np.mean(h_b)),
            "hidden_mean_C_random_parent": float(np.mean(h_c)),
            "hidden_std_A": float(np.std(h_a, ddof=1)),
            "hidden_std_B": float(np.std(h_b, ddof=1)),
            "hidden_std_C": float(np.std(h_c, ddof=1)),
            "dev_mean_A": float(np.mean(d_a)),
            "dev_mean_B": float(np.mean(d_b)),
            "dev_mean_C": float(np.mean(d_c)),
        },
        "overall_champions": {
            "best_independent": {k: v for k, v in overall_best_a.items() if k != "hidden_scores"},
            "best_evolution": {k: v for k, v in overall_best_b.items() if k != "hidden_scores"},
            "best_random_parent": {k: v for k, v in overall_best_c.items() if k != "hidden_scores"},
        },
        "paired_statistics": {
            "evolution_vs_independent": stat_b_vs_a,
            "evolution_vs_random_parent": stat_b_vs_c,
            "independent_vs_random_parent": stat_a_vs_c,
            "evolution_vs_dsatur": stat_b_vs_dsatur,
            "evolution_vs_rlf": stat_b_vs_rlf,
        },
        "family_breakdown": family_breakdown,
    }

    with open(summary_json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[OUTPUT] Saved Experiment #8 complete summary to {summary_json_path}")
    print("\nEXPERIMENT #8 EXECUTION AND EVALUATION FINISHED SUCCESSFULLY.")


if __name__ == "__main__":
    resume_and_complete()
