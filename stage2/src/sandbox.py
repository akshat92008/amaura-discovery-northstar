"""
Stage 2: Strict Security Sandbox & AST Inspector
================================================
Enforces:
1. Static AST analysis against unauthorized imports, forbidden calls, dunder access.
2. Restricted execution environment with safe builtins and allowed pure modules.
3. Defensive copying of input data structures so candidate cannot mutate benchmarks.
4. Scale-aware and hard SIGALRM timeout interruption.
"""

import ast
import copy
import math
import os
import signal
import sys
import time
from typing import Dict, Any, List, Optional, Tuple, Set


ALLOWED_MODULES: Set[str] = {
    "math", "random", "typing", "collections", "itertools", "heapq", "copy"
}

FORBIDDEN_CALLS: Set[str] = {
    "open", "exec", "eval", "__import__", "globals", "locals", "getattr",
    "setattr", "delattr", "compile", "breakpoint", "input", "memoryview"
}

FORBIDDEN_ATTRIBUTES: Set[str] = {
    "system", "popen", "spawn", "fork", "subprocess", "environ",
    "getenv", "putenv", "walk", "listdir", "rmdir"
}


class SandboxTimeoutException(BaseException):
    pass


def _sigalrm_handler(signum, frame):
    raise SandboxTimeoutException("Hard execution timeout triggered via SIGALRM")


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root_mod = name.split(".")[0]
    if root_mod in ALLOWED_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Security restriction: module '{name}' is forbidden.")


SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "float": float,
    "int": int,
    "round": round,
    "bool": bool,
    "len": len,
    "range": range,
    "sum": sum,
    "pow": pow,
    "list": list,
    "tuple": tuple,
    "set": set,
    "dict": dict,
    "enumerate": enumerate,
    "sorted": sorted,
    "any": any,
    "all": all,
    "zip": zip,
    "reversed": reversed,
    "map": map,
    "filter": filter,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "print": lambda *args, **kwargs: None,
    "__import__": _safe_import,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "LookupError": LookupError,
    "ArithmeticError": ArithmeticError,
    "ZeroDivisionError": ZeroDivisionError,
}


class SanitizeExceptTransformer(ast.NodeTransformer):
    """
    Transforms any bare 'except:' to 'except Exception:' so that
    SandboxTimeoutException(BaseException) cannot be intercepted.
    """
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        if node.type is None:
            node.type = ast.Name(id="Exception", ctx=ast.Load())
        return self.generic_visit(node)


def sanitize_and_compile(code_str: str, filename: str = "<candidate>") -> Any:
    """
    Parses code_str, sanitizes bare except handlers, and compiles to bytecode.
    """
    tree = ast.parse(code_str)
    tree = SanitizeExceptTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")


def check_ast_security(code_str: str, required_func: str) -> Tuple[bool, Optional[str]]:
    """
    Performs static AST validation on candidate Python code:
    - Verifies presence of required function.
    - Prohibits unauthorized imports.
    - Prohibits forbidden builtins and dangerous attribute calls.
    - Prohibits dunder attribute access.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"SyntaxError in code: {e}"

    has_required_func = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == required_func:
            has_required_func = True

        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod not in ALLOWED_MODULES:
                    return False, f"Forbidden module import: '{alias.name}'. Only {ALLOWED_MODULES} allowed."

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod not in ALLOWED_MODULES:
                    return False, f"Forbidden module import from: '{node.module}'. Only {ALLOWED_MODULES} allowed."

        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_CALLS or node.id in {"__builtins__", "__import__", "globals", "locals"}:
                return False, f"Security violation: Forbidden identifier '{node.id}'."
            if node.id.startswith("__") and node.id.endswith("__"):
                return False, f"Security violation: Forbidden dunder name access '{node.id}'."

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    return False, f"Security violation: Forbidden call to '{node.func.id}()'."
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_ATTRIBUTES:
                    return False, f"Security violation: Forbidden attribute call to '{node.func.attr}'."

        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                # Disallow arbitrary dunder access except common standard ones if needed
                if node.attr not in {"__len__", "__getitem__"}:
                    return False, f"Security violation: Forbidden dunder attribute access '{node.attr}'."

    if not has_required_func:
        return False, f"Missing required function definition: 'def {required_func}(...)'"

    return True, None
