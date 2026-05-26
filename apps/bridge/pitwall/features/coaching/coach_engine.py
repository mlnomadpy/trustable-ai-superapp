"""
Coach Engine — LLM-agnostic verbal coaching layer.

Sits on top of the sonic model's continuous-tone cues. Where the sonic model
gives reflexive, sub-50ms feedback (pitch IS the delta), the coach engine
gives rally-style pace notes for the *upcoming* corner, debounced to fire
every few seconds on straights only.

Two implementations behind one interface:

  - RuleCoach       : zero-dependency templated phrases keyed by a small
                      pedagogical-vector matcher (Ross Bentley curriculum
                      distilled in project_pitwall_bentley_pedagogy.md).
  - LitertCoach     : on-device Gemma 4 E2B inference via LiteRT-LM
                      (MediaPipe Genai). Runs in-process on the Pixel 10
                      Tensor G5 NPU. Falls back to RuleCoach when the
                      model is unreachable or inference times out.

The arbiter (P3 safety / P2 technique / P1 strategy with cooldown + corner
suppression) lives at the call site in pitwall_app.SessionManager so this
file stays a pure "given context, produce zero or one CoachingMessage".

This module is now a back-compat re-export shim. The implementation lives in
focused per-concern siblings:

  - engine_base.py    — CoachEngine, CoachContext, CoachingMessage, CoachMode,
                        friction sink, emotion extraction
  - prompts.py        — system / user prompt builders + templated fallbacks
  - pedagogy.py       — Bentley concept matcher + capability-aware rule registry
  - rule_coach.py     — RuleCoach (zero-dep templated coach)
  - litert_coach.py   — LitertCoach (HTTP + in-process LiteRT-LM)
  - arbiter.py        — CoachArbiter (P1/P2/P3 cooldown gate)
"""

from __future__ import annotations

from typing import Optional

from pitwall.features.coaching.arbiter import CoachArbiter
from pitwall.features.coaching.engine_base import (
    CoachContext,
    CoachEngine,
    CoachingMessage,
    CoachMode,
    FrictionLogger,
    VALID_EMOTIONS,
    _emit_friction,
    _extract_emotion,
    extract_emotion,
    set_friction_logger,
)
from pitwall.features.coaching.litert_coach import (
    LitertCoach,
    TfliteCoach,
    _extract_assistant_text,
)
from pitwall.features.coaching.pedagogy import (
    COACH_RULES,
    CoachRule,
    coach_rule,
    evaluate_coach_gating,
    match_bentley_concept,
)
from pitwall.features.coaching.prompts import (
    _split_brief_narrative_and_focus,
    _split_debrief_narrative_and_focus,
    _templated_pre_brief,
    build_post_session_user_prompt,
    build_pre_brief_user_prompt,
    build_system_prompt,
    build_user_prompt,
)
from pitwall.features.coaching.rule_coach import RuleCoach


# ─── Helpers for callers ──────────────────────────────────────────────────────


def build_context(
    *,
    driver_level: str,
    track,                       # TrackMap
    frame,                       # TelemetryFrame
    next_corner,                 # CornerDef | None
    meters_to_entry: float,
    in_corner_obj,               # CornerDef | None
    past_apex: bool,
) -> CoachContext:
    """Pack the runtime state into a CoachContext + matched Bentley concept.

    Single helper used by both RuleCoach and LitertCoach so the gating logic
    is identical regardless of which engine is active.
    """
    # Marker lookup — only meaningful when there's an upcoming corner
    next_brake_marker = ""
    next_apex_marker = ""
    next_tip = ""
    next_nick = ""
    if next_corner is not None:
        next_tip = getattr(next_corner, "coaching_tip", "") or ""
        nicks = getattr(next_corner, "nicknames", []) or []
        next_nick = nicks[0] if nicks else ""
        # Pick the closest brake_ref marker on this corner
        markers = getattr(next_corner, "markers", []) or []
        if markers:
            brake_marks = [m for m in markers if m.kind == "brake_ref"]
            apex_marks = [m for m in markers if m.kind == "apex_ref"]
            if brake_marks:
                next_brake_marker = brake_marks[0].label
            if apex_marks:
                next_apex_marker = apex_marks[0].label

    ctx = CoachContext(
        driver_level=driver_level,
        track_name=track.name,
        next_corner_name=next_corner.name if next_corner else "",
        next_corner_direction=(next_corner.direction if next_corner else "")[:1].upper(),
        next_corner_severity=int(next_corner.severity) if next_corner else 0,
        meters_to_entry=float(meters_to_entry) if next_corner else 999.0,
        next_brake_zone_m=float(next_corner.brake_distance) if next_corner else 0.0,
        next_brake_peak_bar=float(next_corner.brake_pressure) if next_corner else 0.0,
        next_apex_speed_kmh=float(next_corner.apex_speed) * 3.6 if next_corner else 0.0,
        next_elevation_change_m=float(next_corner.elevation_change) if next_corner else 0.0,
        next_brake_marker_label=next_brake_marker,
        next_apex_marker_label=next_apex_marker,
        next_corner_tip=next_tip,
        next_corner_nickname=next_nick,
        speed_kmh=frame.speed * 3.6,
        brake_pct=min(frame.brake_pressure, 100.0),
        throttle_pct=float(frame.throttle),
        g_lat=float(frame.g_lat),
        g_long=float(frame.g_long),
        in_corner=in_corner_obj is not None,
        past_apex=past_apex,
    )
    concept, tip = match_bentley_concept(ctx)
    ctx.bentley_concept = concept
    ctx.bentley_tip = tip
    return ctx


def make_coach(
    kind: str = "auto",
    *,
    driver_level: str = "intermediate",
    litert_model_path: str = "",
    # Back-compat alias; older callers may pass `tflite_model_path=`
    tflite_model_path: str = "",
) -> CoachEngine:
    """Factory.

    kind="auto"     : prefer LitertCoach. Per ADR-022 LitertCoach now
                      defaults to HTTP transport against LocalLLM
                      (`http://localhost:8099/v1`) — overridable via
                      PITWALL_ADK_OPENAI_URL (legacy: PITWALL_LITERT_URL).
                      Set the env var to an empty string to fall back to
                      in-process litert-lm; if
                      neither path produces a loaded LLM, falls through
                      to RuleCoach.
    kind="litert"   : force LitertCoach (same HTTP-default behaviour as
                      "auto"). Internally falls back to templated output
                      if LocalLLM is unreachable AND no .litertlm is found.
    kind="rule"     : force the zero-dep templated coach.
    """
    model_path = litert_model_path or tflite_model_path
    if kind == "rule":
        return RuleCoach(driver_level=driver_level)
    # "tflite" kept as a deprecated alias for one cycle
    if kind in ("litert", "tflite"):
        return LitertCoach(model_path=model_path, driver_level=driver_level)
    if kind == "auto":
        try:
            engine = LitertCoach(model_path=model_path, driver_level=driver_level)
            if engine._llm is not None:
                return engine
        except Exception:
            pass
        return RuleCoach(driver_level=driver_level)
    raise ValueError(f"unknown coach kind: {kind!r}")


__all__ = [
    # Engine + types
    "CoachEngine",
    "CoachContext",
    "CoachingMessage",
    "CoachMode",
    "VALID_EMOTIONS",
    "FrictionLogger",
    # Coaches
    "RuleCoach",
    "LitertCoach",
    "TfliteCoach",
    # Factory / wiring
    "make_coach",
    "build_context",
    # Arbiter
    "CoachArbiter",
    # Friction sink
    "set_friction_logger",
    # Emotion
    "extract_emotion",
    "_extract_emotion",
    # Pedagogy
    "match_bentley_concept",
    "COACH_RULES",
    "CoachRule",
    "coach_rule",
    "evaluate_coach_gating",
    # Prompts
    "build_system_prompt",
    "build_user_prompt",
    "build_pre_brief_user_prompt",
    "build_post_session_user_prompt",
    # Internal helpers re-exported for tests
    "_templated_pre_brief",
    "_split_brief_narrative_and_focus",
    "_split_debrief_narrative_and_focus",
    "_extract_assistant_text",
    "_emit_friction",
]
