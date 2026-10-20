"""
Permutation Flow-Shop Scheduling (PFSP) Problem Domain for Search Strategy Benchmark V1
======================================================================================
Constructive NEH skeleton with priority-driven initial job ordering.
Skeleton: Deterministic NEH Construction with Taillard (1990) acceleration.
Primary Baseline: NEH Heuristic (Nawaz, Enscore, Ham 1983).
Secondary Baseline: Natural Order Insertion.

Invalid Handling:
Instance-normalized penalty strictly greater than any feasible makespan (2 * sum of all processing times).
Guarantees invalid or crashing candidates never beat valid candidates.
"""

import json
import math
import os
import time
from typing import Dict, Any, List, Optional, Tuple

from benchmark_v1.src.domains.base import ProblemDomain, DomainEvaluationResult
from stage3.src.sandbox import check_ast_security, sanitize_and_compile, sanitize_exception_name, SAFE_BUILTINS


class PFSPSimulator:
    """
    Deterministic PFSP Simulator using Taillard (1990) O(m * i) accelerated NEH insertion.
    """
    @staticmethod
    def calc_makespan(times: List[List[int]], perm: List[int]) -> int:
        if not times or not perm:
            return 0
        m = len(times[0])
        completion = [0] * m
        for job in perm:
            for c in range(m):
                left = completion[c - 1] if c > 0 else 0
                top = completion[c]
                completion[c] = (left if left > top else top) + times[job][c]
        return completion[-1]

    @staticmethod
    def neh_schedule(times: List[List[int]], priority_fn) -> Tuple[int, List[int]]:
        n = len(times)
        if n == 0:
            return 0, []
        m = len(times[0])

        # Priority scoring of jobs
        scored_jobs = []
        for j in range(n):
            tot = float(sum(times[j]))
            avg = tot / m
            mn = float(min(times[j]))
            mx = float(max(times[j]))
            first_t = float(times[j][0])
            last_t = float(times[j][-1])

            p = float(priority_fn(j, tot, avg, mn, mx, first_t, last_t))
            if not math.isfinite(p):
                raise ValueError(f"Non-finite priority returned for job {j}: {p}")
            scored_jobs.append((p, -j, j))

        scored_jobs.sort(reverse=True)
        order = [j for _, _, j in scored_jobs]

        # Constructive insertion with Taillard acceleration
        seq = [order[0]]
        for i in range(1, n):
            job = order[i]
            k = len(seq)

            # 1. Forward DP: e[r][c]
            e = [[0] * m for _ in range(k)]
            for r in range(k):
                pj = times[seq[r]]
                for c in range(m):
                    top = e[r - 1][c] if r > 0 else 0
                    left = e[r][c - 1] if c > 0 else 0
                    e[r][c] = (top if top > left else left) + pj[c]

            # 2. Backward DP: q[r][c]
            q = [[0] * m for _ in range(k)]
            for r in range(k - 1, -1, -1):
                pj = times[seq[r]]
                for c in range(m - 1, -1, -1):
                    bottom = q[r + 1][c] if r < k - 1 else 0
                    right = q[r][c + 1] if c < m - 1 else 0
                    q[r][c] = (bottom if bottom > right else right) + pj[c]

            # 3. Find optimal insertion position
            pj = times[job]
            best_pos = 0
            best_cmax = float("inf")

            for pos in range(k + 1):
                f = [0] * m
                for c in range(m):
                    top = e[pos - 1][c] if pos > 0 else 0
                    left = f[c - 1] if c > 0 else 0
                    f[c] = (top if top > left else left) + pj[c]

                cmax = 0
                for c in range(m):
                    tail = q[pos][c] if pos < k else 0
                    tot = f[c] + tail
                    if tot > cmax:
                        cmax = tot

                if cmax < best_cmax:
                    best_cmax = cmax
                    best_pos = pos

            seq.insert(best_pos, job)

        final_makespan = PFSPSimulator.calc_makespan(times, seq)
        return final_makespan, seq


class PFSPDomain(ProblemDomain):
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "pfsp")
        self.data_dir = data_dir
        self.simulator = PFSPSimulator()

        with open(os.path.join(self.data_dir, "train.json"), "r", encoding="utf-8") as f:
            self.train_data = json.load(f)
        with open(os.path.join(self.data_dir, "test.json"), "r", encoding="utf-8") as f:
            self.test_data = json.load(f)

        self._train_neh_ref = [self.simulator.neh_schedule(inst["times"], lambda j, tot, avg, mn, mx, f, l: tot)[0] for inst in self.train_data]
        self._test_neh_ref = [self.simulator.neh_schedule(inst["times"], lambda j, tot, avg, mn, mx, f, l: tot)[0] for inst in self.test_data]

        self._baselines = {
            "train": self._compute_baselines(self.train_data, self._train_neh_ref),
            "test": self._compute_baselines(self.test_data, self._test_neh_ref)
        }

    def _compute_baselines(self, dataset: List[Dict[str, Any]], neh_scores: List[int]) -> Dict[str, float]:
        def nat_p(j, tot, avg, mn, mx, f, l):
            return -j

        nat_scores = [self.simulator.neh_schedule(inst["times"], nat_p)[0] for inst in dataset]

        return {
            "neh": sum(neh_scores) / len(dataset),
            "neh_total": float(sum(neh_scores)),
            "natural": sum(nat_scores) / len(dataset),
            "natural_total": float(sum(nat_scores))
        }

    @property
    def name(self) -> str:
        return "pfsp"

    @property
    def function_name(self) -> str:
        return "job_priority"

    @property
    def function_signature(self) -> str:
        return (
            "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
            "    \"\"\"Assigns priority to job for constructive NEH sequencing. Higher priority jobs are inserted earlier.\"\"\""
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert operations researcher and scheduling algorithm designer.\n"
            "Your task is to design a job priority heuristic in pure Python for Permutation Flow-Shop Scheduling (PFSP).\n\n"
            "Interface:\n"
            "```python\n"
            "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
            "```\n"
            "Arguments:\n"
            "- `job_id: int`: 0-indexed job identifier\n"
            "- `total_time: float`: sum of processing times across all machines for this job\n"
            "- `avg_time: float`: average processing time per machine (total_time / m)\n"
            "- `min_time: float`: minimum processing time on any machine\n"
            "- `max_time: float`: maximum processing time on any machine\n"
            "- `first_machine_time: float`: processing time on first machine (M1)\n"
            "- `last_machine_time: float`: processing time on last machine (Mm)\n\n"
            "Rules:\n"
            "1. Output higher priority for jobs that should be inserted earlier in the NEH schedule.\n"
            "2. Objective is to minimize total makespan across the benchmark.\n"
            "3. Allowed libraries: `math` only.\n"
            "4. Return ONLY valid Python inside a ```python ``` markdown block."
        )

    @property
    def canonical_seeds(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "neh",
                "code": (
                    "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
                    "    # NEH (Nawaz, Enscore, Ham 1983): largest total processing time first\n"
                    "    return float(total_time)\n"
                ),
                "description": "Standard NEH priority ranking by descending total work."
            },
            {
                "name": "palmer_slope_variant",
                "code": (
                    "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
                    "    # Palmer slope index: prioritize jobs with smaller initial time and larger final time\n"
                    "    return float(total_time + (last_machine_time - first_machine_time))\n"
                ),
                "description": "Combines total work with flow-shop slope gradient."
            },
            {
                "name": "spread_variance",
                "code": (
                    "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
                    "    # Spread penalty: penalize jobs with high variance across machines\n"
                    "    spread = max_time - min_time\n"
                    "    return float(total_time - 0.5 * spread)\n"
                ),
                "description": "Balances total processing time against machine processing time spread."
            },
            {
                "name": "natural_order",
                "code": (
                    "def job_priority(job_id: int, total_time: float, avg_time: float, min_time: float, max_time: float, first_machine_time: float, last_machine_time: float) -> float:\n"
                    "    # Natural index order\n"
                    "    return float(-job_id)\n"
                ),
                "description": "Index order insertion baseline."
            }
        ]

    def get_baseline_scores(self, split: str = "train") -> Dict[str, float]:
        return self._baselines.get(split, self._baselines["train"])

    def compute_relative_gap(self, raw_score: float, split: str = "train") -> float:
        neh_score = self.get_baseline_scores(split)["neh"]
        if neh_score <= 0.0:
            return 0.0
        # Relative gap vs NEH: (score - NEH) / NEH. Negative means better than NEH.
        return round((raw_score - neh_score) / neh_score, 6)

    def _compute_worst_penalty(self, dataset: List[Dict[str, Any]]) -> float:
        # Strict upper bound: 2 * total sum of all processing times in dataset
        total = sum(sum(sum(row) for row in inst["times"]) * 2 for inst in dataset)
        return float(total)

    def evaluate(self, code: str, split: str = "train") -> DomainEvaluationResult:
        dataset = self.train_data if split == "train" else self.test_data
        t0 = time.perf_counter()

        # AST Safety Check
        is_safe, error_msg = check_ast_security(code, required_func="job_priority")
        if not is_safe:
            worst_penalty = self._compute_worst_penalty(dataset)
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=worst_penalty,
                avg_score=worst_penalty / len(dataset),
                per_instance_scores=[worst_penalty / len(dataset)] * len(dataset),
                relative_gap=self.compute_relative_gap(worst_penalty / len(dataset), split),
                beats_baseline=False,
                error_message=error_msg,
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        # Compile and execute
        exec_globals = {"__builtins__": SAFE_BUILTINS, "math": __import__("math")}
        try:
            compiled = sanitize_and_compile(code, "<candidate_pfsp_priority>")
            exec(compiled, exec_globals)
            priority_fn = exec_globals["job_priority"]
        except Exception as e:
            worst_penalty = self._compute_worst_penalty(dataset)
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=worst_penalty,
                avg_score=worst_penalty / len(dataset),
                per_instance_scores=[worst_penalty / len(dataset)] * len(dataset),
                relative_gap=self.compute_relative_gap(worst_penalty / len(dataset), split),
                beats_baseline=False,
                error_message=f"Compilation/Import Error: {sanitize_exception_name(e)}",
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        scores: List[float] = []
        worst_inst_idx = -1
        max_excess_vs_neh = -float("inf")

        neh_ref = self._train_neh_ref if split == "train" else self._test_neh_ref

        try:
            for idx, inst in enumerate(dataset):
                cmax, _ = self.simulator.neh_schedule(inst["times"], priority_fn)
                scores.append(float(cmax))
                diff_vs_neh = cmax - neh_ref[idx]
                if diff_vs_neh > max_excess_vs_neh:
                    max_excess_vs_neh = diff_vs_neh
                    worst_inst_idx = idx
        except Exception as e:
            worst_penalty = self._compute_worst_penalty(dataset)
            return DomainEvaluationResult(
                is_valid=False,
                raw_score=worst_penalty,
                avg_score=worst_penalty / len(dataset),
                per_instance_scores=[worst_penalty / len(dataset)] * len(dataset),
                relative_gap=self.compute_relative_gap(worst_penalty / len(dataset), split),
                beats_baseline=False,
                error_message=f"Execution Error on instance #{len(scores)}: {sanitize_exception_name(e)}",
                diagnostics=None,
                runtime_ms=round((time.perf_counter() - t0) * 1000.0, 2)
            )

        total_runtime_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        total_makespan = sum(scores)
        avg_makespan = total_makespan / len(scores)
        rel_gap = self.compute_relative_gap(avg_makespan, split)
        neh_avg = self.get_baseline_scores(split)["neh"]
        beats_baseline = bool(avg_makespan < neh_avg - 1e-6)

        # Build diagnostics for Arm E
        diagnostics = {
            "avg_makespan": round(avg_makespan, 2),
            "neh_avg": round(neh_avg, 2),
            "per_instance_scores": scores,
            "worst_instance_idx": worst_inst_idx,
            "worst_instance_makespan": scores[worst_inst_idx] if worst_inst_idx >= 0 else None,
            "worst_instance_neh": neh_ref[worst_inst_idx] if worst_inst_idx >= 0 else None,
            "diagnostic_summary": (
                f"Overall Average Makespan: {avg_makespan:.2f} (NEH baseline: {neh_avg:.2f}, Gap: {rel_gap * 100:+.2f}%).\n"
                f"Worst Instance #{worst_inst_idx}: Produced makespan {scores[worst_inst_idx]:.0f} vs NEH's {neh_ref[worst_inst_idx]} "
                f"(+{scores[worst_inst_idx] - neh_ref[worst_inst_idx]:.0f} excess makespan).\n"
                f"Failure Analysis: Early job sequencing fails to clear bottlenecks on downstream machines.\n"
                f"Refinement Directive: Weight `total_time` highest, but apply secondary gradient favoring jobs where `last_machine_time > first_machine_time`."
            )
        }

        return DomainEvaluationResult(
            is_valid=True,
            raw_score=total_makespan,
            avg_score=round(avg_makespan, 2),
            per_instance_scores=scores,
            relative_gap=rel_gap,
            beats_baseline=beats_baseline,
            error_message=None,
            diagnostics=diagnostics,
            runtime_ms=total_runtime_ms
        )
