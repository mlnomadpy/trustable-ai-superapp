"""
Unit tests for the ADK paddock backend (see ADR-019–024).

Two layers:

1. **Helpers layer** — pure-Python: regex router, SQL allowlist, trace deque,
   corner bounds loader, bridge endpoints with stubbed `run_adk`.
2. **ADK layer** — reloads `adk_agents` and exercises the real Runner /
   PitwallTracingPlugin / session service with a stubbed model. `google-adk`
   and `litellm` are base deps (ADR-024), so these always run.

The ADK layer locks the audit fixes:
  - `Runner` is invoked (not the broken `BaseAgent.run()`)
  - `PitwallTracingPlugin` keys timestamps per agent (no ParallelAgent race)
  - `get_pending_traces(adk_session_id)` filters by session
  - `reset_driver_session` calls `delete_session` on the in-memory store
  - sole transport is `LiteLlm` dialling LocalLLM
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


# ════════════════════════════════════════════════════════════════════════════
# 1. No-ADK layer — pure helpers
# ════════════════════════════════════════════════════════════════════════════


# ─── adk_tools.query_pitwall_db: SQL allowlist + LIMIT wrap ─────────────────


def test_query_rejects_destructive_statements():
    import pitwall.adk_tools as adk_tools
    for stmt in [
        "DELETE FROM laps",
        "INSERT INTO laps VALUES (1)",
        "DROP TABLE laps",
        "ATTACH 'evil.db'",
        "UPDATE laps SET lap_time_s = 0",
    ]:
        result = adk_tools.query_pitwall_db(stmt)
        assert result and "error" in result[0], f"should reject: {stmt}"


def test_query_allows_select_with_pragma_describe():
    import pitwall.adk_tools as adk_tools
    # SELECT works
    assert adk_tools.query_pitwall_db("SELECT 1") == [{"1": 1}]
    # WITH CTE works
    assert adk_tools.query_pitwall_db("WITH x AS (SELECT 1 AS a) SELECT * FROM x") == [{"a": 1}]
    # PRAGMA works (DuckDB-specific)
    pragmas = adk_tools.query_pitwall_db("PRAGMA version")
    assert pragmas and "error" not in pragmas[0]


def test_query_subquery_limit_does_not_escape_outer_cap():
    """A LIMIT 1 in a subquery must not satisfy the outer 500-row cap.

    Audit issue: the old `if "LIMIT" not in stripped` check was satisfied by
    the inner LIMIT, so a query with no outer limit could return unbounded
    rows. New form wraps in `SELECT * FROM (...) LIMIT 500`.
    """
    import pitwall.adk_tools as adk_tools, re
    # We can't easily produce > 500 rows from the test DB, so verify the
    # wrapping behaviour by inspecting that a top-level-LIMIT query is NOT
    # double-wrapped while a subquery-only LIMIT IS wrapped.
    src = Path(adk_tools.__file__).read_text()
    assert "_TOP_LEVEL_LIMIT_RE" in src
    assert "FROM ({stripped}) AS _capped LIMIT 500" in src
    # Also verify the regex matches genuine top-level LIMITs.
    pat = adk_tools._TOP_LEVEL_LIMIT_RE
    assert pat.search("SELECT * FROM x LIMIT 10")
    assert pat.search("SELECT * FROM x LIMIT 10 OFFSET 5")
    assert not pat.search("SELECT * FROM (SELECT 1 LIMIT 1) AS s")


def test_query_handles_empty_input():
    import pitwall.adk_tools as adk_tools
    assert adk_tools.query_pitwall_db("")[0]["error"] == "Empty SQL"
    assert adk_tools.query_pitwall_db("   ;  ")[0]["error"] == "Empty SQL"


# ─── adk_tools._load_corner_bounds: canonical Sonoma JSON source ─────────────


def test_corner_bounds_sourced_from_sonoma_json():
    """Regression for hardcoded CORNER_BOUNDS drift.

    The audit flagged the local table for drifting from sonoma.json's
    corners[]. After the fix, _load_corner_bounds() returns the JSON's
    entry/exit distances. Turn 6 in the JSON is (1294, 1418) — narrower
    than the old hardcoded (1050, 1450). If the loader regresses to the
    fallback we'd see the old wide window again.
    """
    import pitwall.adk_tools as adk_tools
    # Bust the cache so we re-read the JSON.
    adk_tools._corner_bounds_cache = None
    bounds = adk_tools._load_corner_bounds()
    assert "Turn 6" in bounds
    start, end = bounds["Turn 6"]
    # Canonical JSON: 1294 / 1418. Fallback: 1050 / 1450.
    # If we ever return the fallback the test fails loudly.
    assert start == pytest.approx(1294.0, abs=1.0)
    assert end == pytest.approx(1418.0, abs=1.0)


def test_corner_bounds_falls_back_when_json_missing(monkeypatch, tmp_path):
    import pitwall.adk_tools as adk_tools
    monkeypatch.setattr(adk_tools, "_corner_bounds_cache", None)
    monkeypatch.setattr(adk_tools, "_SIM_DIR", str(tmp_path))
    # Also break the data/tracks path by pointing TRACK_JSON_RELATIVE elsewhere.
    import pitwall.features.track.sonoma as sonoma
    monkeypatch.setattr(sonoma, "TRACK_JSON_RELATIVE", "no/such/path.json")
    bounds = adk_tools._load_corner_bounds()
    # With no JSON reachable, we get the fallback table. Turn 6 in the
    # fallback is (1050, 1450).
    assert bounds["Turn 6"] == (1050, 1450)


# ─── adk_agents._classify_intent: regex router ─────────────────────────────


def test_intent_classifier_whole_flow_beats_corner():
    """Audit fix 2026-05-12: whole-flow intents (brief / debrief / voice_script)
    are matched BEFORE the corner pattern so 'brief me on T6' routes to the
    BriefPipeline, not CornerCoachAgent. The earlier behaviour treated any
    mention of a corner as terminal — which broke briefs/debriefs/voice
    scripts that happened to name a corner.
    """
    import pitwall.features.coaching.adk_agents as adk_agents
    classify = adk_agents._classify_intent
    # Whole-flow intents win when they appear alongside a corner reference.
    assert classify("brief me on T6") == "brief"
    assert classify("debrief at Turn 5") == "debrief"
    assert classify("voice script for T3") == "voice_script"
    # Pure brief / debrief / voice still routes correctly.
    assert classify("brief me before I go out") == "brief"
    assert classify("debrief the session") == "debrief"
    assert classify("generate cue scripts") == "voice_script"
    # A query that names a corner WITHOUT a whole-flow keyword still goes to corner.
    assert classify("review my T11 line") == "corner"
    assert classify("how am I doing at the Carousel") == "corner"


def test_intent_classifier_mental_map_covers_consistency():
    """Audit fix 2026-05-12: the mental_map pattern was too narrow, missing
    'consistency' (noun), 'repeatability', and 'stable'. Widening this is
    important because those are the natural phrasings drivers reach for."""
    import pitwall.features.coaching.adk_agents as adk_agents
    classify = adk_agents._classify_intent
    for phrase in (
        "how's my consistency?",
        "consistency through corners",
        "what's my repeatability score",
        "where am I most variance",
        "show my mental map",
        "I'm inconsistent today",
        "am I stable lap-to-lap",
    ):
        assert classify(phrase) == "mental_map", \
            f"phrase {phrase!r} should route to mental_map, got {classify(phrase)!r}"
    # When the query explicitly names a corner, corner-specific routing wins
    # — the CornerCoachAgent can still answer consistency questions per corner.
    assert classify("am I repeatable at T10?") == "corner"
    assert classify("how stable am I through the Carousel") == "corner"


def test_intent_classifier_word_boundaries():
    import pitwall.features.coaching.adk_agents as adk_agents
    classify = adk_agents._classify_intent
    # Used to be substring-based: " t6" only matched with leading space.
    assert classify("T6 was scary") == "corner"
    assert classify("my Carousel time was off") == "corner"
    # 'i have' used to greedy-match session_plan; now needs 'i have N laps'
    assert classify("I have a question about brakes") == "telemetry"
    assert classify("I have 8 laps available") == "session_plan"


def test_intent_classifier_falls_back_to_telemetry():
    import pitwall.features.coaching.adk_agents as adk_agents
    classify = adk_agents._classify_intent
    assert classify("show me the data") == "telemetry"
    assert classify("") == "telemetry"
    assert classify(None) == "telemetry"


def test_intent_classifier_recognises_meta_questions():
    import pitwall.features.coaching.adk_agents as adk_agents
    classify = adk_agents._classify_intent
    assert classify("which agent is slowest right now?") == "agent_meta"
    assert classify("show agent latency for the last hour") == "agent_meta"
    # Generic 'tool call' shouldn't false-positive
    assert classify("what's the brake/throttle tool call sequence at T11?") == "corner"


# ─── adk_agents.get_pending_traces: filter by session ──────────────────────


def test_pending_traces_filter_by_session():
    """Audit issue #3: concurrent Flask requests must not steal each other's
    traces. The drain accepts an adk_session_id and only consumes matching
    rows; non-matching rows stay in the deque for their owner to drain.
    """
    import pitwall.features.coaching.adk_agents as adk_agents
    # Module-level deque, always defined.
    adk_agents._pending_traces.clear()
    adk_agents._pending_traces.append({"trace_id": "A", "agent_name": "x",
                                       "event_type": "agent", "detail": "",
                                       "latency_ms": 1.0, "success": True})
    adk_agents._pending_traces.append({"trace_id": "B", "agent_name": "y",
                                       "event_type": "agent", "detail": "",
                                       "latency_ms": 2.0, "success": True})
    adk_agents._pending_traces.append({"trace_id": "A", "agent_name": "z",
                                       "event_type": "tool", "detail": "t",
                                       "latency_ms": None, "success": True})

    out_a = adk_agents.get_pending_traces(adk_session_id="A")
    assert len(out_a) == 2
    assert {row["agent_name"] for row in out_a} == {"x", "z"}
    # B's row should still be in the buffer.
    assert len(adk_agents._pending_traces) == 1
    assert adk_agents._pending_traces[0]["trace_id"] == "B"

    # Default drain (no filter) consumes everything left.
    out_all = adk_agents.get_pending_traces()
    assert len(out_all) == 1
    assert out_all[0]["trace_id"] == "B"
    assert len(adk_agents._pending_traces) == 0


def test_pending_traces_concurrent_drains_do_not_collide():
    """Two threads each draining their own session must not see each other's rows."""
    import pitwall.features.coaching.adk_agents as adk_agents
    adk_agents._pending_traces.clear()
    for i in range(50):
        adk_agents._pending_traces.append({
            "trace_id": "A" if i % 2 == 0 else "B",
            "agent_name": f"a{i}", "event_type": "agent",
            "detail": "", "latency_ms": float(i), "success": True,
        })

    results: dict[str, list] = {}
    def drain(sid):
        results[sid] = adk_agents.get_pending_traces(adk_session_id=sid)

    t1 = threading.Thread(target=drain, args=("A",))
    t2 = threading.Thread(target=drain, args=("B",))
    t1.start(); t2.start(); t1.join(); t2.join()

    a_ids = {r["agent_name"] for r in results["A"]}
    b_ids = {r["agent_name"] for r in results["B"]}
    assert a_ids.isdisjoint(b_ids)
    assert len(a_ids) == 25 and len(b_ids) == 25
    assert len(adk_agents._pending_traces) == 0


# ─── Bridge: no-ADK responses ──────────────────────────────────────────────


@pytest.fixture
def bridge_app(monkeypatch, tmp_path):
    """Flask test client over pitwall_bridge with a clean tmp DuckDB."""
    db = tmp_path / "test.duckdb"
    monkeypatch.setenv("PITWALL_DB", str(db))
    import importlib
    import pitwall
    importlib.reload(pitwall)
    pitwall.state.db_path = str(db)
    
    # We return a namespace mimicking the old bridge so tests don't break
    class MockBridge:
        def __init__(self):
            self.app = pitwall.create_app()
            self.app.config["TESTING"] = True
            
        @property
        def _adk_agent_registry(self):
            return pitwall.state.adk_agent_registry
            
        @_adk_agent_registry.setter
        def _adk_agent_registry(self, value):
            pitwall.state.adk_agent_registry = value

        # `bp_coaching` did `from … import run_adk, stream_adk, …` at module
        # load, so the live binding endpoints call is `bp_coaching.run_adk`,
        # not `adk_agents.run_adk`. Patching the source module would leave the
        # blueprint's stale reference in place. Target the importing module.
        @property
        def _run_adk(self):
            return pitwall.features.coaching.bp_coaching.run_adk

        @_run_adk.setter
        def _run_adk(self, value):
            pitwall.features.coaching.bp_coaching.run_adk = value

        @property
        def _drain_adk_traces(self):
            return pitwall.features.coaching.bp_coaching._drain_adk_traces

        @_drain_adk_traces.setter
        def _drain_adk_traces(self, value):
            pitwall.features.coaching.bp_coaching._drain_adk_traces = value

        @property
        def _stream_adk(self):
            return pitwall.features.coaching.bp_coaching.stream_adk

        @_stream_adk.setter
        def _stream_adk(self, value):
            pitwall.features.coaching.bp_coaching.stream_adk = value
            
    return MockBridge()


def test_coach_agents_lists_registry(bridge_app, monkeypatch):
    monkeypatch.setattr(bridge_app, "_adk_agent_registry",
                        [{"name": "Demo", "role": "test"}])
    client = bridge_app.app.test_client()
    resp = client.get("/coach/agents")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["available"] is True
    assert body["agents"][0]["name"] == "Demo"


def test_coach_ask_validates_question_present(bridge_app, monkeypatch):
    """Empty question must be rejected before reaching the model."""
    # Stub _run_adk so a regression that bypasses validation fails loudly.
    def _should_not_be_called(*a, **kw):
        raise AssertionError("_run_adk called for empty question")
    monkeypatch.setattr(bridge_app, "_run_adk", _should_not_be_called)
    client = bridge_app.app.test_client()
    resp = client.post("/coach/ask", json={"driver_id": "x", "question": "  "})
    assert resp.status_code == 400


def test_coach_ask_uses_intent_override(bridge_app, monkeypatch):
    """Explicit `intent` body field must reach the orchestrator via
    `state_overrides["temp:intent_override"]` (not as `[intent_override:X]`
    text embedded in the prompt — which the orchestrator never reads).
    Audit fix 2026-05-13: the previous version asserted the broken
    behaviour and let the bug ship.
    """
    captured = {}
    def fake_run(prompt, user_id="driver", state_overrides=None):
        captured["prompt"] = prompt
        captured["user_id"] = user_id
        captured["state_overrides"] = state_overrides
        return ("ok answer [EMOTION:focused]", "fake-sid")
    monkeypatch.setattr(bridge_app, "_run_adk", fake_run)
    monkeypatch.setattr(bridge_app, "_drain_adk_traces", lambda **kw: None)
    client = bridge_app.app.test_client()
    resp = client.post("/coach/ask", json={
        "driver_id": "u1", "session_id": "s1",
        "question": "anything",
        "intent": "corner",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["answer"] == "ok answer"
    assert body["emotion"] == "focused"
    # The override flows through state, not the prompt text. Assert both.
    assert captured["state_overrides"] == {"temp:intent_override": "corner"}
    assert "[intent_override:" not in captured["prompt"], \
        "intent must NOT leak into the prompt text — orchestrator reads session.state"
    assert captured["user_id"] == "u1"


def test_coach_ask_no_intent_passes_no_overrides(bridge_app, monkeypatch):
    """When the request body omits `intent`, the bridge must NOT pass an
    empty/dict state_overrides — it should pass None so the orchestrator's
    fallback regex routing is exercised exactly as before."""
    captured = {}
    def fake_run(prompt, user_id="driver", state_overrides=None):
        captured["state_overrides"] = state_overrides
        return ("ok [EMOTION:neutral]", "sid")
    monkeypatch.setattr(bridge_app, "_run_adk", fake_run)
    monkeypatch.setattr(bridge_app, "_drain_adk_traces", lambda **kw: None)
    client = bridge_app.app.test_client()
    resp = client.post("/coach/ask", json={
        "driver_id": "u1", "session_id": "s1",
        "question": "what about T6",
    })
    assert resp.status_code == 200
    assert captured["state_overrides"] is None


def test_coach_ask_drain_filters_by_adk_session(bridge_app, monkeypatch):
    """Regression: _drain_adk_traces must receive the ADK session id from
    _run_adk so concurrent requests do not steal each other's traces.
    """
    drained = {}
    def fake_run(prompt, user_id="driver", state_overrides=None):
        return ("answer [EMOTION:neutral]", "adk-sid-42")
    def fake_drain(adk_session_id=None, pitwall_sid=""):
        drained["adk_session_id"] = adk_session_id
        drained["pitwall_sid"] = pitwall_sid
    monkeypatch.setattr(bridge_app, "_run_adk", fake_run)
    monkeypatch.setattr(bridge_app, "_drain_adk_traces", fake_drain)
    client = bridge_app.app.test_client()
    resp = client.post("/coach/ask", json={
        "driver_id": "u", "session_id": "p-sid", "question": "what?"})
    assert resp.status_code == 200
    assert drained == {"adk_session_id": "adk-sid-42", "pitwall_sid": "p-sid"}


def test_coach_ask_stream_emits_sse_chunks(bridge_app, monkeypatch):
    """The /coach/ask/stream endpoint should emit `data:` lines per chunk
    plus a terminal {"done": true, ...} payload."""
    monkeypatch.setattr(bridge_app, "_stream_adk",
                        lambda prompt, user_id="driver", state_overrides=None: iter([
                            "Hello ", "world. ", "[EMOTION:encouraging]",
                        ]))
    client = bridge_app.app.test_client()
    resp = client.post("/coach/ask/stream",
                       json={"driver_id": "u", "session_id": "s",
                             "question": "anything"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Each chunk arrives as `data: {...}\n\n`
    assert "Hello " in body
    assert "world." in body
    # Final done payload contains the cleaned answer + emotion.
    assert '"done": true' in body
    assert '"emotion": "encouraging"' in body


# ════════════════════════════════════════════════════════════════════════════
# 2. ADK layer — exercises actual google-adk wiring with a stub model
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def adk_module():
    import importlib
    import pitwall.features.coaching.adk_agents as adk_agents
    importlib.reload(adk_agents)
    return adk_agents


def test_adk_module_loads_full_topology(adk_module):
    assert adk_module.coach_orchestrator is not None
    # ADR-026: phase-2 expansion added 6 specialists (Tire / Handling /
    # EngineHealth / Traction / InputQuality / Safety) on top of the
    # original 17.
    assert len(adk_module.AGENT_REGISTRY) == 23
    names = {a["name"] for a in adk_module.AGENT_REGISTRY}
    for required in [
        "TelemetryAgent", "AgentMetaAgent", "VoiceScriptAgent",
        "TireManagerAgent", "HandlingBalanceAgent", "EngineHealthAgent",
        "TractionAgent", "InputQualityAgent", "SafetyMonitorAgent",
    ]:
        assert required in names, f"missing agent {required!r}"


def test_adk_model_is_local_llm(adk_module):
    """Sole transport: LiteLlm dialling LocalLLM (ADR-024).

    Locks the consolidation — if anyone reintroduces `Gemini(base_url=...)`
    or an in-process `LitertLmModel` branch, this test fails.
    """
    from google.adk.models.lite_llm import LiteLlm
    assert isinstance(adk_module._model, LiteLlm)
    assert adk_module._model.model.startswith("openai/"), \
        "model id must carry the openai/ provider prefix for litellm routing"


def test_adk_pipelines_use_distinct_pedagogy_instances(adk_module):
    """Audit S-tier: ADR-021 created _narrative_brief / _narrative_debrief but
    still shared pedagogy_agent across pipelines. After the fix, each pipeline
    has its own instance to satisfy ADK's single-parent invariant."""
    brief_pedagogy = adk_module.brief_pipeline.sub_agents[0]
    debrief_data = adk_module.debrief_pipeline.sub_agents[0]
    debrief_pedagogy = next(a for a in debrief_data.sub_agents
                            if a.name.startswith("PedagogyAgentDebrief"))
    assert brief_pedagogy is not debrief_pedagogy
    assert brief_pedagogy is not adk_module.pedagogy_agent
    assert debrief_pedagogy is not adk_module.pedagogy_agent


def test_adk_run_returns_tuple_with_session_id(adk_module, monkeypatch):
    """run_adk() must return (text, session_id). A regression to a bare
    string would re-break trace filtering in the bridge."""
    # Stub _run_adk_async so we don't need a real model/server.
    async def fake(prompt, user_id, state_overrides=None):
        return ("hello world [EMOTION:neutral]", "fake-sid-xyz")
    monkeypatch.setattr(adk_module, "_run_adk_async", fake)
    out = adk_module.run_adk("hi", user_id="u")
    assert isinstance(out, tuple) and len(out) == 2
    text, sid = out
    assert "hello world" in text
    assert sid == "fake-sid-xyz"


def test_adk_run_timeout_raises(adk_module, monkeypatch):
    """A wedged lit serve must not block Flask forever."""
    import asyncio
    async def fake(prompt, user_id, state_overrides=None):
        await asyncio.sleep(5)
        return ("never", "x")
    monkeypatch.setattr(adk_module, "_run_adk_async", fake)
    monkeypatch.setattr(adk_module, "_RUN_TIMEOUT_S", 0.5)
    with pytest.raises(RuntimeError, match="timeout"):
        adk_module.run_adk("hi", user_id="u")


def test_adk_session_rotation_at_char_budget(adk_module, monkeypatch):
    """Char-budget rotation: when cumulative chars exceed the budget,
    the next call gets a fresh session id.

    The rotation check fires at the START of _get_or_create_session, so we
    need to push chars over the budget THEN observe call N+1 rotating.
    """
    monkeypatch.setattr(adk_module, "_SESSION_CHAR_BUDGET", 50)
    adk_module._driver_sessions.clear()
    adk_module._session_chars.clear()

    async def fake(prompt, user_id, state_overrides=None):
        sess = await adk_module._get_or_create_session(user_id)
        # Burn 60 chars per call → over the 50-char budget after one call.
        with adk_module._driver_sessions_lock:
            adk_module._session_chars[user_id] = (
                adk_module._session_chars.get(user_id, 0) + 60)
        return ("ok", sess.id)
    monkeypatch.setattr(adk_module, "_run_adk_async", fake)

    _, sid1 = adk_module.run_adk("p1", user_id="u")  # chars 0 → 60
    _, sid2 = adk_module.run_adk("p2", user_id="u")  # chars 60 ≥ budget → rotate
    assert sid1 != sid2


def test_reset_driver_session_deletes_from_session_service(adk_module, monkeypatch):
    """ADR-021 left abandoned sessions in InMemorySessionService forever.
    The fix: reset_driver_session must call session_service.delete_session.
    """
    deleted = []
    original = adk_module._session_service.delete_session

    async def spy(*, app_name, user_id, session_id):
        deleted.append((user_id, session_id))
        return await original(app_name=app_name, user_id=user_id,
                              session_id=session_id)

    monkeypatch.setattr(adk_module._session_service, "delete_session", spy)

    # Plant a fake session for driver 'u'.
    import asyncio
    async def setup_session():
        s = await adk_module._session_service.create_session(
            app_name="pitwall", user_id="u")
        with adk_module._driver_sessions_lock:
            adk_module._driver_sessions["u"] = s.id
        return s.id

    fut = asyncio.run_coroutine_threadsafe(setup_session(), adk_module._loop)
    sid = fut.result(timeout=2)

    adk_module.reset_driver_session("u")
    assert ("u", sid) in deleted
    assert "u" not in adk_module._driver_sessions


def test_tracing_plugin_keys_per_agent(adk_module):
    """Audit S-tier #2: ParallelAgent runs three sub-agents concurrently.
    The plugin must NOT use a single state key, otherwise the third
    before_agent clobbers the first agent's start time and after_agent
    pops the wrong value (latency=None or wildly wrong)."""
    plugin = adk_module.PitwallTracingPlugin()
    state = {}
    ctx_a = SimpleNamespace(agent_name="A",
                            session=SimpleNamespace(id="t1", state=state))
    ctx_b = SimpleNamespace(agent_name="B",
                            session=SimpleNamespace(id="t1", state=state))
    ctx_c = SimpleNamespace(agent_name="C",
                            session=SimpleNamespace(id="t1", state=state))

    plugin.before_agent(ctx_a)
    plugin.before_agent(ctx_b)
    plugin.before_agent(ctx_c)
    # Three distinct keys — ParallelAgent race fixed.
    assert "temp:_agent_start_ms__A" in state
    assert "temp:_agent_start_ms__B" in state
    assert "temp:_agent_start_ms__C" in state

    adk_module._pending_traces.clear()
    time.sleep(0.005)
    plugin.after_agent(ctx_a)
    plugin.after_agent(ctx_b)
    plugin.after_agent(ctx_c)

    rows = adk_module.get_pending_traces(adk_session_id="t1")
    assert len(rows) == 3
    # All three must have a measurable, non-null latency.
    for r in rows:
        assert r["latency_ms"] is not None and r["latency_ms"] > 0


def test_tracing_plugin_marks_tool_errors(adk_module):
    """Audit C-tier: tool responses with {"error": ...} must record success=False
    so AgentMetaAgent can answer 'which tools fail most often?'."""
    plugin = adk_module.PitwallTracingPlugin()
    adk_module._pending_traces.clear()

    tool = SimpleNamespace(name="query_pitwall_db")
    tool_ctx = SimpleNamespace(agent_name="TelemetryAgent",
                               session=SimpleNamespace(id="t-err", state={}))
    plugin.after_tool(tool=tool, args={}, tool_context=tool_ctx,
                      response={"error": "boom"})
    plugin.after_tool(tool=tool, args={}, tool_context=tool_ctx,
                      response=[{"a": 1}])

    rows = adk_module.get_pending_traces(adk_session_id="t-err")
    by_success = {r["success"] for r in rows}
    assert by_success == {True, False}


class _StubAgent:
    """Non-pydantic stand-in for an Agent so we can inject an async-gen
    `run_async` without fighting pydantic's `extra=forbid` config.

    Used for orchestrator routing tests below.
    """
    def __init__(self, name: str = "stub", on_call=None):
        self.name = name
        self.on_call = on_call

    async def run_async(self, ctx):
        if self.on_call:
            self.on_call(ctx)
        if False:
            yield None  # makes this an async generator


def test_orchestrator_records_intent_trace(adk_module, monkeypatch):
    """Routing decision must appear in the trace deque so we can audit
    classifier quality post-hoc."""
    import asyncio

    monkeypatch.setitem(adk_module._INTENT_TO_AGENT, "telemetry",
                        _StubAgent("TelemetryStub"))
    # Replace pipeline reference too — the orchestrator's `if intent==debrief`
    # branch goes straight to debrief_pipeline.run_async, so we swap that path
    # by classifying a non-debrief query and checking the trace.

    async def drive():
        ctx = SimpleNamespace(
            user_content=SimpleNamespace(parts=[SimpleNamespace(text="show me data")]),
            session=SimpleNamespace(id="trace-intent", state={}),
        )
        adk_module._pending_traces.clear()
        async for _ in adk_module.coach_orchestrator._run_async_impl(ctx):
            pass

    asyncio.run(drive())
    rows = adk_module.get_pending_traces(adk_session_id="trace-intent")
    intents = [r for r in rows if r["event_type"] == "intent"]
    assert intents, "expected an intent trace row"
    assert intents[0]["detail"] == "telemetry"
    assert intents[0]["agent_name"] == "PitwallOrchestrator"


def test_orchestrator_honours_intent_override(adk_module, monkeypatch):
    """When session.state['temp:intent_override'] is set, the orchestrator
    bypasses the classifier and routes directly to that intent."""
    import asyncio
    captured = {}
    stub = _StubAgent("CornerStub", on_call=lambda _ctx: captured.update(called=True))
    monkeypatch.setitem(adk_module._INTENT_TO_AGENT, "corner", stub)

    async def drive():
        ctx = SimpleNamespace(
            user_content=SimpleNamespace(parts=[SimpleNamespace(text="ambiguous query")]),
            session=SimpleNamespace(id="ovr", state={"temp:intent_override": "corner"}),
        )
        async for _ in adk_module.coach_orchestrator._run_async_impl(ctx):
            pass

    asyncio.run(drive())
    assert captured.get("called") is True


def test_orchestrator_rejects_invalid_override(adk_module, monkeypatch):
    """An override string not in _VALID_INTENTS must be ignored — the
    classifier runs normally."""
    import asyncio
    captured = {}
    monkeypatch.setitem(adk_module._INTENT_TO_AGENT, "telemetry",
                        _StubAgent("TelStub", on_call=lambda c: captured.update(t=True)))
    monkeypatch.setitem(adk_module._INTENT_TO_AGENT, "corner",
                        _StubAgent("CornerStub", on_call=lambda c: captured.update(c=True)))

    async def drive():
        ctx = SimpleNamespace(
            user_content=SimpleNamespace(parts=[SimpleNamespace(text="show me data")]),
            session=SimpleNamespace(id="bad-ovr",
                                    state={"temp:intent_override": "evil_intent"}),
        )
        async for _ in adk_module.coach_orchestrator._run_async_impl(ctx):
            pass

    asyncio.run(drive())
    assert captured == {"t": True}, "invalid override should fall through to classifier"


def test_stream_adk_yields_chunks(adk_module, monkeypatch):
    """Audit A-tier #7: stream_adk must produce token chunks from the model."""
    async def fake_stream(prompt, user_id, state_overrides=None):
        for chunk in ["one ", "two ", "three"]:
            yield chunk

    monkeypatch.setattr(adk_module, "_stream_adk_async", fake_stream)
    chunks = list(adk_module.stream_adk("hi", user_id="u"))
    assert chunks == ["one ", "two ", "three"]


def test_stream_adk_timeout_raises(adk_module, monkeypatch):
    """A wedged stream must time out instead of blocking forever."""
    import asyncio
    async def fake_stream(prompt, user_id, state_overrides=None):
        await asyncio.sleep(5)
        yield "never"
    monkeypatch.setattr(adk_module, "_stream_adk_async", fake_stream)
    monkeypatch.setattr(adk_module, "_RUN_TIMEOUT_S", 0.5)
    with pytest.raises(RuntimeError, match="timeout"):
        list(adk_module.stream_adk("hi", user_id="u"))


def test_runner_drives_orchestrator_with_stub_model(adk_module, monkeypatch):
    """End-to-end smoke: feed a synthetic LLM response through the real
    Runner + plugin + session-service path. Locks audit S-tier #1: if
    `Gemini(base_url=...)` ever gets re-introduced, this test fails because
    only LiteLlm wraps the model interface we monkeypatch here.
    """
    from google.genai.types import Content, Part as _Part
    from google.adk.models.llm_response import LlmResponse

    async def fake_generate(self, *args, **kwargs):
        yield LlmResponse(
            content=Content(parts=[_Part(text="stub answer [EMOTION:neutral]")]),
            partial=False,
            turn_complete=True,
        )

    # LiteLlm is a pydantic model — patch the class method, not the instance.
    monkeypatch.setattr(type(adk_module._model),
                        "generate_content_async", fake_generate)

    # Drive the orchestrator end-to-end via the real Runner.
    text, sid = adk_module.run_adk("show me the data", user_id="u-end2end")
    assert sid  # got a real session id
    assert "stub answer" in text
    rows = adk_module.get_pending_traces(adk_session_id=sid)
    intents = [r for r in rows if r["event_type"] == "intent"]
    assert intents, "Runner ran orchestrator but no intent trace was recorded"
    assert intents[0]["detail"] == "telemetry"
    # Plugin must have recorded at least one agent latency along the way.
    agent_rows = [r for r in rows if r["event_type"] == "agent"]
    assert agent_rows, "expected agent trace rows from plugin"
