# Amaura Experiment #5 — Rich-State Algorithm Discovery

**Date:** October 3, 2026  
**Primary Question:** Can Amaura discover a genuinely better packing strategy when the candidate algorithm is allowed to observe a richer representation of the current packing state (`item`, `bin_remaining`, `recent_items`, `bin_capacity`)? When given enough information to reason about the whole current state, can Amaura discover a strategy that is genuinely better than a human-designed baseline?

---

## 1. Executive Summary & Verdict

### **VERDICT: INCONCLUSIVE**

The rich-state representation enabled Claude to express sophisticated multi-bin portfolio and stream-aware packing heuristics, matching Best Fit performance across single-shot trials (7,867 bins vs 7,869 on Hidden-1, and 8,296 vs 8,295 on Hidden-2). However, the performance delta remains within statistical noise (+/- 2 bins out of thousands), and 30 generations of evolutionary search severely overfit the development set (dropping to 8.19% on dev, but blowing up to 7,918 bins on hidden).

---

## 2. Core Comparative Matrix (Experiments #2 through #5)

| System | Problem Representation | Search Paradigm | Dev Excess % (25 inst) | Hidden-1 Excess % (120 inst) | Hidden-1 Bins (120 inst) | Hidden-2 Excess % (120 inst) | Hidden-2 Bins (120 inst) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Human Best Fit** | Scalar `(item, rem, cap)` | Deterministic | **8.80%** | **8.14%** | **7,869** | **5.82%** | **8,295** |
| **Human First Fit** | Scalar `(item, rem, cap)` | Deterministic | 10.28% | 8.75% | 7,914 | 6.25% | 8,329 |
| **Human Worst Fit** | Scalar `(item, rem, cap)` | Deterministic | 21.69% | 15.53% | 8,407 | 11.80% | 8,764 |
| **Exp #2 Champion** | Scalar `(item, rem, cap)` | Qwen 1.5B 15-Gen | 10.28% | 8.75% | 7,914 | — | — |
| **Exp #3 Champion** | Scalar `(item, rem, cap)` | Claude Sonnet 30-Gen | 8.71% | 8.15% | 7,870 | — | — |
| **Exp #4 Champion** | Scalar `(item, rem, cap)` | Claude 3-Island Pop | 8.71% | 8.15% | 7,870 | — | — |
| **Exp #5 Best Single-Shot** | **Rich State `choose_bin`** | Claude 10 Single-Shot | **8.71%** | **8.11%** | **7,867** | **5.83%** | **8,296** |
| **Exp #5 Population Champ** | **Rich State `choose_bin`** | **Claude 3-Island Pop** | **8.19%** *(Overfit)* | **8.81%** | **7,918** | **6.19%** | **8,324** |

---

## 3. The Ten Core Questions Answered

### 1. Did richer state improve performance?
**Empirical Answer:** **No.** 
- On **Hidden-1** (120 instances, 18,000 items), Best Fit used **7,869** bins. The Best Single-Shot candidate used **7,867** bins (-2 bins), and the Population Champion used **7,918** bins (+49 bins worse).
- On **Hidden-2** (120 instances, 24,000 items), Best Fit used **8,295** bins. The Best Single-Shot candidate used **8,296** bins (+1 bin), and the Population Champion used **8,324** bins (+29 bins worse).
Net change over 240 held-out instances: **Zero generalizable improvement.**

### 2. Did the model discover a strategy fundamentally different from Best Fit?
**Empirical Answer:** **Yes.** 
In contrast to Experiments #2-4 where candidates were forced to be variations of scalar leftover formulas, the rich state enabled Claude to invent non-trivial algorithmic logic:
- Tracking moving averages and standard deviations of the incoming item stream (`recent_items`).
- Classifying gaps into "orphan ranges" that are statistically unfillable.
- Deliberately returning `-1` to open new bins to protect bins with large remainders for anticipated large arrivals.

### 3. Did population search actually exploit the richer representation?
**Empirical Answer:** **Yes, but it exploited it by OVERFITTING.**
Across 30 generations, the multi-island evolutionary search optimized the orphan-gap thresholds and standard deviation coefficients specifically for the 25 development instances, successfully driving dev excess down from **8.80% to 8.19%** (saving 7 bins on dev). However, because these thresholds were tuned to the development seed, the strategy failed catastrophically on the 120-instance hidden benchmarks (+49 bins worse on Hidden-1, +29 bins worse on Hidden-2).

### 4. Did development improvements generalize?
**Empirical Answer:** **NO. This is the clearest finding of Experiment #5.**
Evolutionary optimization in the rich state space has high expressive capacity, allowing the LLM to fit arbitrary piecewise decision boundaries to the training workload. The 0.61% apparent "discovery gain" on development was 100% training overfitting.

### 5. Did the candidate beat Best Fit on hidden data?
**Empirical Answer:** **No.** On Hidden-1:
- Best Fit: **7,869** bins (`8.14%` excess)
- Exp #5 Population Champ: **7,918** bins (`8.81%` excess)
- Exp #5 Single-Shot Champ: **7,867** bins (`8.11%` excess — effectively tied)

### 6. Did it beat Best Fit on HIDDEN-2?
**Empirical Answer:** **No.** On Hidden-2:
- Best Fit: **8,295** bins (`5.82%` excess)
- Exp #5 Population Champ: **8,324** bins (`6.19%` excess)
- Exp #5 Single-Shot Champ: **8,296** bins (`5.83%` excess — effectively tied)

### 7. How many bins were saved?
**Empirical Answer:** **Zero bins saved.**

### 8. Was the improvement statistically meaningful or just a tiny fluctuation?
**Empirical Answer:** Head-to-Head instance analysis against Best Fit:
- **Population Champion:**
  - *Hidden-1 (120 instances):* Wins = 9 | Losses = 50 | Ties = 61 (Net: -41 losses)
  - *Hidden-2 (120 instances):* Wins = 14 | Losses = 33 | Ties = 73 (Net: -19 losses)
- **Single-Shot Champion:**
  - *Hidden-1 (120 instances):* Wins = 4 | Losses = 2 | Ties = 114 (Statistically indistinguishable from Best Fit)
  - *Hidden-2 (120 instances):* Wins = 2 | Losses = 4 | Ties = 114 (Statistically indistinguishable from Best Fit)

### 9. What did the discovered algorithm actually do?

#### The Overfitted Population Champion (`best_iterative.py`):
```python
def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    import math

    if not bin_remaining:
        return -1

    feasible = [(i, r) for i, r in enumerate(bin_remaining) if r >= item - 1e-6]
    if not feasible:
        return -1

    if recent_items:
        avg = sum(recent_items) / len(recent_items)
        std = math.sqrt(sum((x - avg)**2 for x in recent_items) / len(recent_items)) if len(recent_items) > 1 else avg * 0.2
    else:
        avg = item
        std = item * 0.2

    small_threshold = max(avg - 1.5 * std, bin_capacity * 0.04)
    orphan_lo = small_threshold
    orphan_hi = max(avg - 0.25 * std, small_threshold + 1e-6)

    best_idx = -1
    best_score = float('inf')

    for i, remaining in feasible:
        leftover = remaining - item

        if leftover < 1e-6:
            score = -1000.0
        elif leftover < small_threshold:
            score = leftover / bin_capacity
        elif orphan_lo <= leftover <= orphan_hi:
            score = 2.5 + leftover / bin_capacity
        else:
            n_fits = leftover / avg if avg > 1e-9 else 0
            fractional_waste = (n_fits - math.floor(n_fits)) * avg / bin_capacity
            score = 0.5 + fractional_waste * 1.2 + (leftover / bin_capacity) * 0.08

        if score < best_score:
            best_score = score
            best_idx = i

    if best_idx >= 0:
        leftover = bin_remaining[best_idx] - item
        in_orphan = orphan_lo <= leftover <= orphan_hi
        if in_orphan and item > bin_capacity * 0.25:
            return -1
        return best_idx

    return -1
```

#### The Generalist Single-Shot Candidate (`best_single_shot.py`):
```python
def choose_bin(item: float, bin_remaining: list[float], recent_items: list[float], bin_capacity: float) -> int:
    import math

    if not bin_remaining:
        return -1

    # Compute recent item statistics
    if recent_items:
        avg_recent = sum(recent_items) / len(recent_items)
        variance = sum((x - avg_recent) ** 2 for x in recent_items) / len(recent_items)
        std_recent = math.sqrt(variance) if variance > 0 else 0.0
    else:
        avg_recent = item
        std_recent = 0.0

    # Estimate future item size (use recent average as proxy)
    future_avg = avg_recent

    feasible = [(i, r) for i, r in enumerate(bin_remaining) if r >= item - 1e-6]

    if not feasible:
        return -1

    best_idx = -1
    best_score = float('inf')

    for i, remaining in feasible:
        leftover = remaining - item

        # Penalize bins where leftover is too small to fit future items
        # but not zero (wasted fragmentation)
        if leftover < 1e-6:
            # Perfect fit - very good
            fragmentation_penalty = 0.0
        else:
            # How well does leftover accommodate future items?
            # Ideal: leftover is a multiple of future_avg or at least >= future_avg
            if future_avg > 1e-6:
                # Prefer leftover that can fit at least one more item
                fits_future = leftover / future_avg
                # Penalize if leftover is too small to fit future avg item
                if leftover < future_avg - std_recent:
                    # Wasted space - high penalty
                    fragmentation_penalty = leftover / bin_capacity * 2.0
                else:
                    # Can fit future items - prefer tighter fit
                    # Score based on how close to ideal packing
                    ideal_leftover = (math.floor(fits_future)) * future_avg
                    waste = leftover - ideal_leftover
                    fragmentation_penalty = waste / bin_capacity
            else:
                fragmentation_penalty = leftover / bin_capacity

        # Primary: minimize leftover (best fit style)
        # Secondary: fragmentation awareness
        score = leftover / bin_capacity + fragmentation_penalty * 0.5

        if score < best_score:
            best_score = score
            best_idx = i

    # Decide whether to open a new bin
    # If best leftover is very small (near perfect fit) or we found a good bin, use it
    if best_idx >= 0:
        best_remaining = bin_remaining[best_idx]
        leftover = best_remaining - item
        # Open new bin if item is large and leftover would be wasteful
        # and we expect future large items
        if (future_avg > bin_capacity * 0.4 and
                leftover > bin_capacity * 0.3 and
                leftover < future_avg - std_recent * 0.5):
            return -1
        return best_idx

    return -1
```

### 10. What is the remaining bottleneck?
**Theoretical & Mathematical Insight:**
In Online 1D Bin Packing, the competitive ratio lower bound for any deterministic online algorithm (even with infinite computation and full state awareness) is proven to be at least **1.5401** (Balogh et al., 2012). Best Fit achieves an asymptotic competitive ratio of **1.7000**. Because the sequence is non-anticipative (future arrivals are unknown and stochastic), packing an item to preserve space for an imagined future item often backfires if subsequent items do not match the expected distribution. Hence, greedy instantaneous tight-packing (Best Fit) represents a near-universal empirical Pareto frontier for online stream packing.

---

## 4. Benchmark Suite Breakdown

### Hidden-1 Benchmark (120 Instances, Seed 9999, N=150)
- **Uniform (30 inst):** Best Fit = 7.73% | Exp #5 Pop = 7.53% | Exp #5 SS = 7.63%
- **Weibull (30 inst):** Best Fit = 4.68% | Exp #5 Pop = 5.44% | Exp #5 SS = 4.68%
- **Bimodal (30 inst):** Best Fit = 10.97% | Exp #5 Pop = 11.32% | Exp #5 SS = 10.97%
- **Triplets (30 inst):** Best Fit = 8.80% | Exp #5 Pop = 11.00% | Exp #5 SS = 8.80%

### Hidden-2 Benchmark (120 Instances, Seed 77777, N=200)
- **Pareto Heavy-Tailed (30 inst):** Best Fit = 4.52% | Exp #5 Pop = 4.39% | Exp #5 SS = 4.52%
- **Gaussian (30 inst):** Best Fit = 6.77% | Exp #5 Pop = 7.25% | Exp #5 SS = 6.85%
- **Small-Item Dominant (30 inst):** Best Fit = 4.28% | Exp #5 Pop = 4.86% | Exp #5 SS = 4.23%
- **Tight Quads (30 inst):** Best Fit = 7.53% | Exp #5 Pop = 7.93% | Exp #5 SS = 7.53%

---

## 5. Token and Compute Accounting

- **Total LLM Calls:** 192
- **Total Prompt Tokens:** 564119
- **Total Completion Tokens:** 136594
- **Total Tokens:** 700713
- **Total Financial Cost:** $0.00 (Local OmniRoute connection)
- **Failed Calls:** 0

---

## 6. Final Assessment

> **When we give the AI enough information to reason about the whole current state of the problem, can Amaura discover a strategy that is genuinely better than a human-designed baseline?**

**Brutally Honest Scientific Answer:** **NO.**
Across four controlled experiments spanning model scales (1.5B to Frontier Claude Sonnet 4-6), search architectures (single-chain vs 3-island population with AST diversity filtering), and representations (scalar per-bin vs full open-bin state and recent item history), the Amaura Discovery Engine converges reliably to variations of Best Fit, but **fails to discover any algorithmic heuristic that genuinely outperforms Best Fit on unseen held-out data**.
