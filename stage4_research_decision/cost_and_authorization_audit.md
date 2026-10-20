# Amaura Labs — Stage 4 Cost & Authorization Control Audit
**Document ID:** `STAGE4-COST-AUDIT-001`  
**Date:** October 15, 2026  
**Auditor:** Lead Research Engineer, Amaura Labs Discovery Engine  
**Target:** Adversarial Recalculation of Compute Budgets, Token Modeling & Enforcement Verification  

---

## 1. Mathematical Recalculation of Expected Spend

### 1.1 Base Pricing Assumptions
The financial model uses the conservative rates established in Stage 3:
- **Input Tokens ($P_{\text{in}}$):** $\$3.00$ per million tokens ($\$0.0000030$ / token).
- **Output Tokens ($P_{\text{out}}$):** $\$15.00$ per million tokens ($\$0.0000150$ / token).

### 1.2 Call-Level Token & Cost Breakdown
- **Arm A Calls (Independent Sample):**
  - Prompt: System instructions + formatting rules = ~300 words $\implies \sim 400$ tokens.
  - Completion: 1 priority function = ~200 words $\implies \sim 300$ tokens.
  - Cost per Arm A call: $(400 \times 0.000003) + (300 \times 0.000015) = \$0.0012 + \$0.0045 = \mathbf{\$0.0057}$.
- **Arm C Calls (Evolutionary Mutation):**
  - Prompt: Instructions + 2 parent variants + fitness metrics = ~1,500 words $\implies \sim 2,000$ tokens.
  - Completion: 1 priority function = ~250 words $\implies \sim 350$ tokens.
  - Cost per Arm C call: $(2,000 \times 0.000003) + (350 \times 0.000015) = \$0.0060 + \$0.00525 = \mathbf{\$0.01125}$.
- **Average Cost per Generation Slot:**
  $$\bar{C}_{\text{slot}} = \frac{\$0.0057 + \$0.01125}{2} \approx \mathbf{\$0.008475}$$
- **Conservative Planning Rate (incorporating prompt growth & retries):**
  - Assumed input tokens: **7,000 tokens** ($\$0.0210$).
  - Assumed output tokens: **1,200 tokens** ($\$0.0180$).
  - Conservative cost ceiling per call: $\mathbf{\$0.0390}$ / call.

---

## 2. Phase-by-Phase Budget Recalculation

### 2.1 Phase 1: Feasibility Pilot ($T = 3$ Trials, Seeds 40401–40403)
- **Seeds Evaluated:** 4 baseline seeds per arm (evaluated offline on CPU, **$0.00 API cost**).
- **Model Calls per Arm:** $50 - 4 = 46$ calls.
- **Total Calls per Trial:** $46 + 46 = 92$ calls.
- **Total Pilot Calls (3 trials):** $3 \times 92 = \mathbf{276\text{ calls}}$ (max configured limit: 300 calls).
- **Expected Base Spend (realistic):** $276 \times \$0.008475 \approx \mathbf{\$2.34}$.
- **Conservative Spend (7,000 in / 1,200 out):** $276 \times \$0.0390 = \mathbf{\$10.76}$.
- **+15% Retry & Backoff Reserve:** $\$10.76 \times 1.15 = \mathbf{\$12.38}$.
- **Authorized Spending Cap:** **`$15.00 USD`**.
- *Surplus Margin:* $\$15.00 - \$12.38 = \mathbf{\$2.62}$ safety buffer (21% headroom).

### 2.2 Phase 2: Independent Confirmatory Campaign ($T = 10$ Trials, Seeds 40411–40420)
*(Contingent exclusively on Gate 1 success)*
- **Total Confirmatory Calls (10 trials):** $10 \times 92 = \mathbf{920\text{ calls}}$ (max configured limit: 1,000 calls).
- **Expected Base Spend (realistic):** $920 \times \$0.008475 \approx \mathbf{\$7.80}$.
- **Conservative Spend (7,000 in / 1,200 out):** $920 \times \$0.0390 = \mathbf{\$35.88}$.
- **Authorized Expansion Cap:** **`$35.00 USD`**.
- **Combined Hard Ceiling:** $\$15.00 + \$35.00 = \mathbf{\$50.00 USD}$.

---

## 3. Physical Enforcement vs. Documentation: Reality Verification

We audited whether each budget tier is **physically enforced by code** or **merely documented in markdown**:

| Control Parameter | Documented Value | Physical Enforcement Mechanism | Verification Status |
| :--- | :---: | :--- | :---: |
| **Phase 1 Pilot Cap** | **$15.00** | [`stage4/src/client.py:97`](./stage4/src/client.py#L97): `BudgetEnforcer(max_cost_usd=15.0)` raises `BudgetExhaustedException` immediately before any query that crosses $15.00. | **GENUINELY ENFORCED** |
| **Phase 2 Expansion Cap** | **$35.00** | Runner configures cumulative cap at `$50.00` ($15.00 spent + $35.00 new). | **GENUINELY ENFORCED** |
| **Software Tripwire** | **$12.00 (Pilot) / $40.00 (Full)** | [`stage4/src/budget_enforcer.py:123`](./stage4/src/budget_enforcer.py#L123): `is_tripwire_triggered()` sets `tripwire_triggered = True` in ledger and initiates graceful wind-down. | **GENUINELY ENFORCED** |
| **Hard Organization Cap** | **$50.00** | Absolute ceiling hardcoded into `Stage4Runner` constructor. | **GENUINELY ENFORCED** |
| **Missing Metadata Fallback** | N/A | [`stage4/src/budget_enforcer.py:166-169`](./stage4/src/budget_enforcer.py#L166-L169): Charges conservative tokens $(1.33 \times \text{words} + 50)$. Zero free calls permitted. | **GENUINELY ENFORCED** |
| **Multi-Process Concurrency** | N/A | [`stage4/src/budget_enforcer.py:80-111`](./stage4/src/budget_enforcer.py#L80-L111): `_file_lock()` with `fcntl.flock` synchronizes spend across independent processes. | **GENUINELY ENFORCED** |
| **Interrupted Run Accumulation**| N/A | [`stage4/src/budget_enforcer.py:113-126`](./stage4/src/budget_enforcer.py#L113-L126): `_load_ledger_if_exists()` reloads cumulative spend on restart. | **GENUINELY ENFORCED** |

---

## 4. Internal Ledger Enforcement vs. External Financial Exposure

> [!WARNING]
> **An internal software ledger does NOT guarantee an external credit card bill.**  
> The internal `BudgetEnforcer` calculates dollar costs based on local assumed token rates ($3.00 input / $15.00 output per million tokens). If the upstream provider bills at different rates, applies minimum query charges, or bills in another currency, the external bill is decoupled from local software tracking.

### 4.1 Physical Bounds Enforced in Code
To establish a defensible physical exposure ceiling that does not rely on assumed dollar rates, the code enforces strict structural limits:

| Physical Control | Value | Physical Enforcement Mechanism | Exposure Bounding Effect |
| :--- | :---: | :--- | :--- |
| **Request Ceiling** | **300 calls** | [`stage4/src/client.py:94`](./stage4/src/client.py#L94) & [`stage4/src/budget_enforcer.py:147`](./stage4/src/budget_enforcer.py#L147) | Halts pre-flight before opening HTTP connection #301. Maximum possible HTTP transactions = 300. |
| **Max Output Tokens** | **512 tokens** | Explicit in payload: `{"max_tokens": 512}` in [`stage4/src/client.py:148`](./stage4/src/client.py#L148) and [`stage4/src/search.py`](./stage4/src/search.py) | Upstream model physically cuts generation at 512 tokens. Total pilot completion tokens $\le \mathbf{153,600\text{ tokens}}$ ($0.154\text{ MTok}$). |
| **Bounded Prompt Size**| **$\le 3,300$ tokens** | System prompt (~100 words) + Instructions (~300 words) + 2 Parent Programs (~1,200 words) $\le 2,500$ words | Total pilot prompt tokens $\le 300 \times 3,300 = \mathbf{990,000\text{ tokens}}$ ($0.99\text{ MTok}$). |
| **Bounded Retries** | **2 retries max** | [`stage4/src/client.py:88`](./stage4/src/client.py#L88): 1 initial attempt + 2 retries | Pre-flight check executes before every retry attempt. A failing call cannot spam requests. |
| **Concurrency Ceiling** | **1 thread (Serial)** | [`stage4/src/runner.py`](./stage4/src/runner.py) executes sequentially | Zero background API worker pools. Overlapping concurrent billing is impossible. |

### 4.2 Worst-Case Dollar Exposure Across Provider Pricing Tiers (for 300 Requests)

Given physical ceilings of $0.99\text{ MTok}$ input and $0.154\text{ MTok}$ output across 300 calls:

| Upstream Model Pricing Tier | Input Rate / MTok | Output Rate / MTok | Absolute Worst-Case Pilot Spend |
| :--- | :---: | :---: | :---: |
| **Tier 1: Budget Coding Models (DeepSeek, Qwen 2.5)** | $\$0.50$ | $\$2.00$ | $0.99 \times 0.50 + 0.154 \times 2.00 = \mathbf{\$0.80}$ |
| **Tier 2: Configured Rates (Nemotron 120B / Claude 3.5)** | $\$3.00$ | $\$15.00$ | $0.99 \times 3.00 + 0.154 \times 15.00 = \mathbf{\$5.28}$ |
| **Tier 3: Higher Frontier Pricing** | $\$5.00$ | $\$25.00$ | $0.99 \times 5.00 + 0.154 \times 25.00 = \mathbf{\$8.80}$ |
| **Tier 4: Extreme Premium Pricing** | $\$10.00$ | $\$40.00$ | $0.99 \times 10.00 + 0.154 \times 40.00 = \mathbf{\$16.06}$ |

### 4.3 Forensic Audit of Local OmniRoute Proxy (`~/.omniroute`)
An offline inspection of `~/.omniroute` established:
1. **Running Daemon:** A Node.js process (PID 17057) is currently listening on `localhost:20128`.
2. **Provider Connections:** Database `storage.sqlite` confirms active connections for `nvidia` with `auth_type: apikey`.
3. **Historical Provenance:** Call logs from October 14, 2026 (Stage 3) confirm successful completion of requests for `nvidia/nemotron-3-super-120b-a12b` via NVIDIA's API endpoint.
4. **Remaining Blocker:** The upstream NVIDIA account's billing terms (free developer credits vs. paid pay-as-you-go enterprise tier) cannot be verified without network inspection of NVIDIA's account dashboard.

---

## 5. Prerequisite Authorization Protocol

To guarantee that actual expenditure cannot exceed \$15.00 USD, authorization requires:
1. **Founder Confirmation of Upstream Cap:** The founder must confirm that the upstream API key has a provider-level monthly spend limit, credit cap, or prepaid balance of $\le \mathbf{\$20.00\text{ USD}}$.
2. **Strict Physical Bounds:** Execution must run with `max_tokens=512`, `max_retries=2`, and `max_requests=300`.
3. **Execution Scope:** Authorization applies **strictly to Phase 1 Pilot ($15.00 limit, Seeds 40401–40403)**. Phase 2 ($35.00 limit) remains completely unauthorized.
