"""
car_config.py — per-car YAML → signal post-processing pipelines.

Reads a car config YAML (e.g. data/cars/bmw_e46_m3.yaml), merges with
the shared formula library (data/formulas/standard.yaml), and produces a
`CarConfig` object that knows how to post-process every signal coming
out of cantools' DBC decode.

Three levels of derivation, in order of application per frame:

  1. Per-signal `apply:`   — transforms applied to a single channel's
                             decoded value (sign flips, bias offsets,
                             unit conversions). The signal's stored
                             value is replaced.

  2. Per-signal `derive:`  — additional signals emitted alongside the
                             primary, using the current value plus
                             optional other signals from the latest cache
                             (e.g. speed_mph also emits speed_ms).

  3. Cross-signal `derived:` (top level) — multi-input signals computed
                             after the frame's other signals are
                             processed (e.g. combo_g from g_lat+g_long).

For non-arithmetic derivations (lookup tables, hysteresis) use the
`methods:` block — its handlers are registered in this module and
receive their inputs from the latest-value cache.

All math goes through `formula.FormulaRegistry`, which sandboxes any
expression text via an AST allowlist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pitwall.features.telemetry.formula import (
    FormulaError,
    FormulaRegistry,
    compile_formula,
    load_standard_library,
)


# ── binding resolution ─────────────────────────────────────────────────

class BindingError(ValueError):
    pass


@dataclass(frozen=True)
class Binding:
    """A single formula input binding. One of three kinds:

      const   — fixed numeric literal pulled directly from YAML
      self_   — the current signal's post-transform value (only valid in
                `apply:` and per-signal `derive:` contexts)
      signal  — a name to look up in the latest-value cache
    """
    kind: str           # 'const' | 'self_' | 'signal'
    value: Any          # float for const, str for signal, None for self_

    @classmethod
    def parse(cls, spec: Any) -> "Binding":
        if spec == "$self":
            return cls(kind="self_", value=None)
        if isinstance(spec, (int, float)) and not isinstance(spec, bool):
            return cls(kind="const", value=float(spec))
        if isinstance(spec, str):
            return cls(kind="signal", value=spec)
        raise BindingError(
            f"binding spec must be $self, a number, or a signal name; "
            f"got {spec!r}",
        )

    def resolve(self, self_value: Optional[float], latest: dict[str, float]) -> float:
        if self.kind == "const":
            return float(self.value)
        if self.kind == "self_":
            if self_value is None:
                raise BindingError(
                    "$self binding not available in this context "
                    "(only valid in apply: and per-signal derive:)",
                )
            return self_value
        if self.kind == "signal":
            try:
                return latest[self.value]
            except KeyError:
                raise BindingError(
                    f"signal {self.value!r} not in latest-value cache; "
                    f"derivation deferred",
                ) from None
        raise BindingError(f"unknown binding kind {self.kind!r}")


@dataclass(frozen=True)
class FormulaApplication:
    """A compiled formula + binding plan."""
    name: str
    fn: Callable
    bindings: dict[str, Binding]    # formula input name → Binding

    def __call__(
        self,
        self_value: Optional[float],
        latest: dict[str, float],
    ) -> float:
        kwargs = {
            input_name: binding.resolve(self_value, latest)
            for input_name, binding in self.bindings.items()
        }
        return self.fn(**kwargs)


# ── pipeline step types ────────────────────────────────────────────────

@dataclass(frozen=True)
class ApplyStep:
    """A `apply:` step: transforms a signal's running value in place."""
    app: FormulaApplication

    def run(self, value: float, latest: dict[str, float]) -> float:
        return self.app(self_value=value, latest=latest)


@dataclass(frozen=True)
class DeriveStep:
    """A per-signal `derive:` step: emits a new named signal."""
    output_name: str
    app: FormulaApplication


@dataclass(frozen=True)
class CrossDerived:
    """Top-level `derived:` entry — cross-signal derived emission."""
    output_name: str
    app: FormulaApplication


@dataclass(frozen=True)
class MethodStep:
    """`methods:` entry — non-arithmetic derivation (lookup, hysteresis,
    etc.). Handler is registered in METHOD_HANDLERS."""
    output_name: str
    method_name: str
    handler: Callable
    input_signals: tuple[str, ...]
    params: dict[str, Any]

    def run(self, latest: dict[str, float]) -> float:
        signals = [latest[s] for s in self.input_signals]
        return self.handler(*signals, **self.params)


# ── signal processor ───────────────────────────────────────────────────

@dataclass
class SignalProcessor:
    """Pipeline for one signal coming out of cantools.

    Order of operations:
      1. Run `apply` steps in sequence (each replaces the running value)
      2. Determine the output name (rename_to overrides the raw name)
      3. Emit (output_name, value); also emit (canonical, value) if set
      4. For each `derive`, compute and emit using current value + cache
    """
    raw_name: str
    apply_steps: tuple[ApplyStep, ...] = ()
    rename_to: Optional[str] = None
    canonical: Optional[str] = None
    derives: tuple[DeriveStep, ...] = ()

    def process(
        self,
        value: float,
        latest: dict[str, float],
    ) -> list[tuple[str, float]]:
        v = value
        for step in self.apply_steps:
            v = step.run(v, latest)
        out_name = self.rename_to or self.raw_name
        emissions: list[tuple[str, float]] = [(out_name, v)]
        latest[out_name] = v
        if self.canonical and self.canonical != out_name:
            emissions.append((self.canonical, v))
            latest[self.canonical] = v
        for d in self.derives:
            try:
                dv = d.app(self_value=v, latest=latest)
            except (BindingError, FormulaError):
                # An input wasn't ready; skip this derive for now.
                continue
            emissions.append((d.output_name, dv))
            latest[d.output_name] = dv
        return emissions


# ── method registry ────────────────────────────────────────────────────

METHOD_HANDLERS: dict[str, Callable] = {}


def register_method(name: str):
    def decorator(fn: Callable) -> Callable:
        METHOD_HANDLERS[name] = fn
        return fn
    return decorator


@register_method("rpm_over_wheel_speed_ratio")
def _gear_from_rpm_wheel(
    rpm: float,
    *wheel_speeds_mph: float,
    ratios: dict[str, float],
    final_drive: float,
    tire_circumference_m: float,
    min_speed_kmh: float = 5.0,
) -> int:
    """Derive gear index from RPM and wheel-speed ratio.

    PDF §9 says MSS54HP doesn't broadcast gear. We compute the observed
    gearbox+final-drive ratio:
        observed = rpm * tire_circ * 3.6 / (avg_kmh * 60 * final_drive)
    then return the gear whose ratio is closest. Below `min_speed_kmh`
    we return 0 (neutral/coasting) to avoid divide-by-near-zero noise.
    """
    if not wheel_speeds_mph:
        return 0
    avg_mph = sum(wheel_speeds_mph) / len(wheel_speeds_mph)
    avg_kmh = avg_mph * 1.609344
    if avg_kmh < min_speed_kmh:
        return 0
    observed = rpm * tire_circumference_m * 3.6 / (avg_kmh * 60 * final_drive)
    return int(
        min(ratios.items(), key=lambda kv: abs(float(kv[1]) - observed))[0],
    )


# ── top-level config ───────────────────────────────────────────────────

@dataclass
class CarConfig:
    """Loaded per-car post-processing config."""
    car_id: str
    processors: dict[str, SignalProcessor]   # by DBC raw signal name
    cross_derived: tuple[CrossDerived, ...]
    methods: tuple[MethodStep, ...]
    formulas: FormulaRegistry

    def process_decoded_frame(
        self,
        decoded: dict[str, Any],
        latest: dict[str, float],
    ) -> list[tuple[str, float]]:
        """Run the full pipeline for one decoded frame.

        `decoded` is the dict returned by cantools.decode_message().
        `latest` is the cross-frame latest-value cache (mutated). The
        returned list is the full set of (name, value) pairs to sink.
        """
        emissions: list[tuple[str, float]] = []
        for raw_name, raw_value in decoded.items():
            try:
                fvalue = float(raw_value)
            except (TypeError, ValueError):
                continue
            proc = self.processors.get(raw_name)
            if proc is None:
                # Unmapped — emit as-is at native name, update cache.
                latest[raw_name] = fvalue
                emissions.append((raw_name, fvalue))
                continue
            emissions.extend(proc.process(fvalue, latest))
        # Cross-signal derived: try each, skip if inputs unavailable.
        for cd in self.cross_derived:
            try:
                dv = cd.app(self_value=None, latest=latest)
            except (BindingError, FormulaError):
                continue
            emissions.append((cd.output_name, dv))
            latest[cd.output_name] = dv
        # Methods (gear etc.): try each, skip if any input missing.
        for m in self.methods:
            try:
                mv = m.run(latest)
            except KeyError:
                continue
            emissions.append((m.output_name, float(mv)))
            latest[m.output_name] = float(mv)
        return emissions


# ── loader ─────────────────────────────────────────────────────────────

def _build_application(
    formulas: FormulaRegistry,
    formula_name: str,
    yaml_bind: dict[str, Any] | None,
    self_input_default: bool,
) -> FormulaApplication:
    fn = formulas.get(formula_name)
    declared_inputs = tuple(getattr(fn, "formula_inputs", ()))
    bindings: dict[str, Binding] = {}
    yaml_bind = yaml_bind or {}
    for input_name in declared_inputs:
        if input_name in yaml_bind:
            bindings[input_name] = Binding.parse(yaml_bind[input_name])
        elif self_input_default and input_name == declared_inputs[0]:
            bindings[input_name] = Binding(kind="self_", value=None)
        else:
            raise BindingError(
                f"formula {formula_name!r}: no binding for input "
                f"{input_name!r}",
            )
    extras = set(yaml_bind) - set(declared_inputs)
    if extras:
        raise BindingError(
            f"formula {formula_name!r}: unknown binding key(s) "
            f"{sorted(extras)}; declared inputs are {list(declared_inputs)}",
        )
    return FormulaApplication(name=formula_name, fn=fn, bindings=bindings)


def _build_apply_step(formulas: FormulaRegistry, item: dict) -> ApplyStep:
    # Shortcuts first
    if item.get("sign_flip") is True:
        return ApplyStep(
            app=_build_application(formulas, "negate", None, self_input_default=True),
        )
    if "bias" in item and "formula" not in item:
        return ApplyStep(
            app=_build_application(
                formulas, "offset", {"b": item["bias"]}, self_input_default=True,
            ),
        )
    if "formula" not in item:
        raise FormulaError(
            f"apply: entry must contain 'formula' (or 'sign_flip'/'bias'); "
            f"got {item!r}",
        )
    return ApplyStep(
        app=_build_application(
            formulas, item["formula"], item.get("bind"),
            self_input_default=True,
        ),
    )


def _build_derive_step(formulas: FormulaRegistry, item: dict) -> DeriveStep:
    if "name" not in item or "formula" not in item:
        raise FormulaError(
            f"derive: entry must contain 'name' and 'formula'; got {item!r}",
        )
    return DeriveStep(
        output_name=item["name"],
        app=_build_application(
            formulas, item["formula"], item.get("bind"),
            self_input_default=True,
        ),
    )


def _build_cross_derived(formulas: FormulaRegistry, name: str, item: dict) -> CrossDerived:
    if "formula" not in item:
        raise FormulaError(
            f"derived.{name}: entry must contain 'formula'; got {item!r}",
        )
    return CrossDerived(
        output_name=name,
        app=_build_application(
            formulas, item["formula"], item.get("bind"),
            self_input_default=False,
        ),
    )


def _build_method(name: str, item: dict) -> MethodStep:
    method_name = item.get("method")
    if not method_name or method_name not in METHOD_HANDLERS:
        raise FormulaError(
            f"methods.{name}: unknown method {method_name!r}; "
            f"registered: {sorted(METHOD_HANDLERS)}",
        )
    inputs = tuple(item.get("inputs") or ())
    params = {
        k: v for k, v in item.items() if k not in ("method", "inputs")
    }
    return MethodStep(
        output_name=name,
        method_name=method_name,
        handler=METHOD_HANDLERS[method_name],
        input_signals=inputs,
        params=params,
    )


def load_car_config(
    yaml_path: str | Path,
    *,
    formulas: Optional[FormulaRegistry] = None,
) -> CarConfig:
    """Load a per-car YAML and build a ready-to-run CarConfig.

    The shared formula library is loaded first; the car YAML may add
    car-specific formulas which override / extend it. Validation
    happens at load time — any unknown formula reference, malformed
    binding, or unregistered method name raises before the first frame
    is ever decoded.
    """
    import yaml
    yaml_path = Path(yaml_path)
    with open(yaml_path) as fh:
        cfg = yaml.safe_load(fh) or {}

    if formulas is None:
        formulas = load_standard_library()
    car_formulas = cfg.get("formulas")
    if car_formulas:
        # Reuse register() for each car-local formula
        for fname, fdef in car_formulas.items():
            formulas.register(
                fname,
                fdef.get("expr", ""),
                fdef.get("inputs") or [],
                **{k: v for k, v in fdef.items() if k not in ("inputs", "expr")},
            )

    processors: dict[str, SignalProcessor] = {}
    signals_block = cfg.get("signals") or {}
    if not isinstance(signals_block, dict):
        raise FormulaError(
            f"{yaml_path}: 'signals:' must be a mapping",
        )
    for raw_name, sdef in signals_block.items():
        sdef = sdef or {}
        apply_steps = tuple(
            _build_apply_step(formulas, item)
            for item in (sdef.get("apply") or [])
        )
        derives = tuple(
            _build_derive_step(formulas, item)
            for item in (sdef.get("derive") or [])
        )
        processors[raw_name] = SignalProcessor(
            raw_name=raw_name,
            apply_steps=apply_steps,
            rename_to=sdef.get("rename_to"),
            canonical=sdef.get("canonical"),
            derives=derives,
        )

    cross_block = cfg.get("derived") or {}
    cross_derived = tuple(
        _build_cross_derived(formulas, name, item)
        for name, item in cross_block.items()
    )

    methods_block = cfg.get("methods") or {}
    methods = tuple(
        _build_method(name, item) for name, item in methods_block.items()
    )

    return CarConfig(
        car_id=str(cfg.get("car", {}).get("model", yaml_path.stem)),
        processors=processors,
        cross_derived=cross_derived,
        methods=methods,
        formulas=formulas,
    )
