"""
Sonoma — hardcoded constants module.

Per ADR-014, Sonoma is the canonical track of the app. Everything we
*know* about this track lives here as constants — not data-driven, not
parameterised, not loaded from JSON. The accompanying `data/tracks/
sonoma.json` carries derived/varying data (corner positions, markers,
elevation profile); this module carries facts that don't change.

Every module that needs Sonoma context imports from here:
    from src.simulator import pitwall.features.track.sonoma as sonoma
    if frame.distance > sonoma.DANGER_ZONES[0].start_m:
        ...
"""
from __future__ import annotations

from dataclasses import dataclass


TRACK_NAME = "Sonoma Raceway"
TRACK_LENGTH_M = 4258
ELEVATION_RANGE_M = 49

# Real-world Sonoma GPS — the dataset's coords (~23.49°N) are anonymised.
# `sonoma_real_gps.json` holds the full real-GPS centerline + marker pins.
SF_LAT = 38.16152
SF_LON = -122.45472
SF_HEADING_DEG = 354.2     # S/F line orientation (degrees from North CW)
TRACK_CENTROID_LAT = 38.1601
TRACK_CENTROID_LON = -122.4594


@dataclass(frozen=True)
class Sector:
    """A named track sector bounded by two cumulative-distance markers."""
    name: str
    start_m: float
    end_m: float
    description: str


@dataclass(frozen=True)
class Straight:
    """A named straight segment — feeds top-speed analysis endpoints."""
    name: str
    start_m: float
    end_m: float
    description: str


@dataclass(frozen=True)
class DangerZone:
    """A track region with elevated risk — drives safety overrides and pre-brief warnings."""
    id: str
    start_m: float
    end_m: float
    description: str
    severity: str  # "high" | "medium" | "low"


@dataclass(frozen=True)
class WeatherPhase:
    """A time-of-day weather phase — drives surface coaching and warm-up advice."""
    id: str
    start_hour: int
    end_hour: int
    surface_state: str
    coaching_note: str


# Three named sectors, not just "Sector 1/2/3"
SECTORS = (
    Sector(
        name="Front Loop",
        start_m=0,
        end_m=1294,
        description="Start/finish through the esses, into the Carousel entry",
    ),
    Sector(
        name="Carousel & Back",
        start_m=1294,
        end_m=2752,
        description="Carousel exit through T9, into T10 brake zone",
    ),
    Sector(
        name="T10 to Calamity",
        start_m=2752,
        end_m=4258,
        description="T10 exit through T11 (Calamity Corner) onto the front straight",
    ),
)


# Three named straights — top-speed measurements per straight feed
# `/session/<sid>/straight_line_speed`. Front Straight wraps over S/F.
STRAIGHTS = (
    Straight(
        name="Front Straight",
        start_m=4080,
        end_m=60,
        description="T11 exit through S/F into T1 brake zone (wraps S/F)",
    ),
    Straight(
        name="T4 Run",
        start_m=600,
        end_m=880,
        description="Short squirt out of T4 toward T5",
    ),
    Straight(
        name="T7 → T8a",
        start_m=1620,
        end_m=1820,
        description="Downhill section — fastest sustained speed",
    ),
)


# Per-corner lap-time leverage weights — drive corner-grade weighting
# and highlight-finder severity. Calibrated from Sonoma intel:
# T10 is fastest (highest brake-zone leverage), T11 exits onto the long
# main straight (highest exit-speed leverage), T6 is the longest sweeper.
# Weights sum to 1.00.
LAP_TIME_LEVERAGE = {
    "Turn 1":  0.06,
    "Turn 2":  0.08,
    "Turn 3":  0.07,
    "Turn 4":  0.09,
    "Turn 5":  0.04,
    "Turn 6":  0.13,   # Carousel — long, sets up the back-straight pace
    "Turn 7":  0.09,
    "Turn 8":  0.06,
    "Turn 9":  0.07,
    "Turn 10": 0.16,   # Fastest corner — biggest brake-zone leverage
    "Turn 11": 0.15,   # Exits onto the front straight — biggest exit-speed leverage
}

# Sanity check the weights at import time — fail loud if they drift.
assert abs(sum(LAP_TIME_LEVERAGE.values()) - 1.0) < 1e-6, \
    f"LAP_TIME_LEVERAGE must sum to 1.0, got {sum(LAP_TIME_LEVERAGE.values())}"


# Known dangerous spots — feed safety overrides during drive + a "today's danger"
# admonition in the pre-brief.
DANGER_ZONES = (
    DangerZone(
        id="T6_runoff",
        start_m=1294,
        end_m=1418,
        description="Carousel run-off — wall close on the outside",
        severity="high",
    ),
    DangerZone(
        id="T9_downhill",
        start_m=1820,
        end_m=2108,
        description="Long downhill into the Carousel exit — momentum builds",
        severity="medium",
    ),
    DangerZone(
        id="T11_dive_passing",
        start_m=4080,
        end_m=4256,
        description="Calamity Corner — canonical late-race dive-bomb passing zone",
        severity="medium",
    ),
)


# Sonoma weather pattern by hour of day (local). Drives pre-brief
# admonitions and out-lap warm-up coaching.
WEATHER_PHASES = (
    WeatherPhase(
        id="morning_fog",
        start_hour=6,
        end_hour=10,
        surface_state="cool damp",
        coaching_note="First session of the day — surface is cool and possibly damp. Build pace gradually; T6 carousel and T11 hairpin grip is below normal.",
    ),
    WeatherPhase(
        id="warm_up",
        start_hour=10,
        end_hour=12,
        surface_state="rising grip",
        coaching_note="Grip rising as the surface dries and tires reach temp. Push harder each lap.",
    ),
    WeatherPhase(
        id="peak_grip",
        start_hour=12,
        end_hour=15,
        surface_state="optimal",
        coaching_note="Peak conditions. Personal-best window — lean on the marks.",
    ),
    WeatherPhase(
        id="late_session",
        start_hour=15,
        end_hour=18,
        surface_state="tire degradation",
        coaching_note="Pace will drop with tire wear. Smoothness > aggression in the last stints.",
    ),
)


def weather_phase_for_hour(hour_local: int) -> WeatherPhase:
    """Return the WeatherPhase covering this hour. Phases use a half-open
    interval [start, end), and the last phase extends through the end of
    the day. Defaults to peak_grip if no phase covers the hour (e.g. 22:00
    early-morning case)."""
    last_end = WEATHER_PHASES[-1].end_hour
    for ph in WEATHER_PHASES:
        if ph.start_hour <= hour_local < ph.end_hour:
            return ph
    # Hours after the last defined phase fold into the last phase
    if hour_local >= last_end:
        return WEATHER_PHASES[-1]
    return WEATHER_PHASES[2]  # peak_grip default


# Sonoma was fully repaved in February 2024 — first repave in 23 years.
# Lap times dropped ~2.5 s under the previous track record per NASCAR.com.
# Implication: any pre-2024 reference VBO is materially slow vs current
# grip; gold-standard interpretation must factor this in.
SURFACE_HISTORY = {
    "last_repave_iso":  "2024-02",
    "repave_lap_time_drop_s": 2.5,
    "note": (
        "Sonoma was repaved in February 2024 (first time in 23 years, "
        "1.5 inch mill + new asphalt). Lap times immediately dropped "
        "around 2.5 s. Pre-2024 reference laps are materially slow vs "
        "current grip and should be flagged as such."
    ),
}


# Hardware quirks specific to this car + this track combo. Surfaces
# in pre-brief + helps the analyser understand telemetry artifacts.
RIG_NOTES = {
    "bluetooth_dropouts": [
        "Back of the Carousel (T6 exit, hill blocks line-of-sight to the dash mount)",
    ],
    "data_lull": "T2 → T3 climb is RPM-flat at 4500-5000 — looks like a stuck signal; it isn't.",
    "video_sync_marker": (
        "Downhill at T6 (~1340 m) has the largest IMU spike of the lap — "
        "use as the canonical A/V sync marker."
    ),
    "car": "BMW M3 (E46) — boosted brake is feathery; throttle map limits to ~99%.",
}


# Per-corner authoritative coaching tips — same content as in
# data/tracks/sonoma.json but exposed as a dict for fast lookup. Voice is
# T-Rod's where applicable, Bentley's where not. ADR-011 + ADR-014.
CORNER_TIPS = {
    "Turn 1":  "carry throttle through, swing tight to the K-wall bend",
    "Turn 2":  "you can brake less than you think; carry speed uphill",
    "Turn 3":  "give-away corner — sacrifice T3 entry to win T3a and T4",
    "Turn 4":  "downhill, off-camber — back the brake up by one marker",
    "Turn 5":  "throwaway corner — preserve T6 entry, breathe the throttle",
    "Turn 6":  "smooth exit — speed here carries the long straight; no early throttle",
    "Turn 7":  "eyes up — late turn-in, late apex; second apex matters more",
    "Turn 8":  "smooth, don't pinch — apexes all slightly late, throttle on exit",
    "Turn 9":  "setup for T10 — exit T8a at full throttle",
    "Turn 10": "lift, don't brake — fastest corner; carry full throttle past apex",
    "Turn 11": "wait for the bump to settle, trail to the apex, all the road on exit",
}


# Canonical T-Rod phrases — the LLM coach pulls from these so the
# voice is consistent across pre-brief, during-drive, and post-session.
TROD_VOICE = (
    "Distance is king",
    "Be closer to the tire stacks",
    "Open up nine, straight shot to ten",
    "Single apex, treat as double",
    "Just go 100",
    "Wait, you're not at the apex yet",
    "Roll the brake to the apex",
    "Trust the curb, it catches you",
    "Cool-down means same line, slower",
    "Cut the distance, don't open up",
)


# The full Sonoma lore block injected into every LLM coach's system prompt.
# Single source of truth — coach_engine reads this constant rather than
# composing track context from a dict.
SYSTEM_PROMPT_LORE = (
    f"TRACK CONTEXT: {TRACK_NAME}, "
    f"{TRACK_LENGTH_M / 1000:.2f} km, {ELEVATION_RANGE_M} m elevation, "
    f"11 numbered corners. "
    "Reference vocabulary at Sonoma is environmental, not numeric. "
    "Use these names when relevant: 'the bridge' (T2 brake), "
    "'the K-wall bend' (T1 apex), 'the Carousel' (T6), "
    "'just after the slight crest' (T6 brake), 'the 300 board' (T7 brake), "
    "'the Toyota sign letters' (T10 visual), 'Calamity Corner' (T11 hairpin), "
    "'the bump where the road widens left' (T11 brake — wait for the car to settle), "
    "'the third tire stack' (T11 apex). "
    "\n"
    "STRATEGY: T3 is a give-away (sacrifice for T3a/T4); "
    "T5 is throwaway (preserve T6 entry); T6 punishes early throttle; "
    "T10 is fastest — most drivers brake when they only need a lift; "
    "T11 has no painted brake board — the bump is the reference. "
    "\n"
    "T-ROD VOICE (canonical pace-note phrasings, BMW M3 intermediate-driver "
    "session at Sonoma): "
    + ". ".join(f"'{p}'" for p in TROD_VOICE) + ". "
    "\n"
    "CAR: BMW M3 (E46) — boosted brake is feathery; focus on application "
    "before adding more inputs. "
    "\n"
    "SURFACE: track was repaved February 2024 (first time in 23 years). "
    "Lap times dropped about 2.5 s vs the old surface; modern grip is "
    "materially higher than pre-2024 references suggest."
)


# Path constants — used by every module that loads track artifacts.
# Keep these as STRINGS so callers can compose os.path.expanduser /
# Path() at call time without tight coupling to a layout choice.
TRACK_JSON_RELATIVE = "data/tracks/sonoma.json"
TRACK_REAL_GPS_RELATIVE = "data/tracks/sonoma_real_gps.json"
GOLD_STANDARD_RELATIVE = "data/reference/sonoma_gold.json"
GOLD_TRACE_RELATIVE = "data/reference/sonoma_gold_trace.json"


# Exposed corner names in canonical order. Use this when iterating the
# track in lap order; matches sonoma.json corners[].name.
CORNER_ORDER = (
    "Turn 1", "Turn 2", "Turn 3", "Turn 4", "Turn 5",
    "Turn 6", "Turn 7", "Turn 8", "Turn 9", "Turn 10", "Turn 11",
)


__all__ = [
    "TRACK_NAME", "TRACK_LENGTH_M", "ELEVATION_RANGE_M",
    "SF_LAT", "SF_LON", "SF_HEADING_DEG",
    "TRACK_CENTROID_LAT", "TRACK_CENTROID_LON",
    "Sector", "DangerZone", "WeatherPhase", "Straight",
    "SECTORS", "STRAIGHTS",
    "LAP_TIME_LEVERAGE", "DANGER_ZONES", "WEATHER_PHASES",
    "weather_phase_for_hour", "RIG_NOTES", "SURFACE_HISTORY",
    "CORNER_TIPS", "TROD_VOICE", "SYSTEM_PROMPT_LORE",
    "TRACK_JSON_RELATIVE", "TRACK_REAL_GPS_RELATIVE",
    "GOLD_STANDARD_RELATIVE", "GOLD_TRACE_RELATIVE",
    "CORNER_ORDER",
]
