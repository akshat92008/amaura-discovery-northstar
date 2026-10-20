"""
Stage 3: Master Search Orchestrator & Arm Controllers (Concurrent Architecture)
==============================================================================
Executes the three strictly matched search arms under 100-slot accounting:
1. Arm A (A_INDEPENDENT_BEST_OF_100):
   - 100 independent candidate generation calls. Zero feedback.
   - Generated in parallel batches (default 10 workers) preserving independence.
   - Evaluated on development instances post-hoc.
   - Selects dev-best valid candidate.
2. Arm B (B_BLIND_ITERATIVE):
   - 10 generations x 10 candidates (100 slots).
   - Generational barrier strictly enforced: Gen g+1 never begins until Gen g finishes.
   - The 10 candidates of generation g are generated concurrently receiving identical text context.
   - Strictly ZERO execution scores, validity, runtimes, or benchmark info.
   - Generation 10: deterministic blind-selection prompt chooses exactly one winner.
3. Arm C (C_AMAURA):
   - 10 generations x 10 candidates (100 slots).
   - Generational barrier strictly enforced: Gen g+1 never begins until Gen g finishes & evaluates.
   - The 10 candidates of generation g are generated concurrently receiving identical structured JSON feedback.
   - Zero evaluator prose diagnostics.
   - Selects dev-best valid candidate across all 100 candidates.

Critical Invariants:
- Exactly 100 slots per arm per trial.
- Invalid candidates, crashes, timeouts consume exactly 1 slot.
- Zero retries, zero replacements, zero bonus candidates.
- Zero-valid arm outcomes recorded as ARM_FAILURE_NO_VALID_CANDIDATE.
- Strict generational barrier: Generation g+1 cannot start before Generation g finishes.
- Complete isolation: Arm A, B, and C run in separate execution phases.
"""

import concurrent.futures
import copy
import json
import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple

from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.llm_client import Stage3LLMClient
from stage3.src.lineage import LineageTracker


class Stage3SearchEngine:
    def __init__(
        self,
        config: Dict[str, Any],
        llm_client: Stage3LLMClient,
        evaluator: GraphColoringEvaluator,
        lineage_tracker: LineageTracker,
        system_prompt: str = (
            "You are an expert combinatorial algorithm designer. "
            "Write a standalone Python function enclosed in ```python ... ``` blocks. "
            "Output the Python code directly without conversational preamble or verbose explanation."
        ),
        max_workers: int = 10
    ):
        self.config = config
        self.llm_client = llm_client
        self.evaluator = evaluator
        self.lineage_tracker = lineage_tracker
        self.system_prompt = system_prompt
        self.max_workers = max_workers

        with open(self.config["prompts"]["expert_gc"]) as f:
            self.expert_prompt_text = f.read()

        with open(self.config["prompts"]["blind_select"]) as f:
            self.blind_select_prompt_text = f.read()

    # =========================================================================
    # ARM A: INDEPENDENT BEST-OF-100
    # =========================================================================
    def run_arm_a(
        self,
        trial_id: int,
        dev_dataset: List[Dict[str, Any]],
        trial_seed: int
    ) -> Dict[str, Any]:
        arm_name = "A_INDEPENDENT_BEST_OF_100"
        candidates = []
        batch_size = self.max_workers
        total_slots = 100

        for batch_start in range(0, total_slots, batch_size):
            batch_indices = list(range(batch_start, min(batch_start + batch_size, total_slots)))

            def query_slot_a(idx):
                global_idx = idx + 1
                cand_id = f"T{trial_id:02d}_A_C{global_idx:03d}"
                call_id = f"call-T{trial_id:02d}-A-{global_idx:03d}"
                cand_seed = trial_seed + global_idx
                resp = self.llm_client.query(
                    prompt=self.expert_prompt_text,
                    system_prompt=self.system_prompt,
                    temperature=self.config.get("temperature", 0.7),
                    max_tokens=self.config.get("max_tokens", 4096),
                    expected_func="color_graph"
                )
                return idx, global_idx, cand_id, call_id, cand_seed, resp

            if self.max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    batch_results = list(executor.map(query_slot_a, batch_indices))
            else:
                batch_results = [query_slot_a(idx) for idx in batch_indices]

            # Deterministic sort by idx to guarantee identical record order
            batch_results.sort(key=lambda r: r[0])

            for idx, global_idx, cand_id, call_id, cand_seed, resp in batch_results:
                res = self.evaluator.evaluate_code(resp["code"], dev_dataset)
                cand_rec = self.lineage_tracker.record_candidate(
                    trial_id=trial_id,
                    arm=arm_name,
                    generation=1,
                    candidate_index_in_gen=global_idx,
                    global_candidate_index=global_idx,
                    candidate_id=cand_id,
                    code=resp["code"],
                    prompt_text=self.expert_prompt_text,
                    system_prompt=self.system_prompt,
                    model_identifier=resp["returned_model"],
                    model_call_id=call_id,
                    prompt_tokens=resp["prompt_tokens"],
                    completion_tokens=resp["completion_tokens"],
                    generation_cost=resp["cost"],
                    latency_ms=resp["latency_ms"],
                    validity=res["is_valid"],
                    development_score=res["total_colors"],
                    failure_category=res["failure_category"],
                    runtime_ms=res["runtime_ms"],
                    error_msg=res["error"],
                    parent_candidate_ids=[],
                    mutation_type="initial_generation",
                    random_seed=cand_seed
                )
                cand_rec["code_body"] = resp["code"]
                candidates.append(cand_rec)

            valid_in_batch = sum(1 for _, g_idx, _, _, _, _ in batch_results if candidates[g_idx-1]["validity"])
            print(f"  [Arm A] Batch {batch_start+1:03d}-{batch_start+len(batch_indices):03d}/100 complete: valid={valid_in_batch}/{len(batch_indices)}", flush=True)

        valid_cands = [c for c in candidates if c["validity"] and c["development_score"] is not None]
        if valid_cands:
            best_cand = min(valid_cands, key=lambda c: (c["development_score"], c["candidate_id"]))
            return {
                "arm": arm_name,
                "status": "VALID",
                "selected_candidate_id": best_cand["candidate_id"],
                "selected_candidate_code": best_cand["code_body"],
                "selected_dev_score": best_cand["development_score"],
                "total_candidates_generated": 100,
                "valid_candidates_count": len(valid_cands),
                "candidates": candidates
            }
        else:
            return {
                "arm": arm_name,
                "status": "ARM_FAILURE_NO_VALID_CANDIDATE",
                "selected_candidate_id": None,
                "selected_candidate_code": None,
                "selected_dev_score": None,
                "total_candidates_generated": 100,
                "valid_candidates_count": 0,
                "candidates": candidates
            }

    # =========================================================================
    # ARM B: BLIND ITERATIVE SEARCH
    # =========================================================================
    def run_arm_b(
        self,
        trial_id: int,
        dev_dataset: List[Dict[str, Any]],
        trial_seed: int
    ) -> Dict[str, Any]:
        arm_name = "B_BLIND_ITERATIVE"
        candidates = []
        gen_10_candidates = []
        prior_gen_code_snippets = []

        for gen in range(1, 11):
            def query_slot_b(c_idx):
                global_idx = (gen - 1) * 10 + c_idx + 1
                cand_id = f"T{trial_id:02d}_B_G{gen:02d}_C{c_idx+1:02d}"
                call_id = f"call-T{trial_id:02d}-B-{global_idx:03d}"
                cand_seed = trial_seed + global_idx

                if gen == 1:
                    prompt = self.expert_prompt_text
                    parent_ids = []
                    mut_type = "initial_generation"
                else:
                    history_block = "\n\n".join([
                        f"--- Prior Candidate {i+1} ---\n```python\n{code}\n```"
                        for i, code in enumerate(prior_gen_code_snippets[:3])
                    ])
                    prompt = (
                        f"{self.expert_prompt_text}\n\n"
                        f"## Prior Iteration Context (Execution-Blind)\n"
                        f"Here are candidate implementations explored in the previous generation:\n"
                        f"{history_block}\n\n"
                        f"TASK FOR THIS GENERATION:\n"
                        f"Reflect on these approaches from theoretical, algorithmic, and asymptotic perspectives. "
                        f"Propose a refined, recombined, or alternative graph coloring algorithm in pure Python."
                    )
                    parent_ids = [f"T{trial_id:02d}_B_G{gen-1:02d}_C01"]
                    mut_type = "blind_iterative_refinement"

                resp = self.llm_client.query(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=self.config.get("temperature", 0.7),
                    max_tokens=self.config.get("max_tokens", 4096),
                    expected_func="color_graph"
                )
                return c_idx, global_idx, cand_id, call_id, cand_seed, prompt, parent_ids, mut_type, resp

            if self.max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, self.max_workers)) as executor:
                    gen_results = list(executor.map(query_slot_b, range(10)))
            else:
                gen_results = [query_slot_b(c_idx) for c_idx in range(10)]

            gen_results.sort(key=lambda r: r[0])

            current_gen_cands = []
            for c_idx, global_idx, cand_id, call_id, cand_seed, prompt, parent_ids, mut_type, resp in gen_results:
                res = self.evaluator.evaluate_code(resp["code"], dev_dataset)
                cand_rec = self.lineage_tracker.record_candidate(
                    trial_id=trial_id,
                    arm=arm_name,
                    generation=gen,
                    candidate_index_in_gen=c_idx + 1,
                    global_candidate_index=global_idx,
                    candidate_id=cand_id,
                    code=resp["code"],
                    prompt_text=prompt,
                    system_prompt=self.system_prompt,
                    model_identifier=resp["returned_model"],
                    model_call_id=call_id,
                    prompt_tokens=resp["prompt_tokens"],
                    completion_tokens=resp["completion_tokens"],
                    generation_cost=resp["cost"],
                    latency_ms=resp["latency_ms"],
                    validity=res["is_valid"],
                    development_score=res["total_colors"],
                    failure_category=res["failure_category"],
                    runtime_ms=res["runtime_ms"],
                    error_msg=res["error"],
                    parent_candidate_ids=parent_ids,
                    mutation_type=mut_type,
                    random_seed=cand_seed
                )
                cand_rec["code_body"] = resp["code"]
                candidates.append(cand_rec)
                current_gen_cands.append(cand_rec)

            prior_gen_code_snippets = [c["code_body"] for c in current_gen_cands]
            valid_in_gen = sum(1 for c in current_gen_cands if c["validity"])
            print(f"  [Arm B] Gen {gen:02d}/10 complete: valid={valid_in_gen}/10", flush=True)

            if gen == 10:
                gen_10_candidates = current_gen_cands

        # Deterministic blind selection at Generation 10
        select_context = "\n\n".join([
            f"=== Candidate_{i+1:02d} (ID: {c['candidate_id']}) ===\n```python\n{c['code_body']}\n```"
            for i, c in enumerate(gen_10_candidates)
        ])
        blind_select_full_prompt = (
            f"{self.blind_select_prompt_text}\n\n"
            f"## Generation 10 Candidates to Choose From:\n\n"
            f"{select_context}"
        )

        select_resp = self.llm_client.query(
            prompt=blind_select_full_prompt,
            system_prompt=self.system_prompt,
            temperature=0.1,
            max_tokens=1024,
            expected_func=""
        )

        raw_sel = select_resp.get("raw_response", "")
        match = re.search(r"SELECTED_CANDIDATE:\s*(Candidate_\d{2})", raw_sel, re.IGNORECASE)
        if match:
            matched_tag = match.group(1).capitalize()
            idx_match = int(matched_tag.split("_")[1]) - 1
            if 0 <= idx_match < len(gen_10_candidates):
                selected_candidate = gen_10_candidates[idx_match]
            else:
                selected_candidate = gen_10_candidates[0]
        else:
            selected_candidate = gen_10_candidates[0]

        if selected_candidate["validity"] and selected_candidate["development_score"] is not None:
            return {
                "arm": arm_name,
                "status": "VALID",
                "selected_candidate_id": selected_candidate["candidate_id"],
                "selected_candidate_code": selected_candidate["code_body"],
                "selected_dev_score": selected_candidate["development_score"],
                "total_candidates_generated": 100,
                "valid_candidates_count": sum(1 for c in candidates if c["validity"]),
                "blind_selection_details": {
                    "raw_response": raw_sel,
                    "prompt_hash": select_resp["prompt_hash"]
                },
                "candidates": candidates
            }
        else:
            return {
                "arm": arm_name,
                "status": "ARM_FAILURE_NO_VALID_CANDIDATE",
                "selected_candidate_id": selected_candidate["candidate_id"],
                "selected_candidate_code": selected_candidate["code_body"],
                "selected_dev_score": None,
                "total_candidates_generated": 100,
                "valid_candidates_count": sum(1 for c in candidates if c["validity"]),
                "blind_selection_details": {
                    "raw_response": raw_sel,
                    "prompt_hash": select_resp["prompt_hash"]
                },
                "candidates": candidates
            }

    # =========================================================================
    # ARM C: AMAURA EXECUTION-DRIVEN ADAPTIVE SEARCH
    # =========================================================================
    def run_arm_c(
        self,
        trial_id: int,
        dev_dataset: List[Dict[str, Any]],
        trial_seed: int
    ) -> Dict[str, Any]:
        arm_name = "C_AMAURA"
        candidates = []
        prior_gen_eval_results: List[Dict[str, Any]] = []

        for gen in range(1, 11):
            if gen > 1:
                # Construct strictly 5-field structured JSON feedback packet
                feedback_packet = [
                    {
                        "candidate_id": r["candidate_id"],
                        "validity": "VALID" if r["validity"] else "INVALID",
                        "development_score": r["development_score"],
                        "failure_category": r["failure_category"],
                        "runtime_ms": r["runtime_ms"]
                    }
                    for r in prior_gen_eval_results
                ]
                cumulative_valid = [
                    r for r in candidates if r["validity"] and r["development_score"] is not None
                ]
                valid_prior = sorted(
                    cumulative_valid, key=lambda x: (x["development_score"], x["candidate_id"])
                )
                best_prior = valid_prior[0] if valid_prior else prior_gen_eval_results[0]
                feedback_json = json.dumps(feedback_packet, indent=2)
            else:
                feedback_packet = []
                valid_prior = []
                best_prior = None
                feedback_json = ""

            def query_slot_c(c_idx):
                global_idx = (gen - 1) * 10 + c_idx + 1
                cand_id = f"T{trial_id:02d}_C_G{gen:02d}_C{c_idx+1:02d}"
                call_id = f"call-T{trial_id:02d}-C-{global_idx:03d}"
                cand_seed = trial_seed + global_idx

                if gen == 1:
                    prompt = self.expert_prompt_text
                    parent_ids = []
                    mut_type = "initial_generation"
                    parent_decision = None
                    mut_directive = "initial_generation"
                    is_explor = True
                else:
                    if c_idx < 4:
                        mut_directive = "mutate_top_candidate"
                        parent_ids = [best_prior["candidate_id"]]
                        parent_decision = f"Selected best prior candidate {best_prior['candidate_id']} (score: {best_prior['development_score']})"
                        mut_type = "modify_tiebreaker"
                        is_explor = False
                        directive_text = (
                            f"DIRECTIVE: Refine and mutate top candidate {best_prior['candidate_id']}. "
                            f"Modify vertex selection tie-breakers, optimize Kempe elimination, or adjust First-Fit loops."
                        )
                    elif c_idx < 7:
                        mut_directive = "combine_parents"
                        parents = [r["candidate_id"] for r in (valid_prior[:2] if len(valid_prior) >= 2 else prior_gen_eval_results[:2])]
                        parent_ids = parents
                        parent_decision = f"Selected parents {parents} for structural recombination"
                        mut_type = "combine_parents"
                        is_explor = False
                        directive_text = (
                            f"DIRECTIVE: Recombine algorithmic features from candidates {parent_ids}. "
                            f"Synthesize independent set extraction with dynamic saturation ordering."
                        )
                    else:
                        mut_directive = "explore_orthogonal_heuristic"
                        parent_ids = [best_prior["candidate_id"]]
                        parent_decision = "Orthogonal heuristic exploration slot"
                        mut_type = "add_heuristic"
                        is_explor = True
                        directive_text = (
                            "DIRECTIVE: Explore an orthogonal heuristic paradigm (e.g. Smallest-Last peeling, "
                            "adaptive saturation weights, or maximal independent set extraction) to escape local optima."
                        )

                    parent_lookup = {r["candidate_id"]: r for r in candidates}
                    selected_parent_records = [
                        parent_lookup[pid] for pid in parent_ids if pid in parent_lookup
                    ] or [best_prior]
                    parent_code_blocks = "\n\n".join(
                        f"Parent Code Snippet ({p_rec['candidate_id']}):\n```python\n{p_rec['code_body']}\n```"
                        for p_rec in selected_parent_records
                    )

                    prompt = (
                        f"{self.expert_prompt_text}\n\n"
                        f"## Empirical Development Execution Feedback (Generation {gen-1})\n"
                        f"The following structured execution metrics were measured on the 40 development instances:\n"
                        f"```json\n{feedback_json}\n```\n\n"
                        f"{parent_code_blocks}\n\n"
                        f"TASK FOR THIS CANDIDATE:\n"
                        f"{directive_text}\n"
                        f"Write a standalone Python function enclosed in ```python ... ``` blocks."
                    )

                resp = self.llm_client.query(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=self.config.get("temperature", 0.7),
                    max_tokens=self.config.get("max_tokens", 4096),
                    expected_func="color_graph"
                )
                return c_idx, global_idx, cand_id, call_id, cand_seed, prompt, parent_ids, mut_type, parent_decision, mut_directive, is_explor, resp

            if self.max_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, self.max_workers)) as executor:
                    gen_results = list(executor.map(query_slot_c, range(10)))
            else:
                gen_results = [query_slot_c(c_idx) for c_idx in range(10)]

            gen_results.sort(key=lambda r: r[0])

            current_gen_cands = []
            for c_idx, global_idx, cand_id, call_id, cand_seed, prompt, parent_ids, mut_type, parent_decision, mut_directive, is_explor, resp in gen_results:
                res = self.evaluator.evaluate_code(resp["code"], dev_dataset)
                cand_rec = self.lineage_tracker.record_candidate(
                    trial_id=trial_id,
                    arm=arm_name,
                    generation=gen,
                    candidate_index_in_gen=c_idx + 1,
                    global_candidate_index=global_idx,
                    candidate_id=cand_id,
                    code=resp["code"],
                    prompt_text=prompt,
                    system_prompt=self.system_prompt,
                    model_identifier=resp["returned_model"],
                    model_call_id=call_id,
                    prompt_tokens=resp["prompt_tokens"],
                    completion_tokens=resp["completion_tokens"],
                    generation_cost=resp["cost"],
                    latency_ms=resp["latency_ms"],
                    validity=res["is_valid"],
                    development_score=res["total_colors"],
                    failure_category=res["failure_category"],
                    runtime_ms=res["runtime_ms"],
                    error_msg=res["error"],
                    parent_candidate_ids=parent_ids,
                    mutation_type=mut_type,
                    random_seed=cand_seed,
                    feedback_exposed=feedback_packet if gen > 1 else None,
                    parent_selection_decision=parent_decision,
                    mutation_directive=mut_directive,
                    is_exploration=is_explor
                )
                cand_rec["code_body"] = resp["code"]
                candidates.append(cand_rec)
                current_gen_cands.append(cand_rec)

            prior_gen_eval_results = current_gen_cands
            valid_in_gen = sum(1 for c in current_gen_cands if c["validity"])
            best_gen_score = min([c["development_score"] for c in current_gen_cands if c["validity"] and c["development_score"] is not None], default=None)
            print(f"  [Arm C] Gen {gen:02d}/10 complete: valid={valid_in_gen}/10, best_gen_score={best_gen_score}", flush=True)

        valid_cands = [c for c in candidates if c["validity"] and c["development_score"] is not None]
        if valid_cands:
            best_cand = min(valid_cands, key=lambda c: (c["development_score"], c["candidate_id"]))
            return {
                "arm": arm_name,
                "status": "VALID",
                "selected_candidate_id": best_cand["candidate_id"],
                "selected_candidate_code": best_cand["code_body"],
                "selected_dev_score": best_cand["development_score"],
                "total_candidates_generated": 100,
                "valid_candidates_count": len(valid_cands),
                "candidates": candidates
            }
        else:
            return {
                "arm": arm_name,
                "status": "ARM_FAILURE_NO_VALID_CANDIDATE",
                "selected_candidate_id": None,
                "selected_candidate_code": None,
                "selected_dev_score": None,
                "total_candidates_generated": 100,
                "valid_candidates_count": 0,
                "candidates": candidates
            }
