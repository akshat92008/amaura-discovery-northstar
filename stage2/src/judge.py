"""
Stage 2: Execution-Blind Judge & Deterministic Aggregation Engine (Arm B)
========================================================================
Enforces Section 3:
1. Execution-blind judging: Judge sees only problem description and candidate code.
2. 3 independent shuffles with fresh randomized candidate presentation orders.
3. Deterministic aggregation rules:
   - Case 1: All 3 agree -> select candidate.
   - Case 2: 2 agree, 1 disagrees -> majority vote selects candidate.
   - Case 3: 3-way split -> deterministic pre-registered tie-break (lowest candidate_id).
4. Supports secondary stronger judge robustness check.
5. Logs full provenance and tokens for each shuffle.
"""

import json
import random
import re
import time
from typing import List, Dict, Any, Tuple, Optional

from stage2.prompts.judge_prompts import build_judge_prompt, JUDGE_SYSTEM_PROMPT
from stage2.src.llm_client import Stage2LLMClient


class BlindJudgeEngine:
    def __init__(
        self,
        llm_client: Stage2LLMClient,
        aggregation_rule: str = "majority_with_lexicographic_tiebreak",
        secondary_client: Optional[Stage2LLMClient] = None
    ):
        self.llm_client = llm_client
        self.aggregation_rule = aggregation_rule
        self.secondary_client = secondary_client

        if self.aggregation_rule != "majority_with_lexicographic_tiebreak":
            raise ValueError(f"Unsupported or missing aggregation rule: {self.aggregation_rule}. Fail closed.")

    @staticmethod
    def parse_judge_choice(raw_text: str, valid_options: List[str]) -> str:
        # Match pattern 'SELECTED_CANDIDATE:\s*(Option_\d+)'
        match = re.search(r"SELECTED_CANDIDATE:\s*(Option_\d+)", raw_text, re.IGNORECASE)
        if match:
            choice = match.group(1).capitalize()
            # Normalize to Option_XX
            for opt in valid_options:
                if choice.lower() == opt.lower():
                    return opt

        # Fallback regex searching for any Option_\d+ in text
        matches = re.findall(r"Option_\d+", raw_text, re.IGNORECASE)
        if matches:
            last_match = matches[-1]
            for opt in valid_options:
                if last_match.lower() == opt.lower():
                    return opt

        # Fallback to first option if unparseable
        return valid_options[0]

    def run_single_shuffle(
        self,
        problem_type: str,
        candidates: List[Dict[str, Any]],
        shuffle_seed: int,
        client: Stage2LLMClient
    ) -> Dict[str, Any]:
        rng = random.Random(shuffle_seed)
        shuffled = list(candidates)
        rng.shuffle(shuffled)

        presentation_list = []
        option_to_cand_id = {}
        for idx, cand in enumerate(shuffled):
            opt_id = f"Option_{idx+1:02d}"
            option_to_cand_id[opt_id] = cand["candidate_id"]
            presentation_list.append({
                "option_id": opt_id,
                "candidate_id": cand["candidate_id"],
                "code": cand["code"]
            })

        prompt = build_judge_prompt(problem_type, presentation_list)
        resp = client.query(
            prompt=prompt,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            temperature=0.1,  # Low temperature for reasoning stability
            max_tokens=2048,
            expected_func=""
        )

        valid_options = list(option_to_cand_id.keys())
        chosen_opt = self.parse_judge_choice(resp["raw_response"], valid_options)
        selected_cand_id = option_to_cand_id[chosen_opt]

        return {
            "shuffle_seed": shuffle_seed,
            "presentation_order": [p["candidate_id"] for p in presentation_list],
            "chosen_option": chosen_opt,
            "selected_candidate_id": selected_cand_id,
            "raw_response": resp["raw_response"],
            "model": resp["returned_model"],
            "prompt_tokens": resp["prompt_tokens"],
            "completion_tokens": resp["completion_tokens"],
            "cost": resp["cost"],
            "latency_ms": resp["latency_ms"],
            "prompt_hash": resp["prompt_hash"]
        }

    def aggregate_votes(self, votes: List[str]) -> Tuple[str, str]:
        """
        Deterministic aggregation rule:
        - 3/3 -> Unanimous
        - 2/3 -> Majority
        - 1/1/1 -> Lexicographic tie-break on candidate_id
        """
        counts = {}
        for v in votes:
            counts[v] = counts.get(v, 0) + 1

        # Check for 3 or 2 votes
        for cand_id, c in counts.items():
            if c == 3:
                return cand_id, "UNANIMOUS_3_0"
            if c == 2:
                return cand_id, "MAJORITY_2_1"

        # 3-way split: deterministic tie-break (lexicographically smallest ID)
        sorted_cands = sorted(counts.keys())
        winner = sorted_cands[0]
        return winner, f"TIE_BREAK_3_WAY_LEXICOGRAPHIC (out of {sorted_cands})"

    def judge_candidates(
        self,
        problem_type: str,
        candidates: List[Dict[str, Any]],
        trial_seed: int
    ) -> Dict[str, Any]:
        """
        Executes 3 independent shuffles and aggregates the vote deterministically.
        """
        if len(candidates) != 20:
            raise ValueError(f"Judge requires exactly 20 candidates, got {len(candidates)}")

        shuffles = []
        votes = []
        total_p_tok = 0
        total_c_tok = 0
        total_cost = 0.0

        for s_idx in range(3):
            # Derive fresh shuffle seed from trial_seed
            s_seed = trial_seed + 777 * (s_idx + 1)
            shuf_res = self.run_single_shuffle(problem_type, candidates, s_seed, self.llm_client)
            shuffles.append(shuf_res)
            votes.append(shuf_res["selected_candidate_id"])
            total_p_tok += shuf_res["prompt_tokens"]
            total_c_tok += shuf_res["completion_tokens"]
            total_cost += shuf_res["cost"]

        selected_cand_id, agg_reason = self.aggregate_votes(votes)

        result: Dict[str, Any] = {
            "selected_candidate_id": selected_cand_id,
            "aggregation_reason": agg_reason,
            "votes": votes,
            "shuffles": shuffles,
            "total_judge_prompt_tokens": total_p_tok,
            "total_judge_completion_tokens": total_c_tok,
            "total_judge_cost": round(total_cost, 6)
        }

        # Secondary judge robustness evaluation if configured
        if self.secondary_client is not None:
            sec_shuffles = []
            sec_votes = []
            for s_idx in range(3):
                s_seed = trial_seed + 999 * (s_idx + 1)
                sec_res = self.run_single_shuffle(problem_type, candidates, s_seed, self.secondary_client)
                sec_shuffles.append(sec_res)
                sec_votes.append(sec_res["selected_candidate_id"])
            sec_selected, sec_reason = self.aggregate_votes(sec_votes)
            result["secondary_judge"] = {
                "selected_candidate_id": sec_selected,
                "aggregation_reason": sec_reason,
                "votes": sec_votes,
                "shuffles": sec_shuffles
            }

        return result
