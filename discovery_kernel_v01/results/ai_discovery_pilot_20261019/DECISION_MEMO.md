# DECISION MEMO: North BlueStar AI Discovery Pilot
## Decision on Evidence-Guided Search & Algorithmic Discovery in PFSP

**Date:** 2026-10-19  
**To:** Amaura Labs Executive Committee & Technical Leadership  
**From:** Lead Experimental Scientist & Research Infrastructure Engineer  
**Experiment Identifier:** `ai_discovery_pilot_20261019`  
**Artifact Directory:** `discovery_kernel_v01/results/ai_discovery_pilot_20261019/`  

---

## 1. Executive Verdict

### **Verdict: MODIFY**

The bounded experimental pilot ran strictly to protocol completion under rigorous data quarantine, process containment, and zero financial spend ($0.00). However, the **preregistered discovery criterion was not met**. Neither candidate generation arm discovered an algorithm that outperformed the frozen Primary Baseline (`neh_ls_insertion`) by the preregistered 1.0% threshold on untouched holdout data.

Furthermore, evidence-guided search (Arm B) suffered severe mode collapse and performed significantly worse than independent candidate generation (Arm A).

---

## 2. Categorized Findings & Conclusions

### 1. Infrastructure Success: **HIGH CONFIDENCE PASS**
- **Discovery Kernel v0.1:** The kernel architecture operated with flawless stability across 740 instance evaluations.
- **Process Isolation & Containment:** Zero arbitrary Python code was executed. Candidates were restricted to a declarative configuration space executed via the trusted `PFSPDeclarativeAdapter`.
- **Fault Tolerance:** 100% of candidate solutions satisfied valid permutation constraints. Zero timeouts, memory leaks, or execution crashes occurred.
- **Budget Compliance:** Financial spend was verified at exactly **$0.00** across all 24 proposals using local host inference via Ollama (`qwen2.5-coder:1.5b`).

### 2. Candidate-Generation Success: **MODERATE (Arm A) / POOR (Arm B)**
- **Arm A (Independent Best-of-12):** Valid spec rate was 100% (12/12). Explored 7 distinct algorithmic recipes across the component space, identifying `arm_a_prop_08` (an accelerated flow-time guided insertion heuristic).
- **Arm B (Evidence-Guided Search):** Valid spec rate was 100% (12/12), but search dynamics suffered from severe **prompt anchoring**. Presenting the model with development results from early proposals caused it to anchor on a suboptimal heuristic (Palmer slope index) and re-generate the identical recipe across rounds (10 of 12 proposals were syntactic duplicates).

### 3. Generalization to Final Instances: **CONFIRMED GENERALIZATION DEFICIT**
- Evaluated on 30 fresh, quarantined holdout instances (seeds 500101–500130, SHA-256 `b714990db09d...`):
  - `neh_ls_insertion` (Primary Baseline): **3872.23** (Mean runtime: 357.5 ms)
  - `iterated_greedy` (Baseline): **3873.70** (Mean runtime: 285.5 ms)
  - `arm_a_prop_08` (Champion A): **3887.70** (Mean runtime: 107.0 ms)
  - `candidate_2_bounded` (Baseline): **3887.83** (Mean runtime: 91.3 ms)
  - `neh_classical` (Baseline): **3897.60** (Mean runtime: 92.1 ms)
  - `arm_b_prop_01` (Champion B): **3974.43** (Mean runtime: 101.9 ms)

### 4. Evidence For or Against Feedback-Guided Search: **STRONGLY NEGATIVE UNDER TESTED CONDITIONS**
- **Champion B vs Champion A:**
  - Mean relative makespan improvement $\bar{g}_{B \text{ vs } A} = -2.151\%$.
  - 95% Bootstrap Confidence Interval: **[-2.625%, -1.658%]**.
  - Win/Tie/Loss: **2 Wins, 1 Tie, 27 Losses**.
- **Conclusion:** Under the tested model tier and prompt structure, providing performance feedback degraded exploratory diversity and led to premature convergence on an inferior local optimum. Feedback did not guide the search toward better algorithms; it anchored it to an early mediocre proposal.

### 5. Evidence for an AI Discovery Advantage: **NEGATIVE**
- **Champion A vs Primary Baseline (`neh_ls_insertion`):**
  - Mean relative improvement $\bar{g} = -0.372\%$.
  - 95% Bootstrap Confidence Interval: **[-0.680%, -0.093%]**.
  - Win/Tie/Loss: **7 Wins, 4 Ties, 19 Losses**.
  - Preregistered 1.0% Gate: **FAIL**.
- **Champion B vs Primary Baseline (`neh_ls_insertion`):**
  - Mean relative improvement $\bar{g} = -2.528\%$.
  - 95% Bootstrap Confidence Interval: **[-2.984%, -2.015%]**.
  - Win/Tie/Loss: **1 Win, 1 Tie, 28 Losses**.
  - Preregistered 1.0% Gate: **FAIL**.
- **Silver Lining (Runtime/Quality Trade-Off):** Champion A outperformed classical NEH (3887.70 vs 3897.60) while achieving a **3.3x runtime speedup** over `neh_ls_insertion` (106.98 ms vs 357.51 ms). However, in accordance with scientific rigor, this efficiency trade-off cannot be relabeled as meeting the primary quality discovery gate.

---

## 3. Justification for MODIFY (Not GO, Not Open Treadmill)

1. **Why not GO?**  
   The preregistered gate required a statistically significant $\ge 1.0\%$ makespan improvement with a 95% bootstrap CI strictly above 0. Both candidates produced negative relative improvements against the primary conventional baseline. Claiming success would violate empirical integrity.

2. **Why not STOP the entire research engine?**  
   The Discovery Kernel infrastructure proved completely viable, reproducible, safe, and cost-effective. The failure occurred specifically at the prompt-level interaction between the LLM generator and round-based feedback. The declarative component space is sound, but the feedback formulation actively suppressed exploration.

3. **Required Modifications Before Future Investment:**
   - **Exploration vs Exploitation Prompting:** Feedback prompts must explicitly instruct the generator to mutate away from current champions (e.g. forced novelty penalties or component-level diversity constraints).
   - **Model Scaling Assessment:** Parameter-constrained models (such as 1.5B–7B) exhibit acute prompt recency bias; feedback search requires larger reasoning models or explicit external mutation operators (e.g., genetic crossover over the declarative JSON AST) rather than relying on LLM in-context memory.
   - **Do NOT launch an immediate automatic batch.** Evaluate these architectural modifications formally before allocating compute.

---

## 4. Finite Next Action

1. **Commit Artifacts:** Archive the pilot directory `discovery_kernel_v01/results/ai_discovery_pilot_20261019/` with its cryptographic manifest.
2. **Present Findings:** Review this memo with the research committee.
3. **No Unapproved Compute:** Suspend all further candidate-generation runs until the prompt feedback mechanism has been redesigned and approved.
