# AMAURA LABS — NORTH BLUESTAR DISCOVERY KERNEL V0.1
## Unresolved Issues & Smallest Justified Next Actions

**Document:** `discovery_kernel_v01/UNRESOLVED_ISSUES_AND_NEXT_ACTIONS.md`  
**System:** North BlueStar — Discovery Kernel v0.1  
**Date:** October 19, 2026  

---

## 1. Unresolved Technical & Architectural Issues

While Discovery Kernel v0.1 satisfies all five immediate acceptance gates, the following architectural boundaries and limitations remain:

### Issue 1: Process Isolation vs. Hostile Code Containerization
- **Diagnosis:** The current `ExecutionSupervisor` uses Python `multiprocessing` with SIGTERM/SIGKILL termination. This provides total crash containment, GIL isolation, and timeout enforcement, but runs under the host user account.
- **Risk:** If an untrusted frontier LLM generates code containing malicious OS calls (`import os; os.system(...)`), process isolation alone does not prevent unauthorized filesystem reads or network activity unless augmented by AST checks or OS namespaces.
- **Scope Limit:** Resolved for trusted deterministic algorithms and benchmark heuristics; unresolved for untrusted code execution.

### Issue 2: Single Active Domain in Adapter Registry
- **Diagnosis:** The initial pilot integrated and verified PFSP (Permutation Flow Shop Scheduling) with 5 concrete adapters. Bin packing and graph coloring implementations exist in the repository but have not yet been wrapped into concrete `MethodAdapter` subclasses in `discovery_kernel/`.
- **Impact:** The kernel is architecturally domain-agnostic, but its pre-packaged adapter library currently supports one production domain.

### Issue 3: Platform-Dependent Memory Bounding (`setrlimit`)
- **Diagnosis:** Memory bounding via `resource.setrlimit(RLIMIT_AS)` is enforced on Linux but is non-operational on macOS Darwin for heap allocations via `malloc`.
- **Impact:** Memory-runaway attacks or massive memory allocation leaks require Linux cgroups or OS containerization to guarantee strict memory caps on macOS.

### Issue 4: Deterministic vs. Dynamic Budget Allocation
- **Diagnosis:** The controller enforces a static evaluation cap (`max_evaluations`) and fixed per-instance timeout (`max_runtime_sec_per_instance`).
- **Opportunity:** Advanced search controllers will require dynamic, multi-fidelity resource allocation (e.g., successive halving or bandit allocation) where unpromising methods are cut early to conserve budget for champions.

---

## 2. The Single Smallest Justified Next Action

> [!IMPORTANT]
> In accordance with the bounded research strategy, we do **NOT** recommend launching an algorithm discovery campaign or generating new LLM batches.

The single smallest justified next engineering action is:

### **Next Action: Implement `BinPackingMethodAdapter` in `discovery_kernel/method_adapter.py`**
- **Objective:** Verify multi-domain pluggability by wrapping existing deterministic bin packing heuristics (Best-Fit, First-Fit, Worst-Fit from [`stage4/src/simulator.py`](file:///Users/ashishsingh/Desktop/experiment1/stage4/src/simulator.py)) into the `MethodAdapter` interface.
- **Resource Cost:** 
  - Paid API spend: **\$0.00**.
  - Compute: **< 1 minute CPU**.
  - Engineering effort: **~30 minutes**.
- **Deliverable:** 
  - Add `BinPackingMethodAdapter` to `discovery_kernel/method_adapter.py`.
  - Add 2 focused unit tests in `tests/test_discovery_kernel.py`.
  - Confirm that the existing `DeterministicController`, `ExecutionSupervisor`, and `EvidenceStore` execute bin packing without modifying a single line of kernel code.
