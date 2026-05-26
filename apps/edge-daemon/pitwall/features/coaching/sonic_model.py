"""
Sonic Co-Driver — maps telemetry frames to audio parameters.

Three layers of sound:
1. Grip tone (continuous) — pitch rises with friction circle usage
2. Brake approach (overlay) — ascending pitch as corner approaches
3. Trail brake guide (overlay) — pitch follows brake release through corner
4. Throttle pulse (overlay) — encourages throttle pickup after apex

Plus lap time estimation chimes at sector boundaries.
"""

from dataclasses import dataclass
from enum import Enum


class Pattern(Enum):
    """Audio playback pattern for the sonic co-driver's multi-layer output."""
    SILENT = "silent"
    CONTINUOUS = "continuous"
    PULSE = "pulse"
    FAST_PULSE = "fast_pulse"
    SHARP = "sharp"
    BUZZ = "buzz"
    CHIME_UP = "chime_up"       # ascending — ahead of pace
    CHIME_DOWN = "chime_down"   # descending — behind pace
    CHIME_NEUTRAL = "chime_neutral"


@dataclass
class AudioCue:
    """A single sonic coaching cue — one layer of the multi-layer audio output."""
    layer: str          # "grip", "brake_approach", "trail_brake", "throttle", "lap_estimate"
    frequency: float    # Hz (200-2000)
    volume: float       # 0.0-1.0
    pattern: Pattern
    priority: int       # 0 (background) to 3 (safety)
    reason: str         # human-readable explanation for debugging


# Session-level calibration (updated from observed data)
MAX_COMBO_G = 2.29      # from VBO analysis
MAX_BRAKE_BAR = 73.5    # from VBO analysis
MAX_RPM = 8321.0        # from VBO analysis


def compute_cues(frame: dict, prev_frame: object = None) -> list[AudioCue]:
    """
    Map a telemetry frame to zero or more audio cues.
    Returns a list of cues that should be mixed and played.
    """
    cues = []

    speed = frame.get("speed", 0)               # m/s
    g_lat = frame.get("g_lat", 0)
    g_long = frame.get("g_long", 0)
    combo_g = frame.get("combo_g", 0)
    brake = frame.get("brake_pressure", 0)       # bar
    throttle = frame.get("throttle", 0)          # 0-100
    steering = frame.get("steering", 0)          # degrees
    dist_to_corner = frame.get("distance_to_corner", 999)
    corner_severity = frame.get("corner_severity", 0)
    past_apex = frame.get("past_apex", False)
    in_corner = frame.get("in_corner", False)

    # ===== LAYER 1: GRIP TONE (always active, background) =====
    grip_usage = min(combo_g / MAX_COMBO_G, 1.5) if MAX_COMBO_G > 0 else 0

    if grip_usage > 1.05:
        # OVER THE LIMIT — sliding
        cues.append(AudioCue(
            layer="grip",
            frequency=1600,
            volume=0.8,
            pattern=Pattern.BUZZ,
            priority=3,
            reason=f"Over grip limit: {combo_g:.2f}G / {MAX_COMBO_G:.2f}G max"
        ))
    elif grip_usage > 0.90:
        # AT THE LIMIT — high pitch, loud
        cues.append(AudioCue(
            layer="grip",
            frequency=1200 + (grip_usage - 0.9) * 4000,
            volume=0.5,
            pattern=Pattern.CONTINUOUS,
            priority=0,
            reason=f"Near limit: {grip_usage:.0%} grip usage"
        ))
    elif grip_usage > 0.3:
        # WORKING — moderate pitch
        freq = 200 + (grip_usage * 1000)
        vol = 0.1 + (grip_usage * 0.25)
        cues.append(AudioCue(
            layer="grip",
            frequency=freq,
            volume=vol,
            pattern=Pattern.CONTINUOUS,
            priority=0,
            reason=f"Grip: {grip_usage:.0%}"
        ))
    # Below 0.3 grip usage — silence (on straight, no feedback needed)

    # ===== LAYER 2: BRAKE APPROACH (corner approaching, driver not braking yet) =====
    if corner_severity > 0 and dist_to_corner < corner_severity * 50 and dist_to_corner > 5 and brake < 2:
        approach_pct = 1.0 - (dist_to_corner / (corner_severity * 50))
        approach_pct = max(0, min(1, approach_pct))

        if approach_pct > 0.85:
            # Very close to brake point — sharp beep
            cues.append(AudioCue(
                layer="brake_approach",
                frequency=1200,
                volume=0.7,
                pattern=Pattern.FAST_PULSE,
                priority=2,
                reason=f"Brake zone! {dist_to_corner:.0f}m to corner"
            ))
        else:
            # Approaching — ascending pitch
            freq = 400 + (approach_pct * 800)
            vol = 0.15 + (approach_pct * 0.45)
            cues.append(AudioCue(
                layer="brake_approach",
                frequency=freq,
                volume=vol,
                pattern=Pattern.PULSE,
                priority=1,
                reason=f"Approaching corner: {dist_to_corner:.0f}m"
            ))

    # ===== LAYER 3: TRAIL BRAKE GUIDE (in corner, brake applied) =====
    if brake > 3 and abs(g_lat) > 0.4 and in_corner:
        # Pitch follows brake pressure — descends as driver releases
        brake_pct = min(brake / MAX_BRAKE_BAR, 1.0)
        freq = 300 + (brake_pct * 600)  # 300Hz at released, 900Hz at full brake
        cues.append(AudioCue(
            layer="trail_brake",
            frequency=freq,
            volume=0.35,
            pattern=Pattern.CONTINUOUS,
            priority=1,
            reason=f"Trail braking: {brake:.1f} bar ({brake_pct:.0%})"
        ))

    # ===== LAYER 4: THROTTLE PICKUP (past apex, should be accelerating) =====
    if past_apex and throttle < 20 and abs(g_lat) > 0.3 and speed > 10:
        # Gentle pulse encouraging throttle — speeds up the longer they wait
        if prev_frame and prev_frame.get("past_apex", False):
            # Has been past apex for multiple frames — increase urgency
            cues.append(AudioCue(
                layer="throttle",
                frequency=280,
                volume=0.3,
                pattern=Pattern.PULSE,
                priority=1,
                reason=f"Past apex, throttle only {throttle:.0f}%"
            ))

    # ===== COASTING DETECTION =====
    if throttle < 5 and brake < 2 and speed > 15 and not in_corner and dist_to_corner > 100:
        # On a straight, not braking, not on throttle — wasting time
        cues.append(AudioCue(
            layer="coast_warning",
            frequency=350,
            volume=0.25,
            pattern=Pattern.PULSE,
            priority=1,
            reason=f"Coasting on straight: throttle {throttle:.0f}%, brake {brake:.1f} bar"
        ))

    return cues


def compute_lap_estimate_cue(
    current_distance: float,
    elapsed_time: float,
    track_length: float,
    best_lap_time: object,
) -> object:
    """
    Estimate lap time from current pace and emit a chime.
    Called at sector boundaries.
    """
    if current_distance < 10 or track_length < 100:
        return None

    progress = (current_distance % track_length) / track_length
    if progress < 0.05:
        return None

    predicted_lap = elapsed_time / progress

    if best_lap_time is None:
        return AudioCue(
            layer="lap_estimate",
            frequency=600,
            volume=0.4,
            pattern=Pattern.CHIME_NEUTRAL,
            priority=0,
            reason=f"Predicted lap: {predicted_lap:.1f}s (no best to compare)"
        )

    delta = predicted_lap - best_lap_time

    if delta < -0.5:
        return AudioCue(
            layer="lap_estimate",
            frequency=800,
            volume=0.5,
            pattern=Pattern.CHIME_UP,
            priority=0,
            reason=f"Predicted {predicted_lap:.1f}s — {abs(delta):.1f}s AHEAD of best ({best_lap_time:.1f}s)"
        )
    elif delta > 0.5:
        return AudioCue(
            layer="lap_estimate",
            frequency=400,
            volume=0.5,
            pattern=Pattern.CHIME_DOWN,
            priority=0,
            reason=f"Predicted {predicted_lap:.1f}s — {delta:.1f}s BEHIND best ({best_lap_time:.1f}s)"
        )
    else:
        return AudioCue(
            layer="lap_estimate",
            frequency=600,
            volume=0.3,
            pattern=Pattern.CHIME_NEUTRAL,
            priority=0,
            reason=f"Predicted {predicted_lap:.1f}s — even with best ({best_lap_time:.1f}s)"
        )
