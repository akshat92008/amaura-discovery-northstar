"""
Centralized LLM configuration — replaces hard-coded proxy URLs (REPRO-1).
All LLM access across Amaura and Stage 4 should resolve through this module.
"""
import os
from typing import Dict, Any

LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:20128/v1/chat/completions")
LLM_MODEL: str = os.environ.get("LLM_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
LLM_MAX_TOKENS: int = int(os.environ.get("LLM_MAX_TOKENS", "4096"))


def get_config() -> Dict[str, Any]:
    """Retrieve runtime LLM configuration from environment with standard defaults."""
    return {
        "base_url": os.environ.get("LLM_BASE_URL", LLM_BASE_URL),
        "model": os.environ.get("LLM_MODEL", LLM_MODEL),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", LLM_MAX_TOKENS)),
    }
