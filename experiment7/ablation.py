"""
Experiment #7: Champion Component Ablation Study
================================================
Ablates the discovered champion `gen9_crossover_e21319` on Dev (40) and Hidden (160)
by cleanly enabling/disabling specific algorithmic components:
- Variant 1: Base Portfolio (Deterministic DSATUR + RLF only)
- Variant 2: Portfolio + Randomized Restarts (no Kempe, no Squeeze)
- Variant 3: Portfolio + Restarts + Kempe Reduction (no Squeeze)
- Variant 4: Full Champion (Portfolio + Restarts + Kempe + Squeeze_last)
- Variant 5: Full Champion WITHOUT RLF (DSATUR + Restarts + Kempe + Squeeze)
- Variant 6: Full Champion WITHOUT DSATUR (RLF + Kempe + Squeeze)
- Variant 7: Pure Kempe + Squeeze on single deterministic DSATUR
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from experiment7.evaluator import SolverEvaluator


def run_clean_ablation():
    evaluator = SolverEvaluator()

    # Load Full Champion code from summary.json
    with open("experiment7/summary.json") as f:
        summary_obj = json.load(f)

    champ_code = summary_obj["champion"]["code"]

    variants = {}

    # Variant 1: Portfolio Only (Deterministic DSATUR + RLF, no noise, no Kempe, no Squeeze)
    v1_code = champ_code
    # Replace the execution phase at the bottom of the champion:
    exec_block_v1 = """
    # Phase 1: Only initial deterministic constructions
    update_best(dsatur_color(noise=0.0))
    update_best(rlf_color())
    return best_colors
"""
    # Replace from "# Phase 1: Initial constructions" to "return best_colors"
    idx = champ_code.find("    # Phase 1: Initial constructions")
    base_prefix = champ_code[:idx]
    variants["Ablation_1_Portfolio_Only"] = base_prefix + exec_block_v1

    # Variant 2: Portfolio + Randomized Restarts (No Kempe, No Squeeze)
    exec_block_v2 = """
    # Phase 1: Initial constructions + random restarts
    update_best(dsatur_color(noise=0.0))
    update_best(rlf_color())
    for _ in range(8):
        update_best(dsatur_color(noise=1.0))
    return best_colors
"""
    variants["Ablation_2_Portfolio_Plus_Restarts"] = base_prefix + exec_block_v2

    # Variant 3: Portfolio + Restarts + Kempe Reduction (No Squeeze)
    exec_block_v3 = """
    # Phase 1: Initial constructions
    update_best(dsatur_color(noise=0.0))
    update_best(rlf_color())
    for _ in range(3):
        update_best(dsatur_color(noise=1.0))

    # Phase 2: Kempe reduce best
    reduced = kempe_reduce(best_colors)
    update_best(reduced)

    # Phase 3: Restarts with Kempe
    for _ in range(5):
        c = dsatur_color(noise=1.0)
        c = kempe_reduce(c)
        update_best(c)

    # Phase 4: RLF with Kempe
    c = rlf_color()
    c = kempe_reduce(c)
    update_best(c)
    return best_colors
"""
    variants["Ablation_3_Portfolio_Restarts_Kempe_NoSqueeze"] = base_prefix + exec_block_v3

    # Variant 4: Full Champion (Portfolio + Restarts + Kempe + Squeeze_last)
    variants["Ablation_4_Full_Champion"] = champ_code

    # Variant 5: Full Champion WITHOUT RLF
    variants["Ablation_5_No_RLF"] = champ_code.replace("update_best(rlf_color())", "# update_best(rlf_color())").replace("c = rlf_color()", "# c = rlf_color()").replace("c = kempe_reduce(c)\n    update_best(c)", "# no rlf kempe")

    # Variant 6: Full Champion WITHOUT DSATUR
    v6_code = champ_code.replace("update_best(dsatur_color(noise=0.0))", "# no dsatur").replace("for _ in range(3):\n        update_best(dsatur_color(noise=1.0))", "# no dsatur restarts").replace("for _ in range(5):\n        c = dsatur_color(noise=1.0)\n        c = kempe_reduce(c)\n        update_best(c)", "# no dsatur kempe")
    variants["Ablation_6_No_DSATUR"] = v6_code

    # Variant 7: Single DSATUR + Kempe + Squeeze (No Restarts, No RLF)
    exec_block_v7 = """
    # Single DSATUR run + Kempe + Squeeze
    c = dsatur_color(noise=0.0)
    c = kempe_reduce(c)
    c = squeeze_last(c)
    c = kempe_reduce(c)
    return c
"""
    variants["Ablation_7_Single_DSATUR_Plus_LocalSearch"] = base_prefix + exec_block_v7

    print("\n" + "=" * 75)
    print("RUNNING COMPREHENSIVE COMPONENT ABLATION ON DEV & HIDDEN BENCHMARKS")
    print("=" * 75)

    ablation_results = {}
    for name, code in variants.items():
        dev_res = evaluator.evaluate_solver_code(code, dataset_type="dev")
        hidden_res = evaluator.evaluate_solver_code(code, dataset_type="hidden")
        rec = {
            "dev_total_colors": dev_res["total_colors"],
            "dev_runtime_ms": dev_res["runtime_ms"],
            "hidden_total_colors": hidden_res["total_colors"],
            "hidden_runtime_ms": hidden_res["runtime_ms"],
            "dev_valid": dev_res["is_valid"],
            "hidden_valid": hidden_res["is_valid"],
        }
        ablation_results[name] = rec
        print(f"  {name:42s} | Dev: {dev_res['total_colors']:4d} colors ({dev_res['runtime_ms']:6.1f}ms) | "
              f"Hidden: {hidden_res['total_colors']:4d} colors ({hidden_res['runtime_ms']:6.1f}ms)")

    output_path = os.path.join("experiment7", "ablation_results.json")
    with open(output_path, "w") as f:
        json.dump(ablation_results, f, indent=2)
    print(f"\n[OUTPUT] Saved ablation results to {output_path}")


if __name__ == "__main__":
    run_clean_ablation()
