import pytest
import pitwall as br
from conftest import _start_session, _frames_to_payload
from pitwall.features.coaching.cue_renderer import estimate_tts_ms
from pitwall.features.session.laps import detect_laps, quantile
from pitwall.db import log_llm_friction
from pitwall.features.realtime.bp_realtime import cue_bus

# ─── /health ─────────────────────────────────────────────────────────────────


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    for key in ("version", "engine", "duckdb", "track"):
        assert key in body
    assert body["track"] == "Sonoma Raceway"



# ─── /coach/debrief ──────────────────────────────────────────────────────────


def test_debrief_missing_vbo_returns_400(client):
    r = client.post("/coach/debrief",
                    json={"session_id": "missing", "vbo_path": "/nonexistent.vbo"})
    assert r.status_code == 400


def test_debrief_after_frames_persists_returns_bundle(client, synth_lap_frames):
    sid = _start_session(client)
    payload = {"frames": _frames_to_payload(synth_lap_frames[:300])}
    r = client.post(f"/session/{sid}/frames", json=payload)
    assert r.status_code == 200

    r = client.post(
        "/coach/debrief",
        json={"session_id": sid, "driver_id": "test", "persist_to_profile": False},
    )
    assert r.status_code == 200
    bundle = r.get_json()
    for key in ("session_id", "track", "stats", "highlights"):
        assert key in bundle


def test_debrief_normalizes_legacy_narrative_keys_for_frontend(
    client, synth_lap_frames, monkeypatch,
):
    sid = _start_session(client)
    payload = {"frames": _frames_to_payload(synth_lap_frames[:300])}
    r = client.post(f"/session/{sid}/frames", json=payload)
    assert r.status_code == 200

    def _fake_analyze_session(*args, **kwargs):
        return {
            "session_id": sid,
            "track": "Sonoma Raceway",
            "scorecard": {"corners": []},
            "highlights": [],
            "stats": {},
            "smoothness": {},
            "consistency": {},
            "friction": {},
            "hustle_map": [],
            "track_out": {},
            "trail_brake": [],
            "eob": {},
            "slip_band": {},
            "slip_oscillations": [],
            "change_of_speed_events": [],
            "incidents": [],
            "narrative_md": "# Session debrief\n\nTurn 7 needs patience.",
            "next_focus": ["Turn 7", "Brake release", "Exit throttle"],
        }

    monkeypatch.setattr(
        "pitwall.features.coaching.bp_coaching.analyze_session",
        _fake_analyze_session,
    )

    r = client.post(
        "/coach/debrief",
        json={"session_id": sid, "driver_id": "test", "persist_to_profile": False},
    )
    assert r.status_code == 200
    bundle = r.get_json()
    assert bundle["narrative"] == "# Session debrief\n\nTurn 7 needs patience."
    assert bundle["focus"] == ["Turn 7", "Brake release", "Exit throttle"]
    assert bundle["narrative_md"] == "# Session debrief\n\nTurn 7 needs patience."
    assert bundle["next_focus"] == ["Turn 7", "Brake release", "Exit throttle"]


def test_scorecard_after_debrief_returns_data(client, synth_lap_frames):
    sid = _start_session(client)
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(synth_lap_frames[:300])})
    r1 = client.post(
        "/coach/debrief",
        json={"session_id": sid, "driver_id": "test", "persist_to_profile": False},
    )
    assert r1.status_code == 200
    r2 = client.get(f"/session/{sid}/scorecard")
    assert r2.status_code == 200
    body = r2.get_json()
    assert body["session_id"] == sid
    assert "scorecard" in body



# ─── /analyze ────────────────────────────────────────────────────────────────



# ─── /analyze ────────────────────────────────────────────────────────────────


def test_analyze_returns_expected_keys(client):
    burst = {
        "session_id": "burst-sess",
        "burst_id": 7,
        "avg_speed_kmh": 104.0, "max_combo_g": 1.82,
        "max_lateral_g": 1.35, "max_long_g": -0.92,
        "max_brake_bar": 45.0, "avg_throttle_pct": 38.0,
        "avg_steering_deg": 12.0, "coast_frames": 12,
        "trail_brake_frames": 4, "frame_count": 75,
        "corners_visited": ["Turn 3"], "distance_m": 1450.0,
        "in_corner": False, "past_apex": False,
    }
    r = client.post("/analyze", json=burst)
    assert r.status_code == 200
    body = r.get_json()
    for key in ("coaching", "pace_note", "coach_source",
                "cues", "source", "burst_id"):
        assert key in body
    assert body["burst_id"] == 7
