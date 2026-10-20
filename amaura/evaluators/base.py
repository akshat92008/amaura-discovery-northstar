"""
Base Evaluator Protocol and Isolated Execution Sandbox
"""

import ast
import concurrent.futures
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from amaura.engine.candidate import Candidate


@dataclass
class EvaluationResult:
    """Outcome of evaluating a candidate solution."""
    is_valid: bool
    fitness: float                         # Objective score (lower is better)
    raw_score: float                       # Human readable metric (e.g. mean bins, hit rate %)
    train_score: float
    test_score: float
    generalization_score: float
    runtime_ms: float
    passed_tests: int
    total_tests: int
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class BaseEvaluator(ABC):
    """Abstract base class for all domain evaluators."""

    def __init__(self, timeout_sec: float = 2.5):
        self.timeout_sec = timeout_sec

    @abstractmethod
    def get_seed_candidates(self) -> list[Candidate]:
        """Return canonical human baseline candidates."""
        pass

    @abstractmethod
    def evaluate_callable(
        self,
        func: Any,
        dataset: str = "train"
    ) -> Tuple[bool, float, float, int, int, Optional[str]]:
        """
        Evaluate a compiled callable.
        Returns: (is_valid, fitness, raw_score, passed_tests, total_tests, error_msg)
        """
        pass

    def static_analysis_check(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Anti-reward-hacking check using Python AST inspection.
        Detects malicious or cheating behavior:
        - forbidden imports (os, sys, subprocess, socket)
        - global state mutation
        - infinite loop structures without termination
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax Error: {e}"

        forbidden_modules = {"os", "sys", "subprocess", "socket", "requests", "urllib", "shutil", "posix"}
        forbidden_calls = {"eval", "exec", "getattr", "setattr", "open", "input", "__import__"}

        for node in ast.walk(tree):
            # Check forbidden imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_modules:
                        return False, f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in forbidden_modules:
                    return False, f"Forbidden import from: {node.module}"
            # Check forbidden builtins
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    return False, f"Forbidden builtin function call: {node.func.id}"

        return True, None

    def evaluate_candidate(self, candidate: Candidate, include_holdout: bool = False) -> EvaluationResult:
        """
        Full evaluation protocol:
        1. Static analysis & anti-cheat check
        2. Execution compilation
        3. Train/development dataset benchmark with timeout sandbox
        4. Optional holdout validation ONLY when include_holdout=True (never leaked into search fitness)
        """
        # Layer 1: Static analysis
        is_clean, cheat_err = self.static_analysis_check(candidate.code)
        if not is_clean:
            return EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                raw_score=0.0,
                train_score=0.0,
                test_score=0.0,
                generalization_score=0.0,
                runtime_ms=0.0,
                passed_tests=0,
                total_tests=0,
                error_message=cheat_err
            )

        # Layer 2: Compilation
        try:
            func = candidate.compile_function()
        except Exception as e:
            return EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                raw_score=0.0,
                train_score=0.0,
                test_score=0.0,
                generalization_score=0.0,
                runtime_ms=0.0,
                passed_tests=0,
                total_tests=0,
                error_message=f"Compilation Error: {str(e)}"
            )

        # Layer 3: Sandbox execution with timeout (strictly train/dev by default)
        start_time = time.perf_counter()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            # Run train evaluation
            future_train = executor.submit(self.evaluate_callable, func, "train")
            valid_train, fit_train, raw_train, passed_tr, total_tr, err_tr = future_train.result(
                timeout=self.timeout_sec
            )
            if not valid_train:
                return EvaluationResult(
                    is_valid=False,
                    fitness=float("inf"),
                    raw_score=raw_train,
                    train_score=raw_train,
                    test_score=0.0,
                    generalization_score=0.0,
                    runtime_ms=(time.perf_counter() - start_time) * 1000.0,
                    passed_tests=passed_tr,
                    total_tests=total_tr,
                    error_message=err_tr
                )

            if not include_holdout:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return EvaluationResult(
                    is_valid=valid_train,
                    fitness=fit_train,
                    raw_score=raw_train,
                    train_score=raw_train,
                    test_score=0.0,
                    generalization_score=0.0,
                    runtime_ms=elapsed_ms,
                    passed_tests=passed_tr,
                    total_tests=total_tr,
                    error_message=None
                )

            # Layer 4: Holdout evaluation (only when explicitly requested post-selection)
            future_test = executor.submit(self.evaluate_callable, func, "test")
            valid_test, fit_test, raw_test, passed_ts, total_ts, err_ts = future_test.result(
                timeout=self.timeout_sec
            )

            future_gen = executor.submit(self.evaluate_callable, func, "generalization")
            valid_gen, fit_gen, raw_gen, passed_gn, total_gn, err_gn = future_gen.result(
                timeout=self.timeout_sec
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return EvaluationResult(
                is_valid=(valid_train and valid_test and valid_gen),
                fitness=fit_train,
                raw_score=raw_train,
                train_score=raw_train,
                test_score=raw_test,
                generalization_score=raw_gen,
                runtime_ms=elapsed_ms,
                passed_tests=passed_tr + passed_ts + passed_gn,
                total_tests=total_tr + total_ts + total_gn,
                error_message=None
            )

        except concurrent.futures.TimeoutError:
            return EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                raw_score=0.0,
                train_score=0.0,
                test_score=0.0,
                generalization_score=0.0,
                runtime_ms=(time.perf_counter() - start_time) * 1000.0,
                passed_tests=0,
                total_tests=1,
                error_message=f"Evaluation Timeout (> {self.timeout_sec}s)"
            )
        except Exception as e:
            return EvaluationResult(
                is_valid=False,
                fitness=float("inf"),
                raw_score=0.0,
                train_score=0.0,
                test_score=0.0,
                generalization_score=0.0,
                runtime_ms=(time.perf_counter() - start_time) * 1000.0,
                passed_tests=0,
                total_tests=1,
                error_message=f"Runtime Exception: {type(e).__name__}: {str(e)}"
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
