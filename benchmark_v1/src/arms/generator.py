"""
Candidate Search Generators for Benchmark V1
============================================
Supports both:
1. LiveLLMGenerator: Connects to frontier LLM (e.g. Nemotron-3 Super via OmniRoute).
2. SimulatedMutator: Fast, deterministic, reproducible AST/parametric mutator for exhaustive statistical power analysis, width-vs-depth grids, and unit testing.
"""

import hashlib
import json
import math
import os
import random
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

from benchmark_v1.src.arms.base import SearchGenerator, SearchCandidate
from benchmark_v1.src.domains.base import ProblemDomain


class SimulatedMutator(SearchGenerator):
    """
    Fast, deterministic offline mutator producing mathematically structured heuristics.
    Simulates exploration, refinement, recombination, and evidence-driven repairs.
    """
    def __init__(self, invalid_rate: float = 0.05):
        self.invalid_rate = invalid_rate

    def _get_rng(self, seed: int, proposal_idx: int) -> random.Random:
        return random.Random(seed * 10007 + proposal_idx * 37)

    def generate_independent(
        self,
        domain: ProblemDomain,
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        rng = self._get_rng(seed, proposal_idx)
        if rng.random() < self.invalid_rate:
            return "def broken_syntax(:\n    pass", "Malformed syntax proposal", None

        dname = domain.name
        if dname == "bin_packing":
            w_rem = round(rng.uniform(-3.0, 1.0), 3)
            w_item = round(rng.uniform(0.1, 2.0), 3)
            thresh = round(rng.uniform(0.01, 0.2), 3)
            p_exp = rng.choice([1, 2])
            code = (
                f"def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                f"    # Independent heuristic variant {proposal_idx}\n"
                f"    rem = remaining_capacity - item\n"
                f"    if rem < {thresh} * bin_capacity:\n"
                f"        return 1000.0 - rem\n"
                f"    return {w_rem} * (rem ** {p_exp}) + {w_item} * item\n"
            )
            desc = f"Independent candidate exploring rem threshold {thresh} and item weight {w_item}"
            return code, desc, None

        elif dname == "graph_coloring":
            w_sat = round(rng.uniform(500.0, 20000.0), 1)
            w_udeg = round(rng.uniform(0.5, 5.0), 2)
            w_deg = round(rng.uniform(-1.0, 2.0), 2)
            code = (
                f"def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
                f"    # Independent vertex priority variant {proposal_idx}\n"
                f"    return float(saturation * {w_sat} + uncolored_degree * {w_udeg} + degree * {w_deg})\n"
            )
            desc = f"Independent candidate with saturation weight {w_sat} and uncolored degree weight {w_udeg}"
            return code, desc, None

        elif dname == "pfsp":
            w_tot = round(rng.uniform(0.8, 1.2), 3)
            w_slope = round(rng.uniform(-0.8, 0.8), 3)
            w_spread = round(rng.uniform(-0.5, 0.5), 3)
            code = (
                f"def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
                f"    # Independent PFSP priority variant {proposal_idx}\n"
                f"    slope = last_machine_time - first_machine_time\n"
                f"    spread = max_time - min_time\n"
                f"    return float({w_tot} * total_time + {w_slope} * slope + {w_spread} * spread)\n"
            )
            desc = f"Independent candidate with total_time weight {w_tot} and slope weight {w_slope}"
            return code, desc, None

        return "def priority(*args): return 0.0", "Fallback default", None

    def generate_refinement(
        self,
        domain: ProblemDomain,
        champion: SearchCandidate,
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        rng = self._get_rng(seed, proposal_idx)
        if rng.random() < self.invalid_rate:
            return "def priority(invalid): return", "Syntax error in refinement", None

        # Perturb numeric constants in champion code
        def perturb(match):
            val = float(match.group(0))
            scale = rng.uniform(0.85, 1.15)
            new_val = round(val * scale, 3)
            return str(new_val)

        mutated_code = re.sub(r"\b\d+\.\d+\b", perturb, champion.code)
        if mutated_code == champion.code:
            # Fallback if no floats: add fine-tuning term
            mutated_code = champion.code.strip() + f"\n    # Refinement adjustment {proposal_idx}\n"

        desc = f"Refinement of champion {champion.candidate_id} with fine-tuned parameters"
        hyp = f"Slight parametric perturbation to optimize boundary decisions around champion {champion.candidate_id}"
        return mutated_code, desc, hyp

    def generate_variation(
        self,
        domain: ProblemDomain,
        parents: List[SearchCandidate],
        population: List[SearchCandidate],
        trajectory_id: int,
        proposal_idx: int,
        seed: int,
        island_id: Optional[int] = None
    ) -> Tuple[str, str, Optional[str]]:
        rng = self._get_rng(seed, proposal_idx)
        if rng.random() < self.invalid_rate:
            return "def priority(broken syntax", "Variation syntax error", None

        primary = parents[0]
        dname = domain.name

        # Island-specific bias
        bias = ""
        if island_id == 0:  # Exploitation
            scale = rng.uniform(0.95, 1.05)
            bias = "Exploitation island fine-tuning"
        elif island_id == 1:  # Non-linear exploration
            scale = rng.uniform(0.7, 1.4)
            bias = "Exploration island broad search"
        else:  # Robustness / tie-breaking
            scale = rng.uniform(0.85, 1.15)
            bias = "Robustness island structural search"

        def perturb(match):
            val = float(match.group(0))
            return str(round(val * scale, 3))

        mutated_code = re.sub(r"\b\d+\.\d+\b", perturb, primary.code)
        desc = f"Evolutionary variation of {primary.candidate_id} ({bias})"
        hyp = f"Island {island_id} variation adjusting weights by factor {scale:.2f}"
        return mutated_code, desc, hyp

    def generate_evidence_guided(
        self,
        domain: ProblemDomain,
        champion: SearchCandidate,
        diagnostics: Dict[str, Any],
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        rng = self._get_rng(seed, proposal_idx)
        if rng.random() < self.invalid_rate:
            return "def priority(invalid_code): return", "Evidence-guided syntax error", None

        dname = domain.name
        worst_idx = diagnostics.get("worst_instance_idx", 0)

        if dname == "bin_packing":
            hyp = f"Targeted repair for worst stream #{worst_idx}: tighten threshold to prevent overfilling high-residual bins"
            code = (
                "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                "    # Evidence-guided repair\n"
                "    rem = remaining_capacity - item\n"
                "    if rem < 0.03 * bin_capacity:\n"
                "        return 10000.0 - rem\n"
                "    return -(rem ** 1.5) + 0.1 * item\n"
            )
            return code, f"Evidence-guided candidate fixing worst stream #{worst_idx}", hyp

        elif dname == "graph_coloring":
            hyp = f"Targeted repair for graph #{worst_idx}: quadratic saturation weighting dominates degree tie-breaking"
            code = (
                "def vertex_priority(degree: int, saturation: int, uncolored_degree: int, vertex_id: int) -> float:\n"
                "    # Evidence-guided repair\n"
                "    return float((saturation ** 2) * 5000.0 + uncolored_degree * 2.0 + degree * 0.5)\n"
            )
            return code, f"Evidence-guided candidate fixing graph #{worst_idx}", hyp

        elif dname == "pfsp":
            hyp = f"Targeted repair for instance #{worst_idx}: prioritize jobs with smaller first_machine_time to avoid pipeline stalls"
            code = (
                "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
                "    # Evidence-guided repair\n"
                "    slope = last_machine_time - first_machine_time\n"
                "    return float(total_time + 1.2 * slope - 0.3 * first_machine_time)\n"
            )
            return code, f"Evidence-guided candidate fixing instance #{worst_idx}", hyp

        return self.generate_refinement(domain, champion, trajectory_id, proposal_idx, seed)


class LiveLLMGenerator(SearchGenerator):
    """
    Connects to live LLM server (OmniRoute / OpenAI compatible) to generate frontier heuristic proposals.
    Strictly forbids simulated fallbacks or synthetic stand-ins on request failures.
    """
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:20128/v1/chat/completions",
        model: str = "nvidia/nvidia/nemotron-3-super-120b-a12b",
        api_key: Optional[str] = None,
        timeout: int = 120,
        query_log_path: Optional[str] = None
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY") or os.environ.get("STAGE4_API_KEY") or os.environ.get("OPENAI_API_KEY") or "mock-key"
        self.timeout = timeout
        self.query_log_path = query_log_path

    def _query_model(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        call_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 2048,
            "stream": False
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        max_retries = 3
        last_exception = None
        res_obj = None
        latency_sec = 0.0

        for attempt in range(1, max_retries + 1):
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    latency_sec = round(time.time() - t0, 3)
                    res_obj = json.loads(raw_bytes.decode("utf-8"))
                    break
            except Exception as e:
                last_exception = e
                latency_sec = round(time.time() - t0, 3)
                if attempt < max_retries:
                    wait_time = attempt * 3.0
                    print(f" [API transient failure: {e}; retrying in {wait_time}s (attempt {attempt}/{max_retries})...]", flush=True)
                    time.sleep(wait_time)
                else:
                    # STOP AND RAISE: zero silent fallback allowed
                    raise RuntimeError(f"Live LLM API request failed to {self.base_url} after {max_retries} attempts (model={self.model}): {e}") from e

        # Model verification
        returned_model = res_obj.get("model", "")
        if "nemotron" not in returned_model.lower() and returned_model != self.model:
            raise RuntimeError(f"Model verification failed: Expected Nemotron model, but received '{returned_model}'")

        choice = res_obj["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        usage = res_obj.get("usage", {})

        record = {
            "timestamp": time.time(),
            "latency_sec": latency_sec,
            "model": returned_model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
            "content": content,
            "reasoning_content": reasoning,
            "usage": usage,
            "context": call_context or {}
        }

        if self.query_log_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.query_log_path)), exist_ok=True)
            with open(self.query_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

        return record

    def _extract_code(self, response_text: str, func_name: str) -> str:
        # Search for markdown python blocks
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, response_text, re.DOTALL)
        if matches:
            for m in reversed(matches):
                if f"def {func_name}" in m:
                    return m.strip()
            return matches[-1].strip()

        # If not in markdown blocks, search for def func_name directly in raw text
        lines = response_text.splitlines()
        start_idx = -1
        for i, line in enumerate(lines):
            if f"def {func_name}" in line:
                start_idx = i
                break
        if start_idx != -1:
            return "\n".join(lines[start_idx:]).strip()

        # If neither, return the raw text (will fail AST verification and record genuine failure)
        return response_text.strip()

    def generate_independent(
        self,
        domain: ProblemDomain,
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        user_prompt = (
            f"Propose a novel, innovative heuristic policy function `{domain.function_name}` for {domain.name}.\n"
            f"Interface:\n{domain.function_signature}\n\n"
            f"Think outside the box. Implement a creative online packing policy.\n"
            f"IMPORTANT: You MUST conclude your answer with the complete Python code inside a ```python ``` markdown block.\n"
            f"The function must be named `{domain.function_name}` and use only math library functions."
        )
        ctx = {"arm": "arm_a_best_of_n", "trajectory_id": trajectory_id, "proposal_idx": proposal_idx}
        res = self._query_model(domain.system_prompt, user_prompt, temperature=0.85, call_context=ctx)
        text_to_search = res["content"] if ("```" in res["content"] or f"def {domain.function_name}" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = self._extract_code(text_to_search, domain.function_name)
        return code, f"Independent LLM proposal {proposal_idx}", None

    def generate_refinement(
        self,
        domain: ProblemDomain,
        champion: SearchCandidate,
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        user_prompt = (
            f"You are refining the current champion heuristic for {domain.name}.\n"
            f"Current Champion Code:\n```python\n{champion.code}\n```\n"
            f"Champion Performance: Score = {champion.train_eval.raw_score if champion.train_eval else 'N/A'}, "
            f"Relative Gap vs Baseline = {champion.train_eval.relative_gap * 100:.2f}%.\n\n"
            f"Analyze how this heuristic behaves and propose a targeted, improved version of `{domain.function_name}`.\n"
            f"IMPORTANT: You MUST conclude your answer with the improved Python code inside a ```python ``` markdown block.\n"
            f"The function must be named `{domain.function_name}` and use only math library functions."
        )
        ctx = {"arm": "arm_b_refinement", "trajectory_id": trajectory_id, "proposal_idx": proposal_idx, "champion_id": champion.candidate_id}
        res = self._query_model(domain.system_prompt, user_prompt, temperature=0.6, call_context=ctx)
        text_to_search = res["content"] if ("```" in res["content"] or f"def {domain.function_name}" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = self._extract_code(text_to_search, domain.function_name)
        return code, f"Iterative refinement of {champion.candidate_id}", "Targeted iterative improvement"

    def generate_variation(
        self,
        domain: ProblemDomain,
        parents: List[SearchCandidate],
        population: List[SearchCandidate],
        trajectory_id: int,
        proposal_idx: int,
        seed: int,
        island_id: Optional[int] = None
    ) -> Tuple[str, str, Optional[str]]:
        p_strs = []
        for idx, p in enumerate(parents):
            score_str = f"{p.train_eval.raw_score:.4f}" if p.train_eval else "N/A"
            p_strs.append(f"Parent {idx + 1} (Score: {score_str}):\n```python\n{p.code}\n```")
        parents_block = "\n\n".join(p_strs)

        arm_name = f"arm_d_island_{island_id}" if island_id is not None else "arm_c_evolution"
        user_prompt = (
            f"You are generating an evolutionary offspring for {domain.name}.\n"
            f"Context: {arm_name}\n"
            f"Selected Parents:\n{parents_block}\n\n"
            f"Create an innovative offspring `{domain.function_name}` by recombining key ideas from the parents or mutating their parameters.\n"
            f"IMPORTANT: You MUST conclude your answer with the complete Python code inside a ```python ``` markdown block.\n"
            f"The function must be named `{domain.function_name}` and use only math library functions."
        )
        ctx = {"arm": arm_name, "trajectory_id": trajectory_id, "proposal_idx": proposal_idx, "parent_ids": [p.candidate_id for p in parents]}
        res = self._query_model(domain.system_prompt, user_prompt, temperature=0.75, call_context=ctx)
        text_to_search = res["content"] if ("```" in res["content"] or f"def {domain.function_name}" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = self._extract_code(text_to_search, domain.function_name)
        return code, f"Evolutionary variation from {[p.candidate_id for p in parents]}", f"Recombination on {arm_name}"

    def generate_evidence_guided(
        self,
        domain: ProblemDomain,
        champion: SearchCandidate,
        diagnostics: Dict[str, Any],
        trajectory_id: int,
        proposal_idx: int,
        seed: int
    ) -> Tuple[str, str, Optional[str]]:
        summary = diagnostics.get("diagnostic_summary", "Detailed failure diagnostic not available.")
        user_prompt = (
            f"Current Champion Heuristic Code:\n```python\n{champion.code}\n```\n\n"
            f"EVALUATOR DIAGNOSTIC EVIDENCE:\n{summary}\n\n"
            f"Instructions:\n"
            f"1. Formulate a specific improvement HYPOTHESIS explaining why the current heuristic failed on the identified instances.\n"
            f"2. Write the repaired `{domain.function_name}` implementing your hypothesis.\n"
            f"Format:\n"
            f"HYPOTHESIS: <your hypothesis here>\n"
            f"```python\n<your code here>\n```\n"
            f"The function must be named `{domain.function_name}` and use only math library functions."
        )
        ctx = {"arm": "arm_e_evidence", "trajectory_id": trajectory_id, "proposal_idx": proposal_idx, "champion_id": champion.candidate_id}
        res = self._query_model(domain.system_prompt, user_prompt, temperature=0.5, call_context=ctx)
        text_to_search = res["content"] if ("```" in res["content"] or f"def {domain.function_name}" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = self._extract_code(text_to_search, domain.function_name)
        hyp = "Evidence-guided repair"
        full_raw = f"{res['content']}\n{res['reasoning_content']}"
        if "HYPOTHESIS:" in full_raw:
            try:
                hyp_line = full_raw.split("HYPOTHESIS:")[1].split("\n")[0].strip()
                if hyp_line:
                    hyp = hyp_line
            except Exception:
                pass
        return code, f"Evidence-guided candidate {proposal_idx}", hyp
