"""
Unit Tests for Benchmark V1 Search Arms
=======================================
Verifies that Arms A, B, C, D, and E:
1. Enforce strict proposal counts (e.g. exactly 16 proposals).
2. Produce non-empty best-so-far curves matching the budget.
3. Correctly track the champion candidate.
4. Execute deterministically given an RNG seed.
"""

import pytest
from benchmark_v1.src.domains.bin_packing import BinPackingDomain
from benchmark_v1.src.domains.graph_coloring import GraphColoringDomain
from benchmark_v1.src.domains.pfsp import PFSPDomain
from benchmark_v1.src.arms.generator import SimulatedMutator
from benchmark_v1.src.arms.arm_a_best_of_n import ArmABestOfN
from benchmark_v1.src.arms.arm_b_refinement import ArmBRefinement
from benchmark_v1.src.arms.arm_c_evolution import ArmCEvolution
from benchmark_v1.src.arms.arm_d_multi_island import ArmDMultiIsland
from benchmark_v1.src.arms.arm_e_evidence import ArmEEvidence


@pytest.mark.parametrize("domain_cls", [BinPackingDomain, GraphColoringDomain, PFSPDomain])
def test_all_arms_budget_enforcement(domain_cls):
    domain = domain_cls()
    mutator = SimulatedMutator(invalid_rate=0.0)
    seeds = domain.canonical_seeds
    budget = 12

    arms = [
        ArmABestOfN(domain, mutator),
        ArmBRefinement(domain, mutator),
        ArmCEvolution(domain, mutator, population_size=4),
        ArmDMultiIsland(domain, mutator, num_islands=2, island_size=2, migration_interval=4),
        ArmEEvidence(domain, mutator)
    ]

    for arm in arms:
        prog = arm.run_trajectory(trajectory_id=0, proposal_budget=budget, initial_seeds=seeds, rng_seed=42)
        assert prog.total_proposals == budget, f"{arm.name} produced {prog.total_proposals} instead of {budget}"
        assert len(prog.proposals_history) == budget
        assert len(prog.best_so_far_curve) == budget
        assert prog.best_candidate is not None
        assert prog.best_candidate.train_eval.is_valid
        # Monotonically non-increasing best_so_far curve
        for i in range(1, len(prog.best_so_far_curve)):
            assert prog.best_so_far_curve[i] <= prog.best_so_far_curve[i - 1] + 1e-9
