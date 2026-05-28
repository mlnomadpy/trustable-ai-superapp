"""Round-trip CAN pipeline tests.

Both reader and simulator share python-can's `interface='virtual'` bus.
Multiple Bus instances on the same channel see each other's frames in pure
Python — no kernel modules, no permissions, works in CI.

These tests also serve as the canonical example of the CAN data path:
encode → bus → decode → DuckDB.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]          # apps/edge-daemon
sys.path.insert(0, str(ROOT))                        # → import pitwall
sys.path.insert(0, str(ROOT / "simulator"))          # → import can_simulator

import can
import cantools

import pitwall as br

# Rewritten 2026-05-28 for the AiM MXP DBC schema (ADR-016): the producer
# sends *raw* AiM frames (SmartyCam01 / AimExtended06_Accel / …) and the
# CanReader runs them through the bmw_e46_m3.yaml pipeline, which is what
# converts raw signals (lateral_accel_g, speed_mph, brake_press_psi) into the
# wide-table canonicals (g_lat, speed_ms, brake_bar). This is the real
# production path, end to end.
from pitwall.features.telemetry.can_reader import CanReader, DEFAULT_DBC


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    """Each test gets a clean DuckDB file with the schema initialised.

    Production runs DDL once at boot via state.init_imports(); tests rotate
    db_path per fixture so each fresh DB needs its own schema init (V2 hoisted
    DDL out of the per-connection path)."""
    monkeypatch.setattr(br.state, "db_path", str(tmp_path / "can.duckdb"))
    monkeypatch.setattr(br.state, "has_duckdb", True)
    br.db.init_schema_once()
    yield


@pytest.fixture
def virtual_channel(request):
    """Unique channel per test so concurrent tests don't share traffic."""
    return f"pitwall_test_{request.node.name}"


@pytest.fixture
def producer_bus(virtual_channel):
    """The 'simulator' side of the bus — we send frames into this."""
    bus = can.Bus(interface="virtual", channel=virtual_channel)
    yield bus
    bus.shutdown()


@pytest.fixture
def reader(virtual_channel, isolated_db):
    """A started CanReader consuming the same virtual channel."""
    r = CanReader(
        session_id="test-can-001",
        interface="virtual",
        channel=virtual_channel,
        flush_ms=20,                # tighter flush for fast tests
    )
    r.start()
    yield r
    r.stop(timeout=1.0)


@pytest.fixture(scope="module")
def db():
    return cantools.database.load_file(str(DEFAULT_DBC))


# ── Helpers ──────────────────────────────────────────────────────────────


def _send(producer_bus, db, msg_name, signals, t):
    msg = db.get_message_by_name(msg_name)
    producer_bus.send(can.Message(
        arbitration_id=msg.frame_id,
        data=msg.encode(signals),
        timestamp=t,
        is_extended_id=False,
    ))


# ── Tests ────────────────────────────────────────────────────────────────


# Complete signal dicts per AiM message (cantools.encode needs every signal).
# Profile-plausible values; the YAML pipeline converts the raw ones.
_ACCEL = {"inline_accel_g": -0.8, "lateral_accel_g": 0.5, "vertical_accel_g": -0.99}
_SC01 = {"rpm": 5400.0, "speed_mph": 62.0, "gear": 0.0, "water_temp_f": 190.0}
_SC04 = {"steer_angle_deg": -3.2, "yaw_rate_degs_std": 0.0,
         "lateral_accel_g_std": 0.5, "inline_accel_g_std": -0.8}
_ECU3 = {"engine_oil_temp_f": 230.0, "ambient_temp_f": 75.0,
         "steer_angle_deg_ext": -3.2, "pedal_pos_pct": 88.0}
_ANALOG20 = {"oil_press_psi": 60.0, "water_press_psi_an": 20.0,
             "fuel_press_psi": 45.0, "brake_press_psi": 145.0377}


def test_reader_imports_dbc_with_expected_messages(db):
    """The shipped DBC is the AiM MXP SmartyCam protocol (ADR-016)."""
    names = {m.name for m in db.messages}
    assert {
        "SmartyCam01", "SmartyCam04", "SmartyCam05",
        "AimExtended02_WheelSpeeds", "AimExtended03_ECU3",
        "AimExtended06_Accel", "AimExtended08_Analog20",
        "AimExtended10_GPS", "AimExtended11_TpmsPress",
    } <= names


def test_round_trip_motion_frame_sinks_to_wide_table(reader, producer_bus, db):
    """Raw AiM frames → YAML pipeline → wide-table canonicals.

    Sends the burst of frames that together fill a wide row (accel → g_*,
    SmartyCam01 → speed_ms/rpm, ECU3 → throttle_pct, Analog20 → brake_bar,
    SmartyCam04 → steering_deg), then force-flushes and reads the latest row.
    The wide buffer accumulates across frames, so the final row carries every
    canonical produced during the burst."""
    _send(producer_bus, db, "AimExtended06_Accel", _ACCEL, t=1000.000)
    _send(producer_bus, db, "SmartyCam01", _SC01, t=1000.005)
    _send(producer_bus, db, "AimExtended03_ECU3", _ECU3, t=1000.010)
    _send(producer_bus, db, "AimExtended08_Analog20", _ANALOG20, t=1000.015)
    _send(producer_bus, db, "SmartyCam04", _SC04, t=1000.020)

    time.sleep(0.5)
    reader._flush_wide(force=True)

    conn = br.get_db()
    row = conn.execute(
        "SELECT speed_ms, g_lat, g_long, combo_g, "
        "       throttle_pct, brake_bar, steering_deg, rpm "
        "FROM telemetry WHERE session_id = ? ORDER BY frame_idx DESC LIMIT 1",
        ["test-can-001"],
    ).fetchone()
    conn.close()

    assert row is not None
    assert abs(row[0] - 27.7165) < 0.02    # speed_ms (62 mph)
    assert abs(row[1] - 0.5) < 0.001       # g_lat (lateral_accel_g)
    assert abs(row[2] - (-0.8)) < 0.001    # g_long (inline_accel_g)
    assert abs(row[3] - 0.9434) < 0.01     # combo_g (cross-derived)
    assert abs(row[4] - 88.0) < 0.01       # throttle_pct (pedal_pos_pct)
    assert abs(row[5] - 10.0) < 0.05       # brake_bar (psi → bar)
    assert abs(row[6] - (-3.2)) < 0.05     # steering_deg
    assert abs(row[7] - 5400.0) < 1.0      # rpm


def test_round_trip_oil_temp_sinks_to_tall_store(reader, producer_bus, db):
    """Engine oil temp is not a wide canonical → lands in telemetry_signals.

    AiM frame AimExtended03_ECU3 carries `engine_oil_temp_f`; the YAML derives
    `engine_oil_temp_c`. Both go to the tall store."""
    br.seed_signal_registry()
    # 194/197/...°F → 90/91.7/... °C
    for i in range(5):
        f = _ECU3 | {"engine_oil_temp_f": 194.0 + i * 1.8}  # +1 °C steps
        _send(producer_bus, db, "AimExtended03_ECU3", f, t=1000.0 + i * 0.5)

    time.sleep(0.5)

    conn = br.get_db()
    rows = conn.execute(
        """SELECT t, value FROM telemetry_signals ts
           JOIN signal_registry sr USING(signal_id)
           WHERE ts.session_id = ? AND sr.name = 'engine_oil_temp_c'
           ORDER BY t""",
        ["test-can-001"],
    ).fetchall()
    conn.close()

    assert len(rows) == 5
    assert rows[0][1] == pytest.approx(90.0, abs=0.05)
    assert rows[-1][1] == pytest.approx(94.0, abs=0.05)


def test_novel_signal_auto_registers_via_decoded_name(reader, producer_bus, db):
    """A signal decoded from the DBC that isn't in the obd2 seed should
    auto-register on first sighting (ADR-015 'discovered' path).

    `luminosity_pct` (AimExtended09_Analog1) is an AiM logger channel not in
    obd2_pids.json — it must appear in the registry after ingest."""
    _send(producer_bus, db, "AimExtended09_Analog1", {
        "oil_filter_temp_f": 200.0, "luminosity_pct": 73.0, "logger_temp_f": 95.0,
    }, t=1000.0)

    time.sleep(0.5)

    conn = br.get_db()
    row = conn.execute(
        "SELECT discovery FROM signal_registry WHERE name = 'luminosity_pct'",
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] in ("static_obd2", "static_dbc", "discovered")


def test_unknown_can_id_is_silently_dropped(reader, producer_bus):
    """Frames with arbitration_ids not in the DBC must not crash the reader."""
    producer_bus.send(can.Message(
        arbitration_id=0x7FF,        # not in pitwall.dbc
        data=b"\x00" * 8,
        is_extended_id=False,
    ))
    # Send a known AiM frame after to confirm the reader is still alive.
    db_local = cantools.database.load_file(str(DEFAULT_DBC))
    _send(producer_bus, db_local, "AimExtended06_Accel", _ACCEL, t=2000.0)
    _send(producer_bus, db_local, "SmartyCam01", _SC01, t=2000.005)

    time.sleep(0.5)

    conn = br.get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM telemetry WHERE session_id = ?",
        ["test-can-001"],
    ).fetchone()[0]
    conn.close()
    assert n >= 1


def test_capabilities_after_can_ingest(reader, producer_bus, db):
    """A session populated entirely via AiM CAN should produce capabilities
    that include the wide canonicals + the tall signals seen on the bus."""
    br.seed_signal_registry()

    for i in range(20):
        t = 1000.0 + i * 0.1
        _send(producer_bus, db, "AimExtended06_Accel",
              _ACCEL | {"lateral_accel_g": 0.1 * i}, t=t)
        _send(producer_bus, db, "SmartyCam01",
              _SC01 | {"speed_mph": 40.0 + i}, t=t)
        _send(producer_bus, db, "AimExtended03_ECU3", _ECU3, t=t)
        if i % 5 == 0:
            _send(producer_bus, db, "AimExtended08_Analog20", _ANALOG20, t=t)

    time.sleep(0.7)
    n_caps = br._compute_capabilities("test-can-001")

    assert n_caps >= len(br._WIDE_SIGNAL_NAMES)

    conn = br.get_db()
    names = {r[0] for r in conn.execute(
        """SELECT sr.name FROM session_capabilities sc
           JOIN signal_registry sr USING(signal_id)
           WHERE sc.session_id = ?""", ["test-can-001"],
    ).fetchall()}
    conn.close()
    assert "speed_ms" in names
    assert "g_lat" in names
    assert "engine_oil_temp_c" in names


def test_dead_reckoner_advances_distance_from_speed(reader, producer_bus, db):
    """ADR-018: AiM exposes no distance CAN signal — distance_m is dead-
    reckoned by integrating speed. Drive ~28 m/s (62 mph) on SmartyCam01 with
    real-time spacing and confirm the wide-row distance creeps forward
    monotonically."""
    br.seed_signal_registry()
    for _ in range(20):
        # Real-time spacing — the virtual bus stamps msg.timestamp with the
        # receiver wall-clock, so the dead-reckoner needs actual elapsed time
        # to integrate motion. ~10 ms/frame ≈ 100 Hz.
        time.sleep(0.010)
        _send(producer_bus, db, "SmartyCam01", _SC01, t=0)

    time.sleep(0.3)
    reader._flush_wide(force=True)

    conn = br.get_db()
    rows = conn.execute(
        "SELECT timestamp, distance_m FROM telemetry "
        "WHERE session_id = ? ORDER BY timestamp",
        ["test-can-001"],
    ).fetchall()
    conn.close()

    assert len(rows) >= 3, f"expected ≥3 wide rows, got {len(rows)}"
    final_distance = rows[-1][1]
    # 20 frames × ~10 ms × 27.7 m/s ≈ 5.5 m of true travel. Loose bounds.
    assert final_distance > 1.0, (
        f"dead-reckoned distance never advanced past 1 m: {final_distance}"
    )
    distances = [r[1] for r in rows]
    assert all(b >= a - 0.01 for a, b in zip(distances, distances[1:])), (
        f"distance went backwards: {distances}"
    )
