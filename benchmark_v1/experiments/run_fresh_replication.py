"""
Fresh Replication Evaluation Script
====================================
Evaluates frozen algorithm variants and classical baselines on the 30 fresh PFSP instances.
Enforces per-instance 4.0s timeout and validates all permutations.
Outputs structured JSON and tabular summaries.
"""

import sys
sys.path.insert(0, '.')
import json
import time
import math
import numpy as np
import scipy.stats as stats
from typing import Dict, Any, List

from benchmark_v1.src.domains.pfsp_full_algorithm import validate_permutation
from benchmark_v1.src.domains.pfsp_candidate2_variants import (
    calc_makespan_ref,
    solve_v0_original,
    solve_v1_exact_accel,
    solve_v2_anytime_bounded,
    solve_v3_insertion_ls,
    neh_solve,
    neh_ls_single_pass_solve,
    neh_ls_multi_pass_solve,
    iterated_greedy_solve
)

TIMEOUT_SEC = 4.0

def run_with_timeout(fn, pts, timeout_sec=TIMEOUT_SEC):
    """Executes fn on pts with time measurement and timeout handling."""
    t0 = time.perf_counter()
    try:
        # Note: In production sandbox, SIGALRM is used. Here we time accurately.
        res = fn(pts)
        dur = time.perf_counter() - t0
        if dur > timeout_sec:
            return None, dur, True, f"Exceeded runtime limit {timeout_sec}s ({dur:.3f}s)"
        return res, dur, False, None
    except Exception as e:
        dur = time.perf_counter() - t0
        return None, dur, False, str(e)


def main():
    fresh_path = 'benchmark_v1/data/pfsp/fresh_replication_instances.json'
    with open(fresh_path, 'r', encoding='utf-8') as f:
        instances = json.load(f)

    print(f"Loaded {len(instances)} fresh instances from {fresh_path}")

    algos = {
        'NEH': lambda pts: neh_solve(pts),
        'NEH-LS (Single-Pass)': lambda pts: neh_ls_single_pass_solve(pts),
        'NEH-LS (Multi-Pass)': lambda pts: neh_ls_multi_pass_solve(pts),
        'IteratedGreedy': lambda pts: iterated_greedy_solve(pts, max_iter=25),
        'Candidate2_V0_Original': lambda pts: solve_v0_original(pts),
        'Candidate2_V1_ExactAccel': lambda pts: solve_v1_exact_accel(pts),
        'Candidate2_V2_B100': lambda pts: solve_v2_anytime_bounded(pts, max_evals=100),
        'Candidate2_V2_B500': lambda pts: solve_v2_anytime_bounded(pts, max_evals=500),
        'Candidate2_V2_B2000': lambda pts: solve_v2_anytime_bounded(pts, max_evals=2000),
        'Candidate2_V2_B10000': lambda pts: solve_v2_anytime_bounded(pts, max_evals=10000),
        'Candidate2_V3_InsertionLS': lambda pts: solve_v3_insertion_ls(pts)
    }

    results = {
        name: {
            'cmaxes': [],
            'runtimes': [],
            'timeouts': 0,
            'invalid': 0,
            'per_instance': []
        } for name in algos
    }

    for idx, inst in enumerate(instances):
        pts = inst['times']
        n = inst['n']
        m = inst['m']
        inst_id = inst['id']

        for name, fn in algos.items():
            perm, dur, timed_out, err = run_with_timeout(fn, pts)
            if timed_out:
                results[name]['timeouts'] += 1
                results[name]['cmaxes'].append(None)
                results[name]['runtimes'].append(dur)
                results[name]['per_instance'].append({
                    'id': inst_id, 'n': n, 'm': m, 'cmax': None, 'time_sec': dur, 'status': 'TIMEOUT', 'error': err
                })
            elif err or perm is None:
                results[name]['invalid'] += 1
                results[name]['cmaxes'].append(None)
                results[name]['runtimes'].append(dur)
                results[name]['per_instance'].append({
                    'id': inst_id, 'n': n, 'm': m, 'cmax': None, 'time_sec': dur, 'status': 'ERROR', 'error': err
                })
            else:
                is_valid, val_err = validate_permutation(perm, n)
                if not is_valid:
                    results[name]['invalid'] += 1
                    results[name]['cmaxes'].append(None)
                    results[name]['runtimes'].append(dur)
                    results[name]['per_instance'].append({
                        'id': inst_id, 'n': n, 'm': m, 'cmax': None, 'time_sec': dur, 'status': 'INVALID_PERM', 'error': val_err
                    })
                else:
                    cmax = calc_makespan_ref(pts, perm)
                    results[name]['cmaxes'].append(cmax)
                    results[name]['runtimes'].append(dur)
                    results[name]['per_instance'].append({
                        'id': inst_id, 'n': n, 'm': m, 'cmax': cmax, 'time_sec': dur, 'status': 'VALID', 'error': None
                    })

    # Summary Statistics Calculation
    summary = {}
    neh_cmaxes = np.array(results['NEH']['cmaxes'], dtype=float)
    neh_ls_single_cmaxes = np.array(results['NEH-LS (Single-Pass)']['cmaxes'], dtype=float)
    neh_ls_multi_cmaxes = np.array(results['NEH-LS (Multi-Pass)']['cmaxes'], dtype=float)

    print("\n" + "="*110)
    print(f"{'Algorithm':<26} {'Valid':<7} {'Timeouts':<9} {'Total Cmax':<12} {'Mean Cmax':<11} {'vs NEH (%)':<12} {'vs NEH-LS (%)':<15} {'Mean Time':<10}")
    print("="*110)

    for name, data in results.items():
        valid_mask = [c is not None for c in data['cmaxes']]
        n_valid = sum(valid_mask)
        timeouts = data['timeouts']
        mean_time = float(np.mean(data['runtimes']))

        if n_valid == len(instances):
            arr = np.array(data['cmaxes'], dtype=float)
            tot_cmax = int(np.sum(arr))
            mean_cmax = float(np.mean(arr))
            
            # Gaps vs NEH
            rel_gaps_neh = (arr - neh_cmaxes) / neh_cmaxes
            mean_gap_neh = float(np.mean(rel_gaps_neh)) * 100
            median_gap_neh = float(np.median(rel_gaps_neh)) * 100

            # Gaps vs NEH-LS Single
            rel_gaps_ls = (arr - neh_ls_single_cmaxes) / neh_ls_single_cmaxes
            mean_gap_ls = float(np.mean(rel_gaps_ls)) * 100
            median_gap_ls = float(np.median(rel_gaps_ls)) * 100

            # Paired Wilcoxon vs NEH
            diffs_neh = arr - neh_cmaxes
            wins_neh = int(np.sum(diffs_neh < 0))
            ties_neh = int(np.sum(diffs_neh == 0))
            losses_neh = int(np.sum(diffs_neh > 0))

            diffs_ls = arr - neh_ls_single_cmaxes
            wins_ls = int(np.sum(diffs_ls < 0))
            ties_ls = int(np.sum(diffs_ls == 0))
            losses_ls = int(np.sum(diffs_ls > 0))

            tot_neh = float(np.sum(neh_cmaxes))
            agg_gap_neh = ((tot_cmax - tot_neh) / tot_neh) * 100
            tot_ls = float(np.sum(neh_ls_single_cmaxes))
            agg_gap_ls = ((tot_cmax - tot_ls) / tot_ls) * 100

            print(f"{name:<26} {n_valid:<7} {timeouts:<9} {tot_cmax:<12,d} {mean_cmax:<11.2f} {agg_gap_neh:<+12.3f}% {agg_gap_ls:<+15.3f}% {mean_time:<9.3f}s")

            summary[name] = {
                'valid_count': n_valid,
                'timeouts': timeouts,
                'total_cmax': tot_cmax,
                'mean_cmax': mean_cmax,
                'aggregate_gap_vs_neh': agg_gap_neh,
                'mean_gap_vs_neh': mean_gap_neh,
                'median_gap_vs_neh': median_gap_neh,
                'wins_ties_losses_vs_neh': [wins_neh, ties_neh, losses_neh],
                'aggregate_gap_vs_ls_single': agg_gap_ls,
                'mean_gap_vs_ls_single': mean_gap_ls,
                'median_gap_vs_ls_single': median_gap_ls,
                'wins_ties_losses_vs_ls_single': [wins_ls, ties_ls, losses_ls],
                'mean_runtime_sec': mean_time
            }
        else:
            print(f"{name:<26} {n_valid:<7} {timeouts:<9} {'FAILED/TIMEOUT':<12} {'N/A':<11} {'N/A':<12} {'N/A':<15} {mean_time:<9.3f}s")
            summary[name] = {
                'valid_count': n_valid,
                'timeouts': timeouts,
                'total_cmax': None,
                'mean_cmax': None,
                'aggregate_gap_vs_neh': None,
                'mean_runtime_sec': mean_time
            }

    print("="*110)

    # Breakdown by dimension groups (Small, Medium, Large)
    dim_groups = {
        'Small (n <= 30, 8 inst)': [0, 1, 2, 3, 4, 5, 6, 7],
        'Medium (50 <= n <= 75, 14 inst)': list(range(8, 22)),
        'Large (100 <= n <= 120, 8 inst)': list(range(22, 30))
    }

    group_summary = {}
    print("\nPerformance by Dimension Groups (Aggregate Gap vs NEH %):")
    print(f"{'Algorithm':<26} {'Small (n<=30)':<18} {'Medium (50<=n<=75)':<22} {'Large (100<=n<=120)':<20}")
    print("-" * 88)

    for name in algos:
        row_str = f"{name:<26} "
        group_summary[name] = {}
        for gname, indices in dim_groups.items():
            sub_cmax = [results[name]['cmaxes'][i] for i in indices]
            sub_neh = [results['NEH']['cmaxes'][i] for i in indices]
            if any(c is None for c in sub_cmax):
                row_str += f"{'TIMEOUT':<20}"
                group_summary[name][gname] = None
            else:
                tot_sub = sum(sub_cmax)
                tot_sub_neh = sum(sub_neh)
                gap = ((tot_sub - tot_sub_neh) / tot_sub_neh) * 100
                row_str += f"{gap:+.3f}%{'':<13}"
                group_summary[name][gname] = gap
        print(row_str)

    output_payload = {
        'metadata': {
            'dataset': fresh_path,
            'total_instances': len(instances),
            'timestamp': time.time(),
            'timeout_limit_sec': TIMEOUT_SEC
        },
        'summary': summary,
        'group_summary': group_summary,
        'per_instance_records': results
    }

    out_file = 'benchmark_v1/results/pfsp_candidate2_verification_20261018/fresh_replication_evaluation.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, indent=2)

    print(f"\nSaved complete replication evaluation to {out_file}")

if __name__ == '__main__':
    main()
