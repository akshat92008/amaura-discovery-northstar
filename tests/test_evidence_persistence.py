"""
Evidence Store Persistence & Tamper Detection Tests (P0.11, P0.12)
==================================================================
Verifies that:
1. EvidenceStore can be atomically persisted to disk and restored with verified hash chain.
2. Tampering with any field in the persisted evidence json triggers ValueError on reload.
"""

from __future__ import annotations

import json
import os
import pytest

from north_bluestar import (
    CandidateSpec,
    EvidenceStore,
    ExecutionSupervisor,
    MethodRegistry,
    NorthBlueStarEngine,
    OptimizationDirection,
    SplitType,
    build_pfsp_problem,
)


def test_evidence_atomic_save_and_restore(tmp_path):
    """P0.11: Persist and restore evidence chain across process restarts."""
    problem = build_pfsp_problem(seed=42, dev_count=3, val_count=1, holdout_count=1)
    engine = NorthBlueStarEngine(problem=problem)
    registry = MethodRegistry.create_default_registry()

    adapter = registry.get("verified_classical_and_exact")
    baselines = adapter.get_default_candidates("pfsp_makespan")
    for spec in baselines[:2]:
        rep = engine.supervisor.evaluate_candidate_on_split(
            problem, spec, split=SplitType.DEVELOPMENT, verify_repeatability=True
        )
        engine.evidence.append(spec, rep)

    save_path = str(tmp_path / "evidence_store.json")
    engine.evidence.save_to_file(save_path)
    assert os.path.exists(save_path)

    # Restore from disk
    restored = EvidenceStore.load_from_file(save_path)
    assert restored.verify_hash_chain()
    assert len(restored.records) == 2
    assert restored.records[0].record_hash == engine.evidence.records[0].record_hash
    assert restored.records[1].record_hash == engine.evidence.records[1].record_hash


def test_evidence_tamper_detection(tmp_path):
    """P0.12: Tampering with a persisted record must invalidate the hash chain."""
    problem = build_pfsp_problem(seed=42, dev_count=2, val_count=1, holdout_count=1)
    engine = NorthBlueStarEngine(problem=problem)
    registry = MethodRegistry.create_default_registry()

    adapter = registry.get("verified_classical_and_exact")
    spec = adapter.get_default_candidates("pfsp_makespan")[0]
    rep = engine.supervisor.evaluate_candidate_on_split(problem, spec, split=SplitType.DEVELOPMENT)
    engine.evidence.append(spec, rep)

    save_path = str(tmp_path / "tampered_evidence.json")
    engine.evidence.save_to_file(save_path)

    # Tamper with the objective score
    with open(save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["records"][0]["mean_objective"] = 1.0  # Fabricated score
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="TAMPERING DETECTED"):
        EvidenceStore.load_from_file(save_path)
