#!/usr/bin/env python3
"""
Controlled Representation Experiment: Online 1D Bin Packing
============================================================
Compares:
- Representation A: Priority heuristic `priority(item, remaining_capacity, bin_capacity) -> float`
- Representation B: Expanded policy `select_bin(item, open_bins, stream_history, bin_capacity) -> int`

Protocol:
- Same live frontier LLM: Nemotron-3 Super via OmniRoute
- Zero simulated fallback
- 16 proposals per representation (32 total measured calls)
- Shared 20 training streams (`train.json`)
- Shared 100 validation streams (`pilot_validation.json`)
- Baselines: Best-Fit, First-Fit, Worst-Fit
- Metrics: Validity, structural diversity, behavioral diversity, decision differences vs Best-Fit,
  training performance, held-out validation performance, replication verification.
"""

import ast
import hashlib
import json
import math
import os
import random
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

# Add repository root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from benchmark_v1.src.arms.generator import LiveLLMGenerator
from benchmark_v1.src.domains.bin_packing import BinPackingDomain
from benchmark_v1.src.domains.bin_packing_rep_b import BinPackingRepBDomain, StatefulBinPackingSimulator
from stage3.src.sandbox import check_ast_security, sanitize_and_compile, sanitize_exception_name, SAFE_BUILTINS
from stage4.src.simulator import DeterministicBinPackingSimulator, best_fit_priority, first_fit_priority, worst_fit_priority


def pack_stream_rep_a_with_decisions(
    items: List[float],
    priority_fn: Any,
    bin_capacity: float = 100.0,
    tolerance: float = 1e-6
) -> Tuple[int, List[float], int, float, List[int]]:
    """Evaluates Representation A candidate while tracking per-item bin placement decisions."""
    open_bins: List[float] = []
    decisions: List[int] = []

    for item in items:
        best_idx = -1
        best_p = -float("inf")
        for idx, rem in enumerate(open_bins):
            if rem >= item - tolerance:
                try:
                    p = float(priority_fn(item, rem, bin_capacity))
                except Exception as e:
                    raise RuntimeError(f"Candidate raised exception on item={item}, rem={rem}: {e}") from e

                if math.isnan(p) or math.isinf(p):
                    raise RuntimeError(f"Candidate returned non-finite priority {p} on item={item}, rem={rem}")

                if p > best_p:
                    best_p = p
                    best_idx = idx

        if best_idx >= 0 and best_p > -float("inf"):
            open_bins[best_idx] = round(open_bins[best_idx] - item, 8)
            decisions.append(best_idx)
        else:
            open_bins.append(round(bin_capacity - item, 8))
            decisions.append(-1)

    bins_used = len(open_bins)
    l1 = int(math.ceil(sum(items) / bin_capacity))
    rho = ((bins_used - l1) / float(l1)) if l1 > 0 else 0.0
    return bins_used, open_bins, l1, rho, decisions


def evaluate_rep_a_candidate(
    code_str: str,
    train_streams: List[List[float]],
    val_streams: List[List[float]],
    train_bf_decisions: List[List[int]],
    val_bf_decisions: List[List[int]],
    train_bf_rho: float,
    val_bf_rho: float
) -> Dict[str, Any]:
    t0 = time.time()
    is_safe, error_msg = check_ast_security(code_str, required_func="priority")
    if not is_safe:
        return {
            "is_valid": False,
            "error": error_msg,
            "train_score": 1.0,
            "train_rel_gap": 1.0,
            "train_beats_bf": False,
            "val_score": None,
            "val_rel_gap": None,
            "val_beats_bf": False,
            "decision_disagreement_rate": None,
            "runtime_ms": round((time.time() - t0) * 1000, 2),
            "stream_scores": []
        }

    try:
        code_obj = sanitize_and_compile(code_str, filename="<rep_a_candidate>")
        namespace = {"__builtins__": SAFE_BUILTINS, "math": math}
        exec(code_obj, namespace)
        cand_fn = namespace.get("priority")
        if not callable(cand_fn):
            return {
                "is_valid": False,
                "error": "Function 'priority' is not callable",
                "train_score": 1.0,
                "train_rel_gap": 1.0,
                "train_beats_bf": False,
                "val_score": None,
                "val_rel_gap": None,
                "val_beats_bf": False,
                "decision_disagreement_rate": None,
                "runtime_ms": round((time.time() - t0) * 1000, 2),
                "stream_scores": []
            }
    except Exception as e:
        return {
            "is_valid": False,
            "error": f"Compilation error: {sanitize_exception_name(e)}",
            "train_score": 1.0,
            "train_rel_gap": 1.0,
            "train_beats_bf": False,
            "val_score": None,
            "val_rel_gap": None,
            "val_beats_bf": False,
            "decision_disagreement_rate": None,
            "runtime_ms": round((time.time() - t0) * 1000, 2),
            "stream_scores": []
        }

    # Evaluate on train
    train_rhos = []
    cand_train_decisions = []
    try:
        for s in train_streams:
            _, _, _, rho, decs = pack_stream_rep_a_with_decisions(s, cand_fn)
            train_rhos.append(rho)
            cand_train_decisions.append(decs)
    except Exception as e:
        return {
            "is_valid": False,
            "error": f"Runtime execution error on train: {sanitize_exception_name(e)}",
            "train_score": 1.0,
            "train_rel_gap": 1.0,
            "train_beats_bf": False,
            "val_score": None,
            "val_rel_gap": None,
            "val_beats_bf": False,
            "decision_disagreement_rate": None,
            "runtime_ms": round((time.time() - t0) * 1000, 2),
            "stream_scores": []
        }

    train_score = sum(train_rhos) / len(train_rhos)
    train_rel_gap = (train_score - train_bf_rho) / train_bf_rho

    # Compute decision disagreement rate vs Best-Fit
    total_items = 0
    disagreements = 0
    for s_idx in range(len(train_streams)):
        bf_s = train_bf_decisions[s_idx]
        cd_s = cand_train_decisions[s_idx]
        for d_idx in range(min(len(bf_s), len(cd_s))):
            total_items += 1
            if bf_s[d_idx] != cd_s[d_idx]:
                disagreements += 1
    disagreement_rate = (disagreements / total_items) if total_items > 0 else 0.0

    # Evaluate on validation
    val_rhos = []
    try:
        for s in val_streams:
            _, _, _, rho, _ = pack_stream_rep_a_with_decisions(s, cand_fn)
            val_rhos.append(rho)
        val_score = sum(val_rhos) / len(val_rhos)
        val_rel_gap = (val_score - val_bf_rho) / val_bf_rho
        val_beats_bf = bool(val_score < val_bf_rho - 1e-6)
    except Exception as e:
        val_score = None
        val_rel_gap = None
        val_beats_bf = False

    return {
        "is_valid": True,
        "error": None,
        "train_score": round(train_score, 6),
        "train_rel_gap": round(train_rel_gap, 6),
        "train_beats_bf": bool(train_score < train_bf_rho - 1e-6),
        "val_score": round(val_score, 6) if val_score is not None else None,
        "val_rel_gap": round(val_rel_gap, 6) if val_rel_gap is not None else None,
        "val_beats_bf": val_beats_bf,
        "decision_disagreement_rate": round(disagreement_rate, 4),
        "runtime_ms": round((time.time() - t0) * 1000, 2),
        "stream_scores": [round(x, 6) for x in train_rhos]
    }


def evaluate_rep_b_candidate(
    code_str: str,
    domain_b: BinPackingRepBDomain
) -> Dict[str, Any]:
    # Evaluate on train
    res_train = domain_b.evaluate_candidate(code_str, on_validation=False)
    if not res_train["is_valid"]:
        return {
            "is_valid": False,
            "error": res_train["error"],
            "train_score": 1.0,
            "train_rel_gap": 1.0,
            "train_beats_bf": False,
            "val_score": None,
            "val_rel_gap": None,
            "val_beats_bf": False,
            "decision_disagreement_rate": None,
            "runtime_ms": res_train["runtime_ms"],
            "stream_scores": []
        }

    # Evaluate on validation
    res_val = domain_b.evaluate_candidate(code_str, on_validation=True)

    return {
        "is_valid": True,
        "error": None,
        "train_score": res_train["score"],
        "train_rel_gap": res_train["relative_gap"],
        "train_beats_bf": res_train["beats_baseline"],
        "val_score": res_val["score"] if res_val["is_valid"] else None,
        "val_rel_gap": res_val["relative_gap"] if res_val["is_valid"] else None,
        "val_beats_bf": res_val["beats_baseline"] if res_val["is_valid"] else False,
        "decision_disagreement_rate": res_train["decision_disagreement_rate"],
        "runtime_ms": res_train["runtime_ms"] + res_val["runtime_ms"],
        "stream_scores": res_train["stream_scores"]
    }


def replicate_candidate(cand_code: str, is_rep_b: bool = False, num_replications: int = 10) -> Dict[str, Any]:
    """Replicates a promising candidate across fresh random streams to confirm discovery."""
    from stage4.src.benchmark import BenchmarkStreamGenerator
    generator = BenchmarkStreamGenerator()
    fresh_streams = generator.generate_dataset(start_seed=88001, num_streams=num_replications, items_per_stream=1000)
    raw_streams = [s["items"] for s in fresh_streams]

    sim_a = DeterministicBinPackingSimulator(bin_capacity=100.0)
    bf_rhos = sim_a.evaluate_streams(raw_streams, best_fit_priority)["stream_excess_ratios"]
    bf_mean = sum(bf_rhos) / len(bf_rhos)

    code_obj = sanitize_and_compile(cand_code)
    ns = {"__builtins__": SAFE_BUILTINS, "math": math}
    exec(code_obj, ns)

    if not is_rep_b:
        cand_fn = ns["priority"]
        cand_rhos = sim_a.evaluate_streams(raw_streams, cand_fn)["stream_excess_ratios"]
    else:
        cand_fn = ns["select_bin"]
        sim_b = StatefulBinPackingSimulator(bin_capacity=100.0)
        cand_rhos = sim_b.evaluate_streams(raw_streams, cand_fn)["stream_excess_ratios"]

    cand_mean = sum(cand_rhos) / len(cand_rhos)
    beats_count = sum(1 for c, b in zip(cand_rhos, bf_rhos) if c < b - 1e-6)

    return {
        "num_streams": num_replications,
        "cand_mean_rho": round(cand_mean, 6),
        "bf_mean_rho": round(bf_mean, 6),
        "relative_gap": round((cand_mean - bf_mean) / bf_mean, 6),
        "streams_beating_bf": beats_count,
        "replicated_success": bool(cand_mean < bf_mean - 1e-6)
    }


def run_experiment():
    output_dir = os.path.join(REPO_ROOT, "benchmark_v1", "results", "representation_experiment_20261018")
    os.makedirs(output_dir, exist_ok=True)
    query_log_path = os.path.join(output_dir, "llm_queries.jsonl")

    print("=" * 80)
    print("AMAURA LABS — CONTROLLED CANDIDATE REPRESENTATION EXPERIMENT")
    print("Online 1D Bin Packing: Representation A vs. Representation B")
    print(f"Output Directory: {output_dir}")
    print("=" * 80)

    # 1. Connectivity Preflight
    print("\n[Phase 1/4] Preflight Connectivity Verification...")
    llm = LiveLLMGenerator(query_log_path=query_log_path)
    t0 = time.time()
    try:
        conn_test = llm._query_model("You are a test assistant.", "Reply with the exact word READY.")
        print(f"  ✓ Live Model Verified: {conn_test['model']}")
        print(f"  ✓ Latency: {conn_test['latency_sec']}s")
        print(f"  ✓ Response: {conn_test['content'].strip()}")
    except Exception as e:
        print(f"FATAL: Preflight connectivity failed: {e}")
        sys.exit(1)

    # 2. Domains and Baselines
    print("\n[Phase 2/4] Initializing Problem Domains and Computing Baselines...")
    domain_a = BinPackingDomain()
    domain_b = BinPackingRepBDomain()

    train_streams = domain_a.train_streams
    val_streams = domain_a.pilot_val_streams

    # Compute Best-Fit decisions on train and val for Representation A
    train_bf_decisions = []
    for s in train_streams:
        _, _, _, _, decs = pack_stream_rep_a_with_decisions(s, best_fit_priority)
        train_bf_decisions.append(decs)

    val_bf_decisions = []
    for s in val_streams:
        _, _, _, _, decs = pack_stream_rep_a_with_decisions(s, best_fit_priority)
        val_bf_decisions.append(decs)

    print(f"  Baselines (Training, 20 streams):")
    print(f"    - Best-Fit:  rho = {domain_a._baselines['train']['best_fit']:.6f}")
    print(f"    - First-Fit: rho = {domain_a._baselines['train']['first_fit']:.6f}")
    print(f"    - Worst-Fit: rho = {domain_a._baselines['train']['worst_fit']:.6f}")
    print(f"  Baselines (Validation, 100 streams):")
    print(f"    - Best-Fit:  rho = {domain_a._baselines['pilot_val']['best_fit']:.6f}")
    print(f"    - First-Fit: rho = {domain_a._baselines['pilot_val']['first_fit']:.6f}")
    print(f"    - Worst-Fit: rho = {domain_a._baselines['pilot_val']['worst_fit']:.6f}")

    assert abs(domain_a._baselines["train"]["best_fit"] - domain_b.baselines["train"]["best_fit"]) < 1e-6, "Baseline mismatch on train"
    assert abs(domain_a._baselines["pilot_val"]["best_fit"] - domain_b.baselines["val"]["best_fit"]) < 1e-6, "Baseline mismatch on val"
    print("  ✓ Domain baseline parity verified to 6 decimal places across representations.")

    num_proposals = 16
    rep_a_candidates: List[Dict[str, Any]] = []
    rep_b_candidates: List[Dict[str, Any]] = []

    # 3. Representation A Execution
    print(f"\n[Phase 3/4] Running Representation A ({num_proposals} independent proposals)...")
    rep_a_file = os.path.join(output_dir, "candidates_rep_a.jsonl")
    if os.path.exists(rep_a_file):
        with open(rep_a_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rep_a_candidates.append(json.loads(line))
        print(f"  Loaded {len(rep_a_candidates)} completed proposals from {rep_a_file}")

    for p_idx in range(len(rep_a_candidates), num_proposals):
        p_start = time.time()
        print(f"  [Rep A | Proposal {p_idx+1:02d}/{num_proposals:02d}] Calling Nemotron-3 Super...", end="", flush=True)

        user_prompt = (
            f"Design an innovative, high-performance online bin packing priority heuristic (variant {p_idx+1}).\n\n"
            "Baseline reference (Best-Fit):\n"
            "```python\n"
            "def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:\n"
            "    # Best-Fit: minimize leftover space\n"
            "    return -(remaining_capacity - item)\n"
            "```\n\n"
            "Can you explore non-linear combinations, multi-scale thresholds, item-to-capacity ratios, or waste penalties to outperform Best-Fit?\n"
            "Output the complete Python code for `priority` inside a ```python ``` block."
        )

        ctx = {"representation": "A", "proposal_idx": p_idx}
        res = llm._query_model(domain_a.system_prompt, user_prompt, temperature=0.7, call_context=ctx)
        text_to_search = res["content"] if ("```" in res["content"] or "def priority" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = llm._extract_code(text_to_search, "priority")
        code_hash = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()[:16]

        eval_res = evaluate_rep_a_candidate(
            code_str=code,
            train_streams=train_streams,
            val_streams=val_streams,
            train_bf_decisions=train_bf_decisions,
            val_bf_decisions=val_bf_decisions,
            train_bf_rho=domain_a._baselines["train"]["best_fit"],
            val_bf_rho=domain_a._baselines["pilot_val"]["best_fit"]
        )

        record = {
            "proposal_idx": p_idx,
            "representation": "A_stateless_priority",
            "function_name": "priority",
            "code_hash": code_hash,
            "code": code,
            "latency_sec": res["latency_sec"],
            "tokens": res["usage"],
            "evaluation": eval_res,
            "timestamp": time.time()
        }
        rep_a_candidates.append(record)

        # Write to JSONL immediately
        with open(rep_a_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        status_str = f"VALID (train_rho={eval_res['train_score']:.6f}, diff_rate={eval_res['decision_disagreement_rate']*100:.1f}%)" if eval_res["is_valid"] else f"INVALID ({eval_res['error']})"
        beats_str = " [BEATS BEST-FIT!]" if eval_res.get("train_beats_bf") else ""
        print(f" -> {status_str}{beats_str} ({res['latency_sec']}s)")

    # 4. Representation B Execution
    print(f"\n[Phase 4/4] Running Representation B ({num_proposals} independent proposals)...")
    rep_b_file = os.path.join(output_dir, "candidates_rep_b.jsonl")
    if os.path.exists(rep_b_file):
        with open(rep_b_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rep_b_candidates.append(json.loads(line))
        print(f"  Loaded {len(rep_b_candidates)} completed proposals from {rep_b_file}")

    for p_idx in range(len(rep_b_candidates), num_proposals):
        p_start = time.time()
        print(f"  [Rep B | Proposal {p_idx+1:02d}/{num_proposals:02d}] Calling Nemotron-3 Super...", end="", flush=True)

        user_prompt = domain_b.get_user_prompt(p_idx + 1)
        ctx = {"representation": "B", "proposal_idx": p_idx}
        res = llm._query_model(domain_b.system_prompt, user_prompt, temperature=0.7, call_context=ctx)
        text_to_search = res["content"] if ("```" in res["content"] or "def select_bin" in res["content"]) else f"{res['content']}\n{res['reasoning_content']}"
        code = llm._extract_code(text_to_search, "select_bin")
        code_hash = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()[:16]

        eval_res = evaluate_rep_b_candidate(code, domain_b)

        record = {
            "proposal_idx": p_idx,
            "representation": "B_stateful_select_bin",
            "function_name": "select_bin",
            "code_hash": code_hash,
            "code": code,
            "latency_sec": res["latency_sec"],
            "tokens": res["usage"],
            "evaluation": eval_res,
            "timestamp": time.time()
        }
        rep_b_candidates.append(record)

        # Write to JSONL immediately
        with open(rep_b_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        status_str = f"VALID (train_rho={eval_res['train_score']:.6f}, diff_rate={eval_res['decision_disagreement_rate']*100:.1f}%)" if eval_res["is_valid"] else f"INVALID ({eval_res['error']})"
        beats_str = " [BEATS BEST-FIT!]" if eval_res.get("train_beats_bf") else ""
        print(f" -> {status_str}{beats_str} ({res['latency_sec']}s)")

    # 5. Analysis and Synthesis
    print("\n[Analysis] Computing Cross-Representation Metrics...")

    def analyze_arm(candidates: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
        valid_cands = [c for c in candidates if c["evaluation"]["is_valid"]]
        valid_rate = len(valid_cands) / len(candidates) if candidates else 0.0

        # Structural diversity
        unique_hashes = len(set(c["code_hash"] for c in candidates))

        # Behavioral diversity
        unique_phenotypes = len(set(tuple(c["evaluation"]["stream_scores"]) for c in valid_cands if c["evaluation"]["stream_scores"]))

        # Decision differences
        diff_rates = [c["evaluation"]["decision_disagreement_rate"] for c in valid_cands if c["evaluation"]["decision_disagreement_rate"] is not None]
        mean_diff = sum(diff_rates) / len(diff_rates) if diff_rates else 0.0

        # Performance
        train_scores = [c["evaluation"]["train_score"] for c in valid_cands]
        val_scores = [c["evaluation"]["val_score"] for c in valid_cands if c["evaluation"]["val_score"] is not None]

        best_train = min(train_scores) if train_scores else 1.0
        median_train = sorted(train_scores)[len(train_scores)//2] if train_scores else 1.0

        best_val = min(val_scores) if val_scores else 1.0
        median_val = sorted(val_scores)[len(val_scores)//2] if val_scores else 1.0

        beats_bf_train = sum(1 for c in valid_cands if c["evaluation"]["train_beats_bf"])
        beats_bf_val = sum(1 for c in valid_cands if c["evaluation"]["val_beats_bf"])

        # Find champion (best train candidate)
        champion = None
        if valid_cands:
            champion = min(valid_cands, key=lambda c: (c["evaluation"]["train_score"], c["proposal_idx"]))

        return {
            "name": name,
            "total_proposals": len(candidates),
            "valid_proposals": len(valid_cands),
            "validity_rate": round(valid_rate, 4),
            "unique_code_hashes": unique_hashes,
            "unique_behavioral_phenotypes": unique_phenotypes,
            "mean_decision_disagreement_rate": round(mean_diff, 4),
            "best_train_rho": round(best_train, 6),
            "median_train_rho": round(median_train, 6),
            "best_val_rho": round(best_val, 6),
            "median_val_rho": round(median_val, 6),
            "candidates_beating_bf_train": beats_bf_train,
            "candidates_beating_bf_val": beats_bf_val,
            "champion": champion
        }

    summary_a = analyze_arm(rep_a_candidates, "Representation A (Stateless Priority)")
    summary_b = analyze_arm(rep_b_candidates, "Representation B (Stateful Select-Bin)")

    # Check for replication candidates
    discovery_candidates = []
    for c in rep_a_candidates + rep_b_candidates:
        if c["evaluation"]["is_valid"] and c["evaluation"]["train_beats_bf"] and c["evaluation"]["val_beats_bf"]:
            discovery_candidates.append(c)

    replication_results = []
    if discovery_candidates:
        print(f"\n[Replication] Found {len(discovery_candidates)} candidate(s) beating Best-Fit on both Train and Val! Replicating...")
        for dc in discovery_candidates:
            is_b = (dc["representation"] == "B_stateful_select_bin")
            rep_res = replicate_candidate(dc["code"], is_rep_b=is_b, num_replications=10)
            rep_res["candidate_id"] = f"{dc['representation']}_p{dc['proposal_idx']}"
            replication_results.append(rep_res)
            print(f"  Candidate {rep_res['candidate_id']}: Replicated = {rep_res['replicated_success']} (Mean rho: {rep_res['cand_mean_rho']} vs BF: {rep_res['bf_mean_rho']})")
    else:
        print("\n[Replication] No candidates strictly beat Best-Fit on both training and validation splits. Discovery threshold not met.")

    # Save summary.json
    summary_data = {
        "timestamp": time.time(),
        "model": "nvidia/nvidia/nemotron-3-super-120b-a12b",
        "budget_per_rep": num_proposals,
        "baselines": {
            "train": domain_a._baselines["train"],
            "val": domain_a._baselines["pilot_val"]
        },
        "representation_a": summary_a,
        "representation_b": summary_b,
        "discovery_candidates_count": len(discovery_candidates),
        "replications": replication_results
    }

    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print(f"\n✓ Experiment Complete! Summary saved to {os.path.join(output_dir, 'summary.json')}")
    return summary_data


if __name__ == "__main__":
    run_experiment()
