"""
Coach engine base — shared types, enums, friction sink, and emotion utility.

Leaf module of the coaching package: imports only from stdlib + pitwall._env,
never from sibling coaching modules. Every other coaching module (prompts,
pedagogy, rule_coach, litert_coach, arbiter) imports its shared vocabulary
from here.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Callable, Optional


# ─── ADR-018: LLM friction sink ───────────────────────────────────────────────
#
# `_friction_logger` is a single optional callback the bridge installs at boot
# via `set_friction_logger`. Every LitertCoach call funnels through `_generate`
# (or its `_log_friction` helper for the no-LLM templated fallback path), so
# this hook captures latency, truncation, fallbacks, and errors with one site
# of instrumentation. Keeping it at module scope means tests, replay harnesses,
# and the bridge can all observe friction without owning a coach instance.

FrictionLogger = Callable[[dict], None]
_friction_logger: Optional[FrictionLogger] = None


def set_friction_logger(fn: Optional[FrictionLogger]) -> None:
    """Install (or clear) the friction-record callback. Must be cheap and
    non-blocking — `_generate` calls it on the inference hot path."""
    global _friction_logger
    _friction_logger = fn


def _emit_friction(record: dict) -> None:
    """Best-effort fan-out to the registered logger. Swallows everything so a
    misbehaving sink never breaks an inference call."""
    fn = _friction_logger
    if fn is None:
        return
    try:
        fn(record)
    except Exception:
        pass


class CoachMode(enum.Enum):
    """Three operational modes per ADR-014 — same engine, different prompts."""
    DURING_DRIVE = "during_drive"   # one-line pace note per burst (existing)
    PRE_BRIEF    = "pre_brief"      # pre-session focus plan paragraph
    POST_SESSION = "post_session"   # full session debrief narrative


# ─── Data types ───────────────────────────────────────────────────────────────


@dataclass
class CoachContext:
    """Everything the coach needs to decide whether and what to say."""
    driver_level: str            # "beginner" | "intermediate" | "pro"
    track_name: str
    # Upcoming corner (may be None if no corner within lookahead)
    next_corner_name: str = ""
    next_corner_direction: str = ""    # "L" | "R" | ""
    next_corner_severity: int = 0      # 1-6
    meters_to_entry: float = 999.0
    next_brake_zone_m: float = 0.0
    next_brake_peak_bar: float = 0.0
    next_apex_speed_kmh: float = 0.0
    next_elevation_change_m: float = 0.0
    # Marker context — preferred over raw distance when present
    next_brake_marker_label: str = ""    # e.g. "the bridge", "the bump"
    next_apex_marker_label: str = ""     # e.g. "the K-wall bend"
    next_corner_tip: str = ""            # one-line Bentley-style tip per corner
    next_corner_nickname: str = ""       # e.g. "the Carousel", "Calamity Corner"
    # Current state
    speed_kmh: float = 0.0
    brake_pct: float = 0.0
    throttle_pct: float = 0.0
    g_lat: float = 0.0
    g_long: float = 0.0
    in_corner: bool = False
    past_apex: bool = False
    # Pedagogy
    bentley_concept: str = ""
    bentley_tip: str = ""


@dataclass
class CoachingMessage:
    """One verbal coaching line, ready for the arbiter."""
    text: str
    priority: int              # 1=strategy, 2=technique, 3=safety
    layer: str = "coach"
    reason: str = ""           # debug only — why we said this


# ─── Engine interface ─────────────────────────────────────────────────────────


class CoachEngine:
    """Base interface. Subclass and override propose()."""

    name: str = "base"

    def propose(self, ctx: CoachContext) -> Optional[CoachingMessage]:
        raise NotImplementedError


# ─── Emotion tag extraction (leaf utility used by prompts + litert_coach) ────


VALID_EMOTIONS = frozenset({
    "neutral", "thinking", "analyzing", "encouraging", "proud",
    "excited", "serious", "concerned", "disappointed", "intense",
    "relaxed", "tired",
})


# Anywhere-in-text matcher: the LLM is instructed to emit the tag at the START
# of its reply, but small models drift and sometimes place it mid- or end-of-
# text, or even repeat it. We accept the tag anywhere and strip ALL occurrences.
_EMOTION_TAG_RE = re.compile(r"\[\s*EMOTION\s*:\s*(\w+)\s*\]", re.IGNORECASE)


def extract_emotion(text: str) -> tuple[str, str]:
    """Strip every `[EMOTION: ...]` tag and return (cleaned_text, emotion).

    Searches anywhere in `text` (case-insensitive, whitespace-tolerant inside
    the brackets). Returns the first tag's value (lower-cased) and removes
    ALL occurrences defensively — the Gemma 4 E2B model is small enough that
    occasional tag drift / repetition is expected.

    Falls back to `neutral` when no tag is present, or when the tag's value
    isn't in VALID_EMOTIONS. Failing safely to neutral keeps the avatar
    rendering even when the LLM forgets.
    """
    if not text:
        return "", "neutral"
    m = _EMOTION_TAG_RE.search(text)
    if not m:
        return text.strip(), "neutral"
    emotion = m.group(1).lower()
    if emotion not in VALID_EMOTIONS:
        emotion = "neutral"
    cleaned = _EMOTION_TAG_RE.sub("", text).strip()
    return cleaned, emotion


# Private alias preserved for existing call sites inside this module.
_extract_emotion = extract_emotion
