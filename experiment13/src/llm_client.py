"""
Experiment #13 LLM Client
=========================
Queries Nvidia Nemotron 3 Super 120B via OmniRoute with:
- Strict token handling (max_tokens=4096)
- Robust dual-mode parsing (standard JSON + SSE fallback)
- Truncation detection (finish_reason == "length")
- Full SHA256 cryptographic provenance tracking
- Retries with exponential backoff
"""

import hashlib
import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional


class CloudSchedulingLLMClient:
    def __init__(
        self,
        model: str = "nvidia/nvidia/nemotron-3-super-120b-a12b",
        base_url: str = "http://127.0.0.1:20128/v1/chat/completions",
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        timeout: int = 120
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY")
        if not self.api_key:
            raise ValueError("OMNIROUTE_API_KEY environment variable is required but missing.")
        self.max_tokens = max_tokens
        self.timeout = timeout

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def extract_python_code(raw_response: str) -> str:
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, raw_response, re.DOTALL)
        if matches:
            candidates = [m.strip() for m in matches if "def select_node" in m]
            if candidates:
                return candidates[-1]
            return matches[-1].strip()

        if "def select_node" in raw_response:
            lines = raw_response.splitlines()
            start_idx = -1
            for i, line in enumerate(lines):
                if "def select_node" in line or "def select_pod" in line:
                    start_idx = i
                    break
            if start_idx != -1:
                return "\n".join(lines[start_idx:]).strip()

        return raw_response.strip()

    def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.6,
        max_retries: int = 4
    ) -> Dict[str, Any]:
        prompt_hash = self.sha256_text(prompt)

        sys_msg = system_prompt or (
            "You are a principal systems architect and cloud cluster optimization scientist. "
            "Your task is to design a high-performance Kubernetes-style pod scheduling policy "
            "that minimizes cluster operational costs and avoids stranded capacity. "
            "You must synthesize valid Python code defining: "
            "`def select_node(pod: dict, feasible_nodes: list[dict], state: dict) -> int:` "
            "(and optionally `def select_pod(pending_pods: list[dict], nodes: list[dict], state: dict) -> int:`) "
            "Every output must be valid executable Python enclosed in ```python ... ``` blocks. "
            "Only pure standard library modules ('math', 'random', 'collections', 'itertools', 'heapq', 'copy') are permitted. "
            "No file I/O, no network, no OS commands. Keep logic concise, fast, and numerically stable."
        )

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": False
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

                    content_type = resp.headers.get("content-type", "")
                    content = ""
                    finish_reason = "stop"
                    p_tokens = 0
                    c_tokens = 0
                    t_tokens = 0
                    model_resp = self.model

                    if "text/event-stream" in content_type or resp_bytes.startswith(b"data:"):
                        parts = []
                        for line in resp_bytes.decode("utf-8", errors="ignore").splitlines():
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
                                        fr = choices[0].get("finish_reason")
                                        if fr:
                                            finish_reason = fr
                                    if "usage" in chunk and chunk["usage"]:
                                        p_tokens = chunk["usage"].get("prompt_tokens", p_tokens)
                                        c_tokens = chunk["usage"].get("completion_tokens", c_tokens)
                                        t_tokens = chunk["usage"].get("total_tokens", t_tokens)
                                    if "model" in chunk:
                                        model_resp = chunk["model"]
                                except Exception:
                                    pass
                        content = "".join(parts)
                    else:
                        resp_json = json.loads(resp_bytes.decode("utf-8"))
                        choices = resp_json.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            content = msg.get("content", "")
                            finish_reason = choices[0].get("finish_reason", "stop")
                        usage = resp_json.get("usage", {})
                        p_tokens = usage.get("prompt_tokens", 0)
                        c_tokens = usage.get("completion_tokens", 0)
                        t_tokens = usage.get("total_tokens", 0)
                        model_resp = resp_json.get("model", self.model)

                    code = self.extract_python_code(content)
                    is_truncated = (finish_reason == "length")
                    resp_hash = self.sha256_text(content)
                    code_hash = self.sha256_text(code)

                    return {
                        "success": True,
                        "raw_response": content,
                        "code": code,
                        "prompt_hash": prompt_hash,
                        "response_hash": resp_hash,
                        "candidate_hash": code_hash,
                        "prompt_tokens": p_tokens,
                        "completion_tokens": c_tokens,
                        "total_tokens": t_tokens,
                        "finish_reason": finish_reason,
                        "is_truncated": is_truncated,
                        "duration_ms": duration_ms,
                        "model": model_resp,
                        "error": None
                    }

            except Exception as e:
                wait_sec = 2.0 * (attempt + 1)
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "raw_response": "",
                        "code": "",
                        "prompt_hash": prompt_hash,
                        "response_hash": "",
                        "candidate_hash": "",
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "finish_reason": "error",
                        "is_truncated": False,
                        "duration_ms": (time.perf_counter() - t0) * 1000.0,
                        "model": self.model,
                        "error": str(e)
                    }
                time.sleep(wait_sec)

        return {
            "success": False,
            "raw_response": "",
            "code": "",
            "prompt_hash": prompt_hash,
            "response_hash": "",
            "candidate_hash": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "finish_reason": "error",
            "is_truncated": False,
            "duration_ms": 0.0,
            "model": self.model,
            "error": "Max retries exceeded"
        }
