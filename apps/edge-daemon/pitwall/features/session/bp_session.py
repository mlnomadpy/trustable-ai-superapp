"""bridge.bp_session — Blueprint: session CRUD, import/export, frames.

Owns the session lifecycle (start/end/list/detail), per-frame telemetry
and video-frame ingestion, session sync, session import (VBO), and
parquet export.
"""

import json
import os
import time
from datetime import datetime

from flask import Blueprint, request, jsonify, Response

from pitwall.state import state, SIM_DIR
from pitwall.db import db_conn, DuckDbUnavailable, compute_capabilities, ensure_session_row, iso
from pitwall.features.session.laps import new_session_id, detect_analysis_laps
from pitwall.features.session.frames import (
    frames_to_rows, rows_to_frames, load_session_frames,
)
from pitwall.features.realtime.bp_realtime import telemetry_bus

bp = Blueprint("session", __name__)


# ── Per-frame telemetry ingestion ──────────────────────────────────────────────

@bp.route("/session/<sid>/frames", methods=["POST"])
def session_frames(sid: str):
    """Append a batch of telemetry frames for a session.

    Body shape:
        {"frames": [{"timestamp": ..., "distance": ..., "speed": ...,
                     "g_lat": ..., "g_long": ..., "combo_g": ...,
                     "brake_pressure": ..., "throttle": ..., "steering": ...,
                     "rpm": ..., "lat": ..., "lon": ...}, ...]}
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    data = request.get_json(force=True, silent=True) or {}
    raw_frames = data.get("frames") or []
    if not raw_frames:
        return jsonify({"saved": False, "error": "no frames"}), 400

    ensure_session_row(
        sid,
        driver=data.get("driver"),
        driver_level=data.get("driver_level"),
        track=data.get("track"),
        car=data.get("car"),
        note=data.get("note"),
    )

    try:
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT COALESCE(MAX(frame_idx), -1) FROM telemetry WHERE session_id = ?",
                [sid],
            ).fetchone()[0]
            next_idx = (existing if existing is not None else -1) + 1

            rows = []
            for j, f in enumerate(raw_frames):
                rows.append((
                    sid, next_idx + j,
                    float(f.get("timestamp", 0)),
                    float(f.get("distance", 0)),
                    float(f.get("speed", 0)),
                    float(f.get("g_lat", 0)),
                    float(f.get("g_long", 0)),
                    float(f.get("combo_g", 0)),
                    float(f.get("brake_pressure", 0)),
                    float(f.get("throttle", 0)),
                    float(f.get("steering", 0)),
                    float(f.get("rpm", 0)),
                    float(f.get("lat", 0)),
                    float(f.get("lon", 0)),
                ))
            conn.executemany(
                "INSERT INTO telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
    except DuckDbUnavailable:
        return jsonify({"saved": False, "error": "duckdb not available"}), 503

    for f in raw_frames:
        telemetry_bus.publish(sid, f)
        
    return jsonify({"saved": True, "session_id": sid, "n_appended": len(raw_frames)})


# ── Video frame metadata ingestion ────────────────────────────────────────────

@bp.route("/session/<sid>/video_frames", methods=["POST"])
def session_video_frames(sid: str):
    """Append video-frame metadata for a session. Body:
        {"frames": [{"timestamp": ..., "avitime_ms": ...,
                     "file_path": "...", "file_offset_s": ...,
                     "width": ..., "height": ...}, ...]}

    Video bytes stay on disk; this endpoint only records the index. Callers
    use this in tandem with /session/<id>/frames to enable
    timestamp-aligned replay + ffmpeg-seek into the chunked MP4.
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    data = request.get_json(force=True, silent=True) or {}
    raws = data.get("frames") or []
    if not raws:
        return jsonify({"saved": False, "error": "no frames"}), 400
    rows = [
        (
            sid,
            float(f.get("timestamp", 0)),
            int(f.get("avitime_ms", 0)),
            str(f.get("file_path", "")),
            float(f.get("file_offset_s", 0)),
            int(f.get("width", 0)),
            int(f.get("height", 0)),
        )
        for f in raws
    ]
    try:
        with db_conn() as conn:
            conn.executemany(
                "INSERT INTO video_frames VALUES (?,?,?,?,?,?,?)",
                rows,
            )
    except DuckDbUnavailable:
        return jsonify({"saved": False, "error": "duckdb not available"}), 503
    return jsonify({"saved": True, "session_id": sid, "n_appended": len(raws)})


# ── Session sync (time-aligned telemetry + video) ─────────────────────────────

@bp.route("/session/<sid>/sync", methods=["GET"])
def session_sync(sid: str):
    """Return time-aligned (telemetry + video) rows for a session window.

    Query params:
        from   (epoch seconds, optional)
        to     (epoch seconds, optional)
        window_s (default 0.05) — match telemetry to video within ± this
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    t_from = float(request.args.get("from", 0))
    t_to = float(request.args.get("to", 0))
    win = float(request.args.get("window_s", 0.05))
    where_t = ""
    params = [sid, win]
    if t_to > 0:
        where_t = "AND t.timestamp BETWEEN ? AND ?"
        params.extend([t_from, t_to])
    sql = (
        "SELECT t.frame_idx, t.timestamp, t.distance_m, t.speed_ms, "
        "       t.brake_bar, t.throttle_pct, t.g_lat, t.g_long, "
        "       v.file_path, v.file_offset_s "
        "FROM telemetry t "
        "LEFT JOIN video_frames v "
        "  ON v.session_id = t.session_id "
        "  AND v.timestamp BETWEEN t.timestamp - ? AND t.timestamp + ? "
        f"WHERE t.session_id = ? {where_t} "
        "ORDER BY t.frame_idx"
    )
    params = [win, win, sid] + ([t_from, t_to] if t_to > 0 else [])
    try:
        with db_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            cols = [d[0] for d in conn.description]
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    return jsonify({
        "session_id": sid,
        "rows": [dict(zip(cols, r)) for r in rows],
        "count": len(rows),
    })


# ── Parquet export ─────────────────────────────────────────────────────────────

@bp.route("/session/<sid>/export.parquet", methods=["GET"])
def session_export_parquet(sid: str):
    """Stream a session's data as Parquet for DuckDB-Wasm hydration.

    Query params:
        table   'telemetry' (wide canonicals) | 'telemetry_signals'
                (ADR-015 tall sink) | 'signal_registry' (catalog —
                session-independent, sid is ignored) | 'capabilities'
                (per-signal Hz + useful flag). Default: 'telemetry'.

    Powers the PWA's analytics flow: PWA fetches the parquet once per
    session, registers it with DuckDB-Wasm, then runs all subsequent
    SQL client-side. No per-query bridge round-trip needed.

    Status codes:
      200  parquet bytes streamed back; Content-Type: application/octet-stream
      400  bad table name
      404  session not found in the requested table (skipped for signal_registry)
      503  no DB backend, or backend lacks Parquet support (SQLite on Termux)
    """
    from pitwall.db import db_backend
    if not state.has_duckdb:
        return jsonify({"error": "no DB backend available"}), 503

    table = (request.args.get("table") or "telemetry").lower()
    if table not in ("telemetry", "telemetry_signals", "signal_registry", "capabilities"):
        return jsonify({"error": f"unknown table: {table}"}), 400

    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    tmp_path = tmp.name
    tmp.close()

    backend = db_backend()

    try:
        try:
            with db_conn() as conn:
                if table == "capabilities":
                    select_sql = (
                        "SELECT sc.session_id, sr.name AS signal_name, "
                        "       sc.n_samples, sc.mean_hz, sc.t_start, sc.t_end, "
                        '       sr.units, sr."group", sr.min_useful_hz '
                        "FROM session_capabilities sc "
                        "JOIN signal_registry sr USING(signal_id) "
                        "WHERE sc.session_id = ?"
                    )
                    params = [sid]
                    skip_session_check = False
                elif table == "signal_registry":
                    # Inject a constant session_id column so the PWA's
                    # `WHERE session_id = ?` filter binds in DuckDB-wasm.
                    # The registry itself is session-independent; we just
                    # stamp it with the requested sid for client-side joins.
                    select_sql = "SELECT ? AS session_id, sr.* FROM signal_registry sr"
                    params = [sid]
                    skip_session_check = True
                elif table == "telemetry_signals":
                    # Re-project session_id into the result so the parquet
                    # carries the column the PWA filters on.
                    select_sql = (
                        "SELECT ? AS session_id, signal_id, t, value "
                        "FROM telemetry_signals WHERE session_id = ?"
                    )
                    params = [sid, sid]
                    skip_session_check = False
                else:  # telemetry
                    select_sql = f"SELECT * FROM {table} WHERE session_id = ?"
                    params = [sid]
                    skip_session_check = False

                n = conn.execute(
                    f"SELECT COUNT(*) FROM ({select_sql})",
                    params,
                ).fetchone()[0]
                if not skip_session_check and not n:
                    return jsonify({
                        "error": "session not found in this table",
                        "session_id": sid, "table": table,
                    }), 404

                if backend == "duckdb":
                    conn.execute(
                        f"COPY ({select_sql}) TO '{tmp_path}' (FORMAT PARQUET)",
                        params,
                    )
                else:
                    # SQLite path: stream rows through pyarrow in batches so
                    # the 3M-row tall store doesn't materialise as a single
                    # Python list. pyarrow is a hard dep on aarch64 Termux
                    # since the duckdb wheel was removed (task #9).
                    import pyarrow as pa
                    import pyarrow.parquet as pq
                    cur = conn.execute(select_sql, params)
                    col_names = [d[0] for d in cur.description]
                    writer = None
                    BATCH = 50_000
                    try:
                        while True:
                            rows = cur.fetchmany(BATCH)
                            if not rows:
                                break
                            cols = list(zip(*rows)) if rows else [[] for _ in col_names]
                            batch = pa.RecordBatch.from_arrays(
                                [pa.array(c) for c in cols],
                                names=col_names,
                            )
                            if writer is None:
                                writer = pq.ParquetWriter(
                                    tmp_path, batch.schema, compression="snappy",
                                )
                            writer.write_batch(batch)
                    finally:
                        if writer is not None:
                            writer.close()
                    if writer is None:
                        # Empty result but session existed (or registry was empty)
                        # — write an empty file with an inferred schema so the
                        # PWA's DuckDB-wasm register call doesn't choke.
                        schema = pa.schema([(c, pa.null()) for c in col_names])
                        pq.write_table(pa.table({c: [] for c in col_names}, schema=schema), tmp_path)
        except DuckDbUnavailable:
            return jsonify({"error": "no DB backend available"}), 503

        with open(tmp_path, "rb") as f:
            data = f.read()
        return Response(
            data,
            mimetype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{sid}-{table}.parquet"',
                "Cache-Control": "no-cache",
                "X-Pitwall-Session": sid,
                "X-Pitwall-Table": table,
                "X-Pitwall-Rows": str(n),
            },
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# ── Analysis-hub lap envelope ─────────────────────────────────────────────────

@bp.route("/session/<sid>/laps", methods=["GET"])
def session_laps(sid: str):
    """Return the Analysis-Hub lap envelope.

    Shape: `{laps: [{name, t_start, t_end, duration_s, distance_m,
    method}], track_length_m: number | null}` — mirrors the JS
    `detectLaps()` in docs/telemetry-viewer.html so the PWA's Analysis
    Hall can drive a lap-filter dropdown off the bridge instead of
    re-implementing the algorithm client-side.

    Three strategies, tried in order: GPS return-to-start, distance-
    based slicing (track_len × 2 threshold), speed-stint fallback. The
    first entry is always `{name: "Full session", method: "all", ...}`.

    Status codes:
      200  envelope returned
      404  no telemetry rows for this session_id
      503  no DB backend
    """
    if not state.has_duckdb:
        return jsonify({"error": "no DB backend available"}), 503
    envelope = detect_analysis_laps(sid)
    if not envelope.get("laps"):
        return jsonify({
            "error": "session not found",
            "session_id": sid,
        }), 404
    return jsonify(envelope)


# ── Session import (VBO) ──────────────────────────────────────────────────────

@bp.route("/session/import", methods=["POST"])
def session_import():
    """Import an entire VBO file into a new session in DuckDB.

    Body: {"vbo_path": "/abs/path/to/file.vbo",
           "driver": "...",
           "driver_level": "intermediate",
           "session_id": (optional, auto-generated if omitted)}

    Parses the VBO, creates a `sessions` row, persists every frame to the
    `telemetry` table. Returns {session_id, n_frames, duration_s, distance_m}.
    Idempotent on session_id: if the session already has frames, returns 409.
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    data = request.get_json(force=True, silent=True) or {}
    vbo = data.get("vbo_path")
    if not vbo or not os.path.exists(vbo):
        return jsonify({"error": f"vbo_path missing or not found: {vbo!r}"}), 400

    sid = data.get("session_id") or new_session_id(state.track.name if state.track else None)
    driver = data.get("driver", "")
    level = data.get("driver_level", "intermediate")
    note = data.get("note", f"Imported from {os.path.basename(vbo)}")

    try:
        from pitwall.features.session.vbo_parser import parse_vbo
        meta, frames = parse_vbo(vbo)
        if not frames:
            return jsonify({"error": f"no frames parsed from {vbo}"}), 400
    except Exception as e:
        return jsonify({"error": f"parse_vbo failed: {e}"}), 500

    try:
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT count(*) FROM telemetry WHERE session_id = ?",
                [sid],
            ).fetchone()[0]
            if existing > 0:
                return jsonify({
                    "error": f"session {sid} already has {existing} frames",
                    "session_id": sid,
                }), 409

            conn.execute(
                "INSERT INTO sessions (session_id, driver, driver_level, track, car, note) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [sid, driver, level,
                 state.track.name if state.track else "Sonoma Raceway",
                 meta.device_type or "", note],
            )
            rows = frames_to_rows(sid, frames)
            conn.executemany(
                "INSERT INTO telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503

    duration_s = frames[-1].timestamp - frames[0].timestamp
    distance_m = frames[-1].distance - frames[0].distance

    n_caps = compute_capabilities(sid)

    return jsonify({
        "session_id":         sid,
        "n_frames":           len(frames),
        "duration_s":         round(duration_s, 2),
        "distance_m":         round(distance_m, 1),
        "vbo_source":         os.path.basename(vbo),
        "capabilities_count": n_caps,
    })


# ── Session lifecycle (start / end / list / detail) ────────────────────────────

@bp.route("/session/start", methods=["POST"])
def session_start():
    """Open a new session row in DuckDB.

    Body fields are optional. If `session_id` is omitted, the bridge generates
    `<track-slug>-<UTC-YYYYMMDD-HHMMSS>`. Idempotent: re-starting an existing
    session_id is a no-op (200 with `started: true` either way).
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    data = request.get_json(force=True, silent=True) or {}
    track_name = data.get("track") or (state.track.name if state.track else None)
    sid = data.get("session_id") or new_session_id(track_name)
    driver_id = data.get("driver", "")
    ensure_session_row(
        sid,
        driver=driver_id,
        driver_level=data.get("driver_level"),
        track=track_name,
        car=data.get("car"),
        note=data.get("note"),
    )
    if driver_id:
        from pitwall.features.coaching.adk_agents import reset_driver_session
        reset_driver_session(driver_id)
    return jsonify({"started": True, "session_id": sid})


@bp.route("/session/<sid>/end", methods=["POST"])
def session_end(sid: str):
    """Stamp `ended_at = now()` on a session. Idempotent."""
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    try:
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", [sid],
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO sessions (session_id, ended_at) VALUES (?, now())",
                    [sid],
                )
            else:
                conn.execute(
                    "UPDATE sessions SET ended_at = now() "
                    "WHERE session_id = ? AND ended_at IS NULL",
                    [sid],
                )
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    return jsonify({"ended": True, "session_id": sid})


@bp.route("/sessions", methods=["GET"])
def sessions_list():
    """List sessions, newest first. `?active_only=true` hides ended ones."""
    if not state.has_duckdb:
        return jsonify({"sessions": [], "error": "duckdb not available"})
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    active_only = (request.args.get("active_only", "false").lower() == "true")

    sessions_out: list = []
    try:
        with db_conn() as conn:
            sql = ("SELECT session_id, driver, driver_level, track, car, "
                   "started_at, ended_at, note FROM sessions")
            params: list = []
            if active_only:
                sql += " WHERE ended_at IS NULL"
            sql += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            sess_rows = conn.execute(sql, params).fetchall()

            for r in sess_rows:
                sid = r[0]
                lap_row = conn.execute(
                    "SELECT COUNT(*), MIN(lap_time_s) FROM laps WHERE session_id = ?",
                    [sid],
                ).fetchone()
                lap_count = int(lap_row[0]) if lap_row else 0
                best_lap_s = float(lap_row[1]) if lap_row and lap_row[1] is not None else None
                sessions_out.append({
                    "session_id":   r[0],
                    "driver":       r[1],
                    "driver_level": r[2],
                    "track":        r[3],
                    "car":          r[4],
                    "started_at":   iso(r[5]),
                    "ended_at":     iso(r[6]),
                    "note":         r[7],
                    "lap_count":    lap_count,
                    "best_lap_s":   best_lap_s,
                })
    except DuckDbUnavailable:
        return jsonify({"sessions": []})
    return jsonify({"sessions": sessions_out, "count": len(sessions_out)})


@bp.route("/session/<sid>", methods=["GET"])
def session_detail(sid: str):
    """Full session detail: row + laps + recent coaching_notes."""
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    try:
        with db_conn() as conn:
            sess_row = conn.execute(
                "SELECT session_id, driver, driver_level, track, car, "
                "started_at, ended_at, note FROM sessions WHERE session_id = ?",
                [sid],
            ).fetchone()
            if sess_row is None:
                return jsonify({"error": "session not found", "session_id": sid}), 404

            lap_rows = conn.execute(
                "SELECT lap_number, lap_time_s, best_sector, avg_speed_kmh, "
                "max_combo_g, coast_pct, recorded_at FROM laps "
                "WHERE session_id = ? ORDER BY lap_number ASC",
                [sid],
            ).fetchall()

            note_rows = conn.execute(
                "SELECT burst_id, distance_m, text, source, recorded_at "
                "FROM coaching_notes WHERE session_id = ? "
                "ORDER BY recorded_at DESC LIMIT 50",
                [sid],
            ).fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503

    laps = [
        {"lap_number":    int(r[0]) if r[0] is not None else None,
         "lap_time_s":    float(r[1]) if r[1] is not None else None,
         "best_sector":   float(r[2]) if r[2] is not None else None,
         "avg_speed_kmh": float(r[3]) if r[3] is not None else None,
         "max_combo_g":   float(r[4]) if r[4] is not None else None,
         "coast_pct":     float(r[5]) if r[5] is not None else None,
         "recorded_at":   iso(r[6])}
        for r in lap_rows
    ]
    notes = [
        {"burst_id":    r[0], "distance_m": r[1], "text": r[2],
         "source":      r[3], "recorded_at": iso(r[4])}
        for r in note_rows
    ]
    best_lap_s = min((l["lap_time_s"] for l in laps if l["lap_time_s"] is not None),
                     default=None)
    session_dict = {
        "session_id":   sess_row[0],
        "driver":       sess_row[1],
        "driver_level": sess_row[2],
        "track":        sess_row[3],
        "car":          sess_row[4],
        "started_at":   iso(sess_row[5]),
        "ended_at":     iso(sess_row[6]),
        "note":         sess_row[7],
    }
    return jsonify({
        "session":    session_dict,
        "laps":       laps,
        "notes":      notes,
        "lap_count":  len(laps),
        "best_lap_s": best_lap_s,
    })


# ── Single-frame ingestion ─────────────────────────────────────────────────────

@bp.route("/session/<sid>/frame", methods=["POST"])
def session_frame(sid: str):
    """Append a single telemetry frame. Foundation for per-corner replay.

    Body shape: same fields as one element of `/frames` (timestamp, distance,
    speed, g_lat, g_long, combo_g, brake_pressure, throttle, steering, rpm,
    lat, lon). Returns the assigned `frame_idx` so the caller can build a
    per-corner replay reference.
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    f = request.get_json(force=True, silent=True) or {}
    if not isinstance(f, dict) or not f:
        return jsonify({"error": "no frame body"}), 400

    ensure_session_row(
        sid,
        driver=f.get("driver"),
        track=f.get("track"),
    )

    try:
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT COALESCE(MAX(frame_idx), -1) FROM telemetry WHERE session_id = ?",
                [sid],
            ).fetchone()[0]
            next_idx = (existing if existing is not None else -1) + 1
            try:
                conn.execute(
                    "INSERT INTO telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sid, next_idx,
                     float(f.get("timestamp", 0)),
                     float(f.get("distance", 0)),
                     float(f.get("speed", 0)),
                     float(f.get("g_lat", 0)),
                     float(f.get("g_long", 0)),
                     float(f.get("combo_g", 0)),
                     float(f.get("brake_pressure", 0)),
                     float(f.get("throttle", 0)),
                     float(f.get("steering", 0)),
                     float(f.get("rpm", 0)),
                     float(f.get("lat", 0)),
                     float(f.get("lon", 0))),
                )
            except (TypeError, ValueError) as e:
                return jsonify({"error": f"invalid frame: {e}"}), 400
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503

    telemetry_bus.publish(sid, f)
    return jsonify({"saved": True, "session_id": sid, "frame_idx": next_idx})


# ── Session reset ──────────────────────────────────────────────────────────────

@bp.route("/session/reset", methods=["POST"])
def session_reset():
    """Clear the burst accumulator — call this when a new session starts."""
    with state.burst_lock:
        count = len(state.session_bursts)
        state.session_bursts.clear()
    return jsonify({"cleared_bursts": count, "status": "ok"})
