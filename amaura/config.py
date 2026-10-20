"""
Amaura Engine Configuration
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class DiscoveryConfig:
    """Core evolutionary discovery configuration."""
    problem: str = "bin_packing"          # "bin_packing" or "cache_policy"
    generations: int = 50                 # Number of evolutionary generations
    population_size: int = 16             # Total population across islands
    num_islands: int = 3                  # Island model to maintain diversity
    migration_interval: int = 5           # Generations between island migrations
    migration_count: int = 2              # Number of individuals migrated
    elitism_count: int = 2                # Top solutions protected per island
    mutation_rate: float = 0.85           # Probability of mutation
    crossover_rate: float = 0.35          # Probability of crossover
    timeout_per_eval_sec: float = 2.0     # Sandbox timeout per evaluation
    seed: int = 42                        # Deterministic random seed
    output_dir: str = "amaura_runs"       # Results and checkpoint directory

    # LLM Settings
    llm_provider: str = "ast"             # "ast" (default offline), "openai", "anthropic", "gemini", "ollama", "auto"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1500

    # Benchmark instance counts
    train_instances: int = 40
    test_instances: int = 60
    generalization_instances: int = 40

    def __post_init__(self):
        # Auto-detect available API keys if provider is "auto"
        if self.llm_provider == "auto":
            if os.environ.get("OPENAI_API_KEY"):
                self.llm_provider = "openai"
                self.llm_api_key = os.environ.get("OPENAI_API_KEY")
            elif os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_API_KEY") != "freecc":
                self.llm_provider = "anthropic"
                self.llm_api_key = os.environ.get("ANTHROPIC_API_KEY")
            elif os.environ.get("GEMINI_API_KEY"):
                self.llm_provider = "gemini"
                self.llm_api_key = os.environ.get("GEMINI_API_KEY")
            else:
                # Default to autonomous AST/heuristic evolutionary mutator
                self.llm_provider = "ast"
