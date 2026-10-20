"""
Stage 2: Master Experiment Orchestrator
=======================================
Implements the 4-arm experimental design:
- Arm A: Random Pick from 20 Expert Candidates + Pool Mean
- Arm B: Blind LLM Judge on 20 Expert Candidates (3-shuffle deterministic voting)
- Arm C: Diversified Amaura (20 distinct perspectives, dev selection)
- Arm D: Amaura + Expert Prompt (Exact same 20 Expert Candidates as B, dev selection)

Critical invariants:
- candidate_i_hash_B == candidate_i_hash_D for all i in [1, 20]. Aborts trial if violated.
- Zero hidden access until state machine reaches SELECTIONS_FROZEN.
"""

import copy
import hashlib
import json
import os
import random
import sys
import time
from typing import Dict, Any, List, Tuple, Optional

from stage2.src.state_machine import StateMachine, ExperimentState
from stage2.src.llm_client import Stage2LLMClient, ModelMismatchException
from stage2.src.evaluator_gc import GraphColoringEvaluator
from stage2.src.evaluator_pfsp import PFSPEvaluator
from stage2.src.judge import BlindJudgeEngine
from stage2.src.pool_spread import PoolSpreadAnalyzer
from stage2.src.scaling import SubsamplingScalingEngine
from stage2.prompts.amaura_perspectives_gc import AMAURA_PERSPECTIVES_GC
from stage2.prompts.amaura_perspectives_pfsp import AMAURA_PERSPECTIVES_PFSP


class Stage2Runner:
    def __init__(
        self,
        config_path: str = "stage2/config.json",
        state_machine: Optional[StateMachine] = None,
        mock_mode: bool = False
    ):
        self.config_path = config_path
        with open(config_path) as f:
            self.config = json.load(f)

        self.mock_mode = mock_mode or self.config.get("mock_mode", False)
        self.state_machine = state_machine or StateMachine()

        # LLM Clients
        model_name = self.config.get("model", "nvidia/nvidia/nemotron-3-super-120b-a12b")
        api_key = self.config.get("api_key") or os.environ.get("STAGE2_API_KEY") or os.environ.get("OPENAI_API_KEY") or "local-proxy"
        self.generator_client = Stage2LLMClient(
            model=model_name,
            base_url=self.config.get("api_base_url", "http://127.0.0.1:20128/v1/chat/completions"),
            api_key=api_key,
            mock_mode=self.mock_mode
        )
        self.judge_client = Stage2LLMClient(
            model=model_name,
            base_url=self.config.get("api_base_url", "http://127.0.0.1:20128/v1/chat/completions"),
            api_key=api_key,
            mock_mode=self.mock_mode
        )

        # Evaluators
        self.gc_evaluator = GraphColoringEvaluator()
        self.pfsp_evaluator = PFSPEvaluator()

        # Engines
        self.judge_engine = BlindJudgeEngine(self.judge_client)
        self.spread_analyzer = PoolSpreadAnalyzer()
        self.scaling_engine = SubsamplingScalingEngine()

        # Paths
        self.candidates_log_path = self.config.get("candidates_log_path", "stage2/candidates/candidates.jsonl")
        self.selections_path = self.config.get("selections_path", "stage2/results/selections.json")
        self.results_path = self.config.get("results_path", "stage2/results/evaluation_results.json")

        os.makedirs(os.path.dirname(self.candidates_log_path) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(self.selections_path) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(self.results_path) or ".", exist_ok=True)

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def generate_candidate_pool(
        self,
        problem: str,
        pool_type: str,  # 'expert' or 'diversified'
        trial_id: int,
        prompt_text: str,
        system_prompt: str,
        expected_func: str
    ) -> List[Dict[str, Any]]:
        """
        Generates exactly 20 candidates for a pool.
        """
        candidates = []
        perspectives = AMAURA_PERSPECTIVES_GC if problem == "graph_coloring" else AMAURA_PERSPECTIVES_PFSP

        from concurrent.futures import ThreadPoolExecutor

        def _generate_candidate(c_idx: int) -> Tuple[int, Dict[str, Any]]:
            cand_id = f"{problem}_T{trial_id:02d}_{pool_type[0].upper()}_C{c_idx+1:02d}"

            if pool_type == "expert":
                active_prompt = prompt_text
                perspective_name = "Expert Prompt Single-Family"
                perspective_id = 0
            else:
                p_item = perspectives[c_idx % len(perspectives)]
                active_prompt = f"{prompt_text}\n\nSPECIFIC PERSPECTIVE DIRECTIVE:\n{p_item['prompt']}"
                perspective_name = p_item["name"]
                perspective_id = p_item["id"]

            resp = self.generator_client.query(
                prompt=active_prompt,
                system_prompt=system_prompt,
                temperature=0.6,
                max_tokens=4096,
                expected_func=expected_func
            )

            cand_rec = {
                "experiment_id": "Amaura_Stage_2",
                "trial_id": trial_id,
                "problem": problem,
                "pool_type": pool_type,
                "candidate_id": cand_id,
                "candidate_index": c_idx + 1,
                "candidate_hash": resp["candidate_hash"],
                "prompt_hash": resp["prompt_hash"],
                "perspective_id": perspective_id,
                "perspective_name": perspective_name,
                "model_id": resp["returned_model"],
                "provider": resp["provider"],
                "code": resp["code"],
                "prompt_tokens": resp["prompt_tokens"],
                "completion_tokens": resp["completion_tokens"],
                "generation_cost": resp["cost"],
                "generation_timestamp": resp["timestamp"],
                "is_truncated": resp["is_truncated"],
                "error": resp["error"]
            }
            return c_idx, cand_rec

        max_workers = 1 if self.mock_mode else 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            indexed_results = list(executor.map(_generate_candidate, range(20)))

        # Sort strictly by candidate index 0..19 to ensure deterministic pool order
        indexed_results.sort(key=lambda x: x[0])
        candidates = [rec for _, rec in indexed_results]

        # Append immutably to candidates.jsonl in deterministic order
        with open(self.candidates_log_path, "a") as f:
            for cand_rec in candidates:
                f.write(json.dumps(cand_rec) + "\n")

        return candidates

    @staticmethod
    def verify_pool_identity(pool_b: List[Dict[str, Any]], pool_d: List[Dict[str, Any]]):
        """
        Adversarially validates that Pool B and Pool D are strictly 1:1 identical in length, code, and hash.
        Fails immediately with ValueError if any discrepancy exists.
        """
        if len(pool_b) != 20 or len(pool_d) != 20:
            raise ValueError(f"CRITICAL EXPERIMENT VIOLATION: Pool size mismatch B={len(pool_b)}, D={len(pool_d)}")
        for idx in range(20):
            hb = pool_b[idx].get("candidate_hash")
            hd = pool_d[idx].get("candidate_hash")
            cb = pool_b[idx].get("code")
            cd = pool_d[idx].get("code")
            if hb != hd or cb != cd:
                raise ValueError(
                    f"CRITICAL EXPERIMENT VIOLATION: Candidate {idx+1} mismatch between Arm B and Arm D! "
                    f"(hash_B={hb}, hash_D={hd}). Aborting trial."
                )

    def evaluate_pool_on_dev(
        self,
        problem: str,
        candidates: List[Dict[str, Any]],
        dev_dataset: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        evaluator = self.gc_evaluator if problem == "graph_coloring" else self.pfsp_evaluator
        score_key = "total_colors" if problem == "graph_coloring" else "total_makespan"

        for cand in candidates:
            res = evaluator.evaluate_code(cand["code"], dev_dataset)
            cand["dev_score"] = res[score_key]
            cand["dev_is_valid"] = res["is_valid"]
            cand["dev_runtime_ms"] = res["runtime_ms"]
            cand["dev_error"] = res["error"]

        return candidates

    def run_trial(
        self,
        problem: str,
        trial_id: int,
        dev_dataset: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Executes a single trial containing Arms A, B, C, D:
        1. Generates 20 expert candidates (Pool 1).
        2. Generates 20 diversified candidates (Pool 2).
        3. Enforces hash & code identity between Arm B and Arm D.
        4. Selects candidate for Arm B execution-blind BEFORE dev evaluation occurs.
        5. Evaluates candidates on Dev data for Arms A, C, D.
        """
        prompt_file = f"stage2/prompts/expert_prompt_{'gc' if problem == 'graph_coloring' else 'pfsp'}.txt"
        with open(prompt_file) as f:
            expert_prompt_text = f.read()

        sys_prompt = (
            "You are an expert combinatorial algorithm designer. "
            "Write a standalone Python function enclosed in ```python ... ``` blocks. "
            "Output the Python code directly without conversational preamble or verbose explanation."
        )
        expected_func = "color_graph" if problem == "graph_coloring" else "schedule_flowshop"

        # 1. Pool 1: 20 Expert Candidates (Used by Arm A, Arm B, and Arm D)
        expert_pool = self.generate_candidate_pool(
            problem=problem,
            pool_type="expert",
            trial_id=trial_id,
            prompt_text=expert_prompt_text,
            system_prompt=sys_prompt,
            expected_func=expected_func
        )

        # 2. Pool 2: 20 Diversified Candidates (Used by Arm C)
        diversified_pool = self.generate_candidate_pool(
            problem=problem,
            pool_type="diversified",
            trial_id=trial_id,
            prompt_text=expert_prompt_text,
            system_prompt=sys_prompt,
            expected_func=expected_func
        )

        # Separate independent copies for Arm B and Arm D
        pool_b = copy.deepcopy(expert_pool)
        pool_d = copy.deepcopy(expert_pool)

        # SECTION 5 & 35: CRITICAL HASH IDENTITY VERIFICATION (B vs D)
        self.verify_pool_identity(pool_b, pool_d)

        # Arm B: Blind LLM Judge executed BEFORE any dev evaluation occurs!
        # This physically prevents dev scores from leaking into judge prompts or candidate objects.
        judge_res = self.judge_engine.judge_candidates(problem, pool_b, trial_seed=trial_id * 1000)
        selected_b_id = judge_res["selected_candidate_id"]
        selected_b = [c for c in pool_b if c["candidate_id"] == selected_b_id][0]

        # Evaluate pool_d and diversified_pool on Dev data
        pool_d = self.evaluate_pool_on_dev(problem, pool_d, dev_dataset)
        diversified_pool = self.evaluate_pool_on_dev(problem, diversified_pool, dev_dataset)

        # Re-verify hash and code identity between B and D
        self.verify_pool_identity(pool_b, pool_d)

        # Pool Spread Analysis on Dev Scores
        score_key = "dev_score"
        spread_expert = self.spread_analyzer.analyze_pool([c[score_key] for c in pool_d], "expert_pool")
        spread_div = self.spread_analyzer.analyze_pool([c[score_key] for c in diversified_pool], "diversified_pool")

        # -------------------------------------------------------------
        # SELECTIONS
        # -------------------------------------------------------------
        # Arm D: Best candidate in expert pool on Dev
        selected_d = min(pool_d, key=lambda c: c.get(score_key, float("inf")))

        # Arm C: Best candidate in diversified pool on Dev
        selected_c = min(diversified_pool, key=lambda c: c.get(score_key, float("inf")))

        # Arm A: Seeded random pick from expert pool + pool mean
        rng = random.Random(trial_id * 54321)
        selected_a = rng.choice(pool_d)
        expert_pool_dev_scores = [c[score_key] for c in pool_d if c[score_key] < 900000]
        pool_mean_dev = float(sum(expert_pool_dev_scores) / len(expert_pool_dev_scores)) if expert_pool_dev_scores else 999999.0

        return {
            "trial_id": trial_id,
            "problem": problem,
            "selections": {
                "Arm_A_Random": {
                    "candidate_id": selected_a["candidate_id"],
                    "candidate_hash": selected_a["candidate_hash"],
                    "code": selected_a["code"],
                    "dev_score": selected_a["dev_score"],
                    "pool_mean_dev_score": round(pool_mean_dev, 4)
                },
                "Arm_B_Judge": {
                    "candidate_id": selected_b["candidate_id"],
                    "candidate_hash": selected_b["candidate_hash"],
                    "code": selected_b["code"],
                    "dev_score": [c for c in pool_d if c["candidate_id"] == selected_b_id][0].get("dev_score"),
                    "judge_details": judge_res
                },
                "Arm_C_Amaura_Div": {
                    "candidate_id": selected_c["candidate_id"],
                    "candidate_hash": selected_c["candidate_hash"],
                    "code": selected_c["code"],
                    "dev_score": selected_c["dev_score"],
                    "perspective_name": selected_c["perspective_name"]
                },
                "Arm_D_Amaura_Expert": {
                    "candidate_id": selected_d["candidate_id"],
                    "candidate_hash": selected_d["candidate_hash"],
                    "code": selected_d["code"],
                    "dev_score": selected_d["dev_score"]
                }
            },
            "pools": {
                "expert_pool": expert_pool,
                "diversified_pool": diversified_pool
            },
            "spread_analysis": {
                "expert_pool": spread_expert,
                "diversified_pool": spread_div
            }
        }

    def evaluate_hidden_trial(self, trial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforces Section 12 & Section 32:
        Evaluates selected candidates A, B, C, D AND all 20 candidates in both pools on hidden data.
        Calculates selection regret.
        Accesses hidden data via state_machine (fails closed if not in SELECTIONS_FROZEN or later).
        """
        problem = trial_data["problem"]
        hidden_dataset = self.state_machine.access_hidden_dataset(problem, caller_tag="Stage2Runner.evaluate_hidden_trial")

        evaluator = self.gc_evaluator if problem == "graph_coloring" else self.pfsp_evaluator
        score_key = "total_colors" if problem == "graph_coloring" else "total_makespan"

        # 1. Evaluate all candidates in expert_pool
        expert_pool = trial_data["pools"]["expert_pool"]
        for c in expert_pool:
            res = evaluator.evaluate_code(c["code"], hidden_dataset)
            c["hidden_score"] = res[score_key]
            c["hidden_is_valid"] = res["is_valid"]
            c["hidden_runtime_ms"] = res["runtime_ms"]

        # 2. Evaluate all candidates in diversified_pool
        diversified_pool = trial_data["pools"]["diversified_pool"]
        for c in diversified_pool:
            res = evaluator.evaluate_code(c["code"], hidden_dataset)
            c["hidden_score"] = res[score_key]
            c["hidden_is_valid"] = res["is_valid"]
            c["hidden_runtime_ms"] = res["runtime_ms"]

        # 3. Identify best possible hidden score in expert pool
        valid_expert_hidden = [c["hidden_score"] for c in expert_pool if c["hidden_score"] < 900000]
        has_valid_expert = len(valid_expert_hidden) > 0
        best_expert_hidden = min(valid_expert_hidden) if has_valid_expert else 999999.0

        # 4. Map hidden scores back to selections & compute Regret
        selections = trial_data["selections"]
        for arm_name in ["Arm_A_Random", "Arm_B_Judge", "Arm_C_Amaura_Div", "Arm_D_Amaura_Expert"]:
            cand_id = selections[arm_name]["candidate_id"]
            matched_pool = diversified_pool if arm_name == "Arm_C_Amaura_Div" else expert_pool
            cand = [c for c in matched_pool if c["candidate_id"] == cand_id][0]
            
            h_score = cand["hidden_score"]
            selections[arm_name]["hidden_score"] = h_score
            selections[arm_name]["hidden_is_valid"] = cand["hidden_is_valid"]
            selections[arm_name]["hidden_runtime_ms"] = cand["hidden_runtime_ms"]

            if arm_name != "Arm_C_Amaura_Div":
                # Compute Regret vs best in expert pool only if both candidate and pool are valid
                if not cand["hidden_is_valid"] or h_score >= 900000 or not has_valid_expert:
                    selections[arm_name]["absolute_regret"] = None
                    selections[arm_name]["relative_regret_pct"] = None
                    selections[arm_name]["is_valid_regret"] = False
                else:
                    abs_regret = h_score - best_expert_hidden
                    rel_regret = (abs_regret / best_expert_hidden) * 100.0 if best_expert_hidden > 0 else 0.0
                    selections[arm_name]["absolute_regret"] = round(abs_regret, 4)
                    selections[arm_name]["relative_regret_pct"] = round(rel_regret, 2)
                    selections[arm_name]["is_valid_regret"] = True

        # 5. Evaluate scaling on expert pool
        scaling_results = self.scaling_engine.evaluate_scaling(
            candidate_pool=expert_pool,
            selection_key="dev_score",
            evaluation_key="hidden_score",
            seed=trial_data["trial_id"] * 1234
        )

        return {
            "trial_id": trial_data["trial_id"],
            "problem": problem,
            "best_expert_hidden_score": best_expert_hidden,
            "selections": selections,
            "scaling": scaling_results,
            "spread_analysis": trial_data["spread_analysis"]
        }

