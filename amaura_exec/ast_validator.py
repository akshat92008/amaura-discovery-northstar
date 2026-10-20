"""
Shared Allowlist AST Security Validator (SEC-1, SEC-2, SEC-3)
==============================================================
Enforces strict allowlist validation for candidate Python code across:
- North BlueStar (`north_bluestar/methods.py`)
- Stage 4 Evaluator (`stage4/src/evaluator.py`)
- Legacy Amaura Evaluators (`amaura/evaluators/`)

Threat Model & Defenses:
1. Denylists are fundamentally broken:
   - ().__class__.__base__.__subclasses__() reaches 'os' without any import (SEC-1).
   - Generator expressions (gi_frame.f_back.f_globals) reach module globals (SEC-2).
2. Allowlist Defense:
   - ONLY allow whitelisted AST node types (computational structures).
   - Attribute access is strictly restricted: ONLY math.<func> is allowed.
   - Any identifier (name or attribute) starting with an underscore '_' is rejected.
   - All imports, class definitions, try/except, generator expressions, lambdas,
     yields, globals, nonlocals, and f-strings are rejected.
"""

from __future__ import annotations

import ast
from typing import Optional, Set, Tuple


class ASTValidationError(ValueError):
    """Raised when candidate code fails AST security or structural validation."""
    pass


# Allowed safe math attributes
SAFE_MATH_ATTRS: Set[str] = {
    "sqrt", "log", "log2", "log10", "exp", "ceil", "floor",
    "sin", "cos", "tan", "pi", "e", "inf", "fabs", "pow",
    "copysign", "fmod", "isfinite", "isinf", "isnan",
}

# Forbidden function call names (even if defined or resolved)
FORBIDDEN_CALL_NAMES: Set[str] = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "getattr", "setattr", "delattr", "hasattr", "globals", "locals",
    "vars", "breakpoint", "exit", "quit", "print", "id", "dir",
    "help", "memoryview", "classmethod", "staticmethod", "property",
    "super", "type", "object",
}

# Strict AST node allowlist
ALLOWED_NODE_TYPES: Set[type] = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Assign,
    ast.AugAssign,
    ast.If,
    ast.For,
    ast.While,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.Expr,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.Subscript,
    ast.Slice,
    ast.Attribute,
    ast.ListComp,
    ast.comprehension,
    # Operators
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd,
    ast.Invert, ast.Not, ast.UAdd, ast.USub,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,
    ast.And, ast.Or,
}

# Explicitly forbidden node types with helpful error messages
EXPLICITLY_FORBIDDEN_NODES: dict[type, str] = {
    ast.Import: "Import statements are forbidden (SEC-1, SEC-3). Candidates may only use built-in math.",
    ast.ImportFrom: "Import statements are forbidden (SEC-1, SEC-3). Candidates may only use built-in math.",
    ast.ClassDef: "Class definitions are forbidden (SEC-1).",
    ast.GeneratorExp: "Generator expressions are forbidden due to frame-leak risks (SEC-2). Use list comprehensions.",
    ast.Lambda: "Lambda expressions are forbidden.",
    ast.Yield: "Yield statements are forbidden.",
    ast.YieldFrom: "Yield statements are forbidden.",
    ast.AsyncFunctionDef: "Async functions are forbidden.",
    ast.AsyncFor: "Async loops are forbidden.",
    ast.AsyncWith: "Async context managers are forbidden.",
    ast.Await: "Await expressions are forbidden.",
    ast.Global: "Global statements are forbidden.",
    ast.Nonlocal: "Nonlocal statements are forbidden.",
    ast.Try: "Try/except blocks are forbidden (candidates must not suppress runtime errors).",
    ast.With: "With blocks are forbidden.",
    ast.Delete: "Del statements are forbidden.",
    ast.Raise: "Raise statements are forbidden.",
    ast.Assert: "Assert statements are forbidden.",
    ast.JoinedStr: "Formatted strings (f-strings) are forbidden.",
    ast.FormattedValue: "Formatted values are forbidden.",
    ast.Starred: "Starred expressions are forbidden.",
}

# Python 3.8+ specific nodes
if hasattr(ast, "NamedExpr"):
    EXPLICITLY_FORBIDDEN_NODES[ast.NamedExpr] = "Named expressions (walrus operator) are forbidden."


def validate_candidate_ast(
    code: str,
    expected_func_name: Optional[str] = None,
    expected_param_count: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validates Python source code against the strict security allowlist.

    Parameters:
        code: The Python code to validate.
        expected_func_name: Optional name of the required entry function.
        expected_param_count: Optional required number of parameters for the entry function.

    Returns:
        (is_valid, error_message): (True, None) if code is strictly safe,
                                   (False, "description") otherwise.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    except Exception as e:
        return False, f"ParseError: {type(e).__name__}: {e}"

    # 1. Top-level statement check:
    # Only FunctionDef or module docstrings (ast.Expr with Constant) allowed at top level.
    found_entry_func = False
    entry_param_count = 0

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            if expected_func_name is None or stmt.name == expected_func_name:
                found_entry_func = True
                entry_param_count = len(stmt.args.args)
        elif isinstance(stmt, ast.Import):
            names = ", ".join(alias.name for alias in stmt.names)
            return False, f"Forbidden import: {names} (Import statement rejected)"
        elif isinstance(stmt, ast.ImportFrom):
            return False, f"Forbidden import: {stmt.module} (Import statement rejected)"
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            # Safe docstring
            continue
        elif isinstance(stmt, ast.Assign):
            # Only simple literal assignments at module level
            if not isinstance(stmt.value, (ast.Constant, ast.List, ast.Tuple, ast.Dict)):
                return False, f"Forbidden top-level execution statement: found '{type(stmt).__name__}' with complex expression"
        else:
            return False, f"Forbidden top-level execution statement: found '{type(stmt).__name__}' outside function definition"

    if expected_func_name and not found_entry_func:
        return False, f"Required entry function '{expected_func_name}' not defined"

    if expected_param_count is not None and found_entry_func and entry_param_count != expected_param_count:
        return False, f"Function '{expected_func_name}' must take exactly {expected_param_count} parameters (got {entry_param_count})"

    # 2. Complete AST Node Walk
    for node in ast.walk(tree):
        node_type = type(node)

        # Check imports first to format forbidden import name nicely
        if isinstance(node, ast.Import):
            names = ", ".join(alias.name for alias in node.names)
            return False, f"Forbidden import: {names} (Import statement rejected)"
        if isinstance(node, ast.ImportFrom):
            return False, f"Forbidden import: {node.module} (Import statement rejected)"

        # Check explicitly forbidden nodes next for detailed errors
        if node_type in EXPLICITLY_FORBIDDEN_NODES:
            return False, EXPLICITLY_FORBIDDEN_NODES[node_type]

        # Check against overall allowlist
        if node_type not in ALLOWED_NODE_TYPES:
            return False, f"Forbidden AST node type '{node_type.__name__}' is not in security allowlist"

        # Check Name nodes: reject underscore names
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                return False, f"Forbidden identifier starting with underscore: '{node.id}'"

        # Check FunctionDef / arg names: reject underscore names
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("_"):
                return False, f"Forbidden function name starting with underscore: '{node.name}'"
            for a in node.args.args:
                if a.arg.startswith("_"):
                    return False, f"Forbidden argument name starting with underscore: '{a.arg}'"

        # Check Attribute access:
        # ONLY math.<safe_attr> is allowed.
        # This completely neutralizes __class__, __base__, __subclasses__, gi_frame, f_back, etc.
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                return False, f"Forbidden attribute starting with underscore: '{node.attr}'"
            if isinstance(node.value, ast.Name) and node.value.id == "math":
                if node.attr not in SAFE_MATH_ATTRS:
                    return False, f"Forbidden math attribute '{node.attr}'; allowed: {sorted(SAFE_MATH_ATTRS)}"
            else:
                return False, f"Forbidden attribute access '{node.attr}' on non-math object '{ast.dump(node.value)}'"

        # Check Function Calls:
        # Block forbidden builtins
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALL_NAMES:
                    return False, f"Forbidden function call '{node.func.id}'"
            elif isinstance(node.func, ast.Attribute):
                # Must be math.<func>
                if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "math"):
                    return False, "Forbidden attribute call: only math.<function>() calls are permitted"

    return True, None
