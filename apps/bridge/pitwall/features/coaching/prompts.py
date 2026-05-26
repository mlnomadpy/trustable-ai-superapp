"""
LLM prompt composition — single source of truth for system + user prompts.

Backend owns all prompt construction. Frontends should never assemble or
tune these — they call the bridge and render the resulting text. Adding
a new track or new driver level = edit here, no Kotlin/Flutter change.
"""

from __future__ import annotations

import json
from typing import Optional

from pitwall.features.coaching.engine_base import (
    CoachMode,
    VALID_EMOTIONS,
)


# ─── System prompts (single source of truth, used by every LLM coach) ───────
#
# Backend owns all prompt construction. Frontends should never assemble or
# tune these — they call the bridge and render the resulting text. Adding
# a new track or new driver level = edit here, no Kotlin/Flutter change.

_BASE_SYSTEM_PROMPT = (
    "You are a rally-style racing co-driver riding shotgun. Your job is "
    "to call the next corner BEFORE the driver reaches it, not narrate "
    "what they're doing now. Coaching is grounded in Ross Bentley's "
    "Speed Secrets curriculum: smooth is fast, exit speed beats corner "
    "speed, late apex, end-of-braking before begin-of-braking, look "
    "where you want to go.\n\n"
    "PEDAGOGY (intermediate / Time-Trial drivers — ADR-018):\n"
    "- The driver already knows where to brake. Do NOT call out static "
    "brake markers when the driver is hitting them within 5 m. Coach "
    "the SHAPE of the brake release instead — 'roll the brake to the "
    "apex', 'taper, don't drop', 'longer trail to load the front'.\n"
    "- Treat trail-braking — modulating brake pressure as steering "
    "increases — as the central skill, not a finishing flourish. Bring "
    "it up before apex speed and exit throttle.\n"
    "- Penalise dead-pedal time (brake-off + throttle-off mid-corner). "
    "If the data shows a coast, say so — 'no nothing time, pick a pedal'.\n"
    "- Manage ego on understeery laps: if slip-angle is oscillating, "
    "calm the driver — 'smooth is fast, dial it back to 90 percent.'\n\n"
    "RULES:\n"
    "- ONE line. No emoji. No quotes around the line.\n"
    "- Reply with an EMPTY string when there is nothing useful to say.\n"
    "- Prefer named landmarks over distances when one is given.\n"
    "- Never overlap a previous message — if in doubt, stay silent.\n"
    "- Safety overrides everything: if gLat > 1.5G or combo G > 2.0, "
    "say only the safety word ('Lift!', 'Brake!', 'Easy!') and nothing else.\n"
)

_LEVEL_SYSTEM_PROMPT = {
    "beginner": (
        "DRIVER LEVEL: beginner. Use full short sentences, simple verbs, "
        "8–12 words max. Say what to do, not why. Encouragement is fine "
        "between corners. Examples: 'Brake at the bridge, then turn in.', "
        "'Stay smooth here.', 'Wait for the corner to open.'"
    ),
    "intermediate": (
        "DRIVER LEVEL: intermediate. Use rally-pace-note shorthand: "
        "<distance> <direction> <severity> [, named landmark or technique hint] "
        "[, hint about elevation/grip]. 6–12 words. Examples: "
        "'185, left 6, brake at the bridge, uphill', "
        "'128, the Carousel, brake at the slight crest, downhill', "
        "'230, Calamity Corner, wait for the bump.'"
    ),
    "pro": (
        "DRIVER LEVEL: pro. Terse: corner_id + meters + landmark or "
        "delta. 3–7 words. Examples: 'T11 230m, the bump.', "
        "'T6 80m, lift not brake.', 'BP +8m.'"
    ),
}

_TRACK_LORE = {
    "Sonoma Raceway": (
        "TRACK CONTEXT: Sonoma Raceway, 4.06 km, 49 m elevation. "
        "Reference vocabulary at Sonoma is environmental, not numeric. "
        "Use these names when relevant: 'the bridge' (T2 brake), "
        "'the K-wall bend' (T1 apex), 'the Carousel' (T6), "
        "'the slight crest' (T6 brake), 'the 300 board' (T7 brake), "
        "'the Toyota sign letters' (T10 visual), "
        "'Calamity Corner' (T11 hairpin), "
        "'the bump where the road widens left' (T11 brake — wait for "
        "the car to settle), 'the third tire stack' (T11 apex). "
        "\n"
        "STRATEGY: T3 is a give-away (sacrifice for T3a/T4); "
        "T5 is throwaway (preserve T6 entry); T6 punishes early throttle; "
        "T10 is fastest — most drivers brake when they only need a lift; "
        "T11 has no painted brake board — the bump is the reference. "
        "\n"
        "T-ROD VOICE (canonical pace-note phrasings, BMW M3 intermediate-driver "
        "session at Sonoma): "
        "'Distance is king' for long sweepers (T6, T7, T11 — cut the inside, "
        "do not open up to carry mph). "
        "'Be closer to the tire stacks' for T11. "
        "'Open up nine, straight shot to ten.' "
        "'Single apex, treat as double' for T7 (cut entry, rotate, hit "
        "second apex). "
        "'Just go 100' when the driver hesitates at 60% throttle "
        "(60→100% is only ~20 ft-lbs of torque). "
        "'Wait, you're not at the apex yet' to delay early throttle. "
        "'Roll the brake to the apex' (peak then taper, not square-wave; "
        "off-brake at maximum-grip mid-corner). "
        "'Trust the curb, it catches you' (Sonoma's serrated berms are "
        "banked in the driver's favour). "
        "'Cool-down means same line, slower.' "
        "M3-specific: boosted brake is feathery — focus on application "
        "before adding more inputs."
    ),
}


_PRE_BRIEF_SYSTEM_PROMPT = (
    "You are a professional race coach giving a PRE-SESSION BRIEF before "
    "the driver heads out. The driver is at Sonoma Raceway in a BMW M3, "
    "intermediate level. Goal of the brief: focus the driver's attention on "
    "their three chosen corners + today's specific conditions + one safety "
    "reminder. Keep it warm but tight — drivers are putting a helmet on, not "
    "studying. Use named landmarks ('the bridge', 'the bump', 'the Toyota "
    "sign letters'). Use canonical T-Rod phrasings where they fit.\n\n"
    "PEDAGOGY FOCUS (ADR-018, intermediate / HPDE / Time-Trial driver):\n"
    "- Frame the brief around TRANSITIONS, not corner identification: brake "
    "release shape, throttle pickup timing, dead-pedal avoidance.\n"
    "- 'Roll the brake to the apex' is the headline cue — repeat it.\n"
    "- If the driver has been over-driving lately, lead with calm: "
    "'smooth is fast, dial it back to 90 percent first lap'.\n"
    "- Do NOT prescribe brake markers — say 'taper your release', not 'brake at the 100 board'.\n\n"
    "End with the literal token <FOCUS> followed by a JSON list of exactly "
    "3 short actionable focus items. Total ~150 words."
)


_POST_SESSION_SYSTEM_PROMPT = (
    "You are a professional race engineer giving a POST-SESSION DEBRIEF. "
    "The driver just finished a session at Sonoma Raceway in a BMW M3, "
    "intermediate level. The user message contains structured session data: "
    "scorecard with per-corner A-F grades, time-loss decomposition per "
    "corner, top highlight moments, stat cards, slip-angle band + slip "
    "oscillations, EoB summary, consistency, and incidents. Use this data — "
    "DO NOT invent events that aren't in the data. Speak in T-Rod's "
    "canonical voice where it fits ('Distance is king', 'Just go 100', "
    "'Wait, you're not at the apex yet', 'Roll the brake to the apex'). "
    "Reference named Sonoma landmarks.\n\n"
    "STRUCTURE (ADR-018 — lead with a positive maneuver before any "
    "critique; intermediate drivers buy in faster when they hear what "
    "worked first):\n"
    "1) HEADLINE — one-paragraph assessment that OPENS with a validated "
    "positive moment from the data: best sector, the highest-scoring "
    "corner, or a specific highlight tagged 'good_*'. Name it ('your "
    "T10 entry on lap 4 was an A — that's the gold lap signal'). Even on "
    "a rough session, find one thing that worked.\n"
    "2) HIGHLIGHTS — one paragraph per highlight (≤3 total, lap N, what "
    "happened, what to do next time). Mix wins and lessons, but lead "
    "with at least one win.\n"
    "3) ONE BIG LEVER — paragraph identifying the single biggest lap-time "
    "opportunity (typically T10 or T11). Frame as 'next session' work, "
    "not as failure. If the slip-oscillation count is high (>2), this is "
    "where to say 'smooth is fast — dial it back to 90 percent first stint'.\n"
    "4) FOCUS — three items for next session, formatted as a JSON list "
    "after the literal token <NEXT_FOCUS>. Each focus item must be a "
    "transition-level cue (brake release, throttle pickup, dead-pedal "
    "elimination), NOT a brake-marker prescription.\n\n"
    "Total ~300 words."
)


_SYSTEM_PROMPTS_BY_MODE = {
    CoachMode.DURING_DRIVE: _BASE_SYSTEM_PROMPT,
    CoachMode.PRE_BRIEF:    _PRE_BRIEF_SYSTEM_PROMPT,
    CoachMode.POST_SESSION: _POST_SESSION_SYSTEM_PROMPT,
}

# Compact prompts for LLM backends with tight context caps (e.g. LocalLLM's
# default Gemma 4 cap is 256 input tokens). Triggered by env var
# `PITWALL_COMPACT_PROMPTS=1`. Sacrifices the rich T-Rod recipe + pedagogy
# bullets for fit, but keeps the contract (FOCUS list, emotion tag).
_COMPACT_PRE_BRIEF_SYSTEM_PROMPT = (
    "You are a race coach. Pre-session brief for a BMW M3 driver at Sonoma. "
    "Warm tone, ~80 words. Cover: today's focus corners, conditions, one "
    "safety note. End with <FOCUS> + a JSON list of 3 short cues."
)
_COMPACT_POST_SESSION_SYSTEM_PROMPT = (
    "You are a race engineer giving a post-session debrief for a BMW M3 "
    "driver at Sonoma. Use the structured user data — do NOT invent events. "
    "Structure: HEADLINE (1 paragraph, open with a positive), HIGHLIGHTS "
    "(up to 3, lead with a win), ONE BIG LEVER. End with <NEXT_FOCUS> + a "
    "JSON list of 3 transition-level cues. ~150 words total."
)
_COMPACT_SYSTEM_PROMPTS_BY_MODE = {
    CoachMode.DURING_DRIVE: _BASE_SYSTEM_PROMPT,
    CoachMode.PRE_BRIEF:    _COMPACT_PRE_BRIEF_SYSTEM_PROMPT,
    CoachMode.POST_SESSION: _COMPACT_POST_SESSION_SYSTEM_PROMPT,
}


_EMOTION_TAG_INSTRUCTION = (
    "At the START of your reply, emit exactly one tag in the form "
    "[EMOTION: <name>] where <name> is one of: "
    + ", ".join(sorted(VALID_EMOTIONS))
    + ". Then a single newline, then your normal coaching response. "
    "Do not emit the tag anywhere else in the reply."
)


def build_system_prompt(driver_level: str, track_name: str = "",
                        mode: CoachMode = CoachMode.DURING_DRIVE) -> str:
    """Compose the full system prompt for any LLM coach.

    Single source of truth used by LitertCoach (and any future cloud coach).
    Frontends never call this — they call the bridge.

    Set `PITWALL_COMPACT_PROMPTS=1` to use the compact variants (drops the
    rich T-Rod track lore + pedagogy bullets to fit tight LLM context caps,
    e.g. LocalLLM's default 256-token Gemma 4 cap).
    """
    import os
    compact = os.getenv("PITWALL_COMPACT_PROMPTS", "").strip() in ("1", "true", "yes")
    table = _COMPACT_SYSTEM_PROMPTS_BY_MODE if compact else _SYSTEM_PROMPTS_BY_MODE
    base = table.get(mode, _BASE_SYSTEM_PROMPT)
    parts = [base.strip()]
    if mode == CoachMode.DURING_DRIVE:
        parts.append(
            _LEVEL_SYSTEM_PROMPT.get(
                driver_level, _LEVEL_SYSTEM_PROMPT["intermediate"]
            ).strip()
        )
    # Track lore is heavy (~1500 chars for Sonoma) — skip in compact mode.
    if track_name and track_name in _TRACK_LORE and not compact:
        parts.append(_TRACK_LORE[track_name].strip())
    # Emotion-tag contract — LLM declares its mood for the avatar.
    # Compact mode skips it (the rule_coach adds neutral fallback).
    if not compact:
        parts.append(_EMOTION_TAG_INSTRUCTION)
    return "\n\n".join(parts)


def build_pre_brief_user_prompt(
    driver_id: str,
    today_iso: str,
    weather_phase: str,
    surface_state: str,
    markers_selected: list[str],
    weakest_recent_corner: Optional[str],
    biggest_recent_improvement: Optional[dict],
    danger_zones_today: list[str],
    goal: str = "personal best lap",
) -> str:
    """User prompt for PRE_BRIEF mode."""
    parts = [
        f"DRIVER: {driver_id}",
        f"DATE: {today_iso}",
        f"WEATHER PHASE: {weather_phase} ({surface_state})",
        f"GOAL: {goal}",
        f"FOCUS CORNERS THIS SESSION: {', '.join(markers_selected) or '(driver did not pick)'}",
    ]
    if weakest_recent_corner:
        parts.append(f"WEAKEST RECENT CORNER: {weakest_recent_corner}")
    if biggest_recent_improvement:
        parts.append(
            f"BIGGEST RECENT IMPROVEMENT: "
            f"{biggest_recent_improvement.get('corner')} "
            f"(score Δ {biggest_recent_improvement.get('delta_score', 0):+.2f})"
        )
    if danger_zones_today:
        parts.append(f"DANGER ZONES TO WATCH: {'; '.join(danger_zones_today)}")
    parts.append("Brief the driver now.")
    return "\n".join(parts)


def build_post_session_user_prompt(bundle: dict) -> str:
    """User prompt for POST_SESSION mode — feeds the analyzer bundle to the LLM.

    Keeps the prompt compact: scorecard + top highlights + stats + the
    handful of analytics the coach needs to talk about. Skips full friction
    samples / hustle map (those are for the frontend, not the LLM).
    """
    sc = bundle.get("scorecard") or {}
    hs = bundle.get("highlights") or []
    stats = bundle.get("stats") or {}
    eob = bundle.get("eob") or {}
    sb = bundle.get("slip_band") or {}
    cons = bundle.get("consistency") or {}
    osc = bundle.get("slip_oscillations") or []

    # Compact scorecard
    scorecard_lines = []
    for c in sc.get("corners", []):
        attrs = c.get("time_loss_attribution") or []
        biggest = (max(attrs, key=lambda a: a["seconds_lost"]) if attrs else None)
        scorecard_lines.append(
            f"  {c['corner']:<8} grade={c['grade']:<2} "
            f"Δt={c['delta_time_s']:+.2f}s "
            f"apex={c['apex_delta_kmh']:+.1f}kmh "
            f"exit={c['exit_delta_kmh']:+.1f}kmh "
            f"BP={c['brake_point_delta_m']:+.1f}m"
            + (f" cause={biggest['cause']}({biggest['seconds_lost']:.2f}s)"
               if biggest else "")
        )

    # ADR-018: surface the highlight reel — best corner score, best
    # highlight, and best lap delta — so the LLM has a concrete positive
    # to open with. Pre-extracted here to avoid the model fishing for it.
    corners = sc.get("corners") or []
    best_corner = max(
        corners, key=lambda c: c.get("score_pct", 0.0), default=None,
    ) if corners else None
    positive_highlight = next(
        (h for h in hs if str(h.get("kind", "")).startswith("good")
         or h.get("severity") == "positive"
         or "good" in str(h.get("kind", ""))),
        None,
    )
    highlight_reel_lines: list[str] = ["HIGHLIGHT REEL (lead the debrief with one of these):"]
    if best_corner:
        highlight_reel_lines.append(
            f"  best corner: {best_corner.get('corner')} "
            f"grade {best_corner.get('grade')} "
            f"({best_corner.get('score_pct', 0):.1%})"
        )
    if positive_highlight:
        highlight_reel_lines.append(
            f"  positive highlight: {positive_highlight.get('title', '?')} "
            f"— {positive_highlight.get('narrative_seed', '')}"
        )
    if not best_corner and not positive_highlight:
        # Even on a rough session we want SOMETHING positive — lap-time
        # progression often is. Use best vs prior-best lap as the floor.
        highlight_reel_lines.append(
            "  no clear highlight — open with raw effort or pace progression"
        )

    highlight_lines = []
    for h in hs[:5]:
        highlight_lines.append(
            f"  [{h['severity']}] {h['title']} — {h['narrative_seed']}"
        )

    parts = [
        f"SESSION: {sc.get('session_id', '?')}",
        f"LAPS: {sc.get('n_laps', 0)} — best {sc.get('best_lap_s', 0):.2f}s "
        f"vs gold {sc.get('gold_lap_s', 0):.2f}s "
        f"(Δ {sc.get('best_lap_s', 0) - sc.get('gold_lap_s', 0):+.2f}s)",
        f"SESSION GRADE: {sc.get('session_grade', '?')} "
        f"({sc.get('weighted_total_pct', 0):.1%})",
        "",
        "SCORECARD (best pass per corner):",
        *(scorecard_lines or ["  (no scorecard available)"]),
        "",
        *highlight_reel_lines,
        "",
        "TOP HIGHLIGHTS:",
        *(highlight_lines or ["  (no highlights detected)"]),
        "",
        f"STATS: top {stats.get('top_speed_kmh', '?')} km/h, "
        f"max {stats.get('max_combo_g', '?')} G, "
        f"max brake {stats.get('max_brake_bar', '?')} bar, "
        f"longest 100% throttle {stats.get('longest_full_throttle_s', '?')} s",
        f"SLIP-ANGLE BAND: {sb.get('dominant_band', '?')} — "
        f"{sb.get('interpretation', '')}",
        # ADR-018: lead with oscillation count when it's high — that's the
        # 'over-driving / ego' signal the debrief must address head-on.
        f"SLIP OSCILLATIONS: {len(osc)} ego-swing windows"
        + (f" (peak {max(o['crossings'] for o in osc)} band crossings)" if osc else ""),
        f"EOB: avg nothing-time {eob.get('average_nothing_time_s', 0):.2f}s, "
        f"worst at {eob.get('worst_corner', '—')}",
        f"CONSISTENCY: lap std {cons.get('lap_time_std', 0):.2f}s; "
        f"most variable corner: {(cons.get('most_variable_corner') or {}).get('corner', '—')}",
        "",
        "Generate the debrief now per the system instructions.",
    ]
    return "\n".join(parts)


_USER_PROMPT_TEMPLATE = (
    "UPCOMING: {corner} {direction} sev{severity} in {m_in} m, "
    "brake_zone {bz} m peaking {bar} bar, apex {apex} km/h, elev {elev} m.\n"
    "{landmark_hint}"
    "NOW: {speed} km/h, brake {brake}%, throttle {thr}%, gLat {glat:+.2f}.\n"
    "PEDAGOGY: {concept} — {tip}\n"
    "{tip_hint}"
    "Speak the pace note now."
)


def build_user_prompt(ctx) -> str:
    """Compose the per-frame user prompt. Reuses every CoachContext field
    including the marker labels populated by build_context().
    """
    landmark_hint = ""
    if ctx.next_brake_marker_label:
        landmark_hint = f"BRAKE LANDMARK: {ctx.next_brake_marker_label}\n"
    elif ctx.next_apex_marker_label:
        landmark_hint = f"APEX LANDMARK: {ctx.next_apex_marker_label}\n"
    tip_hint = f"COACHING TIP: {ctx.next_corner_tip}\n" if ctx.next_corner_tip else ""

    return _USER_PROMPT_TEMPLATE.format(
        corner=ctx.next_corner_nickname or ctx.next_corner_name or "none",
        direction=ctx.next_corner_direction or "-",
        severity=ctx.next_corner_severity,
        m_in=int(round(ctx.meters_to_entry)) if ctx.meters_to_entry < 999 else 999,
        bz=int(round(ctx.next_brake_zone_m)),
        bar=int(round(ctx.next_brake_peak_bar)),
        apex=int(round(ctx.next_apex_speed_kmh)),
        elev=int(round(ctx.next_elevation_change_m)),
        speed=int(round(ctx.speed_kmh)),
        brake=int(round(ctx.brake_pct)),
        thr=int(round(ctx.throttle_pct)),
        glat=ctx.g_lat,
        concept=ctx.bentley_concept or "look_ahead",
        tip=ctx.bentley_tip or "eyes far ahead",
        landmark_hint=landmark_hint,
        tip_hint=tip_hint,
    )


# ─── Templated fallbacks + response splitters (used when no LLM is loaded) ───


def _templated_pre_brief(*, driver_id: str, weather_phase: str,
                          surface_state: str, markers_selected: list[str],
                          weakest_recent_corner: Optional[str],
                          danger_zones_today: list[str]) -> tuple[str, list[str]]:
    parts = [
        f"# Pre-session brief — {driver_id} at Sonoma",
        f"_{weather_phase} — {surface_state}._",
    ]
    if markers_selected:
        parts.append(f"**Today's focus:** {', '.join(markers_selected)}.")
    if weakest_recent_corner:
        parts.append(f"Your weakest recent corner has been **{weakest_recent_corner}** — "
                     f"give it special attention.")
    if danger_zones_today:
        parts.append("**Danger zones today:**")
        for d in danger_zones_today:
            parts.append(f"- {d}")
    parts.append("Have a great session.")
    focus = list(markers_selected[:3]) if markers_selected else []
    return "\n\n".join(parts), focus


def _split_brief_narrative_and_focus(text: str) -> tuple[str, list[str]]:
    """Parse the <FOCUS>[...] tail off a PRE_BRIEF response."""
    if "<FOCUS>" in text:
        head, _, tail = text.partition("<FOCUS>")
        try:
            focus = json.loads(tail.strip())
            if isinstance(focus, list):
                return head.strip(), [str(x) for x in focus[:3]]
        except (json.JSONDecodeError, ValueError):
            # Bad JSON in <FOCUS> tail — drop to narrative-only.
            pass
    return text.strip(), []


def _split_debrief_narrative_and_focus(text: str) -> tuple[str, list[str]]:
    """Parse the <NEXT_FOCUS>[...] tail off a POST_SESSION response."""
    if "<NEXT_FOCUS>" in text:
        head, _, tail = text.partition("<NEXT_FOCUS>")
        try:
            focus = json.loads(tail.strip())
            if isinstance(focus, list):
                return head.strip(), [str(x) for x in focus[:3]]
        except (json.JSONDecodeError, ValueError):
            # Bad JSON in <NEXT_FOCUS> tail — drop to narrative-only.
            pass
    return text.strip(), []
