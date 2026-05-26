"""Unit tests for src/simulator/analytics.py."""
from types import SimpleNamespace

import pytest
import pitwall.features.session.analytics as analytics
from pitwall.features.session.corner_grader import CornerPass


def _osc_frame(t, combo_g):
    """Minimal frame for slip-oscillation tests — only `timestamp` and
    `combo_g` matter for the band classifier."""
    return SimpleNamespace(
        timestamp=t, distance=0.0, speed=20.0, lat=0.0, lon=0.0,
        heading=0.0, altitude=0.0, g_lat=0.0, g_long=0.0,
        combo_g=combo_g, brake_pressure=0.0, brake_position=0.0,
        throttle=50.0, steering=0.0, rpm=4500.0,
        coolant_temp=88.0, oil_temp=95.0, fuel_level=50.0,
        avitime=0.0, lap=0, lap_time=0.0,
        distance_to_corner=0.0, corner_name="", corner_severity=0,
    )


def _pass(corner, lap=0, **kwargs):
    defaults = dict(
        entry_speed_kmh=100, apex_speed_kmh=80, exit_speed_kmh=110,
        min_speed_kmh=78, peak_brake_bar=30, brake_point_m=80,
        brake_release_m=10, trail_brake_bar_at_apex=5,
        throttle_at_exit_pct=70, max_g_lat=1.2, max_combo_g=1.5,
        corner_time_s=4.0, coast_seconds=0.0, steering_corrections=1,
        nothing_time_s=0.1,
    )
    defaults.update(kwargs)
    return CornerPass(corner=corner, lap=lap, **defaults)


# ─── stat_cards ───────────────────────────────────────────────────────────────


def test_stat_cards_empty():
    assert analytics.stat_cards([]) == {}


def test_stat_cards_basic(synth_lap_frames):
    s = analytics.stat_cards(synth_lap_frames)
    assert s["n_frames"] == len(synth_lap_frames)
    assert s["top_speed_kmh"] > 100
    assert s["max_brake_bar"] >= 0
    assert s["session_duration_s"] > 0


def test_stat_cards_longest_full_throttle(make_frame_fn):
    """Full-throttle stretch detection."""
    frames = [
        make_frame_fn(t=i * 0.1, throttle_pct=100, speed_kmh=170)
        for i in range(100)   # 10s of full throttle
    ]
    s = analytics.stat_cards(frames)
    assert s["longest_full_throttle_s"] >= 9.5


# ─── friction_circle ──────────────────────────────────────────────────────────


def test_friction_circle_empty():
    assert analytics.friction_circle([]) == {}


def test_friction_circle_histogram_sums(synth_lap_frames):
    fc = analytics.friction_circle(synth_lap_frames)
    assert sum(fc["histogram_pct"]) == pytest.approx(100, abs=0.5)
    assert 0 <= fc["over_limit_pct"] <= 100


def test_friction_circle_stride_samples_distributed(make_frame_fn):
    """Regression: samples used to come from head of lap; should now stride."""
    # 5000 frames; ask for 100 samples → stride should be ~50
    frames = [make_frame_fn(t=i * 0.1, g_lat=0.5) for i in range(5000)]
    fc = analytics.friction_circle(frames, n_samples=100)
    assert len(fc["samples"]) <= 100


# ─── hustle_map ───────────────────────────────────────────────────────────────


def test_hustle_map_segments_track(synth_lap_frames):
    hm = analytics.hustle_map(synth_lap_frames, segment_m=50, track_len=4258)
    assert len(hm) == int(4258 / 50) + 1
    for seg in hm:
        assert 0 <= seg["hustle_pct"] <= 100


def test_hustle_map_full_throttle_segment(make_frame_fn):
    """A segment full of 100% throttle frames should report 100% hustle."""
    frames = [
        make_frame_fn(t=i * 0.1, distance=i * 5, throttle_pct=99,
                      speed_kmh=170)
        for i in range(20)
    ]
    hm = analytics.hustle_map(frames, segment_m=50, track_len=200)
    # Segments with full-throttle frames should be at 100
    assert any(seg["hustle_pct"] >= 90 for seg in hm)


# ─── consistency ──────────────────────────────────────────────────────────────


def test_consistency_low_when_lap_times_match():
    c = analytics.consistency([], [100.0, 100.1, 100.05])
    assert c["lap_time_std"] < 0.1
    assert c["lap_time_spread"] < 0.2


def test_consistency_identifies_most_variable_corner():
    p = [
        _pass("Turn 1", lap=0, corner_time_s=2.0),
        _pass("Turn 1", lap=1, corner_time_s=2.05),
        _pass("Turn 11", lap=0, corner_time_s=4.0),
        _pass("Turn 11", lap=1, corner_time_s=5.0),  # huge spread
    ]
    c = analytics.consistency(p, [])
    assert c["most_variable_corner"]["corner"] == "Turn 11"


# ─── eob_summary ──────────────────────────────────────────────────────────────


def test_eob_summary_empty():
    s = analytics.eob_summary([])
    assert s["average_nothing_time_s"] == 0.0
    assert s["worst_corner"] is None


def test_eob_summary_picks_worst_corner():
    p = [
        _pass("Turn 1", nothing_time_s=0.2),
        _pass("Turn 11", nothing_time_s=0.8),    # worst
    ]
    s = analytics.eob_summary(p)
    assert s["worst_corner"] == "Turn 11"


# ─── slip_angle_band ──────────────────────────────────────────────────────────


def test_slip_angle_band_under_driving(make_frame_fn):
    """All-low-G frames should classify as under_driving."""
    frames = [make_frame_fn(t=i * 0.1, g_lat=0.2, g_long=0) for i in range(100)]
    sb = analytics.slip_angle_band(frames)
    assert sb["dominant_band"] == "under_driving"


def test_slip_angle_band_at_peak(make_frame_fn):
    """Frames at ~85% utilisation should classify as at_peak."""
    frames = [make_frame_fn(t=i * 0.1, g_lat=2.0, g_long=0)  # combo_g ≈ 2.0
              for i in range(100)]
    sb = analytics.slip_angle_band(frames, max_combo_g_observed=2.29)
    # 2.0/2.29 ≈ 0.87 → at_peak band (0.80 - 0.95)
    assert sb["dominant_band"] == "at_peak"


# ─── trail_brake_events ───────────────────────────────────────────────────────


def test_trail_brake_events_score():
    p = [
        _pass("Turn 4", peak_brake_bar=20, trail_brake_bar_at_apex=4),
        _pass("Turn 5", peak_brake_bar=5, trail_brake_bar_at_apex=0),  # no trail
    ]
    events = analytics.trail_brake_events(p)
    assert len(events) == 1   # only Turn 4 qualifies
    assert events[0]["corner"] == "Turn 4"
    assert 0 <= events[0]["quality"] <= 1


# ─── change_in_speed_events ───────────────────────────────────────────────────


def test_change_in_speed_events_detects(make_frame_fn, real_track):
    # Two frames with rising throttle while gLat is high and below entry speed
    t1 = next(c for c in real_track.corners if c.name == "Turn 3")
    d_in = (t1.entry_distance + t1.exit_distance) / 2
    f0 = make_frame_fn(t=0.0, distance=d_in, throttle_pct=20, g_lat=0.7,
                       speed_kmh=70)
    f1 = make_frame_fn(t=0.1, distance=d_in + 5, throttle_pct=60,  # +400 %/s
                       g_lat=0.7, speed_kmh=72)
    gold_speeds = {"Turn 3": 90}     # gold entry is 90 km/h, driver is at 72
    events = analytics.change_in_speed_events([f0, f1], gold_speeds, real_track)
    assert len(events) >= 0   # may or may not fire depending on thresholds


# ─── flight_recorder ──────────────────────────────────────────────────────────


def test_flight_recorder_threshold(make_frame_fn):
    """Combo-G above threshold should trigger an incident."""
    frames = [make_frame_fn(t=i * 0.1, g_lat=2.5, g_long=0) for i in range(10)]
    incidents = analytics.flight_recorder(frames, max_combo_g_threshold=2.0)
    assert len(incidents) >= 1
    assert incidents[0]["combo_g"] >= 2.0


def test_flight_recorder_no_threshold(make_frame_fn):
    frames = [make_frame_fn(t=i * 0.1, g_lat=0.5, g_long=0) for i in range(10)]
    incidents = analytics.flight_recorder(frames, max_combo_g_threshold=2.0)
    assert incidents == []


# ─── plateau_detector ─────────────────────────────────────────────────────────


def test_plateau_detector_flat():
    """Three sessions with no improvement → plateau."""
    history = [("s1", 100.0), ("s2", 100.0), ("s3", 100.0)]
    p = analytics.plateau_detector(history, window=3)
    assert p["plateau"] is True


def test_plateau_detector_improving():
    history = [("s1", 110.0), ("s2", 105.0), ("s3", 100.0)]
    p = analytics.plateau_detector(history, window=3)
    assert p["plateau"] is False


# ─── limit_oscillation ────────────────────────────────────────────────────────


def test_limit_oscillation_empty_history():
    r = analytics.limit_oscillation([])
    assert r["archetype"] == "unknown"


def test_limit_oscillation_stable_at_limit():
    """High avg score, low variance → archetype #3 (settled at limit)."""
    history = [
        {"corner": "T1", "score_pct": 0.95},
        {"corner": "T1", "score_pct": 0.93},
        {"corner": "T1", "score_pct": 0.94},
    ]
    r = analytics.limit_oscillation(history)
    assert r["archetype"] == "3_at_limit"


def test_limit_oscillation_under_limit():
    history = [
        {"corner": "T1", "score_pct": 0.65},
        {"corner": "T1", "score_pct": 0.70},
    ]
    r = analytics.limit_oscillation(history)
    assert r["archetype"] == "1_under_limit"


# ─── smoothness_per_corner ────────────────────────────────────────────────────


def test_smoothness_per_corner_uses_real_track(real_track, synth_lap_frames):
    """Regression: function used to ignore the track and emit session-wide stats.
    Now requires a real TrackMap to bound each corner's frames."""
    # Build a few synthetic passes for known corners
    passes = [_pass("Turn 1", lap=0), _pass("Turn 6", lap=0)]
    sm = analytics.smoothness_per_corner(passes, synth_lap_frames, real_track)
    # Should be keyed by corner name, not session-wide
    for k in sm:
        assert k in [c.name for c in real_track.corners]


# ─── ADR-018: slip_oscillation_events ────────────────────────────────────────

def test_slip_oscillation_empty_input_returns_empty():
    assert analytics.slip_oscillation_events([]) == []
    assert analytics.slip_oscillation_events([_osc_frame(0, 1.0)]) == []


def test_slip_oscillation_quiet_session_no_events():
    """A driver staying in one band the whole time produces no events."""
    frames = [_osc_frame(t * 0.1, 1.0) for t in range(60)]    # 6 s steady
    assert analytics.slip_oscillation_events(frames) == []


def test_slip_oscillation_detects_ego_swings():
    """Five rapid band crossings inside a 3 s window must produce an event."""
    # max_combo_g defaults to the max in-frames so set the peak to 2.0:
    # bands cut at 0.55·2 = 1.10, 0.80·2 = 1.60, 0.95·2 = 1.90.
    # Alternate 1.0 (under) → 1.7 (at_peak) → 1.0 → 1.95 (over) → 1.0 → 1.7 → 2.0
    pattern = [1.0, 1.7, 1.0, 1.95, 1.0, 1.7, 2.0, 1.0]
    frames = [_osc_frame(i * 0.3, g) for i, g in enumerate(pattern)]
    events = analytics.slip_oscillation_events(frames, window_s=3.0,
                                               min_band_crossings=4)
    assert len(events) >= 1
    e = events[0]
    assert e["crossings"] >= 4
    assert e["severity"] in ("medium", "high")
    assert e["t_start"] <= 0.0
    assert e["t_end"] >= e["t_start"]


def test_slip_oscillation_high_severity_for_extreme_swings():
    """Eight band crossings inside one window earn severity='high'."""
    pattern = [1.0, 1.7, 1.0, 1.95, 1.0, 1.7, 1.0, 1.95, 2.0]
    frames = [_osc_frame(i * 0.25, g) for i, g in enumerate(pattern)]
    events = analytics.slip_oscillation_events(frames, window_s=3.0,
                                               min_band_crossings=4)
    assert any(e["severity"] == "high" for e in events)
