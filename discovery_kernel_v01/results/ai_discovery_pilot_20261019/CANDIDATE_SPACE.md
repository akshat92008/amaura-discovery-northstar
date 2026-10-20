# PFSP Restricted Declarative Algorithm Space

## 1. Motivation & Execution Safety

To guarantee 100% containment and zero arbitrary code execution, North BlueStar does not allow language models to execute unconstrained Python scripts in the execution supervisor. Instead, candidate algorithms are expressed as **declarative configuration specifications** over a strictly verified space of algorithmic components.

Every proposal is validated against a formal JSON schema, canonicalized to eliminate syntactic variation, and mapped deterministically to a verified modular solver (`PFSPDeclarativeAdapter`).

---

## 2. Component Taxonomy & Allowlist

A valid PFSP candidate specification is a JSON object with two top-level fields:
1. `rationale`: A natural language explanation of the design hypothesis.
2. `config`: A dictionary specifying exact algorithmic choices from the verified component allowlist.

### 2.1 Construction Phase Components

1. **`initial_order`** (Job Priority / Ordering Heuristic):
   - `"total_processing_time_desc"`: Jobs sorted by total processing time across all machines in descending order (classical NEH priority, LPT).
   - `"total_processing_time_asc"`: Jobs sorted by total processing time in ascending order (Shortest Processing Time, SPT).
   - `"first_machine_asc"`: Jobs sorted by processing time on machine 1 ascending (Johnson's rule heuristic).
   - `"last_machine_desc"`: Jobs sorted by processing time on the final machine descending (Johnson's rule heuristic).
   - `"weighted_profile_desc"`: Palmer's slope index $\sum_{k=1}^m (2k - m - 1) p_{j,k}$ descending (prioritizes jobs with earlier light processing and later heavy processing).

2. **`construction_criterion`** (Partial Insertion Objective):
   - `"makespan_only"`: Evaluates partial schedules by makespan $C_{\max}$ alone (classical NEH insertion).
   - `"makespan_and_flow_time"`: Evaluates partial schedules primarily by makespan $C_{\max}$, and secondarily by partial total flow time $\sum C_j$ (Candidate #2 / V0 heuristic).
   - `"makespan_and_idle_time"`: Evaluates partial schedules primarily by makespan $C_{\max}$, and secondarily by cumulative machine idle time.

3. **`tie_break`** (Position Tie-Breaking Strategy):
   - `"first_found"`: Selects the first position index achieving the optimal criterion score (stable prefix insertion).
   - `"last_found"`: Selects the last position index achieving the optimal criterion score.
   - `"flow_time_min"`: Resolves makespan ties by choosing the position with minimal partial flow time.
   - `"idle_time_min"`: Resolves makespan ties by choosing the position with minimal machine idle time.

---

### 2.2 Local Search Phase Components

4. **`local_search`** (Neighborhood Operator):
   - `"none"`: No local search; pure constructive heuristic (e.g. classical NEH).
   - `"pairwise_swap"`: Explores adjacent pairwise swaps of jobs across the permutation.
   - `"single_pass_insertion"`: Taillard single-pass insertion neighborhood (extracts each job in sequence and tests all possible insertion positions, keeping improvements).
   - `"multi_pass_insertion"`: Multi-pass insertion neighborhood repeated until local optimum or evaluation budget exhaustion.

5. **`search_strategy`** (Neighborhood Step Control):
   - `"first_improvement"`: Accepts the first neighbor that improves the acceptance criterion.
   - `"best_improvement"`: Evaluates all candidate neighbors in a pass and moves to the best neighbor.
   - `"none"`: Required when `local_search == "none"`.

6. **`acceptance_rule`** (Move Acceptance Criterion):
   - `"strictly_better_makespan"`: Accepts a neighbor if and only if $C_{\max}(\pi') < C_{\max}(\pi)$.
   - `"better_makespan_or_flow"`: Accepts a neighbor if $C_{\max}(\pi') < C_{\max}(\pi)$, or if $C_{\max}(\pi') == C_{\max}(\pi)$ and flow time is strictly improved (Candidate #2 rule).
   - `"none"`: Required when `local_search == "none"`.

7. **`budget_evaluations`** (Evaluation Cap per Instance):
   - Integer in range $[0, 500]$.
   - If `local_search == "none"`, normalized to `0`.
   - If `local_search != "none"`, must be $\ge 50$ and $\le 500$ to ensure bounded runtime within supervisor limits.

---

## 3. Formal JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PFSPDeclarativeAlgorithmConfig",
  "type": "object",
  "required": ["rationale", "config"],
  "properties": {
    "rationale": {
      "type": "string",
      "minLength": 5
    },
    "config": {
      "type": "object",
      "required": [
        "initial_order",
        "construction_criterion",
        "tie_break",
        "local_search",
        "search_strategy",
        "acceptance_rule",
        "budget_evaluations"
      ],
      "properties": {
        "initial_order": {
          "type": "string",
          "enum": [
            "total_processing_time_desc",
            "total_processing_time_asc",
            "first_machine_asc",
            "last_machine_desc",
            "weighted_profile_desc"
          ]
        },
        "construction_criterion": {
          "type": "string",
          "enum": [
            "makespan_only",
            "makespan_and_flow_time",
            "makespan_and_idle_time"
          ]
        },
        "tie_break": {
          "type": "string",
          "enum": [
            "first_found",
            "last_found",
            "flow_time_min",
            "idle_time_min"
          ]
        },
        "local_search": {
          "type": "string",
          "enum": [
            "none",
            "pairwise_swap",
            "single_pass_insertion",
            "multi_pass_insertion"
          ]
        },
        "search_strategy": {
          "type": "string",
          "enum": [
            "none",
            "first_improvement",
            "best_improvement"
          ]
        },
        "acceptance_rule": {
          "type": "string",
          "enum": [
            "none",
            "strictly_better_makespan",
            "better_makespan_or_flow"
          ]
        },
        "budget_evaluations": {
          "type": "integer",
          "minimum": 0,
          "maximum": 500
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

---

## 4. Canonicalization & Duplicate Detection

To identify identical algorithm specifications regardless of whitespace or key ordering:
1. If `local_search == "none"`, normalize `search_strategy = "none"`, `acceptance_rule = "none"`, and `budget_evaluations = 0`.
2. Format the `config` dictionary as a compact, sorted JSON string: `json.dumps(config, sort_keys=True, separators=(',', ':'))`.
3. Compute the cryptographic SHA-256 digest of the canonical string to produce `recipe_hash`.
4. Any subsequent proposal with the identical `recipe_hash` is flagged as a **syntactic duplicate**.
5. During evaluation, if a proposal produces identical makespan values across all development instances to an earlier proposal, it is recorded as a **behavioral duplicate**.
