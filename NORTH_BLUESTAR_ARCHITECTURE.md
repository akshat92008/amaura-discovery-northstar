# AMAURA LABS — NORTH BLUESTAR ARCHITECTURE & FORENSIC AUDIT REPORT

## 1. Executive Summary & Forensic Verification of Prompt Hypotheses

Following a zero-trust, code-and-artifact forensic audit of the supplied Amaura repository (`amaura/`, `stage2/`, `stage3/`, `stage4/`, and `experiment2/`–`experiment16/`), every claim in the engineering brief was tested directly against the raw source code and execution logs.

### 1.1 Verification of Supplied Repository State vs. Prompt Hypotheses

| Hypothesis / Claim in Brief | Forensic Verification Against Raw Repository Artifacts | Root Cause Identified in Source Code |
| :--- | :--- | :--- |
| **1. Prompt-example anchoring, duplicate proposals, behavioural collapse, and zero discovery advantage** | **VERIFIED (Exact Match in `stage4/results/pilot2/results.json`)**: Out of 50 LLM-generated candidates in Pilot 2, 46 were valid (21 AI-only valid, 25 deterministic-repaired). Although AST canonicalization recorded **25 unique canonical AST hashes**, all 46 valid candidates achieved the **exact same fitness score (`0.03143305906678479`)**—identical to the canonical `Best-Fit` baseline (`0.0%` discovery advantage). | In `stage4/src/simulator.py` (line 172), the prompt instructs: *"Write a concise Python function `priority(item, remaining_capacity)` that returns a float priority score to minimize leftover space."* Because online bin selection takes $\arg\max_{b} \text{priority}(w, r_b)$, **any strictly decreasing monotonic transformation $f(r_b - w)$ induces the exact same total order over open bins as Best-Fit** ($\text{priority} = -(r_b - w)$). Syntactic AST hashing treated `-(rem - item)`, `1.0 / (rem - item + 1.0)`, and `-(rem - item)**2` as distinct candidates even though they are 100% behaviorally identical. |
| **2. Stage 2 PFSP & Graph Coloring evaluation flaws** | **VERIFIED (`stage2/src/evaluator_pfsp.py`, `tests/test_pfsp_penalty_flaw.py`, `STAGE2_FINAL_REPORT.md`)**: Early experiments assigned a static penalty (`1e9`) to invalid PFSP permutations and allowed candidates to mutate the input matrix in-place (`matrix[i][j] = 0`), enabling zero-makespan reward hacking. Even after patching (`STAGE2_FINAL_REPORT.md`), LLM proposals in PFSP failed to beat classical `NEH` (`3202.27` vs `3201.95`, $p=0.5839$). | Raw LLM Python code synthesis for $O(N^2 M)$ combinatorial scheduling struggled to implement Taillard's $O(N M)$ forward/backward acceleration matrices (`e[r][k]`, `q[r][k]`) without off-by-one bugs or timeouts, degenerating into slow $O(N^3 M)$ loops or simple priority sorts equivalent to Palmer/NEH without local search (`NEH-LS`). |
| **3. 780 structural PFSP configurations & semantic redundancies** | **VERIFIED & FORMALIZED (`north_bluestar/candidates.py`)**: A declarative PFSP operator space crossing $5$ priority rules $\times 4$ tie-breakers $\times 3$ insertion modes ($60$ constructive bases) with $13$ refinement slots yields **780 structural configurations**. Semantic canonicalization proves **120 structural configurations collapse by 60** (to **660 canonical configurations**, a **15.38% structural redundancy**) before even running an instance. | When `local_search_op == "none"`, the `pivot_rule` parameter (`first_improvement` vs. `best_improvement`) is dead state that never executes. Furthermore, on instances without exact processing-time ties, secondary tie-breakers collapse to identical initial permutations. |
| **4. Feedback controller & generational memory limitations (`stage3/src/search_engine.py`)** | **VERIFIED (`stage3/src/search_engine.py` lines 356, 388–418, 483)**: Two structural bugs crippled Arm C (`C_AMAURA`) adaptive search: (a) **Markov-1 Generational Amnesia**: `prior_gen_eval_results = current_gen_cands` overwrote the parent pool every generation, forgetting better elites from generations $1 \dots g-2$; (b) **Fake Recombination**: `combine_parents` selected two parent IDs (`valid_prior[:2]`), but lines 424–426 only injected `best_prior['code_body']` into the LLM prompt—never showing the second parent's code! | Both defects in `stage3/src/search_engine.py` have now been remediated so cumulative valid elites are retained across all generations and all selected parent code blocks are injected during structural recombination. |
| **5. Holdout leakage, silent baseline impersonation, and unkillable timeout threads in `amaura/`** | **VERIFIED (`amaura/evaluators/base.py`, `amaura/evaluators/cache_policy.py`, `amaura/engine/generator.py`)**: (a) `BaseEvaluator.evaluate_candidate()` unconditionally ran `train`, `test`, and `generalization` splits on every search step; (b) `CachePolicyEvaluator.simulate_cache()` caught candidate exceptions and silently substituted `-float(meta["recency"])` (canonical LRU), crediting broken candidates with LRU's hit rate; (c) `ThreadPoolExecutor` timeouts cannot kill runaway Python CPU loops. | Remediated directly in `amaura/evaluators/base.py` (`include_holdout: bool = False` default), `amaura/evaluators/cache_policy.py` (raises `RuntimeError` on exception or `NaN`/`Inf`), `amaura/engine/generator.py` (fail-closed when LLM credentials are missing), and superseded by `north_bluestar/execution.py` with OS subprocess `SIGKILL` enforcement. |

---

## 2. Target Architecture of North BlueStar (`north_bluestar/`)

North BlueStar is engineered as a modular, method-agnostic discovery kernel organized around seven explicit capabilities:

### Capability A: Problem Formalization & Cryptographic Split Firewall (`north_bluestar/problem.py`)
- **`ProblemSpecification` ABC**: Separates hard constraint verification (`validate_solution() -> ConstraintCheckResult`), exact scalar objective computation (`compute_objective() -> float`), mathematical bounding (`compute_theoretical_bound() -> Optional[float]`), and verified classical baselines (`get_baselines()`).
- **Strict Separation of Feasibility and Optimality**:
  - Infeasible, crashing, or timed-out evaluations **always** receive `objective_value = None` and `status in {INFEASIBLE, EXECUTION_ERROR, TIMEOUT}`—eliminating penalty-score ranking inversions.
  - Feasible solutions are compared against mathematical lower/upper bounds (e.g., Taillard's machine-bottleneck lower bound for PFSP; $L_1 = \lceil \sum w_i / C \rceil$ for Bin Packing; clique/triangle lower bound for Graph Coloring) to distinguish `SolutionStatus.FEASIBLE` (measured heuristic improvement) from `SolutionStatus.PROVEN_OPTIMAL` ($\text{obj} = \text{bound}$).
- **`SplitFirewall`**: Isolates `DEVELOPMENT`, `VALIDATION`, and `FINAL_HOLDOUT` splits. Any attempt to read `FINAL_HOLDOUT` before `freeze_champions()` raises `SplitAccessViolationError`. Freezing champions emits a SHA-256 certificate binding the frozen champion IDs to the holdout dataset hash.

### Capability B: Plugin-Based Method Registry (`north_bluestar/methods.py`)
- **`MethodRegistry` & `MethodAdapter`**: Solvers register declarative `MethodCapabilities` specifying their `MethodParadigm`, supported problem IDs, supported `CandidateKind`s, optimality-proof capability, determinism, and compute cost tier.
- **Registered Paradigms**:
  1. `VerifiedBaselineMethodAdapter`: Classical heuristics (`NEH`, `Palmer`, `CDS`, `Best-Fit`, `First-Fit`, `Worst-Fit`, `DSATUR`, `Smallest-Last`), local search (`NEH-LS`, `DSATUR-Kempe-LS`), and bounded exact Branch-and-Bound with Iterated Greedy intensification (`BB-IG-Exact`).
  2. `DeclarativePFSPMethodAdapter`: Compiles `DeclarativePFSPConfig` specifications into $O(N^2 M)$ Taillard-accelerated constructive + Variable Neighborhood Descent (`insertion_ls`, `swap_ls`, `vnd_insert_swap`) solvers with zero `eval`/`exec`.
  3. `ParametricBinPackingMethodAdapter`: Compiles `DeclarativeBinPackingConfig` specifications combining slack exponents, fill-ratio bonuses, tight-fit thresholds, and mid-gap dead-zone penalties.
  4. `SandboxedPythonProgramMethodAdapter`: AST-validated Python program compiler blocking dangerous imports (`os`, `sys`, `subprocess`, `socket`, etc.) and dunder introspection.

### Capability C: Candidate Layer, Canonicalization & Behavioral Diversity (`north_bluestar/candidates.py`)
- **Three-Tier Identity Model**: Every `CandidateSpec` carries:
  1. `structural_hash`: Hash of raw configuration or source code.
  2. `canonical_hash`: Hash after semantic normalization (collapsing dead parameters such as `pivot_rule` when `local_search_op == "none"`, normalizing monotonic single-term Best-Fit exponents, or alpha-renaming & constant-folding Python ASTs via `_ASTNormalizer`).
  3. `behavioral_hash` & `behavioral_trace`: Computed by `BehavioralFingerprinter` on fixed synthetic micro-probes disjoint from all benchmark splits. Uses normalized Kendall $\tau$ rank distance (`compute_kendall_tau_distance`) over permutations and open-bin rankings so syntactically distinct candidates that induce identical decisions are automatically detected and deduplicated.

### Capability D: Modular Search Controller (`north_bluestar/controller.py`)
- Avoids monolithic heuristics by decomposing search into seven independently selectable `SearchStrategy` plugins:
  1. `BaselinePortfolioStrategy` (established OR & exact/B&B algorithms)
  2. `StructuredEnumerationStrategy` (stratified enumeration over canonicalized space)
  3. `RandomizedSearchStrategy` (seeded uniform canonical sampling)
  4. `LocalCoordinateSearchStrategy` (1-step operator neighborhood search around top elites)
  5. `OperatorRecombinationStrategy` (true multi-parent crossover combining constructive traits from Parent A with refinement traits from Parent B)
  6. `SurrogateUCBStrategy` (empirical factorial main-effect surrogate model with Upper Confidence Bound acquisition)
  7. `ProgramSynthesisStrategy` (anti-anchored AST program synthesis)
- **Adaptive Portfolio Allocation & Stopping**: `SearchController` allocates evaluations via empirical UCB posteriors and halts early upon reaching proven split optimality or hitting the diminishing-returns stagnation threshold.

### Capability E: Execution & Verification Supervisor (`north_bluestar/execution.py`)
- **True OS Subprocess Isolation**: Untrusted/synthesized candidates execute in separate OS processes (`multiprocessing.Process`) with defensive deep copies of input instances.
- **Hard `SIGKILL` Timeout Enforcement**: If a worker exceeds `timeout_ms`, the supervisor issues `proc.kill()` (`os.kill(pid, signal.SIGKILL)`) and joins immediately, recording `FailureCategory.TIMEOUT_SIGKILL` and incrementing `worker_killed_count`.
- **Honest Threat Model (`IsolationThreatModel`)**: Explicitly states POSIX process + AST allowlist guarantees while refusing to claim containment against kernel/native root exploits without an external microVM/seccomp sandbox.

### Capability F: Auditable Evidence Store & Empirical Learning (`north_bluestar/evidence.py`)
- **Cryptographic Hash Chain**: Every `EvidenceRecord` links to `prev_record_hash` with a SHA-256 `record_hash` verified by `verify_hash_chain()`.
- **Empirical Learning**:
  - `compute_marginal_operator_effects()` quantifies the marginal objective delta of every operator value (`vnd_insert_swap`, `insertion_ls`, `min_machine_idle`, `bottleneck_slack`, etc.) across DEVELOPMENT evaluations.
  - `compute_strategy_posteriors()` computes per-strategy feasibility rate, behavioral novelty rate, and UCB acquisition scores.

### Capability G: Preregistered Experimentation & Comparative Benchmarks (`north_bluestar/orchestrator.py`)
- Enforces the 4-phase scientific lifecycle:
  1. Anchor baseline evaluation on `DEVELOPMENT`.
  2. Budget-bounded search on `DEVELOPMENT` (`FINAL_HOLDOUT` sealed).
  3. Top-$K$ finalist selection on `VALIDATION`.
  4. Cryptographic champion freeze (`freeze_champions()`) and one-shot verification on `FINAL_HOLDOUT`.
