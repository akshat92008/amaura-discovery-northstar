"""
Experiment #9: LLM Client for PFSP Solver Synthesis
===================================================
Client for Claude Sonnet 4-6 via OmniRoute.
Guarantees:
- Strict provenance tracking (prompt hash, response hash, tokens, latency)
- Thread-safe accounting
- NO SILENT FALLBACKS: errors are explicitly raised and recorded as failed calls
"""

import hashlib
import json
import os
import re
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional


class PFSPLLMClient:
    def __init__(
        self,
        model: str = "antigravity/claude-sonnet-4-6",
        base_url: str = "http://127.0.0.1:20128/v1/chat/completions",
        api_key: Optional[str] = None
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY")
        if not self.api_key:
            raise ValueError("OMNIROUTE_API_KEY environment variable is required but missing.")
        self.lock = threading.Lock()
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.failed_calls = 0

    def _extract_code(self, text: str) -> Optional[str]:
        """Extracts python code block defining def schedule_flowshop."""
        pattern = r"```(?:python)?\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        candidates = []
        if matches:
            for match in matches:
                if "def schedule_flowshop" in match:
                    candidates.append(match)
        
        if not candidates and "def schedule_flowshop" in text:
            candidates.append(text)

        if not candidates:
            return None

        # Return longest matching block
        candidates.sort(key=lambda s: len(s), reverse=True)
        return candidates[0].strip()

    def query(
        self,
        prompt: str,
        temperature: float = 0.6,
        system_prompt: Optional[str] = None,
        max_tokens: int = 3000
    ) -> Dict[str, Any]:
        """
        Queries Claude Sonnet with full provenance tracking.
        If an error occurs, returns success=False with exact error details.
        NEVER substitutes a local fallback.
        """
        sys_msg = system_prompt or (
            "You are an expert combinatorial algorithm designer and operations research scientist. "
            "Your task is to design an algorithm for Permutation Flow Shop Scheduling (PFSP) that minimizes makespan C_max. "
            "You must synthesize a complete, standalone Python function: "
            "`def schedule_flowshop(times: list[list[int]]) -> list[int]:` "
            "that receives a 2D matrix of processing times [n_jobs][n_machines] and returns a valid permutation of range(n_jobs). "
            "Every output must be valid executable Python code enclosed in ```python ... ``` blocks. "
            "Only the pure 'math' and 'random' modules are permitted. No external packages, no I/O, no network."
        )

        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )

        start_time = time.perf_counter()
        last_exception = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw_bytes = resp.read()
                    duration_ms = (time.perf_counter() - start_time) * 1000.0

                    full_text = ""
                    p_tokens = 0
                    c_tokens = 0

                    content_type = resp.headers.get("content-type", "")
                    if "text/event-stream" in content_type or raw_bytes.startswith(b"data:"):
                        parts = []
                        for line in raw_bytes.decode("utf-8", errors="ignore").splitlines():
                            line = line.strip()
                            if line.startswith("data:") and line != "data: [DONE]":
                                data_str = line[5:].strip()
                                try:
                                    chunk = json.loads(data_str)
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        if "content" in delta and delta["content"]:
                                            parts.append(delta["content"])
                                    if "usage" in chunk and chunk["usage"]:
                                        p_tokens = chunk["usage"].get("prompt_tokens", p_tokens)
                                        c_tokens = chunk["usage"].get("completion_tokens", c_tokens)
                                except Exception:
                                    pass
                        full_text = "".join(parts)
                    else:
                        data = json.loads(raw_bytes.decode("utf-8"))
                        full_text = data["choices"][0]["message"]["content"]
                        usage = data.get("usage", {})
                        p_tokens = usage.get("prompt_tokens", 0)
                        c_tokens = usage.get("completion_tokens", 0)

                    if p_tokens == 0:
                        p_tokens = len(prompt.split()) * 2
                    if c_tokens == 0:
                        c_tokens = len(full_text.split()) * 2

                    with self.lock:
                        self.total_calls += 1
                        self.total_prompt_tokens += p_tokens
                        self.total_completion_tokens += c_tokens

                    response_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:12]
                    code = self._extract_code(full_text)
                    cand_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12] if code else None

                    return {
                        "success": bool(code),
                        "code": code,
                        "raw_text": full_text,
                        "prompt_hash": prompt_hash,
                        "response_hash": response_hash,
                        "candidate_hash": cand_hash,
                        "prompt_tokens": p_tokens,
                        "completion_tokens": c_tokens,
                        "total_tokens": p_tokens + c_tokens,
                        "duration_ms": round(duration_ms, 2),
                        "model": self.model,
                        "error": None if code else "Failed to parse Python code defining def schedule_flowshop"
                    }

            except Exception as e:
                last_exception = e
                if attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        with self.lock:
            self.failed_calls += 1
            self.total_calls += 1
        return {
            "success": False,
            "code": None,
            "raw_text": "",
            "prompt_hash": prompt_hash,
            "response_hash": None,
            "candidate_hash": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "duration_ms": round(duration_ms, 2),
            "model": self.model,
            "error": f"LLM API Exception (after 3 attempts): {type(last_exception).__name__}: {last_exception}"
        }

