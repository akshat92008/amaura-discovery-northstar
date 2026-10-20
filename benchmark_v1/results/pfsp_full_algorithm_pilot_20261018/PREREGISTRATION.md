# PREREGISTRATION: PFSP FULL ALGORITHM DISCOVERY PILOT
**Experiment Identifier:** `pfsp_full_algorithm_pilot_20261018`  
**Date:** October 18, 2026  
**Investigator:** Amaura Labs Autonomous Research Team  
**Problem Domain:** Permutation Flow-Shop Scheduling (PFSP)  
**Status:** Frozen Prior to Candidate Generation  

---

## 1. Research Question & Hypothesis

### Question
Can a frontier LLM discover a genuinely superior scheduling algorithm when granted a complete algorithm interface rather than a narrow job-priority scoring function?

### Hypothesis
In PFSP, constructive NEH insertion heuristics leave an empirical optimality gap, and job permutations exhibit non-linear multi-machine interactions. A full algorithm interface (`def solve(processing_times: list[list[int]]) -> list[int]`) allows the model to implement novel initial sorting metrics, lookahead tie-breaking, or post-insertion local search procedures, unlocking optimization paths inaccessible to scalar priority functions.

---

## 2. Model & Endpoint Configuration

- **Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b`
- **Serving Stack:** OmniRoute (`http://127.0.0.1:20128/v1/chat/completions`)
- **Sampling Mode:** Independent generation (Best-of-$N$, $N=32$)
- **Decoding Hyperparameters:**
  - `temperature`: 0.70
  - `max_tokens`: 2048
  - `stream`: False
- **Integrity Rule:** Zero simulated stand-ins. Transient transport failures are retried via bounded exponential backoff (max 3 retries). If failures persist, the affected slot preserves its failure status without fabrication.

---

## 3. Dataset Integrity & Quarantined Partitions

| Split | Path | Instances | Size Distribution | SHA-256 Hash |
| :--- | :--- | :---: | :---: | :--- |
| **Training** | `benchmark_v1/data/pfsp/train.json` | 18 | $n \in [20, 120], m \in [5, 15]$ | `558d5eaf61c313553f32ac0e32be971ef3d8ae84c4d0756d905d8fb4eb4a8595` |
| **Held-Out Test** | `benchmark_v1/data/pfsp/test.json` | 36 | $n \in [20, 100], m \in [5, 15]$ | `2f450676400f71f9085f0c3e3866c112ed3256d78bb5736d1a1f979a56460bbb` |

**Quarantine Protocol:**
The test dataset is strictly sealed. Neither test instances, processing matrices, nor test scores are accessible during candidate generation or champion selection. Champion selection is determined strictly on the 18 training instances. The selected champion is evaluated exactly once on the 36 held-out test instances.

---

## 4. Empirical Baseline Reference Landscape

Evaluated on exact cryptographic datasets prior to candidate generation:

| Baseline Algorithm | Training Total Makespan ($C_{\max}$) | Training Mean ($C_{\max}$) | Test Total Makespan ($C_{\max}$) | Test Mean ($C_{\max}$) | Rel. vs NEH (Train) | Rel. vs NEH (Test) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Natural Order** | 85,106 | 4,728.11 | 176,820 | 4,911.67 | $+0.23\%$ | $+0.23\%$ |
| **NEH (Nawaz et al. 1983)** | **84,907** | **4,717.06** | **176,409** | **4,900.25** | **0.00%** | **0.00%** |
| **Iterated Greedy (bounded)** | 84,844 | 4,713.56 | 176,338 | 4,898.28 | $-0.07\%$ | $-0.04\%$ |
| **NEH-LS (NEH + Insertion Local Search)** | **84,593** | **4,699.61** | **176,145** | **4,892.92** | **$-0.37\%$** | **$-0.15\%$** |

*Note: Measured opportunity on these benchmark instances shows that a single-pass insertion local search (thousands of sequence evaluations) yields a $-0.37\%$ improvement on Train and $-0.15\%$ on Test. A 1% improvement over NEH represents a major algorithmic advance.*

---

## 5. Candidate Interface, Evaluator & Sandbox

- **Interface:**
  ```python
  def solve(processing_times: list[list[int]]) -> list[int]:
  ```
  - Input: $n \times m$ matrix where row $j$ contains processing times of job $j$ across $m$ machines.
  - Output: Permutation of $[0, 1, ..., n-1]$.
- **Execution Limits:**
  - Per-instance timeout: 4.0 seconds.
  - Total evaluation timeout (across 18 training instances): 40.0 seconds.
- **Validity Checks:**
  - Permutation length exactly $n$.
  - All elements integers in $[0, n-1]$.
  - Zero duplicates (set length exactly $n$).
  - Any violation, timeout, or runtime exception results in invalidity (`score = None`, rejected).
- **Security Sandbox:**
  - AST verification: forbidden calls (`eval`, `exec`, `open`, `__import__`, etc.) and unauthorized modules blocked.
  - Allowed modules: `math`, `random`, `collections`, `itertools`, `heapq`, `copy`.

---

## 6. Predetermined Success Criterion & Decision Framework

### Success Gate (Candidate Discovery)
A candidate algorithm is designated a **discovery candidate** if and only if:
1. **Validity:** It produces strictly valid permutations across all evaluation instances.
2. **Training Improvement:** Its total makespan on training data is strictly less than NEH ($< 84,907$).
3. **Generalization:** Its relative makespan improvement over NEH on held-out test data is at least **1.0%** ($\le -0.010$).
4. **Independent Replication:** It must be replicated across 10 fresh, previously unseen PFSP instances (seeds 90001–90010) before a confirmatory claim is issued.

### Decision Rules
- **GO:** At least one candidate meets the discovery criteria and replicates. Proceed to targeted exploitation / confirmatory scaling.
- **MODIFY:** Candidates exhibit valid, diverse algorithmic structures but fail to reach the 1% threshold; analyze structural bottlenecks (e.g. timeout limits, local search depth, representation prompts).
- **STOP:** Candidates fail to produce useful algorithmic behaviors or are strictly dominated by standard baselines; conclude this configuration and recommend a pivot.
