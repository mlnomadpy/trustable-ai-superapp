"""Tests for src/pitwall/features/telemetry/formula.py.

Two categories:
  1. Correctness — every formula in data/formulas/standard.yaml computes
     the right physical value on known inputs.
  2. Adversarial — every disallowed AST shape (attribute access,
     subscript, comprehension, lambda, undeclared name, …) raises
     FormulaError at compile time, before any user-supplied code runs.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from pitwall.features.telemetry.formula import (
    FormulaError,
    FormulaRegistry,
    compile_formula,
    load_standard_library,
)


# ── 1. Standard library correctness ────────────────────────────────────

@pytest.fixture(scope="module")
def std() -> FormulaRegistry:
    return load_standard_library()


def test_standard_library_loads(std: FormulaRegistry):
    assert len(std) >= 20
    for must_have in (
        "mph_to_ms", "kmh_to_ms", "psi_to_bar", "f_to_c",
        "negate", "combo_g", "magnitude_3d", "clamp", "deadzone",
    ):
        assert must_have in std, f"missing standard formula: {must_have}"


@pytest.mark.parametrize("name,kwargs,expected", [
    ("identity",     {"x": 42.0},                 42.0),
    ("negate",       {"x": 1.5},                  -1.5),
    ("negate",       {"x": -0.99},                0.99),
    ("linear",       {"x": 10, "a": 2, "b": 3},   23.0),
    ("scale",        {"x": 5, "a": 0.1},          0.5),
    ("offset",       {"x": 100, "b": -32},        68.0),
    ("mph_to_ms",    {"x": 100.0},                100 * 0.44704),
    ("kmh_to_ms",    {"x": 36.0},                 10.0),
    ("ms_to_kmh",    {"x": 10.0},                 36.0),
    ("psi_to_bar",   {"x": 14.5038},              14.5038 * 0.0689476),
    ("kpa_to_bar",   {"x": 100.0},                1.0),
    ("f_to_c",       {"x": 32.0},                 0.0),
    ("f_to_c",       {"x": 212.0},                100.0),
    ("c_to_f",       {"x": 100.0},                212.0),
    ("c_to_k",       {"x": 0.0},                  273.15),
    ("deg_to_rad",   {"x": 180.0},                math.pi),
    ("rad_to_deg",   {"x": math.pi},              180.0),
    ("combo_g",      {"glat": 3.0, "glong": 4.0}, 5.0),
    ("magnitude_3d", {"x": 1.0, "y": 2.0, "z": 2.0}, 3.0),
    ("mean_2",       {"a": 10, "b": 20},          15.0),
    ("mean_4",       {"a": 1, "b": 2, "c": 3, "d": 4}, 2.5),
    ("clamp",        {"x": 5,   "lo": 0, "hi": 10}, 5.0),
    ("clamp",        {"x": -5,  "lo": 0, "hi": 10}, 0.0),
    ("clamp",        {"x": 999, "lo": 0, "hi": 10}, 10.0),
    ("deadzone",     {"x": 0.05, "threshold": 0.1}, 0.0),
    ("deadzone",     {"x": 0.5,  "threshold": 0.1}, 0.5),
])
def test_standard_formula_values(std: FormulaRegistry, name, kwargs, expected):
    got = std.get(name)(**kwargs)
    assert got == pytest.approx(expected, rel=1e-9, abs=1e-12), (
        f"{name}({kwargs}) → {got}, expected {expected}"
    )


# ── 2. Adversarial / sandbox ───────────────────────────────────────────

# Each of these should fail at *compile* time, not at evaluate time.
ATTACK_EXPRS = [
    # Attribute access — most common escape vector
    ("attr_class",    "x.__class__"),
    ("attr_dict",     "x.__dict__"),
    ("attr_builtins", "().__class__"),
    # Subscript — could read items off injected dicts/lists
    ("subscript",     "x[0]"),
    # Calling something that isn't in ALLOWED_FUNCS
    ("call_eval",     "eval('1')"),
    ("call_exec",     "exec('1')"),
    ("call_open",     "open('/etc/passwd')"),
    ("call_getattr",  "getattr(x, '__class__')"),
    # Comprehensions / generator expressions
    ("listcomp",      "[i for i in [1,2,3]]"),
    ("setcomp",       "{i for i in [1,2,3]}"),
    ("dictcomp",      "{i: i for i in [1,2,3]}"),
    ("genexp",        "(i for i in [1,2,3])"),
    # Lambdas / function defs
    ("lambda",        "(lambda y: y * 2)(x)"),
    # Walrus
    ("walrus",        "(y := x) + 1"),
    # Tuple / list / dict / set literals
    ("list_literal",  "[1, 2, 3]"),
    ("dict_literal",  "{'a': 1}"),
    ("tuple_literal", "(1, 2)"),
    ("set_literal",   "{1, 2, 3}"),
    # Star expansion
    ("starred",       "max(*[x, 1, 2])"),
    # String / bytes constants (only numbers allowed)
    ("string_const",  "'abc'"),
    ("bytes_const",   "b'abc'"),
    # Undeclared name reference
    ("unknown_name",  "y * 2"),
    # Keyword args in calls
    ("kw_call",       "min(x, 1, key=abs)"),
]


@pytest.mark.parametrize("attack_id,expr", ATTACK_EXPRS, ids=[a[0] for a in ATTACK_EXPRS])
def test_disallowed_expressions_reject(attack_id, expr):
    with pytest.raises(FormulaError):
        compile_formula("attack", expr, ["x"])


def test_statements_reject_at_parse():
    # ast.parse(mode='eval') refuses statements entirely.
    for stmt in ("import os", "x = 1", "return x", "if x: x"):
        with pytest.raises(FormulaError):
            compile_formula("stmt", stmt, ["x"])


def test_input_cannot_shadow_function():
    with pytest.raises(FormulaError, match="shadow"):
        compile_formula("bad", "sqrt + 1", ["sqrt"])


def test_eval_strips_builtins():
    # Even if we tried to use a name like `__import__`, the validator
    # rejects unknown Names — but if it ever slipped through, eval()
    # has no builtins to find it through anyway. Quick smoke test.
    f = compile_formula("ok", "sqrt(x)", ["x"])
    assert f(x=4.0) == 2.0


def test_extra_inputs_rejected_at_call():
    f = compile_formula("ok", "x + 1", ["x"])
    with pytest.raises(FormulaError, match="unexpected"):
        f(x=1, y=2)


def test_missing_inputs_rejected_at_call():
    f = compile_formula("ok", "x + y", ["x", "y"])
    with pytest.raises(FormulaError, match="missing"):
        f(x=1)


def test_registry_get_unknown_raises():
    r = FormulaRegistry()
    with pytest.raises(FormulaError, match="unknown formula"):
        r.get("nope")


def test_registry_override():
    r = FormulaRegistry()
    r.register("f", "x + 1", ["x"])
    r.register("f", "x + 2", ["x"])  # override
    assert r.get("f")(x=10) == 12


def test_division_by_zero_propagates():
    # ZeroDivisionError is a runtime issue, not a sandbox escape.
    f = compile_formula("div", "x / 0", ["x"])
    with pytest.raises(ZeroDivisionError):
        f(x=1.0)


def test_ternary_works():
    f = compile_formula("tern", "x if x > 0 else -x", ["x"])
    assert f(x=5) == 5
    assert f(x=-5) == 5


def test_boolop_works():
    f = compile_formula("guard", "x if x > 0 and x < 10 else 0", ["x"])
    assert f(x=5) == 5
    assert f(x=-1) == 0
    assert f(x=99) == 0
