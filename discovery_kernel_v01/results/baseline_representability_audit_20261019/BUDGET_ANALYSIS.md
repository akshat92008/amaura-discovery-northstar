# BUDGET ANALYSIS: Evaluation Caps & Neighborhood Truncation Dynamics

**Date:** 2026-10-19  
**Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Schema Budget Rule:** `50 <= budget_evaluations <= 500`  
**Auditor:** Independent AI Research Scientist & Algorithm-Discovery Engineer  

---

## 1. Neighborhood Move Complexity vs. Evaluation Caps

The declarative candidate space (`pfsp_declarative.py`) defines three local search operators with radically different move complexities:

1. **`pairwise_swap` (Adjacent Pairwise Swap):**
   - In each pass, tests swapping adjacent jobs $(i, i+1)$ for $i \in \{0, \dots, n-2\}$.
   - Move count per pass:
     $$M_{\mathrm{swap}}(n) = n - 1$$
2. **`single_pass_insertion` (Taillard Single-Pass Insertion):**
   - For each job $i \in \{0, \dots, n-1\}$, tests inserting into all other positions $j \ne i$.
   - Move count for exactly one complete pass:
     $$M_{\mathrm{ins}}(n) = n(n - 1)$$
3. **`multi_pass_insertion` (Multi-Pass Iterated Insertion):**
   - Repeats single-pass insertion until local optimality or budget exhaustion (up to 5 passes):
     $$M_{\mathrm{multi}}(n) \le 5 \times n(n - 1)$$

---

## 2. Quantitative Neighborhood Coverage Across Instance Dimensions

The benchmark evaluates instances ranging from $n=20$ to $n=120$. The table below details the exact move counts required versus the maximum allowable budget in the candidate schema ($\text{Budget}_{\max} = 500$):

| Instance Dimension ($n$) | Benchmark Instances | Adjacent Swap Moves ($n-1$) | Max Swap Passes at Budget=500 | Insertion Moves per Pass $n(n-1)$ | Max Insertion Coverage at Budget=500 | Jobs Examined Before Truncation ($\frac{500}{n-1}$) | Full Single-Pass Possible at Budget=500? |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **$n = 20$** | `pfsp_dev_00`–`03` | 19 | 26.3 passes | 380 | **100.0%** (500 > 380) | 20 / 20 jobs | **YES** |
| **$n = 30$** | `pfsp_dev_04`–`05` | 29 | 17.2 passes | 870 | **57.5%** | 17 / 30 jobs | **NO** |
| **$n = 50$** | `pfsp_dev_06`–`11` | 49 | 10.2 passes | 2,450 | **20.4%** | 10 / 50 jobs | **NO** |
| **$n = 75$** | `pfsp_dev_12`–`15` | 74 | 6.8 passes | 5,550 | **9.0%** | 6 / 75 jobs | **NO** |
| **$n = 100$** | `pfsp_dev_16`–`18` | 99 | 5.1 passes | 9,900 | **5.1%** | 5 / 100 jobs | **NO** |
| **$n = 120$** | `pfsp_dev_19` | 119 | 4.2 passes | 14,280 | **3.5%** | 4 / 120 jobs | **NO** |

---

## 3. Structural Consequences of the Budget Ceiling

### 3.1 Asymmetric Neighborhood Distortion
Because the budget limit is a fixed scalar ($[50, 500]$) rather than an instance-adaptive scaling factor:
- **`pairwise_swap` is super-saturated:** Even at $n=120$, budget=500 permits more than 4 full passes over the permutation. Swap local search runs to local optimality on small instances and executes multiple passes on all instances.
- **`single_pass_insertion` is severely starved:** On large instances ($n \ge 75$), an insertion candidate can evaluate fewer than 7 jobs before being forcibly terminated. 91% to 96% of the jobs are never examined.

### 3.2 Induced Behavioral Degeneracy (The Multi-Pass Illusion)
In `pfsp_declarative.py`, `multi_pass_insertion` is defined as:
```python
max_passes = 1 if local_search == "single_pass_insertion" else 5
for _ in range(max_passes):
    ...
    if evals_used >= budget_evals:
        break
```
Because a single pass requires 2,450 moves at $n=50$ and 14,280 moves at $n=120$, `evals_used` hits the 500 cap inside pass 1 for all instances where $n \ge 30$ (16 out of 20 development instances).
- **Mathematical Fact:** Across 80% of development instances and 73% of holdout instances, **`multi_pass_insertion` is 100% behaviorally identical to `single_pass_insertion`**.
- This directly explains why in Arm B, proposals with `multi_pass_insertion` (`arm_b_prop_02`, `arm_b_prop_12`) produced the exact same makespan (3654.15) as the single-pass proposals.

### 3.3 Artificial Advantage Granted to the Conventional Baseline
The baseline adapter `PFSPNEHLSAdapter` was constructed by wrapping `neh_ls_solve`, which has no budget parameter:
```python
def solve(self, instance: Any, context: Optional[Dict[str, Any]] = None) -> List[int]:
    from benchmark_v1.src.domains.pfsp_full_algorithm import neh_ls_solve
    times = instance["times"] if isinstance(instance, dict) else instance
    return neh_ls_solve(times)
```
- On `pfsp_dev_19` ($n=120$), `PFSPNEHLSAdapter` executed **14,280 evaluations**.
- On `pfsp_dev_19` ($n=120$), any candidate proposed by the AI in `PFSPDeclarativeAdapter` was cut off at **500 evaluations**.
- The baseline was allowed to consume **28.5 times more computational evaluations** than the candidate space permitted any AI proposal to spend on the same instance.
- Comparing these methods under the label of "fair quality comparison" was scientifically invalid.
