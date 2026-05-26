"""pitwall.features.coaching.cue_renderer — cue/rule → text + TTS timing.

Converts AudioCue objects from sonic_model into short coaching sentences,
provides a fallback rule engine for when sonic_model is unavailable, and
estimates TTS duration for the audio-ducker.
"""

from pitwall.state import state
from pitwall.features.coaching.sonic_model import compute_cues
from pitwall.features.track.track_loader import (
    find_nearest_corner,
    distance_to_corner,
)


def cues_to_coaching(cues: list) -> str:
    """Convert AudioCue list from sonic_model into a single coaching sentence."""
    if not cues:
        return "Smooth sector. Maintain pace."

    # Sort by priority descending — highest priority cue drives the message
    top = sorted(cues, key=lambda c: c.priority, reverse=True)[0]
    reason = top.reason

    # Map patterns + layers to brief coaching language
    pat = top.pattern.value if hasattr(top.pattern, "value") else str(top.pattern)
    layer = top.layer

    if pat == "buzz":
        return f"OVER GRIP LIMIT — ease off. {reason}"
    if layer == "grip" and top.priority >= 2:
        return f"At grip limit. {reason}"
    if layer == "brake_approach":
        return f"Brake marker. {reason}"
    if layer == "trail_brake":
        return f"Trail brake — hold pressure. {reason}"
    if layer == "throttle":
        return f"Throttle now. {reason}"
    if layer == "lap_estimate":
        return reason

    return reason[:120] if reason else "Stay focused."


def sonic_coaching(burst: dict) -> tuple[str, list]:
    """Run the real sonic_model over the burst's representative frame data.
    Returns (coaching_text, serialised_cues).
    """
    if not state.has_sonic:
        return None, []

    frame = {
        "speed":             burst.get("avg_speed_kmh", 0) / 3.6,
        "g_lat":             burst.get("max_lateral_g", burst.get("max_combo_g", 0) * 0.7),
        "g_long":            burst.get("max_long_g",    burst.get("max_combo_g", 0) * 0.7),
        "combo_g":           burst.get("max_combo_g", 0),
        "brake_pressure":    burst.get("max_brake_bar", 0),
        "throttle":          burst.get("avg_throttle_pct", 0),
        "steering":          burst.get("avg_steering_deg", 0),
        "distance_to_corner": burst.get("dist_to_next_corner_m", 50),
        "corner_severity":   burst.get("next_corner_severity", 3),
        "past_apex":         burst.get("past_apex", False),
        "in_corner":         burst.get("in_corner", len(burst.get("corners_visited", [])) > 0),
    }

    corners = burst.get("corners_visited", [])
    if state.track and corners:
        nearest = find_nearest_corner(state.track, burst.get("distance_m", 0))
        if nearest:
            frame["distance_to_corner"] = distance_to_corner(
                state.track, burst.get("distance_m", 0), nearest
            )
            frame["corner_severity"] = nearest.severity

    cues = compute_cues(frame, prev_frame=None)
    coaching = cues_to_coaching(cues)

    serialised = [
        {
            "layer":     c.layer,
            "frequency": c.frequency,
            "volume":    c.volume,
            "pattern":   c.pattern.value if hasattr(c.pattern, "value") else str(c.pattern),
            "priority":  c.priority,
            "reason":    c.reason,
        }
        for c in cues
    ]
    return coaching, serialised


def rule_coaching(burst: dict) -> str:
    """Fallback rule engine — used when sonic_model is unavailable."""
    avg_speed    = burst.get("avg_speed_kmh", 0)
    max_g        = burst.get("max_combo_g", 0)
    coast_frames = burst.get("coast_frames", 0)
    trail_frames = burst.get("trail_brake_frames", 0)
    frame_count  = burst.get("frame_count", 1)
    corners      = burst.get("corners_visited", [])

    coast_pct = coast_frames / max(frame_count, 1) * 100

    if max_g > 2.1:
        return "Back off — at grip limit. Smooth inputs only."
    if coast_pct > 25:
        corner = corners[0] if corners else "next corner"
        return f"Coasting {coast_pct:.0f}% of sector. Get on throttle earlier through {corner}."
    if trail_frames > 0 and max_g > 1.5:
        return "Good trail braking. Carry that commitment to the next corner."
    if avg_speed < 60:
        return "Below 60 km/h avg — check braking points, you may be braking too early."
    if avg_speed > 120:
        return "Strong sector pace. Stay smooth on the wheel."
    return f"Sector avg {avg_speed:.0f} km/h, max {max_g:.2f}G. Focus on exit speed — throttle at apex."


def estimate_tts_ms(text: str) -> int:
    """Rough TTS duration estimate for the audio-ducker hint on cue events.

    150 ms/word matches Gemini-TTS's canonical T-Rod render rate; floored at
    800 ms so a one-word safety call ('Brake!') still ducks long enough for
    a clean handover over the continuous tactical tones.
    """
    if not text:
        return 0
    words = max(1, len(text.split()))
    return max(800, words * 150)
