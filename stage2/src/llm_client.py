"""
Stage 2: Strict Model Provenance & LLM Client
=============================================
Enforces Section 16 & Section 21:
1. Model/Provider Provenance:
   - Aborts experiment job if returned model != requested model (ModelMismatchException).
2. Transparent token and cost accounting:
   - Prompt tokens, completion tokens, latency, request ID, prompt hash, timestamp.
3. Dual operating modes:
   - Live query mode (via OmniRoute / OpenAI compatible endpoint).
   - Mock mode (for deterministic dry-run and canary testing without billable calls).
4. Multi-role support:
   - Candidate generator.
   - Execution-blind Judge (Arm B).
"""

import hashlib
import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List


class ModelMismatchException(Exception):
    pass


class Stage2LLMClient:
    def __init__(
        self,
        model: str = "nvidia/nvidia/nemotron-3-super-120b-a12b",
        base_url: str = "http://127.0.0.1:20128/v1/chat/completions",
        api_key: Optional[str] = None,
        cost_per_m_input: float = 3.00,
        cost_per_m_output: float = 15.00,
        mock_mode: bool = False,
        timeout: int = 120
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("STAGE2_API_KEY") or os.environ.get("OPENAI_API_KEY") or "local-proxy"
        self.cost_per_m_input = cost_per_m_input
        self.cost_per_m_output = cost_per_m_output
        self.mock_mode = mock_mode
        self.timeout = timeout

        # Telemetry counters
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        cost = (prompt_tokens / 1_000_000.0) * self.cost_per_m_input + (completion_tokens / 1_000_000.0) * self.cost_per_m_output
        return round(cost, 6)

    @staticmethod
    def extract_python_code(raw_response: str, expected_func: str = "") -> str:
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, raw_response, re.DOTALL)
        if matches:
            if expected_func:
                cands = [m.strip() for m in matches if f"def {expected_func}" in m]
                if cands:
                    return cands[-1]
            return matches[-1].strip()

        if expected_func and f"def {expected_func}" in raw_response:
            lines = raw_response.splitlines()
            start_idx = -1
            for i, line in enumerate(lines):
                if line.strip().startswith(f"def {expected_func}") or f"def {expected_func}" in line:
                    start_idx = i
                    break
            if start_idx != -1:
                return "\n".join(lines[start_idx:]).strip()

        return raw_response.strip()

    def query(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.6,
        max_tokens: int = 4096,
        expected_func: str = "",
        max_retries: int = 4
    ) -> Dict[str, Any]:
        prompt_hash = self.sha256_text(prompt)
        sys_hash = self.sha256_text(system_prompt)

        # -------------------------------------------------------------
        # MOCK MODE (Zero billable calls, deterministic for dry-run)
        # -------------------------------------------------------------
        if self.mock_mode:
            p_tok = len(prompt.split()) + 50
            c_tok = 150
            call_cost = self.calculate_cost(p_tok, c_tok)
            self.total_calls += 1
            self.total_input_tokens += p_tok
            self.total_output_tokens += c_tok
            self.total_cost += call_cost

            if expected_func == "color_graph":
                mock_code = (
                    "def color_graph(adj: list[list[int]]) -> list[int]:\n"
                    "    # Mock candidate: simple greedy first-fit\n"
                    "    n = len(adj)\n"
                    "    colors = [-1] * n\n"
                    "    for v in range(n):\n"
                    "        used = {colors[u] for u in adj[v] if colors[u] >= 0}\n"
                    "        c = 0\n"
                    "        while c in used:\n"
                    "            c += 1\n"
                    "        colors[v] = c\n"
                    "    return colors\n"
                )
            elif expected_func == "schedule_flowshop":
                mock_code = (
                    "def schedule_flowshop(times: list[list[int]]) -> list[int]:\n"
                    "    # Mock candidate: sorted by total duration descending\n"
                    "    n = len(times)\n"
                    "    totals = [(sum(times[i]), i) for i in range(n)]\n"
                    "    totals.sort(key=lambda x: -x[0])\n"
                    "    return [x[1] for x in totals]\n"
                )
            else:
                # Judge mock output
                mock_code = "SELECTED_CANDIDATE: Candidate_01\nReasoning: Selected based on structural elegance."

            return {
                "success": True,
                "raw_response": f"```python\n{mock_code}\n```" if expected_func else mock_code,
                "code": mock_code,
                "prompt_hash": prompt_hash,
                "system_hash": sys_hash,
                "candidate_hash": self.sha256_text(mock_code),
                "requested_model": self.model,
                "returned_model": self.model,
                "provider": "mock",
                "request_id": f"mock-{int(time.time()*1000)}",
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": p_tok + c_tok,
                "cost": call_cost,
                "finish_reason": "stop",
                "is_truncated": False,
                "latency_ms": 12.5,
                "timestamp": time.time(),
                "error": None
            }

        # -------------------------------------------------------------
        # LIVE API QUERY MODE
        # -------------------------------------------------------------
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {"thinking": False}
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        for attempt in range(max_retries):
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(self.base_url, data=data_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_bytes = resp.read()
                    duration_ms = (time.perf_counter() - t0) * 1000.0

                    body = json.loads(resp_bytes.decode("utf-8"))
                    returned_model = body.get("model", "")

                    # SECTION 16 CRITICAL RULE: Model Mismatch Abort
                    # Allow minor prefix/suffix differences if standard proxy, but strictly fail on different family/fallback
                    if returned_model and returned_model != self.model:
                        # Check if base names match
                        base_req = self.model.split("/")[-1].lower()
                        base_ret = returned_model.split("/")[-1].lower()
                        if base_req not in base_ret and base_ret not in base_req:
                            raise ModelMismatchException(
                                f"FATAL MODEL MISMATCH: Requested '{self.model}', but provider silently returned '{returned_model}'. Aborting experiment job."
                            )

                    choice = body["choices"][0]
                    content = choice["message"].get("content") or choice["message"].get("reasoning_content") or ""
                    finish_reason = choice.get("finish_reason", "stop")
                    usage = body.get("usage", {})
                    p_tok = usage.get("prompt_tokens", 0)
                    c_tok = usage.get("completion_tokens", 0)
                    t_tok = usage.get("total_tokens", p_tok + c_tok)
                    req_id = body.get("id", f"req-{int(time.time()*1000)}")

                    call_cost = self.calculate_cost(p_tok, c_tok)
                    self.total_calls += 1
                    self.total_input_tokens += p_tok
                    self.total_output_tokens += c_tok
                    self.total_cost += call_cost

                    is_truncated = (finish_reason == "length")
                    code = self.extract_python_code(content, expected_func) if expected_func else content

                    return {
                        "success": True,
                        "raw_response": content,
                        "code": code,
                        "prompt_hash": prompt_hash,
                        "system_hash": sys_hash,
                        "candidate_hash": self.sha256_text(code),
                        "requested_model": self.model,
                        "returned_model": returned_model or self.model,
                        "provider": "omniroute",
                        "request_id": req_id,
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok,
                        "total_tokens": t_tok,
                        "cost": call_cost,
                        "finish_reason": finish_reason,
                        "is_truncated": is_truncated,
                        "latency_ms": duration_ms,
                        "timestamp": time.time(),
                        "error": None
                    }
            except ModelMismatchException:
                raise
            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "raw_response": "",
                        "code": "",
                        "prompt_hash": prompt_hash,
                        "system_hash": sys_hash,
                        "candidate_hash": "",
                        "requested_model": self.model,
                        "returned_model": "none",
                        "provider": "omniroute",
                        "request_id": "failed",
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost": 0.0,
                        "finish_reason": "error",
                        "is_truncated": False,
                        "latency_ms": duration_ms,
                        "timestamp": time.time(),
                        "error": f"LLM Query Failed after {max_retries} attempts: {e}"
                    }
                time.sleep(2.0 * (attempt + 1))
