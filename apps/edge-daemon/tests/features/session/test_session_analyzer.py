"""Unit tests for src/simulator/session_analyzer.py."""
import json
import pytest

from pitwall.features.session.session_analyzer import (
    analyze_session, _segment_into_laps, _narrate, _no_gold_bundle,
)


EXPECTED_BUNDLE_KEYS = {
    "session_id", "track", "scorecard", "highlights", "stats",
    "smoothness", "consistency", "friction", "hustle_map", "track_out",
    "trail_brake", "eob", "slip_band", "change_of_speed_events",
    "incidents", "narrative_md", "next_focus",
}


def test_analyze_session_with_no_frames(real_track_path, real_gold_path):
    """Empty frames must not crash; bundle still has session_id and track."""
    bundle = analyze_session(
        "x", [],
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    assert bundle["session_id"] == "x"
    assert bundle["track"] == "Sonoma Raceway"


def test_analyze_session_returns_full_bundle_keys(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-1", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    missing = EXPECTED_BUNDLE_KEYS - set(bundle)
    assert not missing, f"bundle missing keys: {missing}"


def test_analyze_session_scorecard_corners_have_required_fields(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-2", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    sc = bundle.get("scorecard")
    if sc is None:
        pytest.skip("scorecard not produced for synth frames")
    required = {"corner", "grade", "score_pct", "weight", "delta_time_s"}
    for c in sc.get("corners", []):
        missing = required - set(c)
        assert not missing, f"scorecard corner missing fields: {missing}"


def test_analyze_session_highlights_are_dicts_with_video_cuts(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-3", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    hs = bundle["highlights"]
    assert isinstance(hs, list)
    for h in hs:
        assert isinstance(h, dict)
        for k in ("title", "severity", "lap", "video_in_s", "video_out_s"):
            assert k in h, f"highlight missing key: {k}"


def test_analyze_session_stats_match_input(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-4", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    stats = bundle["stats"]
    assert stats["top_speed_kmh"] > 0
    assert stats["n_frames"] == len(synth_lap_frames)


def test_analyze_session_narrative_is_h1_markdown(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-5", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    nm = bundle["narrative_md"]
    assert isinstance(nm, str)
    assert nm.strip().startswith("# ")


def test_analyze_session_next_focus_caps_at_three(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-6", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    nf = bundle["next_focus"]
    assert isinstance(nf, list)
    assert len(nf) <= 3


def test_analyze_session_no_gold_path_returns_minimal_bundle(
    synth_lap_frames, real_track_path,
):
    """Missing gold file → bundle has scorecard=None and a clear narrative."""
    bundle = analyze_session(
        "sid-7", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path="/nonexistent/path/gold.json",
    )
    assert bundle["scorecard"] is None
    assert "Gold standard not available" in bundle["narrative_md"]
    # Bundle should still satisfy the contract
    missing = EXPECTED_BUNDLE_KEYS - set(bundle)
    assert not missing, f"no-gold bundle missing keys: {missing}"


def test_narrate_no_plus_minus_when_driver_faster_than_gold():
    """Regression (AUDIT.md): when best_lap < gold (driver faster), the
    narrative must not produce literal '+-' from `+{delta:.2f}`. Headline
    line must format the negative delta as '-X.XX'."""
    bundle = {
        "track": "Sonoma Raceway",
        "scorecard": {
            "session_id": "fast",
            "n_laps": 5,
            "best_lap_s": 100.0,
            "gold_lap_s": 110.0,
            "session_grade": "A",
            "weighted_total_pct": 0.95,
            "summary": "Faster than gold!",
            "corners": [],
        },
        "highlights": [],
        "stats": {},
        "eob": {},
        "slip_band": {},
        "consistency": {},
    }
    text, focus = _narrate(bundle)
    headline_line = next((ln for ln in text.splitlines() if "Best lap:" in ln), "")
    assert "+-" not in headline_line, (
        f"sign-formatting regression in headline: {headline_line!r}"
    )


def test_analyze_session_bundle_is_json_serializable(
    synth_lap_frames, real_track_path, real_gold_path,
):
    bundle = analyze_session(
        "sid-8", synth_lap_frames,
        track_json_path=str(real_track_path),
        gold_path=str(real_gold_path),
    )
    # Must serialise without crashing (default=str catches any datetime leaks)
    s = json.dumps(bundle, default=str)
    assert len(s) > 100


def test_segment_into_laps_empty(real_track):
    assigns, times = _segment_into_laps([], real_track)
    assert assigns == []
    assert times == []


def test_segment_into_laps_assignment_shape(synth_lap_frames, real_track):
    assigns, times = _segment_into_laps(synth_lap_frames, real_track)
    assert len(assigns) == len(synth_lap_frames)
    assert all(isinstance(a, int) and a >= 0 for a in assigns)
    # synth_lap_frames is one synthetic lap covering the full track length —
    # the segmentation may produce 0 or 1 lap_times depending on the
    # 95% threshold. Both are valid; just assert the shape.
    assert isinstance(times, list)
    assert all(isinstance(t, (int, float)) and t >= 0 for t in times)
