# ADK Agent Architecture

Companion to [ADR-019](adr/019-adk-multi-agent-backend.md),
[ADR-020](adr/020-adk-agent-architecture-refactor.md),
[ADR-021](adr/021-adk-second-audit.md), and
[ADR-022](adr/022-openai-compatible-backend-selector.md).

**Current state (2026-05-26):** All phases implemented. Backend selector
landed 2026-05-12 — paddock ADK speaks to
[**LocalLLM**](https://www.tahabouhsine.com/localllm/), an Apache-2.0 Android
APK ([github.com/mlnomadpy/localllm](https://github.com/mlnomadpy/localllm))
that hosts LiteRT-LM and exposes an OpenAI-compatible HTTP server. On the
desktop default it listens on `127.0.0.1:8099/v1`; the phone deploy
(`deploy/phone/70-start-bridge.sh`) sets `PITWALL_ADK_OPENAI_URL` to
`http://localhost:8080/v1` to match LocalLLM's Android default port. Two
legacy paths (`lit serve` via `Gemini(base_url=...)`, in-process
`LitertLmModel`) remain available and are byte-identical from the agents'
point of view.

> **Phone install gap (2026-05-26).** `google-adk` does not install on
> Termux aarch64 — there are no `android_arm64_v8a` wheels for `cffi`,
> `cryptography`, `watchdog`, or `pydantic-core`, and `adb shell su <uid>`
> doesn't have working DNS, so `pip install` from PyPI fails outright on
> the phone. 16 MB of pre-staged ADK wheels live at `~/adk-wheels` on the
> Pixel for an offline install once Termux's DNS is back. Until then,
> every ADK-backed endpoint (`/coach/ask`, `/coach/agents`, `/coach/traces`)
> returns honest `{available: false, reason: "google-adk not installed"}`.

---

## Guiding constraints

1. **ADK never touches the hot path.** In-drive coaching (< 100 ms) stays as `RuleCoach` + `CoachArbiter`. ADK is paddock-only.
2. **DuckDB writes belong to the bridge.** All ADK tools query DuckDB `read_only=True`. The bridge is the sole writer — except `save_voice_scripts`, which writes to `tools/audio_cache/` (JSON files, not DuckDB).
3. **Pluggable local-LLM backend — never a hosted API.** Per [ADR-022](adr/022-openai-compatible-backend-selector.md) the paddock tier is portable across three local backends, selected by `PITWALL_ADK_BACKEND`. All three speak to a model running on the same phone as the bridge. There is no hosted-LLM fallback.

    | `PITWALL_ADK_BACKEND` | Transport            | Server                                                     | Client class                          | Used for                                              |
    | --------------------- | -------------------- | ---------------------------------------------------------- | ------------------------------------- | ----------------------------------------------------- |
    | `openai` *(default)*  | HTTP → `127.0.0.1`   | [**LocalLLM APK**](https://www.tahabouhsine.com/localllm/) (`:8099/v1`) | `LiteLlm(api_base=..., api_key=...)`  | **Pixel field deployment — primary path**             |
    | `engine`              | In-process (no HTTP) | *(same process as bridge — no server)*                     | `LitertLmModel(BaseLlm)`              | Single-process Termux setups without LocalLLM         |
    | `litertlm`            | HTTP → `lit serve`   | `lit serve` Python process                                 | `Gemini(base_url=..., model=...)`     | Legacy / desktop dev with `lit serve` already running |

    **Default behaviour (ADR-022, 2026-05-12 onward):** new installs of the
    bridge talk to [LocalLLM](https://github.com/mlnomadpy/localllm) — a
    separate Apache-2.0 Android APK that hosts LiteRT-LM in a native Android
    process with GPU/NPU delegate access via LiteRT's AUTO backend, owns
    model lifecycle through its in-app catalog, and speaks OpenAI's
    `chat.completions` with SSE streaming and signed-bearer-token auth. The
    same `openai` selector also covers Ollama / LM Studio / llama.cpp / vLLM
    on dev workstations.

    **The warm path is on the same transport.** `LitertCoach.brief()` and
    `LitertCoach.debrief()` ([coach_engine.py](coaching-engine.md)) also
    default to HTTP-to-LocalLLM as of ADR-022 — every LLM call in pitwall
    goes through `127.0.0.1`. Set `PITWALL_ADK_OPENAI_URL=""` (empty;
    legacy alias `PITWALL_LITERT_URL` still works with a
    `DeprecationWarning`) to opt
    back into the in-process `litert_lm.Engine` for the warm path.

4. **Two runtimes, one ecosystem:**

    | Path | Runtime | Model | How invoked | Latency budget |
    |---|---|---|---|---|
    | In-drive (hot) | `litert_lm.Engine` (in-process) | Gemma 4 E2B | Direct API | < 100 ms |
    | Paddock (ADK) | One of the three backends above | Gemma 4 E4B / E2B | See backend table | 2–15 s |

5. **Routing is deterministic Python.** `PitwallOrchestrator` uses `_classify_intent()` — a keyword classifier — not LLM routing. This eliminates mis-routing between similar agents.
6. **SQL queries are bounded.** `query_pitwall_db` enforces `LIMIT 500` and rejects non-SELECT. No agent can blow the context window via a table scan.
7. **All agent calls go through `run_adk()`.** `BaseAgent` has no `.run()` shortcut; the canonical path is `Runner.run_async()` wrapped in `asyncio.run()`.
8. **Persistent sessions for KV cache reuse.** `InMemorySessionService` sessions are reused per driver within a process lifetime. `lit serve` clones the KV cache across turns — session system instructions only prefill once per driving day.

---

## Full topology

```
src/pitwall/__main__.py (Flask, sync)
    │
    │  run_adk(prompt, user_id)          ← _get_or_create_session(user_id)
    │  _drain_adk_traces(pitwall_sid)    ← get_pending_traces() → agent_traces DuckDB
    │  _reset_adk_session(driver_id)     ← called by POST /session/start
    │
    ▼
Runner(PitwallOrchestrator, InMemorySessionService, plugins=[PitwallTracingPlugin])
    │
    ▼
PitwallOrchestrator(BaseAgent)
    _classify_intent(query) → deterministic keyword routing
    │
    ├── "debrief"  →  DebriefPipeline (SequentialAgent)
    │                   ├── DebriefDataPhase (ParallelAgent)  ← 3× concurrent
    │                   │     ├── HighlightFinderAgent  output_key=highlights_data
    │                   │     ├── TelemetryAgent        output_key=telemetry_data
    │                   │     └── PedagogyAgent         output_key=pedagogy_data
    │                   └── NarrativeAgentDebrief       reads {highlights_data}
    │                                                        {telemetry_data}
    │                                                        {pedagogy_data}
    │
    ├── "brief"    →  BriefPipeline (SequentialAgent)
    │                   ├── PedagogyAgent                output_key=pedagogy_data
    │                   └── NarrativeAgentBrief          reads {pedagogy_data}
    │
    └── QA intent  →  single specialist agent (14 paths)
          gold_lap       → GoldLapAgent
          weather        → WeatherAdaptationAgent
          session_plan   → SessionPlannerAgent
          incident       → IncidentReviewAgent
          race_pace      → RacePaceAgent
          goal           → GoalSettingAgent
          mental_map     → MentalMapAgent
          voice_script   → VoiceScriptAgent
          lap_comparison → LapComparisonAgent
          corner         → CornerCoachAgent
          progress       → ProgressTrackerAgent
          setup          → SetupAdvisorAgent
          mindset        → MindsetCoachAgent
          agent_meta     → AgentMetaAgent
          telemetry      → TelemetryAgent  (default)
```

---

## PitwallOrchestrator

`BaseAgent` subclass at `src/pitwall/features/coaching/adk_agents.py`. `_run_async_impl(ctx)` reads `ctx.user_content.parts[0].text`, calls `_classify_intent()`, then `async for event in pipeline.run_async(ctx): yield event`.

**Intent classifier** — `_classify_intent(query: str) -> str` — evaluates keywords top-to-bottom, first match wins. **Order matters:** whole-flow intents (`debrief`, `brief`, `voice_script`) precede `corner` so that "brief me on T6" routes to `BriefPipeline`, not `CornerCoachAgent` (audit fix 2026-05-12).

| # | Keywords matched | Intent | Agent / pipeline |
|---|---|---|---|
| 1 | `debrief`, `how did i do`, `session summary`, `review my session` | `debrief` | DebriefPipeline |
| 2 | `brief`, `pre-session`, `before i go out`, `today's plan` | `brief` | BriefPipeline |
| 3 | `voice script(s)`, `cue script(s)`, `tts`, `pace note(s)`, `audio cue(s)`, `generate cue/voice/audio …` | `voice_script` | VoiceScriptAgent |
| 4 | `TN` / `turn N`, `carousel`, `bus stop` | `corner` | CornerCoachAgent |
| 5 | `gold lap`, `reference lap`, `AJ` | `gold_lap` | GoldLapAgent |
| 6 | `weather`, `fog`, `conditions`, `greasy`, `track temp` | `weather` | WeatherAdaptationAgent |
| 7 | `practice plan`, `laps available`, `i have N laps` | `session_plan` | SessionPlannerAgent |
| 8 | `incident`, `close call`, `scary`, `saved it`, `moment at` | `incident` | IncidentReviewAgent |
| 9 | `race pace`, `stint`, `degradation`, `tyre drop` | `race_pace` | RacePaceAgent |
| 10 | `pb target`, `lap time goal`, `target lap`, `set me a goal` | `goal` | GoalSettingAgent |
| 11 | `variance`, `consistency`, `consistent`, `inconsistent`, `mental map`, `repeatable`, `repeatability`, `stable` | `mental_map` | MentalMapAgent |
| 12 | `lap N vs`, `compare lap`, `why was lap`, `fastest vs slowest` | `lap_comparison` | LapComparisonAgent |
| 13 | `progress`, `improving`, `getting faster`, `over sessions` | `progress` | ProgressTrackerAgent |
| 14 | `setup`, `understeer`, `oversteer`, `balance`, `car feel` | `setup` | SetupAdvisorAgent |
| 15 | `frustrated`, `plateau`, `not working`, `motivation` | `mindset` | MindsetCoachAgent |
| 16 | `slowest`/`latency`/`tool call`/`agent trace` + `agent` | `agent_meta` | AgentMetaAgent |
|   | *(default)* | `telemetry` | TelemetryAgent |

**Routing escape hatch.** `POST /coach/ask` accepts an optional `intent`
field (`bp_coaching.py`) that bypasses `_classify_intent()` entirely. The
orchestrator reads `temp:intent_override` from session state and falls back
to the regex classifier only when the override is empty or not in
`_VALID_INTENTS`. Use this when the natural-language router would misroute
and you know which agent should run. Valid intents are the keys of the table
above.

---

## Pipelines

### DebriefPipeline

```python
_debrief_data_phase = ParallelAgent(
    name="DebriefDataPhase",
    sub_agents=[highlight_finder_agent, telemetry_agent, pedagogy_agent],
)
debrief_pipeline = SequentialAgent(
    name="DebriefPipeline",
    sub_agents=[_debrief_data_phase, _narrative_debrief],
)
```

Three data agents run concurrently. Each writes to `session.state` via `output_key`. `NarrativeAgentDebrief` runs after all three complete — wall-clock time is 1× the slowest data agent, not the sum.

### BriefPipeline

```python
brief_pipeline = SequentialAgent(
    name="BriefPipeline",
    sub_agents=[pedagogy_agent, _narrative_brief],
)
```

`PedagogyAgent` runs first, writes `pedagogy_data` to session state. `NarrativeAgentBrief` generates the pre-session brief from that structured context.

### Narrative agent instances

`_narrative_debrief` and `_narrative_brief` are separate `Agent` instances with identical instruction templates. Separate instances prevent session-state bleed if requests overlap. Both share the same template:

```
Session highlights: {highlights_data}
Telemetry analysis: {telemetry_data}
Pedagogy context:   {pedagogy_data}

[Output format rules + EMOTION tag instruction]
```

A third instance `narrative_agent` is used for QA paths.

---

## Agent catalogue

17 specialist agents exposed via `AGENT_REGISTRY` (`/coach/agents`):

**QA agents (15)** — TelemetryAgent, LapComparisonAgent, CornerCoachAgent,
ProgressTrackerAgent, SetupAdvisorAgent, MindsetCoachAgent, GoldLapAgent,
WeatherAdaptationAgent, SessionPlannerAgent, IncidentReviewAgent,
RacePaceAgent, GoalSettingAgent, MentalMapAgent, VoiceScriptAgent,
AgentMetaAgent.

**Pipeline-only data agents (2)** in the registry but never routed by
`_classify_intent` — they run inside DebriefPipeline / BriefPipeline:
HighlightFinderAgent, PedagogyAgent.

Three additional `Agent` instances exist internally and are NOT in the
registry: `NarrativeAgentBrief`, `NarrativeAgentDebrief`, and the three
`*AgentDebrief` / `*AgentBrief` pipeline copies of TelemetryAgent /
HighlightFinderAgent / PedagogyAgent. They share identical instruction
templates with their siblings; separate instances prevent session-state
bleed across overlapping requests.

All agents share the same `_model` symbol set at module-load by the
backend selector — see [Model backend selector](#model-backend-selector) below.
Agent definitions are backend-agnostic: the selector resolves to one of
`LitertLmModel(...)`, `Gemini(base_url=..., model=...)`, or
`LiteLlm(api_base=..., api_key=..., model=...)`, and every agent picks it up
identically.

### Pipeline data agents (with `output_key`)

| Agent | `output_key` | Tools |
|---|---|---|
| `TelemetryAgent` | `telemetry_data` | `query_pitwall_db`, `get_session_highlights` |
| `HighlightFinderAgent` | `highlights_data` | `get_session_highlights`, `query_pitwall_db` |
| `PedagogyAgent` | `pedagogy_data` | `query_pitwall_db` |
| `NarrativeAgent` / `NarrativeAgentDebrief` / `NarrativeAgentBrief` | *(none)* | *(none)* |

### QA specialist agents

| Agent | Tools |
|---|---|
| `LapComparisonAgent` | `get_lap_delta`, `query_pitwall_db` |
| `CornerCoachAgent` | `get_corner_history`, `query_pitwall_db` |
| `ProgressTrackerAgent` | `get_progress_report`, `query_pitwall_db` |
| `SetupAdvisorAgent` | `get_setup_indicators`, `query_pitwall_db` |
| `MindsetCoachAgent` | `get_progress_report`, `get_corner_history`, `query_pitwall_db` |
| `GoldLapAgent` | `get_gold_lap_comparison`, `query_pitwall_db` |
| `WeatherAdaptationAgent` | `get_weather_adaptation_context`, `query_pitwall_db` |
| `SessionPlannerAgent` | `get_session_plan_context`, `query_pitwall_db` |
| `IncidentReviewAgent` | `get_incident_moments`, `query_pitwall_db` |
| `RacePaceAgent` | `get_race_pace_model`, `query_pitwall_db` |
| `GoalSettingAgent` | `get_goal_targets`, `get_progress_report`, `query_pitwall_db` |
| `MentalMapAgent` | `get_track_variance_map`, `query_pitwall_db` |
| `VoiceScriptAgent` | `get_audio_script_context`, `save_voice_scripts` |
| `AgentMetaAgent` | `get_agent_telemetry` |

---

## Tools specification

All 15 tools live in `src/pitwall/adk_tools.py`. All decorated with `@_adk_tool` (falls back to identity decorator when `google-adk` is not installed).

### `query_pitwall_db(sql)`
Read-only DuckDB query. Safety layer: rejects non-SELECT, auto-injects `LIMIT 500`.
Tables: `laps`, `telemetry`, `coaching_notes`, `telemetry_signals`, `sessions`, `driver_events`, `llm_friction`, `conversations`, `agent_traces`.

### `get_lap_delta(session_id, lap_a, lap_b)`
Frame-by-frame delta between two laps: time, speed, coast pct.

### `get_corner_history(driver_id, corner_name, n_sessions=10)`
Grade history + coaching notes + improvement trend for one corner across N sessions.

### `get_progress_report(driver_id, n_sessions=10)`
Multi-session arc: lap time trend, improving/regressing/stable corners, plateau detection.

### `get_setup_indicators(session_id)`
Telemetry patterns indicating car balance issues: coast ratio, steer oscillation, brake pressure.

### `get_session_highlights(session_id)`
Best lap, peak grip moment, coaching note counts, worst coast lap.

### `get_gold_lap_comparison(session_id)`
Driver's best lap vs AJ's gold standard. Corner-by-corner speed gap + lap-time leverage weights.

### `get_weather_adaptation_context(hour_local)`
Sonoma's 4 weather phases → concrete line, braking, and tyre warm-up advice per corner.

### `get_session_plan_context(driver_id, n_laps=10)`
Weakest corners + leverage weights → structured N-lap practice plan data.

### `get_incident_moments(session_id, combo_g_threshold, steer_spike_threshold)`
Over-limit grip events, emergency brakes, steering saves from telemetry.

### `get_race_pace_model(session_id)`
Lap degradation model: quali pace, race pace median, consistency score, degradation s/lap.

### `get_goal_targets(driver_id)`
Realistic PB targets from improvement rate. Top 3 corners by `(100 - score) × leverage`.

### `get_track_variance_map(session_id)`
Corner-by-corner speed variance from telemetry. High CV = inconsistent.

### `get_agent_telemetry(n_recent=50)`
Queries `agent_traces` table: slowest agents by avg latency, top tools by call count, recent trace rows.

### `get_audio_script_context(corner_name, driver_level)`
Returns corner tip, leverage pct, TROD voice examples, and script guidelines for VoiceScriptAgent.

### `save_voice_scripts(corner_name, scripts)`
Writes generated TTS phrases to `tools/audio_cache/<corner>.json`. Uses `fcntl.flock(LOCK_EX)` + `os.replace()` for atomic concurrent writes.

---

## Model backend selector

Per [ADR-022](adr/022-openai-compatible-backend-selector.md) the paddock model
client is selected at process start by `PITWALL_ADK_BACKEND`. The default is
`litertlm` — existing deployments need no change.

```python
# adk_agents.py — module load
_BACKEND  = os.getenv("PITWALL_ADK_BACKEND", "openai").lower()
_MODEL_ID = get_env_with_legacy(
    "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL", "gemma3n-e2b")
_MODEL_URL = get_env_with_legacy(
    "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
    "http://localhost:8099/v1")

if _BACKEND == "engine":
    _model = LitertLmModel(model=_MODEL_ID)               # in-process
elif _BACKEND == "openai":
    _model = LiteLlm(                                      # OpenAI-compatible HTTP
        model=_MODEL_ID,
        api_base=_MODEL_URL,
        api_key=get_env_with_legacy(
            "PITWALL_ADK_OPENAI_API_KEY", "PITWALL_LITERT_API_KEY",
            "lit-serve-not-required"),
    )
else:                                                      # default: lit serve
    _model = Gemini(model=_MODEL_ID, base_url=_MODEL_URL)
```

### Environment variables

| Variable                       | Default                              | Used by                          |
| ------------------------------ | ------------------------------------ | -------------------------------- |
| `PITWALL_ADK_BACKEND`          | `openai`                             | selector (`engine` \| `litertlm` \| `openai`) |
| `PITWALL_ADK_OPENAI_URL`       | `http://localhost:8099/v1`           | `litertlm`, `openai` (HTTP base); shared with the warm-path `LitertCoach`. Legacy: `PITWALL_LITERT_URL` |
| `PITWALL_ADK_OPENAI_MODEL`     | `gemma3n-e2b`                        | model id (must match what LocalLLM has loaded). Legacy: `PITWALL_LITERT_MODEL` |
| `PITWALL_ADK_OPENAI_API_KEY`   | `lit-serve-not-required`             | `openai` — set to LocalLLM's signed bearer token. Legacy: `PITWALL_LITERT_API_KEY` |
| `PITWALL_LITERT_SIDECAR_URL`   | `http://127.0.0.1:8080`              | LiteRT-LM Kotlin sidecar URL (`engine` backend). Legacy: `PITWALL_LITERTLM_URL` |
| `PITWALL_LITERT_SIDECAR_MODEL` | `gemma-4-e2b`                        | LiteRT-LM Kotlin sidecar model id. Legacy: `PITWALL_LITERTLM_MODEL` |
| `PITWALL_LITERTLM_PATH`        | *(unset)*                            | `engine` (`.litertlm` bundle path) |
| `PITWALL_LITERTLM_BUDGET`      | `30000`                              | `engine` (KV-cache char budget)  |
| `PITWALL_LITERT_HTTP_TIMEOUT_S` | `30`                                | warm-path HTTP client timeout    |

> **Legacy aliases (`PITWALL_LITERT_URL`, `PITWALL_LITERT_MODEL`,
> `PITWALL_LITERT_API_KEY`, `PITWALL_LITERTLM_URL`, `PITWALL_LITERTLM_MODEL`)
> are still read for backward compatibility — they emit a `DeprecationWarning`
> on first use.** The rename clarifies that the `PITWALL_ADK_OPENAI_*` family
> configures the ADK→OpenAI-compatible HTTP shim, while the
> `PITWALL_LITERT_SIDECAR_*` family configures the Kotlin LiteRT-LM sidecar.

> **Default flipped 2026-05-12 (ADR-022).** Defaults now point at LocalLLM
> (`:8099/v1`). To restore the previous `lit serve` behaviour explicitly:
> `PITWALL_ADK_BACKEND=litertlm PITWALL_ADK_OPENAI_URL=http://localhost:8001`.

### Choosing a backend

| Backend     | Pick when                                                                                | Skip when                                              |
| ----------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `openai`    | **Pixel field deployment with LocalLLM** — also: dev box with Ollama / LM Studio / vLLM. | You haven't installed LocalLLM and don't have any OpenAI-compat server running. |
| `engine`    | Termux/Pixel deployment where you want one process and don't want to install LocalLLM.   | You're already running LocalLLM — use `openai` instead. |
| `litertlm`  | Desktop dev with `lit serve` already up; legacy compatibility.                           | You don't have `lit serve` running locally.            |

### What's identical across backends

- The 18 agents, the orchestrator, the pipelines, all 15 tools.
- KV-cache reuse via persistent ADK sessions per driver.
- The `agent_traces` DuckDB schema and `PitwallTracingPlugin` hook.
- The `[EMOTION:x]` tag contract in every system prompt.
- The privacy guarantee — every backend speaks to a model on the same host as the bridge.

### What differs

- `engine` skips the HTTP hop entirely and shares process memory with the warm-path coach.
- `openai` uses `LiteLlm` (litellm) which normalises tool-call shape from OpenAI to ADK's internal schema. ADK handles this transparently; the agents see the same tool-call objects either way.
- `litertlm` uses Gemini-native function-calling shape directly to `lit serve`.

---

## Runner and invocation

```python
# adk_agents.py — all internal
_session_service = InMemorySessionService()
_runner = Runner(
    agent=coach_orchestrator,
    app_name="pitwall",
    session_service=_session_service,
    plugins=[PitwallTracingPlugin()],
)

# Public API — src/pitwall/__main__.py calls these
run_adk(prompt, user_id="driver") -> str      # sync, thread-safe via asyncio.run()
reset_driver_session(user_id)                  # expire session (call at /session/start)
get_pending_traces() -> list[dict]             # drain trace buffer for DuckDB write
```

`BaseAgent` has no `.run()` shortcut — `Runner.run_async()` is the only path.

---

## KV cache and persistent sessions

KV reuse happens at the ADK session layer — pitwall keeps the same
`InMemorySessionService` session alive per driver per process, so every
backend benefits:

- **`engine`** — `LitertLmModel` keeps a Conversation per system prompt; reused turns skip system-instruction prefill (~30–50% cheaper). Direct in-process API, no transport cost.
- **`litertlm`** — `lit serve` clones KV tensors for a reused session (<10 ms) rather than re-prefilling the system instruction tokens.
- **`openai`** — depends on the upstream server. Ollama and llama.cpp's `--server` both keep a per-context KV slot warm; vLLM exposes prefix caching. ADK's session reuse keeps the prompt prefix stable, which is what those servers key on.

```
_driver_sessions: dict[str, str]    # user_id → ADK session_id
_session_turn_count: dict[str, int] # auto-reset at _SESSION_MAX_TURNS = 50
```

**Lifecycle:**
1. `POST /session/start` → `reset_driver_session(driver_id)` — intentional cold reset, acceptable once per day
2. First `run_adk()` call → creates ADK session, stores in `_driver_sessions`
3. Subsequent calls same day → `_session_service.get_session()` → LiteRT-LM clones KV cache
4. After 50 turns → auto-rotation to prevent context overflow
5. Process restart → all sessions lost (InMemory), next call creates fresh session

**Expected impact:** System instruction tokens (~100–300 per agent) skip re-prefill on warm calls → ~30–50% prefill reduction → ~0.5–3 s saved per call on Tensor G5 NPU.

---

## Agent telemetry (DuckDB)

`PitwallTracingPlugin(BasePlugin)` hooks into `Runner` and logs every agent run and tool call to a module-level deque. `src/pitwall/__main__.py` drains it after every `run_adk()` call.

```sql
CREATE TABLE agent_traces (
    id          INTEGER PRIMARY KEY,
    trace_id    VARCHAR,    -- ADK session UUID — groups one run_adk() call
    pitwall_sid VARCHAR,    -- pitwall session_id (empty for Q&A)
    agent_name  VARCHAR,
    event_type  VARCHAR,    -- 'agent' | 'tool'
    detail      VARCHAR,    -- tool name for tool events
    latency_ms  DOUBLE,     -- wall-clock ms for agent events; NULL for tool events
    success     BOOLEAN,
    ts          TIMESTAMP
);
```

**Useful queries:**

```sql
-- Which agents are slowest?
SELECT agent_name, ROUND(AVG(latency_ms), 1) as avg_ms, COUNT(*) as runs
FROM agent_traces WHERE event_type = 'agent'
GROUP BY agent_name ORDER BY avg_ms DESC;

-- Most-called tools
SELECT detail, COUNT(*) FROM agent_traces
WHERE event_type = 'tool' GROUP BY detail ORDER BY 2 DESC;

-- Full trace for one run_adk() call
SELECT agent_name, event_type, detail, latency_ms, ts
FROM agent_traces WHERE trace_id = ? ORDER BY ts;
```

`AgentMetaAgent` can query this table directly via `get_agent_telemetry` tool.

---

## Conversation persistence

All brief/debrief narratives and Q&A turns persist to the `conversations` table.

```sql
CREATE TABLE conversations (
    id           INTEGER PRIMARY KEY,
    session_id   VARCHAR,
    driver_id    VARCHAR,
    role         VARCHAR,   -- 'coach_brief' | 'coach_debrief' | 'user' | 'assistant'
    text         TEXT,
    focus_items  VARCHAR,   -- JSON array
    emotion      VARCHAR,
    recorded_at  TIMESTAMP DEFAULT now()
);
```

Q&A turns buffer in `_qa_histories` (in-memory, TTL = 1 hour) and flush to DuckDB on `POST /coach/ask/end`.

**Read endpoints:**
- `GET /conversations/<session_id>` — all turns for a session
- `GET /conversations/driver/<driver_id>` — brief/debrief history across sessions

---

## Bridge integration points

| Bridge call | What it does |
|---|---|
| `run_adk(prompt, user_id)` | Runs `PitwallOrchestrator` via `Runner`, returns final text |
| `_drain_adk_traces(pitwall_sid)` | Flushes `get_pending_traces()` → `agent_traces` DuckDB |
| `_reset_adk_session(driver_id)` | Expires ADK session (cold KV reset at session start) |
| `POST /session/start` | Calls `_reset_adk_session(driver_id)` automatically |
| `POST /coach/ask` | Calls `run_adk(prompt)`, buffers turns in `_qa_histories` |
| `POST /coach/ask/end` | Flushes `_qa_histories` to `conversations` table |
| `GET /coach/agents` | Returns `AGENT_REGISTRY` for Vue PWA discovery |
| `GET /coach/traces?session_id=&limit=&since_ts=` | Recent rows from `agent_traces` DuckDB table. Always HTTP 200; `available: false` when `google-adk` or DuckDB is absent. Response: `{available, traces:[{trace_id, pitwall_sid, agent_name, event_type, detail, latency_ms, success, ts}], count, reason?}`. `limit` defaults to 200 (max 1000); `since_ts` enables incremental polling. |

---

## What stays unchanged

- `RuleCoach` and `CoachArbiter` — hot path, untouched
- `LitertCoach.propose()` — still delegates to `RuleCoach` per ADR-017
- All existing Flask endpoints and their JSON contracts
- `llm_friction` table — still receives LLM performance metadata
- `litert_lm.Engine` in-process runtime (E2B, hot path)

---

## Startup recipes

### A. `openai` — Pixel 10 + LocalLLM APK *(recommended)*

The production deployment story: install [LocalLLM](https://github.com/mlnomadpy/localllm)
as a regular Android APK, pick a Gemma 4 `.litertlm` from its in-app catalog,
and let the bridge in Termux speak to it over `127.0.0.1`.

```bash
# On the Pixel — one-time setup:
#   1. Install LocalLLM APK (adb install -r app-debug.apk, or build from
#      github.com/mlnomadpy/localllm)
#   2. Open LocalLLM → Catalog → download a Gemma 4 .litertlm
#      (e.g. gemma-4-E2B-it or gemma-4-E4B-it from litert-community)
#   3. LocalLLM autostarts its HTTP server on :8099 with a signed bearer token
#   4. Copy the bearer token from LocalLLM → Settings

# In a Termux shell — pip install 'google-adk[litellm]' once, then:
PITWALL_ADK_BACKEND=openai \
PITWALL_ADK_OPENAI_URL=http://localhost:8099/v1 \
PITWALL_ADK_OPENAI_MODEL=gemma-4-e2b-it \
PITWALL_ADK_OPENAI_API_KEY="<paste-token-from-LocalLLM-Settings>" \
python3 -m src.pitwall \
    --litert-model ~/storage/shared/Pitwall/models/gemma-4-E2B-it.litertlm
# Legacy aliases still work: PITWALL_LITERT_URL / PITWALL_LITERT_MODEL /
# PITWALL_LITERT_API_KEY — they emit a DeprecationWarning on first use.
```

The bridge sends `POST /v1/chat/completions` to LocalLLM with the bearer
token. LocalLLM streams the response via SSE. Two APKs, one phone, one
localhost hop, zero cloud. The hot-path E2B engine still loads in-process
in the bridge for the < 100 ms warm/hot tier — only the paddock LLM moves
to LocalLLM.

### B. `engine` — Pixel 10 collapsed to one process

If you don't want a second APK on the phone, the bridge can host the
paddock model itself in-process, reusing the warm-path engine:

```bash
PITWALL_ADK_BACKEND=engine \
PITWALL_LITERTLM_PATH=~/storage/shared/Pitwall/models/gemma-4-E2B-it.litertlm \
python3 -m src.pitwall
```

No LocalLLM, no `lit serve`. One model resident in the bridge's process.
The trade-off: no GPU delegate access from inside Termux, and a model-
runtime crash takes the bridge down with it.

### C. `litertlm` — desktop dev with `lit serve` *(legacy / default)*

The original ADK doc'd path. Kept for desktop development and for any
existing deployment that's already wired this way.

```bash
# Terminal 1
lit pull gemma-4-e4b
lit serve --port 8001

# Terminal 2 — PITWALL_ADK_BACKEND defaults to "litertlm"
cd ~/pitwall
python3 -m src.pitwall
```

### D. `openai` — dev machine with Ollama / LM Studio / vLLM

Same `openai` backend, different OpenAI-compatible server. Useful for
authoring prompts on a laptop without installing LocalLLM:

```bash
# Ollama (macOS)
PITWALL_ADK_BACKEND=openai \
PITWALL_ADK_OPENAI_URL=http://localhost:11434/v1 \
PITWALL_ADK_OPENAI_MODEL=gemma2:2b \
python3 -m src.pitwall

# LM Studio:    PITWALL_ADK_OPENAI_URL=http://localhost:1234/v1
# llama.cpp:    PITWALL_ADK_OPENAI_URL=http://localhost:8080/v1
# vLLM:         PITWALL_ADK_OPENAI_URL=http://localhost:8000/v1
# (Legacy PITWALL_LITERT_URL still honoured with a DeprecationWarning.)
```

Every backend dials only `localhost`. No hosted LLM is involved at any point.
