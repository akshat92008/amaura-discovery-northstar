"""
Stage 3: Candidate Lineage & Provenance Tracker
===============================================
Enforces complete provenance and traceability for every candidate generated:
- Immutable JSONL append-only log.
- Tracks parent IDs, mutation classifications, prompt hashes, candidate code hashes.
- Records token counts, costs, execution scores, and failure categories.
- Specific audit fields for Arm C (feedback exposed, parent decisions, mutation directives).
"""

import hashlib
import json
import os
import time
from typing import Dict, Any, List, Optional


class LineageTracker:
    def __init__(self, log_path: str = "stage3/candidates/candidates.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def record_candidate(
        self,
        trial_id: int,
        arm: str,
        generation: int,
        candidate_index_in_gen: int,
        global_candidate_index: int,
        candidate_id: str,
        code: str,
        prompt_text: str,
        system_prompt: str,
        model_identifier: str,
        model_call_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        generation_cost: float,
        latency_ms: float,
        validity: bool,
        development_score: Optional[int],
        failure_category: Optional[str],
        runtime_ms: float,
        error_msg: Optional[str],
        parent_candidate_ids: Optional[List[str]] = None,
        mutation_type: str = "initial_generation",
        random_seed: Optional[int] = None,
        feedback_exposed: Optional[List[Dict[str, Any]]] = None,
        parent_selection_decision: Optional[str] = None,
        mutation_directive: Optional[str] = None,
        is_exploration: Optional[bool] = None
    ) -> Dict[str, Any]:
        prompt_hash = self.sha256_text(prompt_text)
        sys_hash = self.sha256_text(system_prompt)
        code_hash = self.sha256_text(code)

        record: Dict[str, Any] = {
            "trial_id": trial_id,
            "arm": arm,
            "generation": generation,
            "candidate_index_in_gen": candidate_index_in_gen,
            "global_candidate_index": global_candidate_index,
            "candidate_id": candidate_id,
            "parent_candidate_ids": parent_candidate_ids or [],
            "mutation_type": mutation_type,
            "model_call_id": model_call_id,
            "prompt_hash": prompt_hash,
            "system_prompt_hash": sys_hash,
            "candidate_code_hash": code_hash,
            "model_identifier": model_identifier,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "generation_cost": round(generation_cost, 6),
            "latency_ms": round(latency_ms, 2),
            "validity": validity,
            "development_score": development_score,
            "failure_category": failure_category,
            "runtime_ms": round(runtime_ms, 2),
            "error": error_msg,
            "timestamp": time.time(),
            "random_seed": random_seed
        }

        # Arm C specific adaptive audit fields
        if arm == "C_AMAURA":
            record["feedback_exposed_to_model"] = feedback_exposed or []
            record["parent_selection_decision"] = parent_selection_decision
            record["mutation_recombination_decision"] = mutation_directive
            record["exploration_decision"] = is_exploration

        with open(self.log_path, "a") as f:
            f.write(json.dumps(record) + "\n")

        return record

    def load_candidates_for_trial(self, trial_id: int, arm: Optional[str] = None) -> List[Dict[str, Any]]:
        if not os.path.exists(self.log_path):
            return []
        cands = []
        with open(self.log_path) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("trial_id") == trial_id:
                    if arm is None or rec.get("arm") == arm:
                        cands.append(rec)
        return cands
