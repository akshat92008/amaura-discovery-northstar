# Amaura Experiment #16 — Formal Scientific Pre-Registration

**Document Status:** FROZEN & PRE-REGISTERED  
**Date:** 2026-10-04  
**Principal Investigator:** Amaura Autonomous Research Protocol  
**Domain:** Dynamic Cloud Pod Scheduling under Continuous Workload Churn  

---

## 1. Executive Summary & Mission

Amaura Experiment #15 confirmed that while our independently discovered policy `T4_C01` matched and slightly improved upon `kube_binpacking` in static batch placement, `kube_binpacking` defeated `T4_C01` by **2.50%** under continuous dynamic replay with asynchronous workload arrivals and departures.

Algorithmic post-mortem identified the **Drainability Gap**:
- `T4_C01` minimizes multi-resource skew $|u_{\text{cpu}} - u_{\text{mem}}|$ across all active nodes, effectively spreading incoming traffic evenly to keep every host balanced.
- In dynamic environments with departures, this load spreading prevents lightly loaded hosts from emptying out to zero, keeping large 96-core servers active and billed.
- Conversely, `kube_binpacking`'s `MostAllocated` term concentrates workloads onto already dense nodes, leaving lightly loaded hosts free to drain and power down.

**The Core Question of Experiment #16:**
> **Can Amaura discover a scheduling policy that explicitly accounts for temporal churn and node-draining dynamics, while retaining strong static packing behavior?**

Experiment #16 tests whether Amaura's frozen discovery loop—when equipped with an evaluator that directly measures continuous infrastructure cost under churn—can autonomously synthesize a policy that bridges this gap and statistically outperforms `kube_binpacking`.

---

## 2. Formal Hypotheses

### Primary Hypothesis (H1 — Churn-Aware Discovery Hypothesis)
When Amaura's evaluator measures true continuous dynamic infrastructure cost ($\int N_{\text{active}}(t) \cdot \text{cost\_rate} \, dt$) under asynchronous arrivals and departures, independent candidate generation will discover at least one policy that statistically outperforms the frozen `kube_binpacking` baseline on unseen dynamic production-like workloads ($p < 0.05$, paired Wilcoxon signed-rank test).

### Null Hypothesis ($H_0$)
Amaura's search will not produce a policy that reliably outperforms `kube_binpacking` on unseen dynamic workloads ($p \ge 0.05$ or higher mean cost).

### Secondary Hypotheses
- **H2 — Dynamic Specialization:** A policy discovered using a dynamic evaluator will substantially outperform the static-discovered champion `T4_C01` under continuous dynamic replay.
- **H3 — Static Preservation:** A successful dynamic policy will not catastrophically degrade static packing performance on Mode B benchmark instances.
- **H4 — Mechanistic Emergence:** The winning policy will exhibit emergent mechanisms related to node drainability, asymmetric host polarization, active-node concentration, or temporal locality, generated independently without manual code insertion.

---

## 3. Negative Constraints (What We Are NOT Testing)

To preserve scientific rigor and prevent human algorithm hacking, the following are strictly prohibited:
1. **No Manual Algorithm Engineering:** Neither `MostAllocated`, nor specific threshold heuristics, nor hand-tuned combinations of `T4_C01` and `kube_binpacking` may be manually inserted.
2. **No Evolutionary / QD Loops:** In accordance with Experiments #8, #11, and #14, search remains strictly **Independent Best-of-N**.
3. **No Prompt Leakage:** Prompts must not expose the 2.5% gap, `T4_C01`'s failure mode, or hidden trace identities.
4. **No Post-Hoc Objective Modification:** The cost function and penalties are permanently frozen.
5. **No Peeking:** Hidden benchmark traces (Days 3–4) remain strictly untouched until discovery is complete and champions are cryptographically frozen.

---

## 4. Frozen Baselines & SHA-256 Provenance

All baselines are frozen in `experiment16/baselines/` and `experiment16/policies/`.

| Baseline Identifier | Strategy / Plugin Description | SHA-256 Hash |
| :--- | :--- | :--- |
| `kube_binpacking` | MostAllocated + BalancedAllocation + Active Bonus (+100.0) | `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` |
| `kube_default` | LeastAllocated (Load Spreading) + BalancedAllocation | `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` |
| `first_fit` | First Feasible Host | `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` |
| `best_fit` | Least Residual Multidimensional Capacity | `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` |
| `best_fit_decreasing` | Norm-Sorted Pods + Best Fit | `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` |
| `worst_fit` | Maximum Residual Capacity (Spreading) | `a5f0b5fa735b3b625dab3dc7ee15769e9473fd3a5aaed28cbb83295292af0cdb` |
| `Policy_A_T4_C01` | Discovered Static Champion (Exp #13 Trial 4 Candidate 01) | `de872ce75fc68d43062b00ba2071e9fb7303163ba9b6040d425b21be41c15101` |
| `Policy_B_N60_T4_C51`| Discovered High-Budget Static Champion (Exp #14 N60 T4 C51) | `7a92d80f99a5d0b56694a52f67e1f5172b333ebd574dfbb132ddce368c7b137b` |

---

## 5. Search Architecture & Budget

- **Architecture:** Pure Independent Best-of-N Conceptual Sampling
- **Model Endpoint:** `nvidia/nvidia/nemotron-3-super-120b-a12b` via OmniRoute proxy (`port 20128`)
- **Sampling Parameters:** Temperature $T = 0.6$, `max_completion_tokens` = 4096
- **Budget per Trial:** $N = 60$ independent candidate generation calls
- **Independent Trials:** 5 independent search replications
- **Total Search Calls:** $5 \times 60 = 300$ candidate calls
- **Trial Seeds:** `[44401, 44402, 44403, 44404, 44405]`
- **Concurrency:** 5 parallel worker threads

---

## 6. Prompt Library & Anti-Leakage Compliance

Candidate generation draws from a library of 60 distinct conceptual perspectives across 10 theoretical categories:
1. Workload Churn & Departure Dynamics (1–6)
2. Node Drainability & Evacuation Velocity (7–12)
3. Active-Node Preference & Hysteresis (13–18)
4. Multi-Resource Balance & Skew Minimization (19–24)
5. Temporal Locality & Lifecycle Heuristics (25–30)
6. Dynamic Consolidation & Bin Packing (31–36)
7. Online Algorithms & Competitive Analysis (37–42)
8. Queueing Theory & Workload Flow (43–48)
9. Utilization Thresholds & Safe Saturation (49–54)
10. Composite & Lexicographic Hybrid Strategies (55–60)

**Zero-Leakage Guarantee:**
Audit confirms zero mention of `MostAllocated`, zero mention of `T4_C01`, zero mention of the 2.5% gap, and zero mention of Alibaba production traces.

---

## 7. Data Partitions & Firewall

Strict chronological isolation is enforced across all trace sets:
- **Development Partition (`benchmarks/dev/`):** Trace events from Day 1 ($t = 0 \to 86,400\text{s}$). Used exclusively during candidate generation and internal ranking.
- **Validation Partition (`benchmarks/val/`):** Trace events from Day 2 ($t = 86,400 \to 172,800\text{s}$). Used for non-tuning pre-evaluation checks.
- **Hidden Benchmark (`benchmarks/hidden/`):** Days 3–4 ($t = 259,200 \to 432,000\text{s}$). Untouched firewall partition opened exactly once after trial champions are frozen.

### Cryptographic Benchmark Manifest
- `dev/mode_a_dynamic.json`: `a27458997cf8e8d95fd6803475249fc5f29872c0710da93b55d662a568790aed`
- `dev/mode_b_static.json`: `eb1c82179fd725b797444ca89913143469a4b19faebbff93d10e7cf401d14c14`
- `val/mode_a_dynamic.json`: `b4aedf0503ec73973b17383507dec96720ae900c8401a20559900720d898c7f6`
- `val/mode_b_static.json`: `a39b3beecc28d0dc2958c8cac04a45b0287f1ee6388434f8f6c0c2fb7d9fbf38`
- `hidden/mode_a_dynamic.json`: `9903e076c62d1aacc5e3c3437ed82030e46fbea0bdaebe78e9f2efef6ba2f4f7`
- `hidden/mode_b_static.json`: `71b263f8e6bea8e94601d9eea954576b798adafd4104edf93a6b9fbad6969ffd`

---

## 8. Dynamic Evaluator & Cost Model

Deterministic discrete-event replay tracks active node intervals $[t_{\text{on}}, t_{\text{off}}]$ clamped to the simulation window $[W_{\text{start}}, W_{\text{end}}]$.

$$\text{Total Cost} = \sum_{j \in \text{Nodes}} \left( \text{cost\_per\_hour}_j \cdot \frac{\text{active\_seconds}_j}{3600} \right) + 1000.0 \cdot N_{\text{unscheduled}}$$

- Uniform hardware rate: \$4.08 per 96-core node-hour (\$0.0425/core-hour).
- Feasibility Constraint: 100% placement required. Penalty: \$1,000.00 per unplaced container.
- Simulator Checksum: `e58e27314c84ac0c9e7ac25bde26c431f4d4d84eaff77dd4b541f518e5bfb9fc` (exact match with certified Exp #15 simulator).

---

## 9. Pre-Registered Decision Criteria

### Strong Success
Amaura discovers a policy that:
1. Achieves lower overall dynamic infrastructure cost than `kube_binpacking` on unseen hidden traces.
2. Achieves statistically significant paired improvement ($p < 0.05$, Wilcoxon signed-rank test).
3. Maintains 100% placement feasibility.
4. Retains competitive static packing performance ($\le 5\%$ difference from `kube_binpacking` on Mode B).
5. Exhibits an autonomously generated churn-aware mechanism.

### Moderate Success
Amaura does not statistically defeat `kube_binpacking`, but:
1. Outperforms `T4_C01` under dynamic replay by $\ge 2.0\%$.
2. Approaches within 1.0% of `kube_binpacking`.
3. Discovers a clear emergent concentration/drainability mechanism.

### Failure
Any of the following:
1. Dynamic discovery performs no better than `T4_C01`.
2. Candidates fail to compile or exhibit runtime crashes ($>15\%$ invalid rate).
3. The discovered policies remain purely static-balance heuristics without dynamic awareness.

---

## 10. Productization Milestone Boundary

Regardless of outcome, Experiment #16 represents the final pure-research benchmark. Upon completion, a comprehensive **Amaura Capability Scorecard** will be compiled, transitioning the project from research benchmarking to **Amaura Productization**.
