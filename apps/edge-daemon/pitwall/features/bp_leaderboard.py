"""pitwall.features.bp_leaderboard — Blueprint: /leaderboard.

Aggregates best lap_time_s per (driver, track, car) across all completed
sessions. No synthetic data: rows come straight from the `laps` + `sessions`
tables. If no real laps have been recorded yet the response is an empty
`entries` list (HTTP 200) — the PWA already handles that case.

503 only when no DB backend is loaded.
"""

from flask import Blueprint, request, jsonify
from pitwall.state import state
from pitwall.db import db_conn, DuckDbUnavailable

bp = Blueprint("leaderboard", __name__)


def _format_time(secs: float) -> str:
    """Format lap seconds as `m:ss.mmm`."""
    if secs is None or secs <= 0:
        return ""
    m = int(secs // 60)
    s = secs - m * 60
    return f"{m}:{s:06.3f}"


def _initials(driver: str) -> str:
    parts = [p for p in (driver or "").strip().split() if p]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:3].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    """Best-lap leaderboard across all real sessions in the DB."""
    if not state.has_duckdb:
        return jsonify({"error": "no DB backend available"}), 503
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
    except ValueError:
        limit = 50
    track_filter = (request.args.get("track") or "").strip()
    extra, params = "", []
    if track_filter:
        extra = " AND s.track = ?"; params.append(track_filter)
    sql = f"""
        SELECT COALESCE(s.driver,'') AS driver,
               COALESCE(s.car,'')    AS car,
               COALESCE(s.track,'')  AS track,
               MIN(l.lap_time_s)     AS best_s
          FROM laps l
          JOIN sessions s ON s.session_id = l.session_id
         WHERE l.lap_time_s IS NOT NULL AND l.lap_time_s > 0{extra}
         GROUP BY s.driver, s.car, s.track
         ORDER BY best_s ASC
         LIMIT ?
    """
    try:
        with db_conn() as conn:
            rows = conn.execute(sql, [*params, limit]).fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "no DB backend available"}), 503
    entries = [
        {"rank": i + 1, "initials": _initials(r[0]), "car": r[1] or "",
         "track": r[2] or "", "time": _format_time(float(r[3]))}
        for i, r in enumerate(rows)
    ]
    return jsonify({"entries": entries, "count": len(entries)})
