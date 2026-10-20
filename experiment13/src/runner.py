"""
Experiment #13 Runner: Cross-Domain Generality Test
===================================================
Domain: Kubernetes-Style Cloud Pod Scheduling Simulation

Protocol:
- 5 Independent Replications (Seeds: 10101, 20202, 30303, 40404, 50505)
- Frozen Discovery Architecture: Pure Independent Best-of-N (15 calls per trial)
- Strict Parity: 5 trials * 15 calls = 75 total LLM calls
- Model: nvidia/nvidia/nemotron-3-super-120b-a12b via OmniRoute
- Scale-aware timeout: T(n_pods, m_nodes) = 1000.0 + 1.0 * (n_pods * m_nodes) ms
- Provenance tracking in experiment13/logs/llm_calls.jsonl
- Candidate tracking in experiment13/candidates/candidates.jsonl
- Frozen champions -> experiment13/results/frozen_champions.json
- Blind Hidden Evaluation (120 instances) -> experiment13/results/hidden_evaluations.json
"""

import copy
import hashlib
import json
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional

from experiment13.src.evaluator import PodSchedulingEvaluator
from experiment13.src.llm_client import CloudSchedulingLLMClient
from experiment13.src.prompts import get_prompt_for_angle, PROMPT_PERSPECTIVES


class Experiment13Runner:
    def __init__(
        self,
        config_path: str = "experiment13/config.json",
        seeds_path: str = "experiment13/seeds.json",
        dev_bench_path: str = "experiment13/benchmarks/dev.json",
        hidden_bench_path: str = "experiment13/benchmarks/hidden.json",
        logs_path: str = "experiment13/logs/llm_calls.jsonl",
        candidates_path: str = "experiment13/candidates/candidates.jsonl"
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
        os.makedirs("experiment13/results", exist_ok=True)

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
        with open(self.logs_path, "a") as f:
            f.write(json.dumps(call_data) + "\n")

    def _log_candidate(self, candidate_data: Dict[str, Any]):
        with open(self.candidates_path, "a") as f:
            f.write(json.dumps(candidate_data) + "\n")

    def run_call(
        self,
        trial_idx: int,
        call_idx: int,
        prompt: str,
        angle_name: str
    ) -> Dict[str, Any]:
        cid = f"T{trial_idx+1}_C{call_idx+1:02d}"

        if cid in self.completed_candidates:
            print(f"[{cid}] Reusing cached candidate record (Cost: {self.completed_candidates[cid]['development_cost']:.2f})")
            return self.completed_candidates[cid]

        print(f"[{cid}] Querying {self.config.get('model')} (Trial {trial_idx+1}/5, Call {call_idx+1}/15: {angle_name})...", flush=True)
        llm_res = self.llm_client.query(prompt=prompt, temperature=self.config["temperature"])

        call_log = {
            "call_id": cid,
            "trial_idx": trial_idx,
            "call_idx": call_idx,
            "angle_name": angle_name,
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

        dev_cost = eval_res["total_cost"]

        candidate_record = {
            "candidate_id": cid,
            "trial_idx": trial_idx,
            "call_idx": call_idx,
            "angle_name": angle_name,
            "timestamp": time.time(),
            "code": code,
            "code_chars": len(code),
            "validity": eval_res["is_valid"],
            "development_cost": dev_cost,
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
        print(f"[{cid}] Result: {status_str} | Dev Total Cost: {dev_cost:8.2f} (Active Nodes: {eval_res['active_nodes_mean']:4.1f}, Unscheduled: {eval_res['unscheduled_total']}) | Eval Runtime: {eval_res['runtime_ms']:.1f}ms | Tokens: {llm_res['completion_tokens']}")
        return candidate_record

    def run_trial(self, trial_idx: int, num_calls: int = 15) -> Dict[str, Any]:
        print(f"\n==========================================")
        print(f"STARTING REPLICATION TRIAL {trial_idx+1}/5")
        print(f"==========================================")
        candidates = []

        for call_idx in range(num_calls):
            prompt = get_prompt_for_angle(call_idx)
            angle_name = PROMPT_PERSPECTIVES[call_idx % len(PROMPT_PERSPECTIVES)]["name"]
            cand = self.run_call(
                trial_idx=trial_idx,
                call_idx=call_idx,
                prompt=prompt,
                angle_name=angle_name
            )
            candidates.append(cand)

        # Select best valid candidate on development benchmark
        valid_cands = [c for c in candidates if c["validity"] and c["development_cost"] < 999999.0]
        if valid_cands:
            champ = min(valid_cands, key=lambda c: c["development_cost"])
        else:
            champ = candidates[0]

        print(f"[TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} ({champ['angle_name']}) | Dev Cost: {champ['development_cost']:.2f} | Active Nodes: {champ['active_nodes_mean']:.1f}")
        return champ

    def run_all_trials(self, num_trials: int = 5, calls_per_trial: int = 15) -> List[Dict[str, Any]]:
        trial_seeds = self.seeds_data["trial_seeds"]
        champions = []

        t0_all = time.perf_counter()
        print("============================================================")
        print("LAUNCHING AMAURA EXPERIMENT #13: CROSS-DOMAIN GENERALITY")
        print(f"Domain: Kubernetes Cloud Pod Scheduling | Model: {self.config['model']}")
        print(f"Trials: {num_trials} | Calls/Trial: {calls_per_trial} | Total Calls: {num_trials * calls_per_trial}")
        print("============================================================")

        for trial_idx in range(num_trials):
            seed = trial_seeds[trial_idx]
            random.seed(seed)
            print(f"\n>>> EXECUTING REPLICATION TRIAL {trial_idx+1}/{num_trials} (Seed: {seed}) <<<")
            champ = self.run_trial(trial_idx, num_calls=calls_per_trial)
            champions.append(champ)

        total_min = (time.perf_counter() - t0_all) / 60.0
        print("\n============================================================")
        print(f"SEARCH PHASE COMPLETE! Total time: {total_min:.1f} minutes")
        print("============================================================")

        self._freeze_champions(champions)
        return champions

    def _freeze_champions(self, champions: List[Dict[str, Any]]):
        frozen_data = {
            "metadata": {
                "experiment": "Amaura Experiment #13: Cross-Domain Generality Test (Cloud Pod Scheduling)",
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": self.config["model"],
                "trials": len(champions),
                "calls_per_trial": self.config["calls_per_trial"]
            },
            "champions": []
        }

        for champ in champions:
            code_sha = hashlib.sha256(champ["code"].encode("utf-8")).hexdigest()
            frozen_data["champions"].append({
                "candidate_id": champ["candidate_id"],
                "trial_idx": champ["trial_idx"],
                "call_idx": champ["call_idx"],
                "angle_name": champ["angle_name"],
                "development_cost": champ["development_cost"],
                "mean_cost": champ["mean_cost"],
                "active_nodes_mean": champ["active_nodes_mean"],
                "unscheduled_total": champ["unscheduled_total"],
                "runtime_ms": champ["runtime_ms"],
                "validity": champ["validity"],
                "code_sha256": code_sha,
                "code": champ["code"]
            })

        out_path = "experiment13/results/frozen_champions.json"
        with open(out_path, "w") as f:
            json.dump(frozen_data, f, indent=2)
        print(f"\nSuccessfully froze all 5 champions -> {out_path}")

    def evaluate_frozen_champions_on_hidden(self):
        print(f"\n============================================================")
        print(f"EVALUATING FROZEN CHAMPIONS ON HIDDEN BENCHMARK (120 INSTANCES)")
        print(f"============================================================")
        frozen_path = "experiment13/results/frozen_champions.json"
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
            "evaluations": []
        }

        for champ in frozen_data["champions"]:
            cid = champ["candidate_id"]
            code = champ["code"]
            print(f"Evaluating {cid} ({champ['angle_name']}) on 120 hidden instances...", flush=True)

            res = self.evaluator.evaluate_solver_code(code, hidden_instances)
            eval_record = {
                "candidate_id": cid,
                "trial_idx": champ["trial_idx"],
                "angle_name": champ["angle_name"],
                "validity": res["is_valid"],
                "hidden_total_cost": res["total_cost"],
                "hidden_mean_cost": res["mean_cost"],
                "instance_costs": res["instance_costs"],
                "active_nodes_mean": res["active_nodes_mean"],
                "unscheduled_total": res["unscheduled_total"],
                "runtime_ms": res["runtime_ms"],
                "error": res["error"]
            }
            hidden_results["evaluations"].append(eval_record)
            status_str = "VALID" if res["is_valid"] else "INVALID"
            print(f"   [{cid}] Hidden Total Cost: {res['total_cost']:.2f} | Mean: {res['mean_cost']:.2f} | Active Nodes: {res['active_nodes_mean']:.1f} | Unscheduled: {res['unscheduled_total']} | Runtime: {res['runtime_ms']:.1f}ms | Status: {status_str}")

        out_path = "experiment13/results/hidden_evaluations.json"
        with open(out_path, "w") as f:
            json.dump(hidden_results, f, indent=2)
        print(f"\nHidden evaluations completed and saved -> {out_path}")


if __name__ == "__main__":
    runner = Experiment13Runner()
    champions = runner.run_all_trials()
    runner.evaluate_frozen_champions_on_hidden()
    print("\nALL EXPERIMENT #13 RUNS AND EVALUATIONS COMPLETED!")
