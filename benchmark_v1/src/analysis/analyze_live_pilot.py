"""
Analyze Live LLM Search Pilot Results
=====================================
Extracts detailed metrics across all 5 arms for online bin packing:
- Candidate validity and error taxonomy
- Search dynamics and best-so-far trajectories
- Unique code diversity and duplicate analysis
- Code snippet inspection
- Token usage, latency, and model responsiveness
"""

import json
import glob
import os
from collections import Counter

res_dir = "benchmark_v1/results/live_llm_binpacking_pilot_20261018"
trial_files = sorted(glob.glob(f"{res_dir}/trial_*.json"))

summary_data = {}
all_trials = []

for tf in trial_files:
    with open(tf) as f:
        data = json.load(f)
    all_trials.append(data)
    arm = data["arm"]
    proposals = data["all_proposals"]
    total = len(proposals)
    valid_count = sum(1 for p in proposals if p["train_eval"]["is_valid"])
    codes = [p["code"].strip() for p in proposals]
    unique_codes = len(set(codes))
    duplicate_count = total - unique_codes
    
    # Trajectory validity split into 4 quarters (8 proposals each)
    q_valid = [0, 0, 0, 0]
    for idx, p in enumerate(proposals):
        q = min(idx // 8, 3)
        if p["train_eval"]["is_valid"]:
            q_valid[q] += 1
            
    sel = data["selection"]
    gen_test = data["generalization_test"]
    pilot_val = data.get("pilot_validation")
    curve = data["best_so_far_curve"]
    
    # Check best generated (excluding seed)
    valid_gen = [p for p in proposals if p["train_eval"]["is_valid"]]
    best_gen_score = min([p["train_eval"]["raw_score"] for p in valid_gen]) if valid_gen else None
    best_gen_cand = min(valid_gen, key=lambda p: p["train_eval"]["raw_score"]) if valid_gen else None
    
    error_list = [p["train_eval"]["error_message"] for p in proposals if not p["train_eval"]["is_valid"]]
    
    summary_data[arm] = {
        "total_proposals": total,
        "valid_proposals": valid_count,
        "validity_rate": valid_count / total,
        "duplicate_count": duplicate_count,
        "unique_codes": unique_codes,
        "quarters_validity": [qv / 8.0 for qv in q_valid],
        "champion_id": sel["candidate_id"],
        "champion_is_seed": sel.get("is_seed", False),
        "train_score": sel["train_score"],
        "train_rel_gap": sel["train_rel_gap"],
        "test_score": gen_test["test_score"],
        "test_rel_gap": gen_test["test_rel_gap"],
        "pilot_val_score": pilot_val["pilot_val_score"] if pilot_val else None,
        "pilot_val_rel_gap": pilot_val["pilot_val_rel_gap"] if pilot_val else None,
        "best_gen_score": best_gen_score,
        "best_gen_gap": best_gen_cand["train_eval"]["relative_gap"] if best_gen_cand else None,
        "best_gen_id": best_gen_cand["candidate_id"] if best_gen_cand else None,
        "errors": error_list,
        "best_so_far_curve": curve,
        "proposals": proposals
    }

print("================================================================================")
print("AMAURA LABS — LIVE LLM SEARCH PILOT: RESULTS SUMMARY")
print("================================================================================")

for arm, s in summary_data.items():
    print(f"\nArm: {arm}")
    print(f"  Validity: {s['valid_proposals']}/{s['total_proposals']} ({s['validity_rate']*100:.1f}%)")
    qv_str = ", ".join(f"Q{i+1}: {q*100:.0f}%" for i, q in enumerate(s['quarters_validity']))
    print(f"  Quarters Validity: {qv_str}")
    print(f"  Duplicates: {s['duplicate_count']} ({s['unique_codes']} unique)")
    print(f"  Champion: {s['champion_id']} (is_seed: {s['champion_is_seed']})")
    print(f"  Train Score: {s['train_score']:.6f} (Gap: {s['train_rel_gap']*100:+.2f}%)")
    print(f"  Test Score: {s['test_score']:.6f} (Gap: {s['test_rel_gap']*100:+.2f}%)")
    if s["pilot_val_score"] is not None:
        print(f"  Pilot Val Score: {s['pilot_val_score']:.6f} (Gap: {s['pilot_val_rel_gap']*100:+.2f}%)")
    if s["best_gen_score"] is not None:
        print(f"  Best Generated: {s['best_gen_id']} Score: {s['best_gen_score']:.6f} (Gap: {s['best_gen_gap']*100:+.2f}%)")
    else:
        print("  Best Generated: NONE VALID")
    if s["errors"]:
        print(f"  Sample errors ({len(s['errors'])} total): {Counter(s['errors']).most_common(2)}")

# Read query log statistics
query_log_path = f"{res_dir}/llm_queries.jsonl"
with open(query_log_path) as f:
    queries = [json.loads(line) for line in f if line.strip()]

latencies = [q["latency_sec"] for q in queries]
prompt_tokens = [q["usage"].get("prompt_tokens", 0) for q in queries]
comp_tokens = [q["usage"].get("completion_tokens", 0) for q in queries]
reasoning_tokens = [q["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0) for q in queries]

print("\n================================================================================")
print("REPRESENTATIVE CODE SNIPPETS ACROSS ARMS")
print("================================================================================")

for arm, s in summary_data.items():
    proposals = s["proposals"]
    valid = [p for p in proposals if p["train_eval"]["is_valid"]]
    print(f"\n#################### {arm.upper()} ####################")
    
    # Early candidate (index 1 or 2)
    early = [p for p in valid if p["proposal_index"] in [1, 2]][0] if [p for p in valid if p["proposal_index"] in [1, 2]] else valid[0]
    e_id = early['candidate_id']
    e_score = early['train_eval']['raw_score']
    print(f"--- Early Candidate ({e_id}, Score: {e_score:.5f}) ---")
    print(early["code"].strip())
    
    # Late candidate (index 28 or 29)
    late = [p for p in valid if p["proposal_index"] in [28, 29]][0] if [p for p in valid if p["proposal_index"] in [28, 29]] else valid[-1]
    l_id = late['candidate_id']
    l_score = late['train_eval']['raw_score']
    print(f"\n--- Late Candidate ({l_id}, Score: {l_score:.5f}) ---")
    print(late["code"].strip())
    
    # Best generated candidate
    best_cand = min(valid, key=lambda p: p["train_eval"]["raw_score"])
    b_id = best_cand['candidate_id']
    b_score = best_cand['train_eval']['raw_score']
    b_gap = best_cand['train_eval']['relative_gap'] * 100
    print(f"\n--- Best Generated Candidate ({b_id}, Score: {b_score:.5f}, Gap: {b_gap:+.2f}%) ---")
    print(best_cand["code"].strip())

