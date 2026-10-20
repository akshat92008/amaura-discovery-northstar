# Amaura Labs — Stage 4 Resource, Compute & Authorization Plan
**Document ID:** `STAGE4-AUTH-PLAN-001`  
**Date:** October 15, 2026  
**Author:** Lead Research Engineer, Amaura Labs Discovery Engine  
**Target:** Explicit Financial Authorization & Phased Spending Ceilings  

---

## 1. Executive Summary & Authorization Request

This document establishes the resource requirements, token pricing models, compute limits, and governance tripwires for Stage 4. 

To maintain strict fiduciary discipline, **spending is phased across two sequential decision gates**. Authorization is currently requested **solely for Phase 1 (Pilot Study)**. Authorization for Phase 2 is strictly contingent upon passing Gate 1.

### Phased Authorization Table

| Phase | Trials | Total Model Calls | Expected Cost | Authorized Cap | Governance Action |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Development & Offline Testing** | N/A | 0 (Mock Mode) | $0.00 | **$0.00** | **Completed & Verified (47/47 tests pass)** |
| **Phase 1: Pilot Feasibility Study** | 3 Paired Trials | 300 calls max | $11.70 | **$15.00** | **REQUESTING AUTHORIZATION NOW** |
| **Phase 2: Decisive Expansion** | 7 Paired Trials | 700 calls max | $27.30 | **$35.00** | *Locked; requires Gate 1 success* |
| **Combined Maximum Ceiling** | **10 Trials** | **1,000 calls max** | **$39.00** | **$50.00** | **Absolute Hard Organization Ceiling** |

---

## 2. Transparent Cost & Token Consumption Model

### 2.1 Configured Endpoint & Pricing Parameters
- **Target Endpoint:** Local OmniRoute proxy (`http://127.0.0.1:20128/v1/chat/completions`) or OpenAI-compatible endpoint.
- **Configured Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b` (or approved frontier code model).
- **Conservative Price Rates (matching Stage 3 code):**
  - **Input Tokens:** $\$3.00$ per $1,000,000$ tokens ($\$0.0000030$ / token).
  - **Output Tokens:** $\$15.00$ per $1,000,000$ tokens ($\$0.0000150$ / token).

### 2.2 Token Expenditure Estimates per Generation Call
- **Prompt Size (Input):**
  - Arm A (Task instructions): ~300 words $\implies \sim 400$ tokens.
  - Arm C (Task instructions + 2 parent programs + metrics): ~1,500 words $\implies \sim 2,000$ tokens.
  - *Conservative Planning Average across arms:* **~7,000 tokens** (accommodating prompt growth across generations).
- **Completion Size (Output):**
  - Priority function code: ~200 words $\implies \sim 300$ tokens.
  - *Conservative Planning Maximum:* **1,200 tokens**.
- **Per-Call Base Cost:**
  $$\text{Cost}_{\text{call}} = (7,000 \times 0.000003) + (1,200 \times 0.000015) = \$0.021 + \$0.018 = \mathbf{\$0.039}$$

### 2.3 Phase 1 Pilot Cost Calculation (300 Calls Maximum)
- **Base Consumption:** $300 \text{ calls} \times \$0.039 = \$11.70$.
- **+15% Retry & Backoff Reserve:** $\$11.70 \times 1.15 = \mathbf{\$13.46}$.
- **Authorized Spending Limit:** **`$15.00`**.
  *(The `BudgetEnforcer` is instantiated with `max_cost_usd=15.0, max_requests=300`. It will halt immediately if this limit is reached).*

### 2.4 Phase 2 Expansion Cost Calculation (700 Calls Maximum)
- **Base Consumption:** $700 \text{ calls} \times \$0.039 = \$27.30$.
- **+15% Retry Reserve:** $\$27.30 \times 1.15 = \mathbf{\$31.40}$.
- **Additional Spending Limit:** **`$35.00`**.
- **Cumulative Total Cap:** $\$15.00 + \$35.00 = \mathbf{\$50.00}$.

---

## 3. Compute & Wall-Clock Estimates

- **LLM Call Latency:** ~2.5 seconds per query (local high-throughput GPU inference).
  - Pilot (300 calls): $300 \times 2.5\text{s} \approx 750\text{s} \approx 12.5\text{ minutes}$.
- **Simulation Latency:**
  - Fast C-optimized / pure Python packing: < 1.0 ms per 1,000 items.
  - Development evaluation (20 streams $\times$ 1,000 items): ~15 ms per candidate.
  - 50 candidates: < 1.0 second per trial.
  - Hidden evaluation (100 streams $\times$ 1,000 items): ~150 ms per trial champion.
- **Expected Total Wall-Clock Time:**
  - **Phase 1 Pilot:** **~45 minutes** (including retry pauses and checkpoint I/O).
  - **Full 10-Trial Campaign:** **~2.5 to 3.0 hours**.
  - **Hard Timeout Limit:** 5.0 hours (enforced by `BudgetEnforcer.max_wall_clock_sec = 18000`).

---

## 4. Explicit Stop Conditions & Safety Tripwires

Execution will halt automatically under any of the following conditions:

1. **Financial Ceilings:**
   - **Pilot Hard Stop:** Total spend reaches `$15.00` $\implies$ Raises `BudgetExhaustedException`.
   - **Cumulative Hard Stop:** Total spend reaches `$50.00` $\implies$ Raises `BudgetExhaustedException`.
   - **Software Tripwire:** Spend reaches 80% of authorized cap ($12.00 in pilot, $40.00 in full) $\implies$ Sets `tripwire_triggered = True`, logs high-priority warning, finishes in-flight evaluations, and halts new generation.
2. **Technical Failure Stops:**
   - **Provider Model Mismatch:** Returned model ID != requested model ID $\implies$ Raises `ModelMismatchException` and aborts immediately.
   - **Benchmark Hash Tampering:** SHA-256 of `dev.json` does not match manifest $\implies$ Fails closed at startup.
   - **Consecutive Unhandled Exceptions:** If 5 consecutive model queries fail after 4 retries each $\implies$ Aborts execution to prevent burning retries on a broken proxy.
3. **Scientific Futility Stop (Gate 1 Failure):**
   - After completing the 3 pilot trials, if Arm C's mean development advantage fails to meet the threshold:
     $$\bar{\Delta}_{\text{dev}} = \frac{1}{3}\sum_{t=1}^3 (\bar{\rho}_{\text{Arm C}, t} - \bar{\rho}_{\text{Arm A}, t}) \ge -0.005$$
     *(Arm C fails to beat Arm A on dev streams by at least 0.5 percentage points)*
     $\implies$ **STOP IMMEDIATELY**. Do not spend the remaining $35.00. Formally close the Stage 4 discovery track.

---

## 5. Conditions for Authorizing Future Scaling (Stage 5)

Additional follow-up experiments or scaling beyond $50.00 will be considered **if and only if**:
1. Stage 4 achieves **`ROBUST_DISCOVERY_SUPPORTED`** at Gate 2 ($p < 0.05, \text{CI}_{\text{upper}} < -0.005$, beating Best-Fit on 100 hidden streams).
2. The discovered heuristic shows demonstrable domain generalization across out-of-distribution item sizes.
3. A formal research proposal for Stage 5 (multi-objective program search or harder combinatorial problems) is submitted with an independent audit.

---

## 6. Founder Authorization Sign-Off Request

To launch the Phase 1 Pilot Study under the strict controls defined in this protocol:

- [ ] **I approve the Phase 1 Pilot Study spending limit of $15.00 USD (300 model calls max).**
- [ ] **I confirm that Phase 2 ($35.00 additional) remains locked until Gate 1 results are reviewed.**
- [ ] **I authorize the Lead Research Engineer to initiate live execution using the configured local endpoint.**

**Signed:** ___________________________________  
**Date:** _____________________________________
