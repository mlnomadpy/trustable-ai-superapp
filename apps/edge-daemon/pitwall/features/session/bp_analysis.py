"""bridge.bp_analysis — Blueprint: Phase-6 lap analysis + analytics proxies.

11 lap performance endpoints + scorecard/highlights/stats/friction/hustle/eob
proxy endpoints that read from the session analysis bundle cache.
"""

import json
import os

from flask import Blueprint, request, jsonify

from pitwall.state import state, SIM_DIR
from pitwall.db import db_conn, DuckDbUnavailable, session_exists, session_has_telemetry
from pitwall.features.session.laps import detect_laps, lap_sectors, quantile
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

bp = Blueprint("analysis", __name__)


# ── Bundle proxies ─────────────────────────────────────────────────────────────

def _section(sid: str, key: str):
    bundle = state.session_bundles.get(sid)
    if bundle is None:
        return (jsonify({"error": "session not analysed; POST /coach/debrief first",
                         "session_id": sid}), 404)
    return (jsonify({"session_id": sid, key: bundle.get(key)}), 200)


@bp.route("/session/<sid>/scorecard", methods=["GET"])
def session_scorecard(sid: str):
    """Return the scorecard section of a session's analysis bundle."""
    return _section(sid, "scorecard")


@bp.route("/session/<sid>/highlights", methods=["GET"])
def session_highlights(sid: str):
    """Return the highlights section of a session's analysis bundle."""
    return _section(sid, "highlights")


@bp.route("/session/<sid>/stats", methods=["GET"])
def session_stats(sid: str):
    """Return the stats section of a session's analysis bundle."""
    return _section(sid, "stats")


@bp.route("/session/<sid>/friction_circle", methods=["GET"])
def session_friction(sid: str):
    """Return the friction-circle section of a session's analysis bundle."""
    return _section(sid, "friction")


@bp.route("/session/<sid>/hustle_map", methods=["GET"])
def session_hustle(sid: str):
    """Return the hustle-map section of a session's analysis bundle."""
    return _section(sid, "hustle_map")


@bp.route("/session/<sid>/eob", methods=["GET"])
def session_eob(sid: str):
    """Return the end-of-braking section of a session's analysis bundle."""
    return _section(sid, "eob")


@bp.route("/session/<sid>/incidents", methods=["GET"])
def session_incidents(sid: str):
    """Return the incidents section of a session's analysis bundle."""
    return _section(sid, "incidents")


@bp.route("/session/<sid>/map", methods=["GET"])
def session_map(sid: str):
    """Map overlay bundle: lap polylines + per-corner color + marker pins."""
    sonoma = state.sonoma
    bundle = state.session_bundles.get(sid)
    if bundle is None:
        return jsonify({"error": "session not analysed first",
                        "session_id": sid}), 404
    if state.track is None:
        return jsonify({"error": "track not loaded"}), 503

    sc = bundle.get("scorecard") or {}
    grade_color = {"A+": "#1b5e20", "A": "#43a047", "B": "#7cb342",
                   "C": "#fdd835", "D": "#fb8c00", "F": "#e53935"}
    per_corner_color = {
        c["corner"]: grade_color.get(c.get("grade"), "#9e9e9e")
        for c in sc.get("corners", [])
    }

    pins = []
    try:
        track_path = os.path.join(SIM_DIR, "..", "..", "..", "data", "tracks", "sonoma.json")
        track_path = os.path.abspath(track_path)
        with open(track_path) as f:
            data = json.load(f)
        for m in data.get("markers", []):
            pins.append({
                "id": m.get("id"), "label": m.get("label"),
                "kind": m.get("kind"), "corner": m.get("corner"),
                "lat": m.get("lat"), "lon": m.get("lon"),
                "distance_m": m.get("distance"),
            })
    except Exception:
        pass

    danger = []
    for d in getattr(sonoma, "DANGER_ZONES", ()):
        danger.append({
            "id": d.id, "start_m": d.start_m, "end_m": d.end_m,
            "description": d.description, "severity": d.severity,
        })

    return jsonify({
        "session_id":       sid,
        "track":            state.track.name,
        "per_corner_color": per_corner_color,
        "marker_pins":      pins,
        "danger_zones":     danger,
        "lap_polylines":    {},
    })


@bp.route("/session/<sid>/clips", methods=["GET"])
def session_clips(sid: str):
    """ffmpeg-ready cut points — derived from highlights' video_in/out fields."""
    bundle = state.session_bundles.get(sid)
    if bundle is None:
        return jsonify({"error": "session not analysed first"}), 404
    clips = [
        {
            "id":       f"h{i}",
            "title":    h.get("title", ""),
            "in_s":     h.get("video_in_s", 0),
            "out_s":    h.get("video_out_s", 0),
            "category": h.get("category", ""),
            "severity": h.get("severity", ""),
            "lap":      h.get("lap", 0),
        }
        for i, h in enumerate(bundle.get("highlights") or [])
    ]
    return jsonify({"session_id": sid, "clips": clips, "count": len(clips)})


# ── Phase-6: lap performance + corner/straight aggregates ────────────────────

@bp.route("/session/<sid>/lap_time_table", methods=["GET"])
def session_lap_time_table(sid: str):
    """Per-lap times + sector splits, with best-lap and best-sector flags."""
    sonoma = state.sonoma
    laps, err = _laps_or_400(sid)
    if err:
        return err

    sectors_per_lap = [lap_sectors(sid, l) for l in laps]
    sector_names = [s.name for s in sonoma.SECTORS]

    best_t = min(l["lap_time_s"] for l in laps)
    best_lap_no = next(l["lap_number"] for l in laps if l["lap_time_s"] == best_t)

    best_sector_t: dict = {}
    for nm in sector_names:
        ts = [s["time_s"] for sl in sectors_per_lap for s in sl if s["name"] == nm]
        if ts:
            best_sector_t[nm] = min(ts)

    laps_out = []
    for lap, secs in zip(laps, sectors_per_lap):
        sec_out = []
        for s in secs:
            best = best_sector_t.get(s["name"])
            sec_out.append({
                "name":    s["name"],
                "time_s":  round(s["time_s"], 3),
                "is_best": best is not None and abs(s["time_s"] - best) < 1e-6,
            })
        laps_out.append({
            "lap_number":      lap["lap_number"],
            "lap_time_s":      round(lap["lap_time_s"], 3),
            "delta_to_best_s": round(lap["lap_time_s"] - best_t, 3),
            "is_best":         lap["lap_number"] == best_lap_no,
            "sectors":         sec_out,
        })
    return jsonify({
        "session_id":      sid,
        "lap_count":       len(laps),
        "best_lap_s":      round(best_t, 3),
        "best_lap_number": best_lap_no,
        "laps":            laps_out,
    })


@bp.route("/session/<sid>/lap_time_distribution", methods=["GET"])
def session_lap_time_distribution(sid: str):
    """Tukey box-plot statistics over the session's lap times."""
    laps, err = _laps_or_400(sid)
    if err:
        return err
    times = sorted(l["lap_time_s"] for l in laps)
    n = len(times)
    q1 = quantile(times, 0.25)
    q2 = quantile(times, 0.50)
    q3 = quantile(times, 0.75)
    iqr = q3 - q1
    lo_fence = q1 - 1.5 * iqr
    hi_fence = q3 + 1.5 * iqr
    in_range = [t for t in times if lo_fence <= t <= hi_fence]
    whisker_low = min(in_range) if in_range else times[0]
    whisker_high = max(in_range) if in_range else times[-1]
    outliers = [
        {"lap_number": l["lap_number"], "lap_time_s": round(l["lap_time_s"], 3)}
        for l in laps if l["lap_time_s"] < lo_fence or l["lap_time_s"] > hi_fence
    ]
    mu = sum(times) / n
    var = sum((t - mu) ** 2 for t in times) / n
    sigma = var ** 0.5
    return jsonify({
        "session_id":     sid,
        "lap_count":      n,
        "min_s":          round(times[0], 3),
        "max_s":          round(times[-1], 3),
        "q1_s":           round(q1, 3),
        "median_s":       round(q2, 3),
        "q3_s":           round(q3, 3),
        "iqr_s":          round(iqr, 3),
        "whisker_low_s":  round(whisker_low, 3),
        "whisker_high_s": round(whisker_high, 3),
        "outliers":       outliers,
        "mean_s":         round(mu, 3),
        "stddev_s":       round(sigma, 3),
    })


@bp.route("/session/<sid>/ideal_lap", methods=["GET"])
def session_ideal_lap(sid: str):
    """Theoretical fastest lap = sum of best per-sector times."""
    sonoma = state.sonoma
    laps, err = _laps_or_400(sid)
    if err:
        return err
    sectors_per_lap = [lap_sectors(sid, l) for l in laps]
    best_per_sector = []
    for sec in sonoma.SECTORS:
        best_time = None
        from_lap = None
        for lap, secs in zip(laps, sectors_per_lap):
            for s in secs:
                if s["name"] != sec.name:
                    continue
                if best_time is None or s["time_s"] < best_time:
                    best_time = s["time_s"]
                    from_lap = lap["lap_number"]
        if best_time is not None:
            best_per_sector.append({
                "name":     sec.name,
                "time_s":   round(best_time, 3),
                "from_lap": from_lap,
            })
    if not best_per_sector:
        return jsonify({"error": "no sector times computed"}), 400
    ideal = sum(s["time_s"] for s in best_per_sector)
    best_actual = min(l["lap_time_s"] for l in laps)
    return jsonify({
        "session_id":        sid,
        "ideal_lap_s":       round(ideal, 3),
        "best_actual_lap_s": round(best_actual, 3),
        "gain_potential_s":  round(best_actual - ideal, 3),
        "best_sectors":      best_per_sector,
    })


@bp.route("/session/<sid>/sector_times", methods=["GET"])
def session_sector_times(sid: str):
    """Thinner per-lap-per-sector view: just S1/S2/S3 numbers."""
    sonoma = state.sonoma
    laps, err = _laps_or_400(sid)
    if err:
        return err
    sectors_per_lap = [lap_sectors(sid, l) for l in laps]
    laps_out = []
    for lap, secs in zip(laps, sectors_per_lap):
        s_by_name = {s["name"]: s["time_s"] for s in secs}
        laps_out.append({
            "lap_number": lap["lap_number"],
            "s1": round(s_by_name.get(sonoma.SECTORS[0].name, 0.0), 3),
            "s2": round(s_by_name.get(sonoma.SECTORS[1].name, 0.0), 3),
            "s3": round(s_by_name.get(sonoma.SECTORS[2].name, 0.0), 3),
        })
    return jsonify({
        "session_id": sid,
        "sector_definitions": [
            {"name": s.name, "start_m": s.start_m, "end_m": s.end_m}
            for s in sonoma.SECTORS
        ],
        "laps": laps_out,
    })


@bp.route("/session/<sid>/pedal_behavior", methods=["GET"])
def session_pedal_behavior(sid: str):
    """4-state distribution: throttle_only / brake_only / trail_brake / coast."""
    from pitwall.db import session_has_telemetry
    if not session_has_telemetry(sid):
        return jsonify({"error": "session not found", "session_id": sid}), 404
    try:
        thr_th = float(request.args.get("throttle_th") or 5.0)
        brk_th = float(request.args.get("brake_th") or 1.0)
    except ValueError:
        return jsonify({"error": "thresholds must be numbers"}), 400

    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, throttle_pct, brake_bar FROM telemetry "
                "WHERE session_id = ? ORDER BY timestamp", [sid],
            ).fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    if not rows:
        return jsonify({"error": "session not found"}), 404

    states = {"throttle_only": 0, "brake_only": 0, "trail_brake": 0, "coast": 0}
    n = 0
    for _t, thr, brk in rows:
        thr = thr or 0.0
        brk = brk or 0.0
        on_thr = thr > thr_th
        on_brk = brk > brk_th
        if on_thr and on_brk:
            states["trail_brake"] += 1
        elif on_thr:
            states["throttle_only"] += 1
        elif on_brk:
            states["brake_only"] += 1
        else:
            states["coast"] += 1
        n += 1

    deltas = sorted(rows[i + 1][0] - rows[i][0] for i in range(len(rows) - 1)) if len(rows) > 1 else [0.1]
    frame_dt = deltas[len(deltas) // 2] if deltas else 0.1

    out = {}
    for k, v in states.items():
        out[k] = {
            "frames": v,
            "pct":    round(100.0 * v / n, 1) if n else 0.0,
            "time_s": round(v * frame_dt, 1),
        }
    return jsonify({
        "session_id":  sid,
        "frame_count": n,
        "thresholds":  {"throttle_pct": thr_th, "brake_bar": brk_th},
        "frame_dt_s":  round(frame_dt, 4),
        "states":      out,
    })


@bp.route("/session/<sid>/throttle_corner_box", methods=["GET"])
def session_throttle_corner_box(sid: str):
    """Per-corner throttle box-plot stats over all passes through that corner."""
    from pitwall.db import session_has_telemetry
    if not session_has_telemetry(sid):
        return jsonify({"error": "session not found", "session_id": sid}), 404
    track = load_track_json("sonoma") or {}
    corner_bounds = corner_bounds_from_track(track)
    if not corner_bounds:
        return jsonify({"error": "no corner geometry available"}), 422

    laps = detect_laps(sid)
    n_passes_default = max(len(laps), 1)

    out: list = []
    try:
        with db_conn() as conn:
            for c in corner_bounds:
                rows = conn.execute(
                    "SELECT throttle_pct FROM telemetry "
                    "WHERE session_id = ? AND distance_m >= ? AND distance_m <= ?",
                    [sid, c["entry_m"], c["exit_m"]],
                ).fetchall()
                samples = sorted(float(r[0]) for r in rows if r[0] is not None)
                if not samples:
                    out.append({
                        "name":       c["name"],
                        "n_passes":   0,
                        "n_samples":  0,
                        "min_pct":    None, "q1_pct": None,
                        "median_pct": None, "q3_pct": None,
                        "max_pct":    None, "mean_pct": None,
                    })
                    continue
                mean = sum(samples) / len(samples)
                out.append({
                    "name":       c["name"],
                    "n_passes":   n_passes_default,
                    "n_samples":  len(samples),
                    "min_pct":    round(samples[0], 2),
                    "q1_pct":     round(quantile(samples, 0.25), 2),
                    "median_pct": round(quantile(samples, 0.50), 2),
                    "q3_pct":     round(quantile(samples, 0.75), 2),
                    "max_pct":    round(samples[-1], 2),
                    "mean_pct":   round(mean, 2),
                })
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    return jsonify({"session_id": sid, "corners": out})


@bp.route("/session/<sid>/corner_classification", methods=["GET"])
def session_corner_classification(sid: str):
    """Group corners into low/med/high speed bands by min apex speed."""
    from pitwall.db import session_has_telemetry
    if not session_has_telemetry(sid):
        return jsonify({"error": "session not found", "session_id": sid}), 404
    try:
        low_max = float(request.args.get("low_max") or 80.0)
        med_max = float(request.args.get("med_max") or 130.0)
    except ValueError:
        return jsonify({"error": "thresholds must be numbers"}), 400
    track = load_track_json("sonoma") or {}
    corner_bounds = corner_bounds_from_track(track)
    if not corner_bounds:
        return jsonify({"error": "no corner geometry available"}), 422

    bands = {"low_speed": [], "med_speed": [], "high_speed": []}
    apex_speeds_by_band: dict = {"low_speed": [], "med_speed": [], "high_speed": []}

    try:
        with db_conn() as conn:
            for c in corner_bounds:
                row = conn.execute(
                    "SELECT MIN(speed_ms) FROM telemetry "
                    "WHERE session_id = ? AND distance_m >= ? AND distance_m <= ?",
                    [sid, c["entry_m"], c["exit_m"]],
                ).fetchone()
                min_ms = row[0] if row else None
                if min_ms is None:
                    continue
                apex_kmh = float(min_ms) * 3.6
                if apex_kmh < low_max:
                    band = "low_speed"
                elif apex_kmh < med_max:
                    band = "med_speed"
                else:
                    band = "high_speed"
                bands[band].append(c["name"])
                apex_speeds_by_band[band].append(apex_kmh)
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503

    out = []
    for band_name in ("low_speed", "med_speed", "high_speed"):
        speeds = apex_speeds_by_band[band_name]
        out.append({
            "band":              band_name,
            "corners":           bands[band_name],
            "mean_apex_kmh":     round(sum(speeds) / len(speeds), 1) if speeds else None,
            "median_apex_kmh":   round(quantile(sorted(speeds), 0.5), 1) if speeds else None,
        })
    return jsonify({
        "session_id": sid,
        "thresholds": {"low_max_kmh": low_max, "med_max_kmh": med_max},
        "bands":      out,
    })


@bp.route("/session/<sid>/straight_line_speed", methods=["GET"])
def session_straight_line_speed(sid: str):
    """Top speed per named straight (sonoma.STRAIGHTS)."""
    sonoma = state.sonoma
    from pitwall.db import session_has_telemetry
    if not session_has_telemetry(sid):
        return jsonify({"error": "session not found", "session_id": sid}), 404
    laps = detect_laps(sid)
    track_len = float(getattr(sonoma, "TRACK_LENGTH_M", 4258))

    out = []
    try:
        with db_conn() as conn:
            for st in sonoma.STRAIGHTS:
                if st.start_m <= st.end_m:
                    where = "distance_m >= ? AND distance_m <= ?"
                    params = [sid, st.start_m, st.end_m]
                else:
                    where = "(distance_m >= ? OR distance_m <= ?)"
                    params = [sid, st.start_m, st.end_m]
                row = conn.execute(
                    f"SELECT timestamp, speed_ms, distance_m FROM telemetry "
                    f"WHERE session_id = ? AND {where} "
                    f"ORDER BY speed_ms DESC LIMIT 1",
                    params,
                ).fetchone()
                if row is None:
                    out.append({
                        "name": st.name, "start_m": st.start_m, "end_m": st.end_m,
                        "top_speed_kmh": None, "from_lap": None,
                    })
                    continue
                t_top, top_ms, _d = row
                from_lap = None
                for l in laps:
                    if l["t_start"] <= t_top <= l["t_end"]:
                        from_lap = l["lap_number"]
                        break
                out.append({
                    "name":          st.name,
                    "start_m":       st.start_m,
                    "end_m":         st.end_m,
                    "top_speed_kmh": round(float(top_ms) * 3.6, 1),
                    "from_lap":      from_lap,
                })
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503
    return jsonify({"session_id": sid, "track_length_m": track_len, "straights": out})


@bp.route("/session/<sid>/brake_acceleration", methods=["GET"])
def session_brake_acceleration(sid: str):
    """Heavy-brake decel + corner-exit longitudinal accel scatter."""
    from pitwall.db import session_has_telemetry
    if not session_has_telemetry(sid):
        return jsonify({"error": "session not found", "session_id": sid}), 404
    track = load_track_json("sonoma") or {}
    corner_bounds = corner_bounds_from_track(track)
    if not corner_bounds:
        return jsonify({"error": "no corner geometry available"}), 422

    BRAKE_TH = 25.0
    laps = detect_laps(sid)
    n_passes = max(len(laps), 1)

    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, distance_m, brake_bar, throttle_pct, g_long, speed_ms "
                "FROM telemetry WHERE session_id = ? ORDER BY timestamp", [sid],
            ).fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "duckdb not available"}), 503

    def nearest_corner(d):
        if d is None:
            return None
        return min(corner_bounds, key=lambda c: abs(d - c["entry_m"]))["name"]

    brake_zones: list = []
    current: list = []
    for r in rows:
        if (r[2] or 0.0) > BRAKE_TH:
            current.append(r)
        elif current:
            brake_zones.append(current)
            current = []
    if current:
        brake_zones.append(current)

    decel_by_corner: dict = {}
    duration_by_corner: dict = {}
    for zone in brake_zones:
        ts = [z[0] for z in zone]
        glongs = [z[4] for z in zone if z[4] is not None]
        d_mid = zone[len(zone) // 2][1]
        if not glongs:
            continue
        cname = nearest_corner(d_mid)
        if cname is None:
            continue
        peak = min(glongs)
        decel_by_corner.setdefault(cname, []).append(peak)
        duration_by_corner.setdefault(cname, []).append(ts[-1] - ts[0])

    brake_zones_out = []
    for cname in sorted(decel_by_corner.keys()):
        peaks = decel_by_corner[cname]
        durs = duration_by_corner.get(cname, [])
        brake_zones_out.append({
            "corner":      cname,
            "max_decel_g": round(sum(peaks) / len(peaks), 3),
            "duration_s":  round(sum(durs) / len(durs), 2) if durs else 0.0,
            "n_passes":    len(peaks),
        })

    accel_by_corner: dict = {}
    exit_speed_by_corner: dict = {}
    for c in corner_bounds:
        glongs = [r[4] for r in rows
                  if r[1] is not None and c["apex_m"] <= r[1] <= c["exit_m"]
                  and (r[3] or 0) > 50 and r[4] is not None]
        exit_speeds = [r[5] for r in rows
                       if r[1] is not None and abs(r[1] - c["exit_m"]) < 5
                       and r[5] is not None]
        if glongs:
            accel_by_corner[c["name"]] = max(glongs)
        if exit_speeds:
            exit_speed_by_corner[c["name"]] = sum(exit_speeds) / len(exit_speeds)

    corner_exits_out = []
    for cname in sorted(accel_by_corner.keys()):
        corner_exits_out.append({
            "corner":           cname,
            "max_long_accel_g": round(accel_by_corner[cname], 3),
            "exit_speed_kmh":   round(exit_speed_by_corner.get(cname, 0.0) * 3.6, 1),
            "n_passes":         n_passes,
        })

    return jsonify({
        "session_id":   sid,
        "brake_zones":  brake_zones_out,
        "corner_exits": corner_exits_out,
    })
