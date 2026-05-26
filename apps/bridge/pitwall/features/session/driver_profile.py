"""
Event-sourced driver profile — per ADR-007 + ADR-014.

Append-only `driver_events` table. Pre-brief reads it
(weakest_recent_corner, best_recent_improvement, plateau detection).
Post-debrief writes to it. Profile is *computed*, not stored — adding
a new event kind never requires a migration.

Backend-portable across DuckDB (Mac dev) and SQLite (Termux/Android).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional

from pitwall.db import db_backend


_DUCKDB_SCHEMA = """
CREATE SEQUENCE IF NOT EXISTS driver_events_id_seq;
CREATE TABLE IF NOT EXISTS driver_events (
    id           INTEGER PRIMARY KEY DEFAULT nextval('driver_events_id_seq'),
    driver_id    VARCHAR,
    session_id   VARCHAR,
    corner       VARCHAR,
    event_kind   VARCHAR,
    value_num    DOUBLE,
    value_str    VARCHAR,
    recorded_at  TIMESTAMP DEFAULT now()
);
"""

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS driver_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id    TEXT,
    session_id   TEXT,
    corner       TEXT,
    event_kind   TEXT,
    value_num    REAL,
    value_str    TEXT,
    recorded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA = _DUCKDB_SCHEMA if db_backend() == "duckdb" else _SQLITE_SCHEMA


@dataclass
class DriverEvent:
    """A single event in the driver's append-only profile store."""
    driver_id: str
    session_id: str
    corner: str
    event_kind: str             # 'grade' | 'apex_speed' | 'mistake' | 'improvement' | 'pb_lap_s'
    value_num: float = 0.0
    value_str: str = ""


def ensure_schema(conn) -> None:
    """Create the driver_events table if it does not exist."""
    if db_backend() == "sqlite":
        conn.executescript(SCHEMA)
    else:
        conn.execute(SCHEMA)


def append_event(conn, e: DriverEvent) -> None:
    """Write a single DriverEvent row to DuckDB."""
    conn.execute(
        "INSERT INTO driver_events (driver_id, session_id, corner, event_kind, value_num, value_str) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [e.driver_id, e.session_id, e.corner, e.event_kind, e.value_num, e.value_str],
    )


def append_session_events(conn, driver_id: str, session_id: str,
                          scorecard_dict: dict) -> int:
    """Take a SessionScorecard dict and write per-corner grade events."""
    ensure_schema(conn)
    n = 0
    for cg in scorecard_dict.get("corners", []):
        append_event(conn, DriverEvent(
            driver_id=driver_id,
            session_id=session_id,
            corner=cg["corner"],
            event_kind="grade",
            value_num=cg["score_pct"],
            value_str=cg["grade"],
        ))
        n += 1
    # Session-level event for plateau detection
    if "best_lap_s" in scorecard_dict:
        append_event(conn, DriverEvent(
            driver_id=driver_id,
            session_id=session_id,
            corner="*",
            event_kind="pb_lap_s",
            value_num=scorecard_dict["best_lap_s"],
        ))
    return n


def compute_profile(conn, driver_id: str, max_sessions: int = 20) -> dict:
    """Compute the driver's profile from the event store.

    Returns a dict suitable for the pre-brief LLM prompt:
        {weakest_recent_corner, best_recent_improvement, plateau_state, ...}
    """
    ensure_schema(conn)

    # Recent grade events per corner
    rows = conn.execute(
        "SELECT session_id, corner, value_num, value_str, recorded_at "
        "FROM driver_events "
        "WHERE driver_id = ? AND event_kind = 'grade' "
        "ORDER BY recorded_at DESC LIMIT ?",
        [driver_id, max_sessions * 11],
    ).fetchall()

    by_corner: dict[str, list[dict]] = {}
    for sid, corner, score, grade, ts in rows:
        by_corner.setdefault(corner, []).append({
            "session_id":  sid,
            "score_pct":   float(score),
            "grade":       grade,
            "recorded_at": ts,
        })

    # Weakest corner — lowest mean score across recent sessions
    weakest = None
    if by_corner:
        means = {c: statistics.mean(h["score_pct"] for h in hs)
                 for c, hs in by_corner.items() if hs}
        if means:
            weakest = min(means.items(), key=lambda kv: kv[1])

    # Biggest improvement — corner where last grade > 2nd-to-last by most.
    # `hs[0]` is most recent (DESC by recorded_at). Filter to genuine
    # improvements (positive deltas) so a regression doesn't masquerade
    # as the biggest improvement.
    biggest_impr = None
    for corner, hs in by_corner.items():
        if len(hs) >= 2:
            delta = hs[0]["score_pct"] - hs[1]["score_pct"]
            if delta <= 0:
                continue
            if biggest_impr is None or delta > biggest_impr[1]:
                biggest_impr = (corner, delta)

    # Plateau check on best lap
    pb_rows = conn.execute(
        "SELECT session_id, value_num "
        "FROM driver_events "
        "WHERE driver_id = ? AND event_kind = 'pb_lap_s' "
        "ORDER BY recorded_at",
        [driver_id],
    ).fetchall()
    pb_history = [(sid, float(v)) for sid, v in pb_rows]

    return {
        "driver_id":             driver_id,
        "weakest_recent_corner": weakest[0] if weakest else None,
        "weakest_recent_score":  round(weakest[1], 3) if weakest else None,
        "biggest_improvement":   {
            "corner": biggest_impr[0],
            "delta_score":  round(biggest_impr[1], 3),
        } if biggest_impr else None,
        "best_lap_history": [
            {"session_id": sid, "lap_s": round(v, 3)}
            for sid, v in pb_history
        ],
        "n_recent_grade_events": len(rows),
    }


__all__ = [
    "SCHEMA", "DriverEvent", "ensure_schema",
    "append_event", "append_session_events", "compute_profile",
]
