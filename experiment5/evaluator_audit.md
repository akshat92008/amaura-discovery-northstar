# Experiment #5: Evaluator Information Boundary & Security Audit

**Date:** October 3, 2026  
**Subject:** Verification of Information Isolation in the Rich-State Candidate Interface (`choose_bin`)

---

## 1. Candidate Function Interface

```python
def choose_bin(
    item: float,
    bin_remaining: list[float],
    recent_items: list[float],
    bin_capacity: float
) -> int:
    """
    Given the current item, the remaining capacities of all open bins,
    and a history of up to 10 recent items, select the target bin index.
    
    Returns:
        int: Index of the open bin (0 <= index < len(bin_remaining)) to pack into,
             OR -1 to open a new bin.
    """
```

---

## 2. Concrete Example of Information Provided at Time Step $t$

At any arbitrary time step $t$ in an online sequence of length $N=100$:

```text
======================= CANDIDATE INPUT STATE =======================
Current item:       42.0
Open bins:          [12.0, 57.0, 81.0]
Recent items:       [31.0, 19.0, 48.0]
Bin capacity:       100.0
=====================================================================
```

---

## 3. Explicit Information Deliberately Withheld / Not Provided

The following variables are **strictly isolated** and never passed or accessible to the candidate function:

```text
=================== DELIBERATELY ISOLATED INFORMATION ================
Future items:                 NOT AVAILABLE (items at t+1, t+2, ... N are unrevealed)
Full sequence:                NOT AVAILABLE (total sequence array is held only in evaluator)
Total sequence length (N):    NOT AVAILABLE (algorithm does not know if 10 or 10,000 items remain)
Theoretical optimum (OPT):    NOT AVAILABLE (lower bound calculated only post-sequence)
Hidden benchmark ID / Seed:   NOT AVAILABLE (evaluator seed is private)
Instance metadata / Family:   NOT AVAILABLE (evaluator does not identify Weibull, Bimodal, etc.)
Current benchmark score:      NOT AVAILABLE (evaluator aggregates bins privately)
Memory between instances:     NOT AVAILABLE (global scope purged per evaluation instance)
External environment:         NOT AVAILABLE (network, filesystem, OS calls blocked by sandbox)
======================================================================
```

---

## 4. Evaluator Defensive Copying Verification

To prevent the candidate from tampering with evaluator internals:
1. `bin_remaining` is passed as a **shallow copy**: `list(open_bins)`. In-place mutations by the candidate do not affect the evaluator's state.
2. `recent_items` is passed as a **shallow copy**: `list(recent_items)`. Modifications to the history do not leak.
3. If the candidate returns an index `idx` where `open_bins[idx] < item - 1e-6` (capacity violation), the evaluator raises an explicit `ValueError` and penalizes the candidate with `excess_pct = inf`.
4. If the candidate raises any exception, it is caught and assigned `excess_pct = inf`. No fallback heuristic is executed.

---

## 5. Security Sandbox Policy

Static analysis (`ast.parse`) strictly verifies:
- Only the pure `math` module is importable.
- Forbidden builtins: `eval`, `exec`, `open`, `__import__`, `globals`, `locals`, `getattr`, `setattr`, `os`, `sys`, `socket`.
- Signature check: Must define `choose_bin(item, bin_remaining, recent_items, bin_capacity)`.

---

## 6. Audit Verdict

**PASS**: The information boundary strictly matches a realistic online agent with local state awareness. No future lookahead or global sequence leakage exists.
