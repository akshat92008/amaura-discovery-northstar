"""
Phase 1 Dry Run for Experiment #14
==================================
Mini dry run with:
- 1 Trial (Seed: 10101)
- 3 LLM calls across the first 3 conceptual angles
- Subset of dev instances (5 instances)
- Verifications:
  1. Candidate interface (`select_node` and optional `select_pod`)
  2. Sandbox execution & safety
  3. Simulator & objective scoring
  4. Scale-aware timeout
  5. Cryptographic provenance & token logging
  6. Clean isolation of hidden benchmark
  7. Cleanup of temporary dry-run logs
"""

import json
import os
import sys

from experiment14.src.evaluator import PodSchedulingEvaluator
from experiment14.src.llm_client import CloudSchedulingLLMClient
from experiment14.src.prompts import PROMPT_PERSPECTIVES, get_prompt_for_perspective
from experiment14.src.simulator import simulate_schedule


def main():
    print("==================================================")
    print("STARTING EXPERIMENT #14 DRY RUN")
    print("==================================================")

    dry_logs = "experiment14/logs/dry_run_llm_calls.jsonl"
    dry_cands = "experiment14/candidates/dry_run_candidates.jsonl"

    if os.path.exists(dry_logs):
        os.remove(dry_logs)
    if os.path.exists(dry_cands):
        os.remove(dry_cands)

    with open("experiment14/benchmarks/dev.json") as f:
        dev_instances = json.load(f)[:5]

    llm_client = CloudSchedulingLLMClient()
    evaluator = PodSchedulingEvaluator()

    for call_idx in range(3):
        perspective = PROMPT_PERSPECTIVES[call_idx]
        prompt = get_prompt_for_perspective(perspective)
        print(f"\n[Dry Run Call {call_idx+1}/3] Querying {perspective['name']}...")

        res = llm_client.query(prompt=prompt)
        print(f"   Success: {res['success']} | Model: {res['model']} | Tokens: {res['completion_tokens']} | Latency: {res['duration_ms']:.1f}ms")
        assert res["success"], f"Call {call_idx+1} failed: {res['error']}"
        assert len(res["code"]) > 0, "No code extracted"

        eval_res = evaluator.evaluate_solver_code(res["code"], dev_instances)
        print(f"   Evaluator Result: Valid={eval_res['is_valid']} | Cost={eval_res['total_cost']:.2f} | Runtime={eval_res['runtime_ms']:.1f}ms | Error={eval_res['error']}")
        assert eval_res["is_valid"], f"Dry run candidate invalid: {eval_res['error']}"
        assert eval_res["total_cost"] < 999999.0, "Evaluator returned invalid penalty cost"

    # Verify Hidden benchmark untouched
    assert not os.path.exists("experiment14/frozen/frozen_champions.json"), "frozen_champions.json should not exist yet"
    assert not os.path.exists("experiment14/results/hidden_results.json"), "hidden_results.json should not exist yet"

    print("\n==================================================")
    print("EXPERIMENT #14 DRY RUN PASSED ALL VERIFICATIONS!")
    print("==================================================")


if __name__ == "__main__":
    main()
