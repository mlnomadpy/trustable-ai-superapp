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
3. **LocalLLM is the sole paddock LLM transport — never a hosted API.** Per [ADR-024](adr/024-localllm-sole-llm-transport.md) (superseding [ADR-022](adr/022-openai-compatible-backend-selector.md)), every ADK call goes through `LiteLlm` to [LocalLLM](https://github.com/mlnomadpy/localllm) on `127.0.0.1:8099/v1`. `google-adk` and `litellm` are base dependencies of `apps/edge-daemon` — the bridge fails to start without them. The earlier `PITWALL_ADK_BACKEND` selector and its `engine` / `litertlm` branches are retired.

    LocalLLM is a separate Apache-2.0 Android APK that hosts LiteRT-LM in a
    native Android process with GPU/NPU delegate access via LiteRT's AUTO
    backend, owns model lifecycle through its in-app catalog, and speaks
    OpenAI's `chat.completions` with SSE streaming and signed-bearer-token
    auth. The same `LiteLlm` client also covers Ollama / LM Studio /
    llama.cpp / vLLM on dev workstations — point `PITWALL_ADK_OPENAI_URL`
    at them and nothing else changes.

    **The warm path is on the same transport.**
    `LitertCoach.brief()` and `LitertCoach.debrief()`
    ([coach_engine.py](coaching-engine.md)) post directly to
    LocalLLM's `/v1/chat/completions` via stdlib `urllib.request` per
    [ADR-025](adr/025-warm-path-localllm-only.md). The in-process
    `litert_lm.Engine` warm-path branch was retired; warm and paddock
    share one transport contract.

4. **One transport, three tiers:**

    | Path | Runtime | Model | How invoked | Latency budget |
    |---|---|---|---|---|
    | In-drive (hot) | `RuleCoach` + canonical phrases | — | Pure Python | < 100 ms |
    | Warm (brief / debrief) | LocalLLM (HTTP → `127.0.0.1:8099/v1`) | Gemma 4 E2B | `urllib.request` POST | 2–4 s brief / 8–15 s debrief |
    | Paddock (ADK) | LocalLLM via `LiteLlm` (HTTP → `127.0.0.1:8099/v1`) | Gemma 4 E4B / E2B | `LiteLlm(model="openai/<id>", api_base=...)` | 2–15 s |

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

23 specialist agents exposed via `AGENT_REGISTRY` (`/coach/agents`).

**Foundation QA agents (15, ADR-019/020/021)** — TelemetryAgent,
LapComparisonAgent, CornerCoachAgent, ProgressTrackerAgent, SetupAdvisorAgent,
MindsetCoachAgent, GoldLapAgent, WeatherAdaptationAgent, SessionPlannerAgent,
IncidentReviewAgent, RacePaceAgent, GoalSettingAgent, MentalMapAgent,
VoiceScriptAgent, AgentMetaAgent.

**Phase-2 AiM-aware specialists (6, 2026-05-28)** — each owns one AiM signal
domain end-to-end and publishes its findings under a named `output_key` that
the brief / debrief narrative templates cite:

- **TireManagerAgent** (`tire_data`) — TPMS pressure / temperature window
  + alarms. Cold→hot delta, per-corner balance, cold-pressure target advice.
- **HandlingBalanceAgent** (`handling_data`) — measured understeer /
  oversteer per corner via yaw rate × steering bicycle model (E46 M3
  wheelbase 2.731 m, ratio 15.4:1). Surfaces YAML §7 sign-convention warning.
- **EngineHealthAgent** (`engine_health_data`) — S54 vitals: oil-pressure
  floor under load, coolant / oil temp drift, fuel pressure under brake.
  Sentinel-aware (drops AiM `0xFFFF` no-reading marker).
- **TractionAgent** (`traction_data`) — wheelspin / lockup events from
  per-wheel speed deltas, attributed to corner segments.
- **InputQualityAgent** (`input_quality_data`) — steering oscillation,
  throttle modulation rate, brake-release shape; 0–100 smoothness score.
- **SafetyMonitorAgent** (`safety_data`) — ABS / DSC / MIL / TPMS alarm
  timeline. Explains pace drops via active safety events.

**Pipeline-only data agents (2)** in the registry but never routed by
`_classify_intent` — they run inside DebriefPipeline / BriefPipeline:
HighlightFinderAgent, PedagogyAgent.

Additional internal `Agent` instances exist and are NOT in the registry:
`NarrativeAgentBrief`, `NarrativeAgentDebrief`, the 9 pipeline copies of
the data agents (`TelemetryAgentDebrief`, `HighlightFinderAgentDebrief`,
`PedagogyAgentDebrief`, `TireManagerAgentDebrief`, etc.), and 3 brief-side
copies (`PedagogyAgentBrief`, `TireManagerAgentBrief`,
`EngineHealthAgentBrief`, `SafetyMonitorAgentBrief`). They share identical
instruction templates with their siblings; separate instances prevent
session-state bleed across overlapping requests and satisfy ADK's
single-parent invariant inside the parallel data phases.

All agents share the same `_model` symbol set at module-load — a
`LiteLlm(model="openai/<id>", api_base=..., api_key=...)` instance dialling
LocalLLM. See [Model transport](#model-transport) below.

### Pipeline data agents (with `output_key`)

| Agent | `output_key` | Tools |
|---|---|---|
| `TelemetryAgent` | `telemetry_data` | `query_pitwall_db`, `get_session_highlights`, `get_safety_events` |
| `HighlightFinderAgent` | `highlights_data` | `get_session_highlights`, `get_input_smoothness`, `get_tire_thermal_window`, `query_pitwall_db` |
| `PedagogyAgent` | `pedagogy_data` | `query_pitwall_db` |
| `TireManagerAgent` | `tire_data` | `get_tire_thermal_window`, `query_pitwall_db` |
| `HandlingBalanceAgent` | `handling_data` | `get_handling_balance`, `query_pitwall_db` |
| `EngineHealthAgent` | `engine_health_data` | `get_engine_health_timeline`, `query_pitwall_db` |
| `TractionAgent` | `traction_data` | `get_traction_events`, `query_pitwall_db` |
| `InputQualityAgent` | `input_quality_data` | `get_input_smoothness`, `query_pitwall_db` |
| `SafetyMonitorAgent` | `safety_data` | `get_safety_events`, `query_pitwall_db` |
| `NarrativeAgentDebrief` / `NarrativeAgentBrief` | *(none)* | *(none)* |

### QA specialist agents

| Agent | Tools |
|---|---|
| `LapComparisonAgent` | `get_lap_delta`, `get_engine_health_timeline`, `get_safety_events`, `query_pitwall_db` |
| `CornerCoachAgent` | `get_corner_history`, `get_handling_balance`, `get_traction_events`, `query_pitwall_db` |
| `ProgressTrackerAgent` | `get_progress_report`, `query_pitwall_db` |
| `SetupAdvisorAgent` | `get_setup_indicators`, `get_handling_balance`, `get_input_smoothness`, `get_tire_thermal_window`, `query_pitwall_db` |
| `MindsetCoachAgent` | `get_progress_report`, `get_corner_history`, `query_pitwall_db` |
| `GoldLapAgent` | `get_gold_lap_comparison`, `query_pitwall_db` |
| `WeatherAdaptationAgent` | `get_weather_adaptation_context`, `get_tire_thermal_window`, `query_pitwall_db` |
| `SessionPlannerAgent` | `get_session_plan_context`, `get_tire_thermal_window`, `query_pitwall_db` |
| `IncidentReviewAgent` | `get_incident_moments`, `get_safety_events`, `get_traction_events`, `query_pitwall_db` |
| `RacePaceAgent` | `get_race_pace_model`, `get_engine_health_timeline`, `get_tire_thermal_window`, `query_pitwall_db` |
| `GoalSettingAgent` | `get_goal_targets`, `get_progress_report`, `query_pitwall_db` |
| `MentalMapAgent` | `get_track_variance_map`, `query_pitwall_db` |
| `VoiceScriptAgent` | `get_audio_script_context`, `save_voice_scripts`, `query_pitwall_db` |
| `AgentMetaAgent` | `get_agent_telemetry` |

### Brief / debrief narrative-slot map

The narrative templates read these `output_key` slots when assembling the
final brief / debrief text. Empty slots collapse to `""` via ADK's `{key?}`
optional binding — pipelines stay valid when a data agent has nothing to say
(e.g. no safety events on a clean session).

```
{highlights_data?}    ← HighlightFinderAgentDebrief
{telemetry_data?}     ← TelemetryAgentDebrief
{pedagogy_data?}      ← PedagogyAgent{Brief,Debrief}
{tire_data?}          ← TireManagerAgent{Brief,Debrief}
{handling_data?}      ← HandlingBalanceAgentDebrief    (debrief only)
{engine_health_data?} ← EngineHealthAgent{Brief,Debrief}
{traction_data?}      ← TractionAgentDebrief           (debrief only)
{input_quality_data?} ← InputQualityAgentDebrief       (debrief only)
{safety_data?}        ← SafetyMonitorAgent{Brief,Debrief}
```

DebriefDataPhase = `ParallelAgent` over 9 data agents. BriefDataPhase =
`ParallelAgent` over 4 (pedagogy + tire + engine + safety — the domains
that carry from the prior session into today's pre-brief).

---

## Tools specification

All 21 tools live in `apps/edge-daemon/pitwall/adk_tools.py`. All decorated with `@_adk_tool` (an identity passthrough — ADK 1.32 registers tools by being passed into `Agent(tools=[...])` directly).

### Phase-2 AiM-aware tools (added 2026-05-28)

- `get_tire_thermal_window(session_id)` — per-corner TPMS pressure / temperature window + alarm bitfield timeline (air leak / low temp / sensor fail). Source: `telemetry_signals` JOIN `signal_registry` on `tpms_press_*_bar`, `tpms_temp_*_c`, `tpms_alm_*`.
- `get_handling_balance(session_id, corner_name?)` — measured vs. expected yaw rate per corner via bicycle model with E46 M3 constants. Folds cumulative distance via `% TRACK_LENGTH_M`. Flags YAML §7 sign-convention warning when counter-steer events > 50 % of samples.
- `get_engine_health_timeline(session_id)` — oil / water / fuel pressure + oil temp aggregates and anomaly markers (oil-pressure starvation under RPM > 3000 + throttle > 10 %, coolant > 105 °C). Sentinel-aware: drops `0xFFFF` markers (psi → 4519 bar after scale per YAML §8).
- `get_traction_events(session_id, slip_threshold_kmh=5.0)` — wheelspin (rear-axle > front-axle under throttle) and lockup (body > front-axle under brake) events, attributed to corner segments via lap-modulo distance.
- `get_input_smoothness(session_id)` — steering oscillation (frame-to-frame stddev), throttle modulation rate (mean `|Δ throttle|`), median brake-release delta, brake-release event count, 0–100 smoothness score, verdict (`smooth` / `competent` / `choppy`).
- `get_safety_events(session_id)` — ABS / DSC / MIL / brake-switch / TPMS alarm timeline. Returns ordered events with first-occurrence timestamp and total count.

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

## Model transport

Per [ADR-024](adr/024-localllm-sole-llm-transport.md) (superseding
[ADR-022](adr/022-openai-compatible-backend-selector.md)) the paddock tier
has a **single** transport — `LiteLlm` dialling LocalLLM on
`127.0.0.1:8099/v1`. There is no env-selectable alternative; reaching a
different OpenAI-compatible server (Ollama, LM Studio, llama.cpp `--server`,
vLLM, …) is done by pointing `PITWALL_ADK_OPENAI_URL` at it.

```python
# adk_agents.py — module load (ADR-024)
_MODEL_ID = get_env_with_legacy(
    "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL", "gemma3n-e2b")
_MODEL_URL = get_env_with_legacy(
    "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
    "http://localhost:8099/v1")
_LITELLM_MODEL = _MODEL_ID if "/" in _MODEL_ID else f"openai/{_MODEL_ID}"
_model = LiteLlm(
    model=_LITELLM_MODEL,                              # litellm provider prefix
    api_base=_MODEL_URL,                               # → LocalLLM at :8099/v1
    api_key=get_env_with_legacy(
        "PITWALL_ADK_OPENAI_API_KEY", "PITWALL_LITERT_API_KEY",
        "lit-serve-not-required"),
)
```

### Environment variables

| Variable                       | Default                              | Purpose                          |
| ------------------------------ | ------------------------------------ | -------------------------------- |
| `PITWALL_ADK_OPENAI_URL`       | `http://localhost:8099/v1`           | LocalLLM endpoint; shared with the warm-path `LitertCoach`. Legacy: `PITWALL_LITERT_URL` |
| `PITWALL_ADK_OPENAI_MODEL`     | `gemma3n-e2b`                        | Model id (must match what LocalLLM has loaded). Legacy: `PITWALL_LITERT_MODEL` |
| `PITWALL_ADK_OPENAI_API_KEY`   | `lit-serve-not-required`             | LocalLLM signed bearer token. Legacy: `PITWALL_LITERT_API_KEY` |
| `PITWALL_ADK_TIMEOUT_S`        | `45`                                 | Per-request timeout |
| `PITWALL_ADK_CHAR_BUDGET`      | `60000`                              | ADK session rotation char budget |
| `PITWALL_LITERT_HTTP_TIMEOUT_S` | `30`                                | Warm-path HTTP client timeout    |

Retired by ADR-024: `PITWALL_ADK_BACKEND`, `PITWALL_LITERTLM_PATH`,
`PITWALL_LITERTLM_BUDGET`. The legacy `PITWALL_LITERT_*` aliases on
`URL` / `MODEL` / `API_KEY` are still read (with a `DeprecationWarning` on
first use) via `pitwall._env.get_env_with_legacy`.

### What's load-bearing identical to ADR-019/021

- The 18 agents, the orchestrator, the pipelines, all 15 tools.
- KV-cache reuse via persistent ADK sessions per driver.
- The `agent_traces` DuckDB schema and `PitwallTracingPlugin` hook.
- The `[EMOTION:x]` tag contract in every system prompt.
- The privacy guarantee — `LiteLlm` speaks only to the configured `api_base`, which defaults to `127.0.0.1`.
- `LiteLlm` (litellm) normalises tool-call shape from OpenAI to ADK's internal schema; agents see ADK-shaped tool calls regardless of which OpenAI-compatible server is on the other end.

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
`InMemorySessionService` session alive per driver per process. The actual
KV-cache reuse then depends on the upstream OpenAI-compatible server:

- **LocalLLM (production target)** — LiteRT-LM 0.11 keeps a per-context KV
  slot warm across turns; reused sessions skip system-instruction prefill.
- **Ollama / llama.cpp `--server`** — same per-context KV reuse.
- **vLLM** — exposes prefix caching keyed on the prompt prefix, which ADK's
  session reuse keeps stable.

In all cases ADK's persistent-session strategy guarantees the prompt prefix
the upstream server sees is byte-identical across turns, which is the
precondition every implementation keys on.

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
- `RuleCoach` + canonical phrase library (hot path)

---

## Startup recipes

### A. Pixel 10 + LocalLLM APK *(production)*

Install [LocalLLM](https://github.com/mlnomadpy/localllm) as a regular
Android APK, pick a Gemma 4 `.litertlm` from its in-app catalog, copy the
bearer token from its Settings screen, and let the bridge in Termux talk to
it over `127.0.0.1`. `google-adk` and `litellm` are base deps of
`apps/edge-daemon`, so a fresh `uv sync` is all you need.

```bash
# On the Pixel — one-time setup:
#   1. Install LocalLLM APK (adb install -r app-debug.apk, or build from
#      github.com/mlnomadpy/localllm)
#   2. Open LocalLLM → Catalog → download a Gemma 4 .litertlm
#      (e.g. gemma-4-E2B-it or gemma-4-E4B-it from litert-community)
#   3. LocalLLM autostarts its HTTP server on :8099 with a signed bearer token
#   4. Copy the bearer token from LocalLLM → Settings

# In a Termux shell (deps already resolved by uv sync):
PITWALL_ADK_OPENAI_URL=http://localhost:8099/v1 \
PITWALL_ADK_OPENAI_MODEL=gemma-4-e2b-it \
PITWALL_ADK_OPENAI_API_KEY="<paste-token-from-LocalLLM-Settings>" \
python3 -m pitwall \
    --litert-model ~/storage/shared/Pitwall/models/gemma-4-E2B-it.litertlm
# Legacy aliases still work: PITWALL_LITERT_URL / PITWALL_LITERT_MODEL /
# PITWALL_LITERT_API_KEY — they emit a DeprecationWarning on first use.
```

The bridge sends `POST /v1/chat/completions` to LocalLLM with the bearer
token; LocalLLM streams the response via SSE. Two APKs, one phone, one
localhost hop, zero cloud. The hot-path E2B engine still loads in-process
in the bridge for the < 100 ms warm/hot tier — only the paddock LLM moves
to LocalLLM.

### B. Dev workstation with Ollama / LM Studio / llama.cpp / vLLM

Same transport, different OpenAI-compatible server. Point
`PITWALL_ADK_OPENAI_URL` at whatever you've got running:

```bash
# Ollama (macOS)
PITWALL_ADK_OPENAI_URL=http://localhost:11434/v1 \
PITWALL_ADK_OPENAI_MODEL=gemma2:2b \
python3 -m pitwall

# LM Studio:    PITWALL_ADK_OPENAI_URL=http://localhost:1234/v1
# llama.cpp:    PITWALL_ADK_OPENAI_URL=http://localhost:8080/v1
# vLLM:         PITWALL_ADK_OPENAI_URL=http://localhost:8000/v1
# (Legacy PITWALL_LITERT_URL still honoured with a DeprecationWarning.)
```

The bridge dials only `localhost`. No hosted LLM is involved at any point.

> **Retired recipes (per [ADR-024](adr/024-localllm-sole-llm-transport.md)):**
> the in-process `PITWALL_ADK_BACKEND=engine` path and the
> separate-`lit serve` `PITWALL_ADK_BACKEND=litertlm` path were removed
> post-Sonoma. If you have a deployment pinned to either, the migration is
> always the same — install LocalLLM and point at it.
