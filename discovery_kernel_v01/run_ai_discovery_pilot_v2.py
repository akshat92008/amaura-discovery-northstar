"""
North BlueStar: Corrected AI Discovery Pilot v2 Runner (2026-10-20)
==================================================================
Fair Budgets, Search Diversity and Unseen-Data Verification
Orchestrates:
1. Preflight baseline evaluation on 20 new development instances.
2. Arm A: 30 independent proposals (5 blocks x 6 calls) with zero feedback.
3. Arm B: 30 diversity-controlled proposals (5 blocks x 3 rounds of 2 calls) with evidence feedback & tabu list.
4. Selection and immutable freezing of Champion A and Champion B.
5. Sealed holdout evaluation on 30 untouched instances.
6. Paired relative improvement statistics, 95% bootstrap CIs, and discovery gate test.
"""

import copy
import hashlib
import json
import math
import os
import random
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from discovery_kernel.problem_spec import ConstraintRule
from discovery_kernel.method_adapter import (
    MethodAdapter, MethodMetadata, PFSPNEHAdapter, PFSPNEHLSAdapter, PFSPFunctionAdapter
)
from discovery_kernel.pfsp_declarative import (
    PFSPDeclarativeAdapter, validate_config, canonicalize_config, solve_declarative
)
from discovery_kernel.execution import ExecutionSupervisor
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    calc_makespan_and_flow_ref,
    iterated_greedy_solve
)
from benchmark_v1.src.domains.pfsp_full_algorithm import (
    calc_makespan,
    validate_permutation,
    neh_solve,
    neh_ls_solve
)

EXPERIMENT_DIR = os.path.join(REPO_ROOT, "discovery_kernel_v01", "results", "ai_discovery_pilot_v2_20261020")
DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")
DEV_RESULTS_PATH = os.path.join(EXPERIMENT_DIR, "development_results.json")
FINAL_RESULTS_PATH = os.path.join(EXPERIMENT_DIR, "final_results.json")
RUN_RECORDS_PATH = os.path.join(EXPERIMENT_DIR, "run_records.jsonl")
MODEL_NAME = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

NEUTRAL_SCHEMA_PROMPT = """You are an expert algorithm designer specializing in Permutation Flow-Shop Scheduling (PFSP).
The objective is to minimize makespan (C_max) on flow-shop benchmark instances.

Design an algorithm by selecting exactly ONE valid option for each of the 6 components from the allowed options below:

1. initial_order:
   - "total_processing_time_desc" (Sum of processing times descending, standard LPT/NEH)
   - "total_processing_time_asc" (Sum of processing times ascending, SPT)
   - "first_machine_asc" (First machine processing time ascending)
   - "last_machine_desc" (Last machine processing time descending)
   - "weighted_profile_desc" (Palmer's slope weighting index descending)

2. construction_criterion:
   - "makespan_only" (Evaluate partial schedules by C_max alone)
   - "makespan_and_flow_time" (Minimize C_max primary, total flow time secondary)
   - "makespan_and_idle_time" (Minimize C_max primary, machine idle time secondary)

3. tie_break:
   - "first_found" (First position that achieves optimal score)
   - "last_found" (Last position that achieves optimal score)
   - "flow_time_min" (Break score ties by minimal total flow time)
   - "idle_time_min" (Break score ties by minimal machine idle time)

4. local_search:
   - "none" (Constructive only, no local search)
   - "pairwise_swap" (Adjacent pairwise swap neighborhood)
   - "single_pass_insertion" (Taillard single-pass insertion neighborhood)

5. search_strategy:
   - "none" (Required if local_search is "none")
   - "first_improvement" (Accept first improving neighbor)
   - "best_improvement" (Scan neighborhood and accept best improving move)

6. acceptance_rule:
   - "none" (Required if local_search is "none")
   - "strictly_better_makespan" (Accept only if makespan strictly decreases)
   - "better_makespan_or_flow" (Accept if makespan decreases, or makespan ties and flow time decreases)

Note: Resource budget is managed externally by the system as a fair single-pass neighborhood budget.

Output MUST be a single JSON object with exactly two keys:
{
  "rationale": "<brief 1-2 sentence explanation of your design hypothesis>",
  "config": {
    "initial_order": "<selected initial_order>",
    "construction_criterion": "<selected construction_criterion>",
    "tie_break": "<selected tie_break>",
    "local_search": "<selected local_search>",
    "search_strategy": "<selected search_strategy>",
    "acceptance_rule": "<selected acceptance_rule>"
  }
}
"""


def query_ollama(prompt: str, temperature: float = 0.7, timeout_sec: int = 60) -> Tuple[str, int, int, float]:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout_sec) as response:
        resp_bytes = response.read()
    latency = time.perf_counter() - t0
    result = json.loads(resp_bytes.decode("utf-8"))
    raw_text = result.get("response", "")
    p_tokens = result.get("prompt_eval_count", 0)
    c_tokens = result.get("eval_count", 0)
    return raw_text, p_tokens, c_tokens, latency


def validate_perm_top(instance: Dict[str, Any], solution: Any) -> Tuple[bool, Optional[str]]:
    times = instance["times"] if isinstance(instance, dict) else instance
    return validate_permutation(solution, len(times))


def pfsp_evaluator_top(instance: Dict[str, Any], solution: Any) -> float:
    times = instance["times"] if isinstance(instance, dict) else instance
    return float(calc_makespan_ref(times, solution))


def solve_ig_top(times: List[List[int]]) -> List[int]:
    return iterated_greedy_solve(times, d=4, max_iter=20)


PFSP_CONSTRAINT = ConstraintRule(
    name="valid_job_permutation",
    description="Solution must be a valid permutation of [0, ..., n-1]",
    validator=validate_perm_top
)


def bootstrap_relative_ci(
    baseline_makespans: List[int],
    candidate_makespans: List[int],
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 42
) -> Dict[str, Any]:
    assert len(baseline_makespans) == len(candidate_makespans)
    n = len(baseline_makespans)
    g_vals = [(b - c) / b for b, c in zip(baseline_makespans, candidate_makespans)]
    mean_g = float(sum(g_vals) / n)
    sorted_g = sorted(g_vals)
    median_g = float(sorted_g[n // 2] if n % 2 != 0 else (sorted_g[n // 2 - 1] + sorted_g[n // 2]) / 2)
    std_g = float(math.sqrt(sum((x - mean_g) ** 2 for x in g_vals) / (n - 1))) if n > 1 else 0.0

    wins = sum(1 for g in g_vals if g > 1e-9)
    ties = sum(1 for g in g_vals if abs(g) <= 1e-9)
    losses = sum(1 for g in g_vals if g < -1e-9)

    rng = random.Random(seed)
    boot_means = []
    for _ in range(n_resamples):
        sample = [g_vals[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    low_idx = int((alpha / 2.0) * n_resamples)
    high_idx = int((1.0 - alpha / 2.0) * n_resamples)
    ci_lower = float(boot_means[low_idx])
    ci_upper = float(boot_means[high_idx])

    return {
        "mean_relative_improvement": mean_g,
        "median_relative_improvement": median_g,
        "std_relative_improvement": std_g,
        "ci_lower_95": ci_lower,
        "ci_upper_95": ci_upper,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "n_instances": n,
        "individual_g": g_vals
    }


def main():
    print("=" * 80)
    print("NORTH BLUESTAR: CORRECTED AI DISCOVERY PILOT V2")
    print("Protocol: Fair Budgets, Search Diversity & Unseen-Data Verification")
    print("=" * 80)

    # 1. Datasets
    dev_path = os.path.join(DATA_DIR, "dev_instances.json")
    holdout_path = os.path.join(DATA_DIR, "holdout_instances.json")

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_instances = json.load(f)
    with open(holdout_path, "r", encoding="utf-8") as f:
        holdout_instances = json.load(f)

    with open(dev_path, "rb") as f:
        dev_hash = hashlib.sha256(f.read()).hexdigest()
    with open(holdout_path, "rb") as f:
        holdout_hash = hashlib.sha256(f.read()).hexdigest()

    print(f"Loaded {len(dev_instances)} Development Instances (SHA-256: {dev_hash})")
    print(f"Loaded {len(holdout_instances)} Sealed Holdout Instances (SHA-256: {holdout_hash})")

    run_records_path = os.path.join(EXPERIMENT_DIR, "run_records.jsonl")
    records_file = open(run_records_path, "w", encoding="utf-8")

    def log_record(event_type: str, data: Dict[str, Any]):
        rec = {
            "timestamp": time.time(),
            "event_type": event_type,
            **data
        }
        records_file.write(json.dumps(rec) + "\n")
        records_file.flush()

    log_record("EXPERIMENT_INITIALIZED", {
        "experiment_name": "ai_discovery_pilot_v2_20261020",
        "dev_instances": len(dev_instances),
        "dev_hash": dev_hash,
        "holdout_instances": len(holdout_instances),
        "holdout_hash": holdout_hash,
        "model": MODEL_NAME,
        "provider": "ollama/local",
        "billing_cost_usd": 0.0,
        "budget_policy": "B(n) = n(n-1) single_pass"
    })

    supervisor = ExecutionSupervisor(timeout_sec=5.0, max_memory_mb=512.0)

    # =========================================================================
    # PHASE 1: Conventional Baselines Evaluation on Development Data
    # =========================================================================
    print("\n--- PHASE 1: Evaluating Conventional Baselines on Development Data ---")

    baseline_adapters = {
        "neh_classical": PFSPNEHAdapter(version="1.0.0"),
        "neh_ls_insertion": PFSPNEHLSAdapter(version="1.0.0"),
        "iterated_greedy": PFSPFunctionAdapter(
            method_id="iterated_greedy",
            solve_func=solve_ig_top,
            description="Iterated Greedy metaheuristic (d=4, max_iter=20)"
        )
    }

    baseline_dev_results = {}
    for b_id, adapter in baseline_adapters.items():
        makespans = []
        runtimes = []
        valid_all = True
        for inst in dev_instances:
            res = supervisor.execute_and_evaluate(
                adapter=adapter,
                instance=inst,
                instance_id=inst["id"],
                evaluator_fn=pfsp_evaluator_top,
                constraints=[PFSP_CONSTRAINT],
                objective_metric="makespan"
            )
            if not res.is_valid:
                valid_all = False
            cmax = int(res.objective_score) if res.is_valid and res.objective_score is not None else 9999999
            makespans.append(cmax)
            runtimes.append(res.runtime_ms)

        mean_ms = sum(makespans) / len(makespans) if valid_all else float("inf")
        mean_rt = sum(runtimes) / len(runtimes)
        baseline_dev_results[b_id] = {
            "all_valid": valid_all,
            "makespans": makespans,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt
        }
        print(f"  Baseline [{b_id}]: Mean Dev Makespan = {mean_ms:.2f}, Mean Runtime = {mean_rt:.2f} ms")
        log_record("BASELINE_DEV_EVALUATED", {
            "baseline_id": b_id,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt,
            "all_valid": valid_all
        })

    primary_baseline_id = "neh_ls_insertion"
    print(f"\nFrozen Reference Baseline: [{primary_baseline_id}] (NEH-LS)")

    # =========================================================================
    # Candidate Evaluation Helper
    # =========================================================================
    seen_recipes: Dict[str, Dict[str, Any]] = {}

    def evaluate_candidate_on_dev(proposal_id: str, cfg: Dict[str, Any], rationale: str) -> Dict[str, Any]:
        adapter = PFSPDeclarativeAdapter(method_id=proposal_id, config=cfg, rationale=rationale)
        makespans = []
        runtimes = []
        evals_used_list = []
        term_conds = []
        all_valid = True
        error_msg = None

        for inst in dev_instances:
            res = supervisor.execute_and_evaluate(
                adapter=adapter,
                instance=inst,
                instance_id=inst["id"],
                evaluator_fn=pfsp_evaluator_top,
                constraints=[PFSP_CONSTRAINT],
                objective_metric="makespan"
            )
            if not res.is_valid:
                all_valid = False
                error_msg = res.error_message or "Invalid permutation"
            cmax = int(res.objective_score) if res.is_valid and res.objective_score is not None else 9999999
            makespans.append(cmax)
            runtimes.append(res.runtime_ms)
            evals_used_list.append(res.diagnostics.get("evaluations_used", 0))
            term_conds.append(res.diagnostics.get("termination_condition", "unknown"))

        mean_ms = sum(makespans) / len(makespans) if all_valid else float("inf")
        mean_rt = sum(runtimes) / len(runtimes)
        tot_evals = sum(evals_used_list)
        return {
            "all_valid": all_valid,
            "error_msg": error_msg,
            "makespans": makespans,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt,
            "total_evaluations_used": tot_evals,
            "termination_conditions": term_conds
        }

    def process_proposal(prop_id: str, arm: str, block_idx: int, raw_text: str, p_tok: int, c_tok: int, lat: float) -> Dict[str, Any]:
        is_valid_spec = False
        val_err = None
        sanitized_cfg = None
        r_hash = None
        rationale = ""

        try:
            parsed = json.loads(raw_text)
            rationale = parsed.get("rationale", "") if isinstance(parsed, dict) else ""
            if isinstance(parsed, dict) and "config" in parsed and isinstance(parsed["config"], dict):
                # Enforce fair external budget
                if parsed["config"].get("local_search") == "none":
                    parsed["config"]["budget_evaluations"] = 0
                else:
                    parsed["config"]["budget_evaluations"] = "single_pass"

                is_val, err, sanitized = validate_config(parsed)
                is_valid_spec = is_val
                val_err = err
                if is_val and sanitized:
                    sanitized_cfg = sanitized["config"]
                    _, _, r_hash = canonicalize_config(sanitized_cfg)
            else:
                val_err = "JSON missing config object"
        except Exception as e:
            val_err = f"JSON parse error: {str(e)}"

        is_dup = False
        dup_of = None
        eval_summary = None

        if is_valid_spec and r_hash:
            if r_hash in seen_recipes:
                is_dup = True
                dup_of = seen_recipes[r_hash]["first_proposal_id"]
                eval_summary = copy.deepcopy(seen_recipes[r_hash]["eval_summary"])
            else:
                eval_summary = evaluate_candidate_on_dev(prop_id, sanitized_cfg, rationale)
                seen_recipes[r_hash] = {
                    "first_proposal_id": prop_id,
                    "config": sanitized_cfg,
                    "eval_summary": eval_summary
                }

        record = {
            "proposal_id": prop_id,
            "arm": arm,
            "block_idx": block_idx,
            "is_valid_spec": is_valid_spec,
            "validation_error": val_err,
            "recipe_hash": r_hash,
            "is_syntactic_duplicate": is_dup,
            "duplicate_of": dup_of,
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "latency_sec": lat,
            "raw_response": raw_text,
            "config": sanitized_cfg,
            "rationale": rationale,
            "eval_summary": eval_summary
        }

        log_record("CANDIDATE_PROPOSAL_GENERATED", {
            "proposal_id": prop_id,
            "arm": arm,
            "block_idx": block_idx,
            "is_valid_spec": is_valid_spec,
            "recipe_hash": r_hash,
            "is_syntactic_duplicate": is_dup,
            "duplicate_of": dup_of,
            "mean_makespan": eval_summary["mean_makespan"] if eval_summary and eval_summary["all_valid"] else None,
            "latency_sec": lat
        })

        return record

    # =========================================================================
    # PHASE 2A: Arm A — Independent Generation (5 blocks x 6 calls = 30 calls)
    # =========================================================================
    print("\n--- PHASE 2A: Arm A — Independent Generation (5 blocks x 6 proposals) ---")
    arm_a_proposals = []
    prop_counter_a = 0

    for block in range(1, 6):
        print(f"\n  [Arm A Block {block}/5]:")
        for call_idx in range(1, 7):
            prop_counter_a += 1
            prop_id = f"arm_a_b{block}_p{call_idx:02d}"
            prompt = f"{NEUTRAL_SCHEMA_PROMPT}\nPropose a novel, high-potential algorithm configuration to minimize makespan. Output only the JSON object."
            print(f"    Generating {prop_id}...", end="", flush=True)
            raw_text, p_tok, c_tok, lat = query_ollama(prompt, temperature=0.7)
            rec = process_proposal(prop_id, "arm_a", block, raw_text, p_tok, c_tok, lat)
            arm_a_proposals.append(rec)
            status = f"C_max: {rec['eval_summary']['mean_makespan']:.2f}" if rec["eval_summary"] and rec["eval_summary"]["all_valid"] else f"ERR: {rec['validation_error']}"
            dup_tag = " (DUP)" if rec["is_syntactic_duplicate"] else ""
            print(f" {status}{dup_tag} [{lat:.2f}s]")

    # =========================================================================
    # PHASE 2B: Arm B — Diversity-Controlled Evidence Search (5 blocks x 6 calls)
    # 3 rounds per block: Round 1 (2 calls), Round 2 (2 calls), Round 3 (2 calls)
    # =========================================================================
    print("\n--- PHASE 2B: Arm B — Diversity-Controlled Search (5 blocks x 6 proposals) ---")
    arm_b_proposals = []
    prop_counter_b = 0

    for block in range(1, 6):
        print(f"\n  [Arm B Block {block}/5]:")
        block_history = []
        tabu_configs = []

        # Round 1: 2 Initial proposals
        print("    -- Round 1 (Initial) --")
        for r_call in range(1, 3):
            prop_counter_b += 1
            prop_id = f"arm_b_b{block}_r1_p{r_call:02d}"
            prompt = f"{NEUTRAL_SCHEMA_PROMPT}\nRound 1 of 3: Propose an initial high-potential algorithm configuration. Output only the JSON object."
            print(f"      Generating {prop_id}...", end="", flush=True)
            raw_text, p_tok, c_tok, lat = query_ollama(prompt, temperature=0.7)
            rec = process_proposal(prop_id, "arm_b", block, raw_text, p_tok, c_tok, lat)
            arm_b_proposals.append(rec)
            block_history.append(rec)
            if rec["config"]:
                tabu_configs.append(rec["config"])
            status = f"C_max: {rec['eval_summary']['mean_makespan']:.2f}" if rec["eval_summary"] and rec["eval_summary"]["all_valid"] else f"ERR: {rec['validation_error']}"
            dup_tag = " (DUP)" if rec["is_syntactic_duplicate"] else ""
            print(f" {status}{dup_tag} [{lat:.2f}s]")

        # Round 2: 2 Proposals with Round 1 feedback & Tabu list
        print("    -- Round 2 (Evidence Feedback & Diversity Directive) --")
        valid_b1 = [r for r in block_history if r["eval_summary"] and r["eval_summary"]["all_valid"]]
        valid_b1.sort(key=lambda r: r["eval_summary"]["mean_makespan"])
        ev_lines = []
        for v in valid_b1:
            cfg = v["config"]
            ev_lines.append(f"- Config: initial_order={cfg.get('initial_order')}, tie_break={cfg.get('tie_break')}, local_search={cfg.get('local_search')} -> Mean Makespan: {v['eval_summary']['mean_makespan']:.2f}")

        evidence_str = "\n".join(ev_lines) if ev_lines else "No valid configurations found in Round 1."
        tabu_str = json.dumps(tabu_configs, indent=2)

        round_2_prompt = f"""{NEUTRAL_SCHEMA_PROMPT}

EVIDENCE FROM ROUND 1 IN THIS SEARCH BLOCK (DEVELOPMENT DATASET):
{evidence_str}

TABU LIST (DO NOT REPEAT THESE PREVIOUSLY EVALUATED CONFIGURATIONS):
{tabu_str}

DIVERSIFICATION & MUTATION INSTRUCTIONS:
To avoid getting trapped in local search modes, do NOT repeat any configuration on the tabu list.
Explore alternative heuristic dimensions:
- Try a different tie-breaking rule (e.g. "idle_time_min" or "flow_time_min" vs "first_found").
- Try an alternative initial ordering (e.g. "total_processing_time_desc" vs "first_machine_asc" or "last_machine_desc").
- Test whether "single_pass_insertion" or "pairwise_swap" yields a more compact schedule.
Propose a distinct, high-potential configuration that is NOT on the tabu list.
Output only the JSON object.
"""
        for r_call in range(1, 3):
            prop_counter_b += 1
            prop_id = f"arm_b_b{block}_r2_p{r_call:02d}"
            print(f"      Generating {prop_id}...", end="", flush=True)
            raw_text, p_tok, c_tok, lat = query_ollama(round_2_prompt, temperature=0.7)
            rec = process_proposal(prop_id, "arm_b", block, raw_text, p_tok, c_tok, lat)
            arm_b_proposals.append(rec)
            block_history.append(rec)
            if rec["config"]:
                tabu_configs.append(rec["config"])
            status = f"C_max: {rec['eval_summary']['mean_makespan']:.2f}" if rec["eval_summary"] and rec["eval_summary"]["all_valid"] else f"ERR: {rec['validation_error']}"
            dup_tag = " (DUP)" if rec["is_syntactic_duplicate"] else ""
            print(f" {status}{dup_tag} [{lat:.2f}s]")

        # Round 3: 2 Proposals with Rounds 1 & 2 feedback & Tabu list
        print("    -- Round 3 (Refinement & Combinatorial Synthesis) --")
        valid_b2 = [r for r in block_history if r["eval_summary"] and r["eval_summary"]["all_valid"]]
        valid_b2.sort(key=lambda r: r["eval_summary"]["mean_makespan"])
        ev_lines3 = []
        for v in valid_b2:
            cfg = v["config"]
            ev_lines3.append(f"- Rank #{valid_b2.index(v)+1}: initial_order={cfg.get('initial_order')}, crit={cfg.get('construction_criterion')}, tie={cfg.get('tie_break')}, LS={cfg.get('local_search')} -> Mean Makespan: {v['eval_summary']['mean_makespan']:.2f}")

        evidence_str3 = "\n".join(ev_lines3)
        tabu_str3 = json.dumps(tabu_configs, indent=2)

        round_3_prompt = f"""{NEUTRAL_SCHEMA_PROMPT}

CUMULATIVE EVIDENCE FROM ROUNDS 1 & 2 IN THIS SEARCH BLOCK (DEVELOPMENT DATASET):
{evidence_str3}

TABU LIST (DO NOT REPEAT THESE CONFIGURATIONS):
{tabu_str3}

SYNTHESIS & EXPLOITATION INSTRUCTIONS:
Identify the best-performing structural components from the evidence above (such as the top initial order and tie-break rule).
Propose an improved configuration that synthesizes these strengths while remaining strictly distinct from all tabu list configurations.
Output only the JSON object.
"""
        for r_call in range(1, 3):
            prop_counter_b += 1
            prop_id = f"arm_b_b{block}_r3_p{r_call:02d}"
            print(f"      Generating {prop_id}...", end="", flush=True)
            raw_text, p_tok, c_tok, lat = query_ollama(round_3_prompt, temperature=0.7)
            rec = process_proposal(prop_id, "arm_b", block, raw_text, p_tok, c_tok, lat)
            arm_b_proposals.append(rec)
            block_history.append(rec)
            if rec["config"]:
                tabu_configs.append(rec["config"])
            status = f"C_max: {rec['eval_summary']['mean_makespan']:.2f}" if rec["eval_summary"] and rec["eval_summary"]["all_valid"] else f"ERR: {rec['validation_error']}"
            dup_tag = " (DUP)" if rec["is_syntactic_duplicate"] else ""
            print(f" {status}{dup_tag} [{lat:.2f}s]")

    # =========================================================================
    # PHASE 3: Development Selection & Champion Freezing
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: Development Champion Selection & Freezing")
    print("=" * 80)

    # Arm A Champion
    valid_a = [p for p in arm_a_proposals if p["eval_summary"] and p["eval_summary"]["all_valid"]]
    valid_a.sort(key=lambda p: p["eval_summary"]["mean_makespan"])
    champ_a_record = valid_a[0] if valid_a else None

    # Arm B Champion
    valid_b = [p for p in arm_b_proposals if p["eval_summary"] and p["eval_summary"]["all_valid"]]
    valid_b.sort(key=lambda p: p["eval_summary"]["mean_makespan"])
    champ_b_record = valid_b[0] if valid_b else None

    print(f"Arm A Total Proposals: {len(arm_a_proposals)} (Valid: {len(valid_a)})")
    if champ_a_record:
        print(f"  Champion A Selected: [{champ_a_record['proposal_id']}]")
        print(f"  Config: {json.dumps(champ_a_record['config'])}")
        print(f"  Mean Dev Makespan: {champ_a_record['eval_summary']['mean_makespan']:.2f}")

    print(f"\nArm B Total Proposals: {len(arm_b_proposals)} (Valid: {len(valid_b)})")
    if champ_b_record:
        print(f"  Champion B Selected: [{champ_b_record['proposal_id']}]")
        print(f"  Config: {json.dumps(champ_b_record['config'])}")
        print(f"  Mean Dev Makespan: {champ_b_record['eval_summary']['mean_makespan']:.2f}")

    log_record("CHAMPIONS_FROZEN", {
        "champion_a_id": champ_a_record["proposal_id"] if champ_a_record else None,
        "champion_a_hash": champ_a_record["recipe_hash"] if champ_a_record else None,
        "champion_a_dev_makespan": champ_a_record["eval_summary"]["mean_makespan"] if champ_a_record else None,
        "champion_a_config": champ_a_record["config"] if champ_a_record else None,
        "champion_b_id": champ_b_record["proposal_id"] if champ_b_record else None,
        "champion_b_hash": champ_b_record["recipe_hash"] if champ_b_record else None,
        "champion_b_dev_makespan": champ_b_record["eval_summary"]["mean_makespan"] if champ_b_record else None,
        "champion_b_config": champ_b_record["config"] if champ_b_record else None,
        "reference_baseline_id": primary_baseline_id,
        "reference_baseline_dev_makespan": baseline_dev_results[primary_baseline_id]["mean_makespan"]
    })

    # Save development_results.json
    dev_results_payload = {
        "metadata": {
            "experiment": "ai_discovery_pilot_v2_20261020",
            "date": "2026-10-20",
            "model": MODEL_NAME,
            "provider": "ollama/local",
            "dev_instances_count": len(dev_instances),
            "dev_instances_hash": dev_hash,
            "total_arm_a_calls": len(arm_a_proposals),
            "total_arm_b_calls": len(arm_b_proposals)
        },
        "baselines_dev": baseline_dev_results,
        "arm_a_proposals": arm_a_proposals,
        "arm_b_proposals": arm_b_proposals,
        "champion_a": champ_a_record,
        "champion_b": champ_b_record
    }
    with open(DEV_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(dev_results_payload, f, indent=2)
    print(f"\nSaved development results to: {DEV_RESULTS_PATH}")

    # =========================================================================
    # PHASE 4: Sealed Holdout Evaluation on 30 Untouched Instances
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 4: Sealed Holdout Evaluation on 30 Untouched Instances")
    print("=" * 80)

    holdout_eval_methods = {
        "reference_neh_ls": PFSPNEHLSAdapter(version="1.0.0"),
        "classical_neh": PFSPNEHAdapter(version="1.0.0"),
        "iterated_greedy": PFSPFunctionAdapter(
            method_id="iterated_greedy",
            solve_func=solve_ig_top,
            description="Iterated Greedy metaheuristic (d=4, max_iter=20)"
        )
    }

    if champ_a_record:
        holdout_eval_methods["champion_arm_a"] = PFSPDeclarativeAdapter(
            method_id="champion_arm_a",
            config=champ_a_record["config"],
            rationale=champ_a_record["rationale"]
        )
    if champ_b_record:
        holdout_eval_methods["champion_arm_b"] = PFSPDeclarativeAdapter(
            method_id="champion_arm_b",
            config=champ_b_record["config"],
            rationale=champ_b_record["rationale"]
        )

    holdout_results = {}
    for m_id, adapter in holdout_eval_methods.items():
        makespans = []
        runtimes = []
        evals_used_list = []
        term_conds = []
        valid_all = True
        print(f"  Evaluating [{m_id}] on 30 holdout instances...", end="", flush=True)

        for inst in holdout_instances:
            res = supervisor.execute_and_evaluate(
                adapter=adapter,
                instance=inst,
                instance_id=inst["id"],
                evaluator_fn=pfsp_evaluator_top,
                constraints=[PFSP_CONSTRAINT],
                objective_metric="makespan"
            )
            if not res.is_valid:
                valid_all = False
            cmax = int(res.objective_score) if res.is_valid and res.objective_score is not None else 9999999
            makespans.append(cmax)
            runtimes.append(res.runtime_ms)
            evals_used_list.append(res.diagnostics.get("evaluations_used", 0))
            term_conds.append(res.diagnostics.get("termination_condition", "unknown"))

            log_record("HOLDOUT_INSTANCE_EVALUATED", {
                "method_id": m_id,
                "instance_id": inst["id"],
                "makespan": cmax,
                "runtime_ms": res.runtime_ms,
                "is_valid": res.is_valid
            })

        mean_ms = sum(makespans) / len(makespans) if valid_all else float("inf")
        mean_rt = sum(runtimes) / len(runtimes)
        tot_evals = sum(evals_used_list)
        holdout_results[m_id] = {
            "all_valid": valid_all,
            "makespans": makespans,
            "mean_makespan": mean_ms,
            "mean_runtime_ms": mean_rt,
            "total_evaluations_used": tot_evals,
            "termination_conditions": term_conds
        }
        print(f" Mean C_max = {mean_ms:.2f}, Mean Runtime = {mean_rt:.2f} ms")

    # =========================================================================
    # PHASE 5: Statistical Comparison & Discovery Gate Verification
    # =========================================================================
    print("\n" + "=" * 80)
    print("PHASE 5: Statistical Comparison & Discovery Gate Evaluation")
    print("=" * 80)

    base_ms = holdout_results["reference_neh_ls"]["makespans"]
    stats_a_vs_base = bootstrap_relative_ci(base_ms, holdout_results["champion_arm_a"]["makespans"]) if "champion_arm_a" in holdout_results else None
    stats_b_vs_base = bootstrap_relative_ci(base_ms, holdout_results["champion_arm_b"]["makespans"]) if "champion_arm_b" in holdout_results else None
    stats_b_vs_a = bootstrap_relative_ci(holdout_results["champion_arm_a"]["makespans"], holdout_results["champion_arm_b"]["makespans"]) if ("champion_arm_a" in holdout_results and "champion_arm_b" in holdout_results) else None

    print("\n1. Arm A Champion vs NEH-LS Reference Baseline:")
    if stats_a_vs_base:
        print(f"   Mean Relative Improvement: {stats_a_vs_base['mean_relative_improvement']*100:+.3f}%")
        print(f"   Median Relative Improvement: {stats_a_vs_base['median_relative_improvement']*100:+.3f}%")
        print(f"   95% Bootstrap CI: [{stats_a_vs_base['ci_lower_95']*100:+.3f}%, {stats_a_vs_base['ci_upper_95']*100:+.3f}%]")
        print(f"   Wins / Ties / Losses: {stats_a_vs_base['wins']} / {stats_a_vs_base['ties']} / {stats_a_vs_base['losses']}")

    print("\n2. Arm B Champion vs NEH-LS Reference Baseline:")
    if stats_b_vs_base:
        print(f"   Mean Relative Improvement: {stats_b_vs_base['mean_relative_improvement']*100:+.3f}%")
        print(f"   Median Relative Improvement: {stats_b_vs_base['median_relative_improvement']*100:+.3f}%")
        print(f"   95% Bootstrap CI: [{stats_b_vs_base['ci_lower_95']*100:+.3f}%, {stats_b_vs_base['ci_upper_95']*100:+.3f}%]")
        print(f"   Wins / Ties / Losses: {stats_b_vs_base['wins']} / {stats_b_vs_base['ties']} / {stats_b_vs_base['losses']}")

    print("\n3. Arm B Champion vs Arm A Champion:")
    if stats_b_vs_a:
        print(f"   Mean Relative Improvement (B over A): {stats_b_vs_a['mean_relative_improvement']*100:+.3f}%")
        print(f"   95% Bootstrap CI: [{stats_b_vs_a['ci_lower_95']*100:+.3f}%, {stats_b_vs_a['ci_upper_95']*100:+.3f}%]")
        print(f"   Wins / Ties / Losses: {stats_b_vs_a['wins']} / {stats_b_vs_a['ties']} / {stats_b_vs_a['losses']}")

    # Check 1.0% Discovery Gate
    gate_passed_a = (stats_a_vs_base is not None and stats_a_vs_base["mean_relative_improvement"] >= 0.010 and stats_a_vs_base["ci_lower_95"] > 0.0)
    gate_passed_b = (stats_b_vs_base is not None and stats_b_vs_base["mean_relative_improvement"] >= 0.010 and stats_b_vs_base["ci_lower_95"] > 0.0)

    print("\n" + "=" * 80)
    print(f"DISCOVERY GATE STATUS: Arm A Met Gate = {gate_passed_a} | Arm B Met Gate = {gate_passed_b}")
    print("=" * 80)

    # Save final_results.json
    final_results_payload = {
        "metadata": {
            "experiment": "ai_discovery_pilot_v2_20261020",
            "date": "2026-10-20",
            "model": MODEL_NAME,
            "provider": "ollama/local",
            "holdout_instances_count": len(holdout_instances),
            "holdout_instances_hash": holdout_hash,
            "primary_baseline": primary_baseline_id,
            "discovery_gate_threshold_percent": 1.0
        },
        "holdout_methods": holdout_results,
        "statistical_tests": {
            "champion_a_vs_baseline": stats_a_vs_base,
            "champion_b_vs_baseline": stats_b_vs_base,
            "champion_b_vs_champion_a": stats_b_vs_a
        },
        "discovery_gate_verdict": {
            "arm_a_passed": gate_passed_a,
            "arm_b_passed": gate_passed_b
        }
    }
    with open(FINAL_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(final_results_payload, f, indent=2)
    print(f"\nSaved final results to: {FINAL_RESULTS_PATH}")

    records_file.close()
    print("\nExperiment execution complete. All records logged.")


if __name__ == "__main__":
    main()
