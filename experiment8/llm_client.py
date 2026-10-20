"""
Experiment #7: LLM Client for Full Solver Synthesis
====================================================
Client for Claude Sonnet 4-6 via OmniRoute.
Supports:
- Robust extraction of entire Python code blocks defining `def color_graph(adj)`
- Preservation of helper functions, classes, and subroutines
- Thread-safe token tracking and cryptographic hashing of prompts and responses
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


class SolverLLMClient:
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

    def query(
        self,
        prompt: str,
        temperature: float = 0.6,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2500
    ) -> Dict[str, Any]:
        """Query Claude Sonnet with full provenance tracking."""
        sys_msg = system_prompt or (
            "You are an expert combinatorial algorithm designer and computer science researcher. "
            "Your task is to design an algorithm for Vertex Graph Coloring that minimizes the total number of colors used. "
            "You must synthesize a complete, standalone Python function `def color_graph(adj: list[list[int]]) -> list[int]:` "
            "that receives an adjacency list and returns a valid vertex coloring (colors list of length len(adj)). "
            "You have full macro-algorithmic freedom: you may use greedy ordering, multi-pass recoloring, "
            "independent set extraction, local search, Kempe chains, backtracking, or hybrid heuristics. "
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
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
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
                    "duration_ms": round(duration_ms, 2),
                    "model": self.model,
                    "provider": "omniroute/antigravity",
                    "error": None if code else "Failed to parse Python code defining `def color_graph` from model output"
                }

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            with self.lock:
                self.failed_calls += 1
            return {
                "success": False,
                "code": None,
                "raw_text": "",
                "prompt_hash": prompt_hash,
                "response_hash": None,
                "candidate_hash": None,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "duration_ms": round(duration_ms, 2),
                "model": self.model,
                "provider": "omniroute/antigravity",
                "error": f"LLM Call Error: {str(e)}"
            }

    def _extract_code(self, text: str) -> Optional[str]:
        """Extract entire Python block containing `def color_graph`."""
        blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
        for b in blocks:
            if "def color_graph" in b:
                return b.strip()
        if "def color_graph" in text:
            # Fallback: extract from first def/import to end of text
            lines = text.splitlines()
            code_lines = []
            capturing = False
            for line in lines:
                if "def color_graph" in line or line.startswith("import ") or line.startswith("def "):
                    capturing = True
                if capturing:
                    code_lines.append(line)
            if code_lines:
                return "\n".join(code_lines).strip()
        return None
