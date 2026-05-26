"""
Coaching pedagogy — Bentley curriculum matcher + capability-aware rule registry.

The Bentley concept matcher (`match_bentley_concept`) picks one short
pedagogical tag per frame from the Ross Bentley curriculum distilled in
`memory/project_pitwall_bentley_pedagogy.md`. The ADR-015 Phase 4 coach-rule
registry (`COACH_RULES`, `coach_rule`, `evaluate_coach_gating`) declares what
each rule needs from the session capabilities envelope so the frontend can
advertise which rules will fire before they fire.
"""

from __future__ import annotations

from dataclasses import dataclass

from pitwall.features.coaching.engine_base import CoachContext


# ─── ADR-015 Phase 4: capability-aware coach rule registry ──────────────────


@dataclass(frozen=True)
class CoachRule:
    """A coach rule's capability declaration.

    The decorated callable is not yet wired into RuleCoach — Phase 4 ships
    the registry + capability filter so the frontend's capabilities endpoint
    can advertise *which rules will fire on this session*. Phase 5 will
    consume the same registry to actually dispatch coaching at runtime.
    """
    id: str
    description: str
    requires: tuple        # signal names this rule reads
    min_rates: tuple       # ((signal_name, hz), ...)


COACH_RULES: list[CoachRule] = []


def coach_rule(*, id: str, description: str = "",
               requires=None, min_rates=None):
    """Decorator that registers a coach rule with its capability requirements.

    Example:
        @coach_rule(id="oil_temp_warning_t11", requires=["oil_temp_c"],
                    min_rates={"oil_temp_c": 1.0})
        def oil_warning(ctx, signals): ...
    """
    req_tuple = tuple(requires or [])
    rates_tuple = tuple(sorted((min_rates or {}).items()))

    def decorator(fn):
        # De-dupe by id (in-place) — a re-import of this module shouldn't
        # double-register. Mutate rather than rebind so other modules that
        # imported the list see the update.
        COACH_RULES[:] = [r for r in COACH_RULES if r.id != id]
        COACH_RULES.append(CoachRule(
            id=id, description=description or fn.__doc__ or "",
            requires=req_tuple, min_rates=rates_tuple,
        ))
        return fn
    return decorator


def evaluate_coach_gating(caps_by_name: dict) -> tuple[list, list]:
    """Split COACH_RULES into (available, disabled) given session capabilities.

    `caps_by_name` maps signal name → {"mean_hz": float, "useful": bool}.
    A rule is *available* iff every name in `requires` is present in caps
    AND every (name, min_hz) in `min_rates` is satisfied by caps[name].mean_hz.
    `disabled` items carry a human-readable reason.
    """
    available: list = []
    disabled: list = []
    for rule in COACH_RULES:
        missing = [n for n in rule.requires if n not in caps_by_name]
        if missing:
            disabled.append({
                "coach_id": rule.id,
                "reason":   f"missing signal: {missing[0]}",
            })
            continue
        rate_fail = None
        for nm, min_hz in rule.min_rates:
            actual = float(caps_by_name.get(nm, {}).get("mean_hz", 0.0))
            if actual < float(min_hz):
                rate_fail = (nm, actual, min_hz)
                break
        if rate_fail:
            nm, actual, min_hz = rate_fail
            disabled.append({
                "coach_id": rule.id,
                "reason":   f"{nm} rate ({actual:.1f} Hz) below min_useful_hz ({min_hz:.1f})",
            })
            continue
        available.append(rule.id)
    return available, disabled


# ─── Built-in coach rules (capability declarations only — Phase 5 wires them) ─


@coach_rule(
    id="base_pace_note",
    description="Default pace-note coaching from sonic_model cues.",
    requires=["speed_ms", "distance_m"],
)
def _rule_base_pace_note(ctx, signals):  # pragma: no cover
    pass


@coach_rule(
    id="trail_brake_score",
    description="Score trail-brake quality at corner entry.",
    requires=["brake_bar", "throttle_pct", "g_lat", "speed_ms"],
)
def _rule_trail_brake_score(ctx, signals):  # pragma: no cover
    pass


@coach_rule(
    id="oil_temp_warning_t11",
    description="Warn driver if oil temp > 105°C approaching T11.",
    requires=["oil_temp_c", "distance_m"],
    min_rates={"oil_temp_c": 1.0},
)
def _rule_oil_temp_warning(ctx, signals):  # pragma: no cover
    pass


@coach_rule(
    id="clutch_balance",
    description="Score clutch position smoothness during shifts.",
    requires=["clutch_pos_pct", "rpm"],
    min_rates={"clutch_pos_pct": 5.0},
)
def _rule_clutch_balance(ctx, signals):  # pragma: no cover
    pass


@coach_rule(
    id="tpms_drift",
    description="Alert on tire pressure drift across stints.",
    requires=["tpms_fl_kpa", "tpms_fr_kpa", "tpms_rl_kpa", "tpms_rr_kpa"],
    min_rates={"tpms_fl_kpa": 5.0},
)
def _rule_tpms_drift(ctx, signals):  # pragma: no cover
    pass


@coach_rule(
    id="slip_angle_oscillation",
    description=(
        "ADR-018 pedagogy: detect rapid swings between friction bands "
        "(approaching_peak ↔ over_driving) within a 3 s window — the "
        "intermediate-driver pattern of overshooting the limit and "
        "reining it back. Cue: 'Smooth is fast — dial it back to 90 percent.' "
        "Reads combo_g + g_lat at high rate so the band assignment is "
        "stable enough to count crossings."
    ),
    requires=["combo_g", "g_lat"],
    min_rates={"combo_g": 20.0, "g_lat": 20.0},
)
def _rule_slip_angle_oscillation(ctx, signals):  # pragma: no cover
    pass


@coach_rule(
    id="mid_corner_coasting",
    description=(
        "ADR-018 pedagogy: penalise the intermediate-driver pattern of "
        "coasting between brake release and throttle-on. Fires when "
        "brake_bar < 0.5 AND throttle_pct < 5 for more than ~0.4 s while "
        "still under lateral load (corner). The cue ('Get back to throttle' "
        "or 'Stop coasting — pick a pedal') closes the dead-pedal gap that "
        "dominates time loss for HPDE drivers."
    ),
    requires=["brake_bar", "throttle_pct", "g_lat", "speed_ms"],
    min_rates={"brake_bar": 10.0, "throttle_pct": 10.0},
)
def _rule_mid_corner_coasting(ctx, signals):  # pragma: no cover
    pass


# ─── Pedagogical vector matcher ───────────────────────────────────────────────


def match_bentley_concept(ctx: CoachContext) -> tuple[str, str]:
    """Pick the single most relevant Ross Bentley concept for this frame.

    Returns (concept_name, one_short_tip). Empty strings if nothing fits.
    Source: docs/Performance-Driving-Illustrated-2-23-24.pdf, distilled in
    memory/project_pitwall_bentley_pedagogy.md.
    """
    # Trail brake on entry
    if ctx.in_corner and ctx.brake_pct > 10 and abs(ctx.g_lat) > 0.4:
        return "trail_brake", "smooth release as steering increases"
    # Entry-released-brake antipattern
    if ctx.in_corner and ctx.brake_pct < 1 and abs(ctx.g_lat) > 0.6:
        return "entry_release", "keep some brake to load the fronts"
    # Past apex with no throttle = wasted exit
    if ctx.past_apex and ctx.throttle_pct < 20 and abs(ctx.g_lat) > 0.3:
        return "exit_speed", "throttle now, exit speed beats corner speed"
    # Coast on a straight
    if not ctx.in_corner and ctx.throttle_pct < 5 and ctx.brake_pct < 2 \
            and ctx.speed_kmh > 50 and ctx.meters_to_entry > 100:
        return "hustle", "100 percent throttle even briefly"
    # Approaching brake zone
    if 30 < ctx.meters_to_entry < ctx.next_brake_zone_m + 30 and ctx.brake_pct < 2:
        return "eob", "look at end of braking, not start"
    # Downhill braking
    if ctx.next_elevation_change_m < -5 and ctx.meters_to_entry < 200:
        return "downhill_brake", "downhill, brake earlier"
    # Uphill braking
    if ctx.next_elevation_change_m > 5 and ctx.meters_to_entry < 200:
        return "uphill_brake", "uphill, zone is shorter"
    # Default approach reminder for upcoming corner
    if 0 < ctx.meters_to_entry < 250:
        return "late_apex", "late apex for a faster exit"
    # On a clean straight far from anything
    return "look_ahead", "eyes far ahead"
