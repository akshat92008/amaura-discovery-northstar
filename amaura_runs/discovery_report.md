# Amaura Discovery Engine: Scientific Validation Report

**Problem Domain:** `BIN_PACKING`  
**Status:** BASELINE PRESERVED  
**Total Generations:** 25  

---

## 1. Executive Summary

| Metric | Human Baseline (seed_best_fit) | Amaura Discovered Champion | Improvement |
|---|---|---|---|
| **Fitness (Lower is Better)** | **6.6839** | **6.6839** | **0.00%** |
| **Test Raw Score** | 58.7167 | 58.7167 | +0.0000 |
| **Generalization Score (Unseen)** | 47.8750 | 47.8750 | +0.0000 |
| **Runtime Latency** | 14.18 ms | 14.18 ms | +0.00 ms |
| **AST Complexity (Nodes)** | 19 | 19 | +0 |

---

## 2. Evolutionary Fitness Trajectory

```text
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 |                          
   6.68 | •••••••••••••••••••••••••
        +-------------------------
        Gen 1             Gen 25
```

---

## 3. Discovered Algorithm Implementation

```python
def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    # Best Fit: pack into bin with least remaining space
    return -remaining_capacity
```

**Discovery Lineage:**
- **Candidate ID:** `e42bc86a`
- **Generation:** `0`
- **Mutation Operator:** `seed_best_fit`
- **Parent Lineage:** `Initial Seed`
- **Code SHA-256 Hash:** `e5b83beb7a80`

---

## 4. Human Baseline Code

```python
def priority(item: float, remaining_capacity: float, bin_capacity: float) -> float:
    # Best Fit: pack into bin with least remaining space
    return -remaining_capacity
```

---

## 5. Statistical Rigor & Anti-Overfitting Analysis

- **Train vs. Generalization Ratio:**
  - Training Score: `58.9000`
  - Held-out Unseen Distribution Score: `47.8750`
  - Generalization Delta: `11.0250` (Close to zero indicates no benchmark gaming or distribution memorization).
- **Physical Feasibility Checks:** Passed 100% of mathematical boundary checks (zero capacity violations, zero duplicate allocations).
