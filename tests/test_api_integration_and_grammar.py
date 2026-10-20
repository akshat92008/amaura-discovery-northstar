"""
API Search Grammar Alignment, Numeric Validation & Evidence Crash Recovery Suite (3.1, 3.2, 3.3, Section 4).
"""
import json
import os
import tempfile
import pytest

from north_bluestar.candidates import (
    PFSP_PRIORITY_RULES,
    PFSP_TIE_BREAKERS,
    PFSP_INSERTION_MODES,
    PFSP_LOCAL_SEARCH_OPS,
    PFSP_PIVOT_RULES,
    DeclarativePFSPConfig,
    CandidateSpec,
)
from north_bluestar.evidence import EvidenceRecord, EvidenceStore
from north_bluestar.problem import OptimizationDirection


def test_api_route_grammar_matches_engine_canonical_constants():
    """3.1: Verify route.ts static allowlists match Python DeclarativePFSPConfig constants."""
    route_path = os.path.join(os.path.dirname(__file__), "..", "app", "api", "bluestar", "route.ts")
    assert os.path.exists(route_path), "route.ts must exist"
    content = open(route_path, "r", encoding="utf-8").read()

    # Verify all PFSP priority rules are present in route.ts
    for rule in PFSP_PRIORITY_RULES:
        assert f"'{rule}'" in content, f"PFSP priority rule '{rule}' missing from route.ts"

    # Verify all tie breakers are present
    for tb in PFSP_TIE_BREAKERS:
        assert f"'{tb}'" in content, f"PFSP tie breaker '{tb}' missing from route.ts"

    # Verify all insertion modes are present
    for im in PFSP_INSERTION_MODES:
        assert f"'{im}'" in content, f"PFSP insertion mode '{im}' missing from route.ts"

    # Verify all local search operators are present
    for op in PFSP_LOCAL_SEARCH_OPS:
        assert f"'{op}'" in content, f"PFSP local search op '{op}' missing from route.ts"

    # Verify all pivot rules are present
    for pr in PFSP_PIVOT_RULES:
        assert f"'{pr}'" in content, f"PFSP pivot rule '{pr}' missing from route.ts"

    # Verify removed invalid rules are NOT in route.ts
    for invalid in ["total_time_asc", "first_op_desc", "last_op_asc", "first_feasible", "insert_adjacent"]:
        assert f"'{invalid}'" not in content, f"Invalid rule '{invalid}' still present in route.ts"


def test_evidence_store_schema_version_and_immutability(tmp_path):
    """Section 4: EvidenceRecord schema versioning, defensive copying, and crash recovery."""
    store = EvidenceStore(direction=OptimizationDirection.MINIMIZE)
    cfg = DeclarativePFSPConfig()
    spec = CandidateSpec.from_declarative_pfsp(cfg, strategy_id="test_strat")

    # Mock report
    from north_bluestar.execution import VerificationReport, FailureCategory
    from north_bluestar.problem import AggregateEvaluationOutcome, SplitType

    outcome = AggregateEvaluationOutcome(
        split=SplitType.DEVELOPMENT,
        is_fully_feasible=True,
        feasible_count=1,
        total_count=1,
        proven_optimal_count=0,
        mean_objective=100.0,
        total_objective=100.0,
        std_objective=0.0,
        mean_optimality_gap_pct=0.0,
        total_runtime_ms=1.0,
        mean_runtime_ms=1.0,
    )
    rep = VerificationReport(
        candidate_id=spec.candidate_id,
        split=SplitType.DEVELOPMENT,
        outcome=outcome,
        failure_category=FailureCategory.NONE,
        is_repeatable=True,
    )

    rec = store.append(spec, rep)
    assert rec.schema_version == 1
    assert "schema_version" in rec.to_dict()

    # Verify nested payload immutability: mutating spec.payload does not alter record
    spec.payload["mutated"] = "danger"
    assert "mutated" not in rec.payload
    assert "mutated" not in rec.to_dict()["payload"]

    # Direct mutation on rec.payload must raise TypeError (MappingProxyType immutability)
    with pytest.raises(TypeError):
        rec.payload["attack"] = "value"

    # Save to disk
    save_path = str(tmp_path / "evidence_v1.json")
    store.save_to_file(save_path)

    # Load from disk
    loaded = EvidenceStore.load_from_file(save_path)
    assert loaded.verify_hash_chain()
    assert len(loaded.records) == 1
    assert loaded.records[0].schema_version == 1

    # Tamper detection: modify a field in the saved JSON file
    with open(save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["records"][0]["mean_objective"] = 50.0  # falsify score
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Reloading tampered file must fail verification
    with pytest.raises(ValueError, match="TAMPERING DETECTED"):
        EvidenceStore.load_from_file(save_path)


def test_evidence_store_fails_closed_on_corrupt_files(tmp_path):
    """Section 4: Evidence store fails closed on empty or malformed files."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        EvidenceStore.load_from_file(str(empty_file))

    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{ unparseable", encoding="utf-8")
    with pytest.raises(ValueError, match="Corrupted JSON"):
        EvidenceStore.load_from_file(str(corrupt_file))


def test_manifest_persistence_and_multi_seed_scientific_benchmark(tmp_path):
    """Section 2.E & Section 3: Experiment manifest generation, persistence, and multi-seed benchmarking."""
    from north_bluestar import (
        build_pfsp_problem, NorthBlueStarEngine, SearchController,
        SearchBudget, BaselinePortfolioStrategy, run_multi_seed_scientific_benchmark,
    )
    manifest_path = str(tmp_path / "manifest.json")
    evidence_path = str(tmp_path / "evidence.json")
    problem = build_pfsp_problem(seed=42, dev_count=3, val_count=2, holdout_count=2)
    engine = NorthBlueStarEngine(
        problem=problem,
        evidence_persist_path=evidence_path,
        manifest_persist_path=manifest_path,
    )
    ctrl = SearchController(
        strategies=[BaselinePortfolioStrategy(seed=42)],
        budget=SearchBudget(max_evaluations=4, stagnation_limit=4),
        seed=42,
    )
    res = engine.run_discovery(ctrl)
    assert res.manifest is not None
    assert os.path.exists(manifest_path)
    assert os.path.exists(evidence_path)

    # Load and verify manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        mf = json.load(f)
    assert mf["schema_version"] == 1
    assert mf["champion_candidate_id"] == res.champion_candidate_id
    assert mf["freeze_certificate_sha256"] == res.freeze_certificate_sha256

    # Test multi-seed scientific benchmark runner with small budget
    bench = run_multi_seed_scientific_benchmark(seeds=(42,), budget_evals=4, problem_id="pfsp_makespan")
    assert bench["problem_id"] == "pfsp_makespan"
    assert len(bench["runs"]) == 1
    assert "north_bluestar_portfolio" in bench["runs"][0]["arms"]
