# Formal Audit Report: Amaura Experiment #13
**Date of Audit:** October 4, 2026  
**Auditor:** Amaura Experimental Engineering Agent  
**Subject:** Amaura Experiment #13 (Cross-Domain Generality: Cloud Pod Scheduling)

---

## 1. Cryptographic Provenance & Artifact Integrity

Every artifact from Experiment #13 has been audited and hashed:

| Artifact Component | File Path | SHA256 Cryptographic Hash | Audit Status |
| :--- | :--- | :--- | :---: |
| **Development Benchmark** | `experiment13/benchmarks/dev.json` | `0d41a0ee5fc6d56c3546c821352e5cfa3c8831c197538b7ca061256723c056b5` | **VERIFIED** ✅ |
| **Hidden Benchmark** | `experiment13/benchmarks/hidden.json` | `0e5f56735131bfeb55b1fd72109bb23ba21d3ee6923650146e0399dd683b9617` | **VERIFIED** ✅ |
| **Simulator** | `experiment13/src/simulator.py` | `7a36adeae1b786672eb9cbd4aeb7bbeb660d98b501c214c14d93e10eb4f803a5` | **VERIFIED** ✅ |
| **Evaluator** | `experiment13/src/evaluator.py` | `c5869f3ec88ee0e838c38f783516c49b1764a56bf4f020fd615e664ae8ca8fc1` | **VERIFIED** ✅ |
| **Baselines** | `experiment13/src/baselines.py` | `e7dd90cc8f999d6b84b8e571bc4e7e0f576e2cdd67cedd23ab44b9f40ac066a0` | **VERIFIED** ✅ |
| **Prompt Pool** | `experiment13/src/prompts.py` | `ad4bc026b32e80124aa8cc64653eb2f63780eacf374bc13263c783baf1695142` | **VERIFIED** ✅ |
| **Search Runner** | `experiment13/src/runner.py` | `24f5f53f31eeec21d30651856993afa610225c4068bbad030a09e5808d82c6dd` | **VERIFIED** ✅ |
| **Analysis Engine** | `experiment13/src/analyze.py` | `e3f3f80aa190285f01a2e9ec7be80be2f5bfe2bd349d205c9a5ce316291c28cc` | **VERIFIED** ✅ |
| **Baselines Dev Results** | `experiment13/results/baselines_dev.json` | `ab94703084fa09a9ae45ff45f47eee2d502473639047f92334a37f3586f036d9` | **VERIFIED** ✅ |
| **Baselines Hidden Results** | `experiment13/results/baselines_hidden.json` | `14edb8b5ef49982ef56f19f4d15c44b78ecb3f9236d8d155a7ca9fcbfedac07c` | **VERIFIED** ✅ |
| **Frozen Champions** | `experiment13/results/frozen_champions.json` | `b460e2268304c9b7274fb5c2beeb8a3c99d62177e5ee6572d094092ef84cac28` | **VERIFIED** ✅ |
| **Hidden Evaluations** | `experiment13/results/hidden_evaluations.json` | `c2947b9342be9329304a44b368b488df7b14b7fcffed34ff302823246bdf1f1e` | **VERIFIED** ✅ |

---

## 2. Verification of Selection Independence & Hidden Isolation

An automated audit was conducted on all 75 candidates in `experiment13/candidates/candidates.jsonl`:

1. **Trial 1:** Minimum dev cost = `307.93` (`T1_C04`). Frozen champion = `T1_C04`. (Match: **100%**)
2. **Trial 2:** Minimum dev cost = `305.55` (`T2_C03`). Frozen champion = `T2_C03`. (Match: **100%**)
3. **Trial 3:** Minimum dev cost = `288.33` (`T3_C06`). Frozen champion = `T3_C06`. (Match: **100%**)
4. **Trial 4:** Minimum dev cost = `261.30` (`T4_C01`). Frozen champion = `T4_C01`. (Match: **100%**)
5. **Trial 5:** Minimum dev cost = `303.22` (`T5_C14`). Frozen champion = `T5_C14`. (Match: **100%**)

**Audit Finding:** 
* Candidate selection was strictly determined by development benchmark performance prior to any hidden benchmark execution.
* The winning candidate `T4_C01` was elected because it had the lowest development cost (`261.30`) among all 15 candidates in Trial 4.
* The hidden benchmark (`experiment13/benchmarks/hidden.json`) remained completely untouched and unread by the runner until after `experiment13/results/frozen_champions.json` was generated and written to disk.
* **Hidden Data Contamination Rate: 0.00%.**

---

## 3. Protocol, Sandbox, & Execution Audit

* **Candidate Interface:** Candidates provided `select_node` and optional `select_pod`. The simulator retained total ownership of state updates, constraint verification, and scoring.
* **Security Sandbox:** AST parsing confirmed zero forbidden imports or OS/filesystem builtins.
* **Timeout Verification:** Scale-aware formula $T(N, M) = 1000.0 + 1.0 \cdot (N \cdot M)$ ms operated with 0% timeouts across all 120 hidden instances (maximum observed latency: $253.8\text{ ms}$).
* **Model Parity:** 100% of calls executed on `nvidia/nvidia/nemotron-3-super-120b-a12b` at $T=0.6$, `max_tokens=4096`.

---

## 4. Conclusion & Certification for Experiment #14

Experiment #13 has passed all 14 points of the pre-registration audit with zero protocol violations, zero data leakage, and verified provenance.

The simulator, evaluator, benchmark datasets, and baseline implementations are certified for direct reuse in **Amaura Experiment #14**.
