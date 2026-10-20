"""
Stage 4 Dedicated Experiment Runner
===================================
Orchestrates paired trials of Arm A vs Arm C under strict budget and isolation gates:
1. Validates benchmark hashes and configuration before launch (fails closed).
2. Runs search phase using exclusively dev.json (20 streams).
3. Freezes candidate selections and writes checkpoint atomically.
4. Unseals hidden.json (100 streams) to evaluate frozen champions and baselines.
5. Computes paired Wilcoxon signed-rank test and 10,000 bootstrap CI for Delta_abs.
6. Enforces hard BudgetEnforcer limits in real request path.
"""

import fcntl
import hashlib
import json
import math
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

from stage4.src.benchmark import compute_sha256
from stage4.src.budget_enforcer import BudgetEnforcer, BudgetExhaustedException
from stage4.src.client import Stage4LLMClient
from stage4.src.evaluator import Stage4Evaluator
from stage4.src.search import run_arm_a_search, run_arm_c_search, LowValidityEarlyStopException
from stage4.src.simulator import (
    DeterministicBinPackingSimulator,
    best_fit_priority, worst_fit_priority, first_fit_priority, first_fit_decreasing_offline
)


def compute_paired_bootstrap_ci(
    diffs: List[float],
    n_resamples: int = 10000,
    alpha: float = 0.05,
    seed: int = 404
) -> Tuple[float, float]:
    """Computes paired bootstrap confidence interval for mean difference."""
    if not diffs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(diffs)
    boot_means = []
    for _ in range(n_resamples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    lower_idx = int((alpha / 2.0) * n_resamples)
    upper_idx = int((1.0 - alpha / 2.0) * n_resamples)
    return boot_means[lower_idx], boot_means[upper_idx]


def compute_experiment_fingerprint(
    model: str,
    dev_benchmark_sha256: str,
    candidate_slots: int,
    mock_mode: bool,
    protocol_version: int = 1,
    evaluator_version: str = "stage4_v1",
    holdout_key: str = "private_hidden"
) -> str:
    """Computes deterministic SHA-256 fingerprint of experiment configuration."""
    payload = {
        "candidate_slots": candidate_slots,
        "dev_benchmark_sha256": dev_benchmark_sha256,
        "evaluator_version": evaluator_version,
        "holdout_key": holdout_key,
        "mock_mode": mock_mode,
        "model": model,
        "protocol_version": protocol_version,
    }
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_wilcoxon_test(diffs: List[float]) -> Tuple[float, float]:
    """
    Computes two-sided Wilcoxon signed-rank test (statistic, p-value) for paired differences.
    Filters exact zeros (abs(d) <= 1e-9).
    Assigns average ranks to ties and preserves exact sign per observation.
    Uses exact distribution for small n (<= 15), normal approximation with continuity correction for n > 15.
    Deterministic reference matches scipy.stats.wilcoxon.
    """
    if not diffs or any(not math.isfinite(d) for d in diffs):
        return float("nan"), float("nan")

    non_zero = [d for d in diffs if abs(d) > 1e-9]
    n = len(non_zero)
    if n == 0:
        return 0.0, 1.0

    abs_diffs = [(abs(d), d) for d in non_zero]
    abs_diffs.sort(key=lambda x: x[0])

    ranks = []
    i = 0
    while i < n:
        j = i
        while j < n and abs(abs_diffs[j][0] - abs_diffs[i][0]) < 1e-9:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks.append((avg_rank, abs_diffs[k][1]))
        i = j

    w_pos = sum(r for r, d in ranks if d > 0)
    w_neg = sum(r for r, d in ranks if d < 0)
    t_stat = min(w_pos, w_neg)

    # For small n, exact two-sided p-value calculation
    if n <= 15:
        count_le = 0
        total_assignments = 1 << n
        for mask in range(total_assignments):
            w = 0.0
            for idx, (rank, _) in enumerate(ranks):
                if (mask >> idx) & 1:
                    w += rank
            if w <= t_stat:
                count_le += 1
        p_val = min(1.0, 2.0 * (count_le / total_assignments))
        return t_stat, round(p_val, 6)

    # Normal approximation for larger n
    mean_t = n * (n + 1) / 4.0
    var_t = n * (n + 1) * (2 * n + 1) / 24.0
    z = (abs(t_stat - mean_t) - 0.5) / math.sqrt(var_t)
    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
    return t_stat, round(p_val, 6)


def compute_wilcoxon_signed_rank(diffs: List[float]) -> float:
    """
    Computes two-sided Wilcoxon signed-rank test p-value for paired differences.
    """
    _, p_val = compute_wilcoxon_test(diffs)
    return p_val


def validate_trial_record(trial: Dict[str, Any]) -> None:
    """Validates structural and semantic integrity of a paired trial record."""
    if not isinstance(trial, dict):
        raise ValueError("MALFORMED_TRIAL_RECORD: Trial record must be a dict.")

    for key in ("trial_id", "seed", "arm_a", "arm_c", "delta_dev"):
        if key not in trial:
            raise ValueError(f"MALFORMED_TRIAL_RECORD: Missing required key '{key}'.")

    for arm_key in ("arm_a", "arm_c"):
        arm_data = trial[arm_key]
        if not isinstance(arm_data, dict):
            raise ValueError(f"MALFORMED_TRIAL_RECORD: '{arm_key}' must be a dict.")

        for fld in ("candidate_id", "code", "is_valid", "mutation_type", "is_seed", "dev_fitness"):
            if fld not in arm_data:
                raise ValueError(f"MALFORMED_TRIAL_RECORD: Missing field '{fld}' in {arm_key}.")

        if not isinstance(arm_data["is_valid"], bool):
            raise ValueError(f"MALFORMED_TRIAL_RECORD: 'is_valid' in {arm_key} must be a bool.")

        if not isinstance(arm_data["is_seed"], bool):
            raise ValueError(f"MALFORMED_TRIAL_RECORD: 'is_seed' in {arm_key} must be a bool.")

        if not isinstance(arm_data["mutation_type"], str) or not arm_data["mutation_type"]:
            raise ValueError(f"MALFORMED_TRIAL_RECORD: 'mutation_type' in {arm_key} must be a non-empty string.")

        # Contradiction checks
        if arm_data["is_seed"] and arm_data["mutation_type"] in ("independent_sample", "evolutionary_step"):
            raise ValueError(f"CONTRADICTORY_TRIAL_RECORD: {arm_key} marked as seed but has AI mutation type '{arm_data['mutation_type']}'.")

        if not arm_data["is_seed"] and arm_data["mutation_type"].startswith("seed_"):
            raise ValueError(f"CONTRADICTORY_TRIAL_RECORD: {arm_key} marked as AI candidate but has seed mutation type '{arm_data['mutation_type']}'.")

        fitness = arm_data["dev_fitness"]
        if arm_data["is_valid"]:
            if not isinstance(fitness, (int, float)) or not math.isfinite(fitness):
                raise ValueError(f"CONTRADICTORY_TRIAL_RECORD: {arm_key} marked valid but dev_fitness is non-finite: {fitness}.")
        else:
            if math.isfinite(fitness):
                raise ValueError(f"CONTRADICTORY_TRIAL_RECORD: {arm_key} marked invalid but dev_fitness is finite: {fitness}.")


class Stage4Runner:
    """
    Dedicated Stage 4 experimental runner enforcing fail-closed isolation and budgets.
    """
    def __init__(
        self,
        output_dir: str,
        benchmark_dir: str,
        max_cost_usd: float = 15.0,
        tripwire_cost_usd: float = 12.0,
        max_requests: int = 300,
        candidate_slots: int = 50,
        mock_mode: bool = True,
        holdout_key: str = "private_hidden",
        max_output_tokens: Optional[int] = None,
        max_input_tokens: Optional[int] = None
    ):
        self.output_dir = output_dir
        self.benchmark_dir = benchmark_dir
        self.max_cost_usd = max_cost_usd
        self.tripwire_cost_usd = tripwire_cost_usd
        self.max_requests = max_requests
        self.candidate_slots = candidate_slots
        self.mock_mode = mock_mode
        self.holdout_key = holdout_key

        os.makedirs(output_dir, exist_ok=True)
        self.ledger_path = os.path.join(output_dir, "budget.json")
        self.checkpoint_path = os.path.join(output_dir, "checkpoint.json")
        self.results_path = os.path.join(output_dir, "results.json")
        self.campaign_lock_path = os.path.join(output_dir, "campaign.lock")

        # Explicit token ceilings based on campaign scope
        self.max_input_tokens = max_input_tokens if max_input_tokens is not None else (1_500_000 if self.candidate_slots <= 50 else 3_000_000)
        self.max_output_tokens = max_output_tokens if max_output_tokens is not None else (700_000 if self.candidate_slots <= 50 else 1_200_000)

        self.enforcer = BudgetEnforcer(
            ledger_path=self.ledger_path,
            max_requests=self.max_requests,
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.max_output_tokens,
            max_cost_usd=self.max_cost_usd,
            tripwire_cost_usd=self.tripwire_cost_usd
        )
        self.client = Stage4LLMClient(
            budget_enforcer=self.enforcer,
            mock_mode=self.mock_mode
        )
        self.evaluator = Stage4Evaluator()
        self.simulator = DeterministicBinPackingSimulator()

    def validate_preconditions(self, is_pilot: bool = True) -> Tuple[List[List[float]], str]:
        """
        Validates benchmark files and SHA-256 hashes. Fails closed.
        Loads ONLY development streams into memory during search.
        In Phase 2 (is_pilot=False), also validates hidden benchmark hash pre-flight.
        """
        # In Phase 2 confirmatory mode, fail closed immediately if holdout key is overridden
        if not is_pilot and self.holdout_key != "private_hidden":
            raise ValueError(
                f"CONFIRMATORY PROTOCOL VIOLATION: Confirmatory holdout must be 'private_hidden', got '{self.holdout_key}'. "
                "CLI or programmatic override is strictly forbidden."
            )

        manifest_path = os.path.join(self.benchmark_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Missing benchmark manifest: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        dev_info = manifest.get("dev", {})
        dev_file = os.path.join(self.benchmark_dir, dev_info.get("path", "dev.json"))
        if not os.path.exists(dev_file):
            raise FileNotFoundError(f"Missing dev benchmark file: {dev_file}")

        computed_dev_hash = compute_sha256(dev_file)
        if computed_dev_hash != dev_info.get("sha256"):
            raise ValueError(
                f"CORRUPTED DEV BENCHMARK: expected {dev_info.get('sha256')}, got {computed_dev_hash}"
            )

        # In Phase 2 confirmatory mode, fail closed immediately if holdout benchmark is corrupted or missing
        if not is_pilot:
            if self.holdout_key not in manifest:
                raise KeyError(
                    f"Confirmatory holdout key '{self.holdout_key}' not found in manifest ({manifest_path}). "
                    f"Confirmatory mode requires '{self.holdout_key}'. No fallback permitted."
                )
            hidden_info = manifest[self.holdout_key]
            hidden_rel_path = hidden_info.get("path")
            if not hidden_rel_path:
                raise KeyError(f"Manifest entry '{self.holdout_key}' missing 'path' specification.")
            hidden_path = os.path.join(self.benchmark_dir, hidden_rel_path)
            if not os.path.exists(hidden_path):
                raise FileNotFoundError(f"Missing confirmatory holdout benchmark file: {hidden_path}")

            computed_hidden_hash = compute_sha256(hidden_path)
            expected_hidden_hash = hidden_info.get("sha256")
            if computed_hidden_hash != expected_hidden_hash:
                raise ValueError(
                    f"CORRUPTED CONFIRMATORY HOLDOUT BENCHMARK (CORRUPTED HIDDEN BENCHMARK): Expected {expected_hidden_hash}, got {computed_hidden_hash}"
                )

        with open(dev_file, "r", encoding="utf-8") as f:
            dev_data = json.load(f)

        dev_streams = [entry["items"] for entry in dev_data]
        return dev_streams, computed_dev_hash


    def run_paired_trial(
        self,
        trial_id: int,
        seed: int,
        dev_streams: List[List[float]]
    ) -> Dict[str, Any]:
        """Runs paired Arm A and Arm C search on development data."""
        # Arm A
        cand_a, arch_a = run_arm_a_search(
            client=self.client,
            evaluator=self.evaluator,
            dev_streams=dev_streams,
            candidate_slots=self.candidate_slots,
            seed=seed
        )

        # Arm C
        cand_c, arch_c = run_arm_c_search(
            client=self.client,
            evaluator=self.evaluator,
            dev_streams=dev_streams,
            candidate_slots=self.candidate_slots,
            seed=seed
        )


        delta_dev = cand_c.fitness - cand_a.fitness

        trial_record = {
            "trial_id": trial_id,
            "seed": seed,
            "arm_a": {
                "candidate_id": cand_a.id,
                "code": cand_a.code,
                "is_valid": cand_a.is_valid,
                "mutation_type": cand_a.mutation_type,
                "is_seed": cand_a.is_seed,
                "dev_fitness": round(cand_a.fitness, 6) if math.isfinite(cand_a.fitness) else cand_a.fitness,
                "error_message": cand_a.error_message,
                "stats": arch_a.get_stats()
            },
            "arm_c": {
                "candidate_id": cand_c.id,
                "code": cand_c.code,
                "is_valid": cand_c.is_valid,
                "mutation_type": cand_c.mutation_type,
                "is_seed": cand_c.is_seed,
                "dev_fitness": round(cand_c.fitness, 6) if math.isfinite(cand_c.fitness) else cand_c.fitness,
                "error_message": cand_c.error_message,
                "stats": arch_c.get_stats()
            },
            "delta_dev": round(delta_dev, 6) if math.isfinite(delta_dev) else delta_dev
        }
        validate_trial_record(trial_record)
        return trial_record

    def evaluate_on_hidden_benchmark(
        self,
        trials: List[Dict[str, Any]],
        hidden_streams: List[List[float]],
        phase_two_authorized: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates frozen trial champions and baselines on unsealed hidden benchmark.
        Fails closed if direct invocation lacks phase_two_authorized=True.
        """
        if not phase_two_authorized:
            raise RuntimeError(
                "PHASE 2 ACCESS FORBIDDEN: Direct call to evaluate_on_hidden_benchmark requires explicit phase_two_authorized=True."
            )

        # Baseline evaluations
        bf_res = self.simulator.evaluate_streams(hidden_streams, best_fit_priority)
        wf_res = self.simulator.evaluate_streams(hidden_streams, worst_fit_priority)
        ff_res = self.simulator.evaluate_streams(hidden_streams, first_fit_priority)

        # Offline FFD reference
        ffd_rhos = [first_fit_decreasing_offline(s)[2] for s in hidden_streams]
        ffd_mean_rho = sum(ffd_rhos) / len(ffd_rhos)

        diffs_hidden = []
        for trial in trials:
            code_a = trial["arm_a"]["code"]
            code_c = trial["arm_c"]["code"]

            eval_a = self.evaluator.evaluate_candidate(code_a, hidden_streams)
            eval_c = self.evaluator.evaluate_candidate(code_c, hidden_streams)

            trial["arm_a"]["hidden_fitness"] = round(eval_a.fitness, 6)
            trial["arm_c"]["hidden_fitness"] = round(eval_c.fitness, 6)
            diff = eval_c.fitness - eval_a.fitness
            trial["delta_hidden"] = round(diff, 6)
            diffs_hidden.append(diff)

        if diffs_hidden:
            mean_diff = sum(diffs_hidden) / len(diffs_hidden)
            ci_lower, ci_upper = compute_paired_bootstrap_ci(diffs_hidden)
            t_stat, p_wilcoxon = compute_wilcoxon_test(diffs_hidden)
        else:
            mean_diff = float("nan")
            ci_lower, ci_upper = float("nan"), float("nan")
            t_stat, p_wilcoxon = float("nan"), float("nan")

        # Gate 2 Multi-Criterion Evaluation
        bf_rho = bf_res["mean_excess_ratio"]
        arm_c_hidden_rhos = [t["arm_c"]["hidden_fitness"] for t in trials]
        mean_c_hidden_rho = sum(arm_c_hidden_rhos) / len(arm_c_hidden_rhos) if arm_c_hidden_rhos else float("nan")

        # Separate explicit gate checks with strict boundary and non-finite validation
        gate2_sufficient_trials = bool(len(trials) == 10)
        gate2_p_pass = bool(p_wilcoxon is not None and math.isfinite(p_wilcoxon) and p_wilcoxon < 0.05)
        gate2_magnitude_pass = bool(math.isfinite(mean_diff) and mean_diff <= -0.005)
        gate2_ci_excludes_zero = bool(math.isfinite(ci_upper) and ci_upper < 0.0)
        gate2_ci_reaches_threshold = bool(math.isfinite(ci_upper) and ci_upper < -0.005)
        gate2_beats_bf = bool(math.isfinite(mean_c_hidden_rho) and math.isfinite(bf_rho) and mean_c_hidden_rho < bf_rho)

        # Authoritative protocol requirement (STAGE4-PREREG-FINAL-001):
        # 1. Wilcoxon p < 0.05
        # 2. Mean delta <= -0.005 (magnitude threshold)
        # 3. 95% Bootstrap CI upper bound strictly below -0.005 (CI threshold)
        # 4. Arm C beats Best-Fit
        # 5. Full cohort (10 paired trials)
        gate2_confirmed = bool(
            gate2_sufficient_trials
            and gate2_p_pass
            and gate2_magnitude_pass
            and gate2_ci_reaches_threshold
            and gate2_beats_bf
        )

        return {
            "num_trials": len(trials),
            "mean_delta_hidden": round(mean_diff, 6) if math.isfinite(mean_diff) else None,
            "bootstrap_ci_95": [
                round(ci_lower, 6) if math.isfinite(ci_lower) else None,
                round(ci_upper, 6) if math.isfinite(ci_upper) else None
            ],
            "wilcoxon_test_statistic": t_stat if math.isfinite(t_stat) else None,
            "wilcoxon_p_value": p_wilcoxon if (p_wilcoxon is not None and math.isfinite(p_wilcoxon)) else None,
            "gate2_evaluation": {
                "sufficient_trials_count_10": gate2_sufficient_trials,
                "wilcoxon_p_less_than_05": gate2_p_pass,
                "mean_delta_at_or_beyond_threshold": gate2_magnitude_pass,
                "bootstrap_ci_excludes_zero": gate2_ci_excludes_zero,
                "bootstrap_ci_upper_strictly_below_target": gate2_ci_reaches_threshold,
                "beats_best_fit": gate2_beats_bf,
                "confirmatory_claim_supported": gate2_confirmed,
                "interpretation_if_nonsignificant": "Inconclusive / null result (does NOT demonstrate equivalence)"
            },
            "baselines": {
                "best_fit_mean_rho": bf_res["mean_excess_ratio"],
                "worst_fit_mean_rho": wf_res["mean_excess_ratio"],
                "first_fit_mean_rho": ff_res["mean_excess_ratio"],
                "ffd_offline_mean_rho": round(ffd_mean_rho, 6)
            }
        }


    def _save_checkpoint(self, trials: List[Dict[str, Any]], is_pilot: bool, config_fingerprint: str = ""):
        """Atomically saves completed trials to disk checkpoint bound to experiment fingerprint."""
        tmp_path = f"{self.checkpoint_path}.tmp.{os.getpid()}"
        data = {
            "timestamp": time.time(),
            "config_fingerprint": config_fingerprint,
            "completed_trials": trials,
            "is_pilot": is_pilot
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.checkpoint_path)

    def _load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Loads existing checkpoint if valid. Fails closed on corrupted checkpoint."""
        if not os.path.exists(self.checkpoint_path):
            return None
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Checkpoint JSON root is not an object.")
            return data
        except Exception as e:
            raise RuntimeError(f"CORRUPTED CHECKPOINT: Failed to load checkpoint from {self.checkpoint_path}: {e}")

    def execute_campaign(
        self,
        num_trials: int = 3,
        start_seed: int = 40401,
        is_pilot: bool = True,
        phase_two_authorized: bool = False,
        pilot_results_path: Optional[str] = None,
        strict_protocol: bool = True
    ) -> Dict[str, Any]:
        """
        Executes campaign under strict two-phase gating.
        Default is_pilot=True guarantees hidden.json is NEVER unsealed or read in pilot mode.
        Phase 2 (is_pilot=False) requires explicit phase_two_authorized=True and valid Gate 1 results.
        Validates hidden benchmark SHA-256 before unsealing.
        Resumes seamlessly from existing checkpoints if interrupted.
        Guarantees serial execution via campaign.lock.
        """
        # 1. Benchmark & manifest integrity preconditions (fail-closed immediately)
        dev_streams, dev_hash = self.validate_preconditions(is_pilot=is_pilot)

        # Deterministic configuration fingerprint
        fingerprint = compute_experiment_fingerprint(
            model=self.client.model,
            dev_benchmark_sha256=dev_hash,
            candidate_slots=self.candidate_slots,
            mock_mode=self.mock_mode,
            protocol_version=1,
            evaluator_version="stage4_v1",
            holdout_key="private_hidden"
        )

        # 2. Protocol Pre-flight Checks
        if is_pilot:
            if strict_protocol:
                if num_trials != 3 or start_seed != 40401:
                    raise ValueError(
                        f"PROTOCOL VIOLATION: Pilot phase requires exactly 3 trials starting at seed 40401, "
                        f"got num_trials={num_trials}, start_seed={start_seed}."
                    )
        else:
            if not phase_two_authorized:
                raise RuntimeError(
                    "PHASE 2 ACCESS FORBIDDEN: Hidden benchmark evaluation requires explicit phase_two_authorized=True."
                )
            if self.holdout_key != "private_hidden":
                raise ValueError(
                    f"CONFIRMATORY PROTOCOL VIOLATION: Confirmatory holdout must be 'private_hidden', got '{self.holdout_key}'. "
                    "CLI or programmatic override is strictly forbidden."
                )
            if strict_protocol:
                if num_trials != 10 or start_seed != 40411:
                    raise ValueError(
                        f"PROTOCOL VIOLATION: Phase 2 confirmatory requires exactly 10 trials starting at seed 40411, "
                        f"got num_trials={num_trials}, start_seed={start_seed}."
                    )
            if not pilot_results_path:
                raise ValueError(
                    "PHASE 2 LAUNCH REJECTED: pilot_results_path is required for confirmatory execution. "
                    "Confirmatory Phase 2 cannot proceed without an audited pilot artifact."
                )
            if not os.path.exists(pilot_results_path):
                raise FileNotFoundError(f"Pilot results artifact not found: {pilot_results_path}")
            with open(pilot_results_path, "r", encoding="utf-8") as f_pilot:
                pilot_data = json.load(f_pilot)
            if not isinstance(pilot_data, dict):
                raise ValueError("PHASE 2 LAUNCH REJECTED: Pilot artifact must be a valid JSON object.")
            p_stats = pilot_data.get("final_statistics", {})
            if not p_stats.get("gate1_passed", False):
                raise RuntimeError(
                    f"PHASE 2 LAUNCH REJECTED: Phase 1 pilot failed Gate 1 (gate1_passed={p_stats.get('gate1_passed')}). "
                    "Confirmatory Phase 2 is forbidden without passing the Gate 1 feasibility criteria."
                )
            if not p_stats.get("operational_feasibility_passed", False):
                raise RuntimeError("PHASE 2 LAUNCH REJECTED: Phase 1 pilot operational feasibility check failed.")
            if not p_stats.get("dev_improvement_passed", False):
                raise RuntimeError("PHASE 2 LAUNCH REJECTED: Phase 1 pilot dev improvement check failed.")
            if p_stats.get("num_trials") and p_stats.get("num_trials") != 3:
                raise RuntimeError(
                    f"PHASE 2 LAUNCH REJECTED: Pilot results must have exactly 3 trials, found {p_stats.get('num_trials')}."
                )

            # Check configuration fingerprint if present
            if "config_fingerprint" in pilot_data:
                if pilot_data["config_fingerprint"] != fingerprint:
                    raise RuntimeError(
                        f"PHASE 2 LAUNCH REJECTED: Pilot configuration fingerprint ({pilot_data['config_fingerprint']}) "
                        f"does not match confirmatory campaign fingerprint ({fingerprint})."
                    )

            # Check trial records in pilot if trials list is present
            if "trials" in pilot_data:
                for pt in pilot_data["trials"]:
                    validate_trial_record(pt)

        os.makedirs(self.output_dir, exist_ok=True)
        f_lock = open(self.campaign_lock_path, "w")
        try:
            fcntl.flock(f_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            f_lock.close()
            raise RuntimeError(
                f"CAMPAIGN LAUNCH REJECTED: Another runner process is already executing in {self.output_dir}. "
                "Simultaneous campaign launches are forbidden to prevent state corruption."
            )

        try:
            checkpoint_data = self._load_checkpoint()

            existing_trials = []
            if checkpoint_data:
                chk_fp = checkpoint_data.get("config_fingerprint")
                if chk_fp and chk_fp != fingerprint:
                    raise RuntimeError(
                        f"CHECKPOINT REUSE REJECTED: Checkpoint fingerprint ({chk_fp}) does not match "
                        f"current experiment fingerprint ({fingerprint}). Incompatible configuration."
                    )
                existing_trials = checkpoint_data.get("completed_trials", [])
                for et in existing_trials:
                    validate_trial_record(et)

            trials = []
            for t_idx in range(num_trials):
                seed = start_seed + t_idx
                trial_id = t_idx + 1

                # Resume logic: If this trial was already completed in an earlier run of the same campaign, reuse it
                if t_idx < len(existing_trials) and existing_trials[t_idx].get("seed") == seed:
                    trial_record = existing_trials[t_idx]
                    trials.append(trial_record)
                    continue

                # Check preflight budget before starting trial
                self.enforcer.check_preflight_limits()
                trial_record = self.run_paired_trial(trial_id=trial_id, seed=seed, dev_streams=dev_streams)
                trials.append(trial_record)

                # Atomic trial checkpointing
                self._save_checkpoint(trials, is_pilot=is_pilot, config_fingerprint=fingerprint)
                self.enforcer.record_checkpoint(
                    checkpoint_id=f"trial_{trial_id}_search_complete",
                    state_summary={"trial_id": trial_id, "delta_dev": trial_record["delta_dev"]}
                )

            mean_delta_dev = sum(t["delta_dev"] for t in trials) / len(trials) if trials else float("nan")

            if is_pilot:
                # STRICT QUARANTINE: In pilot mode, hidden benchmark is NEVER touched!
                for t in trials:
                    validate_trial_record(t)

                all_trials_valid = (
                    len(trials) == 3
                    and all(
                        t["arm_a"]["is_valid"] and t["arm_c"]["is_valid"]
                        for t in trials
                    )
                )
                non_trivial_evolution = any(
                    not t["arm_c"].get("is_seed", False) and t["arm_c"]["mutation_type"] not in ("fallback_best_fit", "seed")
                    for t in trials
                )
                operational_feasibility_pass = bool(
                    len(trials) == 3
                    and all_trials_valid
                    and non_trivial_evolution
                )
                dev_improvement_pass = bool(math.isfinite(mean_delta_dev) and mean_delta_dev < -0.005)
                gate1_passed = bool(operational_feasibility_pass and dev_improvement_pass)

                final_stats = {
                    "phase": "phase_1_pilot_feasibility",
                    "num_trials": len(trials),
                    "mean_delta_dev": round(mean_delta_dev, 6) if math.isfinite(mean_delta_dev) else None,
                    "gate1_threshold": -0.005,
                    "operational_feasibility_passed": operational_feasibility_pass,
                    "dev_improvement_passed": dev_improvement_pass,
                    "gate1_passed": gate1_passed,
                    "hidden_status": "SEALED_AND_UNTOUCHED",
                    "exploratory_warning": (
                        "Gate 1 evaluates operational feasibility and preliminary dev.json signal. "
                        "It is strictly exploratory and NEVER substitutes for confirmatory hidden-test evidence."
                    )
                }
                hidden_hash = "SEALED_NOT_READ"
            else:
                # SELECTIONS ARE NOW FROZEN in confirmatory phase
                # Validate confirmatory holdout benchmark cryptographic hash against manifest BEFORE unsealing
                manifest_path = os.path.join(self.benchmark_dir, "manifest.json")
                if not os.path.exists(manifest_path):
                    raise FileNotFoundError(f"Missing manifest for confirmatory holdout validation: {manifest_path}")
                with open(manifest_path, "r", encoding="utf-8") as f_man:
                    manifest = json.load(f_man)
                if self.holdout_key not in manifest:
                    raise KeyError(
                        f"Confirmatory holdout key '{self.holdout_key}' not found in manifest ({manifest_path}). "
                        f"Confirmatory mode requires '{self.holdout_key}'. No fallback permitted."
                    )
                hidden_info = manifest[self.holdout_key]
                hidden_rel_path = hidden_info.get("path")
                if not hidden_rel_path:
                    raise KeyError(f"Manifest entry '{self.holdout_key}' missing 'path' specification.")
                hidden_path = os.path.join(self.benchmark_dir, hidden_rel_path)
                if not os.path.exists(hidden_path):
                    raise FileNotFoundError(f"Missing confirmatory holdout benchmark file: {hidden_path}")

                computed_hidden_hash = compute_sha256(hidden_path)
                expected_hidden_hash = hidden_info.get("sha256")
                if computed_hidden_hash != expected_hidden_hash:
                    raise ValueError(
                        f"CORRUPTED CONFIRMATORY HOLDOUT BENCHMARK (CORRUPTED HIDDEN BENCHMARK): Expected {expected_hidden_hash}, got {computed_hidden_hash}"
                    )

                with open(hidden_path, "r", encoding="utf-8") as f:
                    hidden_data = json.load(f)
                hidden_streams = [entry["items"] for entry in hidden_data]

                final_stats = self.evaluate_on_hidden_benchmark(trials, hidden_streams, phase_two_authorized=True)
                final_stats["phase"] = "phase_2_confirmatory"
                final_stats["holdout_key"] = self.holdout_key
                final_stats["mean_delta_dev"] = round(mean_delta_dev, 6)
                hidden_hash = computed_hidden_hash

            campaign_results = {
                "timestamp": time.time(),
                "config_fingerprint": fingerprint,
                "metadata": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "model": self.client.model,
                    "base_url": self.client.base_url,
                    "mock_mode": self.mock_mode,
                    "is_pilot": is_pilot,
                    "phase_two_authorized": phase_two_authorized,
                    "strict_protocol": strict_protocol,
                    "holdout_key": self.holdout_key if not is_pilot else None
                },
                "reproducibility_notes": {
                    "provider_nondeterminism": (
                        "Remote frontier LLM inference is subject to provider-side GPU non-determinism "
                        "(MoE routing jitter, FP non-associativity across CUDA threads, dynamic batching) "
                        "even when fixed seeds and temperature are provided. Local components (item streams, "
                        "deterministic simulator, tie-breaking, AST validation, budget ledger) are 100% bit-for-bit reproducible."
                    ),
                    "start_seed": start_seed,
                    "num_trials": num_trials
                },
                "config": {
                    "num_trials": num_trials,
                    "candidate_slots": self.candidate_slots,
                    "max_cost_usd": self.max_cost_usd,
                    "mock_mode": self.mock_mode,
                    "is_pilot": is_pilot,
                    "holdout_key": self.holdout_key
                },
                "dev_benchmark_sha256": dev_hash,
                "hidden_benchmark_sha256": hidden_hash,
                "trials": trials,
                "final_statistics": final_stats,
                "budget_ledger": self.enforcer.get_summary()
            }

            with open(self.results_path, "w", encoding="utf-8") as f:
                json.dump(campaign_results, f, indent=2)

            return campaign_results
        finally:
            try:
                fcntl.flock(f_lock.fileno(), fcntl.LOCK_UN)
                f_lock.close()
            except Exception:
                pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage 4 Experimental Campaign Runner")
    parser.add_argument("--mode", choices=["pilot", "confirmatory"], default="pilot", help="Campaign mode: pilot or confirmatory")
    parser.add_argument("--output-dir", default="stage4/results/pilot2", help="Output directory for results and budget ledger")
    parser.add_argument("--benchmark-dir", default="stage4/benchmarks", help="Path to benchmark directory containing dev.json and manifest.json")
    parser.add_argument("--candidate-slots", type=int, default=50, help="Candidate slots per arm per trial (default 50)")
    parser.add_argument("--max-cost-usd", type=float, default=15.0, help="Hard cap on total USD spend (default $15.00)")
    parser.add_argument("--tripwire-cost-usd", type=float, default=12.0, help="Tripwire USD spend limit (default $12.00)")
    parser.add_argument("--max-requests", type=int, default=300, help="Hard cap on HTTP requests (default 300)")
    parser.add_argument("--max-output-tokens", type=int, default=700000, help="Hard cap on total completion tokens (default 700,000)")
    parser.add_argument("--max-input-tokens", type=int, default=1500000, help="Hard cap on total prompt tokens (default 1,500,000)")
    parser.add_argument("--mock", action="store_true", help="Run with mock LLM client (offline testing)")
    parser.add_argument("--phase-two-authorized", action="store_true", help="Explicit founder authorization for Phase 2 confirmatory run")
    parser.add_argument("--pilot-results-path", default=None, help="Path to pilot results.json required for Phase 2 authorization")
    parser.add_argument("--holdout-key", default="private_hidden", help="Manifest key for confirmatory holdout (default: private_hidden)")

    args = parser.parse_args()

    is_pilot = (args.mode == "pilot")
    if not is_pilot and args.holdout_key != "private_hidden":
        parser.error(
            f"CONFIRMATORY PROTOCOL VIOLATION: Confirmatory mode requires holdout-key 'private_hidden', got '{args.holdout_key}'"
        )
    num_trials = 3 if is_pilot else 10
    start_seed = 40401 if is_pilot else 40411

    runner = Stage4Runner(
        output_dir=args.output_dir,
        benchmark_dir=args.benchmark_dir,
        max_cost_usd=args.max_cost_usd,
        tripwire_cost_usd=args.tripwire_cost_usd,
        max_requests=args.max_requests,
        candidate_slots=args.candidate_slots,
        mock_mode=args.mock,
        holdout_key=args.holdout_key,
        max_output_tokens=args.max_output_tokens,
        max_input_tokens=args.max_input_tokens
    )

    results = runner.execute_campaign(
        num_trials=num_trials,
        start_seed=start_seed,
        is_pilot=is_pilot,
        phase_two_authorized=args.phase_two_authorized,
        pilot_results_path=args.pilot_results_path
    )
    print(f"Campaign finished successfully. Phase: {results['final_statistics']['phase']}. Trials completed: {len(results['trials'])}")

