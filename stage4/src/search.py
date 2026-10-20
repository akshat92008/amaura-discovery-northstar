"""
Stage 4 Search Engine: Arm A (Independent Sampling) vs Arm C (Closed-Loop Evolution)
===================================================================================
Implements strictly budget-equalized arms for fair comparison:
- Arm A: Independent sampling of N candidates with zero feedback.
- Arm C: Evolutionary search with multi-island population and fitness feedback.
Both arms evaluate candidates exclusively against development streams (dev.json).
"""

import random
from typing import List, Dict, Any, Tuple, Optional
from stage4.src.archive import Stage4IslandArchive, Stage4Candidate
from stage4.src.client import Stage4LLMClient
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.simulator import (
    best_fit_priority, worst_fit_priority, first_fit_priority, almost_worst_fit_priority
)



SYSTEM_PROMPT = (
    "You are an expert algorithms researcher designing online bin packing heuristics.\n"
    "Your goal is to invent an online priority function `def priority(item, remaining_capacity, bin_capacity)`\n"
    "that minimizes the number of bins used on unknown item streams."
)


class LowValidityEarlyStopException(RuntimeError):
    """Raised when AI-only candidate validity is < 60% after the first 15 AI candidates of a trial."""
    pass


def get_canonical_seeds() -> List[Stage4Candidate]:
    """Generates canonical baseline seeds for search initialization."""
    c1 = Stage4Candidate(
        code="def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n    # Best Fit\n    return -(remaining_capacity - item)\n",
        function_name="priority",
        mutation_type="seed_best_fit",
        island_id=0,
        is_seed=True
    )
    c2 = Stage4Candidate(
        code="def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n    # Worst Fit\n    return remaining_capacity\n",
        function_name="priority",
        mutation_type="seed_worst_fit",
        island_id=1,
        is_seed=True
    )
    c3 = Stage4Candidate(
        code="def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n    # First Fit\n    return 0.0\n",
        function_name="priority",
        mutation_type="seed_first_fit",
        island_id=2,
        is_seed=True
    )
    c4 = Stage4Candidate(
        code=(
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    # Almost Worst Fit\n"
            "    space_after = remaining_capacity - item\n"
            "    if space_after < 0.05 * bin_capacity:\n"
            "        return 1000.0 - space_after\n"
            "    return remaining_capacity * 0.5\n"
        ),
        function_name="priority",
        mutation_type="seed_almost_worst_fit",
        island_id=0,
        is_seed=True
    )
    return [c1, c2, c3, c4]


def run_arm_a_search(
    client: Stage4LLMClient,
    evaluator: Stage4Evaluator,
    dev_streams: List[List[float]],
    candidate_slots: int = 50,
    seed: int = 40401
) -> Tuple[Stage4Candidate, Stage4IslandArchive]:
    """
    Arm A: Independent Best-of-N Sampling with Baseline Parity.
    Initializes with the identical canonical baseline seeds as Arm C,
    then samples (candidate_slots - len(seeds)) candidates independently.
    Controllable random seed is wired into query seeds.
    """
    rng = random.Random(seed)
    archive = Stage4IslandArchive(num_islands=1, capacity_per_island=candidate_slots, elite_capacity=5)

    # 1. Baseline Parity: Initialize with canonical seeds
    seeds = get_canonical_seeds()
    for seed_item in seeds:
        eval_res = evaluator.evaluate_candidate(seed_item.code, dev_streams, func_name="priority")
        seed_item.is_valid = eval_res.is_valid
        seed_item.fitness = eval_res.fitness
        if eval_res.diagnostics:
            seed_item.diagnostic_summary = eval_res.diagnostics.get("diagnostic_summary")
        archive.add(seed_item)

    remaining_slots = max(0, candidate_slots - len(seeds))

    prompt = (
        "Design a novel, high-performing online bin packing heuristic priority function in Python.\n\n"
        "Interface:\n"
        "```python\n"
        "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
        "```\n\n"
        "Rules:\n"
        "1. Return higher priority for bins where placement is superior.\n"
        "2. Do not use external libraries beyond `math`.\n"
        "3. Output ONLY the function inside ```python ``` markdown block.\n"
    )

    for slot in range(remaining_slots):
        step_seed = rng.randint(0, 1_000_000_000)
        res = client.query(
            prompt=f"{prompt}\n# Independent Attempt {slot + 1} of {remaining_slots}\n",
            system_prompt=SYSTEM_PROMPT,
            temperature=0.8,
            max_tokens=4096,
            expected_func="priority",
            max_retries=2,
            seed=step_seed
        )

        code = res["code"]
        diag_summary = None
        if code and code.strip():
            eval_res = evaluator.evaluate_candidate(code, dev_streams, func_name="priority")
            is_valid = eval_res.is_valid
            fitness = eval_res.fitness
            diag_summary = eval_res.diagnostics.get("diagnostic_summary") if eval_res.diagnostics else None
            error_message = res.get("error") if (not res.get("success") or res.get("error")) else eval_res.error_message
        else:
            is_valid = False
            fitness = float("inf")
            error_message = res.get("error") or "Failed to extract target function from response"

        cand = Stage4Candidate(
            code=code,
            function_name="priority",
            generation=slot,
            island_id=0,
            mutation_type="independent_sample",
            is_valid=is_valid,
            fitness=fitness,
            error_message=error_message,
            prompt_tokens=res.get("prompt_tokens", 0),
            completion_tokens=res.get("completion_tokens", 0),
            cost_usd=res.get("cost", 0.0),
            finish_reason=res.get("finish_reason"),
            is_truncation=res.get("is_truncation", False),
            is_seed=False,
            diagnostic_summary=diag_summary
        )
        archive.add(cand)

        # Early validity stopping rule:
        # If AI-only validity < 60% after the first 15 AI candidates of a trial, stop the run and print failure-reason counts.
        if archive.ai_total == 15:
            validity_ratio = archive.ai_valid / 15.0
            if validity_ratio < 0.60:
                print(f"\n[EARLY VALIDITY STOP] Arm A AI-only validity after 15 candidates is {archive.ai_valid}/15 ({validity_ratio * 100:.1f}%), strictly below 60.0% threshold.")
                print("Failure-reason counts:")
                for reason, count in sorted(archive.failure_reasons.items(), key=lambda x: -x[1]):
                    print(f"  - {reason}: {count}")
                raise LowValidityEarlyStopException(
                    f"Arm A AI-only validity {validity_ratio * 100:.1f}% ({archive.ai_valid}/15) < 60% after first 15 AI candidates. Stopping run."
                )

    best_cand = archive.get_best()
    if best_cand is None:
        # Fallback to Best-Fit if all candidates invalid
        bf_code = "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n    return -(remaining_capacity - item)\n"
        eval_res = evaluator.evaluate_candidate(bf_code, dev_streams)
        best_cand = Stage4Candidate(
            code=bf_code, function_name="priority", mutation_type="fallback_best_fit",
            is_valid=True, fitness=eval_res.fitness
        )

    return best_cand, archive


def run_arm_c_search(
    client: Stage4LLMClient,
    evaluator: Stage4Evaluator,
    dev_streams: List[List[float]],
    candidate_slots: int = 50,
    migration_interval: int = 5,
    seed: int = 40401
) -> Tuple[Stage4Candidate, Stage4IslandArchive]:
    """
    Arm C: Closed-Loop Program-Space Evolution.
    Uses multi-island population with fitness-guided mutation, tournament parent selection, and crossover.
    Controllable random seed is wired into parent selection and query generation.
    """
    rng = random.Random(seed)
    archive = Stage4IslandArchive(num_islands=3, capacity_per_island=6, elite_capacity=5)

    # 1. Initialize with canonical seeds
    seeds = get_canonical_seeds()
    for seed_item in seeds:
        eval_res = evaluator.evaluate_candidate(seed_item.code, dev_streams, func_name="priority")
        seed_item.is_valid = eval_res.is_valid
        seed_item.fitness = eval_res.fitness
        if eval_res.diagnostics:
            seed_item.diagnostic_summary = eval_res.diagnostics.get("diagnostic_summary")
        archive.add(seed_item)

    remaining_slots = max(0, candidate_slots - len(seeds))

    for slot in range(remaining_slots):
        island_id = slot % archive.num_islands
        parents = archive.get_parents(island_id=island_id, count=2, rng=rng)

        parent_descriptions = []
        for p_idx, p in enumerate(parents):
            p_text = f"# Parent Variant {p_idx + 1} (Normalized Excess Ratio: {p.fitness:.4f}):\n{p.code.strip()}\n"
            if p.diagnostic_summary:
                p_text += f"# Execution Diagnostic Profile for Parent {p_idx + 1}:\n# " + p.diagnostic_summary.replace("\n", "\n# ") + "\n"
            parent_descriptions.append(p_text)

        prompt = (
            "You are refining an online bin packing heuristic priority function using evolutionary feedback.\n\n"
            "Existing top-performing parent programs on development streams:\n"
            f"{''.join(parent_descriptions)}\n\n"
            "Your Goal: Invent an improved variant that achieves a LOWER normalized excess ratio.\n"
            "Rules:\n"
            "1. Must output EXACTLY `def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:`.\n"
            "2. Address the specific failure modes, distribution bottlenecks, and waste patterns identified above.\n"
            "3. Consider non-linear combinations of remaining capacity and item size.\n"
            "4. Output ONLY valid Python inside ```python ``` code blocks.\n"
        )

        step_seed = rng.randint(0, 1_000_000_000)
        res = client.query(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=4096,
            expected_func="priority",
            max_retries=2,
            seed=step_seed
        )

        code = res["code"]
        diag_summary = None
        if code and code.strip():
            eval_res = evaluator.evaluate_candidate(code, dev_streams, func_name="priority")
            is_valid = eval_res.is_valid
            fitness = eval_res.fitness
            diag_summary = eval_res.diagnostics.get("diagnostic_summary") if eval_res.diagnostics else None
            error_message = res.get("error") if (not res.get("success") or res.get("error")) else eval_res.error_message
        else:
            is_valid = False
            fitness = float("inf")
            error_message = res.get("error") or "Failed to extract target function from response"

        cand = Stage4Candidate(
            code=code,
            function_name="priority",
            generation=slot + len(seeds),
            island_id=island_id,
            parent_ids=[p.id for p in parents],
            mutation_type="evolutionary_step",
            is_valid=is_valid,
            fitness=fitness,
            error_message=error_message,
            prompt_tokens=res.get("prompt_tokens", 0),
            completion_tokens=res.get("completion_tokens", 0),
            cost_usd=res.get("cost", 0.0),
            finish_reason=res.get("finish_reason"),
            is_truncation=res.get("is_truncation", False),
            is_seed=False,
            diagnostic_summary=diag_summary
        )
        archive.add(cand)

        # Early validity stopping rule:
        # If AI-only validity < 60% after the first 15 AI candidates of a trial, stop the run and print failure-reason counts.
        if archive.ai_total == 15:
            validity_ratio = archive.ai_valid / 15.0
            if validity_ratio < 0.60:
                print(f"\n[EARLY VALIDITY STOP] Arm C AI-only validity after 15 candidates is {archive.ai_valid}/15 ({validity_ratio * 100:.1f}%), strictly below 60.0% threshold.")
                print("Failure-reason counts:")
                for reason, count in sorted(archive.failure_reasons.items(), key=lambda x: -x[1]):
                    print(f"  - {reason}: {count}")
                raise LowValidityEarlyStopException(
                    f"Arm C AI-only validity {validity_ratio * 100:.1f}% ({archive.ai_valid}/15) < 60% after first 15 AI candidates. Stopping run."
                )

        # Island migration
        if (slot + 1) % migration_interval == 0:
            archive.migrate(count=1)


    best_cand = archive.get_best()
    if best_cand is None:
        bf_code = "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n    return -(remaining_capacity - item)\n"
        eval_res = evaluator.evaluate_candidate(bf_code, dev_streams)
        best_cand = Stage4Candidate(
            code=bf_code, function_name="priority", mutation_type="fallback_best_fit",
            is_valid=True, fitness=eval_res.fitness
        )

    return best_cand, archive
