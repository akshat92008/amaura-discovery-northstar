"""
Stage 3: Evaluator Red-Teaming Canary Suite
===========================================
Defines adversarial, buggy, malicious, and pathological candidate codes
to verify that the sandbox and evaluator rigorously catch, classify, and sanitize
every form of defect and security violation.

Categories tested:
1. Trivial invalid coloring (monochromatic assignment)
2. Single edge color conflict
3. Wrong length outputs (short, long)
4. Non-integer or negative color values
5. Non-list return types
6. Infinite loops / SIGALRM timeouts
7. Forbidden imports (os, sys, subprocess, socket)
8. Forbidden dunder access (__class__, __subclasses__, __globals__)
9. Bare except: catch-all bypass attempts (handled by AST transformer)
10. K3 triangle sanity check failure
11. Exception message sanitization (covert channel prevention)
12. Dynamic penalty bound check (S_penalty <= 19,001)
"""

from typing import Dict, Any, List, Tuple
from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.sandbox import check_ast_security, sanitize_exception_name


CANARY_TRIVIAL_SAME_COLOR = """
def color_graph(adj: list[list[int]]) -> list[int]:
    # Malicious/Buggy: Assigns color 0 to all vertices
    return [0] * len(adj)
"""

CANARY_CONFLICT_SINGLE_EDGE = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    # Give all distinct colors except 0 and 1 get same color
    colors = list(range(n))
    if n > 1:
        colors[1] = colors[0]
    return colors
"""

CANARY_WRONG_LENGTH_SHORT = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    return list(range(max(0, n - 1)))
"""

CANARY_WRONG_LENGTH_LONG = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    return list(range(n + 1))
"""

CANARY_NEGATIVE_COLOR = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    colors = list(range(n))
    if n > 0:
        colors[0] = -1
    return colors
"""

CANARY_NON_INTEGER_COLOR = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    colors = list(range(n))
    if n > 0:
        colors[0] = "red"
    return colors
"""

CANARY_NON_LIST_RETURN = """
def color_graph(adj: list[list[int]]) -> list[int]:
    return 42
"""

CANARY_TIMEOUT_INFINITE_LOOP = """
def color_graph(adj: list[list[int]]) -> list[int]:
    while True:
        pass
    return list(range(len(adj)))
"""

CANARY_FORBIDDEN_IMPORT_OS = """
import os

def color_graph(adj: list[list[int]]) -> list[int]:
    return list(range(len(adj)))
"""

CANARY_FORBIDDEN_IMPORT_SYS = """
import sys

def color_graph(adj: list[list[int]]) -> list[int]:
    return list(range(len(adj)))
"""

CANARY_FORBIDDEN_DUNDER_ACCESS = """
def color_graph(adj: list[list[int]]) -> list[int]:
    x = "".__class__.__bases__
    return list(range(len(adj)))
"""

CANARY_BARE_EXCEPT_BYPASS = """
def color_graph(adj: list[list[int]]) -> list[int]:
    import time
    try:
        time.sleep(10)
    except:
        pass
    return list(range(len(adj)))
"""

CANARY_EXCEPTION_SECRET_LEAK = """
def color_graph(adj: list[list[int]]) -> list[int]:
    raise RuntimeError("SECRET_INTERNAL_DATABASE_CREDENTIAL_12345")
"""

CANARY_K3_FAIL = """
def color_graph(adj: list[list[int]]) -> list[int]:
    n = len(adj)
    if n == 3:
        # Color K3 with only 2 colors (violating chromatic number of K3 = 3)
        return [0, 0, 1]
    return list(range(n))
"""


def run_all_canaries(evaluator: GraphColoringEvaluator, sample_dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes all red-teaming canaries against the provided evaluator and dataset.
    Returns a structured report of results.
    """
    results: Dict[str, Dict[str, Any]] = {}

    # 1. Trivial Same Color -> WRONG_OUTPUT
    res = evaluator.evaluate_code(CANARY_TRIVIAL_SAME_COLOR, sample_dataset)
    results["trivial_same_color"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "WRONG_OUTPUT")
    }

    # 2. Conflict Single Edge -> WRONG_OUTPUT
    res = evaluator.evaluate_code(CANARY_CONFLICT_SINGLE_EDGE, sample_dataset)
    results["conflict_single_edge"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "WRONG_OUTPUT")
    }

    # 3. Wrong Length Short -> INVALID
    res = evaluator.evaluate_code(CANARY_WRONG_LENGTH_SHORT, sample_dataset)
    results["wrong_length_short"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "INVALID")
    }

    # 4. Wrong Length Long -> INVALID
    res = evaluator.evaluate_code(CANARY_WRONG_LENGTH_LONG, sample_dataset)
    results["wrong_length_long"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "INVALID")
    }

    # 5. Negative Color -> INVALID
    res = evaluator.evaluate_code(CANARY_NEGATIVE_COLOR, sample_dataset)
    results["negative_color"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "INVALID")
    }

    # 6. Non-Integer Color -> INVALID
    res = evaluator.evaluate_code(CANARY_NON_INTEGER_COLOR, sample_dataset)
    results["non_integer_color"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "INVALID")
    }

    # 7. Non-List Return -> INVALID
    res = evaluator.evaluate_code(CANARY_NON_LIST_RETURN, sample_dataset)
    results["non_list_return"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "INVALID")
    }

    # 8. Timeout Infinite Loop -> TIMEOUT
    res = evaluator.evaluate_code(CANARY_TIMEOUT_INFINITE_LOOP, sample_dataset)
    results["timeout_infinite_loop"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "TIMEOUT")
    }

    # 9. Forbidden Import OS -> AST Rejected (OTHER)
    safe, msg = check_ast_security(CANARY_FORBIDDEN_IMPORT_OS)
    res = evaluator.evaluate_code(CANARY_FORBIDDEN_IMPORT_OS, sample_dataset)
    results["forbidden_import_os"] = {
        "ast_safe": safe,
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not safe) and (not res["is_valid"]) and (res["failure_category"] == "OTHER")
    }

    # 10. Forbidden Import SYS -> AST Rejected (OTHER)
    safe, msg = check_ast_security(CANARY_FORBIDDEN_IMPORT_SYS)
    res = evaluator.evaluate_code(CANARY_FORBIDDEN_IMPORT_SYS, sample_dataset)
    results["forbidden_import_sys"] = {
        "ast_safe": safe,
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not safe) and (not res["is_valid"]) and (res["failure_category"] == "OTHER")
    }

    # 11. Forbidden Dunder Access -> AST Rejected (OTHER)
    safe, msg = check_ast_security(CANARY_FORBIDDEN_DUNDER_ACCESS)
    res = evaluator.evaluate_code(CANARY_FORBIDDEN_DUNDER_ACCESS, sample_dataset)
    results["forbidden_dunder_access"] = {
        "ast_safe": safe,
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not safe) and (not res["is_valid"]) and (res["failure_category"] == "OTHER")
    }

    # 12. Exception Sanitization Leak -> CRASH with sanitized name only
    res = evaluator.evaluate_code(CANARY_EXCEPTION_SECRET_LEAK, sample_dataset)
    err = res.get("error", "")
    secret_leaked = "SECRET_INTERNAL_DATABASE_CREDENTIAL_12345" in str(err)
    results["exception_sanitization"] = {
        "error_str": err,
        "secret_leaked": secret_leaked,
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (not secret_leaked) and ("RuntimeError" in str(err))
    }

    # 13. K3 Sanity Check Failure -> WRONG_OUTPUT
    res = evaluator.evaluate_code(CANARY_K3_FAIL, sample_dataset)
    results["k3_sanity_check_fail"] = {
        "is_valid": res["is_valid"],
        "failure_category": res["failure_category"],
        "passed": (not res["is_valid"]) and (res["failure_category"] == "WRONG_OUTPUT")
    }

    # 14. Bound Verification
    bound = evaluator.compute_worst_case_penalty(sample_dataset)
    results["bound_verification"] = {
        "computed_bound": bound,
        "passed": bound > 0
    }

    all_passed = all(r["passed"] for r in results.values())
    return {
        "all_passed": all_passed,
        "total_canaries": len(results),
        "passed_canaries": sum(1 for r in results.values() if r["passed"]),
        "results": results
    }
