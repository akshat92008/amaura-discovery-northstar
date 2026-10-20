"""
Generate publication-quality diagnostic plots for the PFSP Full Algorithm Pilot.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import os

os.makedirs('benchmark_v1/results/pfsp_full_algorithm_pilot_20261018/plots', exist_ok=True)

# 1. Proposal Breakdown Data
outcomes = {
    'Valid Algorithm (Champion)': 1,
    'Syntax / Parse Error': 12,
    'Execution Timeout (>4s)': 11,
    'Invalid Permutation': 8
}
colors = ['#2ca02c', '#d62728', '#ff7f0e', '#9467bd']

# 2. Makespan Data
baselines = {
    'NEH Heuristic': 84907,
    'NEH + Local Search': 84593,
    'Proposal #2 (LLM Champion)': 84530
}

# 3. Instance-by-Instance Deltas vs NEH (from training set)
# Instances where Proposal #2 gained makespan
inst_labels = [f"I{i} (n={n})" for i, n in enumerate([20, 75, 50, 50, 100, 120, 100, 20, 30, 50, 50, 50, 75, 50, 50, 30, 50, 50])]
neh_vals = [1746, 4569, 3600, 3138, 5641, 6413, 11206, 2335, 3380, 5577, 5736, 6004, 6122, 4896, 4196, 1938, 4302, 4108]
p2_vals =  [1746, 4487, 3516, 3094, 5574, 6414, 11206, 2335, 3369, 5575, 5736, 5959, 6122, 4891, 4178, 1938, 4301, 4089]
gaps = [((p - n) / n) * 100 for p, n in zip(p2_vals, neh_vals)]

# Create figure
fig = plt.figure(figsize=(15, 10))

# Panel 1: Proposal Outcome Breakdown
ax1 = plt.subplot2grid((2, 2), (0, 0))
wedges, texts, autotexts = ax1.pie(
    outcomes.values(),
    labels=outcomes.keys(),
    autopct='%1.1f%%',
    startangle=140,
    colors=colors,
    explode=(0.1, 0, 0, 0),
    wedgeprops=dict(width=0.6, edgecolor='w')
)
for text in texts:
    text.set_fontsize(9)
for autotext in autotexts:
    autotext.set_fontsize(9)
    autotext.set_weight('bold')
ax1.set_title("A. 32 Independent Proposal Outcomes\n(Nemotron-3 Super, Zero-Shot)", fontsize=11, fontweight='bold')

# Panel 2: Aggregate Makespan Comparison
ax2 = plt.subplot2grid((2, 2), (0, 1))
models = list(baselines.keys())
scores = list(baselines.values())
bar_colors = ['#1f77b4', '#aec7e8', '#2ca02c']
bars = ax2.bar(models, scores, color=bar_colors, width=0.5, edgecolor='black', linewidth=0.8)
ax2.set_ylabel("Total Makespan ($C_{max}$)", fontsize=10)
ax2.set_title("B. Training Set Total Makespan (18 Instances)\nLower is Better", fontsize=11, fontweight='bold')
# Zoom y-axis to emphasize difference
min_val = min(scores) - 400
max_val = max(scores) + 300
ax2.set_ylim(min_val, max_val)

for bar, s in zip(bars, scores):
    diff = s - baselines['NEH Heuristic']
    diff_str = f"{s:,}\n(Ref)" if diff == 0 else f"{s:,}\n({diff:+d}, {diff/baselines['NEH Heuristic']*100:+.2f}%)"
    ax2.text(bar.get_x() + bar.get_width() / 2, s + 40, diff_str, ha='center', va='bottom', fontsize=9, fontweight='bold')
ax2.grid(axis='y', linestyle='--', alpha=0.5)

# Panel 3: Instance-by-Instance Gap vs NEH
ax3 = plt.subplot2grid((2, 2), (1, 0), colspan=2)
x = np.arange(len(inst_labels))
bar_c = ['#2ca02c' if g < 0 else ('#d62728' if g > 0 else '#7f7f7f') for g in gaps]
bars3 = ax3.bar(x, gaps, color=bar_c, width=0.6, edgecolor='black', linewidth=0.5)
ax3.axhline(0, color='black', linewidth=0.8)
ax3.axhline(-1.0, color='blue', linestyle='--', linewidth=1.0, label='-1.0% Gate Threshold')
ax3.set_xticks(x)
ax3.set_xticklabels(inst_labels, rotation=45, ha='right', fontsize=9)
ax3.set_ylabel("Relative Makespan Gap vs NEH (%)", fontsize=10)
ax3.set_title("C. Proposal #2 Champion Makespan Advantage per Training Instance\nNegative indicates makespan reduction (better schedule)", fontsize=11, fontweight='bold')
ax3.grid(axis='y', linestyle='--', alpha=0.5)
ax3.legend(loc='lower left', fontsize=9)

for bar, g in zip(bars3, gaps):
    if abs(g) > 0.05:
        va = 'top' if g < 0 else 'bottom'
        offset = -0.15 if g < 0 else 0.05
        ax3.text(bar.get_x() + bar.get_width() / 2, g + offset, f"{g:.2f}%", ha='center', va=va, fontsize=8)

plt.tight_layout()
output_path = 'benchmark_v1/results/pfsp_full_algorithm_pilot_20261018/plots/pilot_summary.png'
plt.savefig(output_path, dpi=300)
print(f"Plot saved successfully to {output_path}")
