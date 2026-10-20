"""
Discovery Kernel v0.1: Problem Specification
============================================
Defines the structured contract for problem domains in North BlueStar.
Enforces strict schema validation, cryptographic data references, explicit
objective directions, and declarative constraint rules.
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
import time
from typing import Dict, Any, List, Optional, Callable, Tuple


class ObjectiveDirection(str, Enum):
    """Direction of optimization."""
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


class SpecificationValidationError(ValueError):
    """Raised when a ProblemSpecification fails validation."""
    pass


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hex digest of a file in chunks."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class DatasetReference:
    """Cryptographic reference to an immutable dataset split."""
    name: str  # e.g., "development", "evaluation"
    file_path: str
    sha256: str
    instance_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def verify(self, base_dir: Optional[str] = None) -> None:
        """Verifies file existence, SHA-256 checksum, and instance count."""
        resolved_path = self.file_path
        if base_dir and not os.path.isabs(resolved_path):
            resolved_path = os.path.join(base_dir, resolved_path)

        if not os.path.exists(resolved_path):
            raise SpecificationValidationError(
                f"Dataset file missing for split '{self.name}': {resolved_path}"
            )

        actual_hash = compute_file_sha256(resolved_path)
        if actual_hash.lower() != self.sha256.lower():
            raise SpecificationValidationError(
                f"Dataset SHA-256 mismatch for split '{self.name}': "
                f"expected {self.sha256}, got {actual_hash}"
            )

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise SpecificationValidationError(
                    f"Dataset file must contain a JSON list of instances: {resolved_path}"
                )
            if len(data) != self.instance_count:
                raise SpecificationValidationError(
                    f"Dataset instance count mismatch for split '{self.name}': "
                    f"expected {self.instance_count}, got {len(data)}"
                )
        except json.JSONDecodeError as e:
            raise SpecificationValidationError(
                f"Corrupted JSON in dataset file '{resolved_path}': {e}"
            )


@dataclass
class ResourceLimits:
    """Enforceable operational and evaluation limits."""
    max_runtime_sec_per_instance: float = 5.0
    max_total_runtime_sec: float = 120.0
    max_evaluations: int = 100
    max_memory_mb: Optional[float] = None

    def validate(self) -> None:
        """Ensures all limits are strictly positive finite values."""
        if self.max_runtime_sec_per_instance <= 0:
            raise SpecificationValidationError(
                f"max_runtime_sec_per_instance must be > 0, got {self.max_runtime_sec_per_instance}"
            )
        if self.max_total_runtime_sec <= 0:
            raise SpecificationValidationError(
                f"max_total_runtime_sec must be > 0, got {self.max_total_runtime_sec}"
            )
        if self.max_evaluations <= 0:
            raise SpecificationValidationError(
                f"max_evaluations must be > 0, got {self.max_evaluations}"
            )
        if self.max_memory_mb is not None and self.max_memory_mb <= 0:
            raise SpecificationValidationError(
                f"max_memory_mb must be > 0 if specified, got {self.max_memory_mb}"
            )


@dataclass
class ConstraintRule:
    """Declarative constraint validation rule."""
    name: str
    description: str
    validator: Callable[[Any, Any], Tuple[bool, Optional[str]]]

    def check(self, instance: Any, solution: Any) -> Tuple[bool, Optional[str]]:
        """Runs the validator function on instance and candidate solution."""
        try:
            return self.validator(instance, solution)
        except Exception as e:
            return False, f"Constraint validator '{self.name}' raised {type(e).__name__}: {str(e)}"


@dataclass
class BaselineMethod:
    """Reference baseline method definition."""
    name: str
    description: str
    known_dev_score: Optional[float] = None
    known_eval_score: Optional[float] = None


@dataclass
class ProblemSpecification:
    """
    Structured problem contract for North BlueStar.
    Provides complete, verifiable definition of an optimization domain.
    """
    problem_id: str
    version: str
    objective_metric: str
    objective_direction: ObjectiveDirection
    constraints: List[ConstraintRule]
    evaluator_name: str
    development_dataset: DatasetReference
    evaluation_dataset: DatasetReference
    resource_limits: ResourceLimits
    baselines: List[BaselineMethod]
    experiment_id: str
    provenance: Dict[str, Any] = field(default_factory=dict)

    def validate(self, verify_data_files: bool = True, base_dir: Optional[str] = None) -> str:
        """
        Validates all fields for completeness, consistency, and data integrity.
        Returns the SHA-256 fingerprint of the validated specification.
        """
        if not self.problem_id or not isinstance(self.problem_id, str):
            raise SpecificationValidationError("problem_id must be a non-empty string")

        if not self.version or not isinstance(self.version, str):
            raise SpecificationValidationError("version must be a non-empty string")

        if not self.objective_metric or not isinstance(self.objective_metric, str):
            raise SpecificationValidationError("objective_metric must be a non-empty string")

        if not isinstance(self.objective_direction, ObjectiveDirection):
            if isinstance(self.objective_direction, str):
                try:
                    self.objective_direction = ObjectiveDirection(self.objective_direction.upper())
                except ValueError:
                    raise SpecificationValidationError(
                        f"Invalid objective_direction: {self.objective_direction}. "
                        f"Must be one of: {[d.value for d in ObjectiveDirection]}"
                    )
            else:
                raise SpecificationValidationError(
                    f"Invalid objective_direction type: {type(self.objective_direction).__name__}"
                )

        if not self.constraints or len(self.constraints) == 0:
            raise SpecificationValidationError(
                "Problem specification must define at least one ConstraintRule"
            )

        for i, c in enumerate(self.constraints):
            if not isinstance(c, ConstraintRule):
                raise SpecificationValidationError(
                    f"Constraint #{i} is not an instance of ConstraintRule"
                )
            if not callable(c.validator):
                raise SpecificationValidationError(
                    f"Constraint '{c.name}' validator is not callable"
                )

        if not self.evaluator_name or not isinstance(self.evaluator_name, str):
            raise SpecificationValidationError("evaluator_name must be a non-empty string")

        if not isinstance(self.development_dataset, DatasetReference):
            raise SpecificationValidationError("development_dataset must be a DatasetReference")

        if not isinstance(self.evaluation_dataset, DatasetReference):
            raise SpecificationValidationError("evaluation_dataset must be a DatasetReference")

        if self.development_dataset.name == self.evaluation_dataset.name:
            raise SpecificationValidationError(
                "development_dataset and evaluation_dataset must have distinct names"
            )

        if not isinstance(self.resource_limits, ResourceLimits):
            raise SpecificationValidationError("resource_limits must be a ResourceLimits instance")
        self.resource_limits.validate()

        if not self.baselines or len(self.baselines) == 0:
            raise SpecificationValidationError(
                "Problem specification must declare at least one BaselineMethod"
            )

        if not self.experiment_id or not isinstance(self.experiment_id, str):
            raise SpecificationValidationError("experiment_id must be a non-empty string")

        if verify_data_files:
            self.development_dataset.verify(base_dir=base_dir)
            self.evaluation_dataset.verify(base_dir=base_dir)

        # Compute deterministic SHA-256 fingerprint
        fingerprint = self.compute_fingerprint()
        self.provenance["spec_sha256"] = fingerprint
        return fingerprint

    def compute_fingerprint(self) -> str:
        """Computes deterministic SHA-256 fingerprint of the specification contract."""
        payload = {
            "problem_id": self.problem_id,
            "version": self.version,
            "objective_metric": self.objective_metric,
            "objective_direction": self.objective_direction.value,
            "constraints": [c.name for c in self.constraints],
            "evaluator_name": self.evaluator_name,
            "development_dataset": {
                "name": self.development_dataset.name,
                "sha256": self.development_dataset.sha256,
                "instance_count": self.development_dataset.instance_count,
            },
            "evaluation_dataset": {
                "name": self.evaluation_dataset.name,
                "sha256": self.evaluation_dataset.sha256,
                "instance_count": self.evaluation_dataset.instance_count,
            },
            "resource_limits": {
                "max_runtime_sec_per_instance": self.resource_limits.max_runtime_sec_per_instance,
                "max_total_runtime_sec": self.resource_limits.max_total_runtime_sec,
                "max_evaluations": self.resource_limits.max_evaluations,
            },
            "baselines": [b.name for b in self.baselines],
            "experiment_id": self.experiment_id,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
