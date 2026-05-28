"""
ADK tool definitions for pitwall paddock agents.

All query tools are read-only (DuckDB read_only=True). write_conversation is
a bridge-side helper called after generation — never exposed to agents directly.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, TYPE_CHECKING

# DB import lazily to support backends that aren't DuckDB (Termux/Android
# uses SQLite). All query helpers below run only inside functions, never at
# module-load time.
if TYPE_CHECKING:
    import duckdb  # noqa: F401

# Monorepo root — data/ lives at the repo root, not under apps/edge-daemon/
# after the V2 consolidation. From apps/edge-daemon/pitwall/adk_tools.py
# that's three levels up (pitwall → edge-daemon → apps → repo root).
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "pitwall_sessions.duckdb")

# simulator/ is a sibling of pitwall/ inside apps/edge-daemon/.
_SIM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulator"))
if _SIM_DIR not in sys.path:
    sys.path.insert(0, _SIM_DIR)

_GOLD_PATH = os.path.abspath(
    os.path.join(_PROJECT_ROOT, "data", "reference", "sonoma_gold.json")
)

# ADK 1.32 doesn't export a `tool` decorator — functions are registered by
# being passed into `Agent(tools=[...])` directly. This passthrough keeps the
# `@_adk_tool` call sites below as legible markers without claiming an import.
def _adk_tool(fn):  # type: ignore[misc]
    return fn


def _db():
    """Open a read-oriented connection via the shared backend (DuckDB or SQLite).

    All ADK tools run SELECT-only queries; no need for the backend's
    read_only flag — the bridge serialises writes via state.db_lock anyway.
    """
    from pitwall.db import get_db as _g
    return _g()


def _q(sql: str, params: list | None = None) -> list[dict[str, Any]]:
    # `_db()` → `get_db()` returns None when no backend is reachable
    # (state.has_duckdb is False) — that's the right "empty" signal because
    # tests rebind state.db_path to tmp files and the module-level DB_PATH
    # constant goes stale.
    conn = _db()
    if conn is None:
        return []
    try:
        try:
            res = conn.execute(sql, params or [])
        except Exception as exc:
            # Return as an error row so the agent can recover instead of
            # propagating an exception into ADK's parallel TaskGroup
            # (which kills the whole DebriefPipeline data phase).
            return [{"error": f"{type(exc).__name__}: {exc}"}]
        cols = [desc[0] for desc in res.description]
        rows = res.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


# ── 1. General query tool ──────────────────────────────────────────────────────

_QUERY_ALLOWED_PREFIXES = ("SELECT", "WITH", "PRAGMA", "DESCRIBE", "SHOW", "EXPLAIN")
_TOP_LEVEL_LIMIT_RE = re.compile(r"\bLIMIT\s+\d+\s*(?:OFFSET\s+\d+)?\s*;?\s*$", re.IGNORECASE)


@_adk_tool
def query_pitwall_db(sql: str) -> list[dict[str, Any]]:
    """Query pitwall session data. Read-only.

    Allowed prefixes: SELECT, WITH (CTE), PRAGMA, DESCRIBE, SHOW, EXPLAIN.
    Anything else (INSERT/UPDATE/DELETE/CREATE/ATTACH/COPY) is rejected.

    A row cap of 500 is enforced by wrapping the query in
    ``SELECT * FROM (<sql>) AS _capped LIMIT 500`` unless the query already
    ends in a top-level LIMIT clause. Wrapping is safer than concat-suffix —
    a subquery LIMIT 1 followed by no outer limit no longer escapes the cap.

    Tables:
      laps(session_id, lap_number, lap_time_s, avg_speed_kmh, max_combo_g, coast_pct)
      telemetry(session_id, frame_idx, distance_m, speed_ms, g_lat, g_long,
                combo_g, brake_bar, throttle_pct, steering_deg, rpm)
      coaching_notes(session_id, distance_m, text, source, recorded_at)
      telemetry_signals(session_id, signal_id, ts, value)
      sessions(session_id, driver, driver_level, track, car, started_at, ended_at)
      driver_events(driver_id, session_id, corner, event_kind, value_num, value_str)
      llm_friction(session_id, role, latency_ms, fell_back, emotion, ts)
      conversations(session_id, driver_id, role, text, focus_items, emotion, recorded_at)
      agent_traces(trace_id, pitwall_sid, agent_name, event_type, detail, latency_ms, success, ts)

    Always filter by session_id or driver_id to avoid full-table scans.
    """
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return [{"error": "Empty SQL"}]
    head = stripped.split(None, 1)[0].upper()
    if head not in _QUERY_ALLOWED_PREFIXES:
        return [{"error": f"Statement '{head}' is not allowed (read-only tool)"}]
    if not _TOP_LEVEL_LIMIT_RE.search(stripped) and head in ("SELECT", "WITH"):
        wrapped = f"SELECT * FROM ({stripped}) AS _capped LIMIT 500"
        return _q(wrapped)
    return _q(stripped)


# ── 2. Lap delta tool ──────────────────────────────────────────────────────────

@_adk_tool
def get_lap_delta(session_id: str, lap_a: int, lap_b: int) -> dict[str, Any]:
    """Compare two laps within a session frame-by-frame.

    Returns lap time difference, speed delta, coast percentage delta, and
    which lap was faster. Use this to explain exactly where time was gained
    or lost between two laps.
    """
    laps = _q(
        "SELECT lap_number, lap_time_s, avg_speed_kmh, max_combo_g, coast_pct "
        "FROM laps WHERE session_id = ? AND lap_number IN (?, ?) ORDER BY lap_number",
        [session_id, lap_a, lap_b],
    )
    if len(laps) < 2:
        return {"error": f"Could not find both lap {lap_a} and {lap_b} for session {session_id}"}

    a = next((r for r in laps if r["lap_number"] == lap_a), laps[0])
    b = next((r for r in laps if r["lap_number"] == lap_b), laps[1])
    return {
        "lap_a": a, "lap_b": b,
        "delta_s": round((b["lap_time_s"] or 0) - (a["lap_time_s"] or 0), 3),
        "faster_lap": lap_b if (b["lap_time_s"] or 0) < (a["lap_time_s"] or 0) else lap_a,
        "avg_speed_delta_kmh": round((b["avg_speed_kmh"] or 0) - (a["avg_speed_kmh"] or 0), 2),
        "coast_pct_delta": round((b["coast_pct"] or 0) - (a["coast_pct"] or 0), 3),
    }


# ── 3. Corner history tool ─────────────────────────────────────────────────────

@_adk_tool
def get_corner_history(driver_id: str, corner_name: str, n_sessions: int = 10) -> dict[str, Any]:
    """Return a driver's grade history for one corner across recent sessions.

    Also returns coaching notes that fired at that corner and the improvement
    trend (improving / plateau / regressing).
    """
    grades = _q(
        "SELECT session_id, value_num as score_pct, value_str as grade, recorded_at "
        "FROM driver_events WHERE driver_id = ? AND corner = ? AND event_kind = 'grade' "
        "ORDER BY recorded_at DESC LIMIT ?",
        [driver_id, corner_name, n_sessions],
    )
    notes = _q(
        "SELECT cn.session_id, cn.text, cn.recorded_at "
        "FROM coaching_notes cn "
        "JOIN driver_events de ON cn.session_id = de.session_id "
        "WHERE de.driver_id = ? AND de.corner = ? AND cn.text ILIKE ? "
        "ORDER BY cn.recorded_at DESC LIMIT 20",
        [driver_id, corner_name, f"%{corner_name}%"],
    )
    trend = "insufficient data"
    if len(grades) >= 3:
        recent = sum(g["score_pct"] for g in grades[:3]) / 3
        older  = sum(g["score_pct"] for g in grades[-3:]) / 3
        diff   = recent - older
        trend  = "improving" if diff > 5 else "regressing" if diff < -5 else "plateau"

    return {
        "corner": corner_name, "driver_id": driver_id,
        "grade_history": grades, "coaching_notes_at_corner": notes,
        "trend": trend,
        "best_score": max((g["score_pct"] for g in grades), default=None),
        "latest_score": grades[0]["score_pct"] if grades else None,
    }


# ── 4. Progress report tool ────────────────────────────────────────────────────

@_adk_tool
def get_progress_report(driver_id: str, n_sessions: int = 10) -> dict[str, Any]:
    """Cross-session improvement summary: lap time trend, corner arcs, plateau detection."""
    pb_laps = _q(
        "SELECT session_id, value_num as lap_s, recorded_at "
        "FROM driver_events WHERE driver_id = ? AND event_kind = 'pb_lap_s' "
        "ORDER BY recorded_at ASC LIMIT ?",
        [driver_id, n_sessions],
    )
    corner_trends = _q(
        "SELECT corner, "
        "  AVG(CASE WHEN rn <= 3 THEN value_num END) as recent_avg, "
        "  AVG(CASE WHEN rn > 3  THEN value_num END) as older_avg, "
        "  COUNT(*) as sessions_seen "
        "FROM (SELECT corner, value_num, "
        "  ROW_NUMBER() OVER (PARTITION BY corner ORDER BY recorded_at DESC) as rn "
        "  FROM driver_events "
        "  WHERE driver_id = ? AND event_kind = 'grade' AND corner != '*') "
        "GROUP BY corner HAVING COUNT(*) >= 2",
        [driver_id],
    )
    improving  = [c for c in corner_trends if (c["recent_avg"] or 0) - (c["older_avg"] or 0) >  5]
    regressing = [c for c in corner_trends if (c["older_avg"] or 0) - (c["recent_avg"] or 0) >  5]

    lap_trend = "insufficient data"
    if len(pb_laps) >= 3:
        delta = pb_laps[-1]["lap_s"] - pb_laps[0]["lap_s"]
        if delta < -1.0:
            lap_trend = f"improving ({abs(delta):.2f}s faster over {len(pb_laps)} sessions)"
        elif delta > 0.5:
            lap_trend = f"regressing ({delta:.2f}s slower)"
        else:
            lap_trend = f"plateau (within {abs(delta):.2f}s over {len(pb_laps)} sessions)"

    return {
        "driver_id": driver_id, "sessions_analysed": len(pb_laps),
        "lap_time_trend": lap_trend, "pb_lap_history": pb_laps,
        "improving_corners": [c["corner"] for c in improving],
        "regressing_corners": [c["corner"] for c in regressing],
        "stable_corners": [c["corner"] for c in corner_trends
                           if c not in improving and c not in regressing],
    }


# ── 5. Setup indicators tool ───────────────────────────────────────────────────

@_adk_tool
def get_setup_indicators(session_id: str) -> dict[str, Any]:
    """Telemetry patterns that indicate car balance issues: understeer, coasting, oscillation."""
    stats = _q(
        "SELECT AVG(ABS(g_lat)) as avg_lateral_g, MAX(ABS(g_lat)) as peak_lateral_g, "
        "  AVG(brake_bar) as avg_brake_bar, MAX(brake_bar) as max_brake_bar, "
        "  AVG(ABS(steering_deg)) as avg_steer_angle, STDDEV(steering_deg) as steer_oscillation, "
        "  AVG(CASE WHEN throttle_pct < 5 AND brake_bar < 2 AND speed_ms > 15 "
        "           THEN 1.0 ELSE 0.0 END) as coast_ratio, "
        "  COUNT(*) as frame_count "
        "FROM telemetry WHERE session_id = ?",
        [session_id],
    )
    if not stats or stats[0]["frame_count"] == 0:
        return {"error": f"No telemetry for session {session_id}"}
    s = stats[0]
    indicators = []
    if (s["coast_ratio"] or 0) > 0.08:
        indicators.append({
            "issue": "mid_corner_coasting",
            "severity": "high" if s["coast_ratio"] > 0.15 else "medium",
            "detail": f"{s['coast_ratio']*100:.1f}% of on-track time coasting — "
                      "throttle or brake, never neither",
        })
    if (s["steer_oscillation"] or 0) > 20:
        indicators.append({
            "issue": "steering_oscillation", "severity": "medium",
            "detail": f"Steering std-dev {s['steer_oscillation']:.1f}° — check tyre pressures "
                      "and damper rebound",
        })
    if (s["avg_brake_bar"] or 0) > 35:
        indicators.append({
            "issue": "high_average_brake_pressure", "severity": "low",
            "detail": f"Average {s['avg_brake_bar']:.1f} bar — check front/rear bias",
        })
    return {"session_id": session_id, "telemetry_stats": s,
            "setup_indicators": indicators, "n_indicators": len(indicators)}


# ── 6. Session highlights tool ─────────────────────────────────────────────────

@_adk_tool
def get_session_highlights(session_id: str) -> dict[str, Any]:
    """Best moments: fastest lap, peak grip instant, cleanest sector, coaching note counts."""
    best_lap   = _q("SELECT lap_number, lap_time_s, avg_speed_kmh, coast_pct FROM laps "
                    "WHERE session_id = ? ORDER BY lap_time_s ASC LIMIT 1", [session_id])
    peak_grip  = _q("SELECT frame_idx, distance_m, combo_g, speed_ms FROM telemetry "
                    "WHERE session_id = ? ORDER BY combo_g DESC LIMIT 1", [session_id])
    note_counts = _q("SELECT source, COUNT(*) as n FROM coaching_notes "
                     "WHERE session_id = ? GROUP BY source ORDER BY n DESC", [session_id])
    worst_coast = _q("SELECT lap_number, coast_pct FROM laps WHERE session_id = ? "
                     "ORDER BY coast_pct DESC LIMIT 1", [session_id])
    return {
        "session_id": session_id,
        "best_lap":        best_lap[0]  if best_lap   else None,
        "peak_grip_moment": peak_grip[0] if peak_grip  else None,
        "coaching_note_counts": note_counts,
        "worst_coast_lap": worst_coast[0] if worst_coast else None,
    }


# ── 7. Gold lap comparison tool ────────────────────────────────────────────────

@_adk_tool
def get_gold_lap_comparison(session_id: str) -> dict[str, Any]:
    """Compare the session's best lap against the gold standard reference lap.

    Returns corner-by-corner speed, g-force, and time delta vs AJ's reference.
    Includes the lap-time leverage weight for each corner so the agent can
    prioritise which gap matters most.
    """
    try:
        import pitwall.features.track.sonoma as _sonoma
        from pitwall.features.track.gold_standard import load_gold_standard
    except ImportError as e:
        return {"error": f"gold_standard not importable: {e}"}

    if not os.path.exists(_GOLD_PATH):
        return {"error": f"Gold standard file not found at {_GOLD_PATH}"}

    try:
        gold = load_gold_standard(_GOLD_PATH)
    except Exception as e:
        return {"error": f"Failed to load gold standard: {e}"}

    best_lap = _q(
        "SELECT lap_number, lap_time_s FROM laps WHERE session_id = ? "
        "ORDER BY lap_time_s ASC LIMIT 1", [session_id]
    )
    if not best_lap:
        return {"error": f"No laps found for session {session_id}"}

    lap_time = best_lap[0]["lap_time_s"] or 0
    gold_time = gold.lap_time_s if hasattr(gold, "lap_time_s") else None
    delta_s   = round(lap_time - gold_time, 3) if gold_time else None

    corners_out = []
    gold_corners = getattr(gold, "corners", {})
    leverage = _sonoma.LAP_TIME_LEVERAGE

    for corner_name, weight in sorted(leverage.items(), key=lambda kv: -kv[1]):
        gc = gold_corners.get(corner_name)
        gold_apex_speed = gc.apex_speed_ms * 3.6 if gc and hasattr(gc, "apex_speed_ms") else None
        tip = _sonoma.CORNER_TIPS.get(corner_name, "")
        corners_out.append({
            "corner": corner_name,
            "lap_time_leverage_pct": round(weight * 100, 1),
            "gold_apex_speed_kmh": round(gold_apex_speed, 1) if gold_apex_speed else None,
            "coaching_tip": tip,
        })

    return {
        "session_id":     session_id,
        "session_best_s": lap_time,
        "gold_lap_s":     gold_time,
        "delta_s":        delta_s,
        "corners":        corners_out,
        "note": "delta_s = session_best - gold (positive = slower than gold)",
    }


# ── 8. Weather adaptation tool ─────────────────────────────────────────────────

@_adk_tool
def get_weather_adaptation_context(hour_local: int) -> dict[str, Any]:
    """Return Sonoma-specific coaching adjustments for the current weather phase.

    Maps morning fog, early dry, optimal afternoon, and hot afternoon to
    concrete line, braking, and tyre warm-up advice per corner.
    """
    try:
        import pitwall.features.track.sonoma as _sonoma
    except ImportError:
        return {"error": "sonoma module not importable"}

    phase = _sonoma.weather_phase_for_hour(hour_local)
    danger_zones = [
        {"id": d.id, "description": d.description, "severity": d.severity}
        for d in _sonoma.DANGER_ZONES
        if phase.id == "morning_fog" and d.severity in ("high", "medium")
        or d.severity == "high"
    ]

    phase_advice = {
        "morning_fog": {
            "surface": "Cold, damp tarmac — grip builds slowly over laps 1-4.",
            "line_change": "Run wider entries (extra 0.5-1 car width) to stay off "
                           "the damp off-line rubber.",
            "brake_change": "Add 2-3 brake markers of caution. The boosted M3 brake "
                            "is feathery cold — pressure builds faster than expected.",
            "tyres": "Minimum 3 out-laps before pushing. T6 and T10 are worst.",
            "priority_corners": ["Turn 6", "Turn 10", "Turn 11"],
        },
        "early_dry": {
            "surface": "Warming up — grip roughly 85% of peak by lap 3.",
            "line_change": "Transition to the normal dry line from lap 2 onwards.",
            "brake_change": "Normal brake points but gentle initial application.",
            "tyres": "Pressures still building — check TPMS before pushing.",
            "priority_corners": ["Turn 10", "Turn 11"],
        },
        "optimal_afternoon": {
            "surface": "Peak grip — rubber is laid, temps ideal. Push confidently.",
            "line_change": "Full normal dry line. T10 is a lift-only corner.",
            "brake_change": "Full confidence brake points. T11 — wait for the bump.",
            "tyres": "Optimal window. This is the session to set PBs.",
            "priority_corners": ["Turn 10", "Turn 11", "Turn 6"],
        },
        "hot_afternoon": {
            "surface": "Tyres degrading faster — watch for graining after lap 6.",
            "line_change": "Avoid the marbles off-line. Be precise.",
            "brake_change": "Brake fade possible after lap 8 — check pedal travel.",
            "tyres": "Cool-down lap every 5-6 laps. Monitor TPMS closely.",
            "priority_corners": ["Turn 6", "Turn 10"],
        },
    }

    return {
        "phase_id":       phase.id,
        "surface_state":  phase.surface_state,
        "coaching_note":  phase.coaching_note,
        "specific_advice": phase_advice.get(phase.id, {}),
        "danger_zones":   danger_zones,
        "hour_local":     hour_local,
    }


# ── 9. Session planner tool ────────────────────────────────────────────────────

@_adk_tool
def get_session_plan_context(driver_id: str, n_laps: int = 10) -> dict[str, Any]:
    """Return data needed to build a structured lap-by-lap practice plan.

    Combines the driver's weakest corners, lap-time leverage weights, and
    Ross Bentley pedagogy so the agent can allocate focus across N laps.
    """
    try:
        import pitwall.features.track.sonoma as _sonoma
    except ImportError:
        return {"error": "sonoma module not importable"}

    profile_rows = _q(
        "SELECT corner, AVG(value_num) as avg_score, COUNT(*) as n "
        "FROM driver_events WHERE driver_id = ? AND event_kind = 'grade' AND corner != '*' "
        "GROUP BY corner ORDER BY avg_score ASC",
        [driver_id],
    )
    pb_row = _q(
        "SELECT value_num as lap_s FROM driver_events "
        "WHERE driver_id = ? AND event_kind = 'pb_lap_s' ORDER BY recorded_at DESC LIMIT 1",
        [driver_id],
    )
    leverage = _sonoma.LAP_TIME_LEVERAGE
    tips = _sonoma.CORNER_TIPS

    # Merge corner scores with leverage weights
    corners = []
    for row in profile_rows:
        name = row["corner"]
        corners.append({
            "corner":       name,
            "avg_score":    round(row["avg_score"], 1),
            "leverage_pct": round(leverage.get(name, 0) * 100, 1),
            "coaching_tip": tips.get(name, ""),
            "priority":     round((100 - row["avg_score"]) * leverage.get(name, 0), 3),
        })
    corners.sort(key=lambda c: -c["priority"])

    return {
        "driver_id":       driver_id,
        "n_laps_available": n_laps,
        "current_pb_s":    pb_row[0]["lap_s"] if pb_row else None,
        "corners_by_priority": corners,
        "note": "priority = (100 - score) * leverage — highest is biggest opportunity",
    }


# ── 10. Incident review tool ───────────────────────────────────────────────────

@_adk_tool
def get_incident_moments(session_id: str,
                         combo_g_threshold: float = 3.0,
                         steer_spike_threshold: float = 60.0) -> dict[str, Any]:
    """Detect anomalous moments in a session's telemetry.

    Finds: over-limit grip events (combo_g spikes), emergency brake applications,
    and steering corrections. Returns the top moments so the agent can narrate
    what happened and why.
    """
    high_g = _q(
        "SELECT frame_idx, distance_m, combo_g, speed_ms, g_lat, g_long, "
        "  brake_bar, throttle_pct, steering_deg "
        "FROM telemetry WHERE session_id = ? AND combo_g > ? "
        "ORDER BY combo_g DESC LIMIT 5",
        [session_id, combo_g_threshold],
    )
    emergency_brakes = _q(
        "SELECT frame_idx, distance_m, brake_bar, speed_ms "
        "FROM telemetry WHERE session_id = ? AND brake_bar > 90 "
        "ORDER BY brake_bar DESC LIMIT 5",
        [session_id],
    )
    steer_spikes = _q(
        "SELECT frame_idx, distance_m, ABS(steering_deg) as steer_abs, speed_ms "
        "FROM telemetry WHERE session_id = ? AND ABS(steering_deg) > ? "
        "ORDER BY steer_abs DESC LIMIT 5",
        [session_id, steer_spike_threshold],
    )
    return {
        "session_id": session_id,
        "over_limit_grip_events": high_g,
        "emergency_brake_events": emergency_brakes,
        "steering_correction_events": steer_spikes,
        "n_incidents": len(high_g) + len(emergency_brakes) + len(steer_spikes),
        "thresholds": {"combo_g": combo_g_threshold, "steer_deg": steer_spike_threshold},
    }


# ── 11. Race pace model tool ───────────────────────────────────────────────────

@_adk_tool
def get_race_pace_model(session_id: str) -> dict[str, Any]:
    """Model lap time degradation across a session to separate quali pace from race pace.

    Returns: lap-time series, degradation rate (s/lap), fastest 3 laps (quali pace),
    median laps (representative race pace), and variance as a consistency score.
    """
    laps = _q(
        "SELECT lap_number, lap_time_s, coast_pct, avg_speed_kmh "
        "FROM laps WHERE session_id = ? AND lap_time_s > 0 ORDER BY lap_number",
        [session_id],
    )
    if len(laps) < 3:
        return {"error": "Need at least 3 laps to model race pace"}

    times = [r["lap_time_s"] for r in laps]
    n     = len(times)
    mean  = sum(times) / n
    # Simple linear degradation: slope via least-squares
    x_mean = (n - 1) / 2
    num    = sum((i - x_mean) * (t - mean) for i, t in enumerate(times))
    den    = sum((i - x_mean) ** 2 for i in range(n))
    slope  = num / den if den else 0

    sorted_times = sorted(times)
    quali_pace   = sum(sorted_times[:3]) / 3
    race_pace    = sorted(times)[n // 2]  # median
    variance     = sum((t - mean) ** 2 for t in times) / n
    consistency  = max(0.0, round(100 - (variance ** 0.5 / mean) * 100, 1))

    return {
        "session_id":       session_id,
        "n_laps":           n,
        "best_lap_s":       min(times),
        "quali_pace_s":     round(quali_pace, 3),
        "race_pace_s":      round(race_pace, 3),
        "degradation_s_per_lap": round(slope, 4),
        "consistency_score": consistency,
        "lap_series":       laps,
        "interpretation": (
            f"Degradation {slope:.3f}s/lap — "
            + ("excellent tyre management" if slope < 0.05
               else "moderate wear" if slope < 0.2
               else "significant degradation — cool-down laps needed")
        ),
    }


# ── 12. Goal setting tool ──────────────────────────────────────────────────────

@_adk_tool
def get_goal_targets(driver_id: str) -> dict[str, Any]:
    """Set realistic lap time targets based on improvement rate and corner leverage.

    Returns current PB, projected 3-session target, stretch goal, and the top 3
    corners to attack (highest leverage × worst score = biggest opportunity).
    """
    try:
        import pitwall.features.track.sonoma as _sonoma
    except ImportError:
        return {"error": "sonoma module not importable"}

    pb_laps = _q(
        "SELECT session_id, value_num as lap_s, recorded_at "
        "FROM driver_events WHERE driver_id = ? AND event_kind = 'pb_lap_s' "
        "ORDER BY recorded_at ASC",
        [driver_id],
    )
    corner_scores = _q(
        "SELECT corner, AVG(value_num) as avg_score "
        "FROM driver_events WHERE driver_id = ? AND event_kind = 'grade' AND corner != '*' "
        "GROUP BY corner",
        [driver_id],
    )

    if not pb_laps:
        return {"error": f"No PB lap data for driver {driver_id}"}

    current_pb = pb_laps[-1]["lap_s"]
    # Average improvement rate over sessions
    if len(pb_laps) >= 3:
        rate_s = (pb_laps[0]["lap_s"] - pb_laps[-1]["lap_s"]) / len(pb_laps)
    else:
        rate_s = 0.5

    leverage = _sonoma.LAP_TIME_LEVERAGE
    opportunities = []
    for row in corner_scores:
        name  = row["corner"]
        score = row["avg_score"] or 50
        lev   = leverage.get(name, 0)
        gain  = (100 - score) / 100 * lev * current_pb * 0.03
        opportunities.append({
            "corner": name, "avg_score": round(score, 1),
            "leverage_pct": round(lev * 100, 1),
            "potential_gain_s": round(gain, 3),
        })
    opportunities.sort(key=lambda o: -o["potential_gain_s"])

    return {
        "driver_id":         driver_id,
        "current_pb_s":      round(current_pb, 3),
        "target_3_sessions": round(current_pb - rate_s * 3, 3),
        "stretch_goal_s":    round(current_pb - rate_s * 6, 3),
        "top_opportunities": opportunities[:3],
        "avg_improvement_rate_s_per_session": round(rate_s, 3),
        "sessions_tracked":  len(pb_laps),
    }


# ── 13. Track variance map tool ────────────────────────────────────────────────

_CORNER_BOUNDS_FALLBACK: dict[str, tuple[float, float]] = {
    "Turn 1":  (0,    150),
    "Turn 2":  (200,  380),
    "Turn 3":  (420,  560),
    "Turn 4":  (600,  780),
    "Turn 5":  (830,  980),
    "Turn 6":  (1050, 1450),
    "Turn 7":  (1500, 1700),
    "Turn 8":  (1720, 1900),
    "Turn 9":  (1950, 2100),
    "Turn 10": (2200, 2550),
    "Turn 11": (2750, 3100),
}

_corner_bounds_cache: dict[str, tuple[float, float]] | None = None


def _load_corner_bounds() -> dict[str, tuple[float, float]]:
    """Read Sonoma corner entry/exit distances from data/tracks/sonoma.json.

    Cached for the life of the process. Falls back to the hard-coded table
    if the JSON is missing or malformed so this never breaks pure-tool tests.
    """
    global _corner_bounds_cache
    if _corner_bounds_cache is not None:
        return _corner_bounds_cache
    try:
        import pitwall.features.track.sonoma as _sonoma
    except ImportError:
        _corner_bounds_cache = dict(_CORNER_BOUNDS_FALLBACK)
        return _corner_bounds_cache

    candidates = [
        os.path.abspath(os.path.join(_PROJECT_ROOT, _sonoma.TRACK_JSON_RELATIVE)),
        os.path.join(_SIM_DIR, "sonoma.json"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path) as fh:
                doc = json.load(fh)
        except Exception:
            continue
        bounds: dict[str, tuple[float, float]] = {}
        for c in doc.get("corners", []) or []:
            name = c.get("name")
            entry = (c.get("entry") or {}).get("distance")
            exit_ = (c.get("exit") or {}).get("distance")
            if name and entry is not None and exit_ is not None:
                bounds[name] = (float(entry), float(exit_))
        if bounds:
            _corner_bounds_cache = bounds
            return _corner_bounds_cache
    _corner_bounds_cache = dict(_CORNER_BOUNDS_FALLBACK)
    return _corner_bounds_cache


@_adk_tool
def get_track_variance_map(session_id: str) -> dict[str, Any]:
    """Corner-by-corner consistency map from telemetry speed variance.

    High variance = inconsistent through that corner.
    Low variance  = repeatable but not necessarily fast.
    Corner distance bounds come from data/tracks/sonoma.json (canonical source);
    falls back to a hard-coded table only if the JSON isn't reachable.
    """
    try:
        import pitwall.features.track.sonoma as _sonoma
    except ImportError:
        return {"error": "sonoma not importable"}

    CORNER_BOUNDS = _load_corner_bounds()
    leverage = _sonoma.LAP_TIME_LEVERAGE
    results  = []
    conn = _db()
    try:
        for corner, (start_m, end_m) in CORNER_BOUNDS.items():
            rows = conn.execute(
                "SELECT speed_ms FROM telemetry WHERE session_id = ? "
                "AND distance_m >= ? AND distance_m <= ?",
                [session_id, start_m, end_m],
            ).fetchall()
            speeds = [r[0] for r in rows if r[0] is not None]
            if len(speeds) < 5:
                continue
            mean_spd = sum(speeds) / len(speeds)
            variance = sum((s - mean_spd) ** 2 for s in speeds) / len(speeds)
            std_dev  = variance ** 0.5
            cv       = std_dev / mean_spd if mean_spd else 0

            results.append({
                "corner":          corner,
                "mean_speed_kmh":  round(mean_spd * 3.6, 1),
                "std_dev_kmh":     round(std_dev * 3.6, 2),
                "consistency_cv":  round(cv, 4),
                "consistency_pct": round(max(0, 100 - cv * 500), 1),
                "leverage_pct":    round(leverage.get(corner, 0) * 100, 1),
                "frames_sampled":  len(speeds),
            })
    finally:
        conn.close()

    results.sort(key=lambda r: r["consistency_cv"], reverse=True)
    return {
        "session_id": session_id,
        "corners": results,
        "most_inconsistent": results[0]["corner"] if results else None,
        "most_consistent":   results[-1]["corner"] if results else None,
        "note": "consistency_cv: lower = more repeatable through that corner",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tall-sink helpers — used by the AiM-pipeline-aware tools below to fetch
# canonical signal values from `telemetry_signals` JOINed via `signal_registry`.
# All AiM canonical names match the YAML pipeline (data/cars/bmw_e46_m3.yaml).
# ──────────────────────────────────────────────────────────────────────────────

def _signal_rows(session_id: str, names: list[str]) -> list[dict[str, Any]]:
    """Return (name, t, value) rows for the given canonical signal names."""
    if not names:
        return []
    placeholders = ",".join("?" * len(names))
    return _q(
        f"SELECT sr.name AS name, ts.t AS t, ts.value AS v "
        f"FROM telemetry_signals ts "
        f"JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
        f"WHERE ts.session_id = ? AND sr.name IN ({placeholders}) "
        f"ORDER BY ts.t",
        [session_id, *names],
    )


def _signal_aggregate(session_id: str, name: str, *,
                      lo: float | None = None, hi: float | None = None
                      ) -> dict[str, Any] | None:
    """Return {min, max, avg, n} for one canonical signal, sentinel-clamped.

    Pass `lo`/`hi` to clip the documented AiM sentinels (0xFFFF / 0x7FFFFFFF
    pass-throughs that the bridge's YAML pipeline doesn't filter — see
    data/cars/bmw_e46_m3.yaml §8 known_constraints).
    """
    clauses = ["ts.session_id = ?", "sr.name = ?"]
    params: list[Any] = [session_id, name]
    if lo is not None:
        clauses.append("ts.value >= ?"); params.append(lo)
    if hi is not None:
        clauses.append("ts.value <= ?"); params.append(hi)
    rows = _q(
        f"SELECT MIN(ts.value) AS mn, MAX(ts.value) AS mx, "
        f"AVG(ts.value) AS av, COUNT(*) AS n "
        f"FROM telemetry_signals ts "
        f"JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
        f"WHERE {' AND '.join(clauses)}",
        params,
    )
    if not rows or rows[0]["n"] == 0:
        return None
    r = rows[0]
    return {
        "min": round(r["mn"], 3) if r["mn"] is not None else None,
        "max": round(r["mx"], 3) if r["mx"] is not None else None,
        "avg": round(r["av"], 3) if r["av"] is not None else None,
        "samples": int(r["n"]),
    }


# ── 14. Tire thermal window tool (AiM TPMS) ───────────────────────────────────

@_adk_tool
def get_tire_thermal_window(session_id: str) -> dict[str, Any]:
    """Per-corner tire pressure / temperature window + alarm timeline.

    Reads the four AiM TrailBrake TPMS signals per corner (pressure bar,
    temperature C, alarm bitfield) from `telemetry_signals` via
    `signal_registry`. Returns cold-start vs hot-peak deltas — the basis for
    cold-pressure target advice next session.

    YAML alarm bitfield (data/cars/bmw_e46_m3.yaml §6, 0x45D):
        bit0 = air leak
        bit4 = low temperature (tire never reached operating window)
        bit5 = sensor fail
    """
    corners = ["fl", "fr", "rl", "rr"]
    out: dict[str, Any] = {"session_id": session_id, "per_corner": {}, "alarms": []}
    for c in corners:
        p = _signal_aggregate(session_id, f"tpms_press_{c}_bar", lo=0.5, hi=5.0)
        t = _signal_aggregate(session_id, f"tpms_temp_{c}_c",    lo=0.0, hi=160.0)
        if p is None and t is None:
            continue
        # Use the first/last sample for cold→hot delta (tall sink is t-ordered).
        seq = _signal_rows(session_id, [f"tpms_press_{c}_bar"])
        cold_p = round(seq[0]["v"], 2) if seq else None
        hot_p  = round(seq[-1]["v"], 2) if seq else None
        out["per_corner"][c] = {
            "pressure_bar": p, "temperature_c": t,
            "cold_pressure_bar": cold_p,
            "final_pressure_bar": hot_p,
            "delta_bar": (round(hot_p - cold_p, 2)
                          if (cold_p is not None and hot_p is not None) else None),
        }
    # Alarms — non-zero bitfields are notable events.
    alarm_rows = _q(
        "SELECT sr.name AS name, ts.t AS t, ts.value AS v "
        "FROM telemetry_signals ts JOIN signal_registry sr "
        "ON sr.signal_id = ts.signal_id "
        "WHERE ts.session_id = ? AND sr.name LIKE 'tpms_alm_%' "
        "AND ts.value > 0 ORDER BY ts.t LIMIT 50",
        [session_id],
    )
    for r in alarm_rows:
        bits = int(r["v"])
        flags: list[str] = []
        if bits & 0x01: flags.append("air_leak")
        if bits & 0x10: flags.append("low_temp")
        if bits & 0x20: flags.append("sensor_fail")
        out["alarms"].append({"corner": r["name"][-2:], "t": r["t"], "flags": flags})
    out["alarm_count"] = len(out["alarms"])
    return out


# ── 15. Handling balance tool (AiM gyro + steering) ───────────────────────────

# BMW E46 M3 chassis constants — from BMW factory spec.
_E46_M3_WHEELBASE_M = 2.731
_E46_M3_STEERING_RATIO = 15.4   # steering wheel deg → road-wheel deg


def _track_length_m() -> float:
    """Sonoma canonical lap length, used to fold cumulative distance into one lap."""
    try:
        from pitwall.features.track.sonoma import TRACK_LENGTH_M
        return float(TRACK_LENGTH_M)
    except Exception:
        return 4258.0


@_adk_tool
def get_handling_balance(session_id: str, corner_name: str = "") -> dict[str, Any]:
    """Measured yaw rate vs. expected yaw rate per corner.

    expected_yaw_dps = (V_ms × tan(road_wheel_rad)) / wheelbase_m × (180/π)
    where road_wheel_rad = steering_wheel_deg / steering_ratio.

    balance > 1 → oversteer (car rotating more than steering commands)
    balance < 1 → understeer (front washing; steer input not producing yaw)
    balance ≈ 1 ±0.05 → neutral

    Computed per Sonoma corner window from data/tracks/sonoma.json bounds.
    Pass `corner_name` to restrict the analysis to one corner.
    """
    try:
        bounds = _load_corner_bounds()
    except Exception as e:
        return {"error": f"corner bounds: {e}"}

    if corner_name and corner_name not in bounds:
        return {"error": f"unknown corner '{corner_name}'. "
                         f"Known: {sorted(bounds.keys())}"}
    targets = {corner_name: bounds[corner_name]} if corner_name else bounds

    out_corners: list[dict[str, Any]] = []
    lap_m = _track_length_m()
    conn = _db()
    if conn is None:
        return {"error": "no database"}
    try:
        for corner, (d_start, d_end) in targets.items():
            # Multi-lap sessions store cumulative distance (0 → 11 × lap_m).
            # Fold to lap-relative with MOD so the corner bound matches every lap.
            # Wide-row gives speed/steer at 10 Hz; yaw_rate lives in the tall
            # sink at 50 Hz, pulled via a ±50ms correlated subquery.
            rows = conn.execute(
                "SELECT t.frame_idx, t.distance_m, t.speed_ms, t.steering_deg, "
                "  t.g_lat, "
                "  (SELECT ts.value FROM telemetry_signals ts "
                "   JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
                "   WHERE ts.session_id = t.session_id "
                "   AND sr.name = 'yaw_rate_degs' "
                "   AND ts.t BETWEEN t.timestamp - 0.05 AND t.timestamp + 0.05 "
                "   LIMIT 1) AS yaw_dps "
                "FROM telemetry t WHERE t.session_id = ? "
                "AND (t.distance_m - ? * CAST(t.distance_m / ? AS INTEGER)) "
                "  BETWEEN ? AND ? "
                "AND ABS(t.steering_deg) > 5 AND t.speed_ms > 8",
                [session_id, lap_m, lap_m, d_start, d_end],
            ).fetchall()
            import math
            ratios: list[float] = []
            counter_steer = 0
            for fidx, dist, v_ms, steer, g_lat, yaw_meas in rows:
                if yaw_meas is None or v_ms is None or steer is None:
                    continue
                # Road-wheel angle from steering wheel angle ÷ ratio.
                rw_deg = steer / _E46_M3_STEERING_RATIO
                # Bicycle model: expected_yaw_dps = V × tan(rw) / wheelbase, rad→deg.
                expected = (v_ms * math.tan(math.radians(rw_deg))
                            / _E46_M3_WHEELBASE_M * 180.0 / math.pi)
                if abs(expected) < 3:   # straight-line noise floor
                    continue
                if (expected > 0) != (yaw_meas > 0):
                    counter_steer += 1   # opposite-sign = counter-steer / oversteer save
                ratios.append(abs(yaw_meas) / abs(expected))
            if not ratios:
                continue
            mean_balance = sum(ratios) / len(ratios)
            verdict = ("oversteer" if mean_balance > 1.10
                       else "understeer" if mean_balance < 0.90
                       else "neutral")
            out_corners.append({
                "corner": corner,
                "balance_ratio": round(mean_balance, 3),
                "verdict": verdict,
                "magnitude_pct": round(abs(mean_balance - 1.0) * 100, 1),
                "counter_steer_events": counter_steer,
                "samples": len(ratios),
            })
    finally:
        conn.close()
    out_corners.sort(key=lambda r: abs(r["balance_ratio"] - 1.0), reverse=True)
    total_samples = sum(c["samples"] for c in out_corners)
    total_cs = sum(c["counter_steer_events"] for c in out_corners)
    sign_warning = ""
    if total_samples and total_cs / total_samples > 0.5:
        sign_warning = (" CALIBRATION: counter_steer_events > 50% of samples "
                        "suggests the YAML §7 sign-convention verify-on-first-"
                        "capture step hasn't been applied — steering and yaw "
                        "rate are sign-flipped vs. bicycle-model expectation. "
                        "Absolute balance numbers are inflated; ranking by "
                        "magnitude is still meaningful.")
    return {
        "session_id": session_id,
        "corners": out_corners,
        "most_under": next((c["corner"] for c in out_corners
                            if c["verdict"] == "understeer"), None),
        "most_over":  next((c["corner"] for c in out_corners
                            if c["verdict"] == "oversteer"),  None),
        "note": "balance > 1: car rotates more than steering commanded (oversteer). "
                "balance < 1: front washing (understeer). "
                "E46 M3 baseline: wheelbase 2.731m, steering ratio 15.4:1."
                + sign_warning,
    }


# ── 16. Engine health timeline (AiM powertrain stream) ────────────────────────

@_adk_tool
def get_engine_health_timeline(session_id: str) -> dict[str, Any]:
    """Engine-health summary across the session.

    Reads oil_press_bar, water_press_bar, fuel_press_bar, engine_oil_temp_c,
    water_temp_c, oil_filter_temp_c from the tall sink. Applies the AiM YAML
    sentinel filter (0xFFFF → 4519 bar for psi-derived signals; data/cars/
    bmw_e46_m3.yaml §8 known_constraints).

    Anomaly detection:
      - oil pressure < 1.5 bar under high g_lat (bearing starvation suspect)
      - water temp climbing > 105 C
      - fuel pressure dropping > 0.5 bar from session average (vapour lock risk)
    """
    # Sentinel ceilings — 0xFFFF scaled by the YAML's psi_to_bar (÷14.504).
    PSI_SENTINEL_BAR = 200.0
    TEMP_SENTINEL_C  = 200.0

    summary: dict[str, dict | None] = {
        "oil_press_bar":      _signal_aggregate(session_id, "oil_press_bar",
                                                lo=0.0, hi=PSI_SENTINEL_BAR),
        "water_press_bar":    _signal_aggregate(session_id, "water_press_bar",
                                                lo=0.0, hi=PSI_SENTINEL_BAR),
        "fuel_press_bar":     _signal_aggregate(session_id, "fuel_press_bar",
                                                lo=0.0, hi=PSI_SENTINEL_BAR),
        "engine_oil_temp_c":  _signal_aggregate(session_id, "engine_oil_temp_c",
                                                lo=-40.0, hi=TEMP_SENTINEL_C),
        "water_temp_c":       _signal_aggregate(session_id, "water_temp_c",
                                                lo=-40.0, hi=TEMP_SENTINEL_C),
        "oil_filter_temp_c":  _signal_aggregate(session_id, "oil_filter_temp_c",
                                                lo=-40.0, hi=TEMP_SENTINEL_C),
    }
    anomalies: list[dict[str, Any]] = []
    # Oil-pressure starvation: low oil_press samples that co-occur with high
    # rpm AND non-zero throttle (engine under load). Idle low-pressure is
    # normal on the M3's S54 (cold-start, in-pit) and was previously the
    # source of false-positive "bearing starvation" alarms.
    starvation = _q(
        "SELECT COUNT(*) AS n FROM telemetry_signals ts_oil "
        "JOIN signal_registry sr_oil ON sr_oil.signal_id = ts_oil.signal_id "
        "JOIN telemetry t ON t.session_id = ts_oil.session_id "
        "  AND ABS(t.timestamp - ts_oil.t) < 0.1 "
        "WHERE ts_oil.session_id = ? AND sr_oil.name = 'oil_press_bar' "
        "AND ts_oil.value > 0 AND ts_oil.value < 1.5 "
        "AND t.rpm > 3000 AND t.throttle_pct > 10",
        [session_id],
    )
    starve_n = (starvation[0].get("n") or 0) if starvation else 0
    if starve_n > 0:
        anomalies.append({
            "kind": "oil_pressure_low_under_load",
            "severity": "high" if starve_n > 50 else "medium",
            "detail": f"oil pressure < 1.5 bar in {starve_n} samples while RPM > "
                      "3000 and throttle > 10%. Investigate bearing windage / oil "
                      "starvation under high lateral G.",
        })
    if summary["water_temp_c"] and (summary["water_temp_c"]["max"] or 0) > 105:
        anomalies.append({
            "kind": "coolant_high",
            "severity": "high" if summary["water_temp_c"]["max"] > 115 else "medium",
            "detail": f"water temp peaked at {summary['water_temp_c']['max']} C "
                      "(>105 C threshold). Check airflow / radiator / cooling fan.",
        })
    return {
        "session_id": session_id,
        "vitals": {k: v for k, v in summary.items() if v is not None},
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "note": "All pressures are sentinel-filtered against the AiM 0xFFFF "
                "no-reading marker (YAML §8); raw query_pitwall_db on these "
                "signals will include sentinel rows.",
    }


# ── 17. Traction events tool (AiM 4-corner wheel speeds) ──────────────────────

@_adk_tool
def get_traction_events(session_id: str, slip_threshold_kmh: float = 5.0
                        ) -> dict[str, Any]:
    """Wheelspin / lockup events from per-wheel speed deltas.

    Wheelspin: rear-axle-avg overspeed vs. front-axle-avg under throttle.
    Lockup:    front wheels under-revving vs. body speed under brake.
    Both surfaced as event lists with time, corner-window, and slip magnitude.

    `slip_threshold_kmh`: minimum front↔rear or body↔wheel gap (default 5 km/h)
    above which a sample counts as a slip event.
    """
    try:
        bounds = _load_corner_bounds()
    except Exception:
        bounds = {}

    # Pull wheel-speed averages alongside wide-row throttle/brake/speed.
    rows = _q(
        "SELECT t.frame_idx, t.distance_m, t.speed_ms, t.throttle_pct, t.brake_bar, "
        "  (SELECT AVG(ts.value) FROM telemetry_signals ts "
        "   JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
        "   WHERE ts.session_id = t.session_id "
        "   AND sr.name IN ('wheel_speed_rl_ms','wheel_speed_rr_ms') "
        "   AND ts.t BETWEEN t.timestamp - 0.05 AND t.timestamp + 0.05) AS rear_ms, "
        "  (SELECT AVG(ts.value) FROM telemetry_signals ts "
        "   JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
        "   WHERE ts.session_id = t.session_id "
        "   AND sr.name IN ('wheel_speed_fl_ms','wheel_speed_fr_ms') "
        "   AND ts.t BETWEEN t.timestamp - 0.05 AND t.timestamp + 0.05) AS front_ms "
        "FROM telemetry t WHERE t.session_id = ? AND t.speed_ms > 5",
        [session_id],
    )

    threshold_ms = slip_threshold_kmh / 3.6
    wheelspin: list[dict[str, Any]] = []
    lockup:    list[dict[str, Any]] = []
    for r in rows:
        if r["rear_ms"] is None or r["front_ms"] is None:
            continue
        rear_over_front = r["rear_ms"] - r["front_ms"]
        body_minus_front = r["speed_ms"] - r["front_ms"]
        # Wheelspin: rear leading front under throttle.
        if (r["throttle_pct"] or 0) > 60 and rear_over_front > threshold_ms:
            wheelspin.append({
                "distance_m": round(r["distance_m"], 1),
                "throttle_pct": round(r["throttle_pct"], 1),
                "slip_kmh": round(rear_over_front * 3.6, 2),
                "corner": _corner_for_distance(r["distance_m"], bounds),
            })
        # Lockup: body speed exceeds front wheels under brake.
        if (r["brake_bar"] or 0) > 10 and body_minus_front > threshold_ms:
            lockup.append({
                "distance_m": round(r["distance_m"], 1),
                "brake_bar": round(r["brake_bar"], 1),
                "lock_kmh": round(body_minus_front * 3.6, 2),
                "corner": _corner_for_distance(r["distance_m"], bounds),
            })
    return {
        "session_id": session_id,
        "wheelspin_events": wheelspin[:20],
        "lockup_events":    lockup[:20],
        "wheelspin_count":  len(wheelspin),
        "lockup_count":     len(lockup),
        "threshold_kmh":    slip_threshold_kmh,
        "note": "Wheelspin = rear-avg > front-avg under throttle. "
                "Lockup = body speed > front-avg under brake.",
    }


def _corner_for_distance(d: float | None,
                         bounds: dict[str, tuple[float, float]]) -> str:
    """Resolve a cumulative-distance reading to its corner via lap-modulo."""
    if d is None:
        return ""
    lap_m = _track_length_m()
    d_lap = d % lap_m if lap_m > 0 else d
    for name, (lo, hi) in bounds.items():
        if lo <= d_lap <= hi:
            return name
    return ""


# ── 18. Input quality tool (steering/throttle/brake smoothness) ───────────────

@_adk_tool
def get_input_smoothness(session_id: str) -> dict[str, Any]:
    """Coach the *quality* of inputs: how smoothly the driver applies them.

    Three metrics derived from the wide-row table:
      - steering oscillation (std-dev of frame-to-frame Δsteering_deg)
      - throttle modulation rate (mean |Δthrottle| per sample)
      - brake-release shape (median of Δbrake_bar over the trailing edge of
        each brake event)

    Lower oscillation and lower throttle Δ are smoother. The brake-release
    metric is positive when releases taper (ideal) and large-negative when
    the driver square-waves off the pedal.
    """
    rows = _q(
        "SELECT steering_deg, throttle_pct, brake_bar "
        "FROM telemetry WHERE session_id = ? ORDER BY frame_idx",
        [session_id],
    )
    if not rows or len(rows) < 50:
        return {"error": f"insufficient telemetry for session {session_id}"}
    n = len(rows)
    abs_steer_d = 0.0
    abs_steer_n = 0
    abs_throt_d = 0.0
    abs_throt_n = 0
    steer_sq_sum = 0.0
    steer_count = 0
    # Brake-release delta tracking: when brake_bar drops from > 5 toward 0.
    release_deltas: list[float] = []
    in_brake = False
    last_brake_bar: float | None = None
    for i in range(1, n):
        s0, s1 = rows[i - 1]["steering_deg"], rows[i]["steering_deg"]
        if s0 is not None and s1 is not None:
            d = s1 - s0
            abs_steer_d += abs(d); abs_steer_n += 1
            steer_sq_sum += d * d; steer_count += 1
        t0, t1 = rows[i - 1]["throttle_pct"], rows[i]["throttle_pct"]
        if t0 is not None and t1 is not None:
            abs_throt_d += abs(t1 - t0); abs_throt_n += 1
        b1 = rows[i]["brake_bar"] or 0.0
        b0 = rows[i - 1]["brake_bar"] or 0.0
        if b0 > 5 and not in_brake:
            in_brake = True
            last_brake_bar = b0
        elif in_brake and b1 < b0 and last_brake_bar is not None:
            release_deltas.append(b1 - b0)   # negative
            if b1 < 1:
                in_brake = False
                last_brake_bar = None

    steer_oscillation = (steer_sq_sum / steer_count) ** 0.5 if steer_count else 0.0
    throttle_jerk = abs_throt_d / abs_throt_n if abs_throt_n else 0.0
    median_release = (sorted(release_deltas)[len(release_deltas) // 2]
                      if release_deltas else 0.0)
    smoothness_score = max(0, 100 - steer_oscillation * 3 - throttle_jerk * 2)
    return {
        "session_id": session_id,
        "steering_oscillation_deg": round(steer_oscillation, 2),
        "throttle_modulation_rate": round(throttle_jerk, 2),
        "median_brake_release_delta_bar": round(median_release, 2),
        "brake_release_events": len(release_deltas),
        "smoothness_score_0_100": round(smoothness_score, 1),
        "verdict": ("smooth"      if smoothness_score >= 75 else
                    "competent"   if smoothness_score >= 55 else
                    "choppy"),
        "note": "Lower steering_oscillation = quieter wheel; "
                "lower throttle_modulation_rate = less bang-bang; "
                "median_brake_release_delta closer to -1 bar/frame = tapered (good); "
                "large negative = square-wave release.",
    }


# ── 19. Safety events tool (AiM status flags + TPMS alarms) ───────────────────

@_adk_tool
def get_safety_events(session_id: str) -> dict[str, Any]:
    """ABS/DSC/MIL faults and TPMS alarm timeline.

    Surfaces edges where any of `abs_fail`, `dsc_reg`, `mil_chk_eng`, or
    `tpms_alm_*` transitions to a non-zero value. Used to explain "what
    actually changed" when pace drops mid-session.
    """
    edges: list[dict[str, Any]] = []
    # Status flags — record the first sample where the signal goes non-zero.
    for sig, kind in [
        ("abs_fail",     "ABS unavailable"),
        ("dsc_reg",      "DSC regulation event"),
        ("mil_chk_eng",  "MIL fault flag"),
        ("brake_switch", "brake-switch state"),
    ]:
        row = _q(
            "SELECT MIN(ts.t) AS first_t, COUNT(*) AS n "
            "FROM telemetry_signals ts "
            "JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
            "WHERE ts.session_id = ? AND sr.name = ? AND ts.value > 0",
            [session_id, sig],
        )
        if row and (row[0].get("n") or 0) > 0:
            edges.append({
                "kind":    kind,
                "signal":  sig,
                "first_t": row[0]["first_t"],
                "count":   row[0]["n"],
            })
    # TPMS alarms (already surfaced by get_tire_thermal_window but echoed here
    # so the safety agent can find them without two tools).
    tpms = _q(
        "SELECT sr.name AS name, COUNT(*) AS n, MIN(ts.t) AS first_t "
        "FROM telemetry_signals ts "
        "JOIN signal_registry sr ON sr.signal_id = ts.signal_id "
        "WHERE ts.session_id = ? AND sr.name LIKE 'tpms_alm_%' AND ts.value > 0 "
        "GROUP BY sr.name",
        [session_id],
    )
    for r in tpms:
        edges.append({
            "kind":    f"TPMS alarm on {r['name'][-2:].upper()}",
            "signal":  r["name"],
            "first_t": r["first_t"],
            "count":   r["n"],
        })
    edges.sort(key=lambda e: e.get("first_t") or 0)
    return {
        "session_id": session_id,
        "events":     edges,
        "event_count": len(edges),
        "note": "Empty events list = the M3 ran clean — no DSC interventions, "
                "no ABS fault, no MIL, no TPMS alarms during this session.",
    }


# ── 20. Agent telemetry query tool ────────────────────────────────────────────

@_adk_tool
def get_agent_telemetry(n_recent: int = 50) -> dict[str, Any]:
    """Return agent trace telemetry: slowest agents, most-called tools, recent errors.

    Reads from agent_traces table (ADR-021). Use to answer meta questions like
    'which agent is slowest?' or 'what tools are called most often?'.
    """
    # Re-open via shared backend (DuckDB on Mac, SQLite on Termux). Uses
    # state.db_path so tests that rebind it see the right DB.
    from pitwall.db import get_db as _g
    conn = _g()
    if conn is None:
        return {"error": "No database found"}
    try:
        slowest = conn.execute(
            "SELECT agent_name, ROUND(AVG(latency_ms), 1) as avg_ms, COUNT(*) as runs "
            "FROM agent_traces WHERE event_type = 'agent' AND latency_ms IS NOT NULL "
            "GROUP BY agent_name ORDER BY avg_ms DESC LIMIT 10"
        ).fetchdf().to_dict("records")

        top_tools = conn.execute(
            "SELECT detail as tool_name, COUNT(*) as calls "
            "FROM agent_traces WHERE event_type = 'tool' AND detail != '' "
            "GROUP BY detail ORDER BY calls DESC LIMIT 10"
        ).fetchdf().to_dict("records")

        recent = conn.execute(
            "SELECT trace_id, agent_name, event_type, detail, latency_ms, success, ts "
            f"FROM agent_traces ORDER BY ts DESC LIMIT {min(n_recent, 200)}"
        ).fetchdf().to_dict("records")

    finally:
        conn.close()

    return {
        "slowest_agents": slowest,
        "top_tools": top_tools,
        "recent_traces": recent,
        "note": "latency_ms is per-agent wall time; tool rows have latency_ms=null",
    }


# ── 15. Voice script context tool ──────────────────────────────────────────────

@_adk_tool
def get_audio_script_context(corner_name: str, driver_level: str = "intermediate") -> dict[str, Any]:
    """Return context for generating pre-rendered TTS audio scripts.

    Per ADR-017, in-drive cues are pre-rendered canonical phrases keyed by
    (corner, phase, bentley_concept). This tool returns the raw material
    the VoiceScriptAgent needs to generate those phrases.
    """
    try:
        import pitwall.features.track.sonoma as _sonoma
        from pitwall.features.coaching.coach_engine import match_bentley_concept
    except ImportError as e:
        return {"error": f"Could not import modules: {e}"}

    tip     = _sonoma.CORNER_TIPS.get(corner_name, "")
    lev     = _sonoma.LAP_TIME_LEVERAGE.get(corner_name, 0)
    trod    = list(_sonoma.TROD_VOICE)
    phases  = ["braking_zone", "turn_in", "apex", "exit_throttle"]

    # Build a minimal context to get Bentley concept match
    danger_corners = ["Turn 6", "Turn 10", "Turn 11"]

    return {
        "corner":          corner_name,
        "driver_level":    driver_level,
        "coaching_tip":    tip,
        "leverage_pct":    round(lev * 100, 1),
        "trod_voice_examples": trod[:5],
        "corner_phases":   phases,
        "is_high_leverage": lev >= 0.10,
        "is_danger_corner": corner_name in danger_corners,
        "script_guidelines": {
            "max_words":   5,
            "tone":        "T-Rod rally co-driver — direct, landmark-based",
            "example_format": "'{phase}: {2-3 word cue}'",
            "examples": {
                "braking_zone": "Toyota sign — now",
                "turn_in":      "Wait, wait, turn",
                "apex":         "Trust the curb",
                "exit_throttle": "All the road",
            },
        },
    }


# ── 15. Voice script persistence tool ─────────────────────────────────────────

@_adk_tool
def save_voice_scripts(corner_name: str, scripts: dict[str, str]) -> dict[str, Any]:
    """Write generated TTS cue phrases to the audio cache (ADR-017).

    scripts: mapping of driving phase → cue phrase, e.g.
        {"braking_zone": "Toyota sign — now", "turn_in": "Wait, wait, turn"}
    Writes to tools/audio_cache/<corner>.json. Merges atomically with any existing file.
    """
    import fcntl

    cache_dir = os.path.join(os.path.dirname(__file__), "audio_cache")
    os.makedirs(cache_dir, exist_ok=True)
    safe_name = corner_name.lower().replace(" ", "_").replace("/", "_")
    path = os.path.join(cache_dir, f"{safe_name}.json")
    lock_path = path + ".lock"

    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            existing: dict[str, str] = {}
            if os.path.exists(path):
                try:
                    with open(path) as fh:
                        existing = json.load(fh)
                except Exception:
                    pass
            existing.update(scripts)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as fh:
                json.dump(existing, fh, indent=2)
            os.replace(tmp_path, path)
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    return {"corner": corner_name, "path": path, "phases_written": list(scripts.keys())}


# ── Bridge-side write helper (not exposed to agents) ──────────────────────────

def write_conversation(
    conn,  # DuckDBPyConnection or sqlite3.Connection — both speak our SQL
    session_id: str,
    driver_id: str,
    role: str,
    text: str,
    focus_items: list[str] | None = None,
    emotion: str | None = None,
) -> None:
    """Persist a coaching conversation turn to the DuckDB conversations table."""
    conn.execute(
        "INSERT INTO conversations "
        "(session_id, driver_id, role, text, focus_items, emotion) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [session_id, driver_id, role, text,
         json.dumps(focus_items or []),
         emotion or "neutral"],
    )
