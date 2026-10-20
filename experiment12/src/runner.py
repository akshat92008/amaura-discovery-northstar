"""
Experiment #12 Runner: Targeted Refinement vs Independent Best-of-N
===================================================================
Protocol:
- 5 Independent Replications (Seeds: 10101, 20202, 30303, 40404, 50505)
- 2 Primary Experimental Conditions:
    - Condition A: Independent Best-of-N (15 unguided, memoryless calls per trial)
    - Condition R: Targeted Refinement (10 independent generation calls + 5 targeted refinement calls from frozen parent)
- Strict Budget Parity: 5 trials * 2 conditions * 15 calls = 150 total LLM calls
- Calibrated scale-aware timeout: T(n, m) = 1000.0 + 2.0 * (n * m) ms
- Provenance tracking in experiment12/logs/llm_calls.jsonl
- Candidate tracking in experiment12/candidates/candidates.jsonl
- Frozen champions -> experiment12/results/frozen_champions.json
- Blind Hidden Evaluation (120 instances) -> experiment12/results/hidden_evaluations.json
"""

import copy
import hashlib
import json
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

from experiment12.src.evaluator import PFSPEvaluator
from experiment12.src.llm_client import PFSPLLMClient
from experiment12.src.prompts import (
    get_condition_a_prompt,
    get_condition_r_generation_prompt,
    get_condition_r_refinement_prompt,
    REFINEMENT_OBJECTIVES,
)


class Experiment12Runner:
    def __init__(
        self,
        config_path: str = "experiment12/config.json",
        seeds_path: str = "experiment12/seeds.json",
        dev_bench_path: str = "experiment12/benchmarks/dev.json",
        hidden_bench_path: str = "experiment12/benchmarks/hidden.json",
        logs_path: str = "experiment12/logs/llm_calls.jsonl",
        candidates_path: str = "experiment12/candidates/candidates.jsonl",
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

        self.llm_client = PFSPLLMClient(
            model=self.config.get("model", "nvidia/nvidia/nemotron-3-super-120b-a12b"),
            base_url=self.config.get("api_base_url", "http://127.0.0.1:20128/v1/chat/completions"),
            api_key=self.config.get("api_key") or os.environ.get("OMNIROUTE_API_KEY"),
            max_tokens=self.config.get("max_completion_tokens", 4096)
        )

        budget_cfg = self.config.get("computational_budget", {})
        self.evaluator = PFSPEvaluator(
            scale_aware_base_ms=budget_cfg.get("scale_aware_timeout_base_ms", 1000.0),
            scale_aware_per_nm_ms=budget_cfg.get("scale_aware_timeout_per_nm_ms", 2.0),
            sigalrm_interrupt_sec=budget_cfg.get("sigalrm_interrupt_sec", 10)
        )

        os.makedirs(os.path.dirname(self.logs_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.candidates_path), exist_ok=True)
        os.makedirs("experiment12/results", exist_ok=True)

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
        condition: str,
        call_idx: int,
        prompt: str,
        phase: str = "generation",
        parent_id: Optional[str] = None,
        parent_score: Optional[int] = None,
        refinement_objective: Optional[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        cid = f"T{trial_idx+1}_{condition}_C{call_idx+1:02d}"

        if cid in self.completed_candidates:
            print(f"[{cid}] Reusing cached candidate record (Makespan: {self.completed_candidates[cid]['development_score']})")
            return self.completed_candidates[cid]

        print(f"[{cid}] Querying {self.config.get('model')} (Cond {condition}, Call {call_idx+1}/15, Phase: {phase})...", flush=True)
        llm_res = self.llm_client.query(prompt=prompt, temperature=self.config["temperature"])

        call_log = {
            "call_id": cid,
            "trial_idx": trial_idx,
            "condition": condition,
            "call_idx": call_idx,
            "phase": phase,
            "parent_id": parent_id,
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
            "error": llm_res["error"],
            "notes": notes
        }
        self._log_llm_call(call_log)

        if llm_res["success"] and llm_res["code"]:
            code = llm_res["code"]
            eval_res = self.evaluator.evaluate_solver_code(code, self.dev_instances)
        else:
            code = ""
            eval_res = {
                "is_valid": False,
                "total_makespan": 999999,
                "mean_makespan": 999999.0,
                "instance_makespans": [],
                "behavior_signature": [],
                "runtime_ms": 0.0,
                "error": llm_res["error"] or "No code synthesized"
            }

        dev_score = eval_res["total_makespan"]
        delta_from_parent = (dev_score - parent_score) if (parent_score is not None and dev_score < 999999) else None

        candidate_record = {
            "candidate_id": cid,
            "trial_idx": trial_idx,
            "condition": condition,
            "call_idx": call_idx,
            "phase": phase,
            "parent_id": parent_id,
            "parent_score": parent_score,
            "refined_score": dev_score if phase == "refinement" else None,
            "delta_from_parent": delta_from_parent,
            "refinement_objective": refinement_objective,
            "timestamp": time.time(),
            "code": code,
            "code_chars": len(code),
            "validity": eval_res["is_valid"],
            "development_score": dev_score,
            "mean_makespan": eval_res["mean_makespan"],
            "instance_makespans": eval_res["instance_makespans"],
            "behavior_signature": eval_res["behavior_signature"],
            "runtime_ms": eval_res["runtime_ms"],
            "eval_error": eval_res["error"],
            "prompt_tokens": llm_res["prompt_tokens"],
            "completion_tokens": llm_res["completion_tokens"],
            "total_tokens": llm_res["total_tokens"],
            "is_truncated": llm_res["is_truncated"],
            "call_duration_ms": llm_res["duration_ms"],
            "notes": notes
        }
        self._log_candidate(candidate_record)

        status_str = "VALID" if eval_res["is_valid"] else "INVALID"
        delta_str = f" | Delta vs Parent: {delta_from_parent:+d}" if delta_from_parent is not None else ""
        print(f"[{cid}] Result: {status_str} | Dev Makespan: {dev_score}{delta_str} | Eval Runtime: {eval_res['runtime_ms']:.1f}ms | Tokens: {llm_res['completion_tokens']}")
        return candidate_record

    # -------------------------------------------------------------
    # Condition A: Independent Search (15 memoryless calls)
    # -------------------------------------------------------------
    def run_condition_a_trial(self, trial_idx: int, num_calls: int = 15) -> Dict[str, Any]:
        print(f"\n==========================================")
        print(f"STARTING CONDITION A — TRIAL {trial_idx+1}/5")
        print(f"==========================================")
        candidates = []
        for call_idx in range(num_calls):
            prompt = get_condition_a_prompt(call_idx)
            cand = self.run_call(
                trial_idx=trial_idx,
                condition="A",
                call_idx=call_idx,
                prompt=prompt,
                phase="generation",
                parent_id=None,
                notes=f"Angle_{call_idx+1}"
            )
            candidates.append(cand)

        valid_cands = [c for c in candidates if c["validity"] and c["development_score"] < 999999]
        if valid_cands:
            champ = min(valid_cands, key=lambda c: c["development_score"])
        else:
            champ = candidates[0]

        print(f"[CONDITION A — TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} | Dev Makespan: {champ['development_score']}")
        return champ

    # -------------------------------------------------------------
    # Condition R: Targeted Refinement (10 Generation + 5 Refinement)
    # -------------------------------------------------------------
    def run_condition_r_trial(
        self,
        trial_idx: int,
        num_gen_calls: int = 10,
        num_ref_calls: int = 5
    ) -> Dict[str, Any]:
        print(f"\n==========================================")
        print(f"STARTING CONDITION R — TRIAL {trial_idx+1}/5")
        print(f"==========================================")
        gen_candidates: List[Dict[str, Any]] = []

        # Phase 1: Generation Phase (Calls 0 to num_gen_calls - 1)
        print(f"--- Condition R Phase 1: Generation ({num_gen_calls} independent calls) ---")
        for call_idx in range(num_gen_calls):
            prompt = get_condition_r_generation_prompt(call_idx)
            cand = self.run_call(
                trial_idx=trial_idx,
                condition="R",
                call_idx=call_idx,
                prompt=prompt,
                phase="generation",
                parent_id=None,
                notes=f"R_Gen_Angle_{call_idx+1}"
            )
            gen_candidates.append(cand)

        # Select the single best valid generation candidate as PARENT
        valid_gen = [c for c in gen_candidates if c["validity"] and c["development_score"] < 999999]
        if valid_gen:
            parent = min(valid_gen, key=lambda c: c["development_score"])
        else:
            parent = gen_candidates[0]

        parent_hash = hashlib.sha256(parent["code"].encode("utf-8")).hexdigest()
        print(f"\n>>> [CONDITION R PARENT SELECTED] Candidate: {parent['candidate_id']} | Dev Makespan: {parent['development_score']} | Hash: {parent_hash[:12]} <<<")

        # Phase 2: Refinement Phase (num_ref_calls targeted refinement calls from FROZEN parent)
        print(f"\n--- Condition R Phase 2: Refinement ({num_ref_calls} targeted refinement calls from parent {parent['candidate_id']}) ---")
        ref_candidates: List[Dict[str, Any]] = []
        for ref_idx in range(num_ref_calls):
            call_idx = num_gen_calls + ref_idx
            prompt = get_condition_r_refinement_prompt(parent, ref_idx)
            ref_spec = REFINEMENT_OBJECTIVES[ref_idx % len(REFINEMENT_OBJECTIVES)]
            cand = self.run_call(
                trial_idx=trial_idx,
                condition="R",
                call_idx=call_idx,
                prompt=prompt,
                phase="refinement",
                parent_id=parent["candidate_id"],
                parent_score=parent["development_score"],
                refinement_objective=ref_spec["name"],
                notes=f"R_Ref_{ref_idx+1}_{ref_spec['name']}"
            )
            ref_candidates.append(cand)

        # Final Condition R Champion: Best valid candidate among ALL calls (generation + refinement)
        all_r_cands = gen_candidates + ref_candidates
        valid_all = [c for c in all_r_cands if c["validity"] and c["development_score"] < 999999]
        if valid_all:
            champ = min(valid_all, key=lambda c: c["development_score"])
        else:
            champ = parent

        valid_refs = [c for c in ref_candidates if c["validity"] and c["development_score"] < 999999]
        best_ref = min(valid_refs, key=lambda c: c["development_score"]) if valid_refs else None

        champ["trial_metadata_r"] = {
            "parent_id": parent["candidate_id"],
            "parent_score": parent["development_score"],
            "best_generation_id": parent["candidate_id"],
            "best_generation_score": parent["development_score"],
            "best_refinement_id": best_ref["candidate_id"] if best_ref else None,
            "best_refinement_score": best_ref["development_score"] if best_ref else None,
            "champion_source": "refinement" if (best_ref and champ["candidate_id"] == best_ref["candidate_id"]) else "generation",
            "refinement_improved_over_parent": (best_ref is not None and best_ref["development_score"] < parent["development_score"])
        }

        print(f"[CONDITION R — TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} | Dev Makespan: {champ['development_score']} | Source: {champ['trial_metadata_r']['champion_source']}")
        return champ

    # -------------------------------------------------------------
    # Full Execution Loop Across All 5 Trials
    # -------------------------------------------------------------
    def run_all_trials(
        self,
        num_trials: int = 5,
        calls_a: int = 15,
        gen_r: int = 10,
        ref_r: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        trial_seeds = self.seeds_data["trial_seeds"]

        champions: Dict[str, List[Dict[str, Any]]] = {
            "A": [],
            "R": []
        }

        start_time_all = time.perf_counter()
        print("============================================================")
        print("LAUNCHING AMAURA EXPERIMENT #12: TARGETED REFINEMENT VS BEST-OF-N")
        print(f"Model: {self.config['model']} | Max Tokens: {self.config['max_completion_tokens']}")
        print(f"Trials: {num_trials} | Total Calls: {num_trials * (calls_a + gen_r + ref_r)}")
        print("============================================================")

        for trial_idx in range(num_trials):
            seed = trial_seeds[trial_idx]
            random.seed(seed)
            print(f"\n>>> EXECUTING REPLICATION TRIAL {trial_idx+1}/{num_trials} (Seed: {seed}) <<<")

            champ_a = self.run_condition_a_trial(trial_idx, num_calls=calls_a)
            champions["A"].append(champ_a)

            champ_r = self.run_condition_r_trial(trial_idx, num_gen_calls=gen_r, num_ref_calls=ref_r)
            champions["R"].append(champ_r)

        total_min = (time.perf_counter() - start_time_all) / 60.0
        print("\n============================================================")
        print(f"SEARCH PHASE COMPLETE! Total time: {total_min:.1f} minutes")
        print("============================================================")

        self._freeze_champions(champions)
        return champions

    def _freeze_champions(self, champions: Dict[str, List[Dict[str, Any]]]):
        frozen_data = {
            "metadata": {
                "experiment": "Amaura Experiment #12: Targeted Refinement vs Independent Best-of-N",
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": self.config["model"],
                "trials": len(champions["A"]),
                "total_champions": sum(len(v) for v in champions.values())
            },
            "champions": {}
        }

        for cond, champ_list in champions.items():
            frozen_data["champions"][cond] = []
            for champ in champ_list:
                code_sha = hashlib.sha256(champ["code"].encode("utf-8")).hexdigest()
                rec = {
                    "candidate_id": champ["candidate_id"],
                    "trial_idx": champ["trial_idx"],
                    "condition": champ["condition"],
                    "call_idx": champ["call_idx"],
                    "phase": champ.get("phase", "generation"),
                    "development_score": champ["development_score"],
                    "mean_makespan": champ["mean_makespan"],
                    "runtime_ms": champ["runtime_ms"],
                    "validity": champ["validity"],
                    "code_sha256": code_sha,
                    "code": champ["code"]
                }
                if "trial_metadata_r" in champ:
                    rec["trial_metadata_r"] = champ["trial_metadata_r"]
                frozen_data["champions"][cond].append(rec)

        out_path = "experiment12/results/frozen_champions.json"
        with open(out_path, "w") as f:
            json.dump(frozen_data, f, indent=2)
        print(f"\nSuccessfully froze all champions -> {out_path}")

    # -------------------------------------------------------------
    # Blind Hidden Benchmark Evaluation
    # -------------------------------------------------------------
    def evaluate_frozen_champions_on_hidden(self):
        print(f"\n============================================================")
        print(f"EVALUATING FROZEN CHAMPIONS ON HIDDEN BENCHMARK (120 INSTANCES)")
        print(f"============================================================")
        frozen_path = "experiment12/results/frozen_champions.json"
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
            for champ in champ_list:
                cid = champ["candidate_id"]
                code = champ["code"]
                print(f"Evaluating {cid} on 120 hidden instances...", flush=True)
                res = self.evaluator.evaluate_solver_code(code, hidden_instances, extract_behavior=False)
                eval_record = {
                    "candidate_id": cid,
                    "condition": cond,
                    "trial_idx": champ["trial_idx"],
                    "validity": res["is_valid"],
                    "hidden_total_makespan": res["total_makespan"],
                    "hidden_mean_makespan": res["mean_makespan"],
                    "instance_makespans": res["instance_makespans"],
                    "runtime_ms": res["runtime_ms"],
                    "error": res["error"]
                }
                if "trial_metadata_r" in champ:
                    eval_record["trial_metadata_r"] = champ["trial_metadata_r"]
                hidden_results["evaluations"][cond].append(eval_record)
                status_str = "VALID" if res["is_valid"] else "INVALID"
                print(f"   [{cid}] Hidden Total Makespan: {res['total_makespan']} | Mean: {res['mean_makespan']:.2f} | Status: {status_str} | Runtime: {res['runtime_ms']:.1f}ms")

        out_path = "experiment12/results/hidden_evaluations.json"
        with open(out_path, "w") as f:
            json.dump(hidden_results, f, indent=2)
        print(f"\nHidden evaluations completed and saved -> {out_path}")


if __name__ == "__main__":
    runner = Experiment12Runner()
    champions = runner.run_all_trials()
    runner.evaluate_frozen_champions_on_hidden()
    print("\nALL EXPERIMENT #12 RUNS AND EVALUATIONS COMPLETED!")
