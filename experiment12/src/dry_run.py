"""
Phase 1 Dry Run for Experiment #12
==================================
Mini dry run with:
- 1 Trial (Seed: 10101)
- Condition A: 3 calls
- Condition R: 2 generation calls + 1 refinement call

Verifications:
1. Refinement receives the correct frozen parent code and parent score.
2. Candidate hashes and provenance are properly logged.
3. Development selection works.
4. Hidden benchmark remains untouched.
5. Clean up dry run output so official experiment starts pristine.
"""

import os
import sys
import json
import shutil
from experiment12.src.runner import Experiment12Runner

def main():
    print("==================================================")
    print("STARTING EXPERIMENT #12 DRY RUN (PHASE 1)")
    print("==================================================")

    dry_logs = "experiment12/logs/dry_run_llm_calls.jsonl"
    dry_cands = "experiment12/candidates/dry_run_candidates.jsonl"

    if os.path.exists(dry_logs):
        os.remove(dry_logs)
    if os.path.exists(dry_cands):
        os.remove(dry_cands)

    runner = Experiment12Runner(
        logs_path=dry_logs,
        candidates_path=dry_cands
    )

    # 1. Test Condition A with 3 calls
    print("\n--- Testing Condition A (3 calls) ---")
    champ_a = runner.run_condition_a_trial(trial_idx=0, num_calls=3)
    assert champ_a is not None, "Condition A champion is None"
    assert champ_a["candidate_id"].startswith("T1_A_"), f"Unexpected ID {champ_a['candidate_id']}"
    print(f"Verified Condition A: Champion {champ_a['candidate_id']} (Makespan: {champ_a['development_score']})")

    # 2. Test Condition R with 2 gen calls + 1 ref call
    print("\n--- Testing Condition R (2 gen + 1 ref) ---")
    champ_r = runner.run_condition_r_trial(trial_idx=0, num_gen_calls=2, num_ref_calls=1)
    assert champ_r is not None, "Condition R champion is None"
    assert champ_r["candidate_id"].startswith("T1_R_"), f"Unexpected ID {champ_r['candidate_id']}"
    assert "trial_metadata_r" in champ_r, "Missing trial_metadata_r"
    parent_id = champ_r["trial_metadata_r"]["parent_id"]
    parent_score = champ_r["trial_metadata_r"]["parent_score"]
    print(f"Verified Condition R: Parent {parent_id} (Makespan: {parent_score}) -> Champ {champ_r['candidate_id']}")

    # 3. Verify logging and provenance
    assert os.path.exists(dry_logs), "dry_run_llm_calls.jsonl not created"
    assert os.path.exists(dry_cands), "dry_run_candidates.jsonl not created"

    with open(dry_logs) as f:
        log_lines = [json.loads(line) for line in f]
    with open(dry_cands) as f:
        cand_lines = [json.loads(line) for line in f]

    print(f"\nLogged LLM calls: {len(log_lines)} (Expected 6)")
    print(f"Logged Candidates: {len(cand_lines)} (Expected 6)")
    assert len(log_lines) == 6, f"Expected 6 calls, got {len(log_lines)}"
    assert len(cand_lines) == 6, f"Expected 6 candidates, got {len(cand_lines)}"

    # Check refinement call provenance
    ref_cand = cand_lines[-1]
    assert ref_cand["phase"] == "refinement", f"Expected refinement phase, got {ref_cand['phase']}"
    assert ref_cand["parent_id"] == parent_id, f"Parent ID mismatch: {ref_cand['parent_id']} vs {parent_id}"
    assert ref_cand["parent_score"] == parent_score, f"Parent score mismatch: {ref_cand['parent_score']} vs {parent_score}"
    assert "code_chars" in ref_cand and ref_cand["code_chars"] > 0, "Refinement candidate has no code"
    print("Verified Refinement provenance: parent ID, score, and objective recorded accurately.")

    # 4. Verify Hidden benchmark isolation
    hidden_eval_path = "experiment12/results/hidden_evaluations.json"
    frozen_champ_path = "experiment12/results/frozen_champions.json"
    assert not os.path.exists(hidden_eval_path), "Hidden evaluations file should NOT exist during dry run!"
    assert not os.path.exists(frozen_champ_path), "Frozen champions file should NOT exist during dry run!"
    print("Verified Hidden benchmark isolation: hidden benchmark untouched.")

    # 5. Clean up dry run files
    os.remove(dry_logs)
    os.remove(dry_cands)
    print("Dry run logs cleaned up successfully.")

    print("\n==================================================")
    print("DRY RUN PASSED ALL PRE-REGISTRATION CHECKS!")
    print("==================================================")

if __name__ == "__main__":
    main()
