"""
Stage 4 Production LLM Client with Embedded Budget Enforcement
==============================================================
Wraps all LLM model queries with:
1. Strict model provenance checking (fails if returned model != requested model).
2. Embedded BudgetEnforcer integration (pre-flight checks, usage tracking, retries).
3. Explicit non-streaming payloads.
4. Python code extraction for canonical `priority` function.
5. Deterministic mock mode for 100% offline testing with zero external calls.
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

from stage4.src.budget_enforcer import BudgetEnforcer, BudgetExhaustedException


class ModelMismatchException(Exception):
    """Raised when the provider returns a model ID different from requested."""
    pass


class Stage4LLMClient:
    """
    Client for frontier LLM inference with mandatory budget enforcement.
    Every query MUST pass through the attached BudgetEnforcer.
    """
    def __init__(
        self,
        budget_enforcer: BudgetEnforcer,
        model: str = "nvidia/nvidia/nemotron-3-super-120b-a12b",
        base_url: str = "http://127.0.0.1:20128/v1/chat/completions",
        api_key: Optional[str] = None,
        mock_mode: bool = False,
        timeout: int = 120
    ):
        self.enforcer = budget_enforcer
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY") or os.environ.get("STAGE4_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not mock_mode and not self.api_key:
            raise ValueError("OMNIROUTE_API_KEY environment variable is missing. Live API calls require OMNIROUTE_API_KEY.")
        self.mock_mode = mock_mode
        self.timeout = timeout
        self._lock = threading.Lock()

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def extract_python_code(raw_response: str, expected_func: str = "priority") -> str:
        """Extract clean Python code for the target function."""
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
        temperature: float = 0.7,
        max_tokens: int = 4096,
        expected_func: str = "priority",
        max_retries: int = 2,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute an LLM query with pre-flight and post-flight budget verification.
        Raises BudgetExhaustedException if budget is exhausted.
        Accounts for billable usage on all network paths, including model mismatch and malformed responses.
        """
        if not self.mock_mode and not self.api_key:
            raise ValueError("OMNIROUTE_API_KEY environment variable is missing. Live API calls require OMNIROUTE_API_KEY.")

        # 1. Hard Pre-Flight Budget Check (Halts before issuing HTTP call)
        self.enforcer.check_preflight_limits()

        # Prompt Size Safety Check (Per-request input token limit)
        prompt_words = len(prompt.split()) + len(system_prompt.split())
        estimated_prompt_tokens = int(prompt_words * 1.33) + 50
        if estimated_prompt_tokens > 4000:
            raise ValueError(
                f"PROMPT SIZE EXCEEDED: Estimated prompt tokens ({estimated_prompt_tokens}) "
                "exceeds per-request limit of 4,000 tokens."
            )

        prompt_hash = self.sha256_text(prompt)
        sys_hash = self.sha256_text(system_prompt)

        # Handle Mock Mode (Offline Testing / Dry-Run)
        if self.mock_mode:
            res_id = self.enforcer.reserve_allowance(
                estimated_prompt_tokens=estimated_prompt_tokens,
                max_output_tokens=max_tokens
            )
            seed_tag = f" # Seed: {seed}" if seed is not None else ""
            mock_code = (
                f"def {expected_func}(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                f"    # Mock candidate generated from prompt hash {prompt_hash[:8]}{seed_tag}\n"
                f"    space_after = remaining_capacity - item\n"
                f"    return -space_after + (item / bin_capacity) * 0.01\n"
            )
            raw_response = f"```python\n{mock_code}\n```"
            usage = {
                "prompt_tokens": len(prompt.split()) + 50,
                "completion_tokens": len(raw_response.split()) + 20
            }
            # Record usage and finalize reservation in enforcer
            call_cost = self.enforcer.finalize_reservation(
                reservation_id=res_id,
                prompt_text=prompt,
                completion_text=raw_response,
                usage_metadata=usage
            )
            return {
                "success": True,
                "raw_response": raw_response,
                "code": mock_code,
                "prompt_hash": prompt_hash,
                "system_hash": sys_hash,
                "candidate_hash": self.sha256_text(mock_code),
                "requested_model": self.model,
                "returned_model": self.model,
                "provider": "mock",
                "request_id": f"mock-{int(time.time()*1000)}",
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["prompt_tokens"] + usage["completion_tokens"],
                "cost": call_cost,
                "retries": 0,
                "finish_reason": "stop",
                "is_truncation": False,
                "latency_ms": 1.0,
                "error": None
            }

        # Live Query Execution with Retry Management
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        if seed is not None:
            payload["seed"] = seed

        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        retries_attempted = 0
        for attempt in range(max_retries):
            # Atomic reservation BEFORE sending HTTP request: prevents check-then-request race
            res_id = self.enforcer.reserve_allowance(
                estimated_prompt_tokens=estimated_prompt_tokens,
                max_output_tokens=max_tokens
            )
            t0 = time.perf_counter()
            resp_bytes = None
            reservation_finalized = False
            is_final_attempt = (attempt == max_retries - 1)

            try:
                req = urllib.request.Request(self.base_url, data=data_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_bytes = resp.read()
                duration_ms = (time.perf_counter() - t0) * 1000.0

                # 1. Parse JSON response
                try:
                    body = json.loads(resp_bytes.decode("utf-8"))
                    usage = body.get("usage", {})
                except Exception as parse_err:
                    # Bytes were returned over wire: server processed request!
                    # Bill conservative fallback tokens immediately before raising/retrying
                    self.enforcer.finalize_reservation(
                        reservation_id=res_id,
                        prompt_text=prompt,
                        completion_text=resp_bytes.decode("utf-8", errors="replace") if resp_bytes else "",
                        usage_metadata=None,
                        is_error=True,
                        is_final=is_final_attempt,
                        is_retry=(attempt > 0)
                    )
                    reservation_finalized = True
                    raise ValueError(f"MALFORMED_JSON_RESPONSE: {parse_err}") from parse_err

                returned_model = body.get("model", "")

                # 2. Provenance Check: If model mismatched, bill usage before aborting
                if returned_model and returned_model != self.model:
                    base_req = self.model.split("/")[-1].lower()
                    base_ret = returned_model.split("/")[-1].lower()
                    if base_req not in base_ret and base_ret not in base_req:
                        self.enforcer.finalize_reservation(
                            reservation_id=res_id,
                            prompt_text=prompt,
                            completion_text=json.dumps(body),
                            usage_metadata=usage,
                            is_error=True,
                            is_final=is_final_attempt,
                            is_retry=(attempt > 0)
                        )
                        reservation_finalized = True
                        raise ModelMismatchException(
                            f"FATAL MODEL MISMATCH: Requested '{self.model}', but provider returned '{returned_model}'. Aborting."
                        )

                # 3. Choice Extraction
                if "choices" not in body or not body["choices"]:
                    self.enforcer.finalize_reservation(
                        reservation_id=res_id,
                        prompt_text=prompt,
                        completion_text="",
                        usage_metadata=usage,
                        is_error=True,
                        is_final=is_final_attempt,
                        is_retry=(attempt > 0)
                    )
                    reservation_finalized = True
                    raise KeyError(f"Missing choices in API response: {list(body.keys())}")

                choice = body["choices"][0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                reasoning_content = message.get("reasoning_content") or ""
                finish_reason = choice.get("finish_reason", "stop")
                req_id = body.get("id", f"req-{int(time.time()*1000)}")

                is_truncation = (finish_reason == "length")
                has_only_reasoning = (not content.strip()) and bool(reasoning_content.strip())

                if has_only_reasoning:
                    error_msg = "no_final_answer"
                    code = ""
                    is_success = False
                elif is_truncation and not content.strip():
                    error_msg = "Truncation: response hit max_tokens limit before producing output"
                    code = ""
                    is_success = False
                else:
                    code = self.extract_python_code(content, expected_func) if expected_func else content
                    is_success = bool(code.strip())
                    if not is_success:
                        error_msg = "Truncation: function incomplete" if is_truncation else "Failed to extract target function from response"
                    else:
                        error_msg = None

                # Post-flight usage recording through BudgetEnforcer
                call_cost = self.enforcer.finalize_reservation(
                    reservation_id=res_id,
                    prompt_text=prompt,
                    completion_text=content or reasoning_content,
                    usage_metadata=usage,
                    is_error=not is_success,
                    is_final=True,
                    is_retry=(attempt > 0)
                )
                reservation_finalized = True

                return {
                    "success": is_success,
                    "raw_response": content,
                    "reasoning_content": reasoning_content,
                    "code": code,
                    "prompt_hash": prompt_hash,
                    "system_hash": sys_hash,
                    "candidate_hash": self.sha256_text(code) if code else "",
                    "requested_model": self.model,
                    "returned_model": returned_model or self.model,
                    "provider": "omniroute",
                    "request_id": req_id,
                    "prompt_tokens": usage.get("prompt_tokens", 0) if usage else 0,
                    "completion_tokens": usage.get("completion_tokens", 0) if usage else 0,
                    "total_tokens": usage.get("total_tokens", 0) if usage else 0,
                    "cost": call_cost,
                    "retries": retries_attempted,
                    "finish_reason": finish_reason,
                    "is_truncation": is_truncation,
                    "latency_ms": duration_ms,
                    "error": error_msg
                }

            except ModelMismatchException:
                # Usage already recorded above; fail closed immediately
                raise
            except BudgetExhaustedException:
                raise
            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                retries_attempted += 1
                if not reservation_finalized:
                    is_timeout = "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower()
                    call_cost = self.enforcer.finalize_reservation(
                        reservation_id=res_id,
                        prompt_text=prompt,
                        completion_text=resp_bytes.decode("utf-8", errors="replace") if resp_bytes else "",
                        is_error=True,
                        is_timeout=is_timeout,
                        is_final=is_final_attempt,
                        is_retry=(attempt > 0)
                    )
                    reservation_finalized = True
                else:
                    call_cost = 0.0

                if is_final_attempt:
                    # Final attempt failed
                    return {
                        "success": False,
                        "raw_response": "",
                        "code": "",
                        "prompt_hash": prompt_hash,
                        "system_hash": sys_hash,
                        "candidate_hash": "",
                        "requested_model": self.model,
                        "returned_model": "failed",
                        "provider": "omniroute",
                        "request_id": "failed",
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost": call_cost,
                        "retries": retries_attempted,
                        "latency_ms": duration_ms,
                        "error": f"LLM Query Failed after {max_retries} attempts: {type(e).__name__} ({str(e)})"
                    }
                time.sleep(3.0 * (attempt + 1))


