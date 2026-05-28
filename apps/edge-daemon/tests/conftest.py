"""
Shared pytest fixtures for the Pitwall backend test suite.

Adds `src/simulator/` to sys.path so tests can `import pitwall.features.track.sonoma as sonoma` etc. without
a package install. Provides synthetic frame generators + a frozen track +
a tiny gold-standard fixture so analytics tests don't need to read disk.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]          # apps/edge-daemon
sys.path.insert(0, str(ROOT))                        # → import pitwall
sys.path.insert(0, str(ROOT / "simulator"))          # → import aim_mxp_simulator, can_simulator

# Data fixtures live at the monorepo root after the V2 consolidation. The
# `data/` tree was never moved under `apps/edge-daemon/`, so test paths
# pointing at tracks / gold-standard JSONs resolve against the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]



# ─── Synthetic frame builder ─────────────────────────────────────────────────


def make_frame(*, t=0.0, distance=0.0, speed_kmh=100.0, brake_bar=0.0,
               throttle_pct=80.0, steering_deg=0.0, g_lat=0.0, g_long=0.0,
               rpm=4500.0, lat=23.49, lon=-73.78, avitime=0.0):
    """Build a single frame as a SimpleNamespace — duck-types `TelemetryFrame`."""
    speed_ms = speed_kmh / 3.6
    combo_g = math.hypot(g_lat, g_long)
    return SimpleNamespace(
        timestamp=t, distance=distance,
        speed=speed_ms, lat=lat, lon=lon, heading=0.0, altitude=0.0,
        g_lat=g_lat, g_long=g_long, combo_g=combo_g,
        brake_pressure=brake_bar, brake_position=brake_bar / 100,
        throttle=throttle_pct, steering=steering_deg, rpm=rpm,
        coolant_temp=88.0, oil_temp=95.0, fuel_level=50.0,
        avitime=avitime, lap=0, lap_time=0.0,
        distance_to_corner=0.0, corner_name="", corner_severity=0,
    )


@pytest.fixture
def make_frame_fn():
    return make_frame


@pytest.fixture
def synth_multi_lap_frames():
    """Build N synthetic laps for lap-detection testing.

    Each lap is 90 seconds, distance wraps 0 → 4258 → 0. Laps differ slightly
    in speed so lap times are not identical (forces best-lap arg-min to pick
    a single winner).

    Returns 3 laps × 900 frames = 2700 frames at 10 Hz.
    """
    frames = []
    track_len = 4258.0
    laps_per_session = 3
    n_per_lap = 900
    base_t = 1000.0
    base_d = 0.0
    corner_distances = [56, 536, 668, 976, 1098, 1294, 1540, 1586, 1820, 2556, 4100]
    for lap_idx in range(laps_per_session):
        speed_factor = 1.0 + lap_idx * 0.05  # later laps slightly faster
        for i in range(n_per_lap):
            d = (i / (n_per_lap - 1)) * track_len
            t = base_t + i * 0.1 / speed_factor
            gaps = [(c - d) % track_len for c in corner_distances]
            nearest_gap = min(gaps)
            if nearest_gap < 80:
                t_in = 1 - (nearest_gap / 80)
                speed_kmh = (110 - 60 * t_in) * speed_factor
                brake_bar = 30 * t_in if nearest_gap > 20 else 5 * t_in
                g_lat = 1.2 * t_in
                throttle = 20 if nearest_gap < 30 else 60
            else:
                speed_kmh = 170 * speed_factor
                brake_bar = 0
                g_lat = 0
                throttle = 99
            prev = frames[-1] if frames else None
            prev_kmh = (prev.speed * 3.6) if prev else speed_kmh
            g_long = (speed_kmh - prev_kmh) / 9.81 if prev else 0
            frames.append(make_frame(
                t=t, distance=d,
                speed_kmh=speed_kmh, brake_bar=brake_bar,
                throttle_pct=throttle, g_lat=g_lat, g_long=g_long,
                steering_deg=g_lat * 30,
                rpm=2000 + (speed_kmh / 200) * 6500,
            ))
        base_t = frames[-1].timestamp + 0.1
    return frames


@pytest.fixture
def synth_lap_frames():
    """Build a synthetic 90-second lap: 11 corners, slow-fast-slow pattern.

    Returns a list of ~900 SimpleNamespace frames at 10 Hz.
    Distance progresses 0 → ~4258 m linearly. Brake/throttle/g_lat
    profiles are simple sinusoids tuned so each corner has a peak G + some
    braking + a min-speed dip.
    """
    frames = []
    track_len = 4258.0
    n = 900
    corner_distances = [56, 536, 668, 976, 1098, 1294, 1540, 1586, 1820, 2556, 4100]
    for i in range(n):
        d = (i / (n - 1)) * track_len
        # Distance to nearest upcoming corner
        gaps = [(c - d) % track_len for c in corner_distances]
        nearest_gap = min(gaps)
        nearest_corner_d = corner_distances[gaps.index(nearest_gap)]

        if nearest_gap < 80:
            # In or near corner — drop speed, raise gLat, brake
            t_in_corner = 1 - (nearest_gap / 80)
            speed_kmh = 110 - 60 * t_in_corner
            brake_bar = 30 * t_in_corner if nearest_gap > 20 else 5 * t_in_corner
            g_lat = 1.2 * t_in_corner * (1 if nearest_corner_d % 2 == 0 else -1)
            throttle = 20 if nearest_gap < 30 else 60
        else:
            # On a straight — full throttle
            speed_kmh = 170
            brake_bar = 0
            g_lat = 0
            throttle = 99

        prev = frames[-1] if frames else None
        prev_kmh = (prev.speed * 3.6) if prev else speed_kmh
        g_long = (speed_kmh - prev_kmh) / 9.81 if prev else 0

        frames.append(make_frame(
            t=i * 0.1, distance=d,
            speed_kmh=speed_kmh, brake_bar=brake_bar, throttle_pct=throttle,
            g_lat=g_lat, g_long=g_long,
            steering_deg=g_lat * 30,
            rpm=2000 + (speed_kmh / 200) * 6500,
            avitime=i * 100,
        ))
    return frames


# ─── Track + gold fixtures ───────────────────────────────────────────────────


@pytest.fixture
def real_track_path():
    """Path to the real, on-disk Sonoma track JSON."""
    return REPO_ROOT / "data" / "tracks" / "sonoma.json"


@pytest.fixture
def real_track(real_track_path):
    from pitwall.features.track.track_loader import load_track
    return load_track(str(real_track_path))


@pytest.fixture
def real_gold_path():
    return REPO_ROOT / "data" / "reference" / "sonoma_gold.json"


@pytest.fixture
def real_gold(real_gold_path):
    from pitwall.features.track.gold_standard import load_gold_standard
    return load_gold_standard(str(real_gold_path))


@pytest.fixture
def synth_corner_pass():
    """Build one CornerPass for unit-testing the grader."""
    from pitwall.features.session.corner_grader import CornerPass
    return CornerPass(
        corner="Turn 10", lap=1,
        entry_speed_kmh=120, apex_speed_kmh=70, exit_speed_kmh=110,
        min_speed_kmh=68, peak_brake_bar=45,
        brake_point_m=124, brake_release_m=10,
        trail_brake_bar_at_apex=8, throttle_at_exit_pct=65,
        max_g_lat=1.4, max_combo_g=1.7,
        corner_time_s=4.2,
        coast_seconds=0.0, steering_corrections=1, nothing_time_s=0.1,
    )


@pytest.fixture
def synth_gold_corner_pass():
    """Build one GoldCornerPass that the synth_corner_pass should grade against."""
    from pitwall.features.track.gold_standard import GoldCornerPass
    return GoldCornerPass(
        corner="Turn 10",
        entry_speed_kmh=120, apex_speed_kmh=73, exit_speed_kmh=115,
        min_speed_kmh=70, peak_brake_bar=47,
        brake_point_m=124, brake_release_m=12,
        trail_brake_bar_at_apex=10, throttle_at_exit_pct=70,
        max_g_lat=1.5, max_combo_g=1.8,
        corner_time_s=4.0,
        apex_distance_m=2626, entry_distance_m=2556, exit_distance_m=2752,
    )


# ─── Ephemeral DuckDB fixture ────────────────────────────────────────────────


@pytest.fixture
def ephemeral_db(tmp_path):
    """Yield a clean DuckDB connection backed by a temp file. Cleans up on teardown."""
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    yield conn
    conn.close()


# ─── Optional: real-data smoke fixture (used by integration tests) ───────────


FORZA_VBO = "/Users/tahabsn/Documents/GitHub/forza/data/Sonoma Intermediate - 1_47.5.vbo"


@pytest.fixture
def forza_vbo_path():
    """Path to the canonical 1:47.5 BMW M3 Sonoma VBO. Skip the test if missing."""
    p = Path(FORZA_VBO)
    if not p.exists():
        pytest.skip(f"forza dataset not available at {FORZA_VBO}")
    return p

import pitwall as br
from pitwall.features.track.track_loader import load_track
from pitwall.features.session.session_analyzer import analyze_session
import pitwall.features.track.sonoma as sonoma
from pitwall.features.coaching.cue_renderer import estimate_tts_ms
from pitwall.features.session.laps import detect_laps, quantile
from pitwall.db import log_llm_friction
from pitwall.features.realtime.bp_realtime import cue_bus

@pytest.fixture(autouse=True)
def isolated_bridge(monkeypatch, tmp_path):
    """Each test gets a clean DuckDB file + fresh in-memory state."""
    monkeypatch.setattr(br.state, "db_path", str(tmp_path / "test.duckdb"))
    monkeypatch.setattr(br.state, "has_duckdb", True)
    monkeypatch.setattr(br.state, "has_analyzer", True)
    monkeypatch.setattr(br.state, "has_coach", False)
    monkeypatch.setattr(br.state, "has_sonic", False)
    monkeypatch.setattr(br.state, "sonoma", sonoma)
    monkeypatch.setattr(br.state, "session_bundles", {})
    monkeypatch.setattr(br.state, "session_bursts", [])
    monkeypatch.setattr(
        br.state, "track",
        load_track(str(REPO_ROOT / "data" / "tracks" / "sonoma.json")),
    )
    monkeypatch.setattr(br.state, "coach", None)
    monkeypatch.setattr(br.state, "arbiter", None)
    # Production runs DDL once at boot via state.init_imports(); tests rotate
    # db_path per fixture so each fresh DuckDB needs its own schema init.
    br.db.init_schema_once()


@pytest.fixture
def client():
    app = br.create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _frames_to_payload(frames):
    return [{
        "timestamp": f.timestamp, "distance": f.distance,
        "speed": f.speed, "g_lat": f.g_lat, "g_long": f.g_long,
        "combo_g": f.combo_g, "brake_pressure": f.brake_pressure,
        "throttle": f.throttle, "steering": f.steering,
        "rpm": f.rpm, "lat": f.lat, "lon": f.lon,
    } for f in frames]


_SID_COUNTER = [0]


def _start_session(client, **body):
    """Generate a synthetic session_id.

    Master removed the explicit /session/start lifecycle in favour of an
    implicit model: any string can be a session_id, and per-frame /
    per-burst endpoints accept it as-is. This helper preserves the
    previous test-suite shape while matching the new API.
    """
    _SID_COUNTER[0] += 1
    return f"test-sid-{_SID_COUNTER[0]:03d}"


