"""
Discovery Kernel v0.1: Evidence Store
====================================
Provides machine-readable, append-only persistence of all execution events,
development comparisons, frozen selections, and final evaluations.
Includes automated reconstruction to verify selection integrity and provenance.
"""

from dataclasses import dataclass, asdict
import hashlib
import json
import os
import time
from typing import Dict, Any, List, Optional
import uuid


class EvidenceStore:
    """
    Manages structured, tamper-evident experiment records.
    Stores raw instance-level runs in JSONL and phase summaries in JSON.
    """
    def __init__(self, output_dir: str, experiment_id: str):
        self.output_dir = output_dir
        self.experiment_id = experiment_id
        os.makedirs(self.output_dir, exist_ok=True)

        self.runs_file = os.path.join(self.output_dir, "run_records.jsonl")
        self.dev_summary_file = os.path.join(self.output_dir, "dev_summary.json")
        self.final_report_file = os.path.join(self.output_dir, "final_report.json")
        self.manifest_file = os.path.join(self.output_dir, "manifest.json")

    def log_evaluation(
        self,
        phase: str,  # "development" or "final_evaluation"
        problem_id: str,
        spec_sha256: str,
        method_id: str,
        method_version: str,
        instance_id: str,
        instance_fingerprint: str,
        status: str,
        is_valid: bool,
        objective_metric: str,
        objective_score: Optional[float],
        runtime_ms: float,
        validation_errors: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Appends a single execution record to the append-only JSONL log."""
        record = {
            "record_id": str(uuid.uuid4()),
            "experiment_id": self.experiment_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phase": phase,
            "problem_id": problem_id,
            "spec_sha256": spec_sha256,
            "method_id": method_id,
            "method_version": method_version,
            "instance_id": str(instance_id),
            "instance_fingerprint": str(instance_fingerprint),
            "status": status,
            "is_valid": is_valid,
            "objective_metric": objective_metric,
            "objective_score": objective_score,
            "runtime_ms": round(runtime_ms, 3),
            "validation_errors": validation_errors or [],
            "error_message": error_message,
            "metadata": metadata or {}
        }

        with open(self.runs_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

        return record

    def record_selection(self, dev_summary: Dict[str, Any]) -> None:
        """Writes the development phase evaluation summary and frozen selection decision."""
        with open(self.dev_summary_file, "w", encoding="utf-8") as f:
            json.dump(dev_summary, f, indent=2, sort_keys=True)

    def record_final_evaluation(self, final_report: Dict[str, Any]) -> None:
        """Writes the confirmatory evaluation report on the holdout dataset."""
        with open(self.final_report_file, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, sort_keys=True)

    def generate_manifest(self) -> Dict[str, Any]:
        """Generates cryptographic manifest of all output files."""
        files_manifest = {}
        for fname in os.listdir(self.output_dir):
            if fname == "manifest.json":
                continue
            fpath = os.path.join(self.output_dir, fname)
            if os.path.isfile(fpath):
                hasher = hashlib.sha256()
                with open(fpath, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                files_manifest[fname] = {
                    "sha256": hasher.hexdigest(),
                    "size_bytes": os.path.getsize(fpath)
                }

        manifest_data = {
            "experiment_id": self.experiment_id,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": files_manifest
        }

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, sort_keys=True)

        return manifest_data


def reconstruct_and_verify_selection(output_dir: str) -> Dict[str, Any]:
    """
    Independently reconstructs development method comparison from raw run records.
    Verifies that the frozen selection matches the recomputed evidence exactly.
    """
    runs_path = os.path.join(output_dir, "run_records.jsonl")
    dev_summary_path = os.path.join(output_dir, "dev_summary.json")

    if not os.path.isfile(runs_path):
        raise FileNotFoundError(f"Missing run records: {runs_path}")
    if not os.path.isfile(dev_summary_path):
        raise FileNotFoundError(f"Missing dev summary: {dev_summary_path}")

    with open(dev_summary_path, "r", encoding="utf-8") as f:
        recorded_summary = json.load(f)

    # Reconstruct from raw records
    methods_stats: Dict[str, Dict[str, Any]] = {}
    with open(runs_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("phase") != "development":
                continue

            mid = rec["method_id"]
            if mid not in methods_stats:
                methods_stats[mid] = {
                    "method_id": mid,
                    "method_version": rec["method_version"],
                    "total_runs": 0,
                    "valid_runs": 0,
                    "scores": [],
                    "total_runtime_ms": 0.0,
                    "has_failures": False
                }

            s = methods_stats[mid]
            s["total_runs"] += 1
            s["total_runtime_ms"] += rec["runtime_ms"]
            if rec["is_valid"] and rec["objective_score"] is not None:
                s["valid_runs"] += 1
                s["scores"].append(rec["objective_score"])
            else:
                s["has_failures"] = True

    # Recompute rankings
    direction = recorded_summary.get("objective_direction", "MINIMIZE")
    ranked = []
    for mid, s in methods_stats.items():
        is_fully_valid = (s["valid_runs"] == s["total_runs"]) and not s["has_failures"]
        mean_score = sum(s["scores"]) / len(s["scores"]) if s["scores"] else None
        ranked.append({
            "method_id": mid,
            "version": s["method_version"],
            "is_fully_valid": is_fully_valid,
            "valid_runs": s["valid_runs"],
            "total_runs": s["total_runs"],
            "mean_score": round(mean_score, 4) if mean_score is not None else None,
            "total_runtime_ms": round(s["total_runtime_ms"], 2)
        })

    # Sort: fully valid first, then by score according to direction, then method_id
    def sort_key(item):
        valid_rank = 0 if item["is_fully_valid"] else 1
        score_val = item["mean_score"]
        if score_val is None:
            score_rank = float("inf")
        elif direction == "MINIMIZE":
            score_rank = score_val
        else:
            score_rank = -score_val
        # Deterministic tie-breaking: strictly method_id. Never use runtime_ms for ranking.
        return (valid_rank, score_rank, item["method_id"])

    ranked.sort(key=sort_key)
    recomputed_champion = ranked[0]["method_id"] if ranked and ranked[0]["is_fully_valid"] else None
    recorded_champion = recorded_summary.get("champion_method_id")

    is_verified = (recomputed_champion == recorded_champion)

    return {
        "verified": is_verified,
        "recorded_champion": recorded_champion,
        "recomputed_champion": recomputed_champion,
        "recorded_dev_score": recorded_summary.get("champion_dev_score"),
        "recomputed_rankings": ranked
    }
