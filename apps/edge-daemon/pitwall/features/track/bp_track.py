"""bridge.bp_track — Blueprint: track/driver/corner/lap endpoints."""

import json, os
from datetime import datetime
from flask import Blueprint, request, jsonify
from pitwall.state import state, SIM_DIR
from pitwall.db import db_conn, DuckDbUnavailable, session_exists, session_has_telemetry, iso
from pitwall.features.session.laps import detect_laps, lap_sectors, quantile
from pitwall.features.session.driver_profile import compute_profile
from pitwall.features.track.track_json import load_track_json, corner_bounds_from_track


def _laps_or_400(sid: str):
    """Resolve laps for a session; returns (laps, error_response).

    Inlined from pitwall.helpers.laps_or_400 — Flask-coupled, used only here.
    """
    if not session_exists(sid):
        return None, (jsonify({"error": "session not found", "session_id": sid}), 404)
    if not session_has_telemetry(sid):
        return None, (jsonify({
            "error": "no telemetry recorded yet",
            "session_id": sid,
        }), 409)
    laps = detect_laps(sid)
    if not laps:
        return None, (jsonify({
            "error":      "no complete laps detected",
            "session_id": sid,
        }), 400)
    return laps, None

bp = Blueprint("track", __name__)


@bp.route("/track/<track_id>/elevation", methods=["GET"])
def track_elevation(track_id: str):
    """Elevation profile sampled along the centerline of a track JSON."""
    track = load_track_json(track_id)
    if track is None:
        return jsonify({"error": "track not found", "track_id": track_id}), 404
    profile = track.get("elevation_profile") or []
    if not profile:
        ref = track.get("reference_line") or []
        if not ref:
            return jsonify({"error": "no reference_line", "track_id": track_id}), 422
        return jsonify({"track_id": track_id, "name": track.get("name", track_id),
                        "track_length_m": track.get("track_length_m"),
                        "elevation_source": "missing", "samples": []})
    try:
        step_m = float(request.args.get("step_m") or 10.0)
    except ValueError:
        return jsonify({"error": "step_m must be a number"}), 400
    if step_m <= 0:
        return jsonify({"error": "step_m must be > 0"}), 400
    pts = sorted(profile, key=lambda p: float(p.get("distance", 0.0)))
    max_d = float(pts[-1].get("distance", 0.0))
    samples: list = []
    j = 0; d = 0.0
    while d <= max_d + 1e-9:
        while j + 1 < len(pts) and float(pts[j + 1]["distance"]) < d:
            j += 1
        if j + 1 >= len(pts):
            elev = float(pts[-1].get("altitude") or 0.0)
        else:
            d0 = float(pts[j].get("distance", 0.0))
            d1 = float(pts[j + 1].get("distance", 0.0))
            a0 = float(pts[j].get("altitude") or 0.0)
            a1 = float(pts[j + 1].get("altitude") or 0.0)
            elev = a0 if d1 == d0 else a0 + (a1 - a0) * (d - d0) / (d1 - d0)
        samples.append({"distance_m": round(d, 2), "elevation_m": round(elev, 2)})
        d += step_m
    elevs = [s["elevation_m"] for s in samples if s["elevation_m"] is not None]
    return jsonify({"track_id": track_id, "name": track.get("name", track_id),
                    "track_length_m": track.get("track_length_m"), "step_m": step_m,
                    "elevation_source": "json_profile",
                    "min_elevation_m": min(elevs) if elevs else None,
                    "max_elevation_m": max(elevs) if elevs else None,
                    "samples": samples})


@bp.route("/driver/<driver_id>/evolution", methods=["GET"])
def driver_evolution(driver_id: str):
    """Multi-session driver evolution time-series."""
    sonoma = state.sonoma
    if not state.has_duckdb:
        return jsonify({"error": "duckdb not available"}), 503
    track_filter = request.args.get("track")
    try:
        with db_conn() as conn:
            sql = "SELECT session_id, started_at, track FROM sessions WHERE driver = ?"
            params: list = [driver_id]
            if track_filter:
                sql += " AND (track = ? OR track IS NULL)"; params.append(track_filter)
            sql += " ORDER BY started_at ASC"
            sess_rows = conn.execute(sql, params).fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    if not sess_rows:
        return jsonify({"error": "no sessions", "driver_id": driver_id}), 404
    if len(sess_rows) < 5:
        return jsonify({"driver_id": driver_id, "track": track_filter,
                        "session_count": len(sess_rows), "evolution": [],
                        "summary": None, "note": "evolution requires >= 5 sessions"}), 204
    evolution = []
    for idx, (sess_id, started_at, sess_track) in enumerate(sess_rows, start=1):
        laps = detect_laps(sess_id)
        if not laps:
            continue
        times = sorted(l["lap_time_s"] for l in laps)
        sectors_per_lap = [lap_sectors(sess_id, l) for l in laps]
        sec_pbs: dict = {}
        for sec_idx, sec in enumerate(sonoma.SECTORS):
            ts = [s["time_s"] for sl in sectors_per_lap for s in sl if s["name"] == sec.name]
            if ts:
                sec_pbs[f"s{sec_idx + 1}"] = round(min(ts), 3)
        evolution.append({"session_id": sess_id,
                          "started_at": iso(started_at),
                          "session_index": idx, "best_lap_s": round(times[0], 3),
                          "median_lap_s": round(quantile(times, 0.5), 3),
                          "lap_count": len(laps), "sector_pbs": sec_pbs})
    if not evolution:
        return jsonify({"driver_id": driver_id, "track": track_filter,
                        "session_count": len(sess_rows), "evolution": [],
                        "summary": None, "note": "no laps detected"})
    first_best = evolution[0]["best_lap_s"]
    latest_best = evolution[-1]["best_lap_s"]
    return jsonify({"driver_id": driver_id, "track": track_filter,
                    "session_count": len(evolution), "evolution": evolution,
                    "summary": {"first_best_s": first_best, "latest_best_s": latest_best,
                                "improvement_s": round(first_best - latest_best, 3)}})


@bp.route("/session/<sid>/corners", methods=["GET"])
def session_corners(sid: str):
    """Per-corner aggregates: best pass + averages, optional gold-standard delta."""
    laps, err = _laps_or_400(sid)
    if err:
        return err
    track = load_track_json("sonoma") or {}
    corner_bounds = corner_bounds_from_track(track)
    if not corner_bounds:
        return jsonify({"error": "no corner geometry available"}), 422
    gold_by_corner = {}
    try:
        from pitwall.features.track.gold_standard import load_gold_standard
        gold_path = os.path.abspath(os.path.join(SIM_DIR, "..", "..", "..", "data", "reference", "sonoma_gold.json"))
        if os.path.exists(gold_path):
            gold = load_gold_standard(gold_path)
            for cp in (gold.corner_passes if hasattr(gold, "corner_passes") else []):
                gold_by_corner[cp.corner] = cp
    except Exception:
        pass
    out = []
    try:
        with db_conn() as conn:
            for c in corner_bounds:
                passes = []
                for lap in laps:
                    rows = conn.execute(
                        "SELECT timestamp, distance_m, speed_ms, brake_bar, g_lat "
                        "FROM telemetry WHERE session_id = ? "
                        "AND timestamp >= ? AND timestamp <= ? "
                        "AND distance_m >= ? AND distance_m <= ? ORDER BY timestamp",
                        [sid, lap["t_start"], lap["t_end"], c["entry_m"] - 50, c["exit_m"] + 10]).fetchall()
                    if not rows:
                        continue
                    in_corner = [r for r in rows if r[1] is not None and c["entry_m"] <= r[1] <= c["exit_m"]]
                    if not in_corner:
                        continue
                    speeds = [r[2] for r in in_corner if r[2] is not None]
                    if not speeds:
                        continue
                    entry_row = min(in_corner, key=lambda r: abs((r[1] or 0) - c["entry_m"]))
                    exit_row = min(in_corner, key=lambda r: abs((r[1] or 0) - c["exit_m"]))
                    apex_idx = min(range(len(in_corner)), key=lambda i: in_corner[i][2] or 1e9)
                    apex_row = in_corner[apex_idx]
                    peak_brake = max(((r[3] or 0) for r in rows), default=0.0)
                    max_glat = max((abs(r[4] or 0) for r in in_corner), default=0.0)
                    t_in = in_corner[0][0]; t_out = in_corner[-1][0]
                    passes.append({
                        "lap_number": lap["lap_number"],
                        "entry_speed_kmh": round(float(entry_row[2] or 0) * 3.6, 1),
                        "apex_speed_kmh": round(float(apex_row[2] or 0) * 3.6, 1),
                        "exit_speed_kmh": round(float(exit_row[2] or 0) * 3.6, 1),
                        "peak_brake_bar": round(float(peak_brake), 1),
                        "max_g_lat": round(float(max_glat), 2),
                        "corner_time_s": round(float(t_out - t_in), 3),
                        "apex_distance_m": round(float(apex_row[1] or 0), 1),
                    })
                if not passes:
                    out.append({
                        "name": c["name"], "n_passes": 0, "best_pass": None,
                        "averages": None, "grade": "ungraded",
                        "gold_delta_kmh":       None,
                        "gold_delta_entry_kmh": None,
                        "gold_delta_exit_kmh":  None,
                        "gold_delta_time_s":    None,
                    })
                    continue
                best_pass = max(passes, key=lambda p: p["apex_speed_kmh"])
                apexes = [p["apex_speed_kmh"] for p in passes]
                ctimes = [p["corner_time_s"] for p in passes]
                averages = {"apex_speed_kmh": round(sum(apexes)/len(apexes), 1),
                            "corner_time_s": round(sum(ctimes)/len(ctimes), 3)}
                grade = "ungraded"
                gold_delta_kmh = None
                gold_delta_entry_kmh = None
                gold_delta_exit_kmh = None
                gold_delta_time_s = None
                gold = gold_by_corner.get(c["name"])
                if gold is not None:
                    # Apex delta drives the corner grade — speed-vs-gold is the
                    # canonical metric. The other three deltas are populated
                    # whenever the gold record carries the field (sonoma_gold.json
                    # has all of entry / exit / corner_time for every corner) so
                    # CornerScorecard can render real arrows on every row.
                    gold_apex = float(getattr(gold, "apex_speed_kmh", 0))
                    if gold_apex > 0:
                        delta = best_pass["apex_speed_kmh"] - gold_apex
                        gold_delta_kmh = round(delta, 1)
                        if delta >= -1.0: grade = "A"
                        elif delta >= -3.0: grade = "B"
                        elif delta >= -5.0: grade = "C"
                        elif delta >= -8.0: grade = "D"
                        else: grade = "F"
                    gold_entry = float(getattr(gold, "entry_speed_kmh", 0))
                    if gold_entry > 0:
                        gold_delta_entry_kmh = round(best_pass["entry_speed_kmh"] - gold_entry, 1)
                    gold_exit = float(getattr(gold, "exit_speed_kmh", 0))
                    if gold_exit > 0:
                        gold_delta_exit_kmh = round(best_pass["exit_speed_kmh"] - gold_exit, 1)
                    gold_time = float(getattr(gold, "corner_time_s", 0))
                    if gold_time > 0:
                        # Time is signed the other way — positive means slower
                        # than gold (lost time in the corner). CornerScorecard
                        # flips the colour convention via `kind: 'time'`.
                        gold_delta_time_s = round(best_pass["corner_time_s"] - gold_time, 3)
                out.append({
                    "name": c["name"],
                    "n_passes": len(passes),
                    "best_pass": best_pass,
                    "averages": averages,
                    "grade": grade,
                    "gold_delta_kmh":       gold_delta_kmh,
                    "gold_delta_entry_kmh": gold_delta_entry_kmh,
                    "gold_delta_exit_kmh":  gold_delta_exit_kmh,
                    "gold_delta_time_s":    gold_delta_time_s,
                    "passes": passes,
                })
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    return jsonify({"session_id": sid, "track": track.get("name", "Sonoma Raceway"),
                    "lap_count": len(laps), "corners": out, "gold_available": bool(gold_by_corner)})


@bp.route("/track/markers", methods=["GET"])
def track_markers():
    """All Sonoma markers."""
    track_path = os.path.abspath(os.path.join(SIM_DIR, "..", "..", "..", "data", "tracks", "sonoma.json"))
    try:
        with open(track_path) as f:
            data = json.load(f)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"track": data.get("name", "Sonoma Raceway"), "markers": data.get("markers", [])})


@bp.route("/track/danger_zones", methods=["GET"])
def track_danger_zones():
    """Return Sonoma danger zones with severity and distance bounds."""
    sonoma = state.sonoma
    return jsonify({"track": "Sonoma Raceway", "danger_zones": [
        {"id": d.id, "start_m": d.start_m, "end_m": d.end_m,
         "description": d.description, "severity": d.severity}
        for d in sonoma.DANGER_ZONES]})


@bp.route("/track/weather", methods=["GET"])
def track_weather():
    """Return the weather phase and coaching note for the given hour."""
    sonoma = state.sonoma
    try:
        hour_local = int(request.args.get("hour_local", datetime.now().hour))
    except ValueError:
        hour_local = 12
    ph = sonoma.weather_phase_for_hour(hour_local)
    return jsonify({"hour_local": hour_local, "phase": ph.id,
                    "surface_state": ph.surface_state, "coaching_note": ph.coaching_note})


@bp.route("/markers", methods=["GET"])
def markers_filtered():
    """Filterable view over the Sonoma marker schema (ADR-011)."""
    track_path = os.path.abspath(os.path.join(SIM_DIR, "..", "..", "..", "data", "tracks", "sonoma.json"))
    try:
        with open(track_path) as fh:
            data = json.load(fh)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    markers = data.get("markers", [])
    corner = request.args.get("corner")
    kind = request.args.get("kind")
    if corner:
        markers = [m for m in markers if m.get("corner") == corner]
    if kind:
        markers = [m for m in markers if m.get("kind") == kind]
    return jsonify({"track": data.get("name", "Sonoma Raceway"),
                    "filters": {"corner": corner, "kind": kind},
                    "markers": markers, "count": len(markers)})


@bp.route("/laps", methods=["GET"])
def get_laps():
    """Query lap records from DuckDB."""
    session_id = request.args.get("session_id")
    limit = int(request.args.get("limit", 20))
    try:
        with db_conn() as conn:
            query = "SELECT * FROM laps"
            params = []
            if session_id:
                query += " WHERE session_id = ?"; params.append(session_id)
            query += f" ORDER BY recorded_at DESC LIMIT {limit}"
            rows = conn.execute(query, params).fetchall()
            cols = [d[0] for d in conn.description]
    except DuckDbUnavailable:
        return jsonify({"laps": [], "error": "duckdb not available"})
    return jsonify({"laps": [dict(zip(cols, r)) for r in rows], "count": len(rows)})


@bp.route("/lap", methods=["POST"])
def save_lap():
    """Insert a completed lap record into DuckDB."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        with db_conn() as conn:
            conn.execute("""INSERT INTO laps (session_id, lap_number, lap_time_s, best_sector,
                            avg_speed_kmh, max_combo_g, coast_pct) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         [data.get("session_id", ""), data.get("lap_number", 0),
                          data.get("lap_time_s", 0), data.get("best_sector", 0),
                          data.get("avg_speed_kmh", 0), data.get("max_combo_g", 0),
                          data.get("coast_pct", 0)])
    except DuckDbUnavailable:
        return jsonify({"saved": False, "error": "duckdb not available"})
    return jsonify({"saved": True})


@bp.route("/driver/<driver_id>/profile", methods=["GET"])
def driver_profile_route(driver_id: str):
    """Return the computed driver profile for the given driver."""
    if not state.has_analyzer or not state.has_duckdb:
        return jsonify({"error": "driver profile unavailable"}), 503
    try:
        with db_conn() as conn:
            profile = compute_profile(conn, driver_id)
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    return jsonify(profile)
