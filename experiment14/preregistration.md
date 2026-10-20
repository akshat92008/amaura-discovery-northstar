# Pre-Registration Document: Amaura Experiment #14
## Search Budget Scaling & Discovery Reliability in Cloud Pod Scheduling
**Registration Date:** October 4, 2026  
**Auditor / Principal Investigator:** Amaura Experimental Engineering Agent  
**Status:** FROZEN & PRE-REGISTERED PRIOR TO SEARCH EXECUTION  

---

### 1. Research Question
> **As we increase the number of independent conceptual samples given to Amaura ($N=15, N=30, N=60$), does the probability of discovering a genuinely superior solution increase predictably and reliably?**

---

### 2. Hypotheses
* **$H_1$ (Scalable Discovery):** Increasing independent conceptual sampling increases the probability of discovering a candidate that materially outperforms the incumbent baseline (`kube_binpacking`) on unseen instances.
* **$H_0$ (Search Saturation / Null):** Increasing independent conceptual sampling does not meaningfully improve discovery success probability.

---

### 3. Experimental Design & Budget Conditions
* **Domain:** Kubernetes-Style Cloud Pod Scheduling Simulation (identical to Experiment #13).
* **Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b` ($T=0.6$, `max_tokens=4096`).
* **Architecture:** Pure Independent Best-of-N (Zero evolution, zero QD, zero refinement, zero parent-child mutation).
* **Three Primary Conditions:**
  1. **Condition A ($N=15$):** 15 independent calls per trial $\times$ 5 trials = **75 calls**
  2. **Condition B ($N=30$):** 30 independent calls per trial $\times$ 5 trials = **150 calls**
  3. **Condition C ($N=60$):** 60 independent calls per trial $\times$ 5 trials = **300 calls**
* **Total Calls:** $75 + 150 + 300 = \mathbf{525\text{ LLM calls}}$.
* **Replications:** 5 independent trials per budget with distinct random seeds.

---

### 4. Master Prompt Pool & Permutation Structure
* **Master Pool:** 60 distinct conceptual prompt perspectives (Categories: Consolidation & Bin Packing, Vector & Geometric, Economic & Price-Performance, Constraint & Slack Preservation, Scheduling & Queue Prioritization, Hybrid & Radical).
* **Permutation Rule:** For each replication trial $k$ with seed $S_k$, the 60 master perspectives are permuted deterministically via `random.Random(seed).shuffle(angles)`.
* **Nested Sampling:**
  - $N=15$ uses the first 15 angles of the trial permutation.
  - $N=30$ uses the first 30 angles of the trial permutation.
  - $N=60$ uses all 60 angles of the trial permutation.

---

### 5. Baselines (Independently Re-Verified & Frozen)
On the 120-instance hidden benchmark:
* `kube_binpacking`: **`2171.1271`** (Strongest Baseline / Reference)
* `first_fit`: **`2412.6474`**
* `best_fit_decreasing`: **`2547.2079`**
* `best_fit`: **`2614.9182`**

---

### 6. Development Selection & Blind Hidden Evaluation
* For each trial, $N$ candidates are executed across 30 development instances (`seed=1042`).
* Exactly one champion per trial is selected by minimum development cost:
  $$\text{Champion} = \arg\min_{c \in \text{Valid}} \text{Cost}_{\text{dev}}(c)$$
* Champions are cryptographically hashed and saved to `experiment14/frozen/frozen_champions.json`.
* Only after all 15 champions (5 for $N=15$, 5 for $N=30$, 5 for $N=60$) are frozen does blind hidden evaluation begin on the 120 hidden instances (`seed=70099`).

---

### 7. Primary Success Metric & Decision Rules
* **Primary Metric:** **Discovery Success Rate** — the proportion of trials where the trial champion outperforms `kube_binpacking` (`2171.13`) on the complete 120-instance hidden benchmark:
  $$\text{Success Rate}(N) = \frac{\text{Successful Trials}(N)}{5}$$
* **Decision Framework:**
  * **Strong Positive:** $N=30$ or $N=60$ substantially increases discovery success rate (e.g. from $20\%$ to $\ge 60\%$), and improvement is statistically meaningful. Conclude: *Independent sampling is a scalable discovery mechanism.*
  * **Weak Positive:** Larger $N$ improves best-case hidden performance but does not increase success rate reliably. Conclude: *More search increases ceiling but not reliability.*
  * **Null / Saturation:** $N=15, 30, 60$ show statistically indistinguishable success rates and hidden scores. Conclude: *Independent sampling saturates; need alternative search allocation.*
  * **Negative:** Larger budgets produce worse results due to dev-set overfitting or noise accumulation.
