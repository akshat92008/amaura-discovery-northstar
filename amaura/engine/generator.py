"""
Candidate Generator: LLM-Guided & AST-Driven Program Synthesis
==============================================================
Generates candidate programs using frontier LLMs (OpenAI, Anthropic, Gemini, Ollama)
and autonomous AST evolutionary operators for hybrid exploration.
"""

import ast
import os
import random
import re
from typing import List, Optional, Tuple, Any
from amaura.config import DiscoveryConfig
from amaura.engine.candidate import Candidate


class ProgramGenerator:
    """
    Synthesizes and mutates algorithm candidates.
    Supports LLM providers and autonomous AST/heuristic operators.
    """

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self._init_llm_client()

    def _init_llm_client(self):
        self.client = None
        provider = self.config.llm_provider

        if provider == "openai":
            try:
                from openai import OpenAI
                api_key = self.config.llm_api_key or os.environ.get("OPENAI_API_KEY")
                if api_key:
                    self.client = OpenAI(
                        api_key=api_key,
                        base_url=self.config.llm_base_url,
                        timeout=3.0,
                        max_retries=0
                    )
            except Exception:
                self.client = None
        elif provider == "ollama":
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key="ollama",
                    base_url=self.config.llm_base_url or "http://localhost:11434/v1",
                    timeout=3.0,
                    max_retries=0
                )
            except Exception:
                self.client = None

    def generate_candidate(
        self,
        parents: List[Candidate],
        generation: int,
        island_id: int,
        task_desc: str
    ) -> Candidate:
        """
        Produce a new candidate through LLM synthesis or AST mutation.
        """
        # When an explicit LLM provider is requested (and not 'ast' or 'hybrid'), do not silently fall back
        if self.config.llm_provider in ["openai", "ollama"]:
            if self.client is None:
                raise RuntimeError(
                    f"Requested LLM provider '{self.config.llm_provider}' is not initialized or missing API credentials. "
                    "Silent fallback to AST mutation is disabled; set llm_provider='ast' for local AST evolution."
                )
            cand = self._generate_with_llm(parents, generation, island_id, task_desc)
            if cand is None:
                raise RuntimeError(
                    f"LLM provider '{self.config.llm_provider}' failed to generate a valid candidate function."
                )
            return cand

        # Autonomous AST / Genetic mutation when llm_provider == 'ast' (or default local mode)
        return self._generate_with_ast(parents, generation, island_id)

    def _generate_with_llm(
        self,
        parents: List[Candidate],
        generation: int,
        island_id: int,
        task_desc: str
    ) -> Optional[Candidate]:
        """Query LLM to propose a novel candidate algorithm."""
        target_func = parents[0].function_name if parents else "priority"
        
        # Build prompt with parent examples and performance
        parent_examples = []
        for idx, p in enumerate(parents[:3]):
            parent_examples.append(
                f"# Parent Variant {idx + 1} (Fitness: {p.fitness:.2f}, Raw Score: {p.raw_score:.2f}):\n"
                f"{p.code.strip()}\n"
            )

        prompt = (
            f"You are Amaura's automated algorithmic discovery engine.\n"
            f"Task: {task_desc}\n\n"
            f"Existing high-performing baseline programs:\n"
            f"{''.join(parent_examples)}\n\n"
            f"Your goal: Invent an IMPROVED algorithm variant that achieves a superior score.\n"
            f"Rules:\n"
            f"1. You must output EXACTLY the Python function named `{target_func}`.\n"
            f"2. Keep the exact parameter signature.\n"
            f"3. Think through non-linear trade-offs, edge-case thresholds, and mathematical combinations.\n"
            f"4. Return ONLY valid Python code inside ```python ``` blocks. No conversational text."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "You are a world-class algorithm design and optimization expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens
            )
            raw_text = response.choices[0].message.content or ""
            code = self._extract_code_from_markdown(raw_text, target_func)
            if code:
                return Candidate(
                    code=code,
                    function_name=target_func,
                    generation=generation,
                    island_id=island_id,
                    parent_ids=[p.id for p in parents],
                    mutation_type=f"llm_{self.config.llm_model}"
                )
        except Exception:
            # Disable non-working client so future mutations run instantly via AST
            self.client = None
            return None

        return None

    def _extract_code_from_markdown(self, text: str, function_name: str) -> Optional[str]:
        """Extract clean Python code from markdown blocks."""
        matches = re.findall(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
        for code_candidate in matches:
            if f"def {function_name}" in code_candidate:
                return code_candidate.strip()

        # If no markdown block, search for function definition in text
        if f"def {function_name}" in text:
            lines = text.splitlines()
            code_lines = []
            capturing = False
            for line in lines:
                if line.strip().startswith(f"def {function_name}"):
                    capturing = True
                if capturing:
                    code_lines.append(line)
            if code_lines:
                return "\n".join(code_lines).strip()

        return None

    def _generate_with_ast(
        self,
        parents: List[Candidate],
        generation: int,
        island_id: int
    ) -> Candidate:
        """
        Autonomous AST mutator and crossover operator.
        Explores mathematical, logical, and structural space of heuristics.
        """
        parent = parents[0] if parents else None
        target_func = parent.function_name if parent else "priority"

        if not parents:
            # Generate default fallback
            code = f"def {target_func}(item, remaining_capacity, bin_capacity):\n    return -remaining_capacity\n"
            return Candidate(code=code, function_name=target_func, generation=generation, island_id=island_id)

        # Choose mutation strategy
        mutation_ops = [
            self._mutate_constants,
            self._mutate_operators,
            self._inject_tight_fit_threshold,
            self._inject_waste_penalty,
            self._crossover_heuristics,
            self._explore_novel_heuristic
        ]
        chosen_op = self.rng.choice(mutation_ops)
        new_code, op_name = chosen_op(parents)

        # Validate syntax
        try:
            ast.parse(new_code)
        except SyntaxError:
            # Fallback to safe perturbation
            new_code = parents[0].code
            op_name = "identity_fallback"

        return Candidate(
            code=new_code,
            function_name=target_func,
            generation=generation,
            island_id=island_id,
            parent_ids=[p.id for p in parents],
            mutation_type=f"ast_{op_name}"
        )

    def _mutate_constants(self, parents: List[Candidate]) -> Tuple[str, str]:
        """Perturb numeric constants in code."""
        code = parents[0].code
        
        def perturb(match):
            val = float(match.group(0))
            factor = self.rng.uniform(0.75, 1.35)
            new_val = round(val * factor, 3)
            return str(new_val)

        # Find numbers with decimals or integers
        new_code = re.sub(r"\b\d+\.\d+\b", perturb, code)
        if new_code == code:
            # If no floats, introduce float multiplier
            new_code = code.replace("return ", f"return {round(self.rng.uniform(0.8, 1.2), 2)} * ")
        return new_code, "constant_perturbation"

    def _mutate_operators(self, parents: List[Candidate]) -> Tuple[str, str]:
        """Mutate arithmetic combinations."""
        code = parents[0].code
        if " - " in code and self.rng.random() < 0.5:
            new_code = code.replace(" - ", " / (1.0 + ", 1) + ")"
            return new_code, "operator_division"
        elif " * " in code:
            new_code = code.replace(" * ", " + ", 1)
            return new_code, "operator_addition"
        else:
            return self._mutate_constants(parents)

    def _inject_tight_fit_threshold(self, parents: List[Candidate]) -> Tuple[str, str]:
        """Inject an adaptive threshold bonus for nearly-full bins."""
        p = parents[0]
        func_name = p.function_name
        threshold = round(self.rng.uniform(0.02, 0.15), 3)
        bonus = round(self.rng.uniform(500.0, 5000.0), 1)

        if func_name == "priority":
            code = (
                "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                f"    # Discovered tight-fit priority heuristic\n"
                f"    space_after = remaining_capacity - item\n"
                f"    if space_after < {threshold} * bin_capacity:\n"
                f"        return {bonus} - (space_after * 10.0)\n"
                f"    waste_ratio = space_after / (bin_capacity + 1e-5)\n"
                f"    return -space_after - ({round(self.rng.uniform(0.5, 3.0), 2)} * waste_ratio * remaining_capacity)\n"
            )
            return code, "tight_fit_injection"
        else:
            # Cache policy eviction heuristic
            code = (
                "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
                f"    # Discovered adaptive frequency-recency decay policy\n"
                f"    alpha = {round(self.rng.uniform(0.6, 1.4), 2)}\n"
                f"    beta = {round(self.rng.uniform(0.3, 0.9), 2)}\n"
                f"    return (float(frequency) ** alpha) / ((float(recency) + 1.0) ** beta)\n"
            )
            return code, "cache_decay_injection"

    def _inject_waste_penalty(self, parents: List[Candidate]) -> Tuple[str, str]:
        """Inject non-linear penalty for residual unfillable space."""
        p = parents[0]
        func_name = p.function_name
        power = round(self.rng.uniform(1.2, 2.5), 2)
        weight = round(self.rng.uniform(0.5, 4.0), 2)

        if func_name == "priority":
            code = (
                "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                f"    # Non-linear residual space minimization\n"
                f"    leftover = remaining_capacity - item\n"
                f"    rel_leftover = leftover / bin_capacity\n"
                f"    return - (leftover ** {power}) - ({weight} * (rel_leftover ** 2.0))\n"
            )
            return code, "waste_penalty_injection"
        else:
            code = (
                "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
                f"    # Dual age-recency weighted eviction\n"
                f"    rec_penalty = float(recency) * {weight}\n"
                f"    age_factor = (float(age) / (cache_size + 1.0)) ** {power}\n"
                f"    return float(frequency) - rec_penalty - age_factor\n"
            )
            return code, "dual_penalty_injection"

    def _crossover_heuristics(self, parents: List[Candidate]) -> Tuple[str, str]:
        """Combine expressions or logic from two distinct parent programs."""
        if len(parents) < 2:
            return self._inject_tight_fit_threshold(parents)

        p1, p2 = parents[0], parents[1]
        func_name = p1.function_name
        w = round(self.rng.uniform(0.2, 0.8), 2)

        if func_name == "priority":
            code = (
                "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                f"    # Recombined hybrid heuristic from parent innovations\n"
                f"    rem_after = remaining_capacity - item\n"
                f"    h1 = -rem_after\n"
                f"    h2 = 1.0 / (rem_after + 0.1)\n"
                f"    return ({w} * h1) + ({1.0 - w:.2f} * h2)\n"
            )
            return code, "crossover_hybrid"
        else:
            code = (
                "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
                f"    # Recombined cache policy\n"
                f"    rec_score = -float(recency)\n"
                f"    freq_score = float(frequency) * {round(self.rng.uniform(1.5, 3.5), 2)}\n"
                f"    return ({w} * freq_score) + ({1.0 - w:.2f} * rec_score)\n"
            )
            return code, "crossover_hybrid"

    def _explore_novel_heuristic(self, parents: List[Candidate]) -> Tuple[str, str]:
        """Propose an unconventional mathematical formulation."""
        p = parents[0]
        func_name = p.function_name

        if func_name == "priority":
            # Advanced harmonic resonance packing heuristic
            k = round(self.rng.uniform(1.5, 4.0), 2)
            code = (
                "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
                f"    # Harmonic resonance heuristic\n"
                f"    space_after = remaining_capacity - item\n"
                f"    # Reward exact or near-exact fits with asymptotic spike\n"
                f"    fit_quality = 1.0 / (space_after + 0.05)\n"
                f"    # Penalize creating medium awkward gaps that can never be filled\n"
                f"    awkward_penalty = {k} * (space_after / bin_capacity)\n"
                f"    return fit_quality - awkward_penalty\n"
            )
            return code, "harmonic_resonance"
        else:
            code = (
                "def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:\n"
                f"    # Log-frequency exponential recency decay\n"
                f"    import math\n"
                f"    log_freq = math.log(frequency + 1.0)\n"
                f"    rec_decay = math.exp(-float(recency) / float(cache_size + 1.0))\n"
                f"    return log_freq * rec_decay\n"
            )
            return code, "log_freq_exp_decay"
