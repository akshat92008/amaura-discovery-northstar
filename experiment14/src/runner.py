"""
Experiment #14 Master Runner: Search Budget Scaling & Discovery Reliability
==========================================================================
Conditions:
- N15: 15 calls / trial (5 trials) -> 75 calls
- N30: 30 calls / trial (5 trials) -> 150 calls
- N60: 60 calls / trial (5 trials) -> 300 calls
Total Calls: 525 LLM calls

Features:
- Concurrent worker pool (max_workers=5) for high-efficiency throughput
- Master prompt pool (60 angles) with deterministic seed permutations per trial
- Resumable candidate logging & caching (candidate_id = {condition}_T{trial}_C{call})
- AST check & sandbox evaluation on 30 dev instances
- Champion freezing in experiment14/frozen/frozen_champions.json
- Blind Hidden Evaluation across 120 hidden instances
"""

import concurrent.futures
import copy
import hashlib
import json
import os
import random
import sys
import threading
import time
from typing import Dict, Any, List, Optional, Tuple

from experiment14.src.evaluator import PodSchedulingEvaluator
from experiment14.src.llm_client import CloudSchedulingLLMClient
from experiment14.src.prompts import PROMPT_PERSPECTIVES, get_prompt_for_perspective


class Experiment14Runner:
    def __init__(
        self,
        config_path: str = "experiment14/config.json",
        seeds_path: str = "experiment14/seeds.json",
        dev_bench_path: str = "experiment14/benchmarks/dev.json",
        hidden_bench_path: str = "experiment14/benchmarks/hidden.json",
        logs_path: str = "experiment14/logs/llm_calls.jsonl",
        candidates_path: str = "experiment14/candidates/candidates.jsonl"
    ):
        with open(config_path) as f:
            self.config = json.load(f)
        with open(seeds_path) as f:
            self.seeds_data = json.load(f)

        self.dev_bench_path = dev_bench_path
        self.hidden_bench_path = hidden_bench_path
        self.logs_path = logs_path
        self.candidates_path = candidates_path

        with open(dev_bench_path) as f:
            self.dev_instances = json.load(f)

        self.max_concurrency = self.config.get("max_concurrency", 5)

        self.llm_client = CloudSchedulingLLMClient(
            model=self.config.get("model", "nvidia/nvidia/nemotron-3-super-120b-a12b"),
            base_url=self.config.get("api_base_url", "http://127.0.0.1:20128/v1/chat/completions"),
            api_key=self.config.get("api_key") or os.environ.get("OMNIROUTE_API_KEY"),
            max_tokens=self.config.get("max_completion_tokens", 4096)
        )

        budget_cfg = self.config.get("computational_budget", {})
        self.evaluator = PodSchedulingEvaluator(
            scale_aware_base_ms=budget_cfg.get("scale_aware_timeout_base_ms", 1000.0),
            scale_aware_per_nm_ms=budget_cfg.get("scale_aware_timeout_per_nm_ms", 1.0),
            sigalrm_interrupt_sec=budget_cfg.get("sigalrm_interrupt_sec", 10)
        )

        os.makedirs(os.path.dirname(self.logs_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.candidates_path), exist_ok=True)
        os.makedirs("experiment14/frozen", exist_ok=True)
        os.makedirs("experiment14/results", exist_ok=True)

        self.log_lock = threading.Lock()
        self.cand_lock = threading.Lock()
        self.completed_candidates: Dict[str, Dict[str, Any]] = self._load_existing_candidates()

    def _load_existing_candidates(self) -> Dict[str, Dict[str, Any]]:
        existing = {}
        if os.path.exists(self.candidates_path):
            with open(self.candidates_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            cid = record["candidate_id"]
                            existing[cid] = record
                        except Exception:
                            pass
        return existing

    def _log_llm_call(self, call_data: Dict[str, Any]):
        with self.log_lock:
            with open(self.logs_path, "a") as f:
                f.write(json.dumps(call_data) + "\n")

    def _log_candidate(self, candidate_data: Dict[str, Any]):
        with self.cand_lock:
            with open(self.candidates_path, "a") as f:
                f.write(json.dumps(candidate_data) + "\n")

    def execute_single_candidate(
        self,
        cond: str,
        trial_idx: int,
        call_idx: int,
        perspective: Dict[str, Any]
    ) -> Dict[str, Any]:
        cid = f"{cond}_T{trial_idx+1}_C{call_idx+1:02d}"

        if cid in self.completed_candidates:
            cand = self.completed_candidates[cid]
            return cand

        prompt = get_prompt_for_perspective(perspective)
        llm_res = self.llm_client.query(prompt=prompt, temperature=self.config["temperature"])

        call_log = {
            "call_id": cid,
            "condition": cond,
            "trial_idx": trial_idx,
            "call_idx": call_idx,
            "perspective_id": perspective["id"],
            "angle_name": perspective["name"],
            "category": perspective["category"],
            "timestamp": time.time(),
            "model": llm_res["model"],
            "prompt_hash": llm_res["prompt_hash"],
            "response_hash": llm_res["response_hash"],
            "candidate_hash": llm_res["candidate_hash"],
            "prompt_tokens": llm_res["prompt_tokens"],
            "completion_tokens": llm_res["completion_tokens"],
            "total_tokens": llm_res["total_tokens"],
            "finish_reason": llm_res["finish_reason"],
            "is_truncated": llm_res["is_truncated"],
            "duration_ms": llm_res["duration_ms"],
            "success": llm_res["success"],
            "error": llm_res["error"]
        }
        self._log_llm_call(call_log)

        if llm_res["success"] and llm_res["code"]:
            code = llm_res["code"]
            eval_res = self.evaluator.evaluate_solver_code(code, self.dev_instances)
        else:
            code = ""
            eval_res = {
                "is_valid": False,
                "total_cost": 999999.0,
                "mean_cost": 999999.0,
                "instance_costs": [],
                "active_nodes_mean": 0.0,
                "unscheduled_total": 999,
                "runtime_ms": 0.0,
                "error": llm_res["error"] or "No code extracted"
            }

        candidate_record = {
            "candidate_id": cid,
            "condition": cond,
            "trial_idx": trial_idx,
            "call_idx": call_idx,
            "perspective_id": perspective["id"],
            "angle_name": perspective["name"],
            "category": perspective["category"],
            "timestamp": time.time(),
            "code": code,
            "code_chars": len(code),
            "validity": eval_res["is_valid"],
            "development_cost": eval_res["total_cost"],
            "mean_cost": eval_res["mean_cost"],
            "instance_costs": eval_res["instance_costs"],
            "active_nodes_mean": eval_res["active_nodes_mean"],
            "unscheduled_total": eval_res["unscheduled_total"],
            "runtime_ms": eval_res["runtime_ms"],
            "eval_error": eval_res["error"],
            "prompt_tokens": llm_res["prompt_tokens"],
            "completion_tokens": llm_res["completion_tokens"],
            "total_tokens": llm_res["total_tokens"],
            "is_truncated": llm_res["is_truncated"],
            "call_duration_ms": llm_res["duration_ms"]
        }
        self._log_candidate(candidate_record)

        status_str = "VALID" if eval_res["is_valid"] else "INVALID"
        cost_str = f"{eval_res['total_cost']:8.2f}" if eval_res["is_valid"] else "  FAIL  "
        print(f"[{cid}] {status_str} | Dev Cost: {cost_str} (Nodes: {eval_res['active_nodes_mean']:4.1f}) | {perspective['name'][:30]:30s} | Tokens: {llm_res['completion_tokens']}", flush=True)

        return candidate_record

    def run_trial(
        self,
        cond: str,
        trial_idx: int,
        budget: int,
        seed: int
    ) -> Dict[str, Any]:
        print(f"\n============================================================")
        print(f"STARTING {cond} — TRIAL {trial_idx+1}/5 (Budget: {budget}, Seed: {seed})")
        print(f"============================================================")

        rng = random.Random(seed)
        # Deterministically permute the 60 master perspectives for this trial
        permuted_perspectives = list(PROMPT_PERSPECTIVES)
        rng.shuffle(permuted_perspectives)

        # Slice the first budget perspectives (nested sequence)
        trial_perspectives = permuted_perspectives[:budget]

        candidates = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            future_to_idx = {
                executor.submit(self.execute_single_candidate, cond, trial_idx, i, p): i
                for i, p in enumerate(trial_perspectives)
            }
            # Collect results in order of completion
            for fut in concurrent.futures.as_completed(future_to_idx):
                cand = fut.result()
                candidates.append(cand)

        # Sort candidates by call_idx to preserve sequential discovery order
        candidates.sort(key=lambda c: c["call_idx"])

        # Track discovery trajectory over calls (best dev score after call 1..N)
        best_so_far = float("inf")
        discovery_trajectory = []
        for c in candidates:
            if c["validity"] and c["development_cost"] < best_so_far:
                best_so_far = c["development_cost"]
            discovery_trajectory.append(best_so_far)

        # Select Trial Champion: Minimum dev cost among valid candidates
        valid_cands = [c for c in candidates if c["validity"] and c["development_cost"] < 999999.0]
        if valid_cands:
            champ = min(valid_cands, key=lambda c: c["development_cost"])
        else:
            champ = candidates[0]

        champ["discovery_trajectory"] = discovery_trajectory
        champ["trial_seed"] = seed
        champ["budget"] = budget

        print(f"\n>>> [{cond} TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} ({champ['angle_name']}) | Dev Cost: {champ['development_cost']:.2f} <<<")
        return champ

    def run_all_conditions(self) -> Dict[str, List[Dict[str, Any]]]:
        conditions = self.config["conditions"]
        budgets = self.config["budgets"]
        trial_seeds = self.seeds_data["trial_seeds"]

        champions_by_cond = {}

        t0_all = time.perf_counter()
        print("================================================================================")
        print("LAUNCHING AMAURA EXPERIMENT #14: SEARCH BUDGET SCALING & DISCOVERY RELIABILITY")
        print(f"Conditions: {conditions} | Total Calls: {self.config['total_llm_calls']} | Workers: {self.max_concurrency}")
        print("================================================================================")

        for cond in conditions:
            budget = budgets[cond]
            seeds = trial_seeds[cond]
            champions_by_cond[cond] = []

            print(f"\n################################################################")
            print(f"EXECUTING CONDITION {cond} (Budget: {budget} calls/trial, 5 trials)")
            print(f"################################################################")

            for trial_idx, seed in enumerate(seeds):
                champ = self.run_trial(cond, trial_idx, budget, seed)
                champions_by_cond[cond].append(champ)

        total_min = (time.perf_counter() - t0_all) / 60.0
        print("\n================================================================================")
        print(f"ALL SEARCH CONDITIONS COMPLETE! Total time: {total_min:.1f} minutes")
        print("================================================================================")

        self._freeze_all_champions(champions_by_cond)
        return champions_by_cond

    def _freeze_all_champions(self, champions_by_cond: Dict[str, List[Dict[str, Any]]]):
        frozen_data = {
            "metadata": {
                "experiment": "Amaura Experiment #14: Search Budget Scaling & Discovery Reliability",
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": self.config["model"],
                "conditions": self.config["conditions"],
                "budgets": self.config["budgets"],
                "total_champions": sum(len(v) for v in champions_by_cond.values())
            },
            "champions": {}
        }

        for cond, champs in champions_by_cond.items():
            frozen_data["champions"][cond] = []
            for c in champs:
                code_sha = hashlib.sha256(c["code"].encode("utf-8")).hexdigest()
                frozen_data["champions"][cond].append({
                    "candidate_id": c["candidate_id"],
                    "condition": cond,
                    "trial_idx": c["trial_idx"],
                    "call_idx": c["call_idx"],
                    "budget": c["budget"],
                    "perspective_id": c["perspective_id"],
                    "angle_name": c["angle_name"],
                    "category": c["category"],
                    "development_cost": c["development_cost"],
                    "mean_cost": c["mean_cost"],
                    "active_nodes_mean": c["active_nodes_mean"],
                    "unscheduled_total": c["unscheduled_total"],
                    "runtime_ms": c["runtime_ms"],
                    "validity": c["validity"],
                    "code_sha256": code_sha,
                    "discovery_trajectory": c.get("discovery_trajectory", []),
                    "code": c["code"]
                })

        out_path = "experiment14/frozen/frozen_champions.json"
        with open(out_path, "w") as f:
            json.dump(frozen_data, f, indent=2)
        print(f"\nSuccessfully froze all 15 champions -> {out_path}")

    def evaluate_frozen_champions_on_hidden(self):
        print(f"\n================================================================================")
        print(f"EVALUATING ALL 15 FROZEN CHAMPIONS ON HIDDEN BENCHMARK (120 INSTANCES)")
        print(f"================================================================================")
        frozen_path = "experiment14/frozen/frozen_champions.json"
        if not os.path.exists(frozen_path):
            raise FileNotFoundError(f"Frozen champions file not found: {frozen_path}")

        with open(frozen_path) as f:
            frozen_data = json.load(f)

        with open(self.hidden_bench_path) as f:
            hidden_instances = json.load(f)

        hidden_results = {
            "metadata": {
                "hidden_benchmark_instances": len(hidden_instances),
                "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timeout_formula": self.config.get("computational_budget", {}).get("formula")
            },
            "evaluations": {}
        }

        for cond, champ_list in frozen_data["champions"].items():
            hidden_results["evaluations"][cond] = []
            print(f"\n--- Evaluating Condition {cond} Champions ---")
            for champ in champ_list:
                cid = champ["candidate_id"]
                code = champ["code"]
                res = self.evaluator.evaluate_solver_code(code, hidden_instances)
                eval_record = {
                    "candidate_id": cid,
                    "condition": cond,
                    "trial_idx": champ["trial_idx"],
                    "budget": champ["budget"],
                    "angle_name": champ["angle_name"],
                    "category": champ["category"],
                    "validity": res["is_valid"],
                    "hidden_total_cost": res["total_cost"],
                    "hidden_mean_cost": res["mean_cost"],
                    "instance_costs": res["instance_costs"],
                    "active_nodes_mean": res["active_nodes_mean"],
                    "unscheduled_total": res["unscheduled_total"],
                    "runtime_ms": res["runtime_ms"],
                    "error": res["error"]
                }
                hidden_results["evaluations"][cond].append(eval_record)
                status_str = "VALID" if res["is_valid"] else "INVALID"
                print(f"   [{cid}] Hidden Total Cost: {res['total_cost']:8.2f} | Mean: {res['mean_cost']:6.2f} | Active Nodes: {res['active_nodes_mean']:4.1f} | Runtime: {res['runtime_ms']:5.1f}ms | Status: {status_str}")

        out_path = "experiment14/results/hidden_results.json"
        with open(out_path, "w") as f:
            json.dump(hidden_results, f, indent=2)
        print(f"\nHidden evaluations completed and saved -> {out_path}")


if __name__ == "__main__":
    runner = Experiment14Runner()
    champions = runner.run_all_conditions()
    runner.evaluate_frozen_champions_on_hidden()
    print("\nALL EXPERIMENT #14 RUNS AND EVALUATIONS COMPLETED!")
