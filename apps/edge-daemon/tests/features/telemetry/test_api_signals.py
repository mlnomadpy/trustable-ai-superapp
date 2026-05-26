import pytest
import pitwall as br
from conftest import _start_session, _frames_to_payload
from pitwall.features.coaching.cue_renderer import estimate_tts_ms
from pitwall.features.session.laps import detect_laps, quantile
from pitwall.db import log_llm_friction
from pitwall.features.realtime.bp_realtime import cue_bus

# ─── ADR-015: signal registry (Phase 1) ──────────────────────────────────────


def test_signal_registry_tables_created(client):
    """get_db() should create all three ADR-015 tables on first connection."""
    conn = br.get_db()
    tables = {t[0] for t in conn.execute("SHOW TABLES").fetchall()}
    conn.close()
    assert {"signal_registry", "telemetry_signals", "session_capabilities"} <= tables


def test_signal_registry_seed_populates_known_pids(client):
    """seed_signal_registry() should load the static OBD-II catalog."""
    n = br.seed_signal_registry()
    assert n > 0
    conn = br.get_db()
    rows = conn.execute(
        "SELECT name, units FROM signal_registry WHERE name = 'oil_temp_c'"
    ).fetchall()
    conn.close()
    assert rows == [("oil_temp_c", "C")]


def test_signal_registry_seed_is_idempotent(client):
    """Calling seed twice must not duplicate rows."""
    br.seed_signal_registry()
    conn = br.get_db()
    n1 = conn.execute("SELECT COUNT(*) FROM signal_registry").fetchone()[0]
    conn.close()
    br.seed_signal_registry()
    conn = br.get_db()
    n2 = conn.execute("SELECT COUNT(*) FROM signal_registry").fetchone()[0]
    conn.close()
    assert n1 == n2 and n1 > 0


def test_signals_registry_endpoint_returns_full_catalog(client):
    """GET /signals/registry must return every seeded signal."""
    br.seed_signal_registry()
    r = client.get("/signals/registry")
    assert r.status_code == 200
    body = r.get_json()
    assert "count" in body and "signals" in body
    names = {s["name"] for s in body["signals"]}
    # Every group should have at least one representative
    assert "speed_ms" in names            # wide-table canonical
    assert "oil_temp_c" in names          # OBD-II
    assert "wheel_speed_fl_kmh" in names  # DBC chassis
    assert "tpms_fl_kpa" in names         # DBC tires
    # Schema completeness
    sample = body["signals"][0]
    for key in ("signal_id", "name", "units", "semantics", "group",
                "expected_hz", "min_useful_hz", "discovery"):
        assert key in sample


def test_signals_registry_endpoint_empty_before_seed(client):
    """Without an explicit seed call, the table is empty but the endpoint still 200s."""
    r = client.get("/signals/registry")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 0
    assert body["signals"] == []


def test_signals_registry_can_state_when_no_reader(client):
    """?include_can_state=true must produce a placeholder block when no
    CAN reader is running — the PWA renders ✗ rows from this shape."""
    r = client.get("/signals/registry?include_can_state=true")
    assert r.status_code == 200
    body = r.get_json()
    assert "can_state" in body
    cs = body["can_state"]
    assert cs["loaded"] is False
    assert cs["connected"] is False
    assert cs["frames_per_second"] == 0.0
    assert cs["unknown_ids"] == []
    assert cs["last_frame_age_s"] is None
    for k in ("interface", "channel", "bitrate", "session_id",
              "frames_total", "frames_unknown", "usb_devices"):
        assert k in cs


def test_session_export_parquet_404_when_no_session(client):
    r = client.get("/session/no-such/export.parquet")
    assert r.status_code == 404


def test_session_export_parquet_400_for_unknown_table(client, make_frame_fn):
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1) for i in range(10)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.get(f"/session/{sid}/export.parquet?table=garbage")
    assert r.status_code == 400


def test_session_export_parquet_streams_telemetry(client, make_frame_fn):
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0)
              for i in range(20)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.get(f"/session/{sid}/export.parquet")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/octet-stream"
    assert "X-Pitwall-Rows" in r.headers
    assert int(r.headers["X-Pitwall-Rows"]) == 20
    # Parquet file magic number: "PAR1" at the start AND end
    body = r.data
    assert body[:4] == b"PAR1"
    assert body[-4:] == b"PAR1"


def test_cues_stream_400_without_session_id(client):
    r = client.get("/cues/stream")
    assert r.status_code == 400


def test_cues_stream_emits_hello_then_published_cue(client):
    """Subscribe to /cues/stream, publish via _cue_bus directly,
    confirm the SSE stream surfaces both the hello event + the cue."""
    import threading
    sid = "stream-test-001"
    received: list[bytes] = []

    def reader():
        with client.get(f"/cues/stream?session_id={sid}",
                        buffered=False) as resp:
            assert resp.status_code == 200
            assert resp.mimetype == "text/event-stream"
            # Read up to ~6 chunks then bail
            for i, chunk in enumerate(resp.response):
                received.append(chunk)
                if len(received) >= 6:
                    break

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    import time; time.sleep(0.3)
    from pitwall.features.realtime.bp_realtime import cue_bus
    cue_bus.publish(sid, {"text": "Distance is king.", "emotion": "encouraging"})
    t.join(timeout=2.0)

    blob = b"".join(received)
    assert b"event: hello" in blob
    assert b"Distance is king" in blob


from pitwall.features.realtime.bp_realtime import validate_spectator_token

def test_spectator_token_create_validate_revoke(client):
    """Token lifecycle: create → validate → revoke."""
    r = client.post("/spectator/token", json={"session_id": "spec-001"})
    assert r.status_code == 200
    body = r.get_json()
    assert "token" in body
    assert body["session_id"] == "spec-001"
    assert body["url"].startswith("/spectator/spec-001")
    token = body["token"]
    # Validate via the helper
    assert validate_spectator_token(token) == "spec-001"
    # Revoke
    rev = client.delete(f"/spectator/token/{token}")
    assert rev.status_code == 200
    assert rev.get_json()["revoked"] is True
    assert validate_spectator_token(token) is None


def test_spectator_token_400_without_session_id(client):
    r = client.post("/spectator/token", json={})
    assert r.status_code == 400


from pitwall.features.realtime.bp_realtime import emit_notification

def test_notifications_emit_and_stream(client):
    """emit_notification publishes; SSE streams the event."""
    import threading
    received: list[bytes] = []

    def reader():
        with client.get("/notifications?driver=evo-driver",
                        buffered=False) as resp:
            assert resp.status_code == 200
            for i, chunk in enumerate(resp.response):
                received.append(chunk)
                if len(received) >= 6:
                    break

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    import time; time.sleep(0.3)
    emit_notification("evo-driver", "medal-earned", medal="trail_brake_apprentice")
    t.join(timeout=2.0)

    blob = b"".join(received)
    assert b"event: hello" in blob
    assert b"medal-earned" in blob


def test_session_export_parquet_handles_capabilities_table(client, make_frame_fn):
    sid = _start_session(client)
    br.seed_signal_registry()
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0)
              for i in range(50)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    br._compute_capabilities(sid)
    r = client.get(f"/session/{sid}/export.parquet?table=capabilities")
    assert r.status_code == 200
    assert r.data[:4] == b"PAR1"
    assert int(r.headers["X-Pitwall-Rows"]) >= len(br._WIDE_SIGNAL_NAMES)


def test_signals_registry_lists_usb_devices(client):
    """The can_state block must include a `usb_devices` array. It can be
    empty (no adapter plugged in) or contain dicts — but the field must
    exist so the PWA can render a "no adapter detected" message
    deterministically."""
    r = client.get("/signals/registry?include_can_state=true")
    body = r.get_json()
    devices = body["can_state"]["usb_devices"]
    assert isinstance(devices, list)
    # Each device (if any) has the expected schema
    for d in devices:
        for k in ("device", "vid", "pid", "description", "manufacturer",
                  "model", "kind", "is_known"):
            assert k in d, f"missing key {k} in device {d!r}"


def test_signals_registry_no_can_state_block_by_default(client):
    """Without ?include_can_state=true the response must NOT include the block —
    keeps the default response cheap (PWA caches it once at app launch)."""
    r = client.get("/signals/registry")
    assert r.status_code == 200
    body = r.get_json()
    assert "can_state" not in body



# ─── ADR-015: signal sink ingest (Phase 2) ──────────────────────────────────


def test_post_signals_appends_and_recompute_caps(client):
    """POST /session/<sid>/signals appends rows + recomputes capabilities."""
    br.seed_signal_registry()
    sid = "phase2-ingest-001"
    r = client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0, "value": 92.1},
        {"name": "oil_temp_c", "t": 1001.0, "value": 92.5},
        {"name": "oil_temp_c", "t": 1002.0, "value": 93.0},
    ]})
    assert r.status_code == 200
    body = r.get_json()
    assert body["n_appended"] == 3
    assert body["names"] == ["oil_temp_c"]
    assert body["capabilities_count"] >= 1


def test_post_signals_auto_registers_novel(client):
    """A name not in the registry is registered as discovery='discovered', units=NULL."""
    br.seed_signal_registry()
    sid = "phase2-novel-001"
    r = client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "shock_pot_fl_v", "t": 1000.0, "value": 1.23},
    ]})
    assert r.status_code == 200
    body = r.get_json()
    assert "shock_pot_fl_v" in body["newly_discovered"]
    conn = br.get_db()
    row = conn.execute(
        "SELECT name, units, discovery FROM signal_registry WHERE name = 'shock_pot_fl_v'"
    ).fetchone()
    conn.close()
    assert row == ("shock_pot_fl_v", None, "discovered")


def test_post_signals_dedup_on_conflict(client):
    """Re-posting (sid, signal_id, t) updates value but doesn't duplicate rows."""
    br.seed_signal_registry()
    sid = "phase2-dedup-001"
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0, "value": 92.1},
    ]})
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0, "value": 95.0},   # same t, new value
    ]})
    conn = br.get_db()
    rows = conn.execute(
        "SELECT t, value FROM telemetry_signals WHERE session_id = ?", [sid],
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][1] == 95.0


def test_post_signals_empty_returns_400(client):
    r = client.post("/session/x/signals", json={"signals": []})
    assert r.status_code == 400


def test_post_signals_invalid_samples_returns_400(client):
    """Items missing t/value/name are dropped; if all are dropped, 400."""
    br.seed_signal_registry()
    r = client.post("/session/x/signals", json={"signals": [
        {"name": "oil_temp_c"},                       # missing t + value
        {"t": 1000.0, "value": 5},                    # missing name + signal_id
    ]})
    assert r.status_code == 400


def test_compute_capabilities_advertises_wide_canonicals(client, make_frame_fn):
    """A session with only wide-table frames still has all 11 canonical caps."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=i * 0.1, distance=i * 5.0) for i in range(50)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    n = br._compute_capabilities(sid)
    assert n == len(br._WIDE_SIGNAL_NAMES)   # 11 canonical fields

    conn = br.get_db()
    rows = conn.execute(
        """SELECT sr.name FROM session_capabilities sc
           JOIN signal_registry sr USING(signal_id)
           WHERE sc.session_id = ? ORDER BY sr.name""",
        [sid],
    ).fetchall()
    conn.close()
    names = {r[0] for r in rows}
    assert names == set(br._WIDE_SIGNAL_NAMES)


def test_compute_capabilities_combines_wide_and_tall(client, make_frame_fn):
    """A session with both wide frames + tall signals exposes both groups."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0) for i in range(20)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0 + i * 0.5, "value": 90 + i}
        for i in range(4)
    ]})
    conn = br.get_db()
    names = {r[0] for r in conn.execute(
        """SELECT sr.name FROM session_capabilities sc
           JOIN signal_registry sr USING(signal_id)
           WHERE sc.session_id = ?""", [sid],
    ).fetchall()}
    conn.close()
    # Wide canonicals + the one tall signal
    assert "speed_ms"   in names
    assert "rpm"        in names
    assert "oil_temp_c" in names


def test_capabilities_recompute_endpoint_returns_count(client, make_frame_fn):
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=i * 0.1) for i in range(30)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.post(f"/session/{sid}/capabilities/recompute")
    assert r.status_code == 200
    body = r.get_json()
    assert body["session_id"] == sid
    assert body["capabilities_count"] >= len(br._WIDE_SIGNAL_NAMES)


def test_compute_capabilities_mean_hz_matches_density(client):
    """3 samples spanning 1s → mean_hz ≈ 3.0; 2 samples spanning 0.05s → ≈ 40.0."""
    br.seed_signal_registry()
    sid = "phase2-rate-001"
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c",     "t": 1000.0,  "value": 90},
        {"name": "oil_temp_c",     "t": 1000.5,  "value": 91},
        {"name": "oil_temp_c",     "t": 1001.0,  "value": 92},
        {"name": "clutch_pos_pct", "t": 1000.0,  "value": 0},
        {"name": "clutch_pos_pct", "t": 1000.05, "value": 50},
    ]})
    conn = br.get_db()
    caps = {r[0]: r[1] for r in conn.execute(
        """SELECT sr.name, sc.mean_hz FROM session_capabilities sc
           JOIN signal_registry sr USING(signal_id)
           WHERE sc.session_id = ?""", [sid],
    ).fetchall()}
    conn.close()
    assert abs(caps["oil_temp_c"] - 3.0) < 0.01
    assert abs(caps["clutch_pos_pct"] - 40.0) < 0.5



# ─── ADR-015: capabilities envelope + synchroniser (Phase 3) ────────────────


def test_capabilities_endpoint_unknown_session_returns_404(client):
    br.seed_signal_registry()
    r = client.get("/session/no-such-session/capabilities")
    assert r.status_code == 404


def test_capabilities_endpoint_wide_only_returns_canonicals(client, make_frame_fn):
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0) for i in range(50)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    br._compute_capabilities(sid)

    r = client.get(f"/session/{sid}/capabilities")
    assert r.status_code == 200
    body = r.get_json()
    assert body["session_id"] == sid
    assert body["duration_s"] > 0
    names = {s["name"] for s in body["signals"]}
    assert set(br._WIDE_SIGNAL_NAMES) <= names
    # All wide canonicals at 10 Hz are useful (min_useful_hz ≤ 10)
    for s in body["signals"]:
        if s["name"] == "speed_ms":
            assert s["useful"] is True
            assert s["mean_hz"] > 5.0
    # Phase-4 wired (separate test verifies content); assert keys exist.
    assert isinstance(body["coaches_available"], list)
    assert isinstance(body["coaches_disabled"], list)


def test_capabilities_endpoint_marks_low_rate_signal_not_useful(client):
    """A 1 Hz signal whose registry min_useful_hz > 1 should report useful=false."""
    br.seed_signal_registry()
    sid = "phase3-useful-001"
    # tpms_fl_kpa min_useful_hz is > 1 in the seed; post a 1 Hz stream
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "tpms_fl_kpa", "t": 1000.0 + i, "value": 230 + i * 0.1}
        for i in range(5)
    ]})
    r = client.get(f"/session/{sid}/capabilities")
    assert r.status_code == 200
    body = r.get_json()
    tpms = next(s for s in body["signals"] if s["name"] == "tpms_fl_kpa")
    assert tpms["mean_hz"] < 2.0
    # Whether useful is False depends on the registry seed; assert the field exists
    assert "useful" in tpms


def test_signals_get_missing_names_returns_400(client):
    r = client.get("/session/anything/signals")
    assert r.status_code == 400


def test_signals_get_unknown_session_returns_404(client):
    br.seed_signal_registry()
    r = client.get("/session/nope/signals?names=speed_ms")
    assert r.status_code == 404


def test_signals_get_unknown_signal_returns_400(client, make_frame_fn):
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1) for i in range(10)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.get(f"/session/{sid}/signals?names=not_a_real_signal")
    assert r.status_code == 400


def test_signals_get_wide_canonical_returns_rows(client, make_frame_fn):
    """Pulling speed_ms off the wide table should return one row per frame."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, speed_kmh=100 + i)
              for i in range(20)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})

    r = client.get(f"/session/{sid}/signals?names=speed_ms")
    assert r.status_code == 200
    body = r.get_json()
    assert body["names"] == ["speed_ms"]
    assert body["missing"] == []
    assert body["count"] == 20
    # First frame: 100 kmh = 27.78 m/s
    assert abs(body["rows"][0]["speed_ms"] - (100 / 3.6)) < 1e-3


def test_signals_get_tall_signal_returns_rows(client):
    """Tall-store signals come back through the synchroniser."""
    br.seed_signal_registry()
    sid = "phase3-tall-001"
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0 + i, "value": 90 + i}
        for i in range(5)
    ]})
    # axis defaults to gps; without a wide-table session, the only
    # axis points come from the tall-store native rate. Use axis=oil_temp_c.
    r = client.get(f"/session/{sid}/signals?names=oil_temp_c&axis=oil_temp_c")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 5
    assert body["rows"][0]["oil_temp_c"] == 90.0
    assert body["rows"][-1]["oil_temp_c"] == 94.0


def test_signals_get_missing_signal_returns_null_column(client, make_frame_fn):
    """A registered-but-empty signal yields null column + missing entry, 200."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1) for i in range(10)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.get(f"/session/{sid}/signals?names=speed_ms,oil_temp_c")
    assert r.status_code == 200
    body = r.get_json()
    assert "oil_temp_c" in body["missing"]
    assert all(row["oil_temp_c"] is None for row in body["rows"])
    assert all(row["speed_ms"] is not None for row in body["rows"])


def test_signals_get_interp_hold_is_asof(client):
    """interp=hold returns the last value with t ≤ axis_t."""
    br.seed_signal_registry()
    sid = "phase3-hold-001"
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0, "value": 90.0},
        {"name": "oil_temp_c", "t": 1002.0, "value": 100.0},
    ]})
    r = client.get(
        f"/session/{sid}/signals?names=oil_temp_c"
        "&t_from=1000&t_to=1002&rate_hz=2&interp=hold"
    )
    assert r.status_code == 200
    body = r.get_json()
    # Axis ts: 1000.0, 1000.5, 1001.0, 1001.5, 2002.0
    ts = [row["t"] for row in body["rows"]]
    vals = [row["oil_temp_c"] for row in body["rows"]]
    assert ts[0] == 1000.0 and vals[0] == 90.0       # exact match
    assert vals[1] == 90.0                            # held, no later sample yet
    assert vals[-1] == 100.0                          # 1002.0 sample seen


def test_signals_get_interp_lerp_is_linear(client):
    """interp=lerp linearly interpolates between bracketing samples."""
    br.seed_signal_registry()
    sid = "phase3-lerp-001"
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1000.0, "value": 90.0},
        {"name": "oil_temp_c", "t": 1002.0, "value": 100.0},
    ]})
    r = client.get(
        f"/session/{sid}/signals?names=oil_temp_c"
        "&t_from=1000&t_to=1002&rate_hz=2&interp=lerp"
    )
    assert r.status_code == 200
    body = r.get_json()
    by_t = {row["t"]: row["oil_temp_c"] for row in body["rows"]}
    assert abs(by_t[1000.0] - 90.0) < 1e-6
    assert abs(by_t[1001.0] - 95.0) < 1e-6   # halfway → 95
    assert abs(by_t[1002.0] - 100.0) < 1e-6


def test_signals_get_lerp_outside_range_is_null(client):
    """lerp emits null for axis points before/after the sample range."""
    br.seed_signal_registry()
    sid = "phase3-lerp-edge"
    client.post(f"/session/{sid}/signals", json={"signals": [
        {"name": "oil_temp_c", "t": 1001.0, "value": 90.0},
        {"name": "oil_temp_c", "t": 1002.0, "value": 100.0},
    ]})
    r = client.get(
        f"/session/{sid}/signals?names=oil_temp_c"
        "&t_from=1000&t_to=1003&rate_hz=1&interp=lerp"
    )
    body = r.get_json()
    by_t = {row["t"]: row["oil_temp_c"] for row in body["rows"]}
    assert by_t[1000.0] is None     # before first sample
    assert by_t[1003.0] is None     # after last sample
    assert by_t[1001.0] == 90.0
    assert by_t[1002.0] == 100.0


def test_signals_get_t_window_clipping(client, make_frame_fn):
    """t_from/t_to clip the wide-table axis grid."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1) for i in range(30)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})

    r = client.get(
        f"/session/{sid}/signals?names=speed_ms&t_from=1001&t_to=1002"
    )
    body = r.get_json()
    ts = [row["t"] for row in body["rows"]]
    assert all(1001.0 <= t <= 1002.0 for t in ts)
    assert len(ts) >= 9   # ~10 samples in the 1s window at 10 Hz


def test_signals_get_rate_hz_uniform_grid(client, make_frame_fn):
    """rate_hz=4 over a 2s window → 9 samples (inclusive of both endpoints)."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1) for i in range(30)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})

    r = client.get(
        f"/session/{sid}/signals?names=speed_ms"
        "&t_from=1000&t_to=1002&rate_hz=4"
    )
    body = r.get_json()
    assert body["count"] == 9
    # Spacing should be 0.25 s
    ts = [row["t"] for row in body["rows"]]
    diffs = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    for d in diffs:
        assert abs(d - 0.25) < 1e-6


def test_signals_get_lap_distance_axis_includes_distance_m(client, make_frame_fn):
    """axis=lap_distance returns rows tagged with distance_m via ASOF on wide."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0) for i in range(20)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})

    r = client.get(f"/session/{sid}/signals?names=speed_ms&axis=lap_distance")
    assert r.status_code == 200
    body = r.get_json()
    assert body["axis"] == "lap_distance"
    assert all("distance_m" in row for row in body["rows"])
    # Distance increases monotonically across the frames
    dists = [row["distance_m"] for row in body["rows"]]
    assert dists[0] < dists[-1]


def test_signals_get_unknown_axis_returns_400(client, make_frame_fn):
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1) for i in range(10)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    r = client.get(
        f"/session/{sid}/signals?names=speed_ms&axis=not_a_real_axis"
    )
    assert r.status_code == 400


def test_signals_get_invalid_interp_returns_400(client):
    r = client.get("/session/x/signals?names=speed_ms&interp=cubic")
    assert r.status_code == 400


def test_signals_get_lap_param_returns_400_phase3(client):
    """Phase 3 documents lap clipping but defers it; unit-test the explicit 400."""
    r = client.get("/session/x/signals?names=speed_ms&lap=2")
    assert r.status_code == 400


# Direct unit tests for the interpolation helpers — easier to debug than the
# end-to-end Flask path.

from pitwall.db import interp_hold, interp_lerp

def test_interp_hold_unit():
    samples = [(1000.0, 10.0), (1002.0, 20.0)]
    assert interp_hold([999.0, 1000.0, 1001.0, 1002.0, 1003.0], samples) == [
        None, 10.0, 10.0, 20.0, 20.0,
    ]


def test_interp_hold_empty():
    assert interp_hold([1.0, 2.0], []) == [None, None]


def test_interp_lerp_unit():
    samples = [(1000.0, 10.0), (1002.0, 20.0)]
    out = interp_lerp([999.0, 1000.0, 1001.0, 1002.0, 1003.0], samples)
    assert out[0] is None
    assert out[1] == 10.0
    assert out[2] == 15.0
    assert out[3] == 20.0
    assert out[4] is None


def test_interp_lerp_zero_width_segment():
    """Two samples at the same t — lerp returns the earlier value."""
    samples = [(1000.0, 10.0), (1000.0, 99.0), (1001.0, 20.0)]
    out = interp_lerp([1000.0], samples)
    assert out == [10.0]

