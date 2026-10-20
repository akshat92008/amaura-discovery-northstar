"""
Consolidated Safe Execution Engine (SEC-4)
===========================================
Replaces duplicated exec call sites across experiment scripts and ensures
candidate functions are evaluated within a restricted, secure builtins namespace.
"""

from __future__ import annotations

import importlib
import math
from typing import Any, Callable, Dict, Optional

from amaura_exec.ast_validator import validate_candidate_ast


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    if name in {"math", "time"}:
        return importlib.import_module(name)
    raise ImportError(f"Forbidden import: {name}")


SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
    "ValueError": ValueError,
    "RuntimeError": RuntimeError,
    "Exception": Exception,
    "__import__": _safe_import,
}


def create_safe_namespace(custom_builtins: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Returns a restricted execution namespace with safe builtins and math."""
    builtins_dict = dict(SAFE_BUILTINS)
    if custom_builtins:
        builtins_dict.update(custom_builtins)
    return {
        "__builtins__": builtins_dict,
        "math": math,
    }


def compile_candidate_program(
    code: str,
    entry_func_name: str,
    validate_ast: bool = True,
    expected_param_count: Optional[int] = None,
) -> Callable[..., Any]:
    """
    Validates AST safety and compiles a candidate program into a callable function.
    Raises ValueError on validation failure or compilation error.
    """
    if validate_ast:
        ok, err = validate_candidate_ast(
            code,
            expected_func_name=entry_func_name,
            expected_param_count=expected_param_count,
        )
        if not ok:
            raise ValueError(f"AST Safety Rejection: {err}")

    namespace = create_safe_namespace()
    compiled_code = compile(code, f"<candidate_{entry_func_name}>", "exec")
    exec(compiled_code, namespace, namespace)

    fn = namespace.get(entry_func_name)
    if not callable(fn):
        raise ValueError(f"Compiled code does not define callable entry function '{entry_func_name}'")
    return fn
