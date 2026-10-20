import { NextRequest, NextResponse } from 'next/server';
import { execFile } from 'child_process';
import fs from 'fs/promises';
import path from 'path';

// Helper to safely execute Python scripts by streaming JSON payloads via stdin (WEB-3)
function runPythonWithStdin(script: string, inputPayload: Record<string, unknown>, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = execFile(
      'python3',
      ['-c', script],
      {
        cwd: process.cwd(),
        timeout: timeoutMs,
      },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr || error.message));
        } else {
          resolve(stdout.trim());
        }
      }
    );

    if (child.stdin) {
      child.stdin.write(JSON.stringify(inputPayload));
      child.stdin.end();
    } else {
      reject(new Error('Failed to open stdin for python process'));
    }
  });
}

// Helper for strict finite integer parsing and range enforcement (3.2)
function parseFiniteInteger(value: unknown, fieldName: string, minVal: number, maxVal: number, defaultValue?: number): number {
  if (value === undefined || value === null) {
    if (defaultValue !== undefined) return defaultValue;
    throw new Error(`Field '${fieldName}' is required.`);
  }
  const n = typeof value === 'number' ? value : Number(String(value).trim());
  if (!Number.isFinite(n) || !Number.isInteger(n)) {
    throw new Error(`Field '${fieldName}' must be a finite integer, got '${String(value)}'.`);
  }
  if (n < minVal || n > maxVal) {
    throw new Error(`Field '${fieldName}' must be between ${minVal} and ${maxVal}, got ${n}.`);
  }
  return n;
}

// Canonical search grammar allowlists matching north_bluestar/candidates.py exactly (3.1)
const ALLOWED_PROBLEM_IDS = new Set([
  'pfsp_makespan',
  'online_bin_packing_1d',
  'graph_coloring',
]);

const ALLOWED_STRATEGY_MODES = new Set([
  'north_bluestar_portfolio',
  'randomized_search',
  'structured_enumeration',
  'local_coordinate_search',
  'operator_recombination',
  'surrogate_ucb',
]);

const ALLOWED_PRIORITY_RULES = new Set([
  'total_time_desc',
  'palmer_slope',
  'gupta_profile',
  'cds_stage_best',
  'front_back_weighted',
]);

const ALLOWED_TIE_BREAKERS = new Set([
  'index_asc',
  'first_machine_asc',
  'last_machine_desc',
  'bottleneck_slack',
]);

const ALLOWED_INSERTION_MODES = new Set([
  'earliest_makespan',
  'latest_makespan',
  'min_machine_idle',
]);

const ALLOWED_LOCAL_SEARCH_OPS = new Set([
  'none',
  'insertion_ls',
  'swap_ls',
  'vnd_insert_swap',
]);

const ALLOWED_PIVOT_RULES = new Set([
  'first_improvement',
  'best_improvement',
]);

const RUN_EXPERIMENT_PY = `
import json, sys
from north_bluestar.orchestrator import (
    NorthBlueStarEngine,
    build_pfsp_problem,
    build_bin_packing_problem,
    build_graph_coloring_problem,
)
from north_bluestar.controller import (
    BaselinePortfolioStrategy,
    StructuredEnumerationStrategy,
    RandomizedSearchStrategy,
    LocalCoordinateSearchStrategy,
    OperatorRecombinationStrategy,
    SurrogateUCBStrategy,
    ProgramSynthesisStrategy,
    SearchBudget,
    SearchController,
)

payload = json.loads(sys.stdin.read())
problem_id = payload["problem_id"]
mode = payload["strategy_mode"]
budget_n = int(payload["budget"])
seed_n = int(payload["seed"])

if problem_id == "pfsp_makespan":
    prob = build_pfsp_problem(seed=seed_n)
elif problem_id == "online_bin_packing_1d":
    prob = build_bin_packing_problem(seed=seed_n)
else:
    prob = build_graph_coloring_problem(seed=seed_n)

strat_map = {
    "randomized_search": [RandomizedSearchStrategy(seed=seed_n)],
    "structured_enumeration": [StructuredEnumerationStrategy(seed=seed_n)],
    "local_coordinate_search": [LocalCoordinateSearchStrategy(seed=seed_n)],
    "operator_recombination": [StructuredEnumerationStrategy(seed=seed_n), OperatorRecombinationStrategy(seed=seed_n)],
    "surrogate_ucb": [RandomizedSearchStrategy(seed=seed_n), SurrogateUCBStrategy(seed=seed_n)],
    "north_bluestar_portfolio": [
        BaselinePortfolioStrategy(seed=seed_n),
        StructuredEnumerationStrategy(seed=seed_n),
        SurrogateUCBStrategy(seed=seed_n),
        LocalCoordinateSearchStrategy(seed=seed_n),
        OperatorRecombinationStrategy(seed=seed_n),
        ProgramSynthesisStrategy(seed=seed_n),
    ],
}

strats = strat_map.get(mode, strat_map["north_bluestar_portfolio"])
engine = NorthBlueStarEngine(problem=prob)
ctrl = SearchController(strategies=strats, budget=SearchBudget(max_evaluations=budget_n, stagnation_limit=16), seed=seed_n)
res = engine.run_discovery(ctrl, controller_mode=mode)
out = res.to_dict()
out["evidence_records"] = [r.to_dict() for r in engine.evidence.records[:30]]
print(json.dumps(out))
`;

const INSPECT_CANDIDATE_PY = `
import json, sys
from north_bluestar.candidates import (
    DeclarativePFSPConfig,
    CandidateSpec,
    BehavioralFingerprinter,
)
from north_bluestar.problem import solve_pfsp_neh, solve_pfsp_neh_ls, SplitType
from north_bluestar.orchestrator import build_pfsp_problem, NorthBlueStarEngine

payload = json.loads(sys.stdin.read())

cfg = DeclarativePFSPConfig(
    priority_rule=payload["priority_rule"],
    tie_breaker=payload["tie_breaker"],
    insertion_mode=payload["insertion_mode"],
    local_search_op=payload["local_search_op"],
    pivot_rule=payload["pivot_rule"],
    perturbation_d=int(payload["perturbation_d"]),
)
spec = CandidateSpec.from_declarative_pfsp(cfg, strategy_id="interactive_probe")
neh_bh, neh_trace = BehavioralFingerprinter.fingerprint_pfsp_solver(solve_pfsp_neh)
neh_ls_bh, neh_ls_trace = BehavioralFingerprinter.fingerprint_pfsp_solver(solve_pfsp_neh_ls)

prob = build_pfsp_problem(seed=42)
engine = NorthBlueStarEngine(problem=prob)
rep = engine.supervisor.evaluate_candidate_on_split(prob, spec, split=SplitType.DEVELOPMENT, verify_repeatability=True)

print(json.dumps({
    "candidate_id": spec.candidate_id,
    "structural_dict": cfg.to_structural_dict(),
    "canonical_dict": cfg.to_canonical_dict(),
    "structural_hash": spec.structural_hash,
    "canonical_hash": spec.canonical_hash,
    "behavioral_hash": spec.behavioral_hash,
    "behavioral_trace": [list(t) for t in (spec.behavioral_trace or [])],
    "distance_from_neh": BehavioralFingerprinter.compute_behavioral_distance(spec.behavioral_trace or [], neh_trace),
    "distance_from_neh_ls": BehavioralFingerprinter.compute_behavioral_distance(spec.behavioral_trace or [], neh_ls_trace),
    "is_redundant_pivot": (cfg.local_search_op == "none" and cfg.pivot_rule == "best_improvement"),
    "dev_evaluation": {
        "is_fully_feasible": rep.outcome.is_fully_feasible,
        "mean_objective": rep.outcome.mean_objective,
        "mean_optimality_gap_pct": rep.outcome.mean_optimality_gap_pct,
        "mean_runtime_ms": rep.outcome.mean_runtime_ms,
        "is_repeatable": rep.is_repeatable,
    }
}))
`;

// GET: read-only access to pre-built workbench snapshot (WEB-2)
export async function GET() {
  try {
    const snapPath = path.join(process.cwd(), 'public', 'north_bluestar_snapshot.json');
    try {
      const raw = await fs.readFile(snapPath, 'utf-8');
      return NextResponse.json(JSON.parse(raw));
    } catch {
      return NextResponse.json(
        {
          error:
            'Workbench snapshot not found. Generate it ahead of time via: ' +
            'python3 -m north_bluestar.cli export-workbench-snapshot --out public/north_bluestar_snapshot.json',
        },
        { status: 404 }
      );
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

// POST: validated RPC handlers with safe parameter transmission (WEB-1, WEB-3, 3.1, 3.2, 3.3)
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const action = String(body.action || 'run_experiment');

    if (action === 'run_experiment') {
      const problemId = String(body.problem_id || 'pfsp_makespan');
      if (!ALLOWED_PROBLEM_IDS.has(problemId)) {
        return NextResponse.json(
          { error: `Invalid problem_id: '${problemId}'. Allowed: ${Array.from(ALLOWED_PROBLEM_IDS).join(', ')}` },
          { status: 400 }
        );
      }

      const strategyMode = String(body.strategy_mode || 'north_bluestar_portfolio');
      if (!ALLOWED_STRATEGY_MODES.has(strategyMode)) {
        return NextResponse.json(
          { error: `Invalid strategy_mode: '${strategyMode}'. Allowed: ${Array.from(ALLOWED_STRATEGY_MODES).join(', ')}` },
          { status: 400 }
        );
      }

      // Safe bounded budget (max 24) to guarantee synchronous HTTP execution completes within 25s (3.3)
      let budget: number;
      let seed: number;
      try {
        budget = parseFiniteInteger(body.budget, 'budget', 4, 24, 16);
        seed = parseFiniteInteger(body.seed, 'seed', 0, 1000000, 42);
      } catch (err) {
        return NextResponse.json({ error: (err as Error).message }, { status: 400 });
      }

      const payload = {
        problem_id: problemId,
        strategy_mode: strategyMode,
        budget,
        seed,
      };

      const stdout = await runPythonWithStdin(RUN_EXPERIMENT_PY, payload, 25000);
      return NextResponse.json(JSON.parse(stdout));
    }

    if (action === 'inspect_candidate') {
      const priorityRule = String(body.priority_rule || 'total_time_desc');
      if (!ALLOWED_PRIORITY_RULES.has(priorityRule)) {
        return NextResponse.json(
          { error: `Invalid priority_rule: '${priorityRule}'. Allowed: ${Array.from(ALLOWED_PRIORITY_RULES).join(', ')}` },
          { status: 400 }
        );
      }

      const tieBreaker = String(body.tie_breaker || 'bottleneck_slack');
      if (!ALLOWED_TIE_BREAKERS.has(tieBreaker)) {
        return NextResponse.json(
          { error: `Invalid tie_breaker: '${tieBreaker}'. Allowed: ${Array.from(ALLOWED_TIE_BREAKERS).join(', ')}` },
          { status: 400 }
        );
      }

      const insertionMode = String(body.insertion_mode || 'earliest_makespan');
      if (!ALLOWED_INSERTION_MODES.has(insertionMode)) {
        return NextResponse.json(
          { error: `Invalid insertion_mode: '${insertionMode}'. Allowed: ${Array.from(ALLOWED_INSERTION_MODES).join(', ')}` },
          { status: 400 }
        );
      }

      const localSearchOp = String(body.local_search_op || 'vnd_insert_swap');
      if (!ALLOWED_LOCAL_SEARCH_OPS.has(localSearchOp)) {
        return NextResponse.json(
          { error: `Invalid local_search_op: '${localSearchOp}'. Allowed: ${Array.from(ALLOWED_LOCAL_SEARCH_OPS).join(', ')}` },
          { status: 400 }
        );
      }

      const pivotRule = String(body.pivot_rule || 'best_improvement');
      if (!ALLOWED_PIVOT_RULES.has(pivotRule)) {
        return NextResponse.json(
          { error: `Invalid pivot_rule: '${pivotRule}'. Allowed: ${Array.from(ALLOWED_PIVOT_RULES).join(', ')}` },
          { status: 400 }
        );
      }

      let perturbationD: number;
      try {
        perturbationD = parseFiniteInteger(body.perturbation_d, 'perturbation_d', 0, 2, 0);
      } catch (err) {
        return NextResponse.json({ error: (err as Error).message }, { status: 400 });
      }

      const payload = {
        priority_rule: priorityRule,
        tie_breaker: tieBreaker,
        insertion_mode: insertionMode,
        local_search_op: localSearchOp,
        pivot_rule: pivotRule,
        perturbation_d: perturbationD,
      };

      const stdout = await runPythonWithStdin(INSPECT_CANDIDATE_PY, payload, 15000);
      return NextResponse.json(JSON.parse(stdout));
    }

    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
