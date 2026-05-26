"""
Corner grader + time-loss decomposition for Sonoma.

Per ADR-014:
- A-F per corner, weighted by sonoma.LAP_TIME_LEVERAGE so T10/T11 dominate
  the session grade.
- Time-loss decomposition: for each corner where the driver is behind gold,
  attribute the delta to specific causes (late brake, low apex speed,
  early lift, coasting, exit understeer) so the post-session debrief
  can say *why* the time was lost, not just *how much*.

The grader is pure functions over typed inputs. The session-analyzer
plugs telemetry frames + gold standard in and gets a SessionScorecard
back, suitable for /session/<id>/scorecard.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import pitwall.features.track.sonoma as sonoma
from pitwall.features.track.gold_standard import GoldCornerPass, GoldStandard
from pitwall.features.track.track_loader import TrackMap, CornerDef


# ─── Data shapes ──────────────────────────────────────────────────────────────


@dataclass
class CornerPass:
    """The driver's actual measurements for one pass through one corner."""
    corner: str
    lap: int
    entry_speed_kmh: float
    apex_speed_kmh: float
    exit_speed_kmh: float
    min_speed_kmh: float
    peak_brake_bar: float
    brake_point_m: Optional[float]
    brake_release_m: Optional[float]
    trail_brake_bar_at_apex: float
    throttle_at_exit_pct: float
    max_g_lat: float
    max_combo_g: float
    corner_time_s: float
    coast_seconds: float                 # in-corner time with throttle<10 AND brake<2
    steering_corrections: int            # discrete steering reversals in-corner
    nothing_time_s: float                # brake-off → throttle-on gap (Bentley EoB)


@dataclass
class TimeLossAttribution:
    """Where the corner-time delta to gold actually came from."""
    cause: str                  # "late_brake" | "early_lift" | "low_apex_speed" | ...
    seconds_lost: float
    detail: str                 # short human-readable explanation


@dataclass
class CornerGrade:
    """Grade for a single corner pass — quality score, time deltas, and coaching."""
    corner: str
    lap: int
    grade: str                  # "A+" .. "F"
    score_pct: float            # 0.0..1.0 raw quality
    weight: float               # = sonoma.LAP_TIME_LEVERAGE[corner]
    delta_time_s: float         # corner_time_s - gold.corner_time_s
    entry_delta_kmh: float
    apex_delta_kmh: float
    exit_delta_kmh: float
    brake_point_delta_m: Optional[float]  # actual - gold (positive = braked too early)
    trail_brake_quality: float  # 0..1 — closer to 1 = matches gold release
    time_loss_attribution: list[TimeLossAttribution]
    trod_voice: str             # the canonical T-Rod phrase that applies


@dataclass
class SessionScorecard:
    """Aggregate session scorecard — per-corner grades and session-level metrics."""
    session_id: str
    n_laps: int
    best_lap_s: float
    gold_lap_s: float
    session_grade: str
    weighted_total_pct: float
    corners: list[CornerGrade]
    summary: str                # one-line summary; full narrative comes from LLM


# ─── Grading internals ────────────────────────────────────────────────────────


def _grade_letter(score: float) -> str:
    if score >= 0.98: return "A+"
    if score >= 0.95: return "A"
    if score >= 0.90: return "B"
    if score >= 0.80: return "C"
    if score >= 0.70: return "D"
    return "F"


def _trod_voice_for(corner: str, attribution: list[TimeLossAttribution]) -> str:
    """Pick the most relevant canonical T-Rod phrase for this corner's biggest issue."""
    if not attribution:
        # Per-corner positive voice lines for graded-A passes
        if corner == "Turn 11":
            return "Perfect line at 11 — you were right on the stacks."
        if corner == "Turn 10":
            return "Beautiful lift at T10. Momentum is king."
        if corner == "Turn 6":
            return "Clean rotation through the Carousel. Textbook."
        if corner == "Turn 7":
            return "Crushed T7 — that single-apex line worked."
        return "Nice — keep that line."

    biggest = max(attribution, key=lambda a: a.seconds_lost)
    cause = biggest.cause
    if corner == "Turn 11":
        return "Be closer to the tire stacks — distance is king."
    if corner == "Turn 10" and cause in ("late_brake", "low_apex_speed"):
        return "Lift, don't brake — fastest corner."
    if corner == "Turn 6":
        return "Smooth exit — the straight is long."
    if corner == "Turn 7":
        return "Single apex, treat as double — cut the inside."
    if cause == "early_lift":
        return "Just go 100 — wait, you're not at the apex yet."
    if cause == "low_apex_speed":
        return "You can brake less than you think."
    if cause == "coast_in_corner":
        return "Hustle — even briefly to 100%."
    if cause == "late_brake":
        return "Roll the brake to the apex, not square-wave it."
    if cause == "exit_understeer":
        return "Open up the wheel — straight shot."
    return "Smooth is fast."


def _decompose_time_loss(p: CornerPass, g: GoldCornerPass) -> list[TimeLossAttribution]:
    """Attribute the corner-time delta to specific causes.

    The simple model: each cause estimates how much faster the corner *would*
    have been if that one issue were fixed. Capped at the actual delta.
    """
    delta = p.corner_time_s - g.corner_time_s
    if delta <= 0.05:           # within 50ms is noise
        return []

    attribs: list[TimeLossAttribution] = []

    # Late brake (positive when driver braked closer to entry than gold did)
    if p.brake_point_m is not None and g.brake_point_m is not None:
        bp_delta = g.brake_point_m - p.brake_point_m
        if bp_delta < -3:           # gold's brake point was further back than yours
            seconds = min(0.05 * abs(bp_delta) / 5, delta * 0.4)
            attribs.append(TimeLossAttribution(
                cause="late_brake",
                seconds_lost=round(seconds, 3),
                detail=f"braked {abs(bp_delta):.0f} m later than gold (gold @ {g.brake_point_m:.0f} m)",
            ))

        # Early brake — ironically also a time loser on Sonoma corners that reward late entry
        if bp_delta > 5:
            seconds = min(0.04 * bp_delta / 5, delta * 0.3)
            attribs.append(TimeLossAttribution(
                cause="early_brake",
                seconds_lost=round(seconds, 3),
                detail=f"braked {bp_delta:.0f} m earlier than gold (gold @ {g.brake_point_m:.0f} m)",
            ))

    # Low apex speed — the biggest single attribution on most corners
    apex_delta = g.apex_speed_kmh - p.apex_speed_kmh
    if apex_delta > 1.5:
        # Rough: 1 km/h apex deficit = ~25 ms over a typical Sonoma corner
        seconds = min(0.025 * apex_delta, delta * 0.5)
        attribs.append(TimeLossAttribution(
            cause="low_apex_speed",
            seconds_lost=round(seconds, 3),
            detail=f"apex {p.apex_speed_kmh:.0f} km/h vs gold {g.apex_speed_kmh:.0f} km/h",
        ))

    # Exit speed deficit — extra costly because it propagates to the next straight
    exit_delta = g.exit_speed_kmh - p.exit_speed_kmh
    if exit_delta > 1.5:
        # 1 km/h exit deficit propagates ~50 ms onto the following straight
        seconds = min(0.05 * exit_delta, delta * 0.6)
        attribs.append(TimeLossAttribution(
            cause="low_exit_speed",
            seconds_lost=round(seconds, 3),
            detail=f"exit {p.exit_speed_kmh:.0f} km/h vs gold {g.exit_speed_kmh:.0f} km/h",
        ))

    # Early lift / under-throttle at exit
    if g.throttle_at_exit_pct - p.throttle_at_exit_pct > 15:
        seconds = min(0.001 * (g.throttle_at_exit_pct - p.throttle_at_exit_pct), delta * 0.3)
        attribs.append(TimeLossAttribution(
            cause="early_lift",
            seconds_lost=round(seconds, 3),
            detail=f"throttle {p.throttle_at_exit_pct:.0f}% at exit vs gold {g.throttle_at_exit_pct:.0f}%",
        ))

    # Coasting in corner — Bentley's #1 wasted-time signal. ADR-018
    # pedagogy: intermediates need a hard penalty here, not a fairness
    # cap. Threshold dropped to 0.2 s and multiplier bumped to 0.85 so a
    # 0.5 s coast registers ~0.4 s of attributed loss instead of ~0.2 s.
    if p.coast_seconds > 0.2:
        seconds = min(p.coast_seconds * 0.85, delta * 0.5)
        attribs.append(TimeLossAttribution(
            cause="coast_in_corner",
            seconds_lost=round(seconds, 3),
            detail=f"{p.coast_seconds:.1f} s coasting (no throttle, no brake)",
        ))

    # Excess "nothing time" between brake-off and throttle-on (Bentley EoB).
    # ADR-018: bumped from 0.4 to 0.6 so a 1.0 s gap in a 1.0 s delta
    # claims ~60 % of the attribution, not 40 %.
    nothing_gap = p.nothing_time_s
    if nothing_gap > 0.3:
        seconds = min(nothing_gap * 0.6, delta * 0.4)
        attribs.append(TimeLossAttribution(
            cause="nothing_time",
            seconds_lost=round(seconds, 3),
            detail=f"{nothing_gap:.2f} s between brake-off and throttle-on",
        ))

    # Steering corrections — proxy for understeer / non-smoothness
    if p.steering_corrections >= 3:
        seconds = min(0.04 * p.steering_corrections, delta * 0.25)
        attribs.append(TimeLossAttribution(
            cause="exit_understeer",
            seconds_lost=round(seconds, 3),
            detail=f"{p.steering_corrections} steering corrections (corrective driving)",
        ))

    # Cap the sum of attributions at the actual delta — don't over-attribute
    total = sum(a.seconds_lost for a in attribs)
    if total > delta and total > 0:
        scale = delta / total
        attribs = [
            TimeLossAttribution(
                cause=a.cause,
                seconds_lost=round(a.seconds_lost * scale, 3),
                detail=a.detail,
            )
            for a in attribs
        ]

    attribs.sort(key=lambda a: a.seconds_lost, reverse=True)
    return attribs


def grade_corner_pass(p: CornerPass, g: GoldCornerPass) -> CornerGrade:
    """A-F grade for one corner pass, weighted by Sonoma lap-time leverage."""
    weight = sonoma.LAP_TIME_LEVERAGE.get(p.corner, 1.0 / 11)

    # Scoring dimensions, from feedback-system.md:118-140
    def safe_ratio(actual: float, gold: float, weight: float, tolerance: float = 0.05) -> float:
        """Score a dimension as 0–1 based on gap to gold (tolerant at ±5%)."""
        if gold <= 0:
            return 1.0
        gap = abs(actual - gold) / gold
        if gap < tolerance:
            return 1.0
        return max(0.0, 1.0 - (gap / 0.30))      # 30% gap → 0 score

    s_entry  = safe_ratio(p.entry_speed_kmh, g.entry_speed_kmh, weight)
    s_apex   = safe_ratio(p.apex_speed_kmh,  g.apex_speed_kmh,  weight)
    s_exit   = safe_ratio(p.exit_speed_kmh,  g.exit_speed_kmh,  weight)
    s_time   = safe_ratio(g.corner_time_s,   p.corner_time_s,   weight)  # inverted
    s_trail  = 1.0 if g.trail_brake_bar_at_apex == 0 else min(
        p.trail_brake_bar_at_apex / max(g.trail_brake_bar_at_apex, 1.0), 1.0
    )
    # ADR-018 pedagogy: intermediates lose more time to "nothing time"
    # (the gap between brake-off and throttle-on) than to anything else.
    # This dimension drops linearly from 1.0 → 0.0 across 0 → 1.5 s
    # of dead pedal time. 0.4 s is roughly the gold-pass threshold; past
    # 1.0 s is "actively coasting through the apex" territory.
    s_nothing = max(0.0, 1.0 - p.nothing_time_s / 1.5)

    # Weighted aggregate. Adjusted from the original (entry 15, apex 25,
    # exit 30, time 20, trail 10) to make room for nothing-time at 15 %.
    # Time, trail, and entry give up the slack — they remain decisive but
    # no longer monopolise the scorecard signal.
    score = (
        s_entry  * 0.10 + s_apex   * 0.25 + s_exit    * 0.30
        + s_time * 0.15 + s_trail  * 0.05 + s_nothing * 0.15
    )
    grade = _grade_letter(score)

    delta_time = p.corner_time_s - g.corner_time_s
    attribution = _decompose_time_loss(p, g)
    voice = _trod_voice_for(p.corner, attribution)

    bp_delta = None
    if p.brake_point_m is not None and g.brake_point_m is not None:
        bp_delta = round(p.brake_point_m - g.brake_point_m, 1)

    return CornerGrade(
        corner=p.corner,
        lap=p.lap,
        grade=grade,
        score_pct=round(score, 4),
        weight=weight,
        delta_time_s=round(delta_time, 3),
        entry_delta_kmh=round(p.entry_speed_kmh - g.entry_speed_kmh, 2),
        apex_delta_kmh=round(p.apex_speed_kmh - g.apex_speed_kmh, 2),
        exit_delta_kmh=round(p.exit_speed_kmh - g.exit_speed_kmh, 2),
        brake_point_delta_m=bp_delta,
        trail_brake_quality=round(s_trail, 3),
        time_loss_attribution=attribution,
        trod_voice=voice,
    )


def grade_session(passes: list[CornerPass], gold: GoldStandard,
                  session_id: str, lap_times_s: list[float]) -> SessionScorecard:
    """Roll up per-pass grades into a session scorecard.

    For each corner, picks the driver's BEST pass (highest score) — this is
    what the scorecard surfaces, on the principle that the driver's ceiling
    is the metric that matters for coaching focus.
    """
    by_corner: dict[str, CornerGrade] = {}
    for p in passes:
        if p.corner not in gold.corners:
            continue
        cg = grade_corner_pass(p, gold.corners[p.corner])
        prior = by_corner.get(p.corner)
        if prior is None or cg.score_pct > prior.score_pct:
            by_corner[p.corner] = cg

    corners_in_order: list[CornerGrade] = []
    for name in sonoma.CORNER_ORDER:
        if name in by_corner:
            corners_in_order.append(by_corner[name])

    # Weighted total: each corner contributes its score × leverage weight
    weighted_total = sum(cg.score_pct * cg.weight for cg in corners_in_order)
    # Re-normalise if some corners are missing
    total_weight = sum(cg.weight for cg in corners_in_order)
    if total_weight > 0:
        weighted_total = weighted_total / total_weight
    session_grade = _grade_letter(weighted_total)

    best_lap_s = min(lap_times_s) if lap_times_s else gold.lap_time_s
    n_laps = len(lap_times_s)
    delta_to_gold = best_lap_s - gold.lap_time_s

    if delta_to_gold < 0.5:
        summary = f"Within {delta_to_gold:.2f}s of gold — strong session."
    elif delta_to_gold < 2.0:
        summary = f"{delta_to_gold:.1f}s off gold — meaningful gap, addressable."
    else:
        summary = f"{delta_to_gold:.1f}s off gold — focus on biggest leverage corners (T10, T11, T6)."

    return SessionScorecard(
        session_id=session_id,
        n_laps=n_laps,
        best_lap_s=round(best_lap_s, 3),
        gold_lap_s=round(gold.lap_time_s, 3),
        session_grade=session_grade,
        weighted_total_pct=round(weighted_total, 4),
        corners=corners_in_order,
        summary=summary,
    )


# ─── Frame → CornerPass extraction ────────────────────────────────────────────


def extract_corner_passes(frames, track: TrackMap, lap_assignment: list[int]) -> list[CornerPass]:
    """Iterate session frames, segment by corner × lap, produce CornerPass list.

    `lap_assignment[i]` is the integer lap number for `frames[i]`.
    """
    passes: list[CornerPass] = []
    by_lap_corner: dict[tuple[int, str], list[int]] = {}

    for i, f in enumerate(frames):
        d = f.distance % track.track_length if track.track_length else f.distance
        lap = lap_assignment[i] if i < len(lap_assignment) else 0
        for c in track.corners:
            if c.entry_distance <= d <= c.exit_distance:
                by_lap_corner.setdefault((lap, c.name), []).append(i)
                break

    for (lap, corner_name), idxs in by_lap_corner.items():
        if len(idxs) < 3:
            continue
        c = next(c for c in track.corners if c.name == corner_name)
        passes.append(_build_corner_pass(frames, c, lap, idxs, track.track_length))

    passes.sort(key=lambda p: (p.lap, sonoma.CORNER_ORDER.index(p.corner)
                               if p.corner in sonoma.CORNER_ORDER else 99))
    return passes


def _build_corner_pass(frames, corner: CornerDef, lap: int,
                       idxs: list[int], track_len: float) -> CornerPass:
    in_frames = [frames[i] for i in idxs]
    speeds = [f.speed * 3.6 for f in in_frames]
    brakes = [f.brake_pressure for f in in_frames]
    glats = [abs(f.g_lat) for f in in_frames]
    combos = [f.combo_g for f in in_frames]

    apex_dist = corner.apex_distance
    apex_idx_local = min(range(len(in_frames)),
                         key=lambda j: abs((in_frames[j].distance % track_len) - apex_dist))

    # Pre-entry window for brake-point detection
    pre_entry = [f for f in frames
                 if (corner.entry_distance - 200) < (f.distance % track_len) < corner.entry_distance]
    brake_point_m: Optional[float] = None
    for f in pre_entry:
        if f.brake_pressure > 5:
            brake_point_m = corner.entry_distance - (f.distance % track_len)
            break

    brake_release_m: Optional[float] = None
    for f in in_frames:
        if f.brake_pressure < 2:
            brake_release_m = (f.distance % track_len) - corner.entry_distance
            break

    coast_seconds = 0.0
    for j, f in enumerate(in_frames[:-1]):
        if f.throttle < 10 and f.brake_pressure < 2:
            dt = in_frames[j + 1].timestamp - f.timestamp
            coast_seconds += max(0, dt)

    steering_signs = [1 if f.steering > 0 else -1 if f.steering < 0 else 0 for f in in_frames]
    corrections = sum(1 for k in range(1, len(steering_signs))
                      if steering_signs[k] != steering_signs[k - 1] and steering_signs[k] != 0)

    # Nothing time: gap between last brake-active frame and first throttle-on frame
    last_brake_t = None
    first_throttle_t = None
    for f in in_frames:
        if f.brake_pressure > 2:
            last_brake_t = f.timestamp
        if last_brake_t is not None and first_throttle_t is None and f.throttle > 10:
            first_throttle_t = f.timestamp
            break
    nothing_time = (first_throttle_t - last_brake_t) if (last_brake_t and first_throttle_t and first_throttle_t > last_brake_t) else 0.0

    return CornerPass(
        corner=corner.name,
        lap=lap,
        entry_speed_kmh=in_frames[0].speed * 3.6,
        apex_speed_kmh=in_frames[apex_idx_local].speed * 3.6,
        exit_speed_kmh=in_frames[-1].speed * 3.6,
        min_speed_kmh=min(speeds) if speeds else 0,
        peak_brake_bar=max(brakes) if brakes else 0,
        brake_point_m=brake_point_m,
        brake_release_m=brake_release_m,
        trail_brake_bar_at_apex=in_frames[apex_idx_local].brake_pressure,
        throttle_at_exit_pct=in_frames[-1].throttle,
        max_g_lat=max(glats) if glats else 0,
        max_combo_g=max(combos) if combos else 0,
        corner_time_s=in_frames[-1].timestamp - in_frames[0].timestamp,
        coast_seconds=round(coast_seconds, 3),
        steering_corrections=corrections,
        nothing_time_s=round(nothing_time, 3),
    )


def scorecard_to_dict(s: SessionScorecard) -> dict:
    """Serialise a SessionScorecard to a JSON-safe dict for the bridge."""
    return {
        "session_id":         s.session_id,
        "n_laps":             s.n_laps,
        "best_lap_s":         s.best_lap_s,
        "gold_lap_s":         s.gold_lap_s,
        "session_grade":      s.session_grade,
        "weighted_total_pct": s.weighted_total_pct,
        "summary":            s.summary,
        "corners":            [
            {**asdict(cg),
             "time_loss_attribution": [asdict(a) for a in cg.time_loss_attribution]}
            for cg in s.corners
        ],
    }


__all__ = [
    "CornerPass", "CornerGrade", "TimeLossAttribution", "SessionScorecard",
    "grade_corner_pass", "grade_session", "extract_corner_passes",
    "scorecard_to_dict",
]
