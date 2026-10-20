# Formal Audit of Experiment #13, Experiment #14, and Simulator Infrastructure

## 1. Executive Summary

This audit establishes the scientific baseline for **Amaura Experiment #15 (Production-Trace Generalization & Real-World Validation)**.
It rigorously inspects the artifacts from Experiment #13 and Experiment #14, identifies the frozen candidate policies, audits the previous simulation engine, and catalogues all simulator fidelity gaps that must be addressed for real-world production workload evaluation.

---

## 2. Audit of Previous Experiments

### 2.1 Experiment #13 (Cross-Domain Generality to Cloud Pod Scheduling)
- **Domain:** Kubernetes-style cloud pod placement on heterogeneous worker nodes.
- **Protocol:** Independent Best-of-N ($N=15$), 5 independent trials, 15 perspectives per trial.
- **Development Benchmark:** 30 synthetic instances (`seed=1042`), 12 to 24 nodes, 40 to 120 pods.
- **Hidden Benchmark:** 120 synthetic instances (`seed=70099`), evaluated blindly after freezing.
- **Result:**
  - Incumbent baseline `kube_binpacking` hidden total cost: `2171.13` (mean: `18.0927`, mean active nodes: `14.41`).
  - Discovered Champion **`T4_C01`** (Trial 4, Perspective: Aggressive Node Consolidation):
    - Hidden total cost: **`2099.51`** (mean: `17.4959`, mean active nodes: **`12.79`**).
    - Statistical significance: $p = 0.0001$, active nodes reduced by **$11.2\%$**.
  - **Limitation:** Beating `kube_binpacking` occurred in only **1 of 5 trials** ($20.0\%$ reliability). 4 trials failed to beat the baseline.

### 2.2 Experiment #14 (Search Budget Scaling & Discovery Reliability)
- **Research Question:** Does increasing independent sampling budget ($N=15 \to 30 \to 60$) predictably improve discovery success probability?
- **Protocol:** 3 conditions ($N=15, 30, 60$), 5 trials each = 15 trials total, 525 LLM calls on `nemotron-3-super-120b-a12b`.
- **Results:**
  - $N=15$: Success rate = $20.0\%$ (1/5), Mean cost = `2257.79`, $\sigma = 155.56$.
  - $N=30$: Success rate = $20.0\%$ (1/5), Mean cost = `2228.50`, $\sigma = 104.71$.
  - $N=60$: Success rate = **$40.0\%$** (2/5), Mean cost = **`2183.80`**, $\sigma = \mathbf{20.92}$.
  - Search variance collapsed by **$86.5\%$** at $N=60$, eliminating catastrophic failure runs.
  - Cost per success stabilized at **$\$0.90$** per win.
- **Strongest Robust Policy:**
  - **`N60_T4_C51`** (Trial 4, Call 51, Perspective: Lexicographic Dual-Constraint Ranking):
    - Development mean cost: `8.7733` (active nodes: `6.8`).
    - Hidden total cost: **`2159.88`** (active nodes: **`13.25`**).
    - Defeated `kube_binpacking` (`2171.13`) on 120 held-out instances with zero unscheduled pods.

---

## 3. Candidate Policy Inventory & Verification

### Policy A: `T4_C01` (Experiment #13 Champion)
- **Source:** `experiment13/results/frozen_champions.json`
- **SHA-256:** `de872ce75fc68d43062b00ba2071e9fb7303163ba9b6040d425b21be41c15101`
- **Perspective:** Aggressive Node Consolidation
- **Mechanism:**
  1. `select_node`: Lexicographically prioritizes already-active nodes (flag 0 vs 1), then minimizes post-placement resource imbalance $|u_{\text{cpu}} - u_{\text{mem}}|$, then breaks ties by node hourly cost.
  2. `select_pod`: Re-orders pending pods by normalized demand $(u_{\text{cpu}}/\text{avg\_cpu} + u_{\text{mem}}/\text{avg\_mem})$, placing the largest/most constrained pod first.

### Policy B: `N60_T4_C51` (Experiment #14 Champion)
- **Source:** `experiment14/frozen/frozen_champions.json`
- **SHA-256:** `7a92d80f99a5d0b56694a52f67e1f5172b333ebd574dfbb132ddce368c7b137b`
- **Perspective:** Lexicographic Dual-Constraint Ranking
- **Mechanism:**
  1. `select_node`: Lexicographically ranks nodes by: (i) already-active priority, (ii) post-placement resource imbalance $|u_{\text{cpu}} - u_{\text{mem}}|$, (iii) node hourly cost.
  2. `select_pod`: None provided (uses default FIFO ordering).

### Core Baseline Inventory
- `kube_binpacking`: MostAllocated score ($50 \times (u_{\text{cpu}} + u_{\text{mem}})/2$) + BalancedAllocation score ($50 \times (1 - |u_{\text{cpu}} - u_{\text{mem}}|)$) + 100.0 active node consolidation bonus.
- `kube_default`: LeastAllocated score ($50 \times ((1-u_{\text{cpu}}) + (1-u_{\text{mem}}))/2$) + BalancedAllocation score.
- `first_fit`: First feasible node in cluster enumeration.
- `best_fit`: Node with least post-allocation normalized residual capacity.
- `best_fit_decreasing`: Re-orders pods by Euclidean norm $\sqrt{\text{cpu}^2 + (\text{mem}/4)^2}$ descending, places on Best Fit node.
- `worst_fit`: Node with most residual capacity (load spreading).

---

## 4. Audit of Simulator Fidelity & Limitations

The Experiment #13/14 simulator (`simulator.py`) was intentionally simplified for fast candidate discovery. The audit identifies the following specific limitations:

| Dimension | Experiment #13/14 Simulator | Production Kubernetes Reality |
| :--- | :--- | :--- |
| **Temporal Dynamics** | Static batch: all pods exist at $t=0$, placed once. | Dynamic stream: pods arrive at real timestamps $t_{\text{arr}}$, run for duration $\Delta t$, and terminate at $t_{\text{dep}}$. |
| **Node Lifecycles** | Static node pool: idle nodes cost 0, active nodes incur full hourly rate. | Autoscaling / Cluster Autoscaler: nodes spin up upon pending pod demand and shut down after idle cooldown. |
| **Infrastructure Metric** | Static sum of node hourly costs + imbalance penalty. | Integrated **node-hours** ($\int N(t) dt$) and hourly monetary expenditure over time. |
| **Workload Distribution** | Synthetic random normal/uniform distributions. | Real production distributions: heavy-tailed, bursty arrivals, multi-tier microservices, correlated resource requests. |
| **Pod Ordering** | Solvers could inspect all future pending pods via `select_pod`. | In real Kubernetes, pending pods arrive in a queue; schedulers operate primarily on the head of queue or within short scheduler cycles. |

---

## 5. Experiment #15 Simulation Architecture

To rigorously evaluate whether the discovered policies transfer to reality without losing scientific comparability, Experiment #15 must evaluate under two explicit modes:

1. **Mode A — Dynamic Trace Replay:**
   - Real container arrival times from production logs.
   - Real container durations (when available or modeled under sensitivity analysis).
   - Dynamic node activation and deactivation.
   - Primary Metric: **Active Node-Hours** and **Normalized Infrastructure Cost**.

2. **Mode B — Deterministic Static Packing Windows:**
   - Workload sliced into temporal windows (e.g., 15-minute, 30-minute, 1-hour arrival bursts).
   - Preserves exact static formulation from Experiments #13 and #14.
   - Primary Metric: **Total Active Node Cost** and **Placement Feasibility** on real production pod demands.

This two-mode architecture isolates whether any observed performance difference is caused by the workload distribution shift (Mode B) or the temporal dynamics (Mode A).
