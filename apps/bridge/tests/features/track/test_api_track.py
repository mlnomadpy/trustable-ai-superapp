import pytest
import pitwall as br
from pitwall.features.coaching.cue_renderer import estimate_tts_ms
from pitwall.features.session.laps import detect_laps, quantile
from pitwall.db import log_llm_friction
from pitwall.features.realtime.bp_realtime import cue_bus

# ─── /track/* ────────────────────────────────────────────────────────────────


def test_track_markers_returns_at_least_16(client):
    r = client.get("/track/markers")
    assert r.status_code == 200
    body = r.get_json()
    assert "markers" in body
    assert len(body["markers"]) >= 16
    for m in body["markers"][:3]:
        for key in ("id", "label", "kind", "corner", "lat", "lon"):
            assert key in m


def test_track_danger_zones_returns_three(client):
    r = client.get("/track/danger_zones")
    assert r.status_code == 200
    zones = r.get_json()["danger_zones"]
    ids = {z["id"] for z in zones}
    assert {"T6_runoff", "T9_downhill", "T11_dive_passing"} <= ids


def test_track_weather_morning_fog(client):
    r = client.get("/track/weather?hour_local=8")
    assert r.status_code == 200
    body = r.get_json()
    assert body["phase"] == "morning_fog"


def test_track_weather_peak_grip(client):
    r = client.get("/track/weather?hour_local=13")
    assert r.status_code == 200
    assert r.get_json()["phase"] == "peak_grip"

