"""
Experiment #9: Complete Experiment Orchestrator and Search Runner
================================================================
Orchestrates:
- 5 Independent Replications (Seeds: 10101, 20202, 30303, 40404, 50505)
- 3 Search Conditions:
    - Condition A: Independent Search (15 unguided, memoryless calls)
    - Condition B: Naive Evolution (5 init + 5 gens x 2 offspring = 15 calls)
    - Condition C: Behavioral Quality-Diversity (QD Archive, delta_min=0.20, max_size=10, 15 calls)
- Total LLM Calls: 5 * 3 * 15 = 225 calls
- Strict provenance tracking in experiment9/logs/llm_calls.jsonl
- Candidate evaluation tracking in experiment9/candidates/candidates.jsonl
- Freezing of all 15 champions -> experiment9/results/frozen_champions.json
- Blind Hidden Benchmark Evaluation (120 instances) -> experiment9/results/hidden_evaluations.json
"""

import copy
import hashlib
import json
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

from experiment9.src.archive import QDArchive
from experiment9.src.evaluator import PFSPEvaluator
from experiment9.src.kendall import mean_behavioral_distance
from experiment9.src.llm_client import PFSPLLMClient
from experiment9.src.prompts import (
    get_condition_a_prompt,
    get_condition_b_refine_prompt,
    get_condition_b_crossover_prompt,
    get_condition_c_novelty_prompt,
    get_condition_c_bridge_prompt,
)


class ExperimentRunner:
    def __init__(
        self,
        config_path: str = "experiment9/config.json",
        seeds_path: str = "experiment9/seeds.json",
        dev_bench_path: str = "experiment9/benchmarks/dev.json",
        hidden_bench_path: str = "experiment9/benchmarks/hidden.json",
        logs_path: str = "experiment9/logs/llm_calls.jsonl",
        candidates_path: str = "experiment9/candidates/candidates.jsonl",
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

        self.hidden_instances = None  # Loaded strictly during hidden eval phase

        self.llm_client = PFSPLLMClient(
            model=self.config.get("model", "antigravity/claude-sonnet-4-6"),
            base_url=self.config.get("api_base_url", "http://127.0.0.1:20128/v1/chat/completions"),
            api_key=self.config.get("api_key") or os.environ.get("OMNIROUTE_API_KEY")
        )

        self.evaluator = PFSPEvaluator()

        os.makedirs(os.path.dirname(self.logs_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.candidates_path), exist_ok=True)
        os.makedirs("experiment9/results", exist_ok=True)

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

    def _log_llm_call(self, record: Dict[str, Any]):
        with open(self.logs_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def _log_candidate(self, record: Dict[str, Any]):
        self.completed_candidates[record["candidate_id"]] = record
        with open(self.candidates_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def run_call(
        self,
        trial_idx: int,
        condition: str,
        call_idx: int,
        prompt: str,
        parent_ids: Optional[List[str]] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Executes a single LLM call, evaluates the resulting code on the dev set,
        logs the call and candidate, and returns the candidate record.
        """
        cid = f"T{trial_idx+1}_{condition}_C{call_idx+1:02d}"

        # Check if already completed from previous run
        if cid in self.completed_candidates:
            print(f"[{cid}] Reusing cached candidate record (Makespan: {self.completed_candidates[cid]['development_score']})")
            return self.completed_candidates[cid]

        print(f"[{cid}] Querying LLM (Condition {condition}, Call {call_idx+1}/15)...", flush=True)
        llm_res = self.llm_client.query(prompt=prompt, temperature=self.config["temperature"])

        # Log LLM call provenance
        call_log = {
            "call_id": cid,
            "trial_idx": trial_idx,
            "condition": condition,
            "call_idx": call_idx,
            "timestamp": time.time(),
            "model": llm_res["model"],
            "prompt_hash": llm_res["prompt_hash"],
            "response_hash": llm_res["response_hash"],
            "candidate_hash": llm_res["candidate_hash"],
            "prompt_tokens": llm_res["prompt_tokens"],
            "completion_tokens": llm_res["completion_tokens"],
            "total_tokens": llm_res["total_tokens"],
            "duration_ms": llm_res["duration_ms"],
            "success": llm_res["success"],
            "error": llm_res["error"],
            "notes": notes
        }
        self._log_llm_call(call_log)

        # Evaluate candidate code
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

        candidate_record = {
            "candidate_id": cid,
            "trial_idx": trial_idx,
            "condition": condition,
            "call_idx": call_idx,
            "timestamp": time.time(),
            "code": code,
            "validity": eval_res["is_valid"],
            "development_score": eval_res["total_makespan"],
            "mean_makespan": eval_res["mean_makespan"],
            "instance_makespans": eval_res["instance_makespans"],
            "behavior_signature": eval_res["behavior_signature"],
            "runtime_ms": eval_res["runtime_ms"],
            "eval_error": eval_res["error"],
            "parent_ids": parent_ids or [],
            "tokens": llm_res["total_tokens"],
            "call_duration_ms": llm_res["duration_ms"],
            "notes": notes
        }
        self._log_candidate(candidate_record)

        status_str = "VALID" if eval_res["is_valid"] else "INVALID"
        print(f"[{cid}] Result: {status_str} | Dev Makespan: {eval_res['total_makespan']} | Eval Runtime: {eval_res['runtime_ms']:.1f}ms | Tokens: {llm_res['total_tokens']}")
        return candidate_record

    # -------------------------------------------------------------
    # Condition A: Independent Search (15 memoryless calls)
    # -------------------------------------------------------------
    def run_condition_a_trial(self, trial_idx: int) -> Dict[str, Any]:
        print(f"\n==========================================")
        print(f"STARTING CONDITION A — TRIAL {trial_idx+1}/5")
        print(f"==========================================")
        candidates = []
        for call_idx in range(15):
            prompt = get_condition_a_prompt(call_idx)
            cand = self.run_call(
                trial_idx=trial_idx,
                condition="A",
                call_idx=call_idx,
                prompt=prompt,
                parent_ids=[],
                notes=f"Angle {call_idx % 5}"
            )
            candidates.append(cand)

        # Champion selection: lowest dev score among valid candidates
        valid_cands = [c for c in candidates if c["validity"] and c["development_score"] < 999999]
        if valid_cands:
            champ = min(valid_cands, key=lambda c: c["development_score"])
        else:
            champ = candidates[0]

        print(f"[CONDITION A — TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} | Dev Makespan: {champ['development_score']}")
        return champ

    # -------------------------------------------------------------
    # Condition B: Naive Evolution (5 init + 5 gens x 2 offspring)
    # -------------------------------------------------------------
    def run_condition_b_trial(self, trial_idx: int) -> Dict[str, Any]:
        print(f"\n==========================================")
        print(f"STARTING CONDITION B — TRIAL {trial_idx+1}/5")
        print(f"==========================================")
        population: List[Dict[str, Any]] = []

        # Calls 1-5: Initial Population
        for call_idx in range(5):
            prompt = get_condition_a_prompt(call_idx)
            cand = self.run_call(
                trial_idx=trial_idx,
                condition="B",
                call_idx=call_idx,
                prompt=prompt,
                parent_ids=[],
                notes="Gen0_Initial"
            )
            population.append(cand)

        # Calls 6-15: 5 Generations of 2 Offspring
        call_counter = 5
        for gen in range(1, 6):
            valid_cands = [c for c in population if c["validity"] and c["development_score"] < 999999]
            if not valid_cands:
                valid_cands = population

            # Sort by dev makespan
            valid_cands.sort(key=lambda c: c["development_score"])
            best_cand = valid_cands[0]
            second_best = valid_cands[1] if len(valid_cands) > 1 else valid_cands[0]

            # Offspring 1: Refinement of the best candidate
            prompt_refine = get_condition_b_refine_prompt(best_cand)
            cand1 = self.run_call(
                trial_idx=trial_idx,
                condition="B",
                call_idx=call_counter,
                prompt=prompt_refine,
                parent_ids=[best_cand["candidate_id"]],
                notes=f"Gen{gen}_Refine"
            )
            population.append(cand1)
            call_counter += 1

            # Offspring 2: Crossover of top 2 candidates
            prompt_cross = get_condition_b_crossover_prompt(best_cand, second_best)
            cand2 = self.run_call(
                trial_idx=trial_idx,
                condition="B",
                call_idx=call_counter,
                prompt=prompt_cross,
                parent_ids=[best_cand["candidate_id"], second_best["candidate_id"]],
                notes=f"Gen{gen}_Crossover"
            )
            population.append(cand2)
            call_counter += 1

        # Champion selection
        valid_cands = [c for c in population if c["validity"] and c["development_score"] < 999999]
        champ = min(valid_cands, key=lambda c: c["development_score"]) if valid_cands else population[0]

        print(f"[CONDITION B — TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} | Dev Makespan: {champ['development_score']}")
        return champ

    # -------------------------------------------------------------
    # Condition C: Behavioral Quality-Diversity (15 calls)
    # -------------------------------------------------------------
    def run_condition_c_trial(self, trial_idx: int) -> Dict[str, Any]:
        print(f"\n==========================================")
        print(f"STARTING CONDITION C — TRIAL {trial_idx+1}/5")
        print(f"==========================================")
        archive = QDArchive(
            delta_min=self.config.get("qd_archive", {}).get("delta_min", 0.20),
            max_archive_size=self.config.get("qd_archive", {}).get("max_archive_size", 10)
        )
        all_candidates: List[Dict[str, Any]] = []

        # Calls 1-5: Initial Population
        for call_idx in range(5):
            prompt = get_condition_a_prompt(call_idx)
            cand = self.run_call(
                trial_idx=trial_idx,
                condition="C",
                call_idx=call_idx,
                prompt=prompt,
                parent_ids=[],
                notes="QD_Gen0_Initial"
            )
            all_candidates.append(cand)
            if cand["validity"] and cand["development_score"] < 999999:
                accepted, reason, dist = archive.add_candidate(cand)
                print(f"   [Archive] Candidate {cand['candidate_id']} -> {reason} (dist={dist:.3f}, size={archive.size()})")

        # Calls 6-15: 10 QD-guided offspring (5 iterations of 2 calls)
        call_counter = 5
        for step in range(5):
            # Select reference elite from archive (or from valid candidates if archive empty)
            if archive.size() == 0:
                valid_cands = [c for c in all_candidates if c["validity"]]
                ref1 = valid_cands[0] if valid_cands else all_candidates[0]
                ref2 = None
                avg_dist = 0.5
                pair_dist = 0.5
            else:
                ref1, ref2 = archive.select_references()
                # Compute average distance from ref1 to all elites
                if archive.size() > 1:
                    dists = [
                        mean_behavioral_distance(ref1["behavior_signature"], e["behavior_signature"])
                        for e in archive.elites if e["candidate_id"] != ref1["candidate_id"]
                    ]
                    avg_dist = sum(dists) / len(dists)
                    pair_dist = mean_behavioral_distance(ref1["behavior_signature"], ref2["behavior_signature"]) if ref2 else avg_dist
                else:
                    avg_dist = 0.5
                    pair_dist = 0.5

            # Offspring 1: Novelty / Behavioral differentiation prompt
            prompt_novelty = get_condition_c_novelty_prompt(ref1, avg_dist)
            cand1 = self.run_call(
                trial_idx=trial_idx,
                condition="C",
                call_idx=call_counter,
                prompt=prompt_novelty,
                parent_ids=[ref1["candidate_id"]],
                notes=f"QD_Step{step+1}_Novelty"
            )
            all_candidates.append(cand1)
            if cand1["validity"] and cand1["development_score"] < 999999:
                accepted, reason, dist = archive.add_candidate(cand1)
                print(f"   [Archive] Candidate {cand1['candidate_id']} -> {reason} (dist={dist:.3f}, size={archive.size()})")
            call_counter += 1

            # Offspring 2: Bridge / Multi-niche prompt
            if ref2:
                prompt_bridge = get_condition_c_bridge_prompt(ref1, ref2, pair_dist)
                parent_ids = [ref1["candidate_id"], ref2["candidate_id"]]
            else:
                prompt_bridge = get_condition_c_novelty_prompt(ref1, avg_dist)
                parent_ids = [ref1["candidate_id"]]

            cand2 = self.run_call(
                trial_idx=trial_idx,
                condition="C",
                call_idx=call_counter,
                prompt=prompt_bridge,
                parent_ids=parent_ids,
                notes=f"QD_Step{step+1}_Bridge"
            )
            all_candidates.append(cand2)
            if cand2["validity"] and cand2["development_score"] < 999999:
                accepted, reason, dist = archive.add_candidate(cand2)
                print(f"   [Archive] Candidate {cand2['candidate_id']} -> {reason} (dist={dist:.3f}, size={archive.size()})")
            call_counter += 1

        # Champion selection: lowest dev score in archive or all valid candidates
        valid_cands = [c for c in all_candidates if c["validity"] and c["development_score"] < 999999]
        if archive.size() > 0:
            arch_champ = archive.get_champion()
            if valid_cands:
                all_champ = min(valid_cands, key=lambda c: c["development_score"])
                champ = arch_champ if arch_champ["development_score"] <= all_champ["development_score"] else all_champ
            else:
                champ = arch_champ
        else:
            champ = min(valid_cands, key=lambda c: c["development_score"]) if valid_cands else all_candidates[0]


        print(f"[CONDITION C — TRIAL {trial_idx+1} COMPLETE] Champion: {champ['candidate_id']} | Dev Makespan: {champ['development_score']} | Final Archive Size: {archive.size()}")
        return champ

    # -------------------------------------------------------------
    # Master Experiment Execution
    # -------------------------------------------------------------
    def run_all_trials(self) -> Dict[str, List[Dict[str, Any]]]:
        num_trials = self.config["num_trials"]
        seeds = self.seeds_data["trial_seeds"]

        champions: Dict[str, List[Dict[str, Any]]] = {
            "A": [],
            "B": [],
            "C": []
        }

        start_time = time.time()
        print(f"============================================================")
        print(f"LAUNCHING AMAURA EXPERIMENT #9: PFSP ALGORITHM DISCOVERY")
        print(f"Model: {self.config['model']} | Trials: {num_trials} | Total Calls: {num_trials * 3 * 15}")
        print(f"============================================================")

        for trial_idx in range(num_trials):
            seed = seeds[trial_idx]
            random.seed(seed)
            print(f"\n>>> EXECUTING REPLICATION TRIAL {trial_idx+1}/{num_trials} (Seed: {seed}) <<<")

            # Condition A
            champ_a = self.run_condition_a_trial(trial_idx)
            champions["A"].append(champ_a)

            # Condition B
            champ_b = self.run_condition_b_trial(trial_idx)
            champions["B"].append(champ_b)

            # Condition C
            champ_c = self.run_condition_c_trial(trial_idx)
            champions["C"].append(champ_c)

        elapsed = time.time() - start_time
        print(f"\n============================================================")
        print(f"SEARCH PHASE COMPLETE! Total time: {elapsed/60.0:.1f} minutes")
        print(f"Total LLM calls logged: {self.llm_client.total_calls} (Failed: {self.llm_client.failed_calls})")
        print(f"Total prompt tokens: {self.llm_client.total_prompt_tokens}")
        print(f"Total completion tokens: {self.llm_client.total_completion_tokens}")
        print(f"============================================================")

        # Freeze the 15 champions
        self.freeze_champions(champions)
        return champions

    def freeze_champions(self, champions: Dict[str, List[Dict[str, Any]]]):
        frozen_data = {
            "metadata": {
                "experiment": "Amaura Experiment #9: PFSP Algorithm Discovery",
                "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": self.config["model"],
                "total_champions": 15,
                "trials": self.config["num_trials"]
            },
            "champions": {}
        }
        for cond, champ_list in champions.items():
            frozen_data["champions"][cond] = []
            for champ in champ_list:
                frozen_data["champions"][cond].append({
                    "candidate_id": champ["candidate_id"],
                    "trial_idx": champ["trial_idx"],
                    "condition": cond,
                    "call_idx": champ["call_idx"],
                    "development_score": champ["development_score"],
                    "mean_makespan": champ["mean_makespan"],
                    "runtime_ms": champ["runtime_ms"],
                    "validity": champ["validity"],
                    "code": champ["code"]
                })

        out_path = "experiment9/results/frozen_champions.json"
        with open(out_path, "w") as f:
            json.dump(frozen_data, f, indent=2)
        print(f"\nSuccessfully froze all 15 champions -> {out_path}")

    # -------------------------------------------------------------
    # Blind Hidden Benchmark Evaluation
    # -------------------------------------------------------------
    def evaluate_frozen_champions_on_hidden(self):
        print(f"\n============================================================")
        print(f"EVALUATING FROZEN CHAMPIONS ON HIDDEN BENCHMARK (120 INSTANCES)")
        print(f"============================================================")
        frozen_path = "experiment9/results/frozen_champions.json"
        if not os.path.exists(frozen_path):
            raise FileNotFoundError(f"Frozen champions file not found: {frozen_path}")

        with open(frozen_path) as f:
            frozen_data = json.load(f)

        with open(self.hidden_bench_path) as f:
            hidden_instances = json.load(f)

        hidden_results = {
            "metadata": {
                "hidden_benchmark_instances": len(hidden_instances),
                "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            },
            "evaluations": {}
        }

        for cond, champ_list in frozen_data["champions"].items():
            hidden_results["evaluations"][cond] = []
            for champ in champ_list:
                cid = champ["candidate_id"]
                code = champ["code"]
                print(f"Evaluating {cid} on 120 hidden instances...", flush=True)
                res = self.evaluator.evaluate_solver_code(code, hidden_instances)
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
                hidden_results["evaluations"][cond].append(eval_record)
                status_str = "VALID" if res["is_valid"] else "INVALID"
                print(f"   [{cid}] Hidden Total Makespan: {res['total_makespan']} | Mean: {res['mean_makespan']} | Status: {status_str} | Runtime: {res['runtime_ms']:.1f}ms")

        out_path = "experiment9/results/hidden_evaluations.json"
        with open(out_path, "w") as f:
            json.dump(hidden_results, f, indent=2)
        print(f"\nHidden evaluations completed and saved -> {out_path}")


if __name__ == "__main__":
    runner = ExperimentRunner()
    champions = runner.run_all_trials()
    runner.evaluate_frozen_champions_on_hidden()
    print("\nALL EXPERIMENT #9 RUNS AND EVALUATIONS COMPLETED!")
