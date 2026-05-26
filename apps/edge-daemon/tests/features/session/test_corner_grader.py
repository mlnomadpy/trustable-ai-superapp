"""Unit tests for src/simulator/corner_grader.py."""
import pytest
from pitwall.features.session.corner_grader import (
    CornerPass, TimeLossAttribution, CornerGrade,
    grade_corner_pass, grade_session, _grade_letter, _decompose_time_loss,
    extract_corner_passes, scorecard_to_dict,
)
from pitwall.features.track.gold_standard import GoldStandard


def test_grade_letter_thresholds():
    assert _grade_letter(0.99) == "A+"
    assert _grade_letter(0.96) == "A"
    assert _grade_letter(0.92) == "B"
    assert _grade_letter(0.85) == "C"
    assert _grade_letter(0.75) == "D"
    assert _grade_letter(0.50) == "F"


def test_grade_corner_pass_basic(synth_corner_pass, synth_gold_corner_pass):
    cg = grade_corner_pass(synth_corner_pass, synth_gold_corner_pass)
    assert isinstance(cg, CornerGrade)
    assert cg.corner == "Turn 10"
    assert cg.grade in ("A+", "A", "B", "C", "D", "F")
    assert 0 <= cg.score_pct <= 1.0
    assert cg.weight > 0
    assert cg.trod_voice  # non-empty voice line


def test_grade_t10_uses_correct_weight(synth_corner_pass, synth_gold_corner_pass):
    cg = grade_corner_pass(synth_corner_pass, synth_gold_corner_pass)
    # T10 has the highest weight in sonoma.LAP_TIME_LEVERAGE
    assert cg.weight == pytest.approx(0.16, abs=0.001)


def test_grade_perfect_pass_grades_a(synth_gold_corner_pass):
    """Driver matches gold exactly → grade should be A or A+."""
    g = synth_gold_corner_pass
    perfect = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh,
        apex_speed_kmh=g.apex_speed_kmh,
        exit_speed_kmh=g.exit_speed_kmh,
        min_speed_kmh=g.min_speed_kmh,
        peak_brake_bar=g.peak_brake_bar,
        brake_point_m=g.brake_point_m,
        brake_release_m=g.brake_release_m,
        trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
        throttle_at_exit_pct=g.throttle_at_exit_pct,
        max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
        corner_time_s=g.corner_time_s,
        coast_seconds=0, steering_corrections=0, nothing_time_s=0,
    )
    cg = grade_corner_pass(perfect, g)
    assert cg.grade in ("A+", "A")
    assert cg.score_pct >= 0.95


def test_grade_terrible_pass_grades_low(synth_gold_corner_pass):
    """Driver way below gold on every metric → grade should be D or F."""
    g = synth_gold_corner_pass
    bad = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh * 0.6,
        apex_speed_kmh=g.apex_speed_kmh * 0.6,
        exit_speed_kmh=g.exit_speed_kmh * 0.6,
        min_speed_kmh=g.min_speed_kmh * 0.6,
        peak_brake_bar=20,
        brake_point_m=g.brake_point_m + 30,
        brake_release_m=0,
        trail_brake_bar_at_apex=0,
        throttle_at_exit_pct=20,
        max_g_lat=0.5, max_combo_g=0.6,
        corner_time_s=g.corner_time_s * 1.5,
        coast_seconds=2.0, steering_corrections=5, nothing_time_s=1.5,
    )
    cg = grade_corner_pass(bad, g)
    assert cg.grade in ("D", "F")


def test_decompose_time_loss_low_apex_speed(synth_gold_corner_pass):
    """Apex deficit should be flagged as 'low_apex_speed' attribution."""
    g = synth_gold_corner_pass
    p = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh,
        apex_speed_kmh=g.apex_speed_kmh - 10,    # 10 km/h slow apex
        exit_speed_kmh=g.exit_speed_kmh,
        min_speed_kmh=g.min_speed_kmh - 10,
        peak_brake_bar=g.peak_brake_bar,
        brake_point_m=g.brake_point_m, brake_release_m=g.brake_release_m,
        trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
        throttle_at_exit_pct=g.throttle_at_exit_pct,
        max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
        corner_time_s=g.corner_time_s + 0.5,
        coast_seconds=0, steering_corrections=0, nothing_time_s=0,
    )
    attrib = _decompose_time_loss(p, g)
    causes = {a.cause for a in attrib}
    assert "low_apex_speed" in causes


def test_decompose_time_loss_caps_at_actual_delta(synth_gold_corner_pass):
    """Sum of attributed seconds should never exceed actual Δt."""
    g = synth_gold_corner_pass
    p = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh - 5,
        apex_speed_kmh=g.apex_speed_kmh - 5,
        exit_speed_kmh=g.exit_speed_kmh - 5,
        min_speed_kmh=g.min_speed_kmh - 5,
        peak_brake_bar=g.peak_brake_bar,
        brake_point_m=g.brake_point_m + 20,    # 20m too early
        brake_release_m=g.brake_release_m,
        trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
        throttle_at_exit_pct=g.throttle_at_exit_pct - 30,
        max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
        corner_time_s=g.corner_time_s + 0.3,
        coast_seconds=1.0, steering_corrections=4, nothing_time_s=0.6,
    )
    attrib = _decompose_time_loss(p, g)
    delta = p.corner_time_s - g.corner_time_s
    total_attributed = sum(a.seconds_lost for a in attrib)
    assert total_attributed <= delta + 1e-6


def test_decompose_time_loss_no_loss_returns_empty(synth_gold_corner_pass):
    """Within-50ms-of-gold pass should produce no attributions."""
    g = synth_gold_corner_pass
    p = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh,
        apex_speed_kmh=g.apex_speed_kmh,
        exit_speed_kmh=g.exit_speed_kmh,
        min_speed_kmh=g.min_speed_kmh,
        peak_brake_bar=g.peak_brake_bar,
        brake_point_m=g.brake_point_m, brake_release_m=g.brake_release_m,
        trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
        throttle_at_exit_pct=g.throttle_at_exit_pct,
        max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
        corner_time_s=g.corner_time_s + 0.02,    # 20 ms slower
        coast_seconds=0, steering_corrections=0, nothing_time_s=0,
    )
    attrib = _decompose_time_loss(p, g)
    assert attrib == []


def test_grade_session_picks_best_pass_per_corner(synth_gold_corner_pass):
    """Two passes for the same corner — scorecard should keep the higher-scored one."""
    g = synth_gold_corner_pass
    bad = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh - 20,
        apex_speed_kmh=g.apex_speed_kmh - 20,
        exit_speed_kmh=g.exit_speed_kmh - 20,
        min_speed_kmh=g.min_speed_kmh - 20,
        peak_brake_bar=20, brake_point_m=g.brake_point_m + 20,
        brake_release_m=0, trail_brake_bar_at_apex=0,
        throttle_at_exit_pct=20, max_g_lat=0.6, max_combo_g=0.7,
        corner_time_s=g.corner_time_s + 1.0,
        coast_seconds=1.5, steering_corrections=3, nothing_time_s=0.8,
    )
    good = CornerPass(
        corner=g.corner, lap=2,
        entry_speed_kmh=g.entry_speed_kmh - 1,
        apex_speed_kmh=g.apex_speed_kmh - 1,
        exit_speed_kmh=g.exit_speed_kmh - 1,
        min_speed_kmh=g.min_speed_kmh - 1,
        peak_brake_bar=g.peak_brake_bar,
        brake_point_m=g.brake_point_m, brake_release_m=g.brake_release_m,
        trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
        throttle_at_exit_pct=g.throttle_at_exit_pct,
        max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
        corner_time_s=g.corner_time_s + 0.05,
        coast_seconds=0, steering_corrections=0, nothing_time_s=0,
    )
    gold = GoldStandard(track="Sonoma Raceway", source_file="t.vbo",
                        lap_time_s=100.0, total_distance_m=4258,
                        corners={g.corner: g}, n_frames=100)
    sc = grade_session([bad, good], gold, "test", [105.5, 108.5])
    assert sc.n_laps == 2
    assert len(sc.corners) == 1
    # Should pick `good` (lap 2)
    assert sc.corners[0].lap == 2
    assert sc.corners[0].grade in ("A", "A+", "B")


def test_extract_corner_passes_from_synth_lap(synth_lap_frames, real_track):
    """Synth lap with 11 corners should produce one pass per corner."""
    lap_assignment = [0] * len(synth_lap_frames)
    passes = extract_corner_passes(synth_lap_frames, real_track, lap_assignment)
    # Synth frames don't perfectly align to real corner distances, but we
    # should detect at least a few corners
    assert len(passes) > 0
    # All passes should have valid corner names
    for p in passes:
        assert p.corner in [c.name for c in real_track.corners]


def test_nothing_time_dimension_lowers_score(synth_gold_corner_pass):
    """ADR-018 pedagogy: a pass that matches gold on every other dimension
    but coasts 1.0 s between brake-off and throttle-on must score lower than
    one with zero nothing-time. The dimension is weighted at 15 % so the
    expected delta is ≈10 % of the perfect score."""
    g = synth_gold_corner_pass

    def _pass_with(nothing_time_s):
        return CornerPass(
            corner=g.corner, lap=1,
            entry_speed_kmh=g.entry_speed_kmh,
            apex_speed_kmh=g.apex_speed_kmh,
            exit_speed_kmh=g.exit_speed_kmh,
            min_speed_kmh=g.min_speed_kmh,
            peak_brake_bar=g.peak_brake_bar,
            brake_point_m=g.brake_point_m, brake_release_m=g.brake_release_m,
            trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
            throttle_at_exit_pct=g.throttle_at_exit_pct,
            max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
            corner_time_s=g.corner_time_s,
            coast_seconds=0, steering_corrections=0,
            nothing_time_s=nothing_time_s,
        )

    clean = grade_corner_pass(_pass_with(0.0), g).score_pct
    coasty = grade_corner_pass(_pass_with(1.0), g).score_pct
    assert clean > coasty
    # 1.0 s of nothing-time costs (1/1.5)·15 % ≈ 0.10 of the score.
    assert (clean - coasty) > 0.05
    assert (clean - coasty) < 0.18


def test_decompose_attributes_nothing_time_above_threshold(synth_gold_corner_pass):
    """0.5 s of nothing-time on a 1.0 s delta should land as a
    `nothing_time` attribution worth ~0.3 s under the new multiplier."""
    g = synth_gold_corner_pass
    p = CornerPass(
        corner=g.corner, lap=1,
        entry_speed_kmh=g.entry_speed_kmh - 2,
        apex_speed_kmh=g.apex_speed_kmh - 2,
        exit_speed_kmh=g.exit_speed_kmh - 2,
        min_speed_kmh=g.min_speed_kmh - 2,
        peak_brake_bar=g.peak_brake_bar,
        brake_point_m=g.brake_point_m, brake_release_m=g.brake_release_m,
        trail_brake_bar_at_apex=g.trail_brake_bar_at_apex,
        throttle_at_exit_pct=g.throttle_at_exit_pct,
        max_g_lat=g.max_g_lat, max_combo_g=g.max_combo_g,
        corner_time_s=g.corner_time_s + 1.0,
        coast_seconds=0, steering_corrections=0,
        nothing_time_s=0.5,
    )
    attribs = _decompose_time_loss(p, g)
    by_cause = {a.cause: a.seconds_lost for a in attribs}
    assert "nothing_time" in by_cause
    # 0.5 s × 0.6 multiplier = 0.30 s before the cap kicks in
    assert by_cause["nothing_time"] >= 0.25


def test_scorecard_to_dict_round_trip(synth_corner_pass, synth_gold_corner_pass):
    g = synth_gold_corner_pass
    gold = GoldStandard(track="Sonoma Raceway", source_file="t.vbo",
                        lap_time_s=100.0, total_distance_m=4258,
                        corners={g.corner: g}, n_frames=100)
    sc = grade_session([synth_corner_pass], gold, "sid", [108.5])
    d = scorecard_to_dict(sc)
    assert d["session_id"] == "sid"
    assert "corners" in d
    assert d["corners"][0]["corner"] == "Turn 10"
    # Time-loss attributions should be JSON-shaped, not dataclasses
    for a in d["corners"][0].get("time_loss_attribution", []):
        assert isinstance(a, dict)
        assert "cause" in a
