"""
Zero-Dependency Pytest Compatibility Runner for Containerized Verification
==========================================================================
Allows running `python3 -m pytest` and `import pytest` (including `pytest.raises`
and `pytest.approx`) using only the Python 3.10 standard library when external wheels
are not installed in the container environment.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Iterator, List, Optional, Tuple, Type, Union


class _ExceptionInfo:
    def __init__(self, exc: Optional[BaseException] = None) -> None:
        self.value = exc
        self.type = type(exc) if exc is not None else None


@contextmanager
def raises(
    expected_exception: Union[Type[BaseException], Tuple[Type[BaseException], ...]],
    match: Optional[str] = None,
) -> Iterator[_ExceptionInfo]:
    info = _ExceptionInfo()
    try:
        yield info
    except expected_exception as exc:
        info.value = exc
        info.type = type(exc)
        if match is not None:
            import re
            if not re.search(match, str(exc)):
                raise AssertionError(f"Regex '{match}' did not match '{exc}'") from exc
        return
    raise AssertionError(f"DID NOT RAISE {expected_exception}")


class _ApproxScalar:
    def __init__(self, expected: float, rel: float = 1e-6, abs_tol: float = 1e-12) -> None:
        self.expected = float(expected)
        self.rel = rel
        self.abs_tol = abs_tol

    def __eq__(self, actual: object) -> bool:
        if not isinstance(actual, (int, float)):
            return False
        tol = max(self.abs_tol, abs(self.expected) * self.rel)
        return abs(float(actual) - self.expected) <= tol


def approx(expected: float, rel: float = 1e-6, abs: float = 1e-12) -> _ApproxScalar:
    return _ApproxScalar(expected, rel=rel, abs_tol=abs)


def fixture(func: Optional[Callable] = None, **_kwargs: Any) -> Any:
    """Compatibility decorator for @pytest.fixture."""
    def _wrap(f: Callable) -> Callable:
        setattr(f, "_is_pytest_fixture", True)
        return f
    if func is not None:
        return _wrap(func)
    return _wrap


def discover_test_files(paths: List[str]) -> List[str]:
    found: List[str] = []
    for p in paths:
        if os.path.isfile(p) and p.endswith(".py"):
            found.append(p)
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if f.startswith("test_") and f.endswith(".py"):
                        found.append(os.path.join(root, f))
    return found


def run_test_files(paths: List[str]) -> int:
    if not paths:
        paths = ["tests"]
    files = discover_test_files(paths)
    passed = 0
    failed = 0
    failures: List[Tuple[str, str]] = []
    t0 = time.perf_counter()

    sys.path.insert(0, os.getcwd())

    for fpath in files:
        mod_name = fpath.replace("/", "_").replace("\\", "_").replace(".py", "")
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            failed += 1
            failures.append((f"{fpath}::<module_load>", traceback.format_exc()))
            print(f"ERROR loading {fpath}")
            continue

        # Collect module-level fixtures
        fixtures = {
            fname: fobj
            for fname, fobj in inspect.getmembers(mod)
            if inspect.isfunction(fobj) and getattr(fobj, "_is_pytest_fixture", False)
        }

        # Run standalone test_* functions
        for name, obj in inspect.getmembers(mod):
            if name.startswith("test_") and inspect.isfunction(obj):
                try:
                    sig = inspect.signature(obj)
                    import pathlib, tempfile
                    with tempfile.TemporaryDirectory() as td:
                        call_kwargs = {}
                        for pname in sig.parameters:
                            if pname == "tmp_path":
                                call_kwargs[pname] = pathlib.Path(td)
                            elif pname in fixtures:
                                f_sig = inspect.signature(fixtures[pname])
                                if "tmp_path" in f_sig.parameters:
                                    call_kwargs[pname] = fixtures[pname](pathlib.Path(td))
                                else:
                                    call_kwargs[pname] = fixtures[pname]()
                        obj(**call_kwargs)
                    passed += 1
                    print(f"PASSED {fpath}::{name}")
                except Exception:
                    failed += 1
                    failures.append((f"{fpath}::{name}", traceback.format_exc()))
                    print(f"FAILED {fpath}::{name}")

            elif inspect.isclass(obj) and (name.startswith("Test") or issubclass(obj, object)):
                # Check if unittest.TestCase subclass
                import unittest
                if issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase:
                    suite = unittest.defaultTestLoader.loadTestsFromTestCase(obj)
                    for test_case in suite:
                        res = unittest.TestResult()
                        test_case.run(res)
                        if res.wasSuccessful():
                            passed += 1
                            print(f"PASSED {fpath}::{obj.__name__}::{test_case._testMethodName}")
                        else:
                            failed += 1
                            err_txt = "\n".join(tb for _, tb in (res.errors + res.failures))
                            failures.append((f"{fpath}::{obj.__name__}::{test_case._testMethodName}", err_txt))
                            print(f"FAILED {fpath}::{obj.__name__}::{test_case._testMethodName}")

    elapsed = time.perf_counter() - t0
    print("=" * 72)
    if failures:
        for test_id, tb in failures:
            print(f"--- FAILURE: {test_id} ---\n{tb}")
    print(f"Summary: {passed} passed, {failed} failed in {elapsed:.2f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    cli_paths = [a for a in sys.argv[1:] if not a.startswith("-")]
    sys.exit(run_test_files(cli_paths))
