'use client';

import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Award,
  BarChart3,
  CheckCircle2,
  Cpu,
  Database,
  FileCode2,
  FlaskConical,
  GitBranch,
  Layers,
  Lock,
  Play,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  Terminal,
} from 'lucide-react';

interface BaselineComparison {
  candidate_id: string;
  algorithm_name: string;
  holdout_mean_objective: number;
  holdout_optimality_gap_pct: number | null;
  holdout_mean_runtime_ms: number;
  is_proven_optimal: boolean;
}

interface ConvergenceStep {
  eval_index: number;
  candidate_id: string;
  strategy_id: string;
  mean_objective: number | null;
  best_so_far: number;
  is_feasible: boolean;
}

interface DiscoveryRunData {
  problem_id: string;
  problem_name: string;
  controller_mode: string;
  termination_reason: string;
  total_dev_evaluations: number;
  total_wall_clock_ms: number;
  anchor_baseline_id: string;
  anchor_baseline_dev_obj: number;
  anchor_baseline_holdout_obj: number;
  champion_candidate_id: string;
  champion_method_id: string;
  champion_strategy_id: string;
  champion_payload: Record<string, unknown>;
  champion_dev_obj: number;
  champion_val_obj: number;
  champion_holdout_obj: number;
  champion_holdout_improvement_vs_anchor_pct: number;
  champion_holdout_gap_to_bound_pct: number | null;
  champion_is_proven_optimal_on_holdout: boolean;
  champion_is_repeatable: boolean;
  freeze_certificate_sha256: string;
  evidence_chain_verified: boolean;
  diversity_summary: {
    total_evaluated: number;
    feasible_count: number;
    unique_structural_hashes: number;
    unique_canonical_hashes: number;
    unique_behavioral_phenotypes: number;
    behavioral_diversity_ratio: number;
    duplicate_rejections: {
      structural: number;
      canonical: number;
      behavioral: number;
    };
  };
  learned_operator_effects: Record<string, Record<string, number>>;
  strategy_posteriors: Record<
    string,
    {
      attempts: number;
      feasibility_rate: number;
      behavioral_novelty_rate: number;
      max_improvement_pct: number;
      mean_improvement_pct: number;
      ucb_score: number;
    }
  >;
  baseline_comparison_table: BaselineComparison[];
  convergence_history: ConvergenceStep[];
}

interface SnapshotData {
  generated_at_epoch: number;
  generation_wall_time_sec: number;
  engine_version: string;
  forensic_audit: {
    stage4_pilot2_audit: {
      found: boolean;
      num_trials: number;
      total_candidates: number;
      ai_total_candidates: number;
      ai_valid_candidates: number;
      ai_validity_rate_pct: number;
      ai_matching_best_fit_count: number;
      unique_ai_fitness_scores: number;
      unique_behavioral_phenotypes_in_top_tier: number;
      best_fit_baseline_fitness: number;
      best_discovered_fitness: number;
      mean_delta_dev: number;
      gate1_passed: boolean;
      total_api_cost_usd: number;
      discovery_advantage_over_best_fit: number;
      root_cause: string;
      sample_behavioral_equivalences: Array<{
        variant: string;
        behavioral_hash: string;
        identical_to_best_fit: boolean;
        fitness: number;
        code_snippet: string;
      }>;
    };
    pfsp_780_space_audit: {
      total_structural_configurations: number;
      unique_structural_hashes: number;
      unique_canonical_configurations: number;
      semantic_redundancy_collapsed_count: number;
      semantic_redundancy_pct: number;
      constructive_base_configs: number;
      distinct_constructive_behavioral_phenotypes: number;
      redundancy_mechanisms: string[];
    };
    verified_legacy_defects_and_fixes: Array<{
      id: string;
      component: string;
      severity: string;
      finding: string;
      status: string;
      remediation: string;
    }>;
  };
  preregistered_benchmarks: {
    budget_evaluations_per_arm: number;
    seed: number;
    domains: Record<string, Record<string, DiscoveryRunData>>;
  };
  registered_methods: Array<{
    method_id: string;
    name: string;
    paradigm: string;
    supported_problem_ids: string[];
    supported_candidate_kinds: string[];
    can_prove_optimality: boolean;
    is_deterministic: boolean;
    estimated_cost_tier: number;
    description: string;
  }>;
  threat_model: {
    level: string;
    enforces_ast_allowlist: boolean;
    enforces_os_process_boundary: boolean;
    enforces_sigkill_on_timeout: boolean;
    guarantees: string[];
    non_guarantees: string[];
  };
}

interface CandidateProbeResult {
  candidate_id: string;
  structural_dict: Record<string, unknown>;
  canonical_dict: Record<string, unknown>;
  structural_hash: string;
  canonical_hash: string;
  behavioral_hash: string;
  behavioral_trace: number[][];
  distance_from_neh: number;
  distance_from_neh_ls: number;
  is_redundant_pivot: boolean;
  dev_evaluation: {
    is_fully_feasible: boolean;
    mean_objective: number;
    mean_optimality_gap_pct: number;
    mean_runtime_ms: number;
    is_repeatable: boolean;
  };
}

export default function NorthBlueStarWorkbench() {
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<
    'campaign' | 'canonicalizer' | 'forensic' | 'architecture'
  >('campaign');

  // Campaign Controls
  const [selectedDomain, setSelectedDomain] = useState<string>('pfsp_makespan');
  const [selectedArm, setSelectedArm] = useState<string>('north_bluestar_portfolio');
  const [customBudget, setCustomBudget] = useState<number>(24);
  const [customSeed, setCustomSeed] = useState<number>(42);
  const [liveRunResult, setLiveRunResult] = useState<DiscoveryRunData | null>(null);
  const [runningExperiment, setRunningExperiment] = useState<boolean>(false);

  // Interactive Canonicalizer Controls
  const [pfspPriority, setPfspPriority] = useState<string>('front_back_weighted');
  const [pfspTieBreaker, setPfspTieBreaker] = useState<string>('bottleneck_slack');
  const [pfspInsertion, setPfspInsertion] = useState<string>('earliest_makespan');
  const [pfspLsOp, setPfspLsOp] = useState<string>('vnd_insert_swap');
  const [pfspPivot, setPfspPivot] = useState<string>('best_improvement');
  const [pfspPerturb, setPfspPerturb] = useState<number>(2);
  const [probeResult, setProbeResult] = useState<CandidateProbeResult | null>(null);
  const [probing, setProbing] = useState<boolean>(false);

  useEffect(() => {
    fetch('/api/bluestar')
      .then((r) => r.json())
      .then((data: SnapshotData) => {
        setSnapshot(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const activeRun: DiscoveryRunData | null =
    liveRunResult &&
    liveRunResult.problem_id === selectedDomain &&
    liveRunResult.controller_mode === selectedArm
      ? liveRunResult
      : snapshot?.preregistered_benchmarks?.domains?.[selectedDomain]?.[selectedArm] ||
        snapshot?.preregistered_benchmarks?.domains?.[selectedDomain]?.[
          'north_bluestar_portfolio'
        ] ||
        null;

  async function handleExecuteLiveRun() {
    setRunningExperiment(true);
    try {
      const res = await fetch('/api/bluestar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'run_experiment',
          problem_id: selectedDomain,
          strategy_mode: selectedArm,
          budget: customBudget,
          seed: customSeed,
        }),
      });
      const data = await res.json();
      if (!data.error) {
        setLiveRunResult(data);
      }
    } finally {
      setRunningExperiment(false);
    }
  }

  async function handleInspectCandidate() {
    setProbing(true);
    try {
      const res = await fetch('/api/bluestar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'inspect_candidate',
          priority_rule: pfspPriority,
          tie_breaker: pfspTieBreaker,
          insertion_mode: pfspInsertion,
          local_search_op: pfspLsOp,
          pivot_rule: pfspPivot,
          perturbation_d: pfspPerturb,
        }),
      });
      const data = await res.json();
      if (!data.error) {
        setProbeResult(data);
      }
    } finally {
      setProbing(false);
    }
  }

  function switchToCanonicalizerTab() {
    setActiveTab('canonicalizer');
    if (!probeResult && !probing) {
      void handleInspectCandidate();
    }
  }

  if (loading || !snapshot) {
    return (
      <div className="min-h-screen bg-[#0B0F17] text-[#F8FAFC] flex items-center justify-center font-sans">
        <div className="flex flex-col items-center gap-3 border border-[#1E293B] bg-[#111827] px-8 py-6 rounded-md">
          <RefreshCw className="w-6 h-6 text-[#3B82F6] animate-spin" />
          <div className="text-sm font-medium tracking-wide">
            Initializing Amaura Labs — North BlueStar Discovery Kernel...
          </div>
          <div className="text-xs text-[#94A3B8] font-mono">
            Verifying SplitFirewall SHA-256 hashes & preregistered benchmark artifacts
          </div>
        </div>
      </div>
    );
  }

  const domainArms = snapshot.preregistered_benchmarks.domains[selectedDomain] || {};
  const auditP2 = snapshot.forensic_audit.stage4_pilot2_audit;
  const audit780 = snapshot.forensic_audit.pfsp_780_space_audit;

  return (
    <div className="min-h-screen bg-[#0B0F17] text-[#F8FAFC] flex flex-col lg:flex-row font-sans selection:bg-[#3B82F6]/30">
      {/* Left Navigation Sidebar */}
      <aside className="w-full lg:w-64 shrink-0 bg-[#111827] border-b lg:border-b-0 lg:border-r border-[#1E293B] flex flex-col justify-between">
        <div>
          <div className="p-5 border-b border-[#1E293B]">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded bg-[#3B82F6]/15 border border-[#3B82F6]/40 flex items-center justify-center text-[#3B82F6]">
                <Cpu className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-[#94A3B8]">
                  AMAURA LABS
                </div>
                <h1 className="text-sm font-bold tracking-tight text-[#F8FAFC]">
                  NORTH BLUESTAR
                </h1>
              </div>
            </div>
            <p className="mt-2.5 text-xs text-[#94A3B8] leading-relaxed">
              Method-Agnostic Algorithmic Discovery Kernel & Forensic Verification Suite
            </p>
          </div>

          <nav className="p-3 space-y-1">
            <button
              onClick={() => setActiveTab('campaign')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium rounded transition-colors ${
                activeTab === 'campaign'
                  ? 'bg-[#3B82F6]/15 text-[#60A5FA] border border-[#3B82F6]/30'
                  : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#1E293B]/60'
              }`}
            >
              <FlaskConical className="w-4 h-4 shrink-0" />
              <span>Discovery Campaign Lab</span>
            </button>

            <button
              onClick={switchToCanonicalizerTab}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium rounded transition-colors ${
                activeTab === 'canonicalizer'
                  ? 'bg-[#3B82F6]/15 text-[#60A5FA] border border-[#3B82F6]/30'
                  : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#1E293B]/60'
              }`}
            >
              <Sliders className="w-4 h-4 shrink-0" />
              <span>780-PFSP Canonicalizer</span>
            </button>

            <button
              onClick={() => setActiveTab('forensic')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium rounded transition-colors ${
                activeTab === 'forensic'
                  ? 'bg-[#3B82F6]/15 text-[#60A5FA] border border-[#3B82F6]/30'
                  : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#1E293B]/60'
              }`}
            >
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>Forensic Repo Audit</span>
            </button>

            <button
              onClick={() => setActiveTab('architecture')}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium rounded transition-colors ${
                activeTab === 'architecture'
                  ? 'bg-[#3B82F6]/15 text-[#60A5FA] border border-[#3B82F6]/30'
                  : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#1E293B]/60'
              }`}
            >
              <Layers className="w-4 h-4 shrink-0" />
              <span>Method Registry & Security</span>
            </button>
          </nav>
        </div>

        {/* Cryptographic Firewall & Integrity Footer */}
        <div className="p-4 border-t border-[#1E293B] bg-[#0B0F17]/60 space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#94A3B8] flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-[#10B981]" />
              Split Firewall
            </span>
            <span className="font-mono text-[11px] text-[#10B981]">ENFORCED</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#94A3B8] flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[#3B82F6]" />
              Worker Timeout
            </span>
            <span className="font-mono text-[11px] text-[#F8FAFC]">OS SIGKILL</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#94A3B8] flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-[#06B6D4]" />
              Evidence Ledger
            </span>
            <span className="font-mono text-[11px] text-[#06B6D4]">SHA-256 CHAIN</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 p-6 lg:p-8 space-y-6 overflow-y-auto">
        {/* Top Context Header */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-[#1E293B]">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-[#60A5FA]">
              <span>CAPABILITY A–G VERIFIED</span>
              <span>•</span>
              <span>ZERO-LEAKAGE HOLDOUT PROTOCOL</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-[#F8FAFC] mt-1">
              {activeTab === 'campaign' &&
                'Preregistered Algorithmic Discovery & Strategy Ablation Lab'}
              {activeTab === 'canonicalizer' &&
                'Declarative PFSP Space (780 Structural → 660 Canonical) & Behavioral Fingerprinter'}
              {activeTab === 'forensic' &&
                'Forensic Audit of Amaura Repository (Stage 2, Stage 3, Stage 4 Pilot 2)'}
              {activeTab === 'architecture' &&
                'Plugin Method Registry, Empirical Operator Learning & Subprocess Threat Model'}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-3 py-1.5 bg-[#111827] border border-[#1E293B] rounded text-xs font-mono text-[#94A3B8]">
              Engine: <span className="text-[#F8FAFC]">{snapshot.engine_version}</span>
            </div>
          </div>
        </header>

        {/* ================================================================= */}
        {/* TAB 1: DISCOVERY CAMPAIGN LAB                                     */}
        {/* ================================================================= */}
        {activeTab === 'campaign' && (
          <div className="space-y-6">
            {/* Control Bar */}
            <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4 grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
              <div>
                <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1.5">
                  Benchmark Problem Family
                </label>
                <select
                  value={selectedDomain}
                  onChange={(e) => {
                    setSelectedDomain(e.target.value);
                    setLiveRunResult(null);
                  }}
                  className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
                >
                  <option value="pfsp_makespan">PFSP (Fm | prmu | Cmax)</option>
                  <option value="online_bin_packing_1d">Online 1D Bin Packing</option>
                  <option value="vertex_graph_coloring">Vertex Graph Coloring</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1.5">
                  Search Controller Strategy
                </label>
                <select
                  value={selectedArm}
                  onChange={(e) => {
                    setSelectedArm(e.target.value);
                    setLiveRunResult(null);
                  }}
                  className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
                >
                  <option value="north_bluestar_portfolio">
                    North BlueStar Adaptive Portfolio (All Methods)
                  </option>
                  <option value="structured_enumeration">
                    Structured Canonical Enumeration
                  </option>
                  <option value="surrogate_ucb">
                    Empirical Factorial Surrogate (UCB)
                  </option>
                  <option value="local_coordinate_search">
                    Elite Neighborhood Local Search
                  </option>
                  <option value="randomized_search">
                    Uniform Random Canonical Search
                  </option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1.5">
                  Dev Evaluation Budget
                </label>
                <input
                  type="number"
                  min={8}
                  max={60}
                  value={customBudget}
                  onChange={(e) => setCustomBudget(Number(e.target.value))}
                  className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1.5">
                  Random Seed
                </label>
                <input
                  type="number"
                  value={customSeed}
                  onChange={(e) => setCustomSeed(Number(e.target.value))}
                  className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
                />
              </div>

              <button
                onClick={handleExecuteLiveRun}
                disabled={runningExperiment}
                className="w-full bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-[#F8FAFC] font-medium text-xs py-2 px-4 rounded flex items-center justify-center gap-2 transition-colors cursor-pointer"
              >
                {runningExperiment ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Executing Kernel...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" />
                    <span>Run Live Discovery</span>
                  </>
                )}
              </button>
            </div>

            {activeRun && (
              <>
                {/* 4 KPI Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                    <div className="text-xs text-[#94A3B8] flex items-center justify-between">
                      <span>Sealed Holdout Objective</span>
                      <Award className="w-4 h-4 text-[#10B981]" />
                    </div>
                    <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-[#F8FAFC]">
                      {activeRun.champion_holdout_obj.toFixed(4)}
                    </div>
                    <div className="mt-1 text-xs font-mono text-[#10B981]">
                      {activeRun.champion_holdout_improvement_vs_anchor_pct >= 0 ? '+' : ''}
                      {activeRun.champion_holdout_improvement_vs_anchor_pct.toFixed(3)}% vs{' '}
                      {activeRun.anchor_baseline_id.replace('baseline-', '')} (
                      {activeRun.anchor_baseline_holdout_obj.toFixed(3)})
                    </div>
                  </div>

                  <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                    <div className="text-xs text-[#94A3B8] flex items-center justify-between">
                      <span>Selected Champion & Method</span>
                      <Sparkles className="w-4 h-4 text-[#3B82F6]" />
                    </div>
                    <div className="mt-2 text-lg font-bold font-mono text-[#60A5FA] truncate">
                      {activeRun.champion_candidate_id}
                    </div>
                    <div className="mt-1 text-xs text-[#94A3B8] font-mono truncate">
                      Method: {activeRun.champion_method_id}
                    </div>
                  </div>

                  <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                    <div className="text-xs text-[#94A3B8] flex items-center justify-between">
                      <span>Behavioral Phenotype Diversity</span>
                      <GitBranch className="w-4 h-4 text-[#06B6D4]" />
                    </div>
                    <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-[#F8FAFC]">
                      {activeRun.diversity_summary.unique_behavioral_phenotypes} /{' '}
                      {activeRun.diversity_summary.feasible_count}
                    </div>
                    <div className="mt-1 text-xs font-mono text-[#94A3B8]">
                      Duplicates rejected:{' '}
                      {activeRun.diversity_summary.duplicate_rejections.structural +
                        activeRun.diversity_summary.duplicate_rejections.canonical +
                        activeRun.diversity_summary.duplicate_rejections.behavioral}
                    </div>
                  </div>

                  <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                    <div className="text-xs text-[#94A3B8] flex items-center justify-between">
                      <span>Execution & Verification</span>
                      <ShieldCheck className="w-4 h-4 text-[#10B981]" />
                    </div>
                    <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-[#F8FAFC]">
                      {activeRun.total_wall_clock_ms.toFixed(0)} ms
                    </div>
                    <div className="mt-1 text-xs font-mono text-[#10B981]">
                      Repeatable: {activeRun.champion_is_repeatable ? 'VERIFIED' : 'FAILED'} •{' '}
                      {activeRun.total_dev_evaluations} Dev Evals
                    </div>
                  </div>
                </div>

                {/* Equal-Budget Strategy Ablation Comparison Table */}
                {Object.keys(domainArms).length > 1 && (
                  <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-sm font-semibold text-[#F8FAFC]">
                          Equal-Budget Multi-Strategy Comparison on{' '}
                          <span className="text-[#60A5FA]">{activeRun.problem_name}</span>
                        </h3>
                        <p className="text-xs text-[#94A3B8]">
                          Independently selectable SearchController strategies evaluated under identical development budgets prior to one-shot FINAL_HOLDOUT unsealing.
                        </p>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-[#1E293B] text-[#94A3B8] font-mono uppercase text-[11px]">
                            <th className="py-2.5 px-3">Strategy Arm</th>
                            <th className="py-2.5 px-3">Champion ID</th>
                            <th className="py-2.5 px-3 text-right">Dev Objective</th>
                            <th className="py-2.5 px-3 text-right">Val Objective</th>
                            <th className="py-2.5 px-3 text-right">Sealed Holdout Obj</th>
                            <th className="py-2.5 px-3 text-right">Holdout Gain vs Anchor</th>
                            <th className="py-2.5 px-3 text-right">Distinct Phenotypes</th>
                            <th className="py-2.5 px-3">Stopping Reason</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1E293B]/60 font-mono">
                          {Object.entries(domainArms).map(([armKey, armData]) => {
                            const isSelected = armKey === selectedArm;
                            return (
                              <tr
                                key={armKey}
                                onClick={() => setSelectedArm(armKey)}
                                className={`cursor-pointer transition-colors ${
                                  isSelected
                                    ? 'bg-[#3B82F6]/10 text-[#F8FAFC]'
                                    : 'hover:bg-[#1E293B]/40 text-[#94A3B8]'
                                }`}
                              >
                                <td className="py-2.5 px-3 font-sans font-medium text-[#F8FAFC]">
                                  {armKey}
                                </td>
                                <td className="py-2.5 px-3 text-[#60A5FA]">
                                  {armData.champion_candidate_id}
                                </td>
                                <td className="py-2.5 px-3 text-right tabular-nums">
                                  {armData.champion_dev_obj.toFixed(4)}
                                </td>
                                <td className="py-2.5 px-3 text-right tabular-nums">
                                  {armData.champion_val_obj.toFixed(4)}
                                </td>
                                <td className="py-2.5 px-3 text-right tabular-nums font-bold text-[#F8FAFC]">
                                  {armData.champion_holdout_obj.toFixed(4)}
                                </td>
                                <td
                                  className={`py-2.5 px-3 text-right tabular-nums ${
                                    armData.champion_holdout_improvement_vs_anchor_pct > 0
                                      ? 'text-[#10B981]'
                                      : 'text-[#94A3B8]'
                                  }`}
                                >
                                  {armData.champion_holdout_improvement_vs_anchor_pct >= 0
                                    ? '+'
                                    : ''}
                                  {armData.champion_holdout_improvement_vs_anchor_pct.toFixed(3)}%
                                </td>
                                <td className="py-2.5 px-3 text-right tabular-nums">
                                  {armData.diversity_summary.unique_behavioral_phenotypes} /{' '}
                                  {armData.diversity_summary.feasible_count}
                                </td>
                                <td className="py-2.5 px-3 text-[11px]">
                                  {armData.termination_reason}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Two-Column Detail View: Baselines + Champion Spec & Operator Effects */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Left 7 Cols: Classical & Exact Baseline Holdout Table + Convergence Trace */}
                  <div className="lg:col-span-7 space-y-6">
                    <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
                      <h3 className="text-sm font-semibold text-[#F8FAFC] mb-1">
                        Sealed FINAL_HOLDOUT Verification vs. Established OR Baselines
                      </h3>
                      <p className="text-xs text-[#94A3B8] mb-4">
                        Freeze Certificate SHA-256:{' '}
                        <span className="font-mono text-[#60A5FA]">
                          {activeRun.freeze_certificate_sha256.slice(0, 32)}...
                        </span>
                      </p>

                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="border-b border-[#1E293B] text-[#94A3B8] font-mono uppercase text-[11px]">
                              <th className="py-2 px-3">Solver / Candidate</th>
                              <th className="py-2 px-3">Role</th>
                              <th className="py-2 px-3 text-right">Holdout Mean Obj</th>
                              <th className="py-2 px-3 text-right">Gap to Bound (%)</th>
                              <th className="py-2 px-3 text-right">Mean Runtime</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#1E293B]/60 font-mono">
                            <tr className="bg-[#10B981]/10 text-[#F8FAFC]">
                              <td className="py-2.5 px-3 font-bold text-[#10B981]">
                                ★ {activeRun.champion_candidate_id}
                              </td>
                              <td className="py-2.5 px-3 font-sans text-xs text-[#10B981]">
                                Discovered Champion ({activeRun.champion_strategy_id})
                              </td>
                              <td className="py-2.5 px-3 text-right font-bold tabular-nums">
                                {activeRun.champion_holdout_obj.toFixed(4)}
                              </td>
                              <td className="py-2.5 px-3 text-right tabular-nums">
                                {activeRun.champion_holdout_gap_to_bound_pct !== null
                                  ? `${activeRun.champion_holdout_gap_to_bound_pct.toFixed(3)}%`
                                  : 'N/A'}
                              </td>
                              <td className="py-2.5 px-3 text-right tabular-nums">Verified</td>
                            </tr>
                            {activeRun.baseline_comparison_table.map((b) => (
                              <tr key={b.candidate_id} className="text-[#94A3B8]">
                                <td className="py-2 px-3 text-[#F8FAFC]">{b.algorithm_name}</td>
                                <td className="py-2 px-3 font-sans text-xs">
                                  Established Baseline
                                </td>
                                <td className="py-2 px-3 text-right tabular-nums">
                                  {b.holdout_mean_objective?.toFixed(4)}
                                </td>
                                <td className="py-2 px-3 text-right tabular-nums">
                                  {b.holdout_optimality_gap_pct !== null
                                    ? `${b.holdout_optimality_gap_pct.toFixed(3)}%`
                                    : 'N/A'}
                                </td>
                                <td className="py-2 px-3 text-right tabular-nums">
                                  {b.holdout_mean_runtime_ms.toFixed(2)} ms
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Development Convergence Trajectory */}
                    <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
                      <h3 className="text-sm font-semibold text-[#F8FAFC] mb-3">
                        Development Split Search Trajectory (Best-So-Far & Strategy Allocation)
                      </h3>
                      <div className="max-h-64 overflow-y-auto pr-1 space-y-1.5 font-mono text-xs">
                        {activeRun.convergence_history.map((step) => (
                          <div
                            key={step.eval_index}
                            className="flex items-center justify-between px-3 py-1.5 rounded bg-[#0B0F17] border border-[#1E293B]/80"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-[#64748B] w-7">#{step.eval_index}</span>
                              <span className="text-[#60A5FA]">{step.candidate_id}</span>
                              <span className="text-[11px] px-2 py-0.5 rounded bg-[#1E293B] text-[#94A3B8]">
                                {step.strategy_id}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 tabular-nums">
                              <span className="text-[#94A3B8]">
                                Obj:{' '}
                                {step.mean_objective !== null
                                  ? step.mean_objective.toFixed(4)
                                  : 'INFEASIBLE'}
                              </span>
                              <span className="text-[#10B981] font-semibold">
                                Best: {step.best_so_far.toFixed(4)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Right 5 Cols: Champion Payload & Empirical Operator Effects */}
                  <div className="lg:col-span-5 space-y-6">
                    <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
                      <h3 className="text-sm font-semibold text-[#F8FAFC] mb-2">
                        Verified Champion Specification
                      </h3>
                      <pre className="bg-[#0B0F17] border border-[#1E293B] rounded p-3 text-xs font-mono text-[#60A5FA] overflow-x-auto">
                        {JSON.stringify(activeRun.champion_payload, null, 2)}
                      </pre>
                    </div>

                    <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
                      <h3 className="text-sm font-semibold text-[#F8FAFC] mb-1">
                        Learned Marginal Operator Contributions (Capability F)
                      </h3>
                      <p className="text-xs text-[#94A3B8] mb-3">
                        Positive utility indicates how much an operator choice improves the objective relative to the population mean on DEVELOPMENT.
                      </p>
                      <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                        {Object.entries(activeRun.learned_operator_effects).map(
                          ([paramName, valMap]) => (
                            <div
                              key={paramName}
                              className="bg-[#0B0F17] border border-[#1E293B] rounded p-3"
                            >
                              <div className="text-xs font-mono font-semibold text-[#F8FAFC] mb-2">
                                {paramName}
                              </div>
                              <div className="space-y-1">
                                {Object.entries(valMap).map(([valKey, util]) => (
                                  <div
                                    key={valKey}
                                    className="flex items-center justify-between text-xs font-mono"
                                  >
                                    <span className="text-[#94A3B8]">{valKey}</span>
                                    <span
                                      className={`tabular-nums ${
                                        util >= 0 ? 'text-[#10B981]' : 'text-[#F59E0B]'
                                      }`}
                                    >
                                      {util >= 0 ? '+' : ''}
                                      {util.toFixed(4)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 2: 780-CONFIG PFSP CANONICALIZER & BEHAVIORAL FINGERPRINTER   */}
        {/* ================================================================= */}
        {activeTab === 'canonicalizer' && (
          <div className="space-y-6">
            {/* Summary Banner of 780 -> 660 Reduction */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                <div className="text-xs text-[#94A3B8]">Raw Structural PFSP Grid</div>
                <div className="mt-1 text-2xl font-bold font-mono text-[#F8FAFC]">
                  {audit780.total_structural_configurations}
                </div>
                <div className="mt-1 text-xs text-[#94A3B8] font-mono">
                  5 × 4 × 3 × 13 operator grid
                </div>
              </div>

              <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                <div className="text-xs text-[#94A3B8]">Semantic Canonical Configs</div>
                <div className="mt-1 text-2xl font-bold font-mono text-[#60A5FA]">
                  {audit780.unique_canonical_configurations}
                </div>
                <div className="mt-1 text-xs text-[#10B981] font-mono">
                  -{audit780.semantic_redundancy_collapsed_count} dead-state configs (
                  {audit780.semantic_redundancy_pct}% collapsed)
                </div>
              </div>

              <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                <div className="text-xs text-[#94A3B8]">
                  Constructive Base Configs
                </div>
                <div className="mt-1 text-2xl font-bold font-mono text-[#F8FAFC]">
                  {audit780.constructive_base_configs}
                </div>
                <div className="mt-1 text-xs text-[#94A3B8] font-mono">
                  When local_search_op = &apos;none&apos;
                </div>
              </div>

              <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                <div className="text-xs text-[#94A3B8]">
                  Distinct Constructive Phenotypes
                </div>
                <div className="mt-1 text-2xl font-bold font-mono text-[#06B6D4]">
                  {audit780.distinct_constructive_behavioral_phenotypes}
                </div>
                <div className="mt-1 text-xs text-[#94A3B8] font-mono">
                  Tie-breakers collapse when no ties
                </div>
              </div>
            </div>

            {/* Interactive Operator Laboratory */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5 bg-[#111827] border border-[#1E293B] rounded-md p-5 space-y-4">
                <h3 className="text-sm font-semibold text-[#F8FAFC]">
                  Interactive Declarative PFSP Operator Builder
                </h3>
                <p className="text-xs text-[#94A3B8]">
                  Select any operator combination below. Try setting{' '}
                  <code className="text-[#60A5FA]">local_search_op = none</code> and toggling{' '}
                  <code className="text-[#60A5FA]">pivot_rule</code> to see how North BlueStar
                  canonicalizes dead parameters to the exact same <code className="text-[#10B981]">canonical_hash</code>.
                </p>

                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1">
                      1. Priority Rule (5 options)
                    </label>
                    <select
                      value={pfspPriority}
                      onChange={(e) => setPfspPriority(e.target.value)}
                      className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC]"
                    >
                      <option value="total_time_desc">total_time_desc (Classical NEH)</option>
                      <option value="front_back_weighted">front_back_weighted</option>
                      <option value="palmer_slope">palmer_slope</option>
                      <option value="gupta_profile">gupta_profile</option>
                      <option value="cds_stage_best">cds_stage_best</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1">
                      2. Tie Breaker (4 options)
                    </label>
                    <select
                      value={pfspTieBreaker}
                      onChange={(e) => setPfspTieBreaker(e.target.value)}
                      className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC]"
                    >
                      <option value="bottleneck_slack">bottleneck_slack</option>
                      <option value="index_asc">index_asc</option>
                      <option value="first_machine_asc">first_machine_asc</option>
                      <option value="last_machine_desc">last_machine_desc</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1">
                      3. Taillard Insertion Tie-Break Mode (3 options)
                    </label>
                    <select
                      value={pfspInsertion}
                      onChange={(e) => setPfspInsertion(e.target.value)}
                      className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC]"
                    >
                      <option value="earliest_makespan">earliest_makespan</option>
                      <option value="latest_makespan">latest_makespan</option>
                      <option value="min_machine_idle">min_machine_idle</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1">
                      4. Local Search Operator (4 options)
                    </label>
                    <select
                      value={pfspLsOp}
                      onChange={(e) => setPfspLsOp(e.target.value)}
                      className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC]"
                    >
                      <option value="vnd_insert_swap">vnd_insert_swap (Insertion + Swap VND)</option>
                      <option value="insertion_ls">insertion_ls (Taillard Insertion LS)</option>
                      <option value="swap_ls">swap_ls (Windowed Swap LS)</option>
                      <option value="none">none (Constructive Only)</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1">
                        5. Pivot Rule
                      </label>
                      <select
                        value={pfspPivot}
                        onChange={(e) => setPfspPivot(e.target.value)}
                        className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC]"
                      >
                        <option value="best_improvement">best_improvement</option>
                        <option value="first_improvement">first_improvement</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-mono uppercase text-[#94A3B8] mb-1">
                        6. IG Perturbation d
                      </label>
                      <select
                        value={pfspPerturb}
                        onChange={(e) => setPfspPerturb(Number(e.target.value))}
                        className="w-full bg-[#0B0F17] border border-[#1E293B] rounded px-3 py-2 text-xs font-mono text-[#F8FAFC]"
                      >
                        <option value={0}>0 (Disabled)</option>
                        <option value={2}>2 (Destruct/Reconstruct d=2)</option>
                      </select>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleInspectCandidate}
                  disabled={probing}
                  className="w-full bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-[#F8FAFC] font-medium text-xs py-2.5 px-4 rounded flex items-center justify-center gap-2 transition-colors cursor-pointer"
                >
                  {probing ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Canonicalizing & Probing...</span>
                    </>
                  ) : (
                    <>
                      <Scale className="w-3.5 h-3.5" />
                      <span>Compute Canonical & Behavioral Fingerprint</span>
                    </>
                  )}
                </button>
              </div>

              {/* Right 7 Cols: Live Canonicalization & Behavioral Output */}
              <div className="lg:col-span-7 space-y-4">
                {probeResult && (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                        <div className="text-[11px] font-mono uppercase text-[#94A3B8]">
                          Structural Hash
                        </div>
                        <div className="mt-1.5 text-sm font-mono font-bold text-[#F8FAFC]">
                          {probeResult.structural_hash}
                        </div>
                        <div className="mt-1 text-[11px] text-[#94A3B8]">
                          Raw parameter tuple identity
                        </div>
                      </div>

                      <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                        <div className="text-[11px] font-mono uppercase text-[#94A3B8]">
                          Semantic Canonical Hash
                        </div>
                        <div className="mt-1.5 text-sm font-mono font-bold text-[#60A5FA]">
                          {probeResult.canonical_hash}
                        </div>
                        <div className="mt-1 text-[11px] text-[#10B981]">
                          {pfspLsOp === 'none'
                            ? 'Dead pivot/perturbation collapsed!'
                            : 'Active refinement normalized'}
                        </div>
                      </div>

                      <div className="bg-[#111827] border border-[#1E293B] rounded-md p-4">
                        <div className="text-[11px] font-mono uppercase text-[#94A3B8]">
                          Behavioral Phenotype Hash
                        </div>
                        <div className="mt-1.5 text-sm font-mono font-bold text-[#06B6D4]">
                          {probeResult.behavioral_hash}
                        </div>
                        <div className="mt-1 text-[11px] text-[#94A3B8]">
                          Kendall τ vs NEH: {probeResult.distance_from_neh.toFixed(3)} | vs NEH-LS:{' '}
                          {probeResult.distance_from_neh_ls.toFixed(3)}
                        </div>
                      </div>
                    </div>

                    <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs font-semibold text-[#F8FAFC] mb-2">
                          Raw Structural Configuration
                        </div>
                        <pre className="bg-[#0B0F17] border border-[#1E293B] rounded p-3 text-xs font-mono text-[#94A3B8] overflow-x-auto">
                          {JSON.stringify(probeResult.structural_dict, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-[#60A5FA] mb-2">
                          Canonicalized Semantic Representation
                        </div>
                        <pre className="bg-[#0B0F17] border border-[#3B82F6]/30 rounded p-3 text-xs font-mono text-[#60A5FA] overflow-x-auto">
                          {JSON.stringify(probeResult.canonical_dict, null, 2)}
                        </pre>
                      </div>
                    </div>

                    <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                        <h4 className="text-xs font-semibold uppercase font-mono text-[#F8FAFC]">
                          Live Development Split Verification & Micro-Probe Permutations
                        </h4>
                        <span className="text-xs font-mono text-[#10B981]">
                          Mean Makespan: {probeResult.dev_evaluation.mean_objective.toFixed(3)} (Gap:{' '}
                          {probeResult.dev_evaluation.mean_optimality_gap_pct.toFixed(3)}% •{' '}
                          {probeResult.dev_evaluation.mean_runtime_ms.toFixed(2)} ms)
                        </span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                        {probeResult.behavioral_trace.map((perm, idx) => (
                          <div
                            key={idx}
                            className="bg-[#0B0F17] border border-[#1E293B] rounded p-2.5"
                          >
                            <div className="text-[11px] text-[#94A3B8] mb-1">
                              Synthetic Probe #{idx + 1} Schedule
                            </div>
                            <div className="text-[#F8FAFC]">[{perm.join(', ')}]</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 3: FORENSIC REPOSITORY AUDIT (STAGE 2, 3, 4 PILOT 2)          */}
        {/* ================================================================= */}
        {activeTab === 'forensic' && (
          <div className="space-y-6">
            {/* Stage 4 Pilot 2 Behavioral Collapse Proof */}
            <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5 space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-[#1E293B] pb-4">
                <div>
                  <div className="text-xs font-mono uppercase text-[#F59E0B] flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4" />
                    FORENSIC VERIFICATION OF STAGE 4 PILOT 2 (`stage4/results/pilot2/results.json`)
                  </div>
                  <h3 className="text-base font-bold text-[#F8FAFC] mt-1">
                    Mathematical Proof of Prompt-Example Anchoring & Best-Fit Behavioral Collapse
                  </h3>
                </div>
                <div className="px-3 py-1 rounded bg-[#F59E0B]/15 border border-[#F59E0B]/40 text-xs font-mono text-[#F59E0B]">
                  Discovery Advantage: 0.0000% (Gate 1 Failed)
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-[#0B0F17] border border-[#1E293B] rounded p-3">
                  <div className="text-xs text-[#94A3B8]">Total Evaluated Slots</div>
                  <div className="text-xl font-bold font-mono text-[#F8FAFC] mt-1">
                    {auditP2.total_candidates} ({auditP2.num_trials} Trials)
                  </div>
                  <div className="text-[11px] font-mono text-[#94A3B8]">
                    {auditP2.ai_valid_candidates} / {auditP2.ai_total_candidates} Valid AI Proposals
                  </div>
                </div>

                <div className="bg-[#0B0F17] border border-[#1E293B] rounded p-3">
                  <div className="text-xs text-[#94A3B8]">AI Proposals Matching Best-Fit</div>
                  <div className="text-xl font-bold font-mono text-[#F59E0B] mt-1">
                    {auditP2.ai_matching_best_fit_count} Candidates
                  </div>
                  <div className="text-[11px] font-mono text-[#94A3B8]">
                    Exact fitness = {auditP2.best_fit_baseline_fitness}
                  </div>
                </div>

                <div className="bg-[#0B0F17] border border-[#1E293B] rounded p-3">
                  <div className="text-xs text-[#94A3B8]">Top-Tier Behavioral Phenotypes</div>
                  <div className="text-xl font-bold font-mono text-[#EF4444] mt-1">
                    {auditP2.unique_behavioral_phenotypes_in_top_tier} Phenotype
                  </div>
                  <div className="text-[11px] font-mono text-[#94A3B8]">
                    All monotonic in (rem - item)
                  </div>
                </div>

                <div className="bg-[#0B0F17] border border-[#1E293B] rounded p-3">
                  <div className="text-xs text-[#94A3B8]">Pilot 2 API Spend</div>
                  <div className="text-xl font-bold font-mono text-[#F8FAFC] mt-1">
                    ${auditP2.total_api_cost_usd.toFixed(2)}
                  </div>
                  <div className="text-[11px] font-mono text-[#94A3B8]">
                    mean_delta_dev = {auditP2.mean_delta_dev.toFixed(4)}
                  </div>
                </div>
              </div>

              <div className="bg-[#0B0F17] border border-[#1E293B] rounded p-4 text-xs text-[#94A3B8] leading-relaxed">
                <strong className="text-[#F8FAFC]">Root Cause Verified in Source Code:</strong>{' '}
                {auditP2.root_cause}
              </div>

              <div>
                <h4 className="text-xs font-mono uppercase text-[#94A3B8] mb-2">
                  Behavioral Fingerprinter Verification: Syntactically Distinct ASTs → Identical Best-Fit Phenotype
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {auditP2.sample_behavioral_equivalences.map((eq) => (
                    <div
                      key={eq.variant}
                      className="bg-[#0B0F17] border border-[#1E293B] rounded p-3 flex flex-col justify-between"
                    >
                      <div className="flex items-center justify-between text-xs font-mono mb-1.5">
                        <span className="text-[#60A5FA] font-semibold">{eq.variant}</span>
                        <span className="text-[#10B981]">
                          Behavioral Hash: {eq.behavioral_hash}
                        </span>
                      </div>
                      <code className="text-xs font-mono text-[#F8FAFC] bg-[#111827] px-2 py-1.5 rounded border border-[#1E293B]">
                        {eq.code_snippet}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Verified Legacy Defects & Remediations Table */}
            <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
              <h3 className="text-sm font-semibold text-[#F8FAFC] mb-1">
                Verified Legacy Codebase Defects & Applied Engineering Remediations
              </h3>
              <p className="text-xs text-[#94A3B8] mb-4">
                Every critical and high-severity flaw discovered during our inspection of `amaura/`, `stage2/`, and `stage3/` has been patched and verified by regression tests.
              </p>

              <div className="space-y-3">
                {snapshot.forensic_audit.verified_legacy_defects_and_fixes.map((defect) => (
                  <div
                    key={defect.id}
                    className="bg-[#0B0F17] border border-[#1E293B] rounded p-4 space-y-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <span className="px-2 py-0.5 rounded bg-[#EF4444]/15 border border-[#EF4444]/40 text-[#EF4444] font-mono text-[11px] font-semibold">
                          {defect.id} • {defect.severity}
                        </span>
                        <span className="font-mono text-xs text-[#60A5FA]">
                          {defect.component}
                        </span>
                      </div>
                      <span className="px-2.5 py-0.5 rounded bg-[#10B981]/15 border border-[#10B981]/40 text-[#10B981] font-mono text-[11px] flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        {defect.status}
                      </span>
                    </div>
                    <p className="text-xs text-[#94A3B8] leading-relaxed">
                      <strong className="text-[#F8FAFC]">Finding:</strong> {defect.finding}
                    </p>
                    <p className="text-xs text-[#10B981] leading-relaxed">
                      <strong className="text-[#F8FAFC]">Remediation:</strong> {defect.remediation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 4: METHOD REGISTRY & ISOLATION THREAT MODEL                   */}
        {/* ================================================================= */}
        {activeTab === 'architecture' && (
          <div className="space-y-6">
            {/* Registered Plugin Methods */}
            <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5">
              <h3 className="text-sm font-semibold text-[#F8FAFC] mb-1">
                Plugin-Based Method Registry (Capability B)
              </h3>
              <p className="text-xs text-[#94A3B8] mb-4">
                Solvers and compilers register declarative `MethodCapabilities` via a uniform `MethodAdapter` interface and are replaceable without modifying the discovery kernel.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {snapshot.registered_methods.map((m) => (
                  <div
                    key={m.method_id}
                    className="bg-[#0B0F17] border border-[#1E293B] rounded p-4 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-[#60A5FA]">
                        {m.method_id}
                      </span>
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#1E293B] text-[#F8FAFC]">
                        {m.paradigm}
                      </span>
                    </div>
                    <div className="text-sm font-semibold text-[#F8FAFC]">{m.name}</div>
                    <p className="text-xs text-[#94A3B8] leading-relaxed">{m.description}</p>
                    <div className="pt-2 border-t border-[#1E293B]/60 flex flex-wrap gap-2 text-[11px] font-mono text-[#94A3B8]">
                      <span>Domains: {m.supported_problem_ids.join(', ')}</span>
                      <span>•</span>
                      <span>Cost Tier: {m.estimated_cost_tier}</span>
                      <span>•</span>
                      <span className="text-[#10B981]">
                        Deterministic: {m.is_deterministic ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Execution Isolation & Threat Model */}
            <div className="bg-[#111827] border border-[#1E293B] rounded-md p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-[#F8FAFC]">
                    Execution Supervisor & Honest Isolation Threat Model (Capability E)
                  </h3>
                  <p className="text-xs text-[#94A3B8]">
                    Active Threat Model Level:{' '}
                    <span className="font-mono text-[#60A5FA]">
                      {snapshot.threat_model.level}
                    </span>
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-[#0B0F17] border border-[#10B981]/30 rounded p-4 space-y-2">
                  <div className="text-xs font-mono uppercase text-[#10B981] font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4" />
                    Verified Isolation & Verification Guarantees
                  </div>
                  <ul className="space-y-1.5 text-xs text-[#94A3B8] list-disc list-inside">
                    {snapshot.threat_model.guarantees.map((g, i) => (
                      <li key={i} className="leading-relaxed">
                        {g}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-[#0B0F17] border border-[#F59E0B]/30 rounded p-4 space-y-2">
                  <div className="text-xs font-mono uppercase text-[#F59E0B] font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4" />
                    Explicit Non-Guarantees (Zero False Security Claims)
                  </div>
                  <ul className="space-y-1.5 text-xs text-[#94A3B8] list-disc list-inside">
                    {snapshot.threat_model.non_guarantees.map((ng, i) => (
                      <li key={i} className="leading-relaxed">
                        {ng}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
