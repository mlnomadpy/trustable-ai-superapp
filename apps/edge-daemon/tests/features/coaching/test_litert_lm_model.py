"""
Unit tests for tools/litert_lm_model.py — the in-process ADK + litert-lm adapter.

Stubs litert_lm.Engine + Conversation entirely so tests run on any machine
without the real package or `.litertlm` model file. Covers:

  - Engine singleton: load once, reuse forever.
  - KV-cache reuse: same system_prompt → same Conversation across calls.
  - Cold rebuild: different system_prompt → new Conversation.
  - Drift detection: shorter ADK history than what we sent triggers rebuild.
  - Budget rotation: chars > _CONV_BUDGET triggers rebuild.
  - NPU lock: send_message calls serialise even under concurrent agents.
  - reset_all_conversations clears the cache.
"""
from __future__ import annotations

import asyncio
import queue
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SIM = ROOT / "src" / "simulator"
for p in (str(TOOLS), str(SIM)):
    if p not in sys.path:
        sys.path.insert(0, p)


# Skip the whole file unless google-adk is available — without it the
# LitertLmModel class is just a placeholder that raises on construction.
pytest.importorskip("google.adk")


# ─── Engine + Conversation stubs ────────────────────────────────────────────


class FakeConversation:
    """Stub Conversation. Tracks every send_message call + its history."""
    _all: list["FakeConversation"] = []

    def __init__(self, messages):
        self.messages = list(messages)
        self.sent: list[dict] = []
        self.replies: list[str] = []
        FakeConversation._all.append(self)

    def send_message(self, message):
        self.sent.append(message)
        text = f"reply-{len(self.sent)}-{len(self.messages)}"
        self.replies.append(text)
        # litert_lm response shape: dict with content list of typed parts.
        return {"role": "assistant",
                "content": [{"type": "text", "text": text}]}


class FakeEngine:
    """Stub Engine. Records create_conversation calls + serves a sentinel."""
    def __init__(self):
        self.created: list[FakeConversation] = []

    def create_conversation(self, messages):
        c = FakeConversation(messages)
        self.created.append(c)
        return c


@pytest.fixture
def fresh_module(monkeypatch):
    """Reload litert_lm_model with a stub engine + clean caches each test."""
    import importlib
    import pitwall.features.coaching.litert_lm_model as litert_lm_model
    # Stop any worker from a previous test before reload.
    try:
        litert_lm_model._shutdown_worker(timeout=2)
    except Exception:
        pass
    importlib.reload(litert_lm_model)

    fake_engine = FakeEngine()
    litert_lm_model._engine_singleton = fake_engine
    monkeypatch.setattr(litert_lm_model, "_load_engine", lambda: fake_engine)
    # Reset caches + worker state between tests.
    litert_lm_model._conversations.clear()
    litert_lm_model._conv_meta.clear()
    FakeConversation._all.clear()

    yield litert_lm_model

    # Always tear down the worker when the test exits.
    try:
        litert_lm_model._shutdown_worker(timeout=2)
    except Exception:
        pass


# ─── Helpers ────────────────────────────────────────────────────────────────


def _llm_request(system: str, history_pairs: list[tuple[str, str]]):
    """Build an LlmRequest-shaped object.

    history_pairs is a list of (role, text) tuples. The last one is the new
    user turn; everything before it is prior conversation history.
    """
    from google.genai.types import Content, Part

    contents = [
        Content(role=role, parts=[Part(text=text)])
        for role, text in history_pairs
    ]
    return SimpleNamespace(
        config=SimpleNamespace(
            system_instruction=Content(role="system",
                                       parts=[Part(text=system)])
        ),
        contents=contents,
    )


async def _collect(model, request):
    out = []
    async for resp in model.generate_content_async(request):
        out.append(resp)
    return out


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_first_call_creates_conversation_with_system_prompt(fresh_module):
    model = fresh_module.LitertLmModel()
    req = _llm_request("YOU ARE THE COACH", [("user", "hello")])

    responses = asyncio.run(_collect(model, req))

    assert len(responses) == 1
    text = responses[0].content.parts[0].text
    assert "reply-" in text
    # Exactly one Conversation built; system prompt was injected up front.
    assert len(FakeConversation._all) == 1
    conv = FakeConversation._all[0]
    assert conv.messages[0] == {"role": "system", "content": "YOU ARE THE COACH"}
    # User message went via send_message, not in initial history.
    assert conv.sent == [{"role": "user", "content": "hello"}]


def test_same_system_prompt_reuses_conversation(fresh_module):
    """KV cache reuse: two calls with the same system prompt share one Conversation."""
    model = fresh_module.LitertLmModel()
    req1 = _llm_request("PROMPT_A", [("user", "first")])
    req2 = _llm_request("PROMPT_A",
                        [("user", "first"),
                         ("model", "reply-1-1"),
                         ("user", "second")])

    asyncio.run(_collect(model, req1))
    asyncio.run(_collect(model, req2))

    # Only one Conversation exists across the two calls.
    assert len(FakeConversation._all) == 1
    conv = FakeConversation._all[0]
    # Both user turns went through send_message; the assistant reply came
    # from FakeConversation (we don't echo it back via initial history).
    assert conv.sent == [
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second"},
    ]


def test_different_system_prompt_creates_new_conversation(fresh_module):
    """Different agents (different system prompts) each get their own KV cache."""
    model = fresh_module.LitertLmModel()
    asyncio.run(_collect(model, _llm_request("AGENT_A", [("user", "q")])))
    asyncio.run(_collect(model, _llm_request("AGENT_B", [("user", "q")])))

    assert len(FakeConversation._all) == 2
    a, b = FakeConversation._all
    assert a.messages[0]["content"] == "AGENT_A"
    assert b.messages[0]["content"] == "AGENT_B"


def test_drift_detection_triggers_rebuild(fresh_module):
    """If ADK supplies a SHORTER history than what we sent, rebuild.

    Scenario: an out-of-band reset on ADK's side resets the visible history
    to one user turn after we already sent two. Our cached Conversation no
    longer matches reality — drop it and start over.
    """
    model = fresh_module.LitertLmModel()
    # Two-turn conversation builds up.
    asyncio.run(_collect(model, _llm_request("P", [("user", "u1")])))
    asyncio.run(_collect(model, _llm_request("P",
                                              [("user", "u1"),
                                               ("model", "reply-1-1"),
                                               ("user", "u2")])))
    assert len(FakeConversation._all) == 1

    # Now ADK comes back with just one new user turn — drift.
    asyncio.run(_collect(model, _llm_request("P", [("user", "u3")])))
    assert len(FakeConversation._all) == 2
    # The new conversation is empty of prior history.
    assert FakeConversation._all[1].messages == [
        {"role": "system", "content": "P"},
    ]


def test_char_budget_rotation(fresh_module, monkeypatch):
    """When chars exceed _CONV_BUDGET, the next call rebuilds the Conversation."""
    monkeypatch.setattr(fresh_module, "_CONV_BUDGET", 50)
    model = fresh_module.LitertLmModel()
    req = _llm_request("S", [("user", "x" * 30)])
    asyncio.run(_collect(model, req))      # chars ≈ 30 (sys=1 + user=30 + reply)
    asyncio.run(_collect(model, _llm_request(
        "S", [("user", "x" * 30), ("model", "r"), ("user", "x" * 30)])))
    # By call 2 the meter is well above 50 → call 3 must rotate.
    asyncio.run(_collect(model, _llm_request(
        "S", [("user", "x" * 30), ("model", "r"),
              ("user", "x" * 30), ("model", "r"), ("user", "y")])))
    assert len(FakeConversation._all) >= 2  # at least one rotation


def test_npu_lock_serialises_concurrent_calls(fresh_module):
    """Tensor G5 NPU is single-threaded. The adapter must serialise
    send_message even when ADK fires multiple agents concurrently
    (ParallelAgent path)."""
    in_flight = {"count": 0, "max": 0}
    in_flight_lock = threading.Lock()

    original_send = FakeConversation.send_message

    def slow_send(self, message):
        with in_flight_lock:
            in_flight["count"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["count"])
        time.sleep(0.05)
        try:
            return original_send(self, message)
        finally:
            with in_flight_lock:
                in_flight["count"] -= 1

    FakeConversation.send_message = slow_send  # type: ignore[assignment]
    try:
        model = fresh_module.LitertLmModel()

        async def fire_n(n):
            tasks = [
                _collect(model, _llm_request(f"A{i}", [("user", f"q{i}")]))
                for i in range(n)
            ]
            await asyncio.gather(*tasks)

        asyncio.run(fire_n(4))
    finally:
        FakeConversation.send_message = original_send  # type: ignore[assignment]

    assert in_flight["max"] == 1, (
        f"expected NPU lock to serialise inferences, "
        f"observed concurrent peak: {in_flight['max']}")


def test_reset_all_conversations_clears_cache(fresh_module):
    """reset_all_conversations() drops every cached Conversation; next call
    rebuilds from scratch even with an unchanged system prompt."""
    model = fresh_module.LitertLmModel()
    asyncio.run(_collect(model, _llm_request("P", [("user", "q")])))
    assert len(FakeConversation._all) == 1

    fresh_module.reset_all_conversations()
    assert fresh_module._conversations == {}
    assert fresh_module._conv_meta == {}

    asyncio.run(_collect(model, _llm_request("P", [("user", "q")])))
    assert len(FakeConversation._all) == 2  # rebuilt


def test_kv_cache_stats_reports_active_count(fresh_module):
    model = fresh_module.LitertLmModel()
    asyncio.run(_collect(model, _llm_request("AGENT_A", [("user", "q")])))
    asyncio.run(_collect(model, _llm_request("AGENT_B", [("user", "q")])))
    stats = fresh_module.get_kv_cache_stats()
    assert stats["active_conversations"] == 2
    assert stats["budget"] == fresh_module._CONV_BUDGET
    assert stats["total_chars"] > 0


def test_empty_request_yields_error_response(fresh_module):
    model = fresh_module.LitertLmModel()
    req = SimpleNamespace(config=None, contents=[])
    out = asyncio.run(_collect(model, req))
    assert len(out) == 1
    assert out[0].error_code == "EMPTY_REQUEST"


def test_empty_user_message_yields_error_response(fresh_module):
    """Last content with no text is rejected — we don't fabricate a turn."""
    from google.genai.types import Content, Part
    model = fresh_module.LitertLmModel()
    req = SimpleNamespace(
        config=SimpleNamespace(system_instruction=None),
        contents=[Content(role="user", parts=[Part(text="")])],
    )
    out = asyncio.run(_collect(model, req))
    assert out[0].error_code == "EMPTY_USER_MESSAGE"


def test_engine_error_surfaced_as_llm_response(fresh_module, monkeypatch):
    """If send_message raises, the model yields a turn_complete LlmResponse
    with error_code/error_message set instead of bubbling the exception."""
    def boom(self, message):
        raise RuntimeError("npu offline")
    monkeypatch.setattr(FakeConversation, "send_message", boom)
    model = fresh_module.LitertLmModel()
    out = asyncio.run(_collect(model, _llm_request("P", [("user", "q")])))
    assert len(out) == 1
    assert out[0].error_code == "LITERTLM_ERROR"
    assert "npu offline" in out[0].error_message


def test_engine_backend_selectable_via_env(monkeypatch, fresh_module):
    """PITWALL_ADK_BACKEND=engine wires LitertLmModel into adk_agents."""
    pytest.importorskip("google.adk")
    monkeypatch.setenv("PITWALL_ADK_BACKEND", "engine")
    # Pre-stub so adk_agents' import-time _load_engine call uses the fake.
    fake_engine = FakeEngine()
    fresh_module._engine_singleton = fake_engine
    monkeypatch.setattr(fresh_module, "_load_engine", lambda: fake_engine)

    import importlib
    from pitwall.features.coaching import adk_agents
    importlib.reload(adk_agents)
    try:
        assert adk_agents._BACKEND == "engine"
        assert type(adk_agents._model).__name__ == "LitertLmModel"
    finally:
        monkeypatch.delenv("PITWALL_ADK_BACKEND", raising=False)
        importlib.reload(adk_agents)


def test_reset_driver_session_flushes_litertlm_cache(monkeypatch, fresh_module):
    """The bridge calls reset_driver_session on /session/start.
    That must also clear the in-process Conversation cache so the next
    driving day starts with a known-fresh KV state."""
    pytest.importorskip("google.adk")
    import importlib
    from pitwall.features.coaching import adk_agents
    importlib.reload(adk_agents)
    # Plant a cache entry directly.
    fresh_module._conversations["abc"] = object()
    fresh_module._conv_meta["abc"] = {"chars": 1, "history_len": 0,
                                       "system_prompt_chars": 1}
    # adk_agents.reset_driver_session calls the imported alias.
    adk_agents.reset_driver_session("driver-x")
    assert fresh_module._conversations == {}
    assert fresh_module._conv_meta == {}


# ════════════════════════════════════════════════════════════════════════════
# Queue / worker / thermal — the "don't cook the phone" layer
# ════════════════════════════════════════════════════════════════════════════


def test_single_worker_serializes_concurrent_calls(fresh_module):
    """Concurrent submitters share one worker drainer. send_message is
    never called concurrently — the Tensor G5 NPU sees one call at a time."""
    in_flight = {"count": 0, "max": 0}
    flight_lock = threading.Lock()
    original = FakeConversation.send_message

    def slow_send(self, message):
        with flight_lock:
            in_flight["count"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["count"])
        time.sleep(0.05)
        try:
            return original(self, message)
        finally:
            with flight_lock:
                in_flight["count"] -= 1

    FakeConversation.send_message = slow_send  # type: ignore[assignment]
    try:
        model = fresh_module.LitertLmModel()

        async def fire_n(n):
            tasks = [
                _collect(model, _llm_request(f"A{i}", [("user", f"q{i}")]))
                for i in range(n)
            ]
            await asyncio.gather(*tasks)

        asyncio.run(fire_n(4))
    finally:
        FakeConversation.send_message = original  # type: ignore[assignment]

    assert in_flight["max"] == 1, (
        f"expected serialized worker, observed peak {in_flight['max']}")


def test_queue_full_rejects_excess_submissions(fresh_module, monkeypatch):
    """When `_QUEUE_MAX` is reached and put() can't free a slot within
    `_QUEUE_TIMEOUT_S`, _submit_inference raises a clear queue-full error
    rather than blocking the caller indefinitely.
    """
    # Tiny queue + tiny put-timeout. Disable the worker so jobs never drain.
    monkeypatch.setattr(fresh_module, "_QUEUE_MAX", 1)
    monkeypatch.setattr(fresh_module, "_QUEUE_TIMEOUT_S", 0.1)
    fresh_module._job_queue = queue.PriorityQueue(maxsize=1)
    fresh_module._worker_started = True   # short-circuit lazy worker start

    # Pre-fill the queue with a sentinel job so the next put() blocks.
    sentinel = fresh_module._Job(priority=0, seq=0,
                                  payload={"key": "sentinel"},
                                  result_q=queue.SimpleQueue())
    fresh_module._job_queue.put(sentinel)

    payload = {"key": "x", "system_prompt": "", "history": [], "last_text": "q"}
    with pytest.raises(RuntimeError, match="queue full"):
        fresh_module._submit_inference(payload, priority=5)


def test_queue_result_timeout_surfaces_clear_error(fresh_module, monkeypatch):
    """If the worker accepts a job but never delivers a result within the
    timeout, the submitter sees a timeout error instead of hanging."""
    monkeypatch.setattr(fresh_module, "_QUEUE_TIMEOUT_S", 0.1)
    # Disable the worker so submitted jobs never get results.
    fresh_module._worker_started = True
    payload = {"key": "x", "system_prompt": "", "history": [], "last_text": "q"}
    with pytest.raises(RuntimeError, match="timed out"):
        fresh_module._submit_inference(payload, priority=5)


def test_cooldown_enforced_between_inferences(fresh_module, monkeypatch):
    """When PITWALL_LITERTLM_COOLDOWN_MS > 0, two back-to-back jobs are at
    least that far apart in start time."""
    monkeypatch.setattr(fresh_module, "_COOLDOWN_S", 0.20)  # 200 ms cooldown
    timestamps: list[float] = []
    original = FakeConversation.send_message

    def stamping_send(self, message):
        timestamps.append(time.monotonic())
        return original(self, message)

    FakeConversation.send_message = stamping_send  # type: ignore[assignment]
    model = fresh_module.LitertLmModel()
    try:
        async def two_calls():
            await _collect(model, _llm_request("S", [("user", "q1")]))
            await _collect(model, _llm_request("S",
                                                [("user", "q1"),
                                                 ("model", "reply-1-1"),
                                                 ("user", "q2")]))
        asyncio.run(two_calls())
    finally:
        FakeConversation.send_message = original  # type: ignore[assignment]

    assert len(timestamps) == 2
    delta = timestamps[1] - timestamps[0]
    assert delta >= 0.18, (
        f"second inference started {delta*1000:.0f}ms after first; "
        f"expected ≥ 200ms cooldown")


def test_thermal_backoff_sleeps_when_hot(fresh_module, monkeypatch):
    """When the simulated thermal zone reads > limit, the worker inserts a
    proportional sleep before the next inference."""
    monkeypatch.setattr(fresh_module, "_THERMAL_LIMIT_C", 60.0)
    monkeypatch.setattr(fresh_module, "_THERMAL_GAIN_S", 0.05)
    # Simulate 70°C — 10°C over limit → 0.5s back-off.
    monkeypatch.setattr(fresh_module, "_read_max_celsius", lambda: 70.0)

    timestamps = []
    original = FakeConversation.send_message

    def stamping_send(self, message):
        timestamps.append(time.monotonic())
        return original(self, message)

    FakeConversation.send_message = stamping_send  # type: ignore[assignment]
    model = fresh_module.LitertLmModel()
    try:
        t0 = time.monotonic()
        asyncio.run(_collect(model, _llm_request("S", [("user", "q")])))
        elapsed = timestamps[0] - t0
    finally:
        FakeConversation.send_message = original  # type: ignore[assignment]

    assert elapsed >= 0.4, (
        f"expected ≥ 400ms thermal back-off before inference, got {elapsed*1000:.0f}ms")


def test_thermal_backoff_skipped_below_limit(fresh_module, monkeypatch):
    """Below the configured threshold, no back-off sleep is added."""
    monkeypatch.setattr(fresh_module, "_THERMAL_LIMIT_C", 60.0)
    monkeypatch.setattr(fresh_module, "_read_max_celsius", lambda: 45.0)
    assert fresh_module._thermal_backoff_seconds() == 0.0


def test_thermal_backoff_disabled_when_limit_zero(fresh_module, monkeypatch):
    """Setting PITWALL_LITERTLM_THERMAL_LIMIT_C=0 disables thermal back-off."""
    monkeypatch.setattr(fresh_module, "_THERMAL_LIMIT_C", 0.0)
    monkeypatch.setattr(fresh_module, "_read_max_celsius", lambda: 90.0)
    assert fresh_module._thermal_backoff_seconds() == 0.0


def test_get_queue_stats_reports_state(fresh_module, monkeypatch):
    monkeypatch.setattr(fresh_module, "_COOLDOWN_S", 0.05)
    monkeypatch.setattr(fresh_module, "_THERMAL_LIMIT_C", 65.0)
    monkeypatch.setattr(fresh_module, "_read_max_celsius", lambda: 42.0)
    model = fresh_module.LitertLmModel()
    asyncio.run(_collect(model, _llm_request("S", [("user", "q")])))
    stats = fresh_module.get_queue_stats()
    assert stats["queue_max"] == fresh_module._QUEUE_MAX
    assert stats["cooldown_ms"] == 50
    assert stats["thermal_limit_c"] == 65.0
    assert stats["thermal_temp_c"] == 42.0
    assert stats["worker_alive"] is True


# ════════════════════════════════════════════════════════════════════════════
# Tool-call parsing
# ════════════════════════════════════════════════════════════════════════════


def test_tool_definitions_injected_into_system_prompt(fresh_module):
    """ADK tools_dict must be rendered into the system prompt the engine sees."""
    model = fresh_module.LitertLmModel()
    decl = SimpleNamespace(description="Query the DB.")
    tools_dict = {"query_pitwall_db": decl}

    from google.genai.types import Content, Part
    request = SimpleNamespace(
        config=SimpleNamespace(
            system_instruction=Content(role="system",
                                        parts=[Part(text="BASE PROMPT")])
        ),
        contents=[Content(role="user", parts=[Part(text="hi")])],
        tools_dict=tools_dict,
    )
    asyncio.run(_collect(model, request))

    assert len(FakeConversation._all) == 1
    sys_msg = FakeConversation._all[0].messages[0]["content"]
    assert "BASE PROMPT" in sys_msg
    assert "query_pitwall_db" in sys_msg
    assert "Query the DB." in sys_msg


def test_function_call_parsed_from_xml_format(fresh_module, monkeypatch):
    """Model output containing <function_call>JSON</function_call> is converted
    to ADK FunctionCall parts so the agent can dispatch the tool."""
    def fake_send(self, message):
        self.sent.append(message)
        return {"role": "assistant", "content": [{"type": "text", "text":
            'Looking it up. <function_call>{"name": "query_pitwall_db", '
            '"args": {"sql": "SELECT 1"}}</function_call>'}]}

    monkeypatch.setattr(FakeConversation, "send_message", fake_send)
    model = fresh_module.LitertLmModel()
    out = asyncio.run(_collect(model, _llm_request("S", [("user", "q")])))

    assert len(out) == 1
    parts = out[0].content.parts
    assert len(parts) == 1
    fc = parts[0].function_call
    assert fc is not None
    assert fc.name == "query_pitwall_db"
    assert fc.args == {"sql": "SELECT 1"}


def test_function_call_parsed_from_tool_code_block(fresh_module, monkeypatch):
    """Gemma sometimes emits ```tool_code\nname(k=v)\n``` instead of XML.
    The fallback parser handles flat kwargs."""
    def fake_send(self, message):
        self.sent.append(message)
        return {"role": "assistant", "content": [{"type": "text", "text":
            "Sure.\n```tool_code\nget_lap_delta(session_id=\"S1\", lap_a=2, lap_b=4)\n```\n"
        }]}

    monkeypatch.setattr(FakeConversation, "send_message", fake_send)
    model = fresh_module.LitertLmModel()
    out = asyncio.run(_collect(model, _llm_request("S", [("user", "q")])))

    fc = out[0].content.parts[0].function_call
    assert fc.name == "get_lap_delta"
    assert fc.args == {"session_id": "S1", "lap_a": 2, "lap_b": 4}


def test_unparseable_output_falls_back_to_text(fresh_module):
    """When the model just produces narrative, we yield it as text."""
    model = fresh_module.LitertLmModel()
    out = asyncio.run(_collect(model, _llm_request("S", [("user", "q")])))
    parts = out[0].content.parts
    assert parts[0].text  # non-empty
    assert parts[0].function_call is None


def test_function_response_in_history_formatted_for_engine(fresh_module):
    """When ADK passes a function_response back in history (after we requested
    a tool call), the adapter must translate it into something the engine
    can read on the next turn."""
    from google.genai.types import Content, FunctionResponse, Part

    model = fresh_module.LitertLmModel()
    history = [
        Content(role="user",  parts=[Part(text="how was lap 4?")]),
        Content(role="model", parts=[Part(text=
            '<function_call>{"name": "get_lap_delta", '
            '"args": {"session_id": "S1", "lap_a": 4, "lap_b": 5}}'
            '</function_call>')]),
        Content(role="user",  parts=[Part(function_response=FunctionResponse(
            name="get_lap_delta",
            response={"delta_s": 0.42, "faster_lap": 4}))]),
    ]
    request = SimpleNamespace(
        config=SimpleNamespace(
            system_instruction=Content(role="system",
                                        parts=[Part(text="S")])
        ),
        contents=history,
    )
    asyncio.run(_collect(model, request))

    conv = FakeConversation._all[-1]
    sent = conv.sent[-1]["content"]
    # The function_response should have been re-rendered as a tool_result tag.
    assert "tool_result" in sent
    assert "get_lap_delta" in sent
    assert "0.42" in sent


# ════════════════════════════════════════════════════════════════════════════
# Streaming probe
# ════════════════════════════════════════════════════════════════════════════


def test_streaming_via_engine_streaming_method(fresh_module, monkeypatch):
    """If Conversation exposes send_message_stream, the adapter yields
    partial LlmResponse chunks then a final turn_complete=True message."""
    def stream(self, message):
        yield "Hello "
        yield "world. "
        yield "[EMOTION:neutral]"

    monkeypatch.setattr(FakeConversation, "send_message_stream", stream,
                        raising=False)
    model = fresh_module.LitertLmModel()
    from google.genai.types import Content, Part
    request = SimpleNamespace(
        config=SimpleNamespace(
            system_instruction=Content(role="system",
                                        parts=[Part(text="S")])
        ),
        contents=[Content(role="user", parts=[Part(text="hi")])],
    )

    async def collect_stream():
        out = []
        async for resp in model.generate_content_async(request, stream=True):
            out.append(resp)
        return out

    out = asyncio.run(collect_stream())

    partials = [r for r in out if getattr(r, "partial", False)]
    finals = [r for r in out if r.turn_complete]
    assert partials, "expected streamed partial chunks"
    assert finals, "expected one final turn_complete=True response"


def test_streaming_falls_back_when_engine_lacks_stream_api(fresh_module):
    """If the engine doesn't expose any streaming method, the adapter
    silently degrades to a single turn_complete response so SSE clients
    still see the answer."""
    model = fresh_module.LitertLmModel()
    from google.genai.types import Content, Part
    request = SimpleNamespace(
        config=SimpleNamespace(
            system_instruction=Content(role="system",
                                        parts=[Part(text="S")])
        ),
        contents=[Content(role="user", parts=[Part(text="hi")])],
    )

    async def collect_stream():
        out = []
        async for resp in model.generate_content_async(request, stream=True):
            out.append(resp)
        return out

    out = asyncio.run(collect_stream())
    finals = [r for r in out if r.turn_complete]
    assert finals, "expected at least one final response when streaming unsupported"


# ════════════════════════════════════════════════════════════════════════════
# Tool-arg kwarg parser unit tests
# ════════════════════════════════════════════════════════════════════════════


def test_parse_kwargs_handles_strings_and_numbers(fresh_module):
    pk = fresh_module._parse_kwargs
    assert pk('s="hello", n=42, f=3.14, ok=true') == {
        "s": "hello", "n": 42, "f": 3.14, "ok": True,
    }


def test_parse_kwargs_handles_quoted_commas(fresh_module):
    """Strings containing commas must not be split as separate kwargs."""
    pk = fresh_module._parse_kwargs
    out = pk('sql="SELECT 1, 2", lim=5')
    assert out == {"sql": "SELECT 1, 2", "lim": 5}


def test_parse_kwargs_empty_string(fresh_module):
    assert fresh_module._parse_kwargs("") == {}
    assert fresh_module._parse_kwargs("   ") == {}
