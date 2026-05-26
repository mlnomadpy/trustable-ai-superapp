import pytest
import pitwall as br
from conftest import _start_session, _frames_to_payload
from pitwall.features.coaching.cue_renderer import estimate_tts_ms
from pitwall.features.session.laps import detect_laps, quantile
from pitwall.db import log_llm_friction
from pitwall.features.realtime.bp_realtime import cue_bus

# ─── /session/start, /sessions, /session/<sid>, /end ─────────────────────────


def test_session_start_returns_id(client):
    r = client.post("/session/start", json={"driver": "Taha", "track": "Sonoma Raceway"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["started"] is True
    assert body["session_id"].startswith("sonoma-raceway-")


def test_session_start_accepts_custom_id(client):
    r = client.post("/session/start", json={"session_id": "my-test-session", "driver": "x"})
    assert r.status_code == 200
    assert r.get_json()["session_id"] == "my-test-session"


def test_sessions_list_includes_new_session(client):
    client.post("/session/start", json={"session_id": "list-test-1", "driver": "a"})
    client.post("/session/start", json={"session_id": "list-test-2", "driver": "b"})
    r = client.get("/sessions")
    assert r.status_code == 200
    body = r.get_json()
    ids = {s["session_id"] for s in body["sessions"]}
    assert {"list-test-1", "list-test-2"} <= ids


def test_sessions_active_only_filters_ended(client):
    client.post("/session/start", json={"session_id": "active-1"})
    client.post("/session/start", json={"session_id": "ended-1"})
    client.post("/session/ended-1/end")
    r = client.get("/sessions?active_only=true")
    assert r.status_code == 200
    ids = {s["session_id"] for s in r.get_json()["sessions"]}
    assert "active-1" in ids
    assert "ended-1" not in ids


def test_session_end_idempotent(client):
    client.post("/session/start", json={"session_id": "end-test"})
    r1 = client.post("/session/end-test/end")
    r2 = client.post("/session/end-test/end")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.get_json()["ended"] is True
    assert r2.get_json()["ended"] is True


def test_session_detail_unknown_returns_404(client):
    r = client.get("/session/no-such-session")
    assert r.status_code == 404


def test_session_detail_returns_session_laps_notes(client, make_frame_fn):
    sid = "detail-test"
    client.post("/session/start", json={"session_id": sid, "driver": "d", "track": "Sonoma Raceway"})
    client.post("/lap", json={
        "session_id": sid, "lap_number": 1, "lap_time_s": 105.5,
        "avg_speed_kmh": 110.0, "max_combo_g": 1.5,
    })
    r = client.get(f"/session/{sid}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["session"]["session_id"] == sid
    assert body["session"]["driver"] == "d"
    assert len(body["laps"]) == 1
    assert body["laps"][0]["lap_time_s"] == 105.5
    assert body["lap_count"] == 1
    assert body["best_lap_s"] == 105.5


def test_sessions_list_limit_param(client):
    for i in range(8):
        client.post("/session/start", json={"session_id": f"lim-{i}"})
    r = client.get("/sessions?limit=3")
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["sessions"]) <= 3



# ─── /session/<sid>/frames ───────────────────────────────────────────────────


def test_post_frames_batch_appends(client, make_frame_fn):
    sid = _start_session(client)
    frames = [make_frame_fn(t=i * 0.1, distance=i * 5.0) for i in range(50)]
    r = client.post(f"/session/{sid}/frames",
                    json={"frames": _frames_to_payload(frames)})
    assert r.status_code == 200
    body = r.get_json()
    assert body["n_appended"] == 50
    assert body["session_id"] == sid


def test_post_frames_empty_returns_400(client):
    sid = _start_session(client)
    r = client.post(f"/session/{sid}/frames", json={"frames": []})
    assert r.status_code == 400
    assert "error" in r.get_json()



# ─── /session/import ─────────────────────────────────────────────────────────


def test_session_import_missing_path_returns_400(client):
    r = client.post("/session/import", json={"vbo_path": "/nonexistent.vbo"})
    assert r.status_code == 400
    assert "error" in r.get_json()



# ─── /session/<sid>/scorecard before debrief ─────────────────────────────────


def test_scorecard_before_analysis_returns_404(client):
    """Regression: an un-analysed session used to return 200 with null fields."""
    sid = _start_session(client)
    r = client.get(f"/session/{sid}/scorecard")
    assert r.status_code == 404



# ─── /session/<sid>/video_frames + /sync ─────────────────────────────────────


def test_post_video_frames_appends(client):
    sid = _start_session(client)
    payload = {"frames": [
        {"timestamp": 1000.0 + i * 0.033, "avitime_ms": i * 33,
         "file_path": "/tmp/x.mp4", "file_offset_s": i * 0.033,
         "width": 1920, "height": 1080}
        for i in range(20)
    ]}
    r = client.post(f"/session/{sid}/video_frames", json=payload)
    assert r.status_code == 200
    assert r.get_json()["n_appended"] == 20


def test_sync_returns_rows_when_telemetry_present(client, make_frame_fn):
    sid = _start_session(client)
    base_t = 1000.0
    frames = [make_frame_fn(t=base_t + i * 0.1, distance=i * 5.0) for i in range(20)]
    client.post(f"/session/{sid}/frames", json={"frames": _frames_to_payload(frames)})
    client.post(f"/session/{sid}/video_frames", json={"frames": [
        {"timestamp": base_t + i * 0.1, "avitime_ms": i * 100,
         "file_path": "/tmp/x.mp4", "file_offset_s": i * 0.1,
         "width": 1920, "height": 1080}
        for i in range(20)
    ]})
    r = client.get(f"/session/{sid}/sync")
    assert r.status_code == 200
    body = r.get_json()
    assert "rows" in body
    assert isinstance(body["rows"], list)
    assert body["count"] == len(body["rows"])



# ─── Helpers (frame round-trip + session-id generator) ───────────────────────


from pitwall.features.session.frames import frames_to_rows, rows_to_frames
from pitwall.features.session.laps import new_session_id

def test_frames_to_rows_round_trip(make_frame_fn):
    frames = [make_frame_fn(t=i * 0.1, distance=i * 5.0,
                            speed_kmh=120, brake_bar=10.0,
                            throttle_pct=80, g_lat=0.5)
              for i in range(5)]
    rows = frames_to_rows("sid-x", frames)
    assert len(rows) == 5
    rebuilt = rows_to_frames(rows)
    for orig, rb in zip(frames, rebuilt):
        assert abs(rb.speed - orig.speed) < 1e-6
        assert abs(rb.g_lat - orig.g_lat) < 1e-6
        assert abs(rb.brake_pressure - orig.brake_pressure) < 1e-6
        assert abs(rb.throttle - orig.throttle) < 1e-6


def test_new_session_id_format():
    sid = new_session_id("Sonoma Raceway")
    assert sid.startswith("sonoma-raceway-")



# ─── Phase 6: lap detection + analysis endpoints ─────────────────────────────


def _ingest_multi_lap(client, sid, frames):
    """Helper: post a multi-lap frame batch to /session/<sid>/frames."""
    return client.post(
        f"/session/{sid}/frames",
        json={"frames": _frames_to_payload(frames), "driver": "test", "track": "Sonoma Raceway"},
    )


def test_detect_laps_finds_multiple_via_distance_wrap(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    laps = detect_laps(sid)
    assert len(laps) >= 2     # at least 2 wraps in 3-lap data
    for l in laps:
        assert 60 <= l["lap_time_s"] <= 300
        assert l["t_end"] > l["t_start"]
        assert l["lap_number"] >= 1


def test_detect_laps_unknown_session_empty(client):
    assert detect_laps("no-such-session") == []


def test_lap_time_table_404_for_unknown_session(client):
    r = client.get("/session/missing/lap_time_table")
    assert r.status_code == 404


def test_lap_time_table_400_when_no_complete_laps(client, make_frame_fn):
    """A short single-frame session can't produce a complete lap → 400."""
    sid = _start_session(client)
    frames = [make_frame_fn(t=i * 0.1, distance=i * 5.0) for i in range(50)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.get(f"/session/{sid}/lap_time_table")
    assert r.status_code == 400


def test_lap_time_table_returns_lap_data(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/lap_time_table")
    assert r.status_code == 200
    body = r.get_json()
    assert body["lap_count"] >= 2
    assert body["best_lap_s"] > 60
    assert body["best_lap_number"] in [l["lap_number"] for l in body["laps"]]
    # Exactly one lap is_best=True
    bests = [l for l in body["laps"] if l["is_best"]]
    assert len(bests) == 1
    # delta_to_best is 0 for the best lap
    assert bests[0]["delta_to_best_s"] == 0.0


def test_lap_time_distribution_returns_box_plot_stats(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/lap_time_distribution")
    assert r.status_code == 200
    body = r.get_json()
    for key in ("min_s", "max_s", "q1_s", "median_s", "q3_s", "iqr_s",
                "whisker_low_s", "whisker_high_s", "outliers", "mean_s", "stddev_s"):
        assert key in body
    assert body["min_s"] <= body["median_s"] <= body["max_s"]
    assert body["q1_s"] <= body["median_s"] <= body["q3_s"]


def test_ideal_lap_returns_sum_of_best_sectors(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/ideal_lap")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ideal_lap_s"] <= body["best_actual_lap_s"] + 1e-3
    assert body["gain_potential_s"] >= -1e-6
    assert len(body["best_sectors"]) == 3


def test_sector_times_thin_view(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/sector_times")
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["sector_definitions"]) == 3
    assert all("s1" in lap and "s2" in lap and "s3" in lap for lap in body["laps"])


def test_pedal_behavior_returns_4_states(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/pedal_behavior")
    assert r.status_code == 200
    body = r.get_json()
    states = body["states"]
    for k in ("throttle_only", "brake_only", "trail_brake", "coast"):
        assert k in states
        assert "pct" in states[k]
        assert "frames" in states[k]
    # Sum of frames equals frame_count
    assert sum(s["frames"] for s in states.values()) == body["frame_count"]


def test_pedal_behavior_thresholds_query_param(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/pedal_behavior?throttle_th=50&brake_th=10")
    assert r.status_code == 200
    body = r.get_json()
    assert body["thresholds"]["throttle_pct"] == 50.0
    assert body["thresholds"]["brake_bar"] == 10.0


def test_pedal_behavior_404_unknown_session(client):
    r = client.get("/session/missing/pedal_behavior")
    assert r.status_code == 404


def test_throttle_corner_box_returns_per_corner_stats(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/throttle_corner_box")
    assert r.status_code == 200
    body = r.get_json()
    assert "corners" in body
    assert len(body["corners"]) == 11    # all Sonoma corners
    sample = next(c for c in body["corners"] if c["n_samples"] > 0)
    assert sample["min_pct"] <= sample["median_pct"] <= sample["max_pct"]


def test_corner_classification_groups_by_apex_speed(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/corner_classification")
    assert r.status_code == 200
    body = r.get_json()
    assert {b["band"] for b in body["bands"]} == {"low_speed", "med_speed", "high_speed"}
    total_corners = sum(len(b["corners"]) for b in body["bands"])
    assert total_corners == 11


def test_corner_classification_404_unknown_session(client):
    r = client.get("/session/missing/corner_classification")
    assert r.status_code == 404


def test_straight_line_speed_returns_per_straight_top(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/straight_line_speed")
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["straights"]) == 3
    front = next(s for s in body["straights"] if s["name"] == "Front Straight")
    assert front["top_speed_kmh"] is not None
    assert front["top_speed_kmh"] > 100


def test_brake_acceleration_returns_zones_and_exits(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/brake_acceleration")
    assert r.status_code == 200
    body = r.get_json()
    assert "brake_zones" in body
    assert "corner_exits" in body
    for z in body["brake_zones"]:
        assert z["max_decel_g"] <= 0   # decel is negative
        assert z["n_passes"] >= 1


def test_track_elevation_returns_samples(client):
    r = client.get("/track/sonoma/elevation")
    assert r.status_code == 200
    body = r.get_json()
    assert body["track_id"] == "sonoma"
    assert body["min_elevation_m"] is not None
    assert body["max_elevation_m"] >= body["min_elevation_m"]
    assert len(body["samples"]) > 100


def test_track_elevation_step_m_query(client):
    r = client.get("/track/sonoma/elevation?step_m=50")
    assert r.status_code == 200
    body = r.get_json()
    assert body["step_m"] == 50.0
    # 4258 m / 50 m ≈ 86 samples
    assert 80 <= len(body["samples"]) <= 90


def test_track_elevation_404_unknown_track(client):
    r = client.get("/track/no-such-track/elevation")
    assert r.status_code == 404


def test_track_elevation_invalid_step_returns_400(client):
    r = client.get("/track/sonoma/elevation?step_m=-5")
    assert r.status_code == 400


def test_driver_evolution_404_unknown_driver(client):
    r = client.get("/driver/no-such-driver/evolution")
    assert r.status_code == 404


def test_driver_evolution_204_with_few_sessions(client, synth_multi_lap_frames):
    """Driver with 2 sessions → 204 (frontend should hide panel)."""
    for i in range(2):
        sid = f"ev-test-{i}"
        client.post(f"/session/{sid}/frames", json={
            "frames": _frames_to_payload(synth_multi_lap_frames),
            "driver": "evo-driver", "track": "Sonoma Raceway",
        })
    r = client.get("/driver/evo-driver/evolution?track=Sonoma Raceway")
    assert r.status_code == 204


def test_driver_evolution_returns_evolution_with_5_sessions(client, synth_multi_lap_frames):
    for i in range(5):
        sid = f"ev5-test-{i}"
        client.post(f"/session/{sid}/frames", json={
            "frames": _frames_to_payload(synth_multi_lap_frames),
            "driver": "many-driver", "track": "Sonoma Raceway",
        })
    r = client.get("/driver/many-driver/evolution?track=Sonoma Raceway")
    assert r.status_code == 200
    body = r.get_json()
    assert body["session_count"] == 5
    assert len(body["evolution"]) == 5
    assert body["summary"]["first_best_s"] > 0
    for ev in body["evolution"]:
        assert "best_lap_s" in ev
        assert "median_lap_s" in ev



# ─── Parquet export + analysis-hub laps ─────────────────────────────────────


def test_export_parquet_signal_registry_returns_catalog(client):
    """signal_registry is session-independent — returns 200 regardless of sid."""
    r = client.get("/session/anything/export.parquet?table=signal_registry")
    # Either 200 (duckdb) or 503 (sqlite/no pyarrow) — never 404 since
    # the catalog ignores the session id.
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.headers.get("X-Pitwall-Table") == "signal_registry"
        assert len(r.data) > 0


def test_export_parquet_unknown_table_400(client):
    r = client.get("/session/x/export.parquet?table=bogus_table")
    assert r.status_code in (400, 503)


def test_export_parquet_signal_registry_includes_session_id(client):
    """Analysis Hub regression: parquet must carry session_id so the PWA's
    DuckDB-wasm `WHERE session_id = ?` filter binds."""
    br.seed_signal_registry()
    sid = "registry-sid-check"
    r = client.get(f"/session/{sid}/export.parquet?table=signal_registry")
    if r.status_code == 503:
        return  # no DB / no pyarrow in this env
    assert r.status_code == 200
    import io
    import pyarrow.parquet as pq
    t = pq.read_table(io.BytesIO(r.data))
    assert "session_id" in t.schema.names
    if t.num_rows > 0:
        assert set(t.column("session_id").to_pylist()) == {sid}


def test_export_parquet_telemetry_signals_includes_session_id(client):
    """Analysis Hub regression: tall-store parquet must carry session_id."""
    br.seed_signal_registry()
    sid = "tall-sid-check"
    r = client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0, "value": 92.1},
        {"name": "oil_temp_c", "t": 1001.0, "value": 92.5},
    ]})
    assert r.status_code == 200
    r = client.get(f"/session/{sid}/export.parquet?table=telemetry_signals")
    if r.status_code == 503:
        return  # no DB / no pyarrow in this env
    assert r.status_code == 200
    import io
    import pyarrow.parquet as pq
    t = pq.read_table(io.BytesIO(r.data))
    assert "session_id" in t.schema.names
    assert t.num_rows >= 2
    assert set(t.column("session_id").to_pylist()) == {sid}


def test_session_laps_404_for_unknown(client):
    r = client.get("/session/no-such-session/laps")
    assert r.status_code in (404, 503)


def test_session_laps_envelope_with_multi_lap(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/laps")
    if r.status_code == 503:
        return  # no DB backend in this env
    assert r.status_code == 200
    body = r.get_json()
    assert "laps" in body and "track_length_m" in body
    assert body["laps"][0]["method"] == "all"
    assert body["laps"][0]["name"] == "Full session"
    for lap in body["laps"]:
        for k in ("name", "t_start", "t_end", "duration_s", "distance_m", "method"):
            assert k in lap


# ─── Quantile helper ────────────────────────────────────────────────────────


def test_quantile_endpoints():
    assert quantile([1.0, 2.0, 3.0, 4.0, 5.0], 0.0) == 1.0
    assert quantile([1.0, 2.0, 3.0, 4.0, 5.0], 1.0) == 5.0
    # Median of 5 values at p=0.5 → (n-1)*0.5+1 = 3 → exact 3.0
    assert quantile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == 3.0
    # Empty list
    assert quantile([], 0.5) == 0.0
    # Single value
    assert quantile([42.0], 0.5) == 42.0



# ─── Roadmap endpoints (POST /session/<sid>/frame, /corners, /score, etc.) ──


def test_post_single_frame_appends_and_returns_idx(client):
    sid = _start_session(client)
    payload = {
        "timestamp": 1000.0, "distance": 0.0, "speed": 28.0,
        "g_lat": 0.0, "g_long": 0.0, "combo_g": 0.0,
        "brake_pressure": 0.0, "throttle": 99.0, "steering": 0.0,
        "rpm": 4000.0, "lat": 23.49, "lon": -73.78,
    }
    r1 = client.post(f"/session/{sid}/frame", json=payload)
    assert r1.status_code == 200
    body = r1.get_json()
    assert body["saved"] is True
    assert body["frame_idx"] == 0

    # Second post increments frame_idx
    r2 = client.post(f"/session/{sid}/frame", json={**payload, "timestamp": 1000.1})
    assert r2.get_json()["frame_idx"] == 1


def test_post_single_frame_empty_returns_400(client):
    sid = _start_session(client)
    r = client.post(f"/session/{sid}/frame", json={})
    assert r.status_code == 400


def test_session_corners_404_when_no_telemetry(client):
    r = client.get("/session/missing/corners")
    assert r.status_code == 404


def test_session_corners_returns_per_corner_aggregates(client, synth_multi_lap_frames):
    sid = _start_session(client)
    _ingest_multi_lap(client, sid, synth_multi_lap_frames)
    r = client.get(f"/session/{sid}/corners")
    assert r.status_code == 200
    body = r.get_json()
    assert body["session_id"] == sid
    assert body["lap_count"] >= 2
    assert len(body["corners"]) == 11
    sample = next(c for c in body["corners"] if c["n_passes"] > 0)
    assert sample["best_pass"] is not None
    for k in ("entry_speed_kmh", "apex_speed_kmh", "exit_speed_kmh",
              "peak_brake_bar", "max_g_lat", "corner_time_s"):
        assert k in sample["best_pass"]
    assert sample["averages"]["apex_speed_kmh"] > 0


def test_score_400_without_session_id(client):
    """Missing session_id is a 400 regardless of coach state."""
    r = client.post("/score", json={})
    assert r.status_code == 400


def test_score_404_for_unknown_session(client, make_frame_fn):
    """Real session_id but no telemetry → 404."""
    r = client.post("/score", json={"session_id": "no-such-session"})
    assert r.status_code == 404


def test_score_503_when_no_local_gemma(client, monkeypatch, make_frame_fn):
    """Session has telemetry but no local Gemma loaded → 503.

    The fixture sets `_coach = None` already (see isolated_bridge), so
    /score should refuse with a clear error rather than crashing.
    """
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0) for i in range(20)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.post("/score", json={"session_id": sid})
    assert r.status_code == 503
    body = r.get_json()
    assert "gemma" in (body.get("error") or "").lower()


def test_markers_no_filter_returns_all(client):
    r = client.get("/markers")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] >= 16
    assert body["filters"] == {"corner": None, "kind": None}


def test_markers_corner_filter(client):
    r = client.get("/markers?corner=Turn 11")
    assert r.status_code == 200
    body = r.get_json()
    assert body["filters"]["corner"] == "Turn 11"
    for m in body["markers"]:
        assert m["corner"] == "Turn 11"


def test_markers_kind_filter(client):
    r = client.get("/markers?kind=brake")
    assert r.status_code == 200
    body = r.get_json()
    for m in body["markers"]:
        assert m["kind"] == "brake"


def test_coach_concepts_lists_nine(client):
    r = client.get("/coach/concepts")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 9
    ids = {c["id"] for c in body["concepts"]}
    assert {"trail_brake", "exit_speed", "eob", "look_ahead",
            "hustle", "late_apex", "entry_release",
            "downhill_brake", "uphill_brake"} == ids
    for c in body["concepts"]:
        assert c["description"]
        assert c["fires_when"]

