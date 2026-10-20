"""
Experiment #16 Master Discovery & Evaluation Runner
===================================================
Orchestrates:
1. Candidate generation across 5 trials x 60 perspectives = 300 calls
2. Sandboxed dynamic replay evaluation on development traces (dev_dyn_00, dev_dyn_01)
3. Selection and freezing of 5 trial champions into frozen_champions.json
4. Blind hidden evaluation on Days 3-4 dynamic traces and static windows
5. Baseline evaluations across all 8 frozen reference solvers
"""

import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
import random
import sys
import os
import threading
import time
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.abspath("."))

from experiment16.src.evaluator import PodSchedulingDynamicEvaluator
from experiment16.src.llm_client import CloudSchedulingLLMClient
from experiment16.src.prompts import PROMPT_PERSPECTIVES, get_prompt_for_perspective
from experiment16.src.simulator import simulate_dynamic_replay, simulate_static_packing


class Experiment16Runner:
    def __init__(
        self,
        config_path: str = "experiment16/config.json",
        seeds_path: str = "experiment16/seeds.json"
    ):
        with open(config_path) as f:
            self.config = json.load(f)
        with open(seeds_path) as f:
            self.seeds_data = json.load(f)

        self.num_trials = self.config.get("num_trials", 5)
        self.candidates_per_trial = self.config.get("candidates_per_trial", 60)
        self.max_concurrency = self.config.get("max_concurrency", 5)
        self.trial_seeds = self.seeds_data["trial_seeds"]

        self.benchmarks_cfg = self.config.get("benchmarks", {})
        self.dev_dynamic_path = self.benchmarks_cfg["dev_dynamic"]
        self.dev_static_path = self.benchmarks_cfg["dev_static"]
        self.val_dynamic_path = self.benchmarks_cfg["val_dynamic"]
        self.val_static_path = self.benchmarks_cfg["val_static"]
        self.hidden_dynamic_path = self.benchmarks_cfg["hidden_dynamic"]
        self.hidden_static_path = self.benchmarks_cfg["hidden_static"]

        with open(self.dev_dynamic_path) as f:
            self.dev_dynamic_traces = json.load(f)
        with open(self.dev_static_path) as f:
            self.dev_static_instances = json.load(f)[:5]  # 5 representative windows for fast static tracking

        self.llm_client = CloudSchedulingLLMClient(
            model=self.config.get("model", "nvidia/nvidia/nemotron-3-super-120b-a12b"),
            base_url=self.config.get("api_base_url", "http://127.0.0.1:20128/v1/chat/completions"),
            api_key=self.config.get("api_key") or os.environ.get("OMNIROUTE_API_KEY"),
            max_tokens=self.config.get("max_completion_tokens", 4096)
        )

        budget_cfg = self.config.get("computational_budget", {})
        self.evaluator = PodSchedulingDynamicEvaluator(
            scale_aware_base_ms=budget_cfg.get("scale_aware_timeout_base_ms", 2000.0),
            scale_aware_per_nm_ms=budget_cfg.get("scale_aware_timeout_per_nm_ms", 1.0),
            sigalrm_interrupt_sec=budget_cfg.get("sigalrm_interrupt_sec", 120)
        )

        self.candidates_log_path = "experiment16/candidates/candidates.jsonl"
        self.calls_log_path = "experiment16/logs/llm_calls.jsonl"
        self.frozen_champions_path = "experiment16/frozen/frozen_champions.json"
        self.results_path = "experiment16/results/evaluation_results.json"

        os.makedirs("experiment16/candidates", exist_ok=True)
        os.makedirs("experiment16/logs", exist_ok=True)
        os.makedirs("experiment16/frozen", exist_ok=True)
        os.makedirs("experiment16/results", exist_ok=True)

        self.log_lock = threading.Lock()
        self.completed_candidates: Dict[str, Dict[str, Any]] = self._load_existing_candidates()

    def _load_existing_candidates(self) -> Dict[str, Dict[str, Any]]:
        existing = {}
        if os.path.exists(self.candidates_log_path):
            with open(self.candidates_log_path) as f:
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

    def _log_candidate(self, record: Dict[str, Any]):
        with self.log_lock:
            with open(self.candidates_log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
            self.completed_candidates[record["candidate_id"]] = record

    def _log_llm_call(self, call_data: Dict[str, Any]):
        with self.log_lock:
            with open(self.calls_log_path, "a") as f:
                f.write(json.dumps(call_data) + "\n")

    def process_candidate(self, trial_idx: int, call_idx: int, perspective: Dict[str, Any]) -> Dict[str, Any]:
        cid = f"T{trial_idx:02d}_C{call_idx:02d}"
        if cid in self.completed_candidates:
            return self.completed_candidates[cid]

        prompt = get_prompt_for_perspective(perspective)
        llm_resp = self.llm_client.query(prompt=prompt, temperature=self.config.get("temperature", 0.6))

        call_record = {
            "candidate_id": cid,
            "trial": trial_idx,
            "call_index": call_idx,
            "perspective_id": perspective["id"],
            "perspective_name": perspective["name"],
            "perspective_category": perspective["category"],
            "prompt_hash": llm_resp["prompt_hash"],
            "finish_reason": llm_resp["finish_reason"],
            "is_truncated": llm_resp["is_truncated"],
            "latency_ms": llm_resp["latency_ms"],
            "code_hash": llm_resp["code_hash"],
            "success": llm_resp["success"],
            "error": llm_resp["error"],
            "usage": llm_resp.get("usage", {})
        }
        self._log_llm_call(call_record)

        if not llm_resp["success"] or not llm_resp["extracted_code"]:
            cand_record = {
                "candidate_id": cid,
                "trial": trial_idx,
                "call_index": call_idx,
                "perspective_id": perspective["id"],
                "perspective_name": perspective["name"],
                "perspective_category": perspective["category"],
                "code": "",
                "code_hash": "",
                "is_valid": False,
                "error": llm_resp.get("error") or "No code extracted",
                "dynamic_cost": float("inf"),
                "node_hours": float("inf"),
                "unscheduled": 999999,
                "feasibility": 0.0,
                "static_cost": float("inf"),
                "runtime_ms": 0.0
            }
            self._log_candidate(cand_record)
            return cand_record

        code = llm_resp["extracted_code"]
        eval_res = self.evaluator.evaluate_solver_code_dynamic(
            code_str=code,
            dynamic_traces=self.dev_dynamic_traces,
            static_instances=self.dev_static_instances
        )

        cand_record = {
            "candidate_id": cid,
            "trial": trial_idx,
            "call_index": call_idx,
            "perspective_id": perspective["id"],
            "perspective_name": perspective["name"],
            "perspective_category": perspective["category"],
            "code": code,
            "code_hash": llm_resp["code_hash"],
            "is_valid": eval_res["is_valid"],
            "error": eval_res.get("error"),
            "dynamic_cost": eval_res.get("total_cost", float("inf")),
            "node_hours": eval_res.get("node_hours", float("inf")),
            "unscheduled": eval_res.get("unscheduled_total", 999999),
            "feasibility": eval_res.get("placement_feasibility", 0.0),
            "static_cost": eval_res.get("static_cost", float("inf")),
            "runtime_ms": eval_res.get("runtime_ms", 0.0)
        }
        self._log_candidate(cand_record)
        return cand_record

    def run_discovery(self) -> Dict[str, Any]:
        """
        Executes candidate generation across all 5 trials x 60 perspectives.
        Selects and freezes 1 champion per trial.
        """
        print(f"\n=================================================================")
        print(f"Starting Discovery Loop: {self.num_trials} Trials x {self.candidates_per_trial} Calls = {self.num_trials * self.candidates_per_trial} Total Calls")
        print(f"=================================================================\n")

        tasks = []
        for t_idx in range(1, self.num_trials + 1):
            seed = self.trial_seeds[t_idx - 1]
            rng = random.Random(seed)
            # Deterministic permutation of the 60 perspectives
            perspectives_shuffled = list(PROMPT_PERSPECTIVES)
            rng.shuffle(perspectives_shuffled)

            for c_idx in range(1, self.candidates_per_trial + 1):
                persp = perspectives_shuffled[c_idx - 1]
                tasks.append((t_idx, c_idx, persp))

        print(f"Total tasks planned: {len(tasks)}. Existing completed: {len(self.completed_candidates)}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            future_to_task = {
                executor.submit(self.process_candidate, t, c, p): (t, c)
                for (t, c, p) in tasks
            }
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_task):
                t, c = future_to_task[future]
                completed_count += 1
                try:
                    res = future.result()
                    status_str = f"VALID (Cost=${res['dynamic_cost']:.2f})" if res['is_valid'] else f"INVALID ({res.get('error', '')[:30]})"
                    if completed_count % 10 == 0 or completed_count == len(tasks):
                        print(f"[{completed_count}/{len(tasks)}] Candidate T{t:02d}_C{c:02d}: {status_str}")
                except Exception as e:
                    print(f"[{completed_count}/{len(tasks)}] Candidate T{t:02d}_C{c:02d} FAILED with exception: {e}")

        # Champion Selection per Trial
        print("\nSelecting Trial Champions based on Dev Dynamic Cost...")
        champions: Dict[str, Any] = {}

        for t_idx in range(1, self.num_trials + 1):
            trial_cands = [
                c for c in self.completed_candidates.values()
                if c["trial"] == t_idx and c["is_valid"] and c["feasibility"] == 1.0
            ]
            if not trial_cands:
                print(f"WARNING: Trial {t_idx} had no 100% feasible candidates! Falling back to best available.")
                trial_cands = [c for c in self.completed_candidates.values() if c["trial"] == t_idx and c["is_valid"]]

            if trial_cands:
                best_cand = min(trial_cands, key=lambda c: c["dynamic_cost"])
                champions[f"Trial_{t_idx}"] = {
                    "candidate_id": best_cand["candidate_id"],
                    "trial": t_idx,
                    "perspective_id": best_cand["perspective_id"],
                    "perspective_name": best_cand["perspective_name"],
                    "perspective_category": best_cand["perspective_category"],
                    "code_hash": best_cand["code_hash"],
                    "dev_dynamic_cost": best_cand["dynamic_cost"],
                    "dev_node_hours": best_cand["node_hours"],
                    "dev_static_cost": best_cand["static_cost"],
                    "code": best_cand["code"]
                }
                print(f"Trial {t_idx} Champion: {best_cand['candidate_id']} ({best_cand['perspective_name']}) - Dev Dynamic Cost: ${best_cand['dynamic_cost']:.2f}")

        # Save champions
        with open(self.frozen_champions_path, "w") as f:
            json.dump(champions, f, indent=2)
        print(f"\nFrozen Champions saved to {self.frozen_champions_path}")
        return champions

    def evaluate_hidden(self):
        """
        Executes blind hidden evaluation of all frozen trial champions and baselines.
        """
        import importlib.util
        from experiment16.baselines.baselines import BASELINES
        from experiment16.analysis.analyze import analyze_results

        print("\n" + "=" * 75)
        print("AMAURA EXPERIMENT #16 — BLIND HIDDEN EVALUATION ENGINE")
        print("=" * 75)

        if not os.path.exists(self.frozen_champions_path):
            raise FileNotFoundError(f"Frozen champions file {self.frozen_champions_path} not found! Run discovery first.")

        with open(self.frozen_champions_path) as f:
            champions = json.load(f)

        # Load solvers
        solvers = {}

        # 1. Add Trial Champions
        for c_name, c_data in champions.items():
            code_str = c_data["code"]
            exec_globals: Dict[str, Any] = {}
            compiled = compile(code_str, f"<{c_name}>", "exec")
            exec(compiled, exec_globals)
            solvers[c_name] = {
                "name": f"Amaura Exp 16 {c_name} ({c_data['candidate_id']})",
                "select_node": exec_globals["select_node"],
                "select_pod": exec_globals.get("select_pod", None),
                "type": "discovered_dynamic_champion"
            }

        # 2. Add Historical Discovered Policies
        def load_pol(filepath):
            spec = importlib.util.spec_from_file_location("pol_mod", filepath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return getattr(mod, "select_node"), getattr(mod, "select_pod", None)

        pa_node, pa_pod = load_pol("experiment16/policies/policy_a_t4_c01.py")
        pb_node, pb_pod = load_pol("experiment16/policies/policy_b_n60_t4_c51.py")
        solvers["Policy_A_T4_C01"] = {"name": "Amaura Policy A (T4_C01 - Exp 13)", "select_node": pa_node, "select_pod": pa_pod, "type": "historical_static_champion"}
        solvers["Policy_B_N60_T4_C51"] = {"name": "Amaura Policy B (N60_T4_C51 - Exp 14)", "select_node": pb_node, "select_pod": pb_pod, "type": "historical_static_champion"}

        # 3. Add 6 Standard Baselines
        for k, v in BASELINES.items():
            solvers[k] = {"name": v["name"], "select_node": v["select_node"], "select_pod": v["select_pod"], "type": "baseline"}

        print(f"Loaded {len(solvers)} total solvers to evaluate: {list(solvers.keys())}")

        # Load hidden benchmarks
        with open(self.hidden_static_path) as f:
            hidden_static = json.load(f)
        with open(self.hidden_dynamic_path) as f:
            hidden_dynamic = json.load(f)

        print(f"Hidden Benchmarks Loaded: {len(hidden_static)} static windows, {len(hidden_dynamic)} dynamic traces.")

        # 1. Mode B Static Evaluation
        print("\n[1/2] Evaluating Mode B Static Benchmarks (55 windows)...")
        static_results = {s_id: {"instance_results": [], "total_cost": 0.0, "total_active_nodes": 0, "total_unscheduled": 0, "total_runtime_ms": 0.0} for s_id in solvers}
        for idx, inst in enumerate(hidden_static):
            inst_id = inst["instance_id"]
            if idx % 15 == 0 or idx == len(hidden_static) - 1:
                print(f"    Static window [{idx+1}/{len(hidden_static)}] {inst_id} ({len(inst['pods'])} pods)...", flush=True)
            for s_id, s_info in solvers.items():
                res = simulate_static_packing(inst, s_info["select_node"], s_info["select_pod"])
                static_results[s_id]["instance_results"].append({
                    "instance_id": inst_id,
                    "regime": inst.get("regime", "unknown"),
                    "pod_count": inst.get("pod_count", len(inst["pods"])),
                    "total_cost": res["total_cost"],
                    "active_nodes": res["active_nodes_count"],
                    "unscheduled": res["unscheduled_count"],
                    "imbalance": res["mean_active_imbalance"],
                    "runtime_ms": res["runtime_ms"]
                })
                static_results[s_id]["total_cost"] += res["total_cost"]
                static_results[s_id]["total_active_nodes"] += res["active_nodes_count"]
                static_results[s_id]["total_unscheduled"] += res["unscheduled_count"]
                static_results[s_id]["total_runtime_ms"] += res["runtime_ms"]

        n_stat = len(hidden_static)
        for s_id in solvers:
            static_results[s_id]["mean_cost"] = round(static_results[s_id]["total_cost"] / n_stat, 4) if n_stat > 0 else 0.0
            static_results[s_id]["mean_active_nodes"] = round(static_results[s_id]["total_active_nodes"] / n_stat, 2) if n_stat > 0 else 0.0
            static_results[s_id]["total_cost"] = round(static_results[s_id]["total_cost"], 4)
            static_results[s_id]["mean_runtime_ms"] = round(static_results[s_id]["total_runtime_ms"] / n_stat, 3) if n_stat > 0 else 0.0

        # 2. Mode A Dynamic Evaluation
        print("\n[2/2] Evaluating Mode A Dynamic Benchmarks (10 traces, 40 hours)...")
        dynamic_results = {s_id: {"trace_results": [], "total_cost": 0.0, "total_node_hours": 0.0, "peak_active_nodes": 0, "total_unscheduled": 0, "total_runtime_ms": 0.0} for s_id in solvers}
        for idx, tr in enumerate(hidden_dynamic):
            tr_id = tr["trace_id"]
            print(f"    Dynamic trace [{idx+1}/{len(hidden_dynamic)}] {tr_id} ({len(tr['events'])} events, {len(tr['nodes'])} nodes)...", flush=True)
            for s_id, s_info in solvers.items():
                t0 = time.perf_counter()
                res = simulate_dynamic_replay(tr, s_info["select_node"], s_info["select_pod"])
                el_ms = (time.perf_counter() - t0) * 1000.0
                dynamic_results[s_id]["trace_results"].append({
                    "trace_id": tr_id,
                    "pod_count": tr.get("pod_count", len(tr["events"])),
                    "total_cost": res["total_cost"],
                    "infrastructure_cost": res["infrastructure_cost"],
                    "node_hours": res["node_hours"],
                    "avg_active_nodes": res["avg_active_nodes"],
                    "peak_active_nodes": res["peak_active_nodes"],
                    "unscheduled": res["unscheduled_count"],
                    "runtime_ms": round(el_ms, 2)
                })
                dynamic_results[s_id]["total_cost"] += res["total_cost"]
                dynamic_results[s_id]["total_node_hours"] += res["node_hours"]
                dynamic_results[s_id]["peak_active_nodes"] = max(dynamic_results[s_id]["peak_active_nodes"], res["peak_active_nodes"])
                dynamic_results[s_id]["total_unscheduled"] += res["unscheduled_count"]
                dynamic_results[s_id]["total_runtime_ms"] += el_ms

        n_dyn = len(hidden_dynamic)
        for s_id in solvers:
            dynamic_results[s_id]["mean_cost"] = round(dynamic_results[s_id]["total_cost"] / n_dyn, 4) if n_dyn > 0 else 0.0
            dynamic_results[s_id]["mean_node_hours"] = round(dynamic_results[s_id]["total_node_hours"] / n_dyn, 2) if n_dyn > 0 else 0.0
            dynamic_results[s_id]["total_cost"] = round(dynamic_results[s_id]["total_cost"], 4)
            dynamic_results[s_id]["total_node_hours"] = round(dynamic_results[s_id]["total_node_hours"], 4)
            dynamic_results[s_id]["mean_runtime_ms"] = round(dynamic_results[s_id]["total_runtime_ms"] / n_dyn, 3) if n_dyn > 0 else 0.0

        full_output = {
            "metadata": {
                "experiment_id": "Amaura_Experiment_16",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_solvers": len(solvers),
                "solvers": list(solvers.keys())
            },
            "mode_b_static": {"hidden": static_results},
            "mode_a_dynamic": {"hidden": dynamic_results}
        }

        with open(self.results_path, "w") as f:
            json.dump(full_output, f, indent=2)
        print(f"\nFull Hidden Evaluation Results saved to {self.results_path}")

        # Run automated analysis
        analyze_results()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amaura Experiment 16 Discovery Runner")
    parser.add_argument("--run-discovery", action="store_true", help="Run full candidate discovery loop")
    parser.add_argument("--evaluate-hidden", action="store_true", help="Execute blind hidden evaluation on Days 3-4")
    args = parser.parse_args()

    runner = Experiment16Runner()
    if args.run_discovery:
        runner.run_discovery()
    elif args.evaluate_hidden:
        runner.evaluate_hidden()
    else:
        print("Experiment 16 Runner initialized. Use --run-discovery to start candidate generation or --evaluate-hidden for blind evaluation.")
