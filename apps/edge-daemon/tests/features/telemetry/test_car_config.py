"""Tests for src/pitwall/features/telemetry/car_config.py.

Three categories:

  1. Loader — `load_car_config('data/cars/bmw_e46_m3.yaml')` produces a
     CarConfig with the right shape (22 signal pipelines, 2 cross-derived,
     1 method, the right standard formulas resolved).

  2. Pipeline correctness — exercise every per-signal transform the BMW
     YAML actually configures: sign flip on vertical_accel_g, mph→m/s on
     speed_mph, psi→bar on brake_press_psi, rename oil_temp_f →
     oil_filter_temp_f + °F→°C derive, lat/lon canonical aliases, the
     cross-signal combo_g, the rpm_over_wheel_speed_ratio gear method.

  3. Bindings & validation — $self/signal/numeric Binding resolution,
     and the error paths (unknown formula, missing binding, unregistered
     method name).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pitwall.features.telemetry.car_config import (
    Binding,
    BindingError,
    CarConfig,
    METHOD_HANDLERS,
    _gear_from_rpm_wheel,
    load_car_config,
)
from pitwall.features.telemetry.formula import (
    FormulaError,
    FormulaRegistry,
    load_standard_library,
)


ROOT = Path(__file__).resolve().parents[3]
BMW_YAML = ROOT / "data" / "cars" / "bmw_e46_m3.yaml"


# ── 1. Loader ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def bmw() -> CarConfig:
    return load_car_config(str(BMW_YAML))


def test_bmw_yaml_loads(bmw: CarConfig):
    assert bmw.car_id == "M3"


def test_bmw_yaml_has_expected_shape(bmw: CarConfig):
    # These counts are load-bearing; if a YAML change moves them, the
    # capability matrix doc + the README ingest section need updates too.
    assert len(bmw.processors) == 22
    assert len(bmw.cross_derived) == 2
    assert len(bmw.methods) == 1


def test_bmw_yaml_specific_pipelines_present(bmw: CarConfig):
    # Spot-check the signal names that drive the pipeline behaviour
    for raw_name in (
        "vertical_accel_g",   # has sign-flip
        "speed_mph",           # derives speed_ms + speed_kmh
        "oil_temp_f",          # renames to oil_filter_temp_f + derives _c
        "brake_press_psi",     # derives brake_bar
        "lateral_accel_g",     # canonical g_lat
        "inline_accel_g",      # canonical g_long
        "gps_lat",             # canonical lat
        "gps_lon",             # canonical lon
    ):
        assert raw_name in bmw.processors, (
            f"missing pipeline for {raw_name}; YAML may have shifted"
        )


def test_bmw_yaml_cross_derived_names(bmw: CarConfig):
    names = {cd.output_name for cd in bmw.cross_derived}
    assert names == {"combo_g", "wheel_speed_avg_mph"}


def test_bmw_yaml_method_registered(bmw: CarConfig):
    m = bmw.methods[0]
    assert m.output_name == "gear_position"
    assert m.method_name == "rpm_over_wheel_speed_ratio"
    assert "rpm" in m.input_signals
    assert "rpm_over_wheel_speed_ratio" in METHOD_HANDLERS


# ── 2. Pipeline correctness on real frames ─────────────────────────────

@pytest.fixture
def latest():
    """Fresh cache per test so signals don't carry across."""
    return {}


def _process_one(bmw, latest, raw_name, raw_value, extra=None):
    """Helper: route a single signal through process_decoded_frame."""
    decoded = {raw_name: raw_value}
    if extra:
        decoded.update(extra)
    return bmw.process_decoded_frame(decoded, latest)


def test_vertical_accel_sign_flip(bmw: CarConfig, latest):
    """PDF §6.2: vertical_accel_g raw -0.99 g must emit as +0.99 g (the
    YAML's `apply: [{sign_flip: true}]` step). Also emits as canonical
    `g_vert`."""
    em = dict(_process_one(bmw, latest, "vertical_accel_g", -0.99))
    assert em["vertical_accel_g"] == pytest.approx(0.99, abs=1e-9)
    assert em["g_vert"] == pytest.approx(0.99, abs=1e-9)


def test_speed_mph_to_ms_derive(bmw: CarConfig, latest):
    """speed_mph 100 mph → emits speed_ms = 100 × 0.44704 = 44.704 m/s,
    plus speed_kmh = 100 × 1.609344 = 160.9344 km/h."""
    em = dict(_process_one(bmw, latest, "speed_mph", 100.0))
    assert em["speed_mph"] == pytest.approx(100.0, abs=1e-9)
    assert em["speed_ms"] == pytest.approx(44.704, abs=1e-6)
    assert em["speed_kmh"] == pytest.approx(160.9344, abs=1e-6)


def test_brake_press_psi_to_bar_derive(bmw: CarConfig, latest):
    """brake_press_psi 145.0377 psi → brake_bar ≈ 10 bar."""
    em = dict(_process_one(bmw, latest, "brake_press_psi", 145.0377))
    # 1 psi = 0.0689476 bar exactly per the standard library
    assert em["brake_bar"] == pytest.approx(145.0377 * 0.0689476, abs=1e-6)


def test_oil_temp_f_rename_and_unit_derive(bmw: CarConfig, latest):
    """PDF's 'Oil Filter Temp' is bound to DBC `oil_temp_f`. The YAML
    renames it to `oil_filter_temp_f` AND emits the °C unit twin.
    The raw DBC name must no longer appear in the emissions — that
    was the whole point of the rename."""
    em = dict(_process_one(bmw, latest, "oil_temp_f", 212.0))
    assert "oil_filter_temp_f" in em
    assert em["oil_filter_temp_f"] == pytest.approx(212.0, abs=1e-9)
    assert em["oil_filter_temp_c"] == pytest.approx(100.0, abs=1e-9)  # 212 °F = 100 °C
    assert "oil_temp_f" not in em, (
        "DBC name oil_temp_f leaked through despite rename_to"
    )


def test_lateral_accel_canonical_alias(bmw: CarConfig, latest):
    """lateral_accel_g has `canonical: g_lat` — emit under both names
    with the same value."""
    em = dict(_process_one(bmw, latest, "lateral_accel_g", 1.5))
    assert em["lateral_accel_g"] == pytest.approx(1.5)
    assert em["g_lat"] == pytest.approx(1.5)


def test_gps_canonical_aliases(bmw: CarConfig, latest):
    em = dict(_process_one(bmw, latest, "gps_lat", 37.123456,
                            extra={"gps_lon": -122.345678}))
    assert em["lat"] == pytest.approx(37.123456)
    assert em["lon"] == pytest.approx(-122.345678)


def test_combo_g_cross_derived(bmw: CarConfig, latest):
    """combo_g = sqrt(g_lat² + g_long²); fires after the per-signal
    pipelines emit g_lat + g_long into the latest-value cache."""
    em = dict(_process_one(bmw, latest, "lateral_accel_g", 0.6,
                            extra={"inline_accel_g": 0.8}))
    assert em["combo_g"] == pytest.approx(1.0, abs=1e-9)


def test_combo_g_skips_when_inputs_missing(bmw: CarConfig, latest):
    """If only g_lat is in the cache (no g_long yet), combo_g shouldn't
    fire — the binding can't resolve."""
    em = dict(_process_one(bmw, latest, "lateral_accel_g", 0.5))
    assert "combo_g" not in em


def test_wheel_speed_avg_cross_derived(bmw: CarConfig, latest):
    em = dict(bmw.process_decoded_frame({
        "wheel_speed_fl_mph": 100.0,
        "wheel_speed_fr_mph": 102.0,
        "wheel_speed_rl_mph":  98.0,
        "wheel_speed_rr_mph": 100.0,
    }, latest))
    assert em["wheel_speed_avg_mph"] == pytest.approx(100.0, abs=1e-9)


def test_gear_method_picks_correct_gear(bmw: CarConfig, latest):
    """rpm=4000, wheels 70 mph each → 70 mph ≈ 112.6 km/h. Method computes
    observed ratio rpm * tire_circ * 3.6 / (kmh * 60 * final_drive). For
    BMW S54 4th gear ratio is 1.226. With tire_circ=1.998m, final=3.62,
    the gear-4 RPM at 112.6 km/h works out to ~4060 — close to 4000, so
    gear_position should pick 4."""
    em = dict(bmw.process_decoded_frame({
        "rpm": 4000.0,
        "wheel_speed_rl_mph": 70.0,
        "wheel_speed_rr_mph": 70.0,
    }, latest))
    assert em["gear_position"] == 4


def test_gear_method_zero_at_rest(bmw: CarConfig, latest):
    """Below min_speed_kmh (5 km/h default), method returns 0 to avoid
    divide-by-near-zero noise."""
    em = dict(bmw.process_decoded_frame({
        "rpm": 800.0,
        "wheel_speed_rl_mph": 0.0,
        "wheel_speed_rr_mph": 0.0,
    }, latest))
    assert em["gear_position"] == 0


# ── 3. Bindings & validation ───────────────────────────────────────────

def test_binding_parse_self():
    b = Binding.parse("$self")
    assert b.kind == "self_"


def test_binding_parse_signal():
    b = Binding.parse("g_lat")
    assert b.kind == "signal" and b.value == "g_lat"


def test_binding_parse_numeric_int():
    b = Binding.parse(5)
    assert b.kind == "const" and b.value == 5.0


def test_binding_parse_numeric_float():
    b = Binding.parse(0.42)
    assert b.kind == "const" and b.value == pytest.approx(0.42)


def test_binding_parse_bool_rejected():
    # booleans are int subclass but logically wrong for bindings
    with pytest.raises(BindingError):
        Binding.parse(True)


def test_binding_resolve_self_value():
    b = Binding(kind="self_", value=None)
    assert b.resolve(self_value=42.0, latest={}) == 42.0


def test_binding_resolve_self_without_context_raises():
    b = Binding(kind="self_", value=None)
    with pytest.raises(BindingError):
        b.resolve(self_value=None, latest={})


def test_binding_resolve_signal_missing_raises():
    b = Binding(kind="signal", value="g_unknown")
    with pytest.raises(BindingError):
        b.resolve(self_value=None, latest={})


def test_binding_resolve_signal_present():
    b = Binding(kind="signal", value="g_lat")
    assert b.resolve(self_value=None, latest={"g_lat": 1.1}) == 1.1


# ── 4. Method handler directly ─────────────────────────────────────────

def test_gear_handler_finds_closest_ratio():
    # Forge a scenario that resolves cleanly to gear 5 (ratio 1.000)
    # rpm = (kmh/3.6) * 60 / tire_circ * final_drive * gear_ratio
    # at 120 km/h, gear-5: rpm = 120/3.6 * 60 / 1.998 * 3.62 * 1.000 ≈ 3624
    g = _gear_from_rpm_wheel(
        3624.0, 120.0 / 1.609344, 120.0 / 1.609344,  # 4 wheel speeds in mph (only 2 here)
        ratios={"1": 4.227, "2": 2.528, "3": 1.669, "4": 1.226, "5": 1.000, "6": 0.828},
        final_drive=3.62,
        tire_circumference_m=1.998,
    )
    assert g == 5


def test_gear_handler_returns_zero_under_min_speed():
    g = _gear_from_rpm_wheel(
        800.0, 0.1, 0.1,                          # almost-stationary wheels
        ratios={"1": 4.227, "2": 2.528, "5": 1.000},
        final_drive=3.62,
        tire_circumference_m=1.998,
        min_speed_kmh=5.0,
    )
    assert g == 0


# ── 5. Loader error paths ──────────────────────────────────────────────

def test_load_with_unknown_formula_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "car: { model: TEST }\n"
        "signals:\n"
        "  some_sig:\n"
        "    apply:\n"
        "      - { formula: not_a_real_formula }\n"
    )
    with pytest.raises(FormulaError):
        load_car_config(str(bad))


def test_load_with_unbound_input_raises(tmp_path):
    """`linear` formula has inputs [x, a, b]; without bind for a + b,
    the loader can't auto-bind those (only the first input gets $self
    as default), so this must fail with BindingError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "car: { model: TEST }\n"
        "signals:\n"
        "  speed_mph:\n"
        "    apply:\n"
        "      - { formula: linear }\n"      # missing bind for a + b
    )
    with pytest.raises(BindingError):
        load_car_config(str(bad))


def test_load_with_unregistered_method_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "car: { model: TEST }\n"
        "methods:\n"
        "  fake_signal:\n"
        "    method: not_a_real_method\n"
        "    inputs: [rpm]\n"
    )
    with pytest.raises(FormulaError, match="unknown method"):
        load_car_config(str(bad))


def test_load_per_car_formula_overrides_standard(tmp_path):
    """Per-car YAML can declare a `formulas:` block that augments /
    overrides the shared library. Verify that a car-local formula is
    callable inside a signal pipeline."""
    bad = tmp_path / "ok.yaml"
    bad.write_text(
        "car: { model: TEST }\n"
        "formulas:\n"
        "  double_x:\n"
        "    inputs: [x]\n"
        "    expr: 'x * 2'\n"
        "signals:\n"
        "  speed_mph:\n"
        "    apply:\n"
        "      - { formula: double_x }\n"
    )
    cc = load_car_config(str(bad))
    em = dict(cc.process_decoded_frame({"speed_mph": 50.0}, {}))
    assert em["speed_mph"] == pytest.approx(100.0)


def test_load_with_custom_formula_registry(tmp_path):
    """Loader accepts a pre-built FormulaRegistry; in-memory tests can
    bypass file-system reads of standard.yaml."""
    bad = tmp_path / "ok.yaml"
    bad.write_text(
        "car: { model: TEST }\n"
        "signals:\n"
        "  speed_mph:\n"
        "    apply:\n"
        "      - { formula: triple }\n"
    )
    reg = FormulaRegistry()
    reg.register("triple", "x * 3", ["x"])
    cc = load_car_config(str(bad), formulas=reg)
    em = dict(cc.process_decoded_frame({"speed_mph": 10.0}, {}))
    assert em["speed_mph"] == pytest.approx(30.0)
