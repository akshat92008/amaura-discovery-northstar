"""
Candidate Program Representation & Metadata
"""

import ast
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


def normalize_code(code_str: str) -> str:
    """Normalize code formatting to compute deterministic semantic hashes."""
    try:
        tree = ast.parse(code_str.strip())
        return ast.unparse(tree)
    except Exception:
        return code_str.strip()


@dataclass
class Candidate:
    """Represents a discovered algorithmic candidate program."""
    code: str
    function_name: str
    generation: int = 0
    island_id: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_ids: List[str] = field(default_factory=list)
    mutation_type: str = "initial"
    
    # Metrics
    fitness: float = float("inf")            # Main objective (lower is better by convention in engine)
    raw_score: float = 0.0                   # Human-interpretable metric (e.g. average bins or hit %)
    train_score: float = 0.0
    test_score: float = 0.0
    generalization_score: float = 0.0
    runtime_ms: float = 0.0
    
    # Validation & Status
    is_valid: bool = False
    passed_tests: int = 0
    total_tests: int = 0
    error_message: Optional[str] = None
    ast_nodes: int = 0
    created_at: float = field(default_factory=time.time)

    # Cached callable
    _callable: Optional[Any] = None

    @property
    def code_hash(self) -> str:
        norm = normalize_code(self.code)
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]

    def compile_function(self) -> Any:
        """Compile and extract the executable function in a restricted local scope."""
        if self._callable is not None:
            return self._callable
        
        local_scope: Dict[str, Any] = {}
        # Execute code in clean namespace
        exec(self.code, {"__builtins__": __builtins__}, local_scope)
        if self.function_name not in local_scope:
            raise ValueError(f"Function '{self.function_name}' not defined in candidate code.")
        
        self._callable = local_scope[self.function_name]
        try:
            tree = ast.parse(self.code)
            self.ast_nodes = sum(1 for _ in ast.walk(tree))
        except Exception:
            self.ast_nodes = len(self.code.splitlines())
        return self._callable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "generation": self.generation,
            "island_id": self.island_id,
            "parent_ids": self.parent_ids,
            "mutation_type": self.mutation_type,
            "fitness": round(self.fitness, 4),
            "raw_score": round(self.raw_score, 4),
            "train_score": round(self.train_score, 4),
            "test_score": round(self.test_score, 4),
            "generalization_score": round(self.generalization_score, 4),
            "runtime_ms": round(self.runtime_ms, 3),
            "is_valid": self.is_valid,
            "passed_tests": self.passed_tests,
            "total_tests": self.total_tests,
            "error_message": self.error_message,
            "code_hash": self.code_hash,
            "ast_nodes": self.ast_nodes,
            "code": self.code,
            "created_at": self.created_at,
        }
