import { NextRequest, NextResponse } from 'next/server';
import { execFile } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';

const execFileAsync = promisify(execFile);

export async function GET() {
  try {
    const snapPath = path.join(process.cwd(), 'public', 'north_bluestar_snapshot.json');
    try {
      const raw = await fs.readFile(snapPath, 'utf-8');
      return NextResponse.json(JSON.parse(raw));
    } catch {
      await execFileAsync('python3', [
        '-m',
        'north_bluestar.cli',
        'export-workbench-snapshot',
        '--out',
        snapPath,
        '--budget',
        '24',
      ]);
      const raw = await fs.readFile(snapPath, 'utf-8');
      return NextResponse.json(JSON.parse(raw));
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const action = body.action || 'run_experiment';

    if (action === 'run_experiment') {
      const problemId = String(body.problem_id || 'pfsp_makespan');
      const strategyMode = String(body.strategy_mode || 'north_bluestar_portfolio');
      const budget = Math.min(60, Math.max(6, Number(body.budget || 20)));
      const seed = Number(body.seed || 42);

      const pyScript = `
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

problem_id = ${JSON.stringify(problemId)}
mode = ${JSON.stringify(strategyMode)}
budget_n = int(${budget})
seed_n = int(${seed})

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
      const { stdout } = await execFileAsync('python3', ['-c', pyScript], {
        cwd: process.cwd(),
        timeout: 25000,
      });
      return NextResponse.json(JSON.parse(stdout.trim()));
    }

    if (action === 'inspect_candidate') {
      const priorityRule = String(body.priority_rule || 'total_time_desc');
      const tieBreaker = String(body.tie_breaker || 'bottleneck_slack');
      const insertionMode = String(body.insertion_mode || 'earliest_makespan');
      const localSearchOp = String(body.local_search_op || 'vnd_insert_swap');
      const pivotRule = String(body.pivot_rule || 'best_improvement');
      const perturbationD = Number(body.perturbation_d ?? 2);

      const pyScript = `
import json
from north_bluestar.candidates import (
    DeclarativePFSPConfig,
    CandidateSpec,
    BehavioralFingerprinter,
)
from north_bluestar.problem import solve_pfsp_neh, solve_pfsp_neh_ls, SplitType
from north_bluestar.orchestrator import build_pfsp_problem, NorthBlueStarEngine

cfg = DeclarativePFSPConfig(
    priority_rule=${JSON.stringify(priorityRule)},
    tie_breaker=${JSON.stringify(tieBreaker)},
    insertion_mode=${JSON.stringify(insertionMode)},
    local_search_op=${JSON.stringify(localSearchOp)},
    pivot_rule=${JSON.stringify(pivotRule)},
    perturbation_d=int(${perturbationD}),
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
      const { stdout } = await execFileAsync('python3', ['-c', pyScript], {
        cwd: process.cwd(),
        timeout: 15000,
      });
      return NextResponse.json(JSON.parse(stdout.trim()));
    }

    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
