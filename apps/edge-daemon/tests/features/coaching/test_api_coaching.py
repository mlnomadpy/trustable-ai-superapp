import pytest
import pitwall as br
from conftest import _start_session, _frames_to_payload
from pitwall.features.coaching.cue_renderer import estimate_tts_ms
from pitwall.features.session.laps import detect_laps, quantile
from pitwall.db import log_llm_friction
from pitwall.features.realtime.bp_realtime import cue_bus

# ─── ADR-015 Phase 4: coach gating ──────────────────────────────────────────


def test_coach_rules_registered_at_import():
    """Built-in rules should be present in COACH_RULES after import."""
    from pitwall.features.coaching.coach_engine import COACH_RULES
    ids = {r.id for r in COACH_RULES}
    assert "base_pace_note" in ids
    assert "oil_temp_warning_t11" in ids
    assert "tpms_drift" in ids


def test_coach_rule_decorator_dedupes_by_id():
    """Re-registering the same id should replace, not duplicate."""
    from pitwall.features.coaching.coach_engine import coach_rule, COACH_RULES

    n_before = len(COACH_RULES)

    @coach_rule(id="dedupe_test", description="v1", requires=["x"])
    def _v1(ctx, signals): pass

    @coach_rule(id="dedupe_test", description="v2", requires=["y"])
    def _v2(ctx, signals): pass

    matching = [r for r in COACH_RULES if r.id == "dedupe_test"]
    assert len(matching) == 1
    assert matching[0].description == "v2"
    # cleanup so other tests aren't affected
    COACH_RULES[:] = [r for r in COACH_RULES if r.id != "dedupe_test"]
    assert len(COACH_RULES) == n_before


def test_evaluate_coach_gating_marks_missing_signals():
    from pitwall.features.coaching.coach_engine import evaluate_coach_gating
    caps = {"speed_ms": {"mean_hz": 10.0, "useful": True},
            "distance_m": {"mean_hz": 10.0, "useful": True}}
    available, disabled = evaluate_coach_gating(caps)
    assert "base_pace_note" in available
    disabled_ids = {d["coach_id"] for d in disabled}
    assert "trail_brake_score" in disabled_ids
    assert "oil_temp_warning_t11" in disabled_ids


def test_evaluate_coach_gating_min_rate_failure():
    """Signal present but below min_useful_hz disables the rule."""
    from pitwall.features.coaching.coach_engine import evaluate_coach_gating
    caps = {
        "oil_temp_c": {"mean_hz": 0.5, "useful": False},   # 0.5 < 1.0
        "distance_m": {"mean_hz": 10.0, "useful": True},
    }
    _, disabled = evaluate_coach_gating(caps)
    oil = next((d for d in disabled if d["coach_id"] == "oil_temp_warning_t11"), None)
    assert oil is not None
    assert "rate" in oil["reason"].lower()


def test_capabilities_endpoint_advertises_coach_gating(client, make_frame_fn):
    """The /capabilities endpoint should populate coaches_available/disabled."""
    br.seed_signal_registry()
    sid = _start_session(client)
    frames = [make_frame_fn(t=1000.0 + i * 0.1, distance=i * 5.0) for i in range(50)]
    client.post(f"/session/{sid}/frames",
                json={"frames": _frames_to_payload(frames)})
    br._compute_capabilities(sid)

    r = client.get(f"/session/{sid}/capabilities")
    assert r.status_code == 200
    body = r.get_json()
    # Wide-only session should at least enable base_pace_note + trail_brake_score
    # (all signals are wide canonicals).
    assert "base_pace_note" in body["coaches_available"]
    assert "trail_brake_score" in body["coaches_available"]
    # And disable ones requiring tall-store signals.
    disabled_ids = {d["coach_id"] for d in body["coaches_disabled"]}
    assert "oil_temp_warning_t11" in disabled_ids
    assert "tpms_drift" in disabled_ids
    # Each disabled entry has a reason
    for d in body["coaches_disabled"]:
        assert "reason" in d



# ─── ADR-018: LLM friction sink + diagnostics endpoint ──────────────────────

def _seed_friction_rows(rows: list[dict]) -> None:
    """Helper — write fake llm_friction rows so the diagnostics endpoint has
    something to aggregate. Uses bridge's own writer so schema stays canonical."""
    for r in rows:
        log_llm_friction(r)


def test_diagnostics_llm_friction_empty_returns_zero_aggregates(client):
    r = client.get("/diagnostics/llm_friction")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 0
    assert body["rows"] == []
    assert body["by_role"] == []
    assert body["fallback_rate"] == 0.0


def test_diagnostics_llm_friction_logs_and_aggregates(client):
    _seed_friction_rows([
        {"session_id": "s1", "role": "brief", "mode": "pre_brief",
         "backend": "cpu", "prompt_chars": 1200, "completion_chars": 600,
         "latency_ms": 7000.0, "truncated": False, "fell_back": False,
         "error": "", "emotion": "encouraging"},
        {"session_id": "s1", "role": "brief", "mode": "pre_brief",
         "backend": "cpu", "prompt_chars": 1100, "completion_chars": 0,
         "latency_ms": 0.0, "truncated": False, "fell_back": True,
         "error": "engine_not_loaded", "emotion": "neutral"},
        {"session_id": "s1", "role": "debrief", "mode": "post_session",
         "backend": "cpu", "prompt_chars": 3000, "completion_chars": 1500,
         "latency_ms": 11000.0, "truncated": True, "fell_back": False,
         "error": "", "emotion": "serious"},
    ])
    r = client.get("/diagnostics/llm_friction")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 3
    assert len(body["rows"]) == 3
    # 1 of 3 fell back, 1 of 3 truncated
    assert abs(body["fallback_rate"] - 1/3) < 1e-6
    assert abs(body["truncation_rate"] - 1/3) < 1e-6
    # Per-role aggregation
    roles = {r["role"]: r for r in body["by_role"]}
    assert roles["brief"]["count"] == 2
    assert roles["debrief"]["count"] == 1
    assert abs(roles["brief"]["fallback_rate"] - 0.5) < 1e-6


def test_diagnostics_llm_friction_filters_by_session(client):
    _seed_friction_rows([
        {"session_id": "s1", "role": "brief", "fell_back": False,
         "latency_ms": 5000, "prompt_chars": 100, "completion_chars": 50,
         "backend": "cpu", "mode": "pre_brief"},
        {"session_id": "s2", "role": "brief", "fell_back": True,
         "latency_ms": 0, "prompt_chars": 100, "completion_chars": 0,
         "backend": "cpu", "mode": "pre_brief"},
    ])
    r = client.get("/diagnostics/llm_friction?session_id=s1")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1
    assert body["rows"][0]["session_id"] == "s1"
    assert body["fallback_rate"] == 0.0


def test_diagnostics_llm_friction_filters_by_role(client):
    _seed_friction_rows([
        {"session_id": "s1", "role": "brief", "fell_back": False,
         "latency_ms": 5000, "prompt_chars": 100, "completion_chars": 50,
         "backend": "cpu", "mode": "pre_brief"},
        {"session_id": "s1", "role": "debrief", "fell_back": False,
         "latency_ms": 9000, "prompt_chars": 200, "completion_chars": 800,
         "backend": "cpu", "mode": "post_session"},
    ])
    r = client.get("/diagnostics/llm_friction?role=debrief")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1
    assert body["rows"][0]["role"] == "debrief"


def test_estimate_tts_ms_floors_short_phrases():
    # Single safety word still ducks the full 800 ms minimum.
    assert estimate_tts_ms("Brake!") == 800


def test_estimate_tts_ms_scales_with_word_count():
    # 11 words × 150 ms = 1650 ms, above the 800 ms floor.
    text = "Wait for the bump then trail to the third tire stack."
    assert text.split() == ["Wait", "for", "the", "bump", "then", "trail",
                            "to", "the", "third", "tire", "stack."]
    assert estimate_tts_ms(text) == 11 * 150


def test_estimate_tts_ms_zero_for_empty():
    assert estimate_tts_ms("") == 0
    # Whitespace-only hits the floor — split() returns [] but max(1, 0) keeps
    # word count at 1 so the duck still engages for the safe minimum.
    assert estimate_tts_ms("   ") == 800


def test_analyze_publishes_cue_with_expected_tts_ms(client, monkeypatch):
    """Audio-ducker contract: every /analyze cue carries the expected_tts_ms
    hint so the PWA can hold the tactical-tone duck for the right window."""
    captured: list[dict] = []
    real_publish = cue_bus.publish
    def _spy(sid, event):
        captured.append({"sid": sid, **event})
        return real_publish(sid, event)
    monkeypatch.setattr(cue_bus, "publish", _spy)

    burst = {
        "session_id": "ducker-sess", "burst_id": 1,
        "avg_speed_kmh": 90.0, "max_combo_g": 1.0,
        "max_lateral_g": 0.5, "max_long_g": -0.3,
        "max_brake_bar": 12.0, "avg_throttle_pct": 50.0,
        "avg_steering_deg": 5.0, "coast_frames": 0,
        "trail_brake_frames": 0, "frame_count": 50,
        "corners_visited": [], "distance_m": 800.0,
        "in_corner": False, "past_apex": False,
    }
    r = client.post("/analyze", json=burst)
    assert r.status_code == 200
    assert len(captured) == 1
    cue = captured[0]
    assert "expected_tts_ms" in cue
    # Must be either 0 (no coaching text) or floored at 800.
    assert cue["expected_tts_ms"] in (0,) or cue["expected_tts_ms"] >= 800


def test_diagnostics_llm_friction_respects_limit(client):
    _seed_friction_rows([
        {"session_id": f"s{i}", "role": "brief", "fell_back": False,
         "latency_ms": 1000.0 * i, "prompt_chars": 100, "completion_chars": 50,
         "backend": "cpu", "mode": "pre_brief"}
        for i in range(1, 6)
    ])
    r = client.get("/diagnostics/llm_friction?limit=2")
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["rows"]) == 2
    # count is the unfiltered total; limit only caps `rows`
    assert body["count"] == 5