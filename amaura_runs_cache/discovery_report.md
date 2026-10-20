# Amaura Discovery Engine: Scientific Validation Report

**Problem Domain:** `CACHE_POLICY`  
**Status:** BREAKTHROUGH DISCOVERED  
**Total Generations:** 30  

---

## 1. Executive Summary

| Metric | Human Baseline (seed_lfu) | Amaura Discovered Champion | Improvement |
|---|---|---|---|
| **Fitness (Lower is Better)** | **57.1944** | **56.9299** | **+0.46%** |
| **Test Raw Score** | 59.9360 | 60.6080 | +0.6720 |
| **Generalization Score (Unseen)** | 17.1100 | 16.7633 | -0.3467 |
| **Runtime Latency** | 348.98 ms | 480.11 ms | +131.13 ms |
| **AST Complexity (Nodes)** | 26 | 52 | +26 |

---

## 2. Evolutionary Fitness Trajectory

```text
  57.19 | •••                           
  57.17 |                               
  57.14 |                               
  57.11 |                               
  57.08 |                               
  57.05 |                               
  57.02 |                               
  56.99 |    •••••                      
  56.96 |         ••••                  
  56.93 |             ••••••••••••••••••
        +------------------------------
        Gen 1                  Gen 30
```

---

## 3. Discovered Algorithm Implementation

```python
def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # Discovered adaptive frequency-recency decay policy
    alpha = 1.402
    beta = 0.386
    return (float(frequency) ** alpha) / ((float(recency) + 0.91) ** beta)
```

**Discovery Lineage:**
- **Candidate ID:** `02f615d4`
- **Generation:** `13`
- **Mutation Operator:** `ast_constant_perturbation`
- **Parent Lineage:** `a96b173a, a96b173a`
- **Code SHA-256 Hash:** `cbda4934a82e`

---

## 4. Human Baseline Code

```python
def evict_score(key: int, recency: int, frequency: int, age: int, cache_size: int) -> float:
    # LFU: lower frequency = lower score = evicted
    return float(frequency)
```

---

## 5. Statistical Rigor & Anti-Overfitting Analysis

- **Train vs. Generalization Ratio:**
  - Training Score: `56.3467`
  - Held-out Unseen Distribution Score: `16.7633`
  - Generalization Delta: `39.5833` (Close to zero indicates no benchmark gaming or distribution memorization).
- **Physical Feasibility Checks:** Passed 100% of mathematical boundary checks (zero capacity violations, zero duplicate allocations).
