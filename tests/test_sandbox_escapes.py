"""
Adversarial Sandbox Escape & AST Security Verification Suite (TEST-2)
=====================================================================
Rigorous regression tests for:
- SEC-1: Object subclass traversal escape via ().__class__.__base__.__subclasses__()
- SEC-2: Generator frame walk escape via gi_frame.f_back.f_globals
- SEC-3: Blocklist bypass via whitespace or omitted modules
- Attribute access probing, f-string injection, lambda/class escapes
- Proving valid mathematical heuristic code passes cleanly
"""

from __future__ import annotations

import pytest

from amaura_exec.ast_validator import validate_candidate_ast
from north_bluestar.methods import SandboxedPythonProgramMethodAdapter
from stage4.src.evaluator import Stage4Evaluator


# =============================================================================
# 1. THE TWO REAL-WORLD PROOFS OF CONCEPT FROM THE DEFECT REPORT
# =============================================================================

def test_sec1_subclass_traversal_escape_rejected():
    """SEC-1: ().__class__.__base__.__subclasses__() must be rejected by AST validator."""
    malicious_code = (
        "def priority(item, rem, cap):\n"
        "    subclasses = ().__class__.__base__.__subclasses__()\n"
        "    for c in subclasses:\n"
        "        if c.__name__ == 'catch_warnings':\n"
        "            c()._module.os.system('id')\n"
        "    return 0.0\n"
    )
    ok, err = validate_candidate_ast(malicious_code, expected_func_name="priority")
    assert not ok
    assert "Forbidden" in str(err) or "underscore" in str(err)


def test_sec2_generator_frame_escape_rejected():
    """SEC-2: Generator expression gi_frame.f_back.f_globals must be rejected."""
    malicious_code = (
        "def priority(item, rem, cap):\n"
        "    gen = (x for x in [1])\n"
        "    g = gen.gi_frame.f_back.f_globals\n"
        "    return float(len(g))\n"
    )
    ok, err = validate_candidate_ast(malicious_code, expected_func_name="priority")
    assert not ok
    assert "Generator expressions are forbidden" in str(err) or "Forbidden" in str(err)


# =============================================================================
# 2. ADDITIONAL ADVERSARIAL ESCAPE CORPUS
# =============================================================================

def test_import_os_rejected():
    code = "import os\ndef priority(item, rem, cap):\n    return 0.0\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Import" in str(err)


def test_import_subprocess_rejected():
    code = "from subprocess import Popen\ndef priority(item, rem, cap):\n    return 0.0\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Import" in str(err)


def test_import_builtins_with_whitespace_rejected():
    """SEC-3: Leading whitespace in module names must still be rejected."""
    code = "import  builtins\ndef priority(item, rem, cap):\n    return 0.0\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok


def test_import_pathlib_rejected():
    code = "import pathlib\ndef priority(item, rem, cap):\n    return 0.0\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok


def test_str_format_attribute_probing_rejected():
    """Format string attribute probing must be rejected."""
    code = (
        "def priority(item, rem, cap):\n"
        "    s = '{0.__class__}'.format(item)\n"
        "    return 0.0\n"
    )
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    # str.format is an attribute access on non-math object ('s.format')
    assert not ok
    assert "Forbidden" in str(err) or "underscore" in str(err)


def test_fstring_injection_rejected():
    """Formatted strings (f-strings) are rejected to prevent expression smuggling."""
    code = (
        "def priority(item, rem, cap):\n"
        "    msg = f'val: {item}'\n"
        "    return 0.0\n"
    )
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Formatted strings" in str(err) or "f-strings" in str(err)


def test_class_definition_rejected():
    """Candidates cannot define classes (avoids metaclass / MRO escapes)."""
    code = (
        "class Exploit:\n"
        "    pass\n"
        "def priority(item, rem, cap):\n"
        "    return 0.0\n"
    )
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Class" in str(err) or "Forbidden" in str(err)


def test_lambda_expression_rejected():
    """Lambdas are rejected to enforce clean named control flow."""
    code = (
        "def priority(item, rem, cap):\n"
        "    f = lambda x: x + 1\n"
        "    return f(item)\n"
    )
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Lambda" in str(err)


def test_try_except_suppression_rejected():
    """Try/except blocks are rejected so runtime errors cannot be masked."""
    code = (
        "def priority(item, rem, cap):\n"
        "    try:\n"
        "        x = 1 / 0\n"
        "    except Exception:\n"
        "        x = 0\n"
        "    return float(x)\n"
    )
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Try/except" in str(err) or "forbidden" in str(err).lower()


def test_eval_call_rejected():
    code = "def priority(item, rem, cap):\n    return eval('1 + 1')\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Forbidden function call 'eval'" in str(err)


def test_exec_call_rejected():
    code = "def priority(item, rem, cap):\n    exec('x = 1')\n    return 0.0\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Forbidden function call 'exec'" in str(err)


def test_underscore_variable_rejected():
    """Variables starting with an underscore are strictly forbidden."""
    code = "def priority(item, rem, cap):\n    _hidden = 10\n    return float(_hidden)\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "underscore" in str(err)


def test_walrus_operator_rejected():
    code = "def priority(item, rem, cap):\n    if (n := item) > 10:\n        return 1.0\n    return 0.0\n"
    ok, err = validate_candidate_ast(code, expected_func_name="priority")
    assert not ok
    assert "Named expression" in str(err) or "walrus" in str(err) or "Forbidden" in str(err)


# =============================================================================
# 3. VERIFICATION ACROSS NORTH BLUESTAR AND STAGE 4 ADAPTERS
# =============================================================================

def test_north_bluestar_adapter_rejects_sec1_and_sec2():
    adapter = SandboxedPythonProgramMethodAdapter()
    sec1_code = "def priority(item, rem, cap):\n    return float(len(().__class__.__base__.__subclasses__()))\n"
    ok, err = adapter.validate_ast_safety(sec1_code, "priority")
    assert not ok

    sec2_code = "def priority(item, rem, cap):\n    gen = (x for x in [1])\n    return float(len(gen.gi_frame.f_back.f_globals))\n"
    ok, err = adapter.validate_ast_safety(sec2_code, "priority")
    assert not ok


def test_stage4_evaluator_rejects_sec1_and_sec2():
    evaluator = Stage4Evaluator()
    sec1_code = "def priority(item, remaining_capacity, bin_capacity):\n    return float(len(().__class__.__base__.__subclasses__()))\n"
    ok, err = evaluator.validate_ast(sec1_code)
    assert not ok

    sec2_code = "def priority(item, remaining_capacity, bin_capacity):\n    gen = (x for x in [1])\n    return float(len(gen.gi_frame.f_back.f_globals))\n"
    ok, err = evaluator.validate_ast(sec2_code)
    assert not ok


# =============================================================================
# 4. VALID MATHEMATICAL HEURISTICS MUST PASS
# =============================================================================

def test_valid_heuristics_pass_validation():
    """Legitimate heuristics using arithmetic, loops, conditionals, and math pass."""
    valid_codes = [
        # Standard Best-Fit
        "def priority(item, rem, cap):\n    return -(rem - item)\n",
        # Non-linear math heuristic
        (
            "def priority(item, rem, cap):\n"
            "    slack = rem - item\n"
            "    if slack <= 0.03 * cap:\n"
            "        return 100.0 - slack\n"
            "    ratio = item / rem\n"
            "    return math.exp(-slack / cap) + 0.5 * math.sqrt(ratio)\n"
        ),
        # Loop with list accumulation
        (
            "def priority(item, rem, cap):\n"
            "    scores = [item, rem, cap]\n"
            "    total = 0.0\n"
            "    for s in scores:\n"
            "        total = total + s\n"
            "    return total\n"
        ),
    ]
    for code in valid_codes:
        ok, err = validate_candidate_ast(code, expected_func_name="priority", expected_param_count=3)
        assert ok, f"Valid code unexpectedly failed validation: {err}"
