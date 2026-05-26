"""
formula.py — safe arithmetic expressions for per-car YAML configs.

The per-car CAN config (e.g. data/cars/bmw_e46_m3.yaml) references a
shared formula library (data/formulas/standard.yaml). Each formula is a
pure-arithmetic expression over named inputs:

    formulas:
      mph_to_ms: { inputs: [x], expr: "x * 0.44704" }
      combo_g:   { inputs: [glat, glong], expr: "sqrt(glat*glat + glong*glong)" }

This module parses those expressions with Python's `ast` module against
a strict allowlist (no attribute access, no subscript, no imports, no
comprehensions, no lambdas), compiles them at load time, and returns
callables that evaluate against bound inputs.

Why allowlist + compile is safe:
  - `ast.parse(mode='eval')` already rejects statements (imports, assigns).
  - `_validate_ast()` rejects every node type that could escape the
    sandbox (Attribute, Subscript, Call to anything not in ALLOWED_FUNCS,
    Name references outside the declared input set + ALLOWED_FUNCS).
  - At runtime, `eval()` is called with `__builtins__={}`; no builtins
    are reachable. Only the math functions registered below can be
    called from a formula.

This is the same pattern asteval / simpleeval use. The result is a
data-driven conversion library: adding `kpa_to_psi` is a YAML edit, not
a Python code change.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Callable, Iterable


# ── allowlists ──────────────────────────────────────────────────────────

# Every AST node type that can appear inside a valid formula. Anything
# else (Attribute, Subscript, Lambda, ListComp, …) → FormulaError.
_ALLOWED_NODE_TYPES: frozenset[type] = frozenset({
    ast.Expression,
    ast.BinOp, ast.UnaryOp, ast.BoolOp,
    ast.Constant, ast.Name, ast.Load,
    ast.Call, ast.IfExp, ast.Compare,
    # Arithmetic operators
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd,
    # Comparison operators
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    # Boolean operators
    ast.And, ast.Or, ast.Not,
})

# Callable names that formulas may invoke. Adding a new name here is the
# only Python-side change needed to expose a new math function to YAML.
ALLOWED_FUNCS: dict[str, Callable] = {
    "sqrt":  math.sqrt,
    "abs":   abs,
    "min":   min,
    "max":   max,
    "sin":   math.sin,
    "cos":   math.cos,
    "tan":   math.tan,
    "asin":  math.asin,
    "acos":  math.acos,
    "atan":  math.atan,
    "atan2": math.atan2,
    "log":   math.log,
    "log10": math.log10,
    "exp":   math.exp,
    "pow":   pow,
    "floor": math.floor,
    "ceil":  math.ceil,
    "round": round,
}


class FormulaError(ValueError):
    """Raised when a formula fails to parse, validate, or evaluate."""


# ── compile ─────────────────────────────────────────────────────────────

def _validate_ast(tree: ast.AST, inputs: frozenset[str], name: str) -> None:
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODE_TYPES:
            raise FormulaError(
                f"formula {name!r}: disallowed AST node "
                f"{type(node).__name__!r} in expression",
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FormulaError(
                    f"formula {name!r}: only direct calls to registered "
                    f"functions are allowed (no attributes, no indirection)",
                )
            if node.func.id not in ALLOWED_FUNCS:
                raise FormulaError(
                    f"formula {name!r}: call to unknown function "
                    f"{node.func.id!r}; allowed: {sorted(ALLOWED_FUNCS)}",
                )
            if node.keywords:
                raise FormulaError(
                    f"formula {name!r}: keyword arguments are not allowed "
                    f"in function calls",
                )
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in inputs and node.id not in ALLOWED_FUNCS:
                raise FormulaError(
                    f"formula {name!r}: unknown name {node.id!r}; "
                    f"must be one of inputs={sorted(inputs)} or a "
                    f"registered function",
                )
        if isinstance(node, ast.Constant) and not isinstance(
            node.value, (int, float, bool),
        ):
            raise FormulaError(
                f"formula {name!r}: constant of type "
                f"{type(node.value).__name__} not allowed "
                f"(only numeric literals)",
            )


def compile_formula(
    name: str, expr: str, inputs: list[str],
) -> Callable[..., float]:
    """Parse, validate, and compile a single formula expression.

    Returns a callable `f(**kwargs) -> float` whose keyword names are
    exactly `inputs`. Compilation is safe; evaluation is safe; the only
    way to break out is to add an unsafe function to `ALLOWED_FUNCS`,
    which is a code-review point.

    Raises FormulaError for any of:
      - syntax error
      - input names that shadow a registered function
      - AST nodes outside the allowlist
      - references to functions outside `ALLOWED_FUNCS`
      - non-numeric literal constants
    """
    if not isinstance(name, str) or not name:
        raise FormulaError("formula name must be a non-empty string")
    if not isinstance(expr, str) or not expr.strip():
        raise FormulaError(f"formula {name!r}: expr must be a non-empty string")
    if not isinstance(inputs, list) or not all(
        isinstance(i, str) and i.isidentifier() for i in inputs
    ):
        raise FormulaError(
            f"formula {name!r}: inputs must be a list of identifier strings",
        )

    input_set = frozenset(inputs)
    overlap = input_set & set(ALLOWED_FUNCS)
    if overlap:
        raise FormulaError(
            f"formula {name!r}: input name(s) {sorted(overlap)} shadow "
            f"registered functions; rename them",
        )

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"formula {name!r}: syntax error: {e.msg}") from e

    _validate_ast(tree, input_set, name)
    code = compile(tree, f"<formula:{name}>", "eval")

    # Frozen globals namespace: zero builtins + registered functions only.
    safe_globals = {"__builtins__": {}, **ALLOWED_FUNCS}

    def evaluate(**kwargs) -> float:
        unknown = set(kwargs) - input_set
        if unknown:
            raise FormulaError(
                f"formula {name!r}: unexpected input(s) {sorted(unknown)}",
            )
        missing = input_set - set(kwargs)
        if missing:
            raise FormulaError(
                f"formula {name!r}: missing input(s) {sorted(missing)}",
            )
        result = eval(code, safe_globals, kwargs)  # noqa: S307 — sandboxed
        return float(result)

    evaluate.__name__ = f"formula_{name}"
    evaluate.__qualname__ = evaluate.__name__
    evaluate.__doc__ = f"Compiled formula {name!r}: {expr}"
    evaluate.formula_expr = expr  # type: ignore[attr-defined]
    evaluate.formula_inputs = tuple(inputs)  # type: ignore[attr-defined]
    return evaluate


# ── registry ───────────────────────────────────────────────────────────

class FormulaRegistry:
    """Loads formula definitions from one or more YAML files and serves
    them by name. Later loads override earlier ones (per-car can override
    the shared library)."""

    def __init__(self):
        self._formulas: dict[str, Callable] = {}
        self._meta: dict[str, dict] = {}

    def load_yaml(self, path: str | Path) -> "FormulaRegistry":
        import yaml
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        formulas = data.get("formulas") or {}
        if not isinstance(formulas, dict):
            raise FormulaError(
                f"{path}: 'formulas:' must be a mapping, got "
                f"{type(formulas).__name__}",
            )
        for fname, fdef in formulas.items():
            if not isinstance(fdef, dict):
                raise FormulaError(
                    f"{path}: formula {fname!r} must be a mapping",
                )
            self._formulas[fname] = compile_formula(
                fname, fdef.get("expr", ""), fdef.get("inputs") or [],
            )
            self._meta[fname] = {
                k: v for k, v in fdef.items() if k not in ("inputs", "expr")
            }
        return self

    def register(
        self, name: str, expr: str, inputs: list[str], **meta,
    ) -> "FormulaRegistry":
        """Programmatic registration (for tests + non-YAML callers)."""
        self._formulas[name] = compile_formula(name, expr, inputs)
        if meta:
            self._meta[name] = dict(meta)
        return self

    def get(self, name: str) -> Callable:
        try:
            return self._formulas[name]
        except KeyError:
            raise FormulaError(
                f"unknown formula {name!r}; registered: {sorted(self._formulas)}",
            ) from None

    def names(self) -> list[str]:
        return sorted(self._formulas)

    def __contains__(self, name: str) -> bool:
        return name in self._formulas

    def __len__(self) -> int:
        return len(self._formulas)


# ── helpers ─────────────────────────────────────────────────────────────

def load_standard_library(extra_paths: Iterable[str | Path] = ()) -> FormulaRegistry:
    """Convenience: load data/formulas/standard.yaml and optional extras."""
    root = Path(__file__).resolve().parents[4]
    reg = FormulaRegistry()
    reg.load_yaml(root / "data" / "formulas" / "standard.yaml")
    for p in extra_paths:
        reg.load_yaml(p)
    return reg
