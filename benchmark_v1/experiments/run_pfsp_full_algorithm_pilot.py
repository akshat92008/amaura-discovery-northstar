#!/usr/bin/env python3
"""
Amaura Labs: PFSP Full Algorithm Discovery Pilot
================================================
Evaluates whether a live frontier LLM (Nemotron-3 Super) can discover
a genuinely better scheduling algorithm when given a full algorithm interface:
    def solve(processing_times: list[list[int]]) -> list[int]:

Protocol:
- 32 independent candidate proposals
- Live LLM calls via OmniRoute (zero simulation stand-ins)
- Training set: 18 instances (benchmark_v1/data/pfsp/train.json)
- Held-out test set: 36 instances (benchmark_v1/data/pfsp/test.json)
- Baselines: NEH (84,907), NEH-LS (84,593), Natural Order (85,106)
- Preregistered success gate: >= 1.0% makespan improvement over NEH on held-out test data.
"""

import hashlib
import json
import math
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from benchmark_v1.src.arms.generator import LiveLLMGenerator
from benchmark_v1.src.domains.pfsp_full_algorithm import (
    PFSPFullAlgorithmDomain,
    calc_makespan,
    validate_permutation,
    neh_solve,
    neh_ls_solve
)


def replicate_candidate_on_fresh_instances(
    code_str: str,
    num_instances: int = 10,
    start_seed: int = 90001
) -> Dict[str, Any]:
    """Generates fresh PFSP instances and verifies whether candidate genuinely outperforms NEH."""
    from stage3.src.sandbox import sanitize_and_compile, SAFE_BUILTINS

    rng = random.Random(start_seed)
    instances = []
    # Generate 10 fresh diverse Taillard-style instances
    sizes = [(20, 5), (20, 10), (30, 10), (50, 10), (50, 15), (75, 10), (75, 15), (100, 10), (100, 15), (120, 10)]
    for idx, (n, m) in enumerate(sizes):
        s = start_seed + idx
        r = random.Random(s)
        times = [[r.randint(1, 99) for _ in range(m)] for _ in range(n)]
        instances.append({"id": f"fresh_{idx:02d}", "n": n, "m": m, "times": times})

    code_obj = sanitize_and_compile(code_str)
    ns = {
        "__builtins__": SAFE_BUILTINS,
        "math": math,
        "random": random,
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "heapq": __import__("heapq"),
        "copy": __import__("copy"),
    }
    exec(code_obj, ns)
    cand_fn = ns["solve"]

    cand_cmaxes = []
    neh_cmaxes = []

    for inst in instances:
        times = inst["times"]
        times_copy = [list(r) for r in times]
        perm_cand = cand_fn(times_copy)
        is_val, _ = validate_permutation(perm_cand, len(times))
        if not is_val:
            return {"replicated": False, "error": "Invalid permutation on fresh instance"}
        c_cand = calc_makespan(times, perm_cand)
        c_neh = calc_makespan(times, neh_solve(times))
        cand_cmaxes.append(c_cand)
        neh_cmaxes.append(c_neh)

    tot_cand = sum(cand_cmaxes)
    tot_neh = sum(neh_cmaxes)
    rel_gain = (tot_cand - tot_neh) / float(tot_neh)
    wins = sum(1 for c, n in zip(cand_cmaxes, neh_cmaxes) if c < n)

    return {
        "replicated": bool(tot_cand < tot_neh),
        "total_cand_makespan": tot_cand,
        "total_neh_makespan": tot_neh,
        "relative_gain": round(rel_gain, 6),
        "wins_vs_neh": wins,
        "total_instances": num_instances
    }


def run_pfsp_pilot():
    output_dir = os.path.join(REPO_ROOT, "benchmark_v1", "results", "pfsp_full_algorithm_pilot_20261018")
    os.makedirs(output_dir, exist_ok=True)
    query_log_path = os.path.join(output_dir, "llm_queries.jsonl")
    candidates_file = os.path.join(output_dir, "candidates.jsonl")

    print("=" * 80)
    print("AMAURA LABS — PFSP FULL ALGORITHM DISCOVERY PILOT")
    print("Testing Complete Algorithm Representation with Live Nemotron-3 Super")
    print(f"Output Directory: {output_dir}")
    print("=" * 80)

    total_proposals = 32
    candidates: List[Dict[str, Any]] = []

    # Check for existing completed proposals to support safe resumption
    if os.path.exists(candidates_file):
        with open(candidates_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))
        print(f"  Loaded {len(candidates)} previously completed proposals from {candidates_file}")

    # 1. Connectivity Preflight (if generation needed)
    llm = LiveLLMGenerator(query_log_path=query_log_path)
    if len(candidates) < total_proposals:
        print("\n[Phase 1/4] Preflight Connectivity Verification...")
        try:
            conn = llm._query_model("You are a test assistant.", "Reply with READY.")
            print(f"  ✓ Live Model Verified: {conn['model']}")
            print(f"  ✓ Latency: {conn['latency_sec']}s")
            print(f"  ✓ Response: {conn['content'].strip()}")
        except Exception as e:
            print(f"FATAL: Preflight connectivity failed: {e}")
            sys.exit(1)

    # 2. Domain & Baselines
    print("\n[Phase 2/4] Initializing Domain and Baseline Verification...")
    domain = PFSPFullAlgorithmDomain()
    train_neh = domain.baselines["train"]["neh"]["total_makespan"]
    train_neh_ls = domain.baselines["train"]["neh_ls"]["total_makespan"]
    test_neh = domain.baselines["test"]["neh"]["total_makespan"]
    test_neh_ls = domain.baselines["test"]["neh_ls"]["total_makespan"]

    print(f"  Training Baselines (18 instances):")
    print(f"    - NEH:    Total C_max = {train_neh:,} (avg: {domain.baselines['train']['neh']['mean_makespan']:.2f})")
    print(f"    - NEH-LS: Total C_max = {train_neh_ls:,} (avg: {domain.baselines['train']['neh_ls']['mean_makespan']:.2f}, rel: {(train_neh_ls - train_neh)/train_neh*100:+.2f}%)")
    print(f"  Held-Out Test Baselines (36 instances):")
    print(f"    - NEH:    Total C_max = {test_neh:,} (avg: {domain.baselines['test']['neh']['mean_makespan']:.2f})")
    print(f"    - NEH-LS: Total C_max = {test_neh_ls:,} (avg: {domain.baselines['test']['neh_ls']['mean_makespan']:.2f}, rel: {(test_neh_ls - test_neh)/test_neh*100:+.2f}%)")

    # 3. Candidate Generation Loop (32 proposals)
    print(f"\n[Phase 3/4] Generating {total_proposals} Independent Candidate Algorithms...")

    for p_idx in range(len(candidates), total_proposals):
        p_num = p_idx + 1
        print(f"  [Proposal {p_num:02d}/{total_proposals:02d}] Querying Nemotron-3 Super...", end="", flush=True)

        user_prompt = domain.get_user_prompt(p_num)
        ctx = {"domain": "pfsp_full_algorithm", "proposal_idx": p_idx}

        try:
            res = llm._query_model(domain.system_prompt, user_prompt, temperature=0.7, call_context=ctx)
        except Exception as e:
            print(f" ERROR calling live LLM: {e}")
            break

        text_to_search = res["content"] if ("```" in res["content"] or "def solve" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = llm._extract_code(text_to_search, "solve")
        code_hash = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()[:16]

        # Evaluate on training instances
        eval_train = domain.evaluate_candidate(code, on_test=False)

        record = {
            "proposal_idx": p_idx,
            "proposal_num": p_num,
            "function_name": "solve",
            "code_hash": code_hash,
            "code": code,
            "latency_sec": res["latency_sec"],
            "tokens": res["usage"],
            "train_evaluation": eval_train,
            "test_evaluation": None,  # Will be populated only for frozen champion and post-selection analysis
            "timestamp": time.time()
        }
        candidates.append(record)

        # Write to disk immediately
        with open(candidates_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        if eval_train["is_valid"]:
            cmax = eval_train["total_makespan"]
            gap = eval_train["relative_gap"] * 100
            beats_str = " [BEATS NEH!]" if eval_train["beats_neh"] else ""
            print(f" -> VALID (C_max={cmax:,}, gap={gap:+.2f}%){beats_str} ({res['latency_sec']}s)")
        else:
            err = eval_train["error"][:50]
            print(f" -> INVALID ({err}) ({res['latency_sec']}s)")

    # 4. Champion Selection & Held-Out Test Evaluation
    print("\n[Phase 4/4] Champion Selection & Held-Out Test Evaluation...")
    valid_cands = [c for c in candidates if c["train_evaluation"]["is_valid"]]
    print(f"  Valid Candidates: {len(valid_cands)} / {len(candidates)} ({len(valid_cands)/len(candidates)*100:.1f}%)")

    champion = None
    if valid_cands:
        # Champion is chosen strictly on training total makespan
        champion = min(valid_cands, key=lambda c: (c["train_evaluation"]["total_makespan"], c["proposal_idx"]))
        print(f"  Champion Selected: Proposal #{champion['proposal_num']} (Code Hash: {champion['code_hash']})")
        print(f"    Train Total C_max: {champion['train_evaluation']['total_makespan']:,} (Gap vs NEH: {champion['train_evaluation']['relative_gap']*100:+.2f}%)")

        # Evaluate champion on held-out test set
        print("  Evaluating Frozen Champion on Sealed Held-Out Test Set (36 instances)...")
        eval_test = domain.evaluate_candidate(champion["code"], on_test=True)
        if eval_test["is_valid"]:
            test_cmax = eval_test["total_makespan"]
            test_gap = eval_test["relative_gap"] * 100
            print(f"    Test Total C_max:  {test_cmax:,} (Gap vs NEH: {test_gap:+.2f}%)")
        else:
            print(f"    Test Total C_max:  INVALID ({eval_test['error']})")

        # Also evaluate remaining valid candidates on test for full empirical landscape
        for c in valid_cands:
            if c["proposal_idx"] != champion["proposal_idx"]:
                c["test_evaluation"] = domain.evaluate_candidate(c["code"], on_test=True)

    # 5. Replication of Candidates Crossing the Success Threshold
    replications = []
    discovery_candidates = []
    for c in valid_cands:
        train_beats = c["train_evaluation"].get("beats_neh", False)
        test_eval = c.get("test_evaluation") or {}
        test_gap = test_eval.get("relative_gap", 0.0)
        # Preregistered threshold: improves on train AND achieves at least 1.0% improvement on test (gap <= -0.010)
        if train_beats and test_eval.get("is_valid", False) and test_gap <= -0.010:
            discovery_candidates.append(c)

    if discovery_candidates:
        print(f"\n[Replication] Found {len(discovery_candidates)} candidate(s) crossing the >=1% held-out discovery gate! Replicating...")
        for dc in discovery_candidates:
            rep_res = replicate_candidate_on_fresh_instances(dc["code"], num_instances=10)
            rep_res["proposal_num"] = dc["proposal_num"]
            rep_res["code_hash"] = dc["code_hash"]
            replications.append(rep_res)
            print(f"  Candidate #{dc['proposal_num']}: Replicated={rep_res['replicated']} (Rel gain vs NEH: {rep_res['relative_gain']*100:+.2f}%, Wins: {rep_res['wins_vs_neh']}/10)")
    else:
        print("\n[Replication] No candidates reached the preregistered >=1.0% held-out improvement threshold over NEH.")

    # 6. Aggregate Diversity & Performance Statistics
    unique_hashes = len(set(c["code_hash"] for c in candidates))

    # Distinct schedule profiles on train
    schedule_signatures = set()
    for c in valid_cands:
        s_tuple = tuple(tuple(s) for s in c["train_evaluation"]["schedules"])
        schedule_signatures.add(s_tuple)
    unique_schedules = len(schedule_signatures)

    train_cmaxes = [c["train_evaluation"]["total_makespan"] for c in valid_cands]
    test_cmaxes = [c["test_evaluation"]["total_makespan"] for c in valid_cands if c.get("test_evaluation") and c["test_evaluation"]["is_valid"]]

    best_train_cmax = min(train_cmaxes) if train_cmaxes else None
    median_train_cmax = sorted(train_cmaxes)[len(train_cmaxes)//2] if train_cmaxes else None

    best_test_cmax = min(test_cmaxes) if test_cmaxes else None
    median_test_cmax = sorted(test_cmaxes)[len(test_cmaxes)//2] if test_cmaxes else None

    cands_beating_neh_train = sum(1 for c in valid_cands if c["train_evaluation"]["beats_neh"])
    cands_beating_neh_test = sum(1 for c in valid_cands if (c.get("test_evaluation") or {}).get("beats_neh", False))
    cands_beating_neh_ls_train = sum(1 for c in valid_cands if c["train_evaluation"]["total_makespan"] < train_neh_ls)
    cands_beating_neh_ls_test = sum(1 for c in valid_cands if (c.get("test_evaluation") or {}).get("total_makespan", float("inf")) < test_neh_ls)

    summary_data = {
        "experiment": "pfsp_full_algorithm_pilot_20261018",
        "timestamp": time.time(),
        "model": "nvidia/nvidia/nemotron-3-super-120b-a12b",
        "total_proposals": len(candidates),
        "valid_proposals": len(valid_cands),
        "validity_rate": round(len(valid_cands) / len(candidates), 4) if candidates else 0.0,
        "unique_code_hashes": unique_hashes,
        "unique_schedule_phenotypes": unique_schedules,
        "baselines": {
            "train": {
                "neh": train_neh,
                "neh_ls": train_neh_ls,
                "natural": domain.baselines["train"]["natural"]["total_makespan"]
            },
            "test": {
                "neh": test_neh,
                "neh_ls": test_neh_ls,
                "natural": domain.baselines["test"]["natural"]["total_makespan"]
            }
        },
        "performance": {
            "best_train_cmax": best_train_cmax,
            "median_train_cmax": median_train_cmax,
            "best_train_gap_vs_neh": round((best_train_cmax - train_neh) / train_neh, 6) if best_train_cmax else None,
            "best_test_cmax": best_test_cmax,
            "median_test_cmax": median_test_cmax,
            "best_test_gap_vs_neh": round((best_test_cmax - test_neh) / test_neh, 6) if best_test_cmax else None,
            "candidates_beating_neh_train": cands_beating_neh_train,
            "candidates_beating_neh_test": cands_beating_neh_test,
            "candidates_beating_neh_ls_train": cands_beating_neh_ls_train,
            "candidates_beating_neh_ls_test": cands_beating_neh_ls_test,
        },
        "champion": {
            "proposal_num": champion["proposal_num"] if champion else None,
            "code_hash": champion["code_hash"] if champion else None,
            "code": champion["code"] if champion else None,
            "train_cmax": champion["train_evaluation"]["total_makespan"] if champion else None,
            "train_gap": champion["train_evaluation"]["relative_gap"] if champion else None,
            "test_cmax": champion["test_evaluation"]["total_makespan"] if champion and champion.get("test_evaluation") else None,
            "test_gap": champion["test_evaluation"]["relative_gap"] if champion and champion.get("test_evaluation") else None,
        },
        "discovery_candidates_count": len(discovery_candidates),
        "replications": replications
    }

    summary_file = os.path.join(output_dir, "summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print(f"\n✓ Experiment Complete! Summary saved to {summary_file}")
    return summary_data


if __name__ == "__main__":
    run_pfsp_pilot()
