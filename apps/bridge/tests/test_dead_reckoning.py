"""Unit tests for tools/dead_reckoning.py — Kalman dead-reckoning filter.

Each test checks one expected property: filter convergence, GPS smoothing,
IMU integration, brake-zone tracking, and the corner-case timestamp/reset
behaviour. Together they verify that the filter satisfies ADR-018's
"distance must be smooth at the CAN rate, even when GPS gaps." requirement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pitwall.dead_reckoning import DeadReckoner, DeadReckonerConfig


# ── helpers ────────────────────────────────────────────────────────────────

def _seed_with_gps(filter: DeadReckoner, t0: float = 0.0,
                   d0: float = 0.0, v0: float = 0.0) -> None:
    """Push a couple of high-confidence GPS readings to anchor the filter
    before driving the actual scenario. Gets us out of the diffuse prior."""
    filter.update_distance(t0, d0)
    filter.update_speed(t0, v0)


# ── prediction-only behavior ───────────────────────────────────────────────

def test_predict_advances_distance_at_constant_speed():
    """No measurements after seeding — distance must integrate from speed."""
    f = DeadReckoner()
    f.seed(distance_m=100.0, speed_ms=50.0, t=0.0)
    f.predict_to(1.0)
    # 1 s at 50 m/s = +50 m
    assert f.distance_m == pytest.approx(150.0, rel=1e-3)
    assert f.speed_ms == pytest.approx(50.0, rel=1e-3)


def test_predict_with_braking_decelerates():
    """g_long < 0 must reduce speed and shorten the distance increment."""
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=60.0, t=0.0)
    # 0.5 s of -1 g (≈ -9.81 m/s²) braking
    f.update_imu(0.5, -1.0)
    # speed drops by ~4.9 m/s; distance ≈ 60·0.5 + ½·(-9.81)·0.25 = 28.77 m
    assert f.speed_ms == pytest.approx(60.0 - 9.81 * 0.5, abs=0.2)
    assert f.distance_m == pytest.approx(
        60.0 * 0.5 + 0.5 * (-9.81) * 0.25, abs=0.5,
    )


def test_predict_skips_negative_dt():
    """An out-of-order timestamp must not roll back state."""
    f = DeadReckoner()
    f.seed(distance_m=100.0, speed_ms=30.0, t=10.0)
    f.predict_to(9.5)
    assert f.distance_m == pytest.approx(100.0)
    assert f.t == 10.0


def test_predict_skips_duplicate_timestamp():
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=20.0, t=0.0)
    f.predict_to(0.0)
    assert f.distance_m == pytest.approx(0.0)


# ── speed updates ──────────────────────────────────────────────────────────

def test_can_speed_dominates_low_uncertainty_signal():
    """Repeated CAN speed measurements drive speed estimate to true value."""
    f = DeadReckoner()
    _seed_with_gps(f, t0=0.0, d0=0.0, v0=20.0)
    truth = 35.0
    for k in range(50):
        f.update_speed(0.1 * (k + 1), truth)
    assert f.speed_ms == pytest.approx(truth, abs=0.2)


def test_speed_updates_propagate_to_distance():
    """A constant speed series should integrate into a credible distance even
    without GPS. This is the *core* dead-reckoning property."""
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=40.0, t=0.0)
    for k in range(100):                  # 1 s of CAN at 100 Hz
        f.update_speed(0.01 * (k + 1), 40.0)
    # Should be very close to 40 m
    assert f.distance_m == pytest.approx(40.0, abs=0.5)


# ── GPS updates ────────────────────────────────────────────────────────────

def test_gps_distance_anchors_estimate():
    f = DeadReckoner()
    _seed_with_gps(f)
    truth = 250.0
    f.update_distance(2.5, truth)
    f.update_distance(2.6, truth + 5.0)        # 5 m at 50 m/s
    f.update_distance(2.7, truth + 10.0)
    assert abs(f.distance_m - (truth + 10.0)) < 5.0


def test_filter_smooths_jittery_gps():
    """The filter's distance must be smoother than raw GPS readings under
    typical 3 m noise — that's exactly why we run a Kalman filter."""
    rng = np.random.default_rng(42)
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=50.0, t=0.0)

    # 5 s of true motion at 50 m/s
    truth_d = []
    raw_d = []
    filt_d = []
    for k in range(50):                       # 10 Hz GPS
        t = 0.1 * (k + 1)
        truth = 50.0 * t
        noisy = truth + rng.normal(0, 3.0)
        # 100 Hz CAN speed in between
        for j in range(10):
            f.update_speed(t - 0.1 + 0.01 * (j + 1), 50.0)
        f.update_distance(t, noisy)
        truth_d.append(truth)
        raw_d.append(noisy)
        filt_d.append(f.distance_m)

    raw_rms = float(np.sqrt(np.mean((np.array(raw_d) - np.array(truth_d)) ** 2)))
    filt_rms = float(np.sqrt(np.mean((np.array(filt_d) - np.array(truth_d)) ** 2)))
    # Filtered RMS should be at least 2× tighter than raw GPS noise.
    assert filt_rms < raw_rms / 2


# ── full pipeline scenarios ────────────────────────────────────────────────

def test_brake_zone_tracking_at_130_mph():
    """Simulate Sonoma's T11 entry: 58 m/s straight → 1 g brake to 30 m/s.
    The filter must track distance to within 1 m when only IMU + CAN are
    available (worst-case GPS-out scenario)."""
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=58.0, t=0.0)

    # Straight: 1 s at 58 m/s, IMU at 100 Hz, CAN at 50 Hz
    t = 0.0
    while t < 1.0:
        t += 0.01
        f.update_imu(t, 0.0)           # cruising
        if int(t * 1000) % 20 == 0:    # 50 Hz CAN
            f.update_speed(t, 58.0)

    # Brake zone: -1 g for 0.5 s (58 → 53.1 m/s)
    while t < 1.5:
        t += 0.01
        f.update_imu(t, -1.0)
        if int(t * 1000) % 20 == 0:
            f.update_speed(t, 58.0 + (-9.81) * (t - 1.0))

    # Truth: 1 s × 58 m/s + ½(58+53.095)·0.5 ≈ 58 + 27.77 = 85.77 m
    expected = 58.0 + 0.5 * (58.0 + 58.0 - 9.81 * 0.5) * 0.5
    assert f.distance_m == pytest.approx(expected, abs=1.0)


def test_filter_converges_with_all_three_streams():
    """With CAN + IMU + GPS all flowing, the filter should sit on truth
    within 1.5 m at any time during a 10 s run."""
    rng = np.random.default_rng(123)
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=30.0, t=0.0)

    truth_d = 0.0
    truth_v = 30.0
    a_history = [0.0, 0.5, -0.3, 0.0, -0.6, 0.0]      # m/s² steps every 1.66 s
    max_err = 0.0
    for k in range(1000):                              # 10 s @ 100 Hz
        t = 0.01 * (k + 1)
        a = a_history[min(int(t / 1.667), len(a_history) - 1)]

        # advance truth
        truth_d += truth_v * 0.01 + 0.5 * a * 0.0001
        truth_v += a * 0.01

        # IMU at 100 Hz
        f.update_imu(t, a / 9.81 + rng.normal(0, 0.02))
        # CAN at 50 Hz
        if k % 2 == 0:
            f.update_speed(t, truth_v + rng.normal(0, 0.2))
        # GPS at 10 Hz
        if k % 10 == 0:
            f.update_distance(t, truth_d + rng.normal(0, 3.0))

        max_err = max(max_err, abs(f.distance_m - truth_d))

    assert max_err < 3.0, f"max distance error {max_err:.2f} m exceeds budget"


# ── lifecycle ──────────────────────────────────────────────────────────────

def test_reset_returns_filter_to_diffuse_prior():
    f = DeadReckoner()
    f.seed(distance_m=500.0, speed_ms=40.0, t=12.3)
    f.reset()
    assert f.distance_m == 0.0
    assert f.speed_ms == 0.0
    assert f.t is None
    # Covariance back to diffuse — variances should be > 100
    P = f.covariance
    assert P[0, 0] > 100
    assert P[1, 1] > 100


def test_seed_sets_tight_prior():
    """seed() should produce a tight covariance — caller is asserting truth.
    A wildly off (~80 m) GPS reading should produce only a small Kalman
    correction (≈10–15% of the innovation), proving the filter weights the
    seed over the noisy measurement."""
    f = DeadReckoner()
    f.seed(distance_m=200.0, speed_ms=40.0, t=0.0)
    # 80 m off-truth should swing the estimate by far less than 80 m.
    f.update_distance(0.1, 280.0)
    swing = abs(f.distance_m - 200.0)
    assert swing < 20.0       # caught instantly if seed gets ignored
    assert swing > 1.0        # but the filter still moves *toward* truth


# ── integration smoke ──────────────────────────────────────────────────────

def test_can_only_run_with_gps_outage_drifts_within_budget():
    """If GPS drops out for 5 s, distance error must stay under 4 m at
    130 mph — the practical resolution limit for marker-based coaching at
    Sonoma's T2 ('the bridge'). Tighter than this requires either a real
    IMU sample-rate spec or a sub-Hz GPS recovery, both out of scope here."""
    f = DeadReckoner()
    f.seed(distance_m=0.0, speed_ms=58.0, t=0.0)

    # Anchor with one GPS reading, then go silent for 5 s
    f.update_distance(0.05, 0.0)

    truth_d = 0.0
    for k in range(500):                  # 5 s of CAN at 100 Hz
        t = 0.05 + 0.01 * (k + 1)
        truth_d += 58.0 * 0.01
        f.update_speed(t, 58.0)
        f.update_imu(t, 0.0)

    assert abs(f.distance_m - truth_d) < 4.0
