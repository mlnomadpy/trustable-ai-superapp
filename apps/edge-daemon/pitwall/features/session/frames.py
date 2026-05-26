"""pitwall.features.session.frames — frame I/O between objects, DuckDB rows.

Pure domain logic with no Flask dependency. Can be unit-tested independently.
"""

from types import SimpleNamespace

from pitwall.state import state
from pitwall.db import db_conn, DuckDbUnavailable


def frames_to_rows(session_id: str, frames) -> list:
    """Map a list of TelemetryFrame objects to DuckDB row tuples."""
    return [
        (
            session_id, i, f.timestamp,
            getattr(f, "distance", 0.0),
            f.speed, f.g_lat, f.g_long, f.combo_g,
            f.brake_pressure, f.throttle, f.steering, f.rpm,
            getattr(f, "lat", 0.0), getattr(f, "lon", 0.0),
        )
        for i, f in enumerate(frames)
    ]


def rows_to_frames(rows):
    """Reconstruct frame-shaped objects (SimpleNamespace) from DuckDB rows."""
    out = []
    for r in rows:
        (sid, idx, ts, dist, spd, gl, gL, cg,
         brk, thr, st, rpm, lat, lon) = r
        out.append(SimpleNamespace(
            timestamp=ts, distance=dist, speed=spd,
            g_lat=gl, g_long=gL, combo_g=cg,
            brake_pressure=brk, throttle=thr, steering=st, rpm=rpm,
            lat=lat, lon=lon,
        ))
    return out


def load_session_frames(sid: str):
    """Read all frames for a session from the telemetry table, ordered."""
    if not state.has_duckdb:
        return []
    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM telemetry WHERE session_id = ? ORDER BY frame_idx",
                [sid],
            ).fetchall()
    except DuckDbUnavailable:
        return []
    return rows_to_frames(rows)
