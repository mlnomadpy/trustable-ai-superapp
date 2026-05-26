"""bridge.bp_signals — Blueprint: ADR-015 signal sink + capabilities."""

import json
from flask import Blueprint, request, jsonify
from pitwall.state import state
from pitwall.db import (
    db_conn, DuckDbUnavailable,
    WIDE_SIGNAL_NAMES, resolve_signal_id, compute_capabilities,
    read_signal, interp_hold, interp,
)

bp = Blueprint("signals", __name__)


@bp.route("/session/<sid>/capabilities", methods=["GET"])
def session_capabilities_get(sid: str):
    """ADR-015 Phase 3: per-session capability envelope.

    If the `session_capabilities` table has no row for this session
    yet but raw telemetry exists, compute on the fly. This makes the
    endpoint useful for live sessions (especially `_live`) without
    requiring the caller to POST /capabilities/recompute first.
    """
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503

    def _fetch():
        try:
            with db_conn() as conn:
                return conn.execute(
                    """SELECT sr.name, sc.n_samples, sc.mean_hz, sr.min_useful_hz,
                              sc.t_start, sc.t_end
                       FROM session_capabilities sc
                       JOIN signal_registry sr USING(signal_id)
                       WHERE sc.session_id = ?
                       ORDER BY sr.name""", [sid]).fetchall()
        except DuckDbUnavailable:
            return None

    rows = _fetch()
    if rows is None:
        return jsonify({"error": "duckdb not available"}), 503

    if not rows:
        # Session has no precomputed capabilities — try a lazy compute
        # from whatever raw telemetry is already in the tall + wide
        # stores. Returns the number of rows it wrote.
        try:
            n = compute_capabilities(sid)
        except Exception as e:
            return jsonify({"error": f"capabilities compute failed: {e}",
                            "session_id": sid}), 500
        if n == 0:
            return jsonify({"error": "session not found", "session_id": sid}), 404
        rows = _fetch() or []
    signals = []
    caps_by_name: dict = {}
    t_starts: list = []
    t_ends: list = []
    for name, n_samples, mean_hz, min_useful_hz, t_start, t_end in rows:
        useful = (min_useful_hz is None) or (float(mean_hz) >= float(min_useful_hz))
        signals.append({"name": name, "n_samples": int(n_samples),
                        "mean_hz": float(mean_hz), "useful": bool(useful)})
        caps_by_name[name] = {"mean_hz": float(mean_hz), "useful": bool(useful)}
        t_starts.append(float(t_start))
        t_ends.append(float(t_end))
    duration_s = (max(t_ends) - min(t_starts)) if t_starts else 0.0
    available: list = []
    disabled: list = []
    try:
        from pitwall.features.coaching.coach_engine import evaluate_coach_gating
        available, disabled = evaluate_coach_gating(caps_by_name)
    except ImportError:
        pass
    return jsonify({"session_id": sid, "duration_s": duration_s,
                    "signals": signals, "coaches_available": available,
                    "coaches_disabled": disabled})


@bp.route("/session/<sid>/signals", methods=["GET"])
def session_signals_get(sid: str):
    """ADR-015 Phase 3: query-time synchroniser."""
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    names_param = request.args.get("names", "") or ""
    names = [n.strip() for n in names_param.split(",") if n.strip()]
    if not names:
        return jsonify({"error": "names is required (comma-separated)"}), 400
    axis = (request.args.get("axis") or "gps").strip()
    interp_kind = (request.args.get("interp") or "hold").strip().lower()
    if interp_kind not in ("hold", "lerp"):
        return jsonify({"error": "interp must be 'hold' or 'lerp'"}), 400
    try:
        rate_hz = float(request.args.get("rate_hz") or 0)
    except ValueError:
        return jsonify({"error": "rate_hz must be a number"}), 400
    if rate_hz < 0:
        return jsonify({"error": "rate_hz must be >= 0"}), 400
    try:
        t_from = request.args.get("t_from")
        t_to = request.args.get("t_to")
        t_from = float(t_from) if t_from not in (None, "") else None
        t_to = float(t_to) if t_to not in (None, "") else None
    except ValueError:
        return jsonify({"error": "t_from/t_to must be numbers"}), 400
    if request.args.get("lap") is not None:
        return jsonify({"error": "lap clipping not yet implemented (Phase 4)"}), 400

    AXIS_KEYWORDS = {"gps", "time", "t", "lap_distance"}

    try:
        with db_conn() as conn:
            n_wide = conn.execute(
                "SELECT COUNT(*) FROM telemetry WHERE session_id = ?", [sid]).fetchone()[0]
            n_tall = conn.execute(
                "SELECT COUNT(*) FROM telemetry_signals WHERE session_id = ?", [sid]).fetchone()[0]
            if not n_wide and not n_tall:
                return jsonify({"error": "session not found", "session_id": sid}), 404
            for nm in names:
                if nm in WIDE_SIGNAL_NAMES:
                    continue
                r = conn.execute("SELECT 1 FROM signal_registry WHERE name = ?", [nm]).fetchone()
                if r is None:
                    return jsonify({"error": f"unknown signal: {nm}"}), 400
            if axis not in AXIS_KEYWORDS and axis not in WIDE_SIGNAL_NAMES:
                r = conn.execute("SELECT 1 FROM signal_registry WHERE name = ?", [axis]).fetchone()
                if r is None:
                    return jsonify({"error": f"unknown axis signal: {axis}"}), 400
            if t_from is None or t_to is None:
                bounds: list = []
                r = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM telemetry WHERE session_id = ?", [sid]).fetchone()
                if r and r[0] is not None:
                    bounds.append((float(r[0]), float(r[1])))
                r = conn.execute("SELECT MIN(t), MAX(t) FROM telemetry_signals WHERE session_id = ?", [sid]).fetchone()
                if r and r[0] is not None:
                    bounds.append((float(r[0]), float(r[1])))
                if bounds:
                    # If only one bound is missing, fill it from the data extent.
                    # If BOTH are missing and rate_hz>0 (resampling requested),
                    # clamp the window to the last 60 s to avoid serialising
                    # multi-million-row sessions through a single fetch. Callers
                    # that want the full session set t_from/t_to explicitly.
                    if t_from is None and t_to is None and rate_hz > 0:
                        t_to = max(b[1] for b in bounds)
                        t_from = t_to - 60.0
                    else:
                        if t_from is None:
                            t_from = min(b[0] for b in bounds)
                        if t_to is None:
                            t_to = max(b[1] for b in bounds)
            # Reject windows that would synth >10000 samples — protects the
            # bridge from OOM on a 1-hour session × 70 Hz × many signals
            # call. The PWA can narrow the window or drop rate_hz.
            MAX_RESAMPLE_POINTS = 10_000
            if rate_hz > 0 and t_from is not None and t_to is not None:
                est_points = max(0, int((t_to - t_from) * rate_hz))
                if est_points > MAX_RESAMPLE_POINTS:
                    return jsonify({
                        "error": "window too large",
                        "hint": (f"rate_hz × (t_to - t_from) = {est_points} "
                                 f"exceeds the {MAX_RESAMPLE_POINTS}-point cap; "
                                 f"narrow the time window or lower rate_hz."),
                        "max_points": MAX_RESAMPLE_POINTS,
                    }), 413
            signal_data = {nm: read_signal(conn, sid, nm, t_from, t_to) for nm in names}
            if rate_hz > 0:
                if t_from is None or t_to is None or t_to <= t_from:
                    return jsonify({"error": "rate_hz>0 requires a non-empty time window"}), 400
                step = 1.0 / rate_hz
                axis_ts: list = []
                t = t_from
                while t <= t_to + 1e-9:
                    axis_ts.append(t)
                    t += step
            elif axis in AXIS_KEYWORDS:
                sql = "SELECT DISTINCT timestamp FROM telemetry WHERE session_id = ?"
                params: list = [sid]
                if t_from is not None:
                    sql += " AND timestamp >= ?"
                    params.append(t_from)
                if t_to is not None:
                    sql += " AND timestamp <= ?"
                    params.append(t_to)
                sql += " ORDER BY timestamp"
                axis_ts = [float(r[0]) for r in conn.execute(sql, params).fetchall()]
            else:
                ax_data = read_signal(conn, sid, axis, t_from, t_to)
                axis_ts = [d[0] for d in ax_data]
            distance_at = None
            if axis == "lap_distance" and axis_ts:
                dist_data = read_signal(conn, sid, "distance_m", t_from, t_to)
                distance_at = interp_hold(axis_ts, dist_data)
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503

    values_by_name: dict = {}
    missing: list = []
    for nm in names:
        data = signal_data[nm]
        if not data:
            values_by_name[nm] = [None] * len(axis_ts)
            missing.append(nm)
        else:
            values_by_name[nm] = interp(axis_ts, data, interp_kind)
    rows_out = []
    for k, at in enumerate(axis_ts):
        row = {"t": at}
        if axis == "lap_distance" and distance_at is not None:
            row["distance_m"] = distance_at[k]
        for nm in names:
            row[nm] = values_by_name[nm][k]
        rows_out.append(row)
    return jsonify({"session_id": sid, "axis": axis, "rate_hz": rate_hz,
                    "interp": interp_kind, "t_from": t_from, "t_to": t_to,
                    "names": names, "rows": rows_out, "missing": missing,
                    "count": len(rows_out)})


@bp.route("/session/<sid>/signals", methods=["POST"])
def session_signals_post(sid: str):
    """ADR-015: append (name, t, value) tuples to telemetry_signals."""
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    body = request.get_json(force=True, silent=True) or {}
    items = body.get("signals") or []
    if not items:
        return jsonify({"error": "no signals"}), 400
    names_seen: set[str] = set()
    discovered: list[str] = []
    rows_written = 0
    try:
        with db_conn() as conn:
            name_to_id: dict[str, int] = {}
            for it in items:
                nm = it.get("name")
                if nm is None or nm in name_to_id:
                    continue
                existed = conn.execute("SELECT 1 FROM signal_registry WHERE name = ?", [nm]).fetchone()
                sid_id = resolve_signal_id(conn, nm)
                name_to_id[nm] = sid_id
                if not existed:
                    discovered.append(nm)
            rows = []
            for it in items:
                nm = it.get("name")
                sig_id = it.get("signal_id") if nm is None else name_to_id.get(nm)
                t = it.get("t")
                v = it.get("value")
                if sig_id is None or t is None or v is None:
                    continue
                try:
                    rows.append((sid, int(sig_id), float(t), float(v)))
                except (TypeError, ValueError):
                    continue
                if nm:
                    names_seen.add(nm)
            if not rows:
                return jsonify({"error": "no valid samples (need name|signal_id, t, value)"}), 400
            conn.executemany(
                """INSERT INTO telemetry_signals VALUES (?, ?, ?, ?)
                   ON CONFLICT (session_id, signal_id, t) DO UPDATE SET value = excluded.value""",
                rows)
            rows_written = len(rows)
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    n_caps = compute_capabilities(sid)
    return jsonify({"saved": True, "session_id": sid, "n_appended": rows_written,
                    "names": sorted(names_seen), "newly_discovered": discovered,
                    "capabilities_count": n_caps})


@bp.route("/session/<sid>/capabilities/recompute", methods=["POST"])
def session_capabilities_recompute(sid: str):
    """Trigger capability recomputation for a session."""
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    n = compute_capabilities(sid)
    return jsonify({"session_id": sid, "capabilities_count": n})


@bp.route("/signals/registry", methods=["GET"])
def signals_registry():
    """ADR-015: full signal catalog."""
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    try:
        with db_conn() as conn:
            rows = conn.execute(
                """SELECT signal_id, name, units, semantics, "group",
                          expected_hz, min_useful_hz, discovery, obd2_pid
                   FROM signal_registry ORDER BY "group", name""").fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    signals = [
        {"signal_id": r[0], "name": r[1], "units": r[2], "semantics": r[3],
         "group": r[4], "expected_hz": r[5], "min_useful_hz": r[6],
         "discovery": r[7], "obd2_pid": r[8]}
        for r in rows
    ]
    body = {"count": len(signals), "signals": signals}
    if (request.args.get("include_can_state") or "").lower() == "true":
        from pitwall.features.bp_diagnostics import can_state_snapshot
        body["can_state"] = can_state_snapshot()
    return jsonify(body)
