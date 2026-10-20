# AMAURA LABS STAGE 3: EXECUTION-SCHEDULING DEVIATION & TRIAL-CONCURRENCY AUDIT LOG

**Protocol Version:** Revision 4.3 (Frozen Protocol)  
**Target Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b` (Temperature 0.7, Max Tokens 4096)  
**Benchmark:** Minimum Vertex Graph Coloring (40 Dev instances, 200 Hidden instances)  
**Date of Deviation Authorization:** 2026-10-11  
**Document Status:** Permanent Audit Trail Record  

---

## 1. NATURE AND RATIONALE OF SCHEDULER DEVIATION

On 2026-10-11, after the successful completion and verification of Trials 01, 02, 03, and 04 under strictly sequential execution ($C = 1$), an execution-scheduler change was authorized to reduce excessive wall-clock latency while preserving the frozen scientific protocol.

### Invariants Preserved (Frozen Protocol):
* $T_{\text{main}} = 30$ paired trials.
* $N = 100$ candidate slots per arm per trial (9,000 total candidate slots).
* Exact Model: `nvidia/nvidia/nemotron-3-super-120b-a12b`.
* Prompts, temperature ($0.7$, $0.1$ for blind select), max tokens ($4,096$), and system prompts.
* Benchmark instances: 40 Dev (`dev.json`, hash verified), 200 Hidden (`hidden.json`, hash verified).
* Technical Hidden Firewall: Actively blocking `hidden.json` access during trial execution.
* Arm A, Arm B, Arm C structural definitions and information flow rules.
* Practical margin of 1 color.
* No-retry, no-replacement, and no-bonus-candidate rules.
* Frozen statistical analysis suite: Finite-only Wilcoxon signed-rank test, 10,000-sample bootstrap CIs, McNemar binary reliability test, bounded worst-case imputation sensitivity ($S_{\text{penalty}} = 19,001$).

### Modification & Rescission History:
* **Proposed Modification (2026-10-11):** Authorized trial-level concurrency with up to four independent trial workers (`max_trial_workers = 4`).
* **Final Executive Directive (2026-10-11T22:35:55):** Rescinded the concurrent scheduler authorization in full. Maintained **strictly sequential execution ($C = 1$)** across all 30 paired trials. No concurrent execution occurred in the main experiment. The original sequential runner (`main_runner.py`) remains the sole execution engine.

---

## 2. INTRA-TRIAL SEQUENTIAL INTEGRITY & GLOBAL SEMAPHORE

Pursuant to the authorized scheduling rules:

1. **Strict Intra-Trial Sequentiality:**
   * Within each trial worker, generation remains **strictly sequential** (`max_workers = 1` inside `Stage3SearchEngine`).
   * **Arm A:** 100 sequential candidate-generation calls. No parallel batching.
   * **Arm B:** 10 generations $\times$ 10 sequential calls, with strict barrier synchronization between generations.
   * **Arm C:** 10 generations $\times$ 10 sequential calls, with evaluation barrier and frozen structured feedback packet between generations.
2. **Global Concurrency Ceiling:**
   * Only **one** LLM request may be in flight per trial worker at any instant.
   * A global bounded semaphore (`threading.BoundedSemaphore(4)`) strictly bounds the maximum number of in-flight LLM requests across the entire operating system to **four**.
3. **Complete Trial Isolation:**
   * Each trial retains its own deterministic seed ($30300 + \text{trial\_id}$).
   * Each trial writes to its own isolated lineage file (`stage3/checkpoints/trial_{trial_id:02d}/trial_{trial_id:02d}_candidates.jsonl`).
   * Each trial writes its own atomic checkpoint (`trial_{trial_id:02d}_record.json` and `status.txt`).
   * Merging to `stage3/candidates/main_candidates.jsonl` occurs atomically under an exclusive mutex (`merge_lock`) only upon verified trial completion.
   * Zero shared mutable state, zero cross-trial feedback, and zero information leakage between trials.

---

## 3. AUDIT OF PRIOR CONCURRENCY EQUIVALENCE FINDINGS

In accordance with scientific integrity guidelines:
* **No claim of certified sequential/concurrent equivalence is made.**
* The earlier preliminary concurrency study (`stage3/audit/concurrency_scientific_equivalence_report.md`) compared only **one single evolutionary trajectory ($T = 1$)** of sequential execution against one single trajectory ($T = 1$) of concurrent execution.
* In stochastic evolutionary systems at temperature 0.7, comparing two individual trajectories pools auto-correlated descendant steps, generating non-generalizable candidate-level $p$-values. Those candidate-level statistics must **not** be interpreted as proof of an intrinsic API concurrency distortion.
* However, because equivalence was not formally certified under strict statistical standards, trial-level parallelization was selected specifically because independent trials are causally, statistically, and mathematically independent replicates.

---

## 4. PER-TRIAL EXECUTION MODE AUDIT TABLE

**EXECUTIVE PROTOCOL AMENDMENT (2026-10-11T22:35:55):**  
The proposed trial-level concurrency scheduler switch was **rescinded**. All 30 paired trials are maintained under **strictly sequential execution ($C = 1$)** with exactly one in-flight LLM call globally at all times.

| Trial ID | Random Seed | Execution Mode | Max In-Flight Calls / Trial | Global Concurrency Limit | Checkpoint Status | Outcome / Selected Scores |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Trial 01** | `30301` | Strictly Sequential | 1 | 1 | `COMPLETED` | Arm A: 222 \| Arm B: 221 \| Arm C: 221 |
| **Trial 02** | `30302` | Strictly Sequential | 1 | 1 | `COMPLETED` | Arm A: 222 \| Arm B: None \| Arm C: 219 |
| **Trial 03** | `30303` | Strictly Sequential | 1 | 1 | `COMPLETED` | Arm A: 222 \| Arm B: None \| Arm C: 219 |
| **Trial 04** | `30304` | Strictly Sequential | 1 | 1 | `COMPLETED` | Arm A: 222 \| Arm B: None \| Arm C: 222 |
| **Trial 05** | `30305` | Strictly Sequential | 1 | 1 | `IN PROGRESS` | In progress (Arm A complete, Arm B in progress) |
| **Trials 06–30** | `30306`–`30330` | Strictly Sequential | 1 | 1 | Queued | To be executed sequentially via `main_runner.py` ($C=1$) |

