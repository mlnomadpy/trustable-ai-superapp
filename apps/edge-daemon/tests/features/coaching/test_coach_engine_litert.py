"""Live-model tests for LitertCoach.

These tests load the actual Gemma 4 E2B `.litertlm` from disk and run real
inference. They're heavy (each call is 0.5–10 s of CPU work) and require
both the `litert-lm` Python package AND the model file on disk.

When either is missing — typical on CI runners and on a fresh dev machine
before `litert-lm import` — every test in this file is skipped. The unit
tests in `test_coach_engine.py` cover the no-LLM fallback path, so green
CI is unaffected.

To enable locally:
    pip install litert-lm
    litert-lm import --from-huggingface-repo \\
        litert-community/gemma-4-E2B-it-litert-lm \\
        gemma-4-E2B-it.litertlm gemma-4-e2b
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "simulator"))

# Skip the whole module if litert-lm isn't importable.
pytest.importorskip("litert_lm", reason="litert-lm not installed")

from pitwall.features.coaching.coach_engine import LitertCoach   # noqa: E402  (after importorskip)


_MODEL_PATH = Path.home() / ".litert-lm" / "models" / "gemma-4-e2b" / "model.litertlm"


pytestmark = pytest.mark.skipif(
    not _MODEL_PATH.exists(),
    reason=(
        f"model file not present at {_MODEL_PATH}; "
        "run `litert-lm import --from-huggingface-repo "
        "litert-community/gemma-4-E2B-it-litert-lm "
        "gemma-4-E2B-it.litertlm gemma-4-e2b`"
    ),
)


# ── Module-scoped coach so we only load the 2.4 GB model once ─────────────


@pytest.fixture(scope="module")
def litert_coach():
    coach = LitertCoach(driver_level="intermediate")
    h = coach.health()
    if not h.get("loaded"):
        pytest.skip(f"LitertCoach failed to load: {h.get('error')}")
    yield coach
    coach.close()


# ── Tests ──────────────────────────────────────────────────────────────────


def test_health_reports_loaded(litert_coach):
    h = litert_coach.health()
    assert h["loaded"] is True
    assert h["error"] == ""
    assert h["fallback"] == "rule"


def test_propose_falls_through_to_rule_per_three_tier_scope(litert_coach):
    """In-drive coaching is intentionally NOT LLM-driven (ADR-016 follow-up).
    `propose()` must short-circuit to RuleCoach output regardless of
    whether the LLM is loaded."""
    from pitwall.features.coaching.coach_engine import CoachContext
    ctx = CoachContext(
        driver_level="intermediate", track_name="Sonoma Raceway",
        next_corner_name="Turn 11", next_corner_direction="L",
        next_corner_severity=5, meters_to_entry=140,
        next_brake_marker_label="the bump",
        next_corner_nickname="Calamity Corner",
        bentley_concept="late_apex",
    )
    msg = litert_coach.propose(ctx)
    # Either None (gating skipped it) or RuleCoach output (reason starts
    # with "rule:") — but never an LLM-flavoured "litert:..." reason.
    if msg is not None:
        assert not msg.reason.startswith("litert"), (
            "propose() must not call the LLM in-drive — "
            f"got reason={msg.reason}"
        )


def test_brief_returns_real_narrative(litert_coach):
    """End-to-end: pre-brief generates narrative + focus list + emotion."""
    from pitwall.features.coaching.coach_engine import VALID_EMOTIONS
    t0 = time.time()
    narrative, focus, emotion = litert_coach.brief(
        driver_id="taha", today_iso="2026-04-29",
        weather_phase="peak_grip", surface_state="dry",
        markers_selected=["the bump", "the K-wall bend"],
        weakest_recent_corner="Turn 7",
        danger_zones_today=["T11_dive_passing"],
        goal="break 1:48",
    )
    elapsed = time.time() - t0
    # Reasonable budget on Apple Silicon CPU; bumped if running on a slow
    # machine (CI runners are typically faster than 30 s for 200 tokens).
    assert elapsed < 30.0, f"brief() too slow: {elapsed:.1f}s"
    assert isinstance(narrative, str)
    assert len(narrative) > 50, f"narrative too short: {narrative!r}"
    assert isinstance(focus, list)
    assert emotion in VALID_EMOTIONS, f"unexpected emotion: {emotion!r}"


def test_debrief_returns_real_narrative(litert_coach):
    """End-to-end: post-session debrief over a stub bundle."""
    bundle = {
        "track":      "Sonoma Raceway",
        "session_id": "live-test",
        "scorecard": {
            "best_lap_s":   105.5,
            "lap_count":    8,
            "consistency_stddev_s": 0.6,
        },
        "highlights": [],
        "stats": {
            "avg_speed_kmh": 110.0,
            "max_combo_g":   1.7,
        },
    }
    from pitwall.features.coaching.coach_engine import VALID_EMOTIONS
    t0 = time.time()
    narrative, focus, emotion = litert_coach.debrief(bundle)
    elapsed = time.time() - t0
    assert elapsed < 30.0, f"debrief() too slow: {elapsed:.1f}s"
    assert isinstance(narrative, str)
    assert isinstance(focus, list)
    # Empty allowed only if the prompt was malformed; we should at least get
    # *some* output back from a healthy model.
    assert len(narrative) > 20, f"debrief narrative too short: {narrative!r}"
    assert emotion in VALID_EMOTIONS, f"unexpected emotion: {emotion!r}"


def test_repeat_calls_share_engine(litert_coach):
    """Two consecutive calls must reuse the same engine handle (no reload)."""
    eng_id_before = id(litert_coach._engine)
    litert_coach.brief(
        driver_id="x", today_iso="2026-04-29",
        weather_phase="peak_grip", surface_state="dry",
        markers_selected=[],
    )
    eng_id_after = id(litert_coach._engine)
    assert eng_id_before == eng_id_after, (
        "Engine handle changed between calls — model reload would be "
        "prohibitively expensive"
    )


def test_extract_assistant_text_handles_typed_parts():
    """Pure-Python check of the response shape parser — no LLM call needed."""
    from pitwall.features.coaching.coach_engine import _extract_assistant_text
    response = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Brake early."},
            {"type": "text", "text": "Apex tight."},
        ],
    }
    assert _extract_assistant_text(response) == "Brake early.\nApex tight."


def test_extract_assistant_text_handles_str_content():
    from pitwall.features.coaching.coach_engine import _extract_assistant_text
    assert _extract_assistant_text({"role": "assistant", "content": "hi"}) == "hi"


def test_extract_assistant_text_returns_empty_for_garbage():
    from pitwall.features.coaching.coach_engine import _extract_assistant_text
    assert _extract_assistant_text(None) == ""
    assert _extract_assistant_text(42) == ""
    assert _extract_assistant_text({}) == ""
