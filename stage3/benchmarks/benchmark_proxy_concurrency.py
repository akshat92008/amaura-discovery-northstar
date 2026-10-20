"""
Stage 3: Real-Prompt Proxy Concurrency Benchmark
================================================
Empirically benchmarks proxy throughput, latency, and response integrity
under concurrency levels 5, 10, 20, and 30 using the REAL Stage 3 generation prompt.

CRITICAL: Infrastructure benchmark only. Zero experimental candidates logged.
"""

import ast
import concurrent.futures
import json
import os
import time
from typing import Dict, Any, List
import numpy as np

from stage3.src.llm_client import Stage3LLMClient


def benchmark_concurrency():
    print("=" * 80)
    print("STAGE 3 REAL-PROMPT PROXY CONCURRENCY BENCHMARK")
    print("=" * 80)

    config_path = "stage3/config.json"
    with open(config_path) as f:
        config = json.load(f)

    with open(config["prompts"]["expert_gc"]) as f:
        expert_prompt = f.read()

    system_prompt = (
        "You are an expert combinatorial algorithm designer. "
        "Write a standalone Python function enclosed in ```python ... ``` blocks. "
        "Output the Python code directly without conversational preamble or verbose explanation."
    )

    client = Stage3LLMClient(
        model=config["model"],
        base_url=config["api_base_url"],
        api_key=config.get("api_key"),
        cost_per_m_input=3.00,
        cost_per_m_output=15.00,
        mock_mode=False,
        timeout=180
    )

    concurrency_levels = [5, 10, 20]
    benchmark_results: Dict[str, Any] = {}

    for c_level in concurrency_levels:
        print(f"\n--- Testing Concurrency Level: {c_level} ---", flush=True)

        def worker_task(worker_id):
            t0 = time.perf_counter()
            try:
                resp = client.query(
                    prompt=expert_prompt,
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=2048,  # Representative output token cap
                    expected_func="color_graph",
                    max_retries=1
                )
                dur = time.perf_counter() - t0
                # Check response integrity
                is_syntax_valid = False
                try:
                    ast.parse(resp["code"])
                    is_syntax_valid = True
                except Exception:
                    is_syntax_valid = False

                model_correct = "nemotron" in resp.get("returned_model", "").lower()

                return {
                    "worker_id": worker_id,
                    "success": resp["success"],
                    "latency_sec": dur,
                    "prompt_tokens": resp["prompt_tokens"],
                    "completion_tokens": resp["completion_tokens"],
                    "model_correct": model_correct,
                    "syntax_valid": is_syntax_valid,
                    "error": resp["error"]
                }
            except Exception as e:
                dur = time.perf_counter() - t0
                return {
                    "worker_id": worker_id,
                    "success": False,
                    "latency_sec": dur,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "model_correct": False,
                    "syntax_valid": False,
                    "error": str(e)
                }

        t_batch_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=c_level) as executor:
            res_list = list(executor.map(worker_task, range(c_level)))
        t_batch_dur = time.perf_counter() - t_batch_start

        latencies = [r["latency_sec"] for r in res_list]
        successes = sum(1 for r in res_list if r["success"])
        errors = c_level - successes
        model_correct_count = sum(1 for r in res_list if r["model_correct"])
        syntax_valid_count = sum(1 for r in res_list if r["syntax_valid"])
        total_tokens = sum(r["prompt_tokens"] + r["completion_tokens"] for r in res_list)
        total_completion_tokens = sum(r["completion_tokens"] for r in res_list)

        median_latency = float(np.median(latencies))
        p95_latency = float(np.percentile(latencies, 95))
        req_per_min = (successes / t_batch_dur) * 60.0
        tok_per_sec = total_completion_tokens / t_batch_dur if t_batch_dur > 0 else 0.0

        metrics = {
            "concurrency": c_level,
            "batch_duration_sec": round(t_batch_dur, 2),
            "requests_completed": successes,
            "requests_failed": errors,
            "error_rate": round(errors / c_level, 4),
            "median_latency_sec": round(median_latency, 2),
            "p95_latency_sec": round(p95_latency, 2),
            "requests_per_minute": round(req_per_min, 2),
            "token_throughput_tokens_per_sec": round(tok_per_sec, 2),
            "model_id_correct_rate": round(model_correct_count / c_level, 4),
            "syntax_valid_rate": round(syntax_valid_count / c_level, 4),
            "individual_latencies": [round(l, 2) for l in sorted(latencies)]
        }
        benchmark_results[f"concurrency_{c_level}"] = metrics

        print(f"Batch Duration: {t_batch_dur:.1f}s | Success: {successes}/{c_level} | Error Rate: {metrics['error_rate']:.1%}")
        print(f"Median Latency: {median_latency:.1f}s | p95: {p95_latency:.1f}s")
        print(f"Throughput: {req_per_min:.1f} req/min | {tok_per_sec:.1f} output tok/s")
        print(f"Model ID Correct: {model_correct_count}/{c_level} | Syntax Valid: {syntax_valid_count}/{c_level}")

        # If error rate > 0 at concurrency 20, don't test 30
        if errors > 0:
            print(f"Encountered errors at concurrency {c_level}; stopping concurrency ramp.")
            break

    # Also test concurrency 30 if 20 had 0 errors
    if benchmark_results.get("concurrency_20", {}).get("error_rate", 1.0) == 0.0:
        c_level = 30
        print(f"\n--- Testing Concurrency Level: {c_level} ---", flush=True)
        t_batch_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=c_level) as executor:
            res_list = list(executor.map(worker_task, range(c_level)))
        t_batch_dur = time.perf_counter() - t_batch_start

        latencies = [r["latency_sec"] for r in res_list]
        successes = sum(1 for r in res_list if r["success"])
        errors = c_level - successes
        model_correct_count = sum(1 for r in res_list if r["model_correct"])
        syntax_valid_count = sum(1 for r in res_list if r["syntax_valid"])
        total_completion_tokens = sum(r["completion_tokens"] for r in res_list)

        median_latency = float(np.median(latencies))
        p95_latency = float(np.percentile(latencies, 95))
        req_per_min = (successes / t_batch_dur) * 60.0
        tok_per_sec = total_completion_tokens / t_batch_dur if t_batch_dur > 0 else 0.0

        metrics = {
            "concurrency": c_level,
            "batch_duration_sec": round(t_batch_dur, 2),
            "requests_completed": successes,
            "requests_failed": errors,
            "error_rate": round(errors / c_level, 4),
            "median_latency_sec": round(median_latency, 2),
            "p95_latency_sec": round(p95_latency, 2),
            "requests_per_minute": round(req_per_min, 2),
            "token_throughput_tokens_per_sec": round(tok_per_sec, 2),
            "model_id_correct_rate": round(model_correct_count / c_level, 4),
            "syntax_valid_rate": round(syntax_valid_count / c_level, 4),
            "individual_latencies": [round(l, 2) for l in sorted(latencies)]
        }
        benchmark_results[f"concurrency_{c_level}"] = metrics

        print(f"Batch Duration: {t_batch_dur:.1f}s | Success: {successes}/{c_level} | Error Rate: {metrics['error_rate']:.1%}")
        print(f"Median Latency: {median_latency:.1f}s | p95: {p95_latency:.1f}s")
        print(f"Throughput: {req_per_min:.1f} req/min | {tok_per_sec:.1f} output tok/s")

    os.makedirs("stage3/audit", exist_ok=True)
    with open("stage3/audit/concurrency_benchmark.json", "w") as f:
        json.dump(benchmark_results, f, indent=2)

    print("\nBenchmark results saved to stage3/audit/concurrency_benchmark.json")
    return benchmark_results


if __name__ == "__main__":
    benchmark_concurrency()
