"""Unit tests for src/simulator/highlight_finder.py."""
import pytest
from pitwall.features.session.highlight_finder import find_highlights, highlights_to_dict, Highlight
from pitwall.features.session.corner_grader import CornerPass
from pitwall.features.track.gold_standard import GoldStandard, GoldCornerPass


def _gold_for(corner: str, **kwargs) -> GoldCornerPass:
    defaults = dict(
        entry_speed_kmh=110, apex_speed_kmh=80, exit_speed_kmh=115,
        min_speed_kmh=78, peak_brake_bar=30,
        brake_point_m=80, brake_release_m=10,
        trail_brake_bar_at_apex=8, throttle_at_exit_pct=70,
        max_g_lat=1.2, max_combo_g=1.5, corner_time_s=4.0,
        apex_distance_m=100, entry_distance_m=80, exit_distance_m=140,
    )
    defaults.update(kwargs)
    return GoldCornerPass(corner=corner, **defaults)


def _pass(corner, lap=0, **kwargs):
    defaults = dict(
        entry_speed_kmh=110, apex_speed_kmh=80, exit_speed_kmh=115,
        min_speed_kmh=78, peak_brake_bar=30, brake_point_m=80,
        brake_release_m=10, trail_brake_bar_at_apex=5,
        throttle_at_exit_pct=70, max_g_lat=1.2, max_combo_g=1.5,
        corner_time_s=4.0, coast_seconds=0.0, steering_corrections=1,
        nothing_time_s=0.1,
    )
    defaults.update(kwargs)
    return CornerPass(corner=corner, lap=lap, **defaults)


def _gold_bundle(corner_passes_dict):
    return GoldStandard(
        track="Sonoma Raceway", source_file="t.vbo",
        lap_time_s=100.0, total_distance_m=4258,
        corners=corner_passes_dict, n_frames=100,
    )


def test_find_highlights_t6_carousel_oversteer(synth_lap_frames):
    p = [_pass("Turn 6", max_combo_g=1.7)]      # > 1.6 trigger
    gold = _gold_bundle({"Turn 6": _gold_for("Turn 6")})
    hs = find_highlights(p, [], gold, synth_lap_frames)
    cats = {h.category for h in hs}
    assert "t6_carousel_oversteer" in cats


def test_find_highlights_t11_late_brake(synth_lap_frames):
    """Brake point 10m closer to entry than gold should trigger T11 highlight."""
    g = _gold_for("Turn 11", brake_point_m=120)
    p = [_pass("Turn 11", brake_point_m=110)]    # 10m late → fires (gold-actual=10>5)
    hs = find_highlights(p, [], _gold_bundle({"Turn 11": g}), synth_lap_frames)
    cats = {h.category for h in hs}
    assert "t11_bump_late_brake" in cats


def test_find_highlights_t10_overbraked(synth_lap_frames):
    """T10 driver braking >30 bar when gold uses <20 bar should fire."""
    g = _gold_for("Turn 10", peak_brake_bar=15)
    p = [_pass("Turn 10", peak_brake_bar=40)]
    hs = find_highlights(p, [], _gold_bundle({"Turn 10": g}), synth_lap_frames)
    cats = {h.category for h in hs}
    assert "t10_lift_when_brake_needed" in cats


def test_find_highlights_coast_in_corner(synth_lap_frames):
    p = [_pass("Turn 4", coast_seconds=0.6)]    # > 0.4
    g = _gold_bundle({"Turn 4": _gold_for("Turn 4")})
    hs = find_highlights(p, [], g, synth_lap_frames)
    cats = {h.category for h in hs}
    assert "coast_in_corner" in cats


def test_find_highlights_t4_perfect_trail_brake(synth_lap_frames):
    """Bug fix verification: T4 trail-brake detector used to never fire because
    the apex/peak ratio condition was malformed (0.5 <= x <= 0.20).
    With apex 8 / peak 50 = 0.16 it should now fire as a positive."""
    p = [_pass("Turn 4", peak_brake_bar=50, trail_brake_bar_at_apex=8)]
    g = _gold_bundle({"Turn 4": _gold_for("Turn 4")})
    hs = find_highlights(p, [], g, synth_lap_frames)
    cats = {h.category for h in hs}
    # Should detect the perfect trail brake as a positive moment
    assert "perfect_trail_brake_T4" in cats


def test_find_highlights_severity_ordering(synth_lap_frames):
    """high > medium > positive > engineering."""
    p = [
        _pass("Turn 6", max_combo_g=1.7),         # high (oversteer)
        _pass("Turn 4", coast_seconds=0.6),       # medium (coast)
    ]
    g = _gold_bundle({c: _gold_for(c) for c in ("Turn 6", "Turn 4")})
    hs = find_highlights(p, [], g, synth_lap_frames)
    severities = [h.severity for h in hs]
    # Highs should come before mediums
    if "high" in severities and "medium" in severities:
        assert severities.index("high") < severities.index("medium")


def test_highlights_to_dict_serializable(synth_lap_frames):
    p = [_pass("Turn 6", max_combo_g=1.7)]
    g = _gold_bundle({"Turn 6": _gold_for("Turn 6")})
    hs = find_highlights(p, [], g, synth_lap_frames)
    out = highlights_to_dict(hs)
    for d in out:
        assert isinstance(d, dict)
        assert "title" in d
        assert "video_in_s" in d
        assert "video_out_s" in d


def test_find_highlights_max_items_caps_output(synth_lap_frames):
    """Even with many trigger conditions, output should cap at max_items."""
    p = [_pass("Turn 6", lap=l, max_combo_g=1.7) for l in range(20)]
    g = _gold_bundle({"Turn 6": _gold_for("Turn 6")})
    hs = find_highlights(p, [], g, synth_lap_frames, max_items=5)
    assert len(hs) <= 5
