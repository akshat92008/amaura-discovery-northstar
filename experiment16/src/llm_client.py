"""
Experiment #16 LLM Client
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
            "that operates under continuous dynamic arrivals and departures of workloads. "
            "The objective is to minimize total cluster operational cost (active node-hours) and ensure 100% placement feasibility. "
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
            "max_tokens": self.max_tokens
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        req = urllib.request.Request(self.base_url, data=data_bytes, headers=headers, method="POST")

        last_error = None
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw_body = response.read().decode("utf-8")
                    latency_ms = (time.time() - start_time) * 1000.0

                    finish_reason = "stop"
                    content = ""
                    usage = {}

                    # Try standard JSON parsing
                    try:
                        resp_json = json.loads(raw_body)
                        choices = resp_json.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            content = msg.get("content", "")
                            finish_reason = choices[0].get("finish_reason", "stop")
                        usage = resp_json.get("usage", {})
                    except json.JSONDecodeError:
                        # Fallback: Parse Server-Sent Events (SSE) data stream
                        content_pieces = []
                        for line in raw_body.splitlines():
                            line_str = line.strip()
                            if line_str.startswith("data: ") and not line_str.endswith("[DONE]"):
                                json_part = line_str[6:].strip()
                                try:
                                    chunk = json.loads(json_part)
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        if "content" in delta and delta["content"]:
                                            content_pieces.append(delta["content"])
                                        if choices[0].get("finish_reason"):
                                            finish_reason = choices[0]["finish_reason"]
                                    if "usage" in chunk and chunk["usage"]:
                                        usage = chunk["usage"]
                                except Exception:
                                    pass
                        content = "".join(content_pieces)

                    is_truncated = (finish_reason == "length")
                    extracted_code = self.extract_python_code(content)
                    code_hash = self.sha256_text(extracted_code)

                    return {
                        "success": True,
                        "prompt_hash": prompt_hash,
                        "raw_response": content,
                        "extracted_code": extracted_code,
                        "code_hash": code_hash,
                        "finish_reason": finish_reason,
                        "is_truncated": is_truncated,
                        "latency_ms": latency_ms,
                        "attempt": attempt + 1,
                        "usage": usage,
                        "error": None
                    }

            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception) as e:
                last_error = str(e)
                time.sleep(1.0 * (2 ** attempt))

        return {
            "success": False,
            "prompt_hash": prompt_hash,
            "raw_response": "",
            "extracted_code": "",
            "code_hash": "",
            "finish_reason": "error",
            "is_truncated": False,
            "latency_ms": 0.0,
            "attempt": max_retries,
            "usage": {},
            "error": last_error
        }
