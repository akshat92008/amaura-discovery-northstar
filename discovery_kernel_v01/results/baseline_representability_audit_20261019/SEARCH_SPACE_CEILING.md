# SEARCH-SPACE CEILING AUDIT: Reachable Optimization Frontier in PFSP Declarative DSL

**Date:** 2026-10-19  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Dataset:** 20 Development Instances (`discovery_kernel_v01/results/ai_discovery_pilot_20261019/data/dev_instances.json`)  
**Evaluation:** Makespan Minimization ($C_{\max}$)  
**Auditor:** Independent AI Research Scientist & Algorithm-Discovery Engineer  

---

## 1. Candidate Space Structure & Behavioral Redundancy

The PFSP declarative DSL (`pfsp_declarative.py`) defines algorithm candidates using seven parameters:
- **`initial_order`** (5 values): `total_processing_time_desc`, `first_machine_asc`, `last_machine_desc`, `variance_processing_time_desc`, `weighted_profile_desc`
- **`construction_criterion`** (3 values): `makespan_only`, `makespan_and_flow_time`, `makespan_and_idle_time`
- **`tie_break`** (4 values): `first_found`, `last_found`, `flow_time_min`, `idle_time_min`
- **`local_search`** (4 values): `none`, `pairwise_swap`, `single_pass_insertion`, `multi_pass_insertion`
- **`search_strategy`** (2 values): `first_improvement`, `best_improvement`
- **`acceptance_rule`** (2 values): `strictly_better_makespan`, `better_or_equal_makespan_flow_time`
- **`budget_evaluations`** (Integer): $50 \le \text{budget} \le 500$

### 1.1 Nominal vs. Effective Search Space Size
Nominally, discretizing budget into 3 standard representative tiers ($\{100, 250, 500\}$) yields:
$$\text{Nominal Space} = 5 \times 3 \times 4 \times (1 + 3 \times 2 \times 2 \times 3) = 2,220 \text{ configurations}$$
(or 780 configurations if budget is fixed to a single setting).

However, rigorous inspection of `pfsp_declarative.py` reveals massive behavioral degeneracies:
1. **Dead Parameters when `local_search == "none"`:**
   When `local_search` is `"none"`, the parameters `search_strategy`, `acceptance_rule`, and `budget_evaluations` are completely bypassed. All $2 \times 2 \times 3 = 12$ variations map to the exact same constructive heuristic. The pure constructive subspace collapses from $60 \times 12 = 720$ nominal configs to **exactly 60 unique constructive algorithms**.
2. **Multi-Pass Degeneracy Under Budget Caps:**
   On instances where $n \ge 30$, a single insertion pass requires $\ge 870$ moves. With $\text{budget} \le 500$, `multi_pass_insertion` exhausts its evaluation budget mid-way through pass 1. On 80% of development instances (and 73% of holdout instances), **`multi_pass_insertion` is 100% behaviorally identical to `single_pass_insertion`**.
3. **Strategy Collapse under Insertion:**
   In `pfsp_declarative.py`, Taillard insertion removes a job and evaluates all $n-1$ positions, always selecting the best position for that job before updating the sequence. Thus, `first_improvement` and `best_improvement` exhibit nearly identical trajectory dynamics during job insertion.

---

## 2. Complete Enumeration of the Constructive Subspace

To establish the empirical floor and ceiling of constructive heuristics prior to any local search, all **60 valid pure constructive configurations** were exhaustively evaluated across all 20 development instances (1,200 instance evaluations, executed in 121.72s).

### 2.1 Constructive Performance Summary
- **Classical NEH Heuristic** (`total_processing_time_desc`, `makespan_only`, `first_found`):
  $$\text{Mean } C_{\max} = \mathbf{3597.80}$$
- **Global Best Constructive Heuristic** (`total_processing_time_desc`, `makespan_only`, `idle_time_min`):
  $$\text{Mean } C_{\max} = \mathbf{3588.20}$$
  *Outperforms classical NEH by 9.60 makespan units (-0.267%) purely constructively without spending a single local-search evaluation.*
- **Worst Constructive Heuristic** (`weighted_profile_desc`, `makespan_only`, `first_found`):
  $$\text{Mean } C_{\max} = \mathbf{3713.45}$$
  *(Palmer slope index ordering; underperforms NEH by +115.65 units / +3.21%).*

### 2.2 Top-Performing Constructive Configurations
All top constructive heuristics utilize total processing time descending (`total_processing_time_desc`) combined with machine idle-time minimization:

| Rank | Initial Job Order | Construction Criterion | Tie-Break Rule | Mean Dev Makespan ($C_{\max}$) | Relative Gap vs NEH |
|:---:|---|---|---|:---:|:---:|
| **1** | `total_processing_time_desc` | `makespan_only` | `idle_time_min` | **3588.20** | -0.27% |
| **2** | `total_processing_time_desc` | `makespan_and_idle_time` | `first_found` | **3588.20** | -0.27% |
| **3** | `total_processing_time_desc` | `makespan_and_idle_time` | `flow_time_min` | **3588.20** | -0.27% |
| **4** | `total_processing_time_desc` | `makespan_and_idle_time` | `idle_time_min` | **3588.20** | -0.27% |
| **5** | `total_processing_time_desc` | `makespan_only` | `flow_time_min` | **3591.65** | -0.17% |

*Key Insight:* Secondary tie-breaking by machine idle time consistently resolves ties toward compact schedules with minimal gaps between consecutive jobs, outperforming the arbitrary `first_found` index convention of classical NEH.

### 2.3 Bottom-Performing Constructive Configurations
| Rank | Initial Job Order | Construction Criterion | Tie-Break Rule | Mean Dev Makespan ($C_{\max}$) | Relative Gap vs NEH |
|:---:|---|---|---|:---:|:---:|
| **58** | `last_machine_desc` | `makespan_and_flow_time` | `last_found` | **3691.45** | +2.60% |
| **59** | `first_machine_asc` | `makespan_only` | `first_found` | **3709.20** | +3.10% |
| **60** | `weighted_profile_desc` | `makespan_only` | `first_found` | **3713.45** | +3.21% |

*Key Insight:* In the previous AI Discovery pilot, the Feedback-guided search (Arm B) collapsed onto `weighted_profile_desc` (Palmer's slope heuristic). The census proves that `weighted_profile_desc` is the single worst initial ordering in the entire search space.

---

## 3. Bounded Local Search Ceiling vs. Unconstrained Baseline

We evaluated the reachable optimization frontier under the maximum permissible candidate schema budget ($\text{budget}=500$) against the unconstrained baseline `neh_ls_solve`:

### 3.1 Macro Benchmark Comparison
| Algorithm Configuration | Local Search Operator | Local Search Budget | Mean Dev Makespan ($C_{\max}$) | Relative Gap vs. Baseline |
|---|---|:---:|:---:|:---:|
| **Target Baseline (`neh_ls_solve`)** | Unconstrained Single-Pass Insertion | Unbounded ($380 \le M \le 14,280$) | **3576.95** | **0.00%** (Ref) |
| **Best Bounded Candidate** (`idle_time_min` tie-break) | `single_pass_insertion` | Bounded ($M \le 500$) | **3584.15** | **+0.20%** |
| **Best Bounded Candidate** (`flow_time_min` tie-break) | `single_pass_insertion` | Bounded ($M \le 500$) | **3586.90** | **+0.28%** |
| **Best Pure Constructive** (`idle_time_min`, no LS) | `none` | 0 | **3588.20** | **+0.31%** |
| **Nominal NEH-LS Bounded** (`first_found`, budget=500) | `single_pass_insertion` | Bounded ($M \le 500$) | **3589.15** | **+0.34%** |
| **Classical NEH Heuristic** (`first_found`, no LS) | `none` | 0 | **3597.80** | **+0.58%** |

---

## 4. Instance-by-Instance Frontier Analysis

The table below details makespan across all 20 development instances for the unconstrained baseline, the best reachable bounded declarative configuration, and the best pure constructive heuristic:

| Instance ID | $n$ | $m$ | Baseline (`neh_ls_solve`) | Best Bounded (Budget=500) | Best Constructive (No LS) | Bounded Gap vs. Baseline (%) | Dominant Limiting Factor |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `pfsp_dev_00` | 20 | 5 | 1,247 | 1,247 | 1,254 | +0.00% | Exact Parity Reached ($500 > 380$) |
| `pfsp_dev_01` | 20 | 5 | 1,292 | 1,292 | 1,292 | +0.00% | Exact Parity Reached ($500 > 380$) |
| `pfsp_dev_02` | 20 | 10 | 1,706 | 1,706 | 1,706 | +0.00% | Exact Parity Reached ($500 > 380$) |
| `pfsp_dev_03` | 20 | 10 | 1,689 | **1,670** | 1,690 | **-1.12%** | **Beats Baseline** (Idle-time tie-break) |
| `pfsp_dev_04` | 30 | 5 | 1,902 | 1,909 | 1,909 | +0.37% | Budget Truncation (evals 500/870) |
| `pfsp_dev_05` | 30 | 10 | 2,074 | 2,074 | 2,080 | +0.00% | Improvement found early in pass |
| `pfsp_dev_06` | 50 | 5 | 2,848 | 2,848 | 2,848 | +0.00% | Constructive already local optimum |
| `pfsp_dev_07` | 50 | 5 | 2,636 | 2,636 | 2,636 | +0.00% | Constructive already local optimum |
| `pfsp_dev_08` | 50 | 10 | 3,128 | 3,149 | 3,149 | +0.67% | Budget Truncation (evals 500/2,450) |
| `pfsp_dev_09` | 50 | 10 | 3,085 | **3,078** | 3,087 | **-0.23%** | Early move found under budget |
| `pfsp_dev_10` | 50 | 15 | 3,587 | **3,566** | 3,579 | **-0.59%** | Early move found under budget |
| `pfsp_dev_11` | 50 | 15 | 3,449 | 3,483 | 3,483 | +0.99% | Budget Truncation (evals 500/2,450) |
| `pfsp_dev_12` | 75 | 10 | 4,382 | 4,382 | 4,390 | +0.00% | Early move matched baseline |
| `pfsp_dev_13` | 75 | 15 | 4,978 | **4,962** | 4,969 | **-0.32%** | Early move found under budget |
| `pfsp_dev_14` | 75 | 10 | 4,332 | 4,338 | 4,342 | +0.14% | Budget Truncation (evals 500/5,550) |
| `pfsp_dev_15` | 75 | 15 | 4,858 | 4,870 | 4,870 | +0.25% | Budget Truncation (evals 500/5,550) |
| `pfsp_dev_16` | 100 | 10 | 5,735 | 5,793 | 5,793 | **+1.01%** | Severe Starvation (5/100 jobs checked) |
| `pfsp_dev_17` | 100 | 10 | 5,746 | **5,717** | 5,717 | **-0.50%** | Superior constructive sequence |
| `pfsp_dev_18` | 100 | 15 | 6,200 | 6,300 | 6,305 | **+1.61%** | Severe Starvation (5/100 jobs checked) |
| `pfsp_dev_19` | 120 | 10 | 6,665 | **6,663** | 6,665 | **-0.03%** | Superior constructive sequence |

---

## 5. Key Empirical Observations

1. **The Bounded Ceiling Cannot Match the Unconstrained Baseline on Average:**
   Across all 20 development instances, the best possible configuration bounded by `budget=500` achieves a mean makespan of **3584.15**, trailing the unconstrained baseline (3576.95) by **+7.20 units (+0.201%)**.
2. **Performance Deficit Scales with Instance Size ($n$):**
   - On small instances ($n=20$), the budget of 500 exceeds the 380 moves required. The bounded candidate matches the baseline on 3 instances and beats it on 1 instance (`pfsp_dev_03`, -1.12%).
   - On intermediate instances ($n=30, 50, 75$), performance is mixed: when an improving move happens to lie in the first few jobs, the candidate captures it; when the improving move lies deeper in the permutation, truncation locks in sub-optimal makespans.
   - On large instances ($n=100, 120$), where 500 moves cover only 3.5% to 5.1% of the neighborhood, the candidate is almost entirely starved. For example, on `pfsp_dev_16` and `pfsp_dev_18`, the local search terminates having examined only 5 out of 100 jobs, returning the constructive schedule and trailing the baseline by +1.01% and +1.61%.
3. **Pure Constructive Exploration Offers High Leverage:**
   Replacing `first_found` with `idle_time_min` in pure NEH construction closes **47.6% of the gap** between classical NEH and the unconstrained local search baseline (from 3597.80 down to 3588.20) without spending any local search moves.
4. **Structural Ceiling Verdict:**
   The failure of AI candidate generation to outperform the baseline was **not** because the search algorithm overlooked an available superior candidate. Under the 500-evaluation budget restriction, **no candidate configuration exists in the DSL that matches the baseline on average across the benchmark instances**.
