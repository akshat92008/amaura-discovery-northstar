"""
Experiment #5: Thread-Safe Stronger LLM Client for Rich-State Search
=====================================================================
Client for Claude Sonnet 4-6 via OmniRoute with thread-safe token accounting,
cryptographic hashing, SSE stream parsing, and extraction of `choose_bin`.
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


class StrongLLMClient:
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
        temperature: float = 0.5,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1500
    ) -> Dict[str, Any]:
        """Query Claude Sonnet with full provenance tracking."""
        sys_msg = system_prompt or (
            "You are an algorithm researcher. You will be given an algorithmic optimization problem. "
            "Write a complete, valid Python function that optimizes the stated objective. "
            "Return executable Python code in ```python ... ``` blocks. "
            "You may use standard arithmetic and the pure 'math' module. Output no external dependencies."
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
            with urllib.request.urlopen(req, timeout=45) as resp:
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
                    "error": None if code else "Failed to parse Python function from model output"
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
        """Extract Python function from markdown code block."""
        blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
        for b in blocks:
            if "def choose_bin" in b:
                return b.strip()
        if "def choose_bin" in text:
            lines = []
            capturing = False
            for line in text.splitlines():
                if line.strip().startswith("def choose_bin"):
                    capturing = True
                if capturing:
                    lines.append(line)
                    if line.startswith("def ") and not line.startswith("def choose_bin"):
                        break
            if lines:
                return "\n".join(lines).strip()
        return None
