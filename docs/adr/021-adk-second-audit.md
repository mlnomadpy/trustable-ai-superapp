# ADR-021 — ADK Second Audit: Runner API, Concurrency Fixes, and Feature Gaps

**Status:** Accepted  
**Date:** 2026-05-01  
**Supersedes:** ADR-020 (extends, does not replace)

**Note:** Files referenced in this ADR have moved: tools/pitwall_bridge.py → src/pitwall/__main__.py; tools/adk_agents.py → src/pitwall/features/coaching/adk_agents.py.

---

## Context

After ADR-020 shipped (7 structural fixes), a second audit of the implementation identified four new bugs and catalogued ADK features not yet used. The audit ran against `adk_agents.py` (post-020 rewrite), `adk_tools.py`, and `pitwall_bridge.py`.

---

## Bugs found and fixed in this ADR

### Bug 1 — `BaseAgent` has no `.run()` method (HIGH)

**File:** `pitwall_bridge.py` (3 call sites)  
**Problem:** All three ADK call sites did `_adk_orchestrator.run(prompt)`. `PitwallOrchestrator` extends `BaseAgent`, which does NOT expose a `.run()` convenience method — that shortcut exists only on `LlmAgent`. Every ADK call would have raised `AttributeError` at runtime.  
**Fix:** Added `Runner` + `InMemorySessionService` + `run_adk()` helper in `adk_agents.py`. Bridge now calls `_run_adk(prompt)` — a sync wrapper around `asyncio.run(_run_adk_async(...))`.

```python
# adk_agents.py — new canonical invocation
_session_service = InMemorySessionService()
_runner = Runner(agent=coach_orchestrator, app_name="pitwall",
                 session_service=_session_service)

async def _run_adk_async(prompt: str, user_id: str) -> str:
    session = await _session_service.create_session(app_name="pitwall", user_id=user_id)
    final_text = ""
    async for event in _runner.run_async(
        user_id=user_id, session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
    ):
        if event.is_final_response() and event.content:
            final_text = event.content.parts[0].text or final_text
    return final_text

def run_adk(prompt: str, user_id: str = "driver") -> str:
    return asyncio.run(_run_adk_async(prompt, user_id))
```

### Bug 2 — `save_voice_scripts` TOCTOU race condition (HIGH)

**File:** `adk_tools.py`  
**Problem:** Read-then-write pattern without locking. Two concurrent `VoiceScriptAgent` calls for the same corner would race: one thread's writes could be silently overwritten by the other.  
**Fix:** `fcntl.flock(LOCK_EX)` + atomic `os.replace(tmp, path)` pattern.

### Bug 3 — Shared `narrative_agent` across two pipelines (MEDIUM)

**File:** `adk_agents.py`  
**Problem:** `debrief_pipeline` and `brief_pipeline` both used the same `narrative_agent` instance. ADK agents may track parent context internally; sharing across pipelines risks state bleed if requests overlap.  
**Fix:** Created three separate `NarrativeAgent` instances: `narrative_agent` (QA paths), `_narrative_debrief` (debrief pipeline), `_narrative_brief` (brief pipeline). All share identical instruction templates.

### Bug 4 — `_qa_histories` memory leak (MEDIUM)

**File:** `pitwall_bridge.py`  
**Problem:** In-memory dict keyed by `"driver_id:session_id"`. `POST /coach/ask/end` flushes and pops the entry, but clients that crash or disconnect mid-conversation never call `/end`. The dict grows unbounded.  
**Fix:** Added `_qa_timestamps` dict + `_qa_cleanup_stale()` called on every `POST /coach/ask`. Entries older than 1 hour are evicted.

---

## Additional items shipped (same session)

### Persistent ADK sessions + KV cache reuse

**Problem:** Each `run_adk()` call created a new ADK session via `InMemorySessionService.create_session()`. `lit serve` saw a completely fresh prompt each time — no KV cache reuse across calls. Agent system instruction tokens (~100–300 per agent) were re-prefilled on every request.

**Research finding:** `lit serve` has no prefix-cache flags. KV cache reuse happens at the ADK session level via **session cloning** — LiteRT-LM clones KV tensors for a reused session (<10 ms overhead) rather than re-prefilling. Keeping the same ADK session alive across calls gives warm requests.

**Fix:** Persistent session registry per driver in `adk_agents.py`:

```python
_driver_sessions: dict[str, str]    # user_id → ADK session_id
_session_turn_count: dict[str, int] # auto-reset at _SESSION_MAX_TURNS = 50

async def _get_or_create_session(user_id: str):
    # Return existing session if valid, else create new one
    ...

def reset_driver_session(user_id: str) -> None:
    # Called by bridge at POST /session/start — intentional cold reset
    ...
```

`POST /session/start` calls `_reset_adk_session(driver_id)` automatically. Cold start at new session start is acceptable; all subsequent calls that day use the warm session.

**Expected impact:** ~30–50% prefill reduction on warm calls → ~0.5–3 s saved per call on Tensor G5 NPU.

---

## ADK features not yet used — prioritised backlog

### Tier 1 — implement next

| Feature | Value for pitwall | Location to add |
|---|---|---|
| **State scopes** (`user:`, `app:`, `temp:`) | Driver preferences persist across sessions; track conditions shared app-wide | `PitwallOrchestrator._run_async_impl` |
| ~~**Plugin system**~~ ✅ shipped | `PitwallTracingPlugin` + `agent_traces` | `adk_agents.py` |
| **SSE streaming** | Vue PWA shows tokens as they arrive — critical for 2–15s E4B latency | New `/coach/ask/stream` endpoint + `RunConfig(streaming_mode=SSE)` |

### Tier 2 — medium term

| Feature | Value | Notes |
|---|---|---|
| **Callbacks** (`before_tool_callback`) | Per-agent SQL policy enforcement | Add to `telemetry_agent`, `query_pitwall_db` tool agents |
| **`LoopAgent`** | Q&A refinement — ask follow-up if answer incomplete | Wrap QA path agents in 3-iteration loop |
| **Artifacts** (`user:` scoped) | Session PDF export, uploaded VBO files | `ToolContext.save_artifact("user:session.pdf", ...)` |
| **Memory service** | Multi-session driver knowledge beyond DuckDB | `VertexAiRagMemoryService` (cloud) or `InMemoryMemoryService` (local) |

### Tier 3 — research only

| Feature | Notes |
|---|---|
| `input_schema` / `output_schema` | Structured JSON in/out per agent — conflicts with multi-step tool use |
| `VertexAiMemoryBankService` | Requires Google Cloud — incompatible with Termux target |
| `Model Armor Plugin` | Production safety API — not on-device |

---

## SSE streaming design (Tier 1 — not yet implemented)

```python
# adk_agents.py addition
async def _stream_adk_async(prompt: str, user_id: str):
    session = await _session_service.create_session(app_name="pitwall", user_id=user_id)
    config = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=20)
    async for event in _runner.run_async(
        user_id=user_id, session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
        run_config=config,
    ):
        if event.content and event.content.parts:
            yield event.content.parts[0].text or ""

# pitwall_bridge.py addition
@app.route("/coach/ask/stream", methods=["POST"])
def coach_ask_stream():
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get("question", "")
    user_id = data.get("driver_id", "driver")

    def generate():
        loop = asyncio.new_event_loop()
        async def collect():
            async for chunk in _stream_adk_async(prompt, user_id):
                yield f"data: {chunk}\n\n"
        for chunk in loop.run_until_complete(...):
            yield chunk

    return Response(generate(), mimetype="text/event-stream")
```

---

## State scopes design (Tier 1 — not yet implemented)

```python
# In PitwallOrchestrator._run_async_impl
# Persist driver focus preference across sessions
ctx.session.state["user:preferred_corner_focus"] = detected_focus

# Share track conditions app-wide (set once by weather endpoint)
ctx.session.state["app:track_phase"] = weather_phase_id

# Temp state for debrief — gone after this invocation
ctx.session.state["temp:debrief_lap_count"] = lap_count
```

---

## DuckDB agent telemetry (implemented)

`agent_traces` table added to `get_db()` — one row per agent run or tool call:

```sql
CREATE TABLE agent_traces (
    id          INTEGER PRIMARY KEY,
    trace_id    VARCHAR,    -- ADK session UUID — groups one run_adk() call
    pitwall_sid VARCHAR,    -- pitwall session_id (empty for Q&A)
    agent_name  VARCHAR,
    event_type  VARCHAR,    -- 'agent' | 'tool'
    detail      VARCHAR,    -- tool name, or intent for orchestrator
    latency_ms  DOUBLE,
    success     BOOLEAN,
    ts          TIMESTAMP
);
```

**`PitwallTracingPlugin(BasePlugin)`** added to `adk_agents.py`:
- `before_agent` → stores `temp:_agent_start_ms` in session state
- `after_agent` → computes latency, pushes to `_pending_traces` deque
- `after_tool` → records tool name + caller agent

`get_pending_traces()` exported from `adk_agents.py`. Bridge calls `_drain_adk_traces(pitwall_sid)` after every `run_adk()` invocation to flush the deque to DuckDB.

**Useful queries:**
```sql
-- Which agents are slowest?
SELECT agent_name, AVG(latency_ms), COUNT(*)
FROM agent_traces WHERE event_type = 'agent'
GROUP BY agent_name ORDER BY AVG(latency_ms) DESC;

-- Tool call frequency
SELECT detail, COUNT(*) FROM agent_traces
WHERE event_type = 'tool' GROUP BY detail ORDER BY 2 DESC;

-- Full trace for one run
SELECT agent_name, event_type, detail, latency_ms, ts
FROM agent_traces WHERE trace_id = ? ORDER BY ts;
```

---

## Consequences

- All four bugs are fixed and 358/358 tests pass.
- `run_adk()` is the canonical sync entry point — bridge has no direct Agent method calls.
- `_qa_histories` is bounded by 1-hour TTL.
- `agent_traces` gives full agent + tool-call observability in the same DuckDB file as all other telemetry.
- Three ADK features (state scopes, plugins, SSE streaming) are documented and ready to implement post-Sonoma.
