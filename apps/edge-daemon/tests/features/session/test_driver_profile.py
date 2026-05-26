"""Unit tests for src/simulator/driver_profile.py."""
import pytest

from pitwall.features.session.driver_profile import (
    SCHEMA, DriverEvent, ensure_schema,
    append_event, append_session_events, compute_profile,
)


def test_ensure_schema_idempotent(ephemeral_db):
    """Two calls in a row must not raise."""
    ensure_schema(ephemeral_db)
    ensure_schema(ephemeral_db)
    # Sanity: table exists
    rows = ephemeral_db.execute(
        "SELECT count(*) FROM driver_events"
    ).fetchone()
    assert rows[0] == 0


def test_driver_event_dataclass_defaults():
    e = DriverEvent(driver_id="x", session_id="s", corner="Turn 1",
                    event_kind="grade")
    assert e.value_num == 0.0
    assert e.value_str == ""


def test_append_event_persists(ephemeral_db):
    ensure_schema(ephemeral_db)
    append_event(ephemeral_db, DriverEvent(
        driver_id="d1", session_id="sess1", corner="Turn 1",
        event_kind="grade", value_num=0.92, value_str="A",
    ))
    rows = ephemeral_db.execute(
        "SELECT driver_id, corner, event_kind, value_num, value_str "
        "FROM driver_events"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "d1"
    assert rows[0][2] == "grade"
    assert rows[0][3] == 0.92


def test_compute_profile_no_events(ephemeral_db):
    ensure_schema(ephemeral_db)
    p = compute_profile(ephemeral_db, "ghost_driver")
    assert p["driver_id"] == "ghost_driver"
    assert p["weakest_recent_corner"] is None
    assert p["biggest_improvement"] is None
    assert p["best_lap_history"] == []


def test_compute_profile_picks_weakest_corner(ephemeral_db):
    ensure_schema(ephemeral_db)
    # T1 is consistently better than T11 — T11 should be flagged weakest
    for sid, corner, score, grade in [
        ("s1", "Turn 1", 0.92, "B"),
        ("s2", "Turn 1", 0.94, "B"),
        ("s1", "Turn 11", 0.65, "F"),
        ("s2", "Turn 11", 0.60, "F"),
    ]:
        append_event(ephemeral_db, DriverEvent(
            driver_id="d", session_id=sid, corner=corner,
            event_kind="grade", value_num=score, value_str=grade,
        ))
    p = compute_profile(ephemeral_db, "d")
    assert p["weakest_recent_corner"] == "Turn 11"


def test_compute_profile_biggest_improvement_filters_negative(ephemeral_db):
    """Regression (AUDIT.md): if most-recent score is *worse* than prior,
    biggest_improvement should NOT show that corner."""
    ensure_schema(ephemeral_db)
    # T1 improved from 0.70 to 0.85 (+0.15)
    # T11 regressed from 0.85 to 0.65 (-0.20) — should be ignored
    import time as _t
    for sid, corner, score, ts in [
        ("s_old", "Turn 1", 0.70, _t.time() - 100),
        ("s_new", "Turn 1", 0.85, _t.time() - 50),
        ("s_old", "Turn 11", 0.85, _t.time() - 100),
        ("s_new", "Turn 11", 0.65, _t.time() - 50),
    ]:
        append_event(ephemeral_db, DriverEvent(
            driver_id="d2", session_id=sid, corner=corner,
            event_kind="grade", value_num=score,
        ))
    p = compute_profile(ephemeral_db, "d2")
    if p["biggest_improvement"]:
        assert p["biggest_improvement"]["corner"] != "Turn 11"
        assert p["biggest_improvement"]["delta_score"] > 0


def test_append_session_events_writes_per_corner(ephemeral_db):
    ensure_schema(ephemeral_db)
    scorecard = {
        "session_id": "s1",
        "best_lap_s": 105.5,
        "corners": [
            {"corner": "Turn 1", "score_pct": 0.92, "grade": "B"},
            {"corner": "Turn 6", "score_pct": 0.85, "grade": "C"},
        ],
    }
    n = append_session_events(ephemeral_db, "d3", "s1", scorecard)
    assert n == 2
    rows = ephemeral_db.execute(
        "SELECT count(*) FROM driver_events WHERE driver_id='d3'"
    ).fetchone()
    # 2 grade events + 1 pb_lap_s event
    assert rows[0] == 3


def test_append_session_events_writes_pb_lap_s(ephemeral_db):
    ensure_schema(ephemeral_db)
    scorecard = {"session_id": "s9", "best_lap_s": 99.5, "corners": []}
    append_session_events(ephemeral_db, "dpb", "s9", scorecard)
    rows = ephemeral_db.execute(
        "SELECT corner, event_kind, value_num FROM driver_events "
        "WHERE driver_id='dpb'"
    ).fetchall()
    assert any(r[1] == "pb_lap_s" and r[2] == 99.5 for r in rows)


def test_compute_profile_pb_history_sorted_chronologically(ephemeral_db):
    ensure_schema(ephemeral_db)
    # Insert in non-chronological order
    for sid, t in [("s2", 105.0), ("s1", 110.0), ("s3", 100.0)]:
        append_event(ephemeral_db, DriverEvent(
            driver_id="dp", session_id=sid, corner="*",
            event_kind="pb_lap_s", value_num=t,
        ))
    p = compute_profile(ephemeral_db, "dp")
    history = p["best_lap_history"]
    # SQL ORDER BY recorded_at ASC — insertion order
    assert [h["session_id"] for h in history] == ["s2", "s1", "s3"]


def test_schema_constant_is_sql_string():
    assert "CREATE TABLE" in SCHEMA
    assert "driver_events" in SCHEMA
