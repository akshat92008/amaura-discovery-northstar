"""
Discovery Kernel v0.1: PFSP LLM Candidate Generator
===================================================
Generates declarative PFSP algorithm specifications via local Ollama inference.
Supports:
- Arm A: Independent Best-of-N proposals (zero feedback).
- Arm B: Evidence-guided search across rounds with development feedback.
Enforces zero financial spend ($0.00) and full cryptographic provenance tracking.
"""

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Dict, Any, Optional, List, Tuple
import urllib.request
import urllib.error

from discovery_kernel.pfsp_declarative import validate_config, canonicalize_config


BASE_SYSTEM_PROMPT = """You are an expert algorithm designer specializing in Permutation Flow-Shop Scheduling (PFSP).
The objective is to minimize makespan (C_max) on flow shop scheduling instances.

You must design an algorithm by selecting ONE valid option for each component from the allowed options below:

1. initial_order:
   - "total_processing_time_desc" (Sum of processing times descending, standard NEH / LPT)
   - "total_processing_time_asc" (Sum of processing times ascending, SPT)
   - "first_machine_asc" (Machine 0 processing time ascending)
   - "last_machine_desc" (Last machine processing time descending)
   - "weighted_profile_desc" (Palmer's slope weighting index descending)

2. construction_criterion:
   - "makespan_only" (Evaluate partial schedules by makespan C_max alone)
   - "makespan_and_flow_time" (Minimize C_max primary, total flow time secondary)
   - "makespan_and_idle_time" (Minimize C_max primary, machine idle time secondary)

3. tie_break:
   - "first_found" (First position that achieves optimal score)
   - "last_found" (Last position that achieves optimal score)
   - "flow_time_min" (Break makespan ties by minimal flow time)
   - "idle_time_min" (Break makespan ties by minimal machine idle time)

4. local_search:
   - "none" (Constructive only, no local search)
   - "pairwise_swap" (Adjacent pairwise swap neighborhood)
   - "single_pass_insertion" (Taillard single-pass insertion neighborhood)
   - "multi_pass_insertion" (Multi-pass insertion neighborhood)

5. search_strategy:
   - "none" (Required if local_search is "none")
   - "first_improvement" (Accept first improving neighbor)
   - "best_improvement" (Evaluate all neighbors in pass and accept best)

6. acceptance_rule:
   - "none" (Required if local_search is "none")
   - "strictly_better_makespan" (Accept only if makespan strictly decreases)
   - "better_makespan_or_flow" (Accept if makespan decreases, or if makespan is equal and flow time decreases)

7. budget_evaluations:
   - 0 if local_search is "none"
   - Integer between 50 and 500 if local_search is active

Output MUST be a single JSON object with two fields:
- "rationale": String describing your design rationale.
- "config": Object containing exactly the 7 keys above.
"""

SCHEMA_EXAMPLE = """{
  "rationale": "Prioritize jobs by Palmer slope index and use flow time tie-breaking during insertion, followed by single-pass insertion local search to polish sequence.",
  "config": {
    "initial_order": "weighted_profile_desc",
    "construction_criterion": "makespan_only",
    "tie_break": "flow_time_min",
    "local_search": "single_pass_insertion",
    "search_strategy": "best_improvement",
    "acceptance_rule": "strictly_better_makespan",
    "budget_evaluations": 250
  }
}"""


@dataclass
class ProposalResult:
    proposal_id: str
    arm: str
    round_idx: int
    raw_response: str
    parsed_proposal: Optional[Dict[str, Any]] = None
    sanitized_config: Optional[Dict[str, Any]] = None
    is_valid_spec: bool = False
    validation_error: Optional[str] = None
    recipe_hash: Optional[str] = None
    model: str = "qwen2.5-coder:1.5b"
    provider: str = "ollama/local"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_sec: float = 0.0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)


class PFSPCandidateGenerator:
    """Queries local Ollama instance for declarative PFSP candidate algorithms."""

    def __init__(
        self,
        model: str = "qwen2.5-coder:1.5b",
        base_url: str = "http://127.0.0.1:11434/api/generate",
        timeout_sec: int = 120
    ):
        self.model = model
        self.base_url = base_url
        self.timeout_sec = timeout_sec

    def _query_ollama(self, prompt: str, temperature: float = 0.7) -> Tuple[str, int, int, float]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
            resp_bytes = response.read()
        latency = time.perf_counter() - t0

        result = json.loads(resp_bytes.decode("utf-8"))
        raw_text = result.get("response", "")
        prompt_tokens = result.get("prompt_eval_count", 0)
        completion_tokens = result.get("eval_count", 0)

        return raw_text, prompt_tokens, completion_tokens, latency

    def generate_independent_candidate(
        self,
        proposal_id: str,
        temperature: float = 0.7
    ) -> ProposalResult:
        """Arm A: Generates candidate with zero previous score feedback."""
        prompt = f"""{BASE_SYSTEM_PROMPT}

Example format:
{SCHEMA_EXAMPLE}

Design a novel, distinct algorithm configuration from the component space above to achieve minimal makespan.
Output only the JSON object."""

        raw_text, p_tokens, c_tokens, latency = self._query_ollama(prompt, temperature)

        res = ProposalResult(
            proposal_id=proposal_id,
            arm="arm_a",
            round_idx=0,
            raw_response=raw_text,
            model=self.model,
            provider="ollama/local",
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            latency_sec=latency,
            cost_usd=0.0
        )

        try:
            parsed = json.loads(raw_text)
            res.parsed_proposal = parsed
            is_val, err, sanitized = validate_config(parsed)
            res.is_valid_spec = is_val
            res.validation_error = err
            if is_val and sanitized:
                res.sanitized_config = sanitized["config"]
                _, _, r_hash = canonicalize_config(sanitized["config"])
                res.recipe_hash = r_hash
        except Exception as e:
            res.is_valid_spec = False
            res.validation_error = f"JSON parse error: {str(e)}"

        return res

    def generate_guided_candidate(
        self,
        proposal_id: str,
        round_idx: int,
        feedback_summary: str,
        temperature: float = 0.7
    ) -> ProposalResult:
        """Arm B: Generates candidate with evidence feedback from earlier rounds."""
        if round_idx == 1 or not feedback_summary.strip():
            # Round 1 has no previous evidence
            prompt = f"""{BASE_SYSTEM_PROMPT}

Round 1 of 3: Propose an initial high-potential algorithm configuration.

Example format:
{SCHEMA_EXAMPLE}

Output only the JSON object."""
        else:
            prompt = f"""{BASE_SYSTEM_PROMPT}

EVIDENCE FROM PREVIOUS ROUND(S) ON DEVELOPMENT INSTANCES:
{feedback_summary}

Based on this evidence, analyze what worked best (e.g. construction criterion, tie-break, local search neighborhood).
Propose an improved or refined configuration that aims to outperform the best seen makespan.

Example format:
{SCHEMA_EXAMPLE}

Output only the JSON object."""

        raw_text, p_tokens, c_tokens, latency = self._query_ollama(prompt, temperature)

        res = ProposalResult(
            proposal_id=proposal_id,
            arm="arm_b",
            round_idx=round_idx,
            raw_response=raw_text,
            model=self.model,
            provider="ollama/local",
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            latency_sec=latency,
            cost_usd=0.0
        )

        try:
            parsed = json.loads(raw_text)
            res.parsed_proposal = parsed
            is_val, err, sanitized = validate_config(parsed)
            res.is_valid_spec = is_val
            res.validation_error = err
            if is_val and sanitized:
                res.sanitized_config = sanitized["config"]
                _, _, r_hash = canonicalize_config(sanitized["config"])
                res.recipe_hash = r_hash
        except Exception as e:
            res.is_valid_spec = False
            res.validation_error = f"JSON parse error: {str(e)}"

        return res
