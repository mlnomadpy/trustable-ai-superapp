"""bridge.bp_core — Blueprint: /health, /analyze.

The hot-path endpoints: health check and the main telemetry analysis
endpoint that fires sonic_model + coach_engine per burst.
"""

import time
import types
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from pitwall.state import state
from pitwall.features.coaching.cue_renderer import (
    sonic_coaching, rule_coaching, estimate_tts_ms,
)
from pitwall.features.coaching.coach_engine import build_context
from pitwall.features.track.track_loader import (
    find_nearest_corner,
    distance_to_corner,
)

bp = Blueprint("core", __name__)


@bp.route("/health", methods=["GET"])
def health():
    """Return bridge status, engine type, coach + driver level, and DuckDB availability.

    PWA-facing contract — keys are stable across releases. Adding fields is
    safe; removing or renaming a key requires a coordinated PWA change.

    Extended fields (additive — original keys preserved):
      - `simulator`: { running, lap_seconds, speed_x } when the AiM MXP
        synthetic simulator is active in-process (--simulate flag).
      - `can`:       { connected, fps, frames_total, frames_unknown,
                       channel, bitrate, last_frame_age_s } from the
        CanReader's state() snapshot.
      - `litert`:    { up, transport, http_url, http_model } from the
        coach engine's own .health().

    The PWA uses these to render status badges and gate UI without
    polling multiple endpoints.
    """
    coach = state.coach
    response = {
        "status":            "ok",
        "version":           "2.1",
        "engine":            "sonic_model" if state.has_sonic else "rules",
        "coach":             getattr(coach, "name", None),
        "driver_level":      getattr(coach, "driver_level", None),
        "track":             state.track.name if state.track else None,
        "duckdb":            state.has_duckdb,
        "active_session_id": state.active_session_id,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
    }

    sim = getattr(state, "simulator", None)
    if sim is not None:
        # Read attributes defensively — sim may be a different shape in tests
        response["simulator"] = {
            "running":     getattr(sim, "_thread", None) is not None
                           and sim._thread.is_alive(),
            "lap_seconds": getattr(getattr(sim, "profile", None), "lap_seconds", None),
            "speed_x":     getattr(sim, "speed_x", None),
        }
    else:
        response["simulator"] = {"running": False}

    reader = getattr(state, "can_reader", None)
    if reader is not None:
        try:
            s = reader.state()
            response["can"] = {
                "connected":         s.get("connected", False),
                "fps":               s.get("frames_per_second", 0.0),
                "frames_total":      s.get("frames_total", 0),
                "frames_unknown":    s.get("frames_unknown", 0),
                "channel":           s.get("channel"),
                "bitrate":           s.get("bitrate"),
                "last_frame_age_s":  s.get("last_frame_age_s"),
            }
        except Exception:
            response["can"] = {"connected": False, "error": "state_unavailable"}
    else:
        response["can"] = {"connected": False}

    # LiteRT / LocalLLM status. coach may be a RuleCoach (no .health()) or
    # a LitertCoach with rich health info.
    coach_health_fn = getattr(coach, "health", None)
    if callable(coach_health_fn):
        try:
            ch = coach_health_fn()
            response["litert"] = {
                "up":         bool(ch.get("loaded", False)),
                "transport":  ch.get("transport"),
                "http_url":   ch.get("http_url"),
                "http_model": ch.get("http_model"),
            }
        except Exception:
            response["litert"] = {"up": False}
    else:
        response["litert"] = {"up": False}

    return jsonify(response)




@bp.route("/analyze", methods=["POST"])
def analyze():
    """
    Receive a telemetry burst and return coaching cues.

    Called by the Vue PWA, CAN reader pipeline, or curl. Expected JSON:
    {
      "session_id": "...",  "burst_id": 7,
      "avg_speed_kmh": 104, "max_combo_g": 1.82,
      "max_brake_bar": 45,  "avg_throttle_pct": 38,
      "coast_frames": 12,   "trail_brake_frames": 4,
      "frame_count": 75,    "corners_visited": ["Turn 3"],
      "distance_m": 1450,   "in_corner": false
    }
    """
    burst = request.get_json(force=True, silent=True) or {}
    burst_id = burst.get("burst_id", 0)

    # Accumulate burst for /insights scoring
    with state.burst_lock:
        state.session_bursts.append(burst)

    # Tier 1: Full sonic_model pipeline (audio cues)
    coaching, cues = sonic_coaching(burst)

    # Tier 2: Rule fallback
    if not coaching:
        coaching = rule_coaching(burst)
        source = "bridge_rules"
    else:
        source = "sonic_model"

    # Tier 3: Insightful Coach Engine (Pace Notes)
    pace_note = None
    coach_source = None

    if state.coach and state.track:
        frame = types.SimpleNamespace(
            speed=burst.get("avg_speed_kmh", 0) / 3.6,
            brake_pressure=burst.get("max_brake_bar", 0),
            throttle=burst.get("avg_throttle_pct", 0),
            g_lat=burst.get("max_lateral_g", burst.get("max_combo_g", 0) * 0.7),
            g_long=burst.get("max_long_g", burst.get("max_combo_g", 0) * 0.7)
        )

        distance_m = burst.get("distance_m", 0)
        nearest = find_nearest_corner(state.track, distance_m)
        dist_to_corner = distance_to_corner(state.track, distance_m, nearest) if nearest else 999.0
        in_corner_obj = nearest if burst.get("in_corner", False) else None

        ctx = build_context(
            driver_level=burst.get("driver_level", "intermediate"),
            track=state.track,
            frame=frame,
            next_corner=nearest,
            meters_to_entry=dist_to_corner,
            in_corner_obj=in_corner_obj,
            past_apex=burst.get("past_apex", False),
        )

        msg = state.coach.propose(ctx)
        msg = state.arbiter.submit(msg, now=time.time(), on_straight=abs(frame.g_lat) < 0.3)
        if msg:
            pace_note = msg.text
            coach_source = state.coach.name
            coaching = pace_note
            source = coach_source

    # Publish to /cues/stream subscribers
    sid = burst.get("session_id")
    if sid:
        from pitwall.features.realtime.bp_realtime import cue_bus
        cue_bus.publish(sid, {
            "ts":              time.time(),
            "burst_id":        burst_id,
            "phrase_id":       None,
            "text":            coaching or "",
            "priority":        1,
            "emotion":         "neutral",
            "source":          source,
            "pace_note":       pace_note,
            "expected_tts_ms": estimate_tts_ms(coaching or ""),
        })

    return jsonify({
        "coaching":     coaching,
        "cues":         cues,
        "burst_id":     burst_id,
        "source":       source,
        "pace_note":    pace_note,
        "coach_source": coach_source,
    })
