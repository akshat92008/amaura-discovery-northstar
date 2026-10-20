# Pre-Registration: Amaura Experiment #15
## Production-Trace Generalization & Real-World Validation of Cloud Pod Schedulers

**Registration Date:** 2026-10-04  
**Principal Investigator:** Amaura Autonomous Discovery Engine  
**Status:** PRE-REGISTERED (FROZEN PRIOR TO PRODUCTION EVALUATION)

---

## 1. Core Research Question

> **Do Amaura-discovered cloud scheduling policies retain their advantage over established scheduling heuristics when evaluated on realistic, externally sourced production workload traces that were not used during discovery?**

### Hypotheses
- **$H_1$ (Generalization Hypothesis):** Discovered policies (`T4_C01` and `N60_T4_C51`) discover universal consolidation principles that outperform the established Kubernetes bin-packing heuristic (`kube_binpacking`) on real-world production container traces, reducing active nodes and infrastructure cost while preserving 100% placement feasibility.
- **$H_0$ (Null / Synthetic Overfitting Hypothesis):** The apparent superiority of discovered policies in Experiments #13 and #14 was an artifact of the synthetic benchmark distribution or idealized simulator assumptions; when evaluated against real production workload traces, the discovered policies do not outperform `kube_binpacking`.

---

## 2. Frozen Candidates & Baselines

Before any production trace evaluation, all candidate policies and baselines are permanently frozen and cryptographically hashed.

### Discovered Policies
1. **Policy A: `T4_C01`**
   - Origin: Amaura Experiment #13 (Trial 4, Call 01, Perspective: Aggressive Node Consolidation)
   - SHA-256: `de872ce75fc68d43062b00ba2071e9fb7303163ba9b6040d425b21be41c15101`
   - File: `experiment15/policies/policy_a_t4_c01.py`
   - Mechanism: Lexicographic active-node preference $\to$ post-placement resource imbalance $|u_{\text{cpu}} - u_{\text{mem}}|$ $\to$ hourly cost tiebreaker; pod selection by normalized demand score.

2. **Policy B: `N60_T4_C51`**
   - Origin: Amaura Experiment #14 (Condition $N=60$, Trial 4, Call 51, Perspective: Lexicographic Dual-Constraint Ranking)
   - SHA-256: `7a92d80f99a5d0b56694a52f67e1f5172b333ebd574dfbb132ddce368c7b137b`
   - File: `experiment15/policies/policy_b_n60_t4_c51.py`
   - Mechanism: Lexicographic active-node preference $\to$ post-placement resource imbalance $|u_{\text{cpu}} - u_{\text{mem}}|$ $\to$ hourly cost tiebreaker; standard FIFO pod order.

### Standard Baselines
- **`kube_binpacking`**: Kubernetes MostAllocated + BalancedAllocation scoring plugin with active node consolidation bonus (+100.0).
- **`kube_default`**: Kubernetes LeastAllocated + BalancedAllocation scoring plugin (standard default spreading behavior).
- **`first_fit`**: Standard greedy first feasible node placement.
- **`best_fit`**: Standard least residual normalized capacity placement.
- **`best_fit_decreasing`**: Norm-sorted descending pod order + Best Fit node placement.
- **`worst_fit`**: Spreading / load-balancing baseline.

---

## 3. External Workload Dataset

- **Dataset Name:** Alibaba Cluster Trace v2018 (`cluster-trace-v2018`)
- **Source:** Alibaba System Software & Infrastructure Team (Alibaba Group)
- **Publication:** APSYS 2018 / Alibaba Cluster Trace Program
- **URL:** `http://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/`
- **Download Date:** 2026-10-04
- **License:** Open Research Data License (Alibaba Cluster Trace Program / Apache 2.0)
- **Workload Scope:**
  - 4,034 physical bare-metal servers (96 CPU cores, 100 normalized memory units each).
  - 71,476 unique production container deployments (microservices and batch workloads).
  - 370,540 container lifecycle events spanning 8.04 days ($t = 0 \to 694,879$ seconds).

---

## 4. Preprocessing & Data Transformation Pipeline

The transformation from raw CSV to simulator format is strictly deterministic:

| Original Field (`container_meta.csv`) | Transformed Field | Transformation Rule | Rationale |
| :--- | :--- | :--- | :--- |
| `container_id` | `pod["id"]` | String UID | Unique pod identification |
| `cpu_request` | `pod["cpu"]` | `cpu_request / 100.0` | In Alibaba trace, 100 units = 1 CPU core |
| `mem_size` | `pod["mem"]` | `float(mem_size)` | Normalized percentage of machine capacity [0, 100] |
| `time_stamp` | `pod["arrival_sec"]` | `int(time_stamp)` | Real temporal arrival time |
| `machine_id` | `node["id"]` | String UID | Cluster node mapping |
| `cpu_num` (`machine_meta.csv`) | `node["cpu_capacity"]` | `float(cpu_num)` = 96.0 | Real physical CPU core capacity |
| `mem_size` (`machine_meta.csv`) | `node["mem_capacity"]` | `float(mem_size)` = 100.0 | Normalized physical memory capacity |
| Standard Cloud Price | `node["cost_per_hour"]`| `$4.08 / hr` | Enterprise 96-core server rate ($0.0425/core-hr) |

---

## 5. Chronological Partitioning (Leakage Prevention)

To prevent temporal leakage and overfitting, the trace is divided chronologically:

1. **Development Trace:** Day 1 ($t = 86,400 \to 172,800$ sec).
   - Used for simulator calibration, parser unit tests, and dry-run validation.
2. **Validation Trace:** Day 2 ($t = 172,800 \to 259,200$ sec).
   - Used for pipeline sanity checks and metric range verification.
3. **Hidden Production Trace:** Days 3–4 ($t = 259,200 \to 432,000$ sec).
   - Strictly isolated. Evaluated only after complete experiment harness freezing.
   - SHA-256 will be calculated and verified upon extraction.

---

## 6. Evaluation Protocol (Two Evaluation Modes)

### Mode A: Dynamic Trace Replay
- Continuous discrete-event simulation over multi-hour operational horizons.
- Pods arrive dynamically at recorded timestamps.
- Nodes activate upon pod placement and deactivate when all placed pods depart.
- Evaluates online scheduling behavior under dynamic load fluctuations.

### Mode B: Static Packing Windows
- Chronological deployment windows (15-minute and 30-minute intervals) converted into static packing instances.
- Recreates the exact mathematical formulation of Experiments #13 and #14, but using 100% genuine production pod requirements.
- Directly isolates whether the synthetic advantage transfers when pod demands reflect real-world distributions.

---

## 7. Primary & Secondary Metrics

### Primary Metric (Pre-Registered)
- **Mode B (Static Packing):** Mean Total Placement Cost across all windows, requiring 100% placement feasibility.
  $$\text{Cost} = \sum_{j \in \text{Active}} \left[ \text{Cost}_j \times (1.0 + 0.2 \times |u_{\text{cpu}, j} - u_{\text{mem}, j}|) \right] + 1000.0 \times N_{\text{unscheduled}}$$
- **Mode A (Dynamic Replay):** Total Infrastructure Cost (Active Node-Hours $\times$ Hourly Rate) with 100% placement feasibility.
  $$\text{Cost}_{\text{infra}} = \sum_{j \in \text{Nodes}} \text{Cost}_j \times \frac{\text{ActiveSeconds}_j}{3600}$$

### Secondary Metrics
- Average active nodes ($\bar{N}_{\text{active}}$)
- Peak active nodes ($\max N_{\text{active}}$)
- Total node activations
- Active resource utilization (CPU and Memory)
- Resource imbalance ($|u_{\text{cpu}} - u_{\text{mem}}|$)
- Scheduler runtime and decision throughput (decisions/sec).

---

## 8. Statistical Methodology

- **Paired Comparisons:** Evaluated on identical workload instances/windows:
  $$\Delta_{\text{cost}} = \text{Cost}(\text{Amaura}) - \text{Cost}(\text{kube\_binpacking})$$
- **Statistical Tests:**
  - Two-tailed Wilcoxon signed-rank test ($\alpha = 0.05$).
  - Paired mean and median percentage difference.
  - 95% Bootstrap Confidence Interval (10,000 resamples).
  - Win / Tie / Loss counts across production windows.

---

## 9. Pre-Registered Success Criteria

- **Strong Success:** Amaura policy beats `kube_binpacking` on the primary metric with $p < 0.05$, maintains 100% feasibility, reduces active nodes across multiple independent production windows, and remains robust under sensitivity analysis.
- **Partial Success:** Amaura matches or marginally improves upon `kube_binpacking`, remains competitive, but does not achieve consistent statistical significance ($p \ge 0.05$).
- **Failure:** Amaura performs worse than `kube_binpacking`, showing that the synthetic advantage failed to generalize to real production workloads.
- **Critical Failure / Inconclusive:** Major simulator artifacts or data processing biases render the comparison invalid.
