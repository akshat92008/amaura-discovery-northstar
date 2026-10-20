"""
Build Pre-Registered Benchmarks for Experiment #15
===================================================
Extracts:
1. Development Benchmark (Day 1: t = 86400 to 172800)
   - 20 Mode B static packing windows
   - 2 Mode A dynamic replay traces (4h each)
2. Validation Benchmark (Day 2: t = 172800 to 259200)
   - 20 Mode B static packing windows
   - 2 Mode A dynamic replay traces (4h each)
3. Hidden Production Benchmark (Days 3-4: t = 259200 to 432000)
   - 60 Mode B static packing windows across 3 regimes (Low, Medium, High)
   - 10 Mode A dynamic replay traces (4h each)

Saves all benchmarks to JSON and calculates SHA-256 manifest.
"""

import os
import sys
import json
import csv
import hashlib
from typing import Dict, Any, List


RAW_CONTAINERS = "experiment15/data/raw/container_meta.csv"
BENCH_DIR = "experiment15/benchmarks"


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_raw_containers(start_t: int, end_t: int) -> List[Dict[str, Any]]:
    records = []
    seen = set()
    with open(RAW_CONTAINERS, "r") as f:
        r = csv.reader(f)
        for row in r:
            if len(row) >= 8 and row[4] == "started":
                ts = int(row[2])
                if start_t <= ts < end_t:
                    cid = row[0]
                    if cid in seen:
                        continue
                    seen.add(cid)
                    cpu_cores = int(row[5]) / 100.0
                    mem_norm = float(row[7])
                    records.append({
                        "id": cid,
                        "timestamp": ts,
                        "cpu": cpu_cores,
                        "mem": mem_norm,
                        "duration_sec": 3600.0  # standard 1h service horizon
                    })
    records.sort(key=lambda x: x["timestamp"])
    return records


def build_node_pool(pods: List[Dict[str, Any]], multiplier: float = 2.0, min_nodes: int = 15) -> List[Dict[str, Any]]:
    total_cpu = sum(p["cpu"] for p in pods)
    total_mem = sum(p["mem"] for p in pods)
    min_cpu_nodes = math_ceil(total_cpu / 96.0)
    min_mem_nodes = math_ceil(total_mem / 100.0)
    needed = max(min_cpu_nodes, min_mem_nodes)
    num_nodes = max(min_nodes, int(needed * multiplier))

    return [
        {
            "id": f"node_{i:04d}",
            "cpu_capacity": 96.0,
            "mem_capacity": 100.0,
            "cost_per_hour": 4.08
        }
        for i in range(num_nodes)
    ]


def math_ceil(val: float) -> int:
    import math
    return math.ceil(val)


def build_static_windows(containers: List[Dict[str, Any]], start_t: int, end_t: int, window_sec: int, max_instances: int, regime_label: str) -> List[Dict[str, Any]]:
    windows = []
    curr_t = start_t
    w_idx = 0

    while curr_t < end_t and len(windows) < max_instances:
        w_end = curr_t + window_sec
        w_pods = [
            {
                "id": c["id"],
                "cpu": c["cpu"],
                "mem": c["mem"]
            }
            for c in containers if curr_t <= c["timestamp"] < w_end
        ]

        if len(w_pods) >= 15:  # meaningful batch
            nodes = build_node_pool(w_pods)
            windows.append({
                "instance_id": f"{regime_label}_w{w_idx:03d}",
                "window_start": curr_t,
                "window_end": w_end,
                "regime": regime_label,
                "pod_count": len(w_pods),
                "total_cpu": round(sum(p["cpu"] for p in w_pods), 2),
                "total_mem": round(sum(p["mem"] for p in w_pods), 2),
                "nodes": nodes,
                "pods": w_pods
            })
            w_idx += 1

        curr_t += window_sec

    return windows


def build_dynamic_traces(containers: List[Dict[str, Any]], start_t: int, end_t: int, duration_sec: int, max_traces: int, prefix: str) -> List[Dict[str, Any]]:
    traces = []
    curr_t = start_t
    t_idx = 0

    while curr_t + duration_sec <= end_t and len(traces) < max_traces:
        sub_end = curr_t + duration_sec
        events = []
        for c in containers:
            if curr_t <= c["timestamp"] < sub_end:
                events.append({
                    "timestamp": c["timestamp"] - curr_t,  # relative to trace start
                    "pod": {
                        "id": c["id"],
                        "cpu": c["cpu"],
                        "mem": c["mem"],
                        "duration_sec": 3600.0  # 1h service lifetime
                    }
                })

        if len(events) >= 50:
            all_pods = [ev["pod"] for ev in events]
            nodes = build_node_pool(all_pods, multiplier=1.8, min_nodes=20)
            traces.append({
                "trace_id": f"{prefix}_dyn_{t_idx:02d}",
                "start_time": 0,
                "end_time": duration_sec,
                "pod_count": len(events),
                "nodes": nodes,
                "events": events
            })
            t_idx += 1

        curr_t += duration_sec

    return traces


def main():
    os.makedirs(f"{BENCH_DIR}/dev", exist_ok=True)
    os.makedirs(f"{BENCH_DIR}/val", exist_ok=True)
    os.makedirs(f"{BENCH_DIR}/hidden", exist_ok=True)

    print("Loading Day 1 (Dev) containers...")
    dev_containers = load_raw_containers(86400, 172800)
    print(f"  Day 1: {len(dev_containers)} unique containers.")

    print("Loading Day 2 (Val) containers...")
    val_containers = load_raw_containers(172800, 259200)
    print(f"  Day 2: {len(val_containers)} unique containers.")

    print("Loading Days 3-4 (Hidden) containers...")
    hidden_containers = load_raw_containers(259200, 432000)
    print(f"  Days 3-4: {len(hidden_containers)} unique containers.")

    # 1. Dev Benchmarks
    dev_static = build_static_windows(dev_containers, 86400, 172800, window_sec=1800, max_instances=20, regime_label="dev")
    dev_dynamic = build_dynamic_traces(dev_containers, 86400, 172800, duration_sec=14400, max_traces=2, prefix="dev")

    # 2. Val Benchmarks
    val_static = build_static_windows(val_containers, 172800, 259200, window_sec=1800, max_instances=20, regime_label="val")
    val_dynamic = build_dynamic_traces(val_containers, 172800, 259200, duration_sec=14400, max_traces=2, prefix="val")

    # 3. Hidden Benchmarks (60 Mode B static windows: 20 Low, 20 Med, 20 High)
    hidden_low = build_static_windows(hidden_containers, 259200, 316800, window_sec=900, max_instances=20, regime_label="hidden_low")
    hidden_med = build_static_windows(hidden_containers, 316800, 374400, window_sec=1800, max_instances=20, regime_label="hidden_med")
    hidden_high = build_static_windows(hidden_containers, 374400, 432000, window_sec=3600, max_instances=20, regime_label="hidden_high")
    hidden_static = hidden_low + hidden_med + hidden_high

    hidden_dynamic = build_dynamic_traces(hidden_containers, 259200, 432000, duration_sec=14400, max_traces=10, prefix="hidden")

    # Save to disk
    with open(f"{BENCH_DIR}/dev/mode_b_static.json", "w") as f:
        json.dump(dev_static, f, indent=2)
    with open(f"{BENCH_DIR}/dev/mode_a_dynamic.json", "w") as f:
        json.dump(dev_dynamic, f, indent=2)

    with open(f"{BENCH_DIR}/val/mode_b_static.json", "w") as f:
        json.dump(val_static, f, indent=2)
    with open(f"{BENCH_DIR}/val/mode_a_dynamic.json", "w") as f:
        json.dump(val_dynamic, f, indent=2)

    with open(f"{BENCH_DIR}/hidden/mode_b_static.json", "w") as f:
        json.dump(hidden_static, f, indent=2)
    with open(f"{BENCH_DIR}/hidden/mode_a_dynamic.json", "w") as f:
        json.dump(hidden_dynamic, f, indent=2)

    # Manifest
    manifest = {
        "dev_static": {
            "instances": len(dev_static),
            "sha256": sha256_file(f"{BENCH_DIR}/dev/mode_b_static.json")
        },
        "dev_dynamic": {
            "traces": len(dev_dynamic),
            "sha256": sha256_file(f"{BENCH_DIR}/dev/mode_a_dynamic.json")
        },
        "val_static": {
            "instances": len(val_static),
            "sha256": sha256_file(f"{BENCH_DIR}/val/mode_b_static.json")
        },
        "val_dynamic": {
            "traces": len(val_dynamic),
            "sha256": sha256_file(f"{BENCH_DIR}/val/mode_a_dynamic.json")
        },
        "hidden_static": {
            "instances": len(hidden_static),
            "sha256": sha256_file(f"{BENCH_DIR}/hidden/mode_b_static.json")
        },
        "hidden_dynamic": {
            "traces": len(hidden_dynamic),
            "sha256": sha256_file(f"{BENCH_DIR}/hidden/mode_a_dynamic.json")
        }
    }

    with open(f"{BENCH_DIR}/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print("\nBenchmark Generation Complete.")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
