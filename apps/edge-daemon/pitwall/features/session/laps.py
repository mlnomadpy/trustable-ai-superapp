"""pitwall.features.session.laps — lap detection, sector splitting, quantile.

Pure domain logic with no Flask dependency. Can be unit-tested independently.

Three strategies for `detect_laps`, picked by data shape:
  1. Cumulative distance — real Racelogic VBOs (monotonic distance_m).
  2. Distance wraparound — synthetic per-lap data (distance resets at S/F).
  3. GPS perpendicular S/F crossing — fallback using track JSON start_finish.
"""

import json
import math
import os
from datetime import datetime, timezone

from pitwall.state import state, SIM_DIR
from pitwall.db import db_conn, DuckDbUnavailable


# ── Lap detection constants ────────────────────────────────────────────────────

LAP_MIN_S = 60.0
LAP_MAX_S = 300.0


# ── Lap detection strategies ──────────────────────────────────────────────────

def detect_laps(sid: str) -> list:
    """Detect complete laps from the wide telemetry table.

    Two strategies, tried in order:
      1. Distance wraparound — `distance_m` resets toward 0 after passing
         the track length. Works for synthetic per-lap data.
      2. GPS perpendicular S/F crossing — uses the loaded track's
         start_finish lat/lon/heading. Works for cumulative-distance data
         (real Racelogic VBO output).

    Lap times outside [60, 300] s are rejected as parser noise.
    """
    sonoma = state.sonoma
    if not state.has_duckdb:
        return []
    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, distance_m, lat, lon "
                "FROM telemetry WHERE session_id = ? "
                "ORDER BY frame_idx",
                [sid],
            ).fetchall()
    except DuckDbUnavailable:
        return []
    if len(rows) < 10:
        return []

    # Three strategies, picked by data shape:
    final_d = next((r[1] for r in reversed(rows) if r[1] is not None), 0.0) or 0.0
    track_len = float(getattr(sonoma, "TRACK_LENGTH_M", 4258))
    if final_d > track_len * 1.5:
        laps = _laps_via_cumulative_distance(rows, track_len)
    else:
        laps = _laps_via_distance_wrap(rows)
    if not laps:
        laps = _laps_via_gps_crossing(rows)

    accepted: list = []
    for l in laps:
        if LAP_MIN_S <= l["lap_time_s"] <= LAP_MAX_S:
            accepted.append({**l, "lap_number": len(accepted) + 1})
    return accepted


def _laps_via_cumulative_distance(rows: list, track_len: float) -> list:
    """Lap boundary = `floor(distance_m / track_len)` increments.

    Real Racelogic VBOs report distance as a monotonically increasing
    cumulative sum from session start. Each time this crosses a new
    multiple of track_length, the car has completed one full lap.

    Discards the pre-first-boundary segment as the out-lap.
    """
    laps: list = []
    start_idx = None
    for i in range(1, len(rows)):
        prev_d = rows[i - 1][1]
        curr_d = rows[i][1]
        if prev_d is None or curr_d is None:
            continue
        if int(curr_d // track_len) > int(prev_d // track_len):
            if start_idx is not None:
                t_start = rows[start_idx][0]
                laps.append({
                    "lap_number":  0,
                    "t_start":     t_start,
                    "t_end":       rows[i][0],
                    "lap_time_s":  rows[i][0] - t_start,
                    "frame_start": start_idx,
                    "frame_end":   i,
                })
            start_idx = i
    return laps


def _laps_via_distance_wrap(rows: list) -> list:
    """Lap = run between two distance_m wraparound points (drop > L/2)."""
    sonoma = state.sonoma
    track_len = float(getattr(sonoma, "TRACK_LENGTH_M", 4258))
    threshold = track_len / 2
    laps: list = []
    start_idx = 0
    for i in range(1, len(rows)):
        prev_d = rows[i - 1][1] or 0.0
        curr_d = rows[i][1] or 0.0
        if (prev_d - curr_d) > threshold:
            t_start = rows[start_idx][0]
            t_end   = rows[i - 1][0]
            laps.append({
                "lap_number":  0,
                "t_start":     t_start,
                "t_end":       t_end,
                "lap_time_s":  t_end - t_start,
                "frame_start": start_idx,
                "frame_end":   i - 1,
            })
            start_idx = i
    return laps


def _laps_via_gps_crossing(rows: list) -> list:
    """Negative→positive sign-change of perpendicular distance to S/F line."""
    sonoma = state.sonoma

    track_path = os.path.abspath(os.path.join(
        SIM_DIR, "..", "..", "data", "tracks", "sonoma.json",
    ))
    sf_lat = sonoma.SF_LAT
    sf_lon = sonoma.SF_LON
    sf_hdg = sonoma.SF_HEADING_DEG
    try:
        with open(track_path) as fh:
            tdata = json.load(fh)
        sf = tdata.get("start_finish") or {}
        sf_lat = float(sf.get("lat", sf_lat))
        sf_lon = float(sf.get("lon", sf_lon))
        sf_hdg = float(sf.get("heading", sf_hdg))
    except Exception:
        pass

    R = 111320.0
    cos_lat = math.cos(math.radians(sf_lat))
    theta = math.radians(sf_hdg)
    sin_t, cos_t = math.sin(theta), math.cos(theta)

    RADIAL_TOL_M = 50.0

    laps: list = []
    start_idx = None
    prev_signed = None
    for i, (t, _d, lat, lon) in enumerate(rows):
        if lat is None or lon is None:
            continue
        x = (lon - sf_lon) * cos_lat * R
        y = (lat - sf_lat) * R
        signed = -x * sin_t + y * cos_t
        radial = math.hypot(x, y)
        if prev_signed is not None and prev_signed < 0 <= signed and radial < RADIAL_TOL_M:
            if start_idx is not None:
                t_start = rows[start_idx][0]
                laps.append({
                    "lap_number":  0,
                    "t_start":     t_start,
                    "t_end":       t,
                    "lap_time_s":  t - t_start,
                    "frame_start": start_idx,
                    "frame_end":   i,
                })
            start_idx = i
        prev_signed = signed
    return laps


# ── Analysis-hub lap detection (port of docs/telemetry-viewer.html) ──────────
#
# Three strategies tried in order — GPS return-to-start, distance-based
# slicing, then speed-stint fallback. Returns the same envelope shape the
# PWA's Analysis Hall already consumes from the static viewer, plus a
# "Full session" entry as the first element regardless of which strategy
# succeeds (or fails — empty session yields just the full-session entry).


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _track_length_m() -> float:
    """Resolve TRACK_LEN_M from data/tracks/sonoma_real_gps.json then
    sonoma.json then fall back to 4060 (Sonoma)."""
    base = os.path.abspath(os.path.join(SIM_DIR, "..", "..", "data", "tracks"))
    for fname in ("sonoma_real_gps.json", "sonoma.json"):
        path = os.path.join(base, fname)
        try:
            with open(path) as fh:
                d = json.load(fh)
            v = d.get("track_length_m")
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
        except (OSError, ValueError):
            continue
    return 4060.0


def detect_analysis_laps(sid: str) -> dict:
    """Return {"laps": [...], "track_length_m": float | None}.

    Mirrors the JS in docs/telemetry-viewer.html lines ~399–510. Always
    includes a leading `{name: "Full session", method: "all", ...}`
    entry. Strategies tried in order:

      1. GPS return-to-start (valid lat/lon only).
      2. Distance-based slicing (track_len × 2 threshold).
      3. Speed-stint fallback (>2 m/s segments separated by ≥5 s gaps).
    """
    track_len_m = _track_length_m()
    if not state.has_duckdb:
        return {"laps": [], "track_length_m": track_len_m}
    try:
        with db_conn() as conn:
            agg = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp), "
                "       MAX(distance_m) - MIN(distance_m) "
                "FROM telemetry WHERE session_id = ?",
                [sid],
            ).fetchone()
            if not agg or agg[0] is None:
                return {"laps": [], "track_length_m": track_len_m}
            t_lo, t_hi, total_dist = agg
            total_dist = float(total_dist or 0.0)
            out: list = [{
                "name": "Full session",
                "t_start": float(t_lo),
                "t_end": float(t_hi),
                "duration_s": float(t_hi) - float(t_lo),
                "distance_m": total_dist,
                "method": "all",
            }]

            # 1. GPS return-to-start
            gps_rows = conn.execute(
                "SELECT timestamp, lat, lon, distance_m FROM telemetry "
                "WHERE session_id = ? "
                "  AND lat > -89 AND lat < 89 "
                "  AND lon BETWEEN -180 AND 200 "
                "  AND lat <> 0 AND lon <> 0 AND lon < 200 "
                "ORDER BY timestamp",
                [sid],
            ).fetchall()
            if len(gps_rows) > 200:
                RADIUS_M = 30.0
                MIN_LAP_S = 30.0
                MIN_LAP_M = 500.0
                cur_start = gps_rows[0]
                left_zone = False
                lap_num = 1
                gps_laps: list = []
                for r in gps_rows[1:]:
                    d_m = _haversine_m(cur_start[1], cur_start[2], r[1], r[2])
                    if not left_zone and d_m > RADIUS_M * 2:
                        left_zone = True
                    elapsed = r[0] - cur_start[0]
                    trav = float(r[3] or 0.0) - float(cur_start[3] or 0.0)
                    if left_zone and d_m < RADIUS_M and elapsed >= MIN_LAP_S and trav >= MIN_LAP_M:
                        gps_laps.append({
                            "name": f"Lap {lap_num}",
                            "t_start": float(cur_start[0]),
                            "t_end": float(r[0]),
                            "duration_s": float(elapsed),
                            "distance_m": float(trav),
                            "method": "gps",
                        })
                        lap_num += 1
                        cur_start = r
                        left_zone = False
                if gps_laps:
                    out.extend(gps_laps)
                    return {"laps": out, "track_length_m": track_len_m}

            # 2. Distance-based laps
            if total_dist >= track_len_m * 2:
                dist_rows = conn.execute(
                    "SELECT timestamp, distance_m, speed_ms FROM telemetry "
                    "WHERE session_id = ? AND distance_m IS NOT NULL "
                    "ORDER BY timestamp",
                    [sid],
                ).fetchall()
                lap_boundary = None
                lap_start_t = None
                lap_num = 1
                dist_laps: list = []
                for t, d_m, sp in dist_rows:
                    if (sp or 0.0) < 1:
                        continue
                    if lap_boundary is None:
                        lap_boundary = float(d_m) + track_len_m
                        lap_start_t = float(t)
                        continue
                    if float(d_m) >= lap_boundary:
                        dist_laps.append({
                            "name": f"Lap {lap_num}",
                            "t_start": float(lap_start_t),
                            "t_end": float(t),
                            "duration_s": float(t) - float(lap_start_t),
                            "distance_m": track_len_m,
                            "method": "distance",
                        })
                        lap_num += 1
                        lap_start_t = float(t)
                        lap_boundary += track_len_m
                if len(dist_laps) >= 2:
                    out.extend(dist_laps)
                    return {"laps": out, "track_length_m": track_len_m}

            # 3. Speed-stint fallback
            speed_rows = conn.execute(
                "SELECT timestamp, speed_ms FROM telemetry "
                "WHERE session_id = ? ORDER BY timestamp",
                [sid],
            ).fetchall()
            if len(speed_rows) > 50:
                MOVING = 2.0
                GAP_S = 5.0
                MIN_STINT_S = 20.0
                stints: list = []
                stint_start = None
                last_move_t = None
                for t, sp in speed_rows:
                    if (sp or 0.0) > MOVING:
                        if stint_start is None:
                            stint_start = float(t)
                        last_move_t = float(t)
                    elif (
                        stint_start is not None
                        and last_move_t is not None
                        and (float(t) - last_move_t) > GAP_S
                    ):
                        if last_move_t - stint_start >= MIN_STINT_S:
                            stints.append((stint_start, last_move_t))
                        stint_start = None
                        last_move_t = None
                if (
                    stint_start is not None
                    and last_move_t is not None
                    and last_move_t - stint_start >= MIN_STINT_S
                ):
                    stints.append((stint_start, last_move_t))
                for i, (ts, te) in enumerate(stints, start=1):
                    d_row = conn.execute(
                        "SELECT MAX(distance_m) - MIN(distance_m) FROM telemetry "
                        "WHERE session_id = ? AND timestamp BETWEEN ? AND ?",
                        [sid, ts, te],
                    ).fetchone()
                    seg_dist = float((d_row[0] if d_row else 0) or 0.0)
                    out.append({
                        "name": f"Stint {i}",
                        "t_start": ts,
                        "t_end": te,
                        "duration_s": te - ts,
                        "distance_m": seg_dist,
                        "method": "stint",
                    })
    except DuckDbUnavailable:
        return {"laps": [], "track_length_m": track_len_m}
    return {"laps": out, "track_length_m": track_len_m}


# ── Sector splitting ──────────────────────────────────────────────────────────

def lap_sectors(sid: str, lap: dict) -> list:
    """Slice one lap into sonoma.SECTORS sub-spans by distance threshold."""
    sonoma = state.sonoma
    if not state.has_duckdb:
        return []
    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, distance_m FROM telemetry "
                "WHERE session_id = ? AND timestamp >= ? AND timestamp <= ? "
                "ORDER BY timestamp",
                [sid, lap["t_start"], lap["t_end"]],
            ).fetchall()
    except DuckDbUnavailable:
        return []
    if not rows:
        return []

    base_d = rows[0][1] or 0.0
    track_len = float(getattr(sonoma, "TRACK_LENGTH_M", 4258))

    def _lap_progress(d):
        """Convert raw cumulative distance to 0-1 lap progress fraction."""
        if d is None:
            return None
        delta = d - base_d
        if delta < -track_len / 2:
            delta += track_len
        return delta

    out: list = []
    for sec in sonoma.SECTORS:
        t_enter = None
        t_exit = None
        for t, d in rows:
            p = _lap_progress(d)
            if p is None:
                continue
            if t_enter is None and p >= sec.start_m:
                t_enter = t
            if t_exit is None and p >= sec.end_m:
                t_exit = t
                break
        if t_enter is None:
            continue
        if t_exit is None:
            t_exit = rows[-1][0]
        out.append({
            "name":    sec.name,
            "start_m": sec.start_m,
            "end_m":   sec.end_m,
            "t_enter": t_enter,
            "t_exit":  t_exit,
            "time_s":  t_exit - t_enter,
        })
    return out


# ── Statistics ─────────────────────────────────────────────────────────────────

def quantile(sorted_vals: list, p: float) -> float:
    """Tukey linear-interp quantile per docs/api.md spec."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    h = p * (n - 1) + 1.0
    lo = max(int(h) - 1, 0)
    hi = min(lo + 1, n - 1)
    frac = h - int(h)
    return float(sorted_vals[lo]) + frac * (float(sorted_vals[hi]) - float(sorted_vals[lo]))


# ── Session id ─────────────────────────────────────────────────────────────────

def new_session_id(track_name: str | None = None) -> str:
    """Stable session id derived from the track + UTC stamp.

    Used by /coach/debrief and /session/import when the caller doesn't
    supply their own session_id.
    """
    slug = (track_name or "session").lower().replace(" ", "-")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{stamp}"
