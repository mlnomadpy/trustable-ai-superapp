"""
RuleCoach — zero-dependency templated coach.

Always available, useful as a baseline and as the fallback when the LLM is
unreachable. Rally-pace-note style phrases keyed by a small pedagogical-vector
matcher (Ross Bentley curriculum, see pedagogy.match_bentley_concept).
"""

from __future__ import annotations

from typing import Optional

from pitwall.features.coaching.engine_base import (
    CoachContext,
    CoachEngine,
    CoachingMessage,
)


# ─── Templated rule coach (no LLM) ────────────────────────────────────────────


class RuleCoach(CoachEngine):
    """Zero-dependency templated coach. Always available, useful as a baseline
    and as the fallback when the LLM is unreachable.

    Phrasing follows the rally-pace-note convention:
        <distance> <corner direction> <severity> [, brake at <m>] [, hint]
    Tuned per driver level.
    """

    name = "rule"

    def __init__(self, driver_level: str = "intermediate"):
        self.driver_level = driver_level

    def propose(self, ctx: CoachContext) -> Optional[CoachingMessage]:
        # Decide priority & whether to fire at all
        if not ctx.next_corner_name and not ctx.in_corner:
            return None
        if 0 < ctx.meters_to_entry < 250:
            prio = 1  # strategy: corner ahead
        elif ctx.in_corner and ctx.bentley_concept in ("entry_release",):
            prio = 2  # technique correction mid-corner
        elif ctx.bentley_concept == "hustle":
            prio = 1
        else:
            return None

        line = self._render(ctx)
        if not line:
            return None
        return CoachingMessage(
            text=line,
            priority=prio,
            reason=f"rule:{ctx.bentley_concept}",
        )

    def _render(self, ctx: CoachContext) -> str:
        c = ctx
        d = "right" if c.next_corner_direction == "R" else "left" if c.next_corner_direction == "L" else ""
        sev = c.next_corner_severity
        m_in = int(round(c.meters_to_entry))
        bz = int(round(c.next_brake_zone_m))
        apex = int(round(c.next_apex_speed_kmh))
        elev_hint = ""
        if c.next_elevation_change_m <= -5:
            elev_hint = ", downhill"
        elif c.next_elevation_change_m >= 5:
            elev_hint = ", uphill"

        # Use the corner's nickname when one exists ("the Carousel" beats "Turn 6")
        corner_name = c.next_corner_nickname or c.next_corner_name
        # Prefer the named brake marker when available ("brake at the bridge"
        # beats "brake at 60m") — Sonoma intel doc finding.
        brake_phrase = (
            f"brake at {c.next_brake_marker_label}"
            if c.next_brake_marker_label
            else (f"brake {bz}" if bz > 0 else "")
        )

        if self.driver_level == "beginner":
            if 0 < m_in < 250 and corner_name:
                if c.bentley_concept == "downhill_brake":
                    return f"{corner_name} ahead, brake early, it goes down"
                if c.bentley_concept == "eob":
                    return f"{corner_name} coming up, look into the corner"
                if c.next_brake_marker_label:
                    return f"{corner_name} in {m_in} meters, {brake_phrase}"
                return f"{corner_name} in {m_in} meters, brake smoothly"
            if c.bentley_concept == "hustle":
                return "full throttle here"
            if c.bentley_concept == "entry_release":
                return "keep a little brake on"
            return ""

        if self.driver_level == "pro":
            if 0 < m_in < 250 and corner_name:
                if c.next_brake_marker_label:
                    return f"{corner_name} {m_in}m, {c.next_brake_marker_label}, apex {apex}"
                return f"{corner_name} {m_in}m, BP {bz}m, apex {apex}"
            if c.bentley_concept == "hustle":
                return "hustle"
            return ""

        # intermediate (default) — pace-note shorthand with optional landmark
        if 0 < m_in < 250 and corner_name:
            head = f"{m_in}, {d} {sev}".strip(", ")
            base = head
            if c.next_corner_nickname:
                base = f"{m_in}, {c.next_corner_nickname}"
            if brake_phrase:
                base += f", {brake_phrase}"
            if c.bentley_concept == "late_apex":
                base += ", late apex"
            elif c.bentley_concept == "eob":
                base += ", look in"
            base += elev_hint
            return base
        if c.bentley_concept == "hustle":
            return "full throttle, even briefly"
        if c.bentley_concept == "entry_release":
            return "trail brake to apex"
        if c.bentley_concept == "exit_speed":
            return "throttle now, exit speed"
        return ""
