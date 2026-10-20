"""
Generate comprehensive diagnostic plots for the PFSP Candidate #2 Verification Experiment.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import os

os.makedirs('benchmark_v1/results/pfsp_candidate2_verification_20261018/plots', exist_ok=True)

with open('benchmark_v1/results/pfsp_candidate2_verification_20261018/fresh_replication_evaluation.json') as f:
    eval_data = json.load(f)

with open('benchmark_v1/results/pfsp_candidate2_verification_20261018/training_baseline_comparison.json') as f:
    train_data = json.load(f)

summary = eval_data['summary']
group_summary = eval_data['group_summary']
per_inst = eval_data['per_instance_records']

fig = plt.figure(figsize=(16, 12))

# ------------------------------------------------------------------------------
# Panel A: Quality vs Compute Curve (Variant 2 Anytime Bounded)
# ------------------------------------------------------------------------------
ax1 = plt.subplot2grid((2, 2), (0, 0))

budgets = [100, 500, 2000, 10000]
b_keys = ['Candidate2_V2_B100', 'Candidate2_V2_B500', 'Candidate2_V2_B2000', 'Candidate2_V2_B10000']

# Training Gaps vs NEH
train_neh_tot = train_data['NEH']['total_cmax']
train_gaps = [((train_data[k]['total_cmax'] - train_neh_tot) / train_neh_tot) * 100 for k in b_keys]

# Fresh Replication Gaps vs NEH
fresh_neh_tot = summary['NEH']['total_cmax']
fresh_gaps = [((summary[k]['total_cmax'] - fresh_neh_tot) / fresh_neh_tot) * 100 for k in b_keys]

ax1.plot(budgets, train_gaps, 'o-', color='#1f77b4', linewidth=2, markersize=7, label='Training Suite (18 instances)')
ax1.plot(budgets, fresh_gaps, 's--', color='#2ca02c', linewidth=2, markersize=7, label='Fresh Replication Suite (30 instances)')
ax1.axhline(-0.510, color='#ff7f0e', linestyle=':', linewidth=1.5, label='NEH-LS Single-Pass Baseline (-0.51%)')
ax1.axhline(-1.000, color='red', linestyle='--', linewidth=1.5, label='Preregistered Gate Threshold (-1.0%)')

ax1.set_xscale('log')
ax1.set_xlabel("Local Search Move Evaluation Budget", fontsize=10)
ax1.set_ylabel("Relative Makespan Gap vs NEH (%)", fontsize=10)
ax1.set_title("A. Quality-vs-Compute Convergence (Variant 2 Anytime)\nNegative = Better Makespan", fontsize=11, fontweight='bold')
ax1.grid(True, linestyle='--', alpha=0.5)
ax1.legend(loc='lower left', fontsize=9)

for b, g in zip(budgets, fresh_gaps):
    ax1.annotate(f"{g:.2f}%", (b, g), textcoords="offset points", xytext=(0, -14), ha='center', fontsize=8, fontweight='bold')

# ------------------------------------------------------------------------------
# Panel B: Aggregate Makespan on 30 Fresh Untouched Instances
# ------------------------------------------------------------------------------
ax2 = plt.subplot2grid((2, 2), (0, 1))

comp_models = [
    'NEH',
    'IteratedGreedy',
    'NEH-LS (Single)',
    'Candidate2 (V2 B10k)'
]
comp_scores = [
    summary['NEH']['total_cmax'],
    summary['IteratedGreedy']['total_cmax'],
    summary['NEH-LS (Single-Pass)']['total_cmax'],
    summary['Candidate2_V2_B10000']['total_cmax']
]
colors = ['#1f77b4', '#9467bd', '#ff7f0e', '#2ca02c']

bars2 = ax2.bar(comp_models, comp_scores, color=colors, width=0.55, edgecolor='black', linewidth=0.8)
ax2.set_ylabel("Total Makespan ($C_{max}$)", fontsize=10)
ax2.set_title("B. Fresh Replication Performance (30 Untouched Instances)\nLower is Better", fontsize=11, fontweight='bold')

min_y = min(comp_scores) - 400
max_y = max(comp_scores) + 300
ax2.set_ylim(min_y, max_y)
ax2.grid(axis='y', linestyle='--', alpha=0.5)

for bar, s in zip(bars2, comp_scores):
    diff = s - comp_scores[0]
    label = f"{s:,}\n(Ref)" if diff == 0 else f"{s:,}\n({diff:+d}, {diff/comp_scores[0]*100:+.2f}%)"
    ax2.text(bar.get_x() + bar.get_width() / 2, s + 30, label, ha='center', va='bottom', fontsize=8.5, fontweight='bold')

# ------------------------------------------------------------------------------
# Panel C: Performance by Problem Dimension Groups
# ------------------------------------------------------------------------------
ax3 = plt.subplot2grid((2, 2), (1, 0))

groups = ['Small\n(n<=30, 8 inst)', 'Medium\n(50<=n<=75, 14 inst)', 'Large\n(100<=n<=120, 8 inst)']
x = np.arange(len(groups))
width = 0.22

g_neh_ls = [group_summary['NEH-LS (Single-Pass)'][k] for k in group_summary['NEH-LS (Single-Pass)']]
g_ig = [group_summary['IteratedGreedy'][k] for k in group_summary['IteratedGreedy']]
g_cand2 = [group_summary['Candidate2_V2_B10000'][k] for k in group_summary['Candidate2_V2_B10000']]

rects1 = ax3.bar(x - width, g_neh_ls, width, label='NEH-LS (Single-Pass)', color='#ff7f0e', edgecolor='black')
rects2 = ax3.bar(x, g_ig, width, label='Iterated Greedy', color='#9467bd', edgecolor='black')
rects3 = ax3.bar(x + width, g_cand2, width, label='Candidate #2 (V2 B10k)', color='#2ca02c', edgecolor='black')

ax3.axhline(0, color='black', linewidth=0.8)
ax3.axhline(-1.0, color='red', linestyle='--', linewidth=1.0, label='-1.0% Gate Threshold')
ax3.set_xticks(x)
ax3.set_xticklabels(groups, fontsize=9.5)
ax3.set_ylabel("Makespan Gap vs NEH (%)", fontsize=10)
ax3.set_title("C. Generalization Breakdown by Instance Size\nCandidate #2 Wins on Medium & Large", fontsize=11, fontweight='bold')
ax3.legend(loc='lower left', fontsize=8.5)
ax3.grid(axis='y', linestyle='--', alpha=0.5)

# ------------------------------------------------------------------------------
# Panel D: Runtime Scaling Comparison Across Problem Sizes
# ------------------------------------------------------------------------------
ax4 = plt.subplot2grid((2, 2), (1, 1))

# Collect runtime by instance size from per_instance records
sizes = [inst['n'] for inst in eval_data['metadata']['dataset']] if False else [20, 20, 20, 20, 30, 30, 30, 30, 50, 50, 50, 50, 50, 50, 50, 50, 75, 75, 75, 75, 75, 75, 100, 100, 100, 100, 120, 120, 120, 120]

# Aggregate runtimes by unique job counts n
unique_n = [20, 30, 50, 75, 100, 120]
t_v0_mean = []
t_v1_mean = []
t_v2_mean = []
t_neh_mean = []

for un in unique_n:
    idx_list = [i for i, s in enumerate(sizes) if s == un]
    t_v0_mean.append(np.mean([per_inst['Candidate2_V0_Original']['runtimes'][i] for i in idx_list]))
    t_v1_mean.append(np.mean([per_inst['Candidate2_V1_ExactAccel']['runtimes'][i] for i in idx_list]))
    t_v2_mean.append(np.mean([per_inst['Candidate2_V2_B10000']['runtimes'][i] for i in idx_list]))
    t_neh_mean.append(np.mean([per_inst['NEH']['runtimes'][i] for i in idx_list]))

ax4.plot(unique_n, t_v0_mean, 'x-', color='#d62728', linewidth=1.8, markersize=6, label='Variant 0 (Original Reference)')
ax4.plot(unique_n, t_v1_mean, '^-', color='#1f77b4', linewidth=1.8, markersize=6, label='Variant 1 (Exact Accelerated)')
ax4.plot(unique_n, t_v2_mean, 's-', color='#2ca02c', linewidth=2.0, markersize=6, label='Variant 2 (Anytime Bounded B10k)')
ax4.plot(unique_n, t_neh_mean, 'k:', linewidth=1.5, label='NEH Reference')

ax4.axhline(4.0, color='red', linestyle='--', linewidth=1.5, label='4.0s Sandbox Cutoff')
ax4.set_xlabel("Number of Jobs (n)", fontsize=10)
ax4.set_ylabel("Mean Execution Time (seconds)", fontsize=10)
ax4.set_title("D. Empirical Runtime Scaling vs Problem Size\nVariant 2 Strictly Within Cutoff", fontsize=11, fontweight='bold')
ax4.grid(True, linestyle='--', alpha=0.5)
ax4.legend(loc='upper left', fontsize=8.5)

plt.tight_layout()
out_plot = 'benchmark_v1/results/pfsp_candidate2_verification_20261018/plots/verification_summary.png'
plt.savefig(out_plot, dpi=300)
print(f"Saved diagnostic plots to {out_plot}")
