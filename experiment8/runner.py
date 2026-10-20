"""
Experiment #8: Evolution vs. Equal-Budget Independent Search
=============================================================
Orchestrates:
- 3 Search Conditions:
  - Condition A: Single-Shot Independent Search
  - Condition B: Evolutionary Search (Fitness-Based Selection & Crossover)
  - Condition C: Random-Parent Search (Control for code exposure without selection)
- Strict Budget Matching: Exactly 15 LLM calls per condition per trial.
- 3 Independent Trials (Trial 1, Trial 2, Trial 3).
- Call-by-call search-efficiency curves (calls 1 to 15).
- Frozen Hidden Benchmark evaluation (160 graphs across 8 families).
- Paired statistical testing (Wilcoxon, Cohen's d, bootstrap CI).
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

# Ensure local imports work
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


COMMON_REQUIREMENTS = """Requirements:
1. Focus on ONE coherent, effective macro-algorithmic strategy.
2. Keep the implementation clean, self-contained, and strictly under 120 lines of code.
3. It must execute rapidly (under 30 ms per graph). Do not write slow O(N^4) loops.
4. Ensure the function always terminates and returns `colors: list[int]` where len(colors) == len(adj), colors[u] >= 0, and adjacent vertices have different colors.
5. Return ONLY executable Python code inside a ```python ``` block.
"""

INDEPENDENT_PROMPTS = [
    # 1. Open unconstrained design
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "The objective is to minimize total colors used across diverse graph types.\n"
    "You have complete macro-algorithmic freedom. Benchmark targets on dev: DSATUR = 223, RLF = 220.\n" + COMMON_REQUIREMENTS,

    # 2. Independent set extraction
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Focus on an iterative independent set extraction paradigm (extracting maximal independent sets to form color classes),\n"
    "optimizing which vertices are grouped together into the same color class to leave the remaining subgraph as easy to color as possible.\n" + COMMON_REQUIREMENTS,

    # 3. Iterated Greedy / Multi-pass recoloring
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Use a multi-pass iterated re-coloring strategy (similar to Culberson's Iterated Greedy),\n"
    "where an initial coloring is constructed, vertices are reordered based on color classes or conflict statistics,\n"
    "and re-colored over multiple fast passes to reduce the total number of colors.\n" + COMMON_REQUIREMENTS,

    # 4. Saturation degree with local search / Kempe chains
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Combine a fast constructive phase (such as saturation-degree ordering) with a local improvement phase,\n"
    "such as Kempe chain color swaps or recoloring vertices belonging to the highest-numbered color classes to eliminate entire colors.\n" + COMMON_REQUIREMENTS,

    # 5. Min-conflicts / repair local search
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Implement a two-stage strategy: first, construct an initial coloring, then apply a fast conflict-repair or recoloring routine "
    "focused on eliminating the rarest colors by redistributing their vertices to lower colors.\n" + COMMON_REQUIREMENTS,

    # 6. Adaptive multi-heuristic selection
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Inspect the graph structure (e.g. edge density, maximum degree) and adaptively select the best coloring strategy,\n"
    "or run two complementary fast heuristics and return whichever uses fewer colors.\n" + COMMON_REQUIREMENTS,

    # 7. Randomized restart portfolio
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Implement a fast randomized restart heuristic that introduces small stochastic tie-breaking into vertex selection,\n"
    "runs multiple independent rapid coloring trials within a 30ms budget, and returns the trial using the fewest colors.\n" + COMMON_REQUIREMENTS,

    # 8. Hybrid RLF + DSATUR
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Design a hybrid algorithm combining the strengths of color-class extraction (RLF) with dynamic saturation-degree coloring (DSATUR).\n" + COMMON_REQUIREMENTS,

    # 9. Degree ordering with Kempe chains
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Start with Welsh-Powell (largest first) degree ordering First-Fit, then perform systematic Kempe chain interchanges to collapse the highest color class.\n" + COMMON_REQUIREMENTS,

    # 10. Multi-start greedy with vertex shuffles
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Generate multiple distinct vertex orderings (e.g. largest-first, smallest-last, and random perturbations), color each rapidly with First-Fit, and select the best.\n" + COMMON_REQUIREMENTS,

    # 11. Independent set with 1-swap neighborhood search
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Extract independent sets iteratively to color the graph, followed by a fast 1-swap post-processing phase that moves vertices out of the highest color class.\n" + COMMON_REQUIREMENTS,

    # 12. Saturation-degree guided recoloring
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Run DSATUR, then identify all vertices in the last color class and attempt to clear them by recoloring their conflicting neighbors with available lower colors.\n" + COMMON_REQUIREMENTS,

    # 13. Squeeze heuristic on maximal color class
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Construct an initial high-quality coloring, then iteratively 'squeeze' the coloring: attempt to eliminate color K-1 by finding alternate colors for its vertices or their 1-hop neighbors.\n" + COMMON_REQUIREMENTS,

    # 14. Bounded Kempe chain reduction on multi-start DSATUR
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Run deterministic DSATUR plus 3 randomized DSATUR passes. For the best result, apply bounded Kempe chain swaps strictly targeting vertices with color K-1 to eliminate the color.\n" + COMMON_REQUIREMENTS,

    # 15. Portfolio of RLF and randomized DSATUR with Kempe reduction
    "Design a complete graph coloring solver in Python: `def color_graph(adj: list[list[int]]) -> list[int]:`.\n"
    "Run RLF and randomized DSATUR, take the best coloring, and apply Kempe chain reduction to reduce the maximum color used.\n" + COMMON_REQUIREMENTS,
]


class Experiment8Runner:
    def __init__(self, output_dir: str = "experiment8"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.evaluator = SolverEvaluator(per_instance_budget_ms=50.0, per_instance_timeout_ms=300.0)
        self.client = SolverLLMClient()
        self.candidates_log_path = os.path.join(self.output_dir, "candidates.jsonl")
        self.summary_json_path = os.path.join(self.output_dir, "summary.json")

    def log_candidate(self, cand_record: Dict[str, Any]):
        """Append candidate record to candidates.jsonl."""
        with open(self.candidates_log_path, "a") as f:
            f.write(json.dumps(cand_record) + "\n")

    # -----------------------------------------------------------------------
    # Condition A: Single-Shot Independent Search (15 calls)
    # -----------------------------------------------------------------------
    def run_trial_condition_a(self, trial_idx: int) -> Tuple[Dict[str, Any], List[int]]:
        print(f"\n  [Trial {trial_idx}] Running Condition A (Single-Shot Independent Search, 15 calls)...")
        candidates = []
        best_so_far_curve = []
        best_so_far = None

        for call_idx in range(1, 16):
            prompt = INDEPENDENT_PROMPTS[call_idx - 1]
            cand_id = f"t{trial_idx}_condA_call{call_idx}_{hashlib.sha256(prompt.encode()).hexdigest()[:6]}"

            res = self.client.query(prompt, temperature=0.6, max_tokens=3200)
            if not res["success"] or not res["code"]:
                print(f"    Call {call_idx:2d}/15: Failed to extract code.")
                rec = {
                    "candidate_id": cand_id, "trial": trial_idx, "condition": "Condition_A_Independent",
                    "call_index": call_idx, "parent_ids": [], "generation": 0, "is_valid": False,
                    "dev_total_colors": 999999, "error": res.get("error", "Code extraction failed"),
                    "prompt_tokens": res.get("prompt_tokens", 0), "completion_tokens": res.get("completion_tokens", 0),
                    "code": "", "macro_classification": {"primary_category": "failed"}
                }
                self.log_candidate(rec)
                current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
                best_so_far_curve.append(current_best_score)
                continue

            eval_res = self.evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
            classification = classify_macro_strategy(res["code"])

            rec = {
                "candidate_id": cand_id, "trial": trial_idx, "condition": "Condition_A_Independent",
                "call_index": call_idx, "parent_ids": [], "generation": 0, "is_valid": eval_res["is_valid"],
                "dev_total_colors": eval_res["total_colors"], "dev_runtime_ms": eval_res["runtime_ms"],
                "dev_scores": eval_res.get("scores", []), "error": eval_res.get("error"),
                "prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"],
                "code": res["code"], "macro_classification": classification,
            }
            self.log_candidate(rec)
            candidates.append(rec)

            if eval_res["is_valid"]:
                if best_so_far is None or eval_res["total_colors"] < best_so_far["dev_total_colors"]:
                    best_so_far = rec
                print(f"    Call {call_idx:2d}/15: Dev = {eval_res['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d} | Strategy = {classification['primary_category']}")
            else:
                print(f"    Call {call_idx:2d}/15: INVALID ({eval_res.get('error')[:40]})")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)

        return best_so_far, best_so_far_curve

    # -----------------------------------------------------------------------
    # Condition B: Evolutionary Search (15 calls: 5 initial + 5 gens x 2)
    # -----------------------------------------------------------------------
    def run_trial_condition_b(self, trial_idx: int) -> Tuple[Dict[str, Any], List[int]]:
        print(f"\n  [Trial {trial_idx}] Running Condition B (Evolutionary Search, 15 calls)...")
        candidates = []
        best_so_far_curve = []
        best_so_far = None
        population = []

        # Calls 1-5: Initial Population
        for call_idx in range(1, 6):
            prompt = INDEPENDENT_PROMPTS[call_idx - 1]
            cand_id = f"t{trial_idx}_condB_init{call_idx}_{hashlib.sha256(prompt.encode()).hexdigest()[:6]}"

            res = self.client.query(prompt, temperature=0.6, max_tokens=3200)
            if not res["success"] or not res["code"]:
                rec = {
                    "candidate_id": cand_id, "trial": trial_idx, "condition": "Condition_B_Evolution",
                    "call_index": call_idx, "parent_ids": [], "generation": 0, "is_valid": False,
                    "dev_total_colors": 999999, "error": res.get("error", "Failed extraction"),
                    "prompt_tokens": res.get("prompt_tokens", 0), "completion_tokens": res.get("completion_tokens", 0),
                    "code": "", "macro_classification": {"primary_category": "failed"}
                }
                self.log_candidate(rec)
                current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
                best_so_far_curve.append(current_best_score)
                continue

            eval_res = self.evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
            classification = classify_macro_strategy(res["code"])

            rec = {
                "candidate_id": cand_id, "trial": trial_idx, "condition": "Condition_B_Evolution",
                "call_index": call_idx, "parent_ids": [], "generation": 0, "is_valid": eval_res["is_valid"],
                "dev_total_colors": eval_res["total_colors"], "dev_runtime_ms": eval_res["runtime_ms"],
                "dev_scores": eval_res.get("scores", []), "error": eval_res.get("error"),
                "prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"],
                "code": res["code"], "macro_classification": classification,
            }
            self.log_candidate(rec)
            candidates.append(rec)

            if eval_res["is_valid"]:
                population.append(rec)
                if best_so_far is None or eval_res["total_colors"] < best_so_far["dev_total_colors"]:
                    best_so_far = rec
                print(f"    Call {call_idx:2d}/15 (Init): Dev = {eval_res['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d} | Strategy = {classification['primary_category']}")
            else:
                print(f"    Call {call_idx:2d}/15 (Init): INVALID ({eval_res.get('error')[:40]})")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)

        # Calls 6-15: 5 Generations x 2 Offspring
        call_counter = 6
        for gen in range(1, 6):
            population = sorted([c for c in population if c["is_valid"]], key=lambda x: x["dev_total_colors"])
            if not population:
                print("    [ERROR] Population empty in evolution.")
                break

            # Offspring 1: Exploitation / Refinement of Best
            parent_a = population[0]
            exploit_prompt = (
                f"You are iteratively refining a complete graph coloring solver.\n"
                f"Current Champion ({parent_a['candidate_id']}) achieved {parent_a['dev_total_colors']} total colors on dev benchmark.\n"
                f"Runtime: {parent_a['dev_runtime_ms']:.1f}ms. Strategy: {parent_a['macro_classification']['primary_category']}.\n\n"
                f"Code:\n```python\n{parent_a['code']}\n```\n\n"
                f"Task: Modify and optimize this solver to use FEWER colors while keeping runtime strictly under 30ms per graph.\n"
                + COMMON_REQUIREMENTS
            )
            cand_id_1 = f"t{trial_idx}_condB_gen{gen}_exploit_{call_counter}"
            res1 = self.client.query(exploit_prompt, temperature=0.6, max_tokens=3200)

            if res1["success"] and res1["code"]:
                eval_res1 = self.evaluator.evaluate_solver_code(res1["code"], dataset_type="dev")
                class1 = classify_macro_strategy(res1["code"])
                rec1 = {
                    "candidate_id": cand_id_1, "trial": trial_idx, "condition": "Condition_B_Evolution",
                    "call_index": call_counter, "parent_ids": [parent_a["candidate_id"]], "generation": gen,
                    "is_valid": eval_res1["is_valid"], "dev_total_colors": eval_res1["total_colors"],
                    "dev_runtime_ms": eval_res1["runtime_ms"], "dev_scores": eval_res1.get("scores", []),
                    "error": eval_res1.get("error"), "prompt_tokens": res1["prompt_tokens"],
                    "completion_tokens": res1["completion_tokens"], "code": res1["code"],
                    "macro_classification": class1,
                }
                self.log_candidate(rec1)
                candidates.append(rec1)
                if eval_res1["is_valid"]:
                    population.append(rec1)
                    if eval_res1["total_colors"] < best_so_far["dev_total_colors"]:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} Exploit): *** IMPROVEMENT! *** Dev = {eval_res1['total_colors']:3d} colors")
                        best_so_far = rec1
                    else:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} Exploit): Dev = {eval_res1['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d}")
                else:
                    print(f"    Call {call_counter:2d}/15 (Gen{gen} Exploit): INVALID")
            else:
                print(f"    Call {call_counter:2d}/15 (Gen{gen} Exploit): Extraction failed")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)
            call_counter += 1

            # Offspring 2: Crossover / Hybridization of Top 2 Distinct Parents
            population = sorted([c for c in population if c["is_valid"]], key=lambda x: x["dev_total_colors"])
            parent_1 = population[0]
            parent_2 = population[1] if len(population) > 1 else population[0]
            for p in population[1:]:
                if p["macro_classification"]["primary_category"] != parent_1["macro_classification"]["primary_category"]:
                    parent_2 = p
                    break

            cross_prompt = (
                f"You are hybridizing two distinct graph coloring strategies.\n"
                f"Parent 1 ({parent_1['candidate_id']}): {parent_1['dev_total_colors']} colors ({parent_1['macro_classification']['primary_category']}).\n"
                f"Parent 2 ({parent_2['candidate_id']}): {parent_2['dev_total_colors']} colors ({parent_2['macro_classification']['primary_category']}).\n\n"
                f"Parent 1 Code:\n```python\n{parent_1['code']}\n```\n\n"
                f"Parent 2 Code:\n```python\n{parent_2['code']}\n```\n\n"
                f"Task: Synthesize a hybrid solver combining the complementary strengths of both approaches to use fewer colors than {min(parent_1['dev_total_colors'], parent_2['dev_total_colors'])}.\n"
                + COMMON_REQUIREMENTS
            )
            cand_id_2 = f"t{trial_idx}_condB_gen{gen}_cross_{call_counter}"
            res2 = self.client.query(cross_prompt, temperature=0.6, max_tokens=3200)

            if res2["success"] and res2["code"]:
                eval_res2 = self.evaluator.evaluate_solver_code(res2["code"], dataset_type="dev")
                class2 = classify_macro_strategy(res2["code"])
                rec2 = {
                    "candidate_id": cand_id_2, "trial": trial_idx, "condition": "Condition_B_Evolution",
                    "call_index": call_counter, "parent_ids": [parent_1["candidate_id"], parent_2["candidate_id"]],
                    "generation": gen, "is_valid": eval_res2["is_valid"], "dev_total_colors": eval_res2["total_colors"],
                    "dev_runtime_ms": eval_res2["runtime_ms"], "dev_scores": eval_res2.get("scores", []),
                    "error": eval_res2.get("error"), "prompt_tokens": res2["prompt_tokens"],
                    "completion_tokens": res2["completion_tokens"], "code": res2["code"],
                    "macro_classification": class2,
                }
                self.log_candidate(rec2)
                candidates.append(rec2)
                if eval_res2["is_valid"]:
                    population.append(rec2)
                    if eval_res2["total_colors"] < best_so_far["dev_total_colors"]:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} Cross): *** IMPROVEMENT! *** Dev = {eval_res2['total_colors']:3d} colors")
                        best_so_far = rec2
                    else:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} Cross): Dev = {eval_res2['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d}")
                else:
                    print(f"    Call {call_counter:2d}/15 (Gen{gen} Cross): INVALID")
            else:
                print(f"    Call {call_counter:2d}/15 (Gen{gen} Cross): Extraction failed")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)
            call_counter += 1

        return best_so_far, best_so_far_curve

    # -----------------------------------------------------------------------
    # Condition C: Random-Parent Search (15 calls: 5 initial + 5 gens x 2)
    # -----------------------------------------------------------------------
    def run_trial_condition_c(self, trial_idx: int) -> Tuple[Dict[str, Any], List[int]]:
        print(f"\n  [Trial {trial_idx}] Running Condition C (Random-Parent Search, 15 calls)...")
        candidates = []
        best_so_far_curve = []
        best_so_far = None
        all_generated_pool = []

        # Calls 1-5: Initial Population (same initial prompts as Cond B)
        for call_idx in range(1, 6):
            prompt = INDEPENDENT_PROMPTS[call_idx - 1]
            cand_id = f"t{trial_idx}_condC_init{call_idx}_{hashlib.sha256(prompt.encode()).hexdigest()[:6]}"

            res = self.client.query(prompt, temperature=0.6, max_tokens=3200)
            if not res["success"] or not res["code"]:
                rec = {
                    "candidate_id": cand_id, "trial": trial_idx, "condition": "Condition_C_RandomParent",
                    "call_index": call_idx, "parent_ids": [], "generation": 0, "is_valid": False,
                    "dev_total_colors": 999999, "error": res.get("error", "Failed extraction"),
                    "prompt_tokens": res.get("prompt_tokens", 0), "completion_tokens": res.get("completion_tokens", 0),
                    "code": "", "macro_classification": {"primary_category": "failed"}
                }
                self.log_candidate(rec)
                current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
                best_so_far_curve.append(current_best_score)
                continue

            eval_res = self.evaluator.evaluate_solver_code(res["code"], dataset_type="dev")
            classification = classify_macro_strategy(res["code"])

            rec = {
                "candidate_id": cand_id, "trial": trial_idx, "condition": "Condition_C_RandomParent",
                "call_index": call_idx, "parent_ids": [], "generation": 0, "is_valid": eval_res["is_valid"],
                "dev_total_colors": eval_res["total_colors"], "dev_runtime_ms": eval_res["runtime_ms"],
                "dev_scores": eval_res.get("scores", []), "error": eval_res.get("error"),
                "prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"],
                "code": res["code"], "macro_classification": classification,
            }
            self.log_candidate(rec)
            candidates.append(rec)
            if eval_res["is_valid"]:
                all_generated_pool.append(rec)
                if best_so_far is None or eval_res["total_colors"] < best_so_far["dev_total_colors"]:
                    best_so_far = rec
                print(f"    Call {call_idx:2d}/15 (Init): Dev = {eval_res['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d} | Strategy = {classification['primary_category']}")
            else:
                print(f"    Call {call_idx:2d}/15 (Init): INVALID")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)

        # Calls 6-15: 5 Generations x 2 Offspring using UNIFORM RANDOM PARENTS
        call_counter = 6
        rng = random.Random(42 + trial_idx)

        for gen in range(1, 6):
            if not all_generated_pool:
                break

            # Offspring 1: Random Single-Parent Mutation
            rand_parent = rng.choice(all_generated_pool)
            rand_prompt = (
                f"You are modifying an existing graph coloring solver.\n"
                f"Previous Candidate Code:\n```python\n{rand_parent['code']}\n```\n\n"
                f"Task: Modify and adjust this solver to minimize colors used.\n"
                + COMMON_REQUIREMENTS
            )
            cand_id_1 = f"t{trial_idx}_condC_gen{gen}_rand1_{call_counter}"
            res1 = self.client.query(rand_prompt, temperature=0.6, max_tokens=3200)

            if res1["success"] and res1["code"]:
                eval_res1 = self.evaluator.evaluate_solver_code(res1["code"], dataset_type="dev")
                class1 = classify_macro_strategy(res1["code"])
                rec1 = {
                    "candidate_id": cand_id_1, "trial": trial_idx, "condition": "Condition_C_RandomParent",
                    "call_index": call_counter, "parent_ids": [rand_parent["candidate_id"]], "generation": gen,
                    "is_valid": eval_res1["is_valid"], "dev_total_colors": eval_res1["total_colors"],
                    "dev_runtime_ms": eval_res1["runtime_ms"], "dev_scores": eval_res1.get("scores", []),
                    "error": eval_res1.get("error"), "prompt_tokens": res1["prompt_tokens"],
                    "completion_tokens": res1["completion_tokens"], "code": res1["code"],
                    "macro_classification": class1,
                }
                self.log_candidate(rec1)
                candidates.append(rec1)
                if eval_res1["is_valid"]:
                    all_generated_pool.append(rec1)
                    if best_so_far is None or eval_res1["total_colors"] < best_so_far["dev_total_colors"]:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} RandMut): *** IMPROVEMENT! *** Dev = {eval_res1['total_colors']:3d} colors")
                        best_so_far = rec1
                    else:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} RandMut): Dev = {eval_res1['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d}")
                else:
                    print(f"    Call {call_counter:2d}/15 (Gen{gen} RandMut): INVALID")
            else:
                print(f"    Call {call_counter:2d}/15 (Gen{gen} RandMut): Extraction failed")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)
            call_counter += 1

            # Offspring 2: Random Two-Parent Combination
            rp1 = rng.choice(all_generated_pool)
            rp2 = rng.choice(all_generated_pool)
            rand_cross_prompt = (
                f"You are combining two previous graph coloring solvers.\n"
                f"Candidate 1 Code:\n```python\n{rp1['code']}\n```\n\n"
                f"Candidate 2 Code:\n```python\n{rp2['code']}\n```\n\n"
                f"Task: Combine ideas from both solvers to create an effective coloring function.\n"
                + COMMON_REQUIREMENTS
            )
            cand_id_2 = f"t{trial_idx}_condC_gen{gen}_rand2_{call_counter}"
            res2 = self.client.query(rand_cross_prompt, temperature=0.6, max_tokens=3200)

            if res2["success"] and res2["code"]:
                eval_res2 = self.evaluator.evaluate_solver_code(res2["code"], dataset_type="dev")
                class2 = classify_macro_strategy(res2["code"])
                rec2 = {
                    "candidate_id": cand_id_2, "trial": trial_idx, "condition": "Condition_C_RandomParent",
                    "call_index": call_counter, "parent_ids": [rp1["candidate_id"], rp2["candidate_id"]],
                    "generation": gen, "is_valid": eval_res2["is_valid"], "dev_total_colors": eval_res2["total_colors"],
                    "dev_runtime_ms": eval_res2["runtime_ms"], "dev_scores": eval_res2.get("scores", []),
                    "error": eval_res2.get("error"), "prompt_tokens": res2["prompt_tokens"],
                    "completion_tokens": res2["completion_tokens"], "code": res2["code"],
                    "macro_classification": class2,
                }
                self.log_candidate(rec2)
                candidates.append(rec2)
                if eval_res2["is_valid"]:
                    all_generated_pool.append(rec2)
                    if best_so_far is None or eval_res2["total_colors"] < best_so_far["dev_total_colors"]:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} RandCross): *** IMPROVEMENT! *** Dev = {eval_res2['total_colors']:3d} colors")
                        best_so_far = rec2
                    else:
                        print(f"    Call {call_counter:2d}/15 (Gen{gen} RandCross): Dev = {eval_res2['total_colors']:3d} colors | Best = {best_so_far['dev_total_colors']:3d}")
                else:
                    print(f"    Call {call_counter:2d}/15 (Gen{gen} RandCross): INVALID")
            else:
                print(f"    Call {call_counter:2d}/15 (Gen{gen} RandCross): Extraction failed")

            current_best_score = best_so_far["dev_total_colors"] if best_so_far else 999999
            best_so_far_curve.append(current_best_score)
            call_counter += 1

        return best_so_far, best_so_far_curve

    # -----------------------------------------------------------------------
    # Master Experiment #8 Runner
    # -----------------------------------------------------------------------
    def run_experiment_8(self):
        t0 = time.time()
        print("=" * 80)
        print("EXPERIMENT #8: EVOLUTION VS EQUAL-BUDGET INDEPENDENT SEARCH")
        print("Conditions: Condition A (Independent), Condition B (Evolution), Condition C (Random-Parent)")
        print("Strict Budget: Exactly 15 LLM calls per condition x 3 independent trials = 135 total calls")
        print("=" * 80)

        # Clear candidates log if restarting
        if os.path.exists(self.candidates_log_path):
            os.remove(self.candidates_log_path)

        # Baseline evaluation on Hidden
        print("\n[PHASE 0] Evaluating Classical Baselines on Hidden Benchmark (160 graphs)...")
        baselines = {
            "DSATUR": DSATUR_CODE,
            "RLF": RLF_CODE,
        }
        baseline_hidden_scores = {}
        for bname, bcode in baselines.items():
            h_res = self.evaluator.evaluate_solver_code(bcode, dataset_type="hidden")
            baseline_hidden_scores[bname] = h_res
            print(f"  {bname:10s} Hidden Total Colors: {h_res['total_colors']} (Runtime: {h_res['runtime_ms']:.1f}ms)")

        # Run 3 Independent Trials
        num_trials = 3
        trial_results = []

        for t_idx in range(1, num_trials + 1):
            print("\n" + "=" * 75)
            print(f"STARTING TRIAL {t_idx} / {num_trials}")
            print("=" * 75)

            # Condition A
            best_a, curve_a = self.run_trial_condition_a(t_idx)

            # Condition B
            best_b, curve_b = self.run_trial_condition_b(t_idx)

            # Condition C
            best_c, curve_c = self.run_trial_condition_c(t_idx)

            # Evaluate each condition's best development candidate on the 160 Hidden Graphs
            print(f"\n[Trial {t_idx} Hidden Evaluation]")
            hidden_a = self.evaluator.evaluate_solver_code(best_a["code"], dataset_type="hidden")
            hidden_b = self.evaluator.evaluate_solver_code(best_b["code"], dataset_type="hidden")
            hidden_c = self.evaluator.evaluate_solver_code(best_c["code"], dataset_type="hidden")

            print(f"  Condition A (Independent)   Best Dev: {best_a['dev_total_colors']} -> Hidden: {hidden_a['total_colors']} colors ({best_a['macro_classification']['primary_category']})")
            print(f"  Condition B (Evolution)     Best Dev: {best_b['dev_total_colors']} -> Hidden: {hidden_b['total_colors']} colors ({best_b['macro_classification']['primary_category']})")
            print(f"  Condition C (Random-Parent) Best Dev: {best_c['dev_total_colors']} -> Hidden: {hidden_c['total_colors']} colors ({best_c['macro_classification']['primary_category']})")

            trial_rec = {
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
            }
            trial_results.append(trial_rec)

        # -------------------------------------------------------------------
        # Cross-Trial Aggregation & Paired Statistical Analysis
        # -------------------------------------------------------------------
        print("\n" + "=" * 75)
        print("EXPERIMENT #8: CROSS-TRIAL AGGREGATION & STATISTICAL ANALYSIS")
        print("=" * 75)

        h_a = [t["best_a"]["hidden_colors"] for t in trial_results]
        h_b = [t["best_b"]["hidden_colors"] for t in trial_results]
        h_c = [t["best_c"]["hidden_colors"] for t in trial_results]

        d_a = [t["best_a"]["dev_colors"] for t in trial_results]
        d_b = [t["best_b"]["dev_colors"] for t in trial_results]
        d_c = [t["best_c"]["dev_colors"] for t in trial_results]

        print(f"\nCondition A (Independent)   Across 3 Trials: Hidden = {h_a} (Mean: {np.mean(h_a):.1f}) | Dev = {d_a} (Mean: {np.mean(d_a):.1f})")
        print(f"Condition B (Evolution)     Across 3 Trials: Hidden = {h_b} (Mean: {np.mean(h_b):.1f}) | Dev = {d_b} (Mean: {np.mean(d_b):.1f})")
        print(f"Condition C (Random-Parent) Across 3 Trials: Hidden = {h_c} (Mean: {np.mean(h_c):.1f}) | Dev = {d_c} (Mean: {np.mean(d_c):.1f})")

        # Average Search-Efficiency Curves across trials (call 1 to 15)
        avg_curve_a = np.mean([t["best_a"]["curve"] for t in trial_results], axis=0).tolist()
        avg_curve_b = np.mean([t["best_b"]["curve"] for t in trial_results], axis=0).tolist()
        avg_curve_c = np.mean([t["best_c"]["curve"] for t in trial_results], axis=0).tolist()

        print("\nSearch-Efficiency Curves (Mean Best Dev Score after N calls):")
        print("Call:  " + "  ".join(f"{c:4d}" for c in range(1, 16)))
        print("Cond A:" + "  ".join(f"{score:4.1f}" for score in avg_curve_a))
        print("Cond B:" + "  ".join(f"{score:4.1f}" for score in avg_curve_b))
        print("Cond C:" + "  ".join(f"{score:4.1f}" for score in avg_curve_c))

        # Overall Best Candidate across all trials for each condition
        overall_best_a = min(trial_results, key=lambda t: t["best_a"]["hidden_colors"])["best_a"]
        overall_best_b = min(trial_results, key=lambda t: t["best_b"]["hidden_colors"])["best_b"]
        overall_best_c = min(trial_results, key=lambda t: t["best_c"]["hidden_colors"])["best_c"]

        # Paired statistics on the 160 Hidden Graphs for Overall Champions
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

        # Paired comparisons:
        # B vs A (Evolution vs Independent)
        stat_b_vs_a = paired_stats(overall_best_b["hidden_scores"], overall_best_a["hidden_scores"], "Evolution vs Independent")
        # B vs C (Evolution vs Random-Parent)
        stat_b_vs_c = paired_stats(overall_best_b["hidden_scores"], overall_best_c["hidden_scores"], "Evolution vs Random-Parent")
        # A vs C (Independent vs Random-Parent)
        stat_a_vs_c = paired_stats(overall_best_a["hidden_scores"], overall_best_c["hidden_scores"], "Independent vs Random-Parent")
        # B vs DSATUR
        stat_b_vs_dsatur = paired_stats(overall_best_b["hidden_scores"], baseline_hidden_scores["DSATUR"]["scores"], "Evolution vs DSATUR")
        # B vs RLF
        stat_b_vs_rlf = paired_stats(overall_best_b["hidden_scores"], baseline_hidden_scores["RLF"]["scores"], "Evolution vs RLF")

        print("\nPaired Statistical Analysis on 160 Hidden Graphs:")
        for s in [stat_b_vs_a, stat_b_vs_c, stat_a_vs_c, stat_b_vs_dsatur, stat_b_vs_rlf]:
            print(f"  {s['comparison']:30s} | W={s['wins']:3d}, L={s['losses']:3d}, T={s['ties']:3d} | Net={s['net_diff']:+4d} | "
                  f"Mean={s['mean_diff']:+.4f} (95% CI: {s['ci_95']}) | Wilcoxon p={s['wilcoxon_p']:.4f} | d={s['cohens_d']:+.3f}")

        total_runtime = time.time() - t0

        summary = {
            "experiment": "Experiment #8 — Evolution vs Equal-Budget Search",
            "model": "antigravity/claude-sonnet-4-6",
            "total_runtime_seconds": round(total_runtime, 2),
            "token_usage": {
                "total_calls": self.client.total_calls,
                "total_prompt_tokens": self.client.total_prompt_tokens,
                "total_completion_tokens": self.client.total_completion_tokens,
                "failed_calls": self.client.failed_calls,
            },
            "num_trials": num_trials,
            "calls_per_condition_per_trial": 15,
            "total_calls_per_trial": 45,
            "total_calls_all_trials": 135,
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
            }
        }

        with open(self.summary_json_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n[OUTPUT] Saved Experiment #8 summary to {self.summary_json_path}")

        print("\n" + "=" * 80)
        print("EXPERIMENT #8 ORCHESTRATION COMPLETED SUCCESSFULLY.")
        print("=" * 80)


if __name__ == "__main__":
    runner = Experiment8Runner()
    runner.run_experiment_8()
