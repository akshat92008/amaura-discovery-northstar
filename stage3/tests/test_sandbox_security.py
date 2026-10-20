"""
Unit Tests: Sandbox Security, AST Checks, and Exception Sanitization
====================================================================
Verifies:
1. Unauthorized imports (os, sys, subprocess, socket) are rejected.
2. Dangerous calls (open, exec, eval) are rejected.
3. Dunder attributes (__class__, __subclasses__) are rejected.
4. Bare except: statements are transformed to except Exception: to preserve SIGALRM.
5. Exception messages are sanitized to type(e).__name__ only.
6. Infinite loops are terminated via SIGALRM.
"""

import ast
import pytest
from stage3.src.sandbox import (
    check_ast_security,
    sanitize_and_compile,
    sanitize_exception_name,
    SanitizeExceptTransformer,
    SandboxTimeoutException
)
from stage3.src.evaluator_gc import GraphColoringEvaluator


def test_ast_forbidden_imports():
    code_os = "import os\ndef color_graph(adj):\n    return []"
    safe, msg = check_ast_security(code_os, "color_graph")
    assert not safe
    assert "Forbidden module import" in msg

    code_sys = "from sys import exit\ndef color_graph(adj):\n    return []"
    safe, msg = check_ast_security(code_sys, "color_graph")
    assert not safe
    assert "Forbidden module import from" in msg


def test_ast_forbidden_calls():
    code_eval = "def color_graph(adj):\n    eval('1+1')\n    return []"
    safe, msg = check_ast_security(code_eval, "color_graph")
    assert not safe
    assert "Forbidden call to 'eval()'" in msg

    code_open = "def color_graph(adj):\n    open('file.txt')\n    return []"
    safe, msg = check_ast_security(code_open, "color_graph")
    assert not safe
    assert "Forbidden call to 'open()'" in msg


def test_ast_dunder_attribute_rejection():
    code_dunder = "def color_graph(adj):\n    x = ().__class__.__bases__\n    return []"
    safe, msg = check_ast_security(code_dunder, "color_graph")
    assert not safe
    assert "Forbidden dunder attribute access" in msg


def test_bare_except_transformer():
    code_bare = """
try:
    x = 1 / 0
except:
    pass
"""
    tree = ast.parse(code_bare)
    transformed = SanitizeExceptTransformer().visit(tree)
    handler = transformed.body[0].handlers[0]
    assert isinstance(handler.type, ast.Name)
    assert handler.type.id == "Exception"


def test_exception_name_sanitization():
    e = RuntimeError("TOP_SECRET_PASSWORD_12345")
    name = sanitize_exception_name(e)
    assert name == "RuntimeError"
    assert "TOP_SECRET" not in name


def test_infinite_loop_timeout_interruption():
    code_loop = """
def color_graph(adj: list[list[int]]) -> list[int]:
    while True:
        pass
    return list(range(len(adj)))
"""
    evaluator = GraphColoringEvaluator(hard_sigalrm_sec=1)
    dataset = [{"adj": [[1, 2], [0, 2], [0, 1]]}]
    res = evaluator.evaluate_code(code_loop, dataset)
    assert not res["is_valid"]
    assert res["failure_category"] == "TIMEOUT"
