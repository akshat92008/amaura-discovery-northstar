"""
North BlueStar — Command-Line Interface & Benchmark Exporter
============================================================
Usage:
  python3 -m north_bluestar.cli audit
  python3 -m north_bluestar.cli benchmark --budget 28 --seed 42
  python3 -m north_bluestar.cli export-workbench-snapshot
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

from north_bluestar.controller import (
    BaselinePortfolioStrategy,
    LocalCoordinateSearchStrategy,
    OperatorRecombinationStrategy,
    ProgramSynthesisStrategy,
    RandomizedSearchStrategy,
    SearchBudget,
    SearchController,
    StructuredEnumerationStrategy,
    SurrogateUCBStrategy,
)
from north_bluestar.orchestrator import (
    ForensicRepositoryAuditor,
    NorthBlueStarEngine,
    build_bin_packing_problem,
    build_graph_coloring_problem,
    build_pfsp_problem,
    run_preregistered_benchmark_suite,
)


def generate_full_workbench_snapshot(budget_evals: int = 24, seed: int = 42) -> Dict[str, Any]:
    t0 = time.perf_counter()
    forensic = ForensicRepositoryAuditor.run_full_forensic_audit(repo_root=".")
    benchmarks = run_preregistered_benchmark_suite(budget_evals=budget_evals, seed=seed)

    # Run Graph Coloring portfolio run as well so all 3 benchmark families are represented
    gc_prob = build_graph_coloring_problem(seed=seed)
    gc_engine = NorthBlueStarEngine(problem=gc_prob)
    gc_ctrl = SearchController(
        strategies=[
            BaselinePortfolioStrategy(seed=seed),
            ProgramSynthesisStrategy(seed=seed),
        ],
        budget=SearchBudget(max_evaluations=10, stagnation_limit=8),
        seed=seed,
    )
    gc_res = gc_engine.run_discovery(gc_ctrl, controller_mode="north_bluestar_portfolio")
    benchmarks["domains"]["vertex_graph_coloring"] = {
        "north_bluestar_portfolio": gc_res.to_dict()
    }

    elapsed_s = round(time.perf_counter() - t0, 3)
    return {
        "generated_at_epoch": int(time.time()),
        "generation_wall_time_sec": elapsed_s,
        "engine_version": "North BlueStar v2.0.0",
        "forensic_audit": forensic,
        "preregistered_benchmarks": benchmarks,
        "registered_methods": [
            {
                "method_id": c.method_id,
                "name": c.name,
                "paradigm": c.paradigm.value,
                "supported_problem_ids": list(c.supported_problem_ids),
                "supported_candidate_kinds": [k.value for k in c.supported_candidate_kinds],
                "can_prove_optimality": c.can_prove_optimality,
                "is_deterministic": c.is_deterministic,
                "estimated_cost_tier": c.estimated_cost_tier,
                "description": c.description,
            }
            for c in gc_engine.registry.list_capabilities()
        ],
        "threat_model": {
            "level": gc_engine.supervisor.threat_model.level.value,
            "enforces_ast_allowlist": gc_engine.supervisor.threat_model.enforces_ast_allowlist,
            "enforces_os_process_boundary": gc_engine.supervisor.threat_model.enforces_os_process_boundary,
            "enforces_sigkill_on_timeout": gc_engine.supervisor.threat_model.enforces_sigkill_on_timeout,
            "guarantees": list(gc_engine.supervisor.threat_model.guarantees),
            "non_guarantees": list(gc_engine.supervisor.threat_model.non_guarantees),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Amaura Labs — North BlueStar Discovery Engine CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("audit", help="Run forensic repository audit against Stage 2, 3, 4 and 780-config PFSP space")

    bench_p = sub.add_parser("benchmark", help="Run preregistered equal-budget multi-strategy benchmark")
    bench_p.add_argument("--budget", type=int, default=24, help="Development evaluations per strategy arm")
    bench_p.add_argument("--seed", type=int, default=42, help="Deterministic random seed")

    snap_p = sub.add_parser("export-workbench-snapshot", help="Export verified JSON snapshot for UI/API")
    snap_p.add_argument("--out", type=str, default="public/north_bluestar_snapshot.json", help="Output path")
    snap_p.add_argument("--budget", type=int, default=24, help="Development evaluations per strategy arm")

    args = parser.parse_args()

    if args.command == "audit":
        report = ForensicRepositoryAuditor.run_full_forensic_audit(repo_root=".")
        print(json.dumps(report, indent=2))
    elif args.command == "benchmark":
        res = run_preregistered_benchmark_suite(budget_evals=args.budget, seed=args.seed)
        print(json.dumps(res, indent=2))
    elif args.command == "export-workbench-snapshot":
        snap = generate_full_workbench_snapshot(budget_evals=args.budget, seed=42)
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2)
        print(f"Exported verified North BlueStar snapshot to {args.out} ({snap['generation_wall_time_sec']}s)")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
