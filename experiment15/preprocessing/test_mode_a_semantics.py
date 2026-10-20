"""
Test Mode A Semantics & Hand-Calculated Cases
=============================================
Tests 5 synthetic cases with hand-calculated expected values:
Case 1: One pod, one node, known duration.
Case 2: Two overlapping pods.
Case 3: Two non-overlapping pods that can reuse one node.
Case 4: Two pods requiring two nodes simultaneously.
Case 5: A pod crossing the beginning/end of the measurement window.

Verifies:
Node-Hours = ∫ active_nodes(t) dt
over the pre-registered measurement window [W_start, W_end].
"""

import sys
from typing import Dict, Any, List
from experiment15.simulator.simulator import simulate_dynamic_replay


def dummy_select_node(pod: Dict[str, Any], feasible_nodes: List[Dict[str, Any]], state: Dict[str, Any]) -> int:
    # First fit / consolidate
    active = set(state.get("active_node_ids", []))
    for n in feasible_nodes:
        if n["id"] in active:
            return n["id"]
    return feasible_nodes[0]["id"]


def run_synthetic_cases():
    print("=" * 70)
    print("RUNNING MODE A SEMANTIC TESTS (5 HAND-CALCULATED BENCHMARK CASES)")
    print("=" * 70)

    nodes = [
        {"id": "node_0", "cpu_capacity": 96.0, "mem_capacity": 100.0, "cost_per_hour": 4.08},
        {"id": "node_1", "cpu_capacity": 96.0, "mem_capacity": 100.0, "cost_per_hour": 4.08}
    ]

    all_passed = True

    # -------------------------------------------------------------
    # Case 1: One pod, one node, known duration
    # Window: [0, 3600] (1h). Pod arrives t=600, duration=1800s (departs t=2400).
    # Active seconds: 1800s = 0.5h. Expected node-hours = 0.5000h, cost = $2.0400
    # -------------------------------------------------------------
    trace1 = {
        "start_time": 0,
        "end_time": 3600,
        "nodes": nodes,
        "events": [
            {"timestamp": 600, "pod": {"id": "p1", "cpu": 10.0, "mem": 10.0, "duration_sec": 1800.0}}
        ]
    }
    res1 = simulate_dynamic_replay(trace1, dummy_select_node)
    expected_nh1 = 0.5000
    expected_cost1 = 2.0400
    p1 = abs(res1["node_hours"] - expected_nh1) < 1e-4 and abs(res1["infrastructure_cost"] - expected_cost1) < 1e-4
    print(f"Case 1 (1 pod, known duration): {'PASS' if p1 else 'FAIL'} | Got: {res1['node_hours']}h (${res1['infrastructure_cost']}), Expected: {expected_nh1}h (${expected_cost1})")
    all_passed = all_passed and p1

    # -------------------------------------------------------------
    # Case 2: Two overlapping pods
    # Window: [0, 3600].
    # Pod 1: t=0, dur=1800s (departs t=1800).
    # Pod 2: t=900, dur=1800s (departs t=2700). Both fit on node_0.
    # Continuous active interval: [0, 2700] = 2700s = 0.75h. Expected = 0.7500h, cost = $3.0600
    # -------------------------------------------------------------
    trace2 = {
        "start_time": 0,
        "end_time": 3600,
        "nodes": nodes,
        "events": [
            {"timestamp": 0, "pod": {"id": "p1", "cpu": 10.0, "mem": 10.0, "duration_sec": 1800.0}},
            {"timestamp": 900, "pod": {"id": "p2", "cpu": 10.0, "mem": 10.0, "duration_sec": 1800.0}}
        ]
    }
    res2 = simulate_dynamic_replay(trace2, dummy_select_node)
    expected_nh2 = 0.7500
    expected_cost2 = 3.0600
    p2 = abs(res2["node_hours"] - expected_nh2) < 1e-4 and abs(res2["infrastructure_cost"] - expected_cost2) < 1e-4
    print(f"Case 2 (Two overlapping pods): {'PASS' if p2 else 'FAIL'} | Got: {res2['node_hours']}h (${res2['infrastructure_cost']}), Expected: {expected_nh2}h (${expected_cost2})")
    all_passed = all_passed and p2

    # -------------------------------------------------------------
    # Case 3: Two non-overlapping pods that can reuse one node
    # Window: [0, 3600].
    # Pod 1: t=0, dur=900s (departs t=900). Idle from 900 to 1800.
    # Pod 2: t=1800, dur=900s (departs t=2700). Placed on node_0.
    # Active intervals: [0, 900] + [1800, 2700] = 1800s = 0.5h. Expected = 0.5000h, cost = $2.0400
    # -------------------------------------------------------------
    trace3 = {
        "start_time": 0,
        "end_time": 3600,
        "nodes": nodes,
        "events": [
            {"timestamp": 0, "pod": {"id": "p1", "cpu": 10.0, "mem": 10.0, "duration_sec": 900.0}},
            {"timestamp": 1800, "pod": {"id": "p2", "cpu": 10.0, "mem": 10.0, "duration_sec": 900.0}}
        ]
    }
    res3 = simulate_dynamic_replay(trace3, dummy_select_node)
    expected_nh3 = 0.5000
    expected_cost3 = 2.0400
    p3 = abs(res3["node_hours"] - expected_nh3) < 1e-4 and abs(res3["infrastructure_cost"] - expected_cost3) < 1e-4
    print(f"Case 3 (Two non-overlapping pods): {'PASS' if p3 else 'FAIL'} | Got: {res3['node_hours']}h (${res3['infrastructure_cost']}), Expected: {expected_nh3}h (${expected_cost3})")
    all_passed = all_passed and p3

    # -------------------------------------------------------------
    # Case 4: Two pods requiring two nodes simultaneously
    # Window: [0, 3600].
    # Pod 1: cpu=60.0, arrives t=0, dur=1800s (departs t=1800) -> node_0
    # Pod 2: cpu=60.0, arrives t=0, dur=1800s (departs t=1800) -> node_1 (cannot fit on node_0)
    # Both active [0, 1800]: 1800s on node_0 (0.5h) + 1800s on node_1 (0.5h) = 1.0000h. Cost = $4.0800
    # -------------------------------------------------------------
    trace4 = {
        "start_time": 0,
        "end_time": 3600,
        "nodes": nodes,
        "events": [
            {"timestamp": 0, "pod": {"id": "p1", "cpu": 60.0, "mem": 10.0, "duration_sec": 1800.0}},
            {"timestamp": 0, "pod": {"id": "p2", "cpu": 60.0, "mem": 10.0, "duration_sec": 1800.0}}
        ]
    }
    res4 = simulate_dynamic_replay(trace4, dummy_select_node)
    expected_nh4 = 1.0000
    expected_cost4 = 4.0800
    p4 = abs(res4["node_hours"] - expected_nh4) < 1e-4 and abs(res4["infrastructure_cost"] - expected_cost4) < 1e-4
    print(f"Case 4 (Two nodes simultaneously): {'PASS' if p4 else 'FAIL'} | Got: {res4['node_hours']}h (${res4['infrastructure_cost']}), Expected: {expected_nh4}h (${expected_cost4})")
    all_passed = all_passed and p4

    # -------------------------------------------------------------
    # Case 5: Pod crossing beginning and end of measurement window
    # Window: [1000, 3000] (2000s window).
    # Pod 1: arrives before window at t=500, departs t=1500. Active inside window: [1000, 1500] = 500s.
    # Pod 2: arrives at t=2000, departs at t=3500 (after window). Active inside window: [2000, 3000] = 1000s.
    # Total active seconds inside window: 500 + 1000 = 1500s = 0.4167 hours.
    # Expected Cost: 0.4167 * 4.08 = $1.7000
    # -------------------------------------------------------------
    trace5 = {
        "start_time": 1000,
        "end_time": 3000,
        "nodes": nodes,
        "events": [
            {"timestamp": 500, "pod": {"id": "p1", "cpu": 10.0, "mem": 10.0, "duration_sec": 1000.0}},  # departs 1500
            {"timestamp": 2000, "pod": {"id": "p2", "cpu": 10.0, "mem": 10.0, "duration_sec": 1500.0}}  # departs 3500
        ]
    }
    res5 = simulate_dynamic_replay(trace5, dummy_select_node)
    expected_nh5 = round(1500.0 / 3600.0, 4)
    expected_cost5 = round((1500.0 / 3600.0) * 4.08, 4)
    p5 = abs(res5["node_hours"] - expected_nh5) < 1e-3 and abs(res5["infrastructure_cost"] - expected_cost5) < 1e-3
    print(f"Case 5 (Window boundary crossing): {'PASS' if p5 else 'FAIL'} | Got: {res5['node_hours']}h (${res5['infrastructure_cost']}), Expected: {expected_nh5}h (${expected_cost5})")
    all_passed = all_passed and p5

    print("\nSummary of Mode A Semantic Tests:", "ALL PASS" if all_passed else "SOME FAILED")
    return all_passed


if __name__ == "__main__":
    passed = run_synthetic_cases()
    sys.exit(0 if passed else 1)
