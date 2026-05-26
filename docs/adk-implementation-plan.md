# ADK Implementation — As-Built Status

> **All phases complete as of 2026-05-01.** 358/358 tests passing.
>
> This document reflects what was actually shipped. For architecture decisions
> see [ADR-019](adr/019-adk-multi-agent-backend.md),
> [ADR-020](adr/020-adk-agent-architecture-refactor.md), and
> [ADR-021](adr/021-adk-second-audit.md). For the current topology see
> [adk-agent-architecture.md](adk-agent-architecture.md).

---

## Phase 1 — Conversation persistence ✅

| Item | File | Status |
|---|---|---|
| `conversations` table DDL in `get_db()` | `src/pitwall/__main__.py` | ✅ shipped |
| Write brief narrative to `conversations` | `src/pitwall/__main__.py` | ✅ shipped |
| Write debrief narrative to `conversations` | `src/pitwall/__main__.py` | ✅ shipped |
| `GET /conversations/<session_id>` | `src/pitwall/__main__.py` | ✅ shipped |
| `GET /conversations/driver/<driver_id>` | `src/pitwall/__main__.py` | ✅ shipped |

---

## Phase 2 — ADK multi-agent backend ✅

### Files created

| File | Lines | Purpose |
|---|---|---|
| `src/pitwall/adk_tools.py` | ~750 | 15 `@_adk_tool` functions + `write_conversation` helper |
| `src/pitwall/features/coaching/adk_agents.py` | ~570 | 18 agents + `PitwallOrchestrator` + `Runner` + tracing |
| `tools/audio_cache/` | directory | TTS phrase cache written by `save_voice_scripts` |

### Agents shipped (18 total)

| Agent | Role | `output_key` |
|---|---|---|
| `TelemetryAgent` | Session data — laps, notes, signals | `telemetry_data` |
| `HighlightFinderAgent` | Best moments, peak grip | `highlights_data` |
| `PedagogyAgent` | Driver profile + Bentley concept | `pedagogy_data` |
| `NarrativeAgent` / `NarrativeAgentDebrief` / `NarrativeAgentBrief` | Final output (3 instances) | — |
| `LapComparisonAgent` | Frame-by-frame lap delta | — |
| `CornerCoachAgent` | Single-corner deep-dive | — |
| `ProgressTrackerAgent` | Multi-session arc | — |
| `SetupAdvisorAgent` | Car balance from telemetry | — |
| `MindsetCoachAgent` | Plateau + motivation | — |
| `GoldLapAgent` | Driver vs AJ gold standard | — |
| `WeatherAdaptationAgent` | Weather phase → adjustments | — |
| `SessionPlannerAgent` | N-lap practice plan | — |
| `IncidentReviewAgent` | Anomaly detection | — |
| `RacePaceAgent` | Lap degradation model | — |
| `GoalSettingAgent` | Realistic PB targets | — |
| `MentalMapAgent` | Corner consistency variance | — |
| `VoiceScriptAgent` | TTS audio cache scripts | — |
| `AgentMetaAgent` | ADK system telemetry queries | — |

### Tools shipped (15 total)

| Tool | Returns |
|---|---|
| `query_pitwall_db(sql)` | DuckDB SELECT, LIMIT 500 enforced, non-SELECT rejected |
| `get_lap_delta(sid, lap_a, lap_b)` | Time / speed / coast delta between two laps |
| `get_corner_history(driver_id, corner, n)` | Grade history + trend for one corner |
| `get_progress_report(driver_id, n)` | Multi-session lap trend + plateau detection |
| `get_setup_indicators(sid)` | Coast ratio, steer oscillation, brake pressure indicators |
| `get_session_highlights(sid)` | Best lap, peak grip, note counts |
| `get_gold_lap_comparison(sid)` | Corner-by-corner speed gap vs gold lap |
| `get_weather_adaptation_context(hour)` | Sonoma weather phase → coaching adjustments |
| `get_session_plan_context(driver_id, n_laps)` | Corner priorities for a practice plan |
| `get_incident_moments(sid, g_thresh, steer_thresh)` | Over-limit events, emergency brakes, saves |
| `get_race_pace_model(sid)` | Degradation rate, quali vs race pace, consistency |
| `get_goal_targets(driver_id)` | PB projections + top 3 corners to attack |
| `get_track_variance_map(sid)` | CV per corner — consistency map |
| `get_agent_telemetry(n_recent)` | ADK trace stats from `agent_traces` table |
| `get_audio_script_context(corner, level)` | Script guidelines for VoiceScriptAgent |
| `save_voice_scripts(corner, scripts)` | Atomic write to `audio_cache/<corner>.json` (fcntl locked) |

### ADR-020 audit fixes (all shipped)

| Finding | Fix | File |
|---|---|---|
| LLM orchestrator routing 17 agents | `PitwallOrchestrator(BaseAgent)` + `_classify_intent()` | `features/coaching/adk_agents.py` |
| No workflow agents | `SequentialAgent` + `ParallelAgent` for debrief/brief | `features/coaching/adk_agents.py` |
| NarrativeAgent data-blind | `output_key` + `{template}` instruction injection | `features/coaching/adk_agents.py` |
| No SQL safety | `LIMIT 500` auto-inject, non-SELECT rejected | `adk_tools.py` (at `src/pitwall/adk_tools.py`) |
| Dead `track_loader` import | Removed | `adk_tools.py` (at `src/pitwall/adk_tools.py`) |
| VoiceScriptAgent scripts disappear | `save_voice_scripts` tool + audio cache dir | `adk_tools.py` (at `src/pitwall/adk_tools.py`) |
| 150-word agent descriptions | All trimmed to ~25–30 words | `features/coaching/adk_agents.py` |

### ADR-021 audit fixes (all shipped)

| Finding | Fix | File |
|---|---|---|
| `BaseAgent.run()` doesn't exist | `Runner` + `run_adk()` helper | `features/coaching/adk_agents.py` |
| `save_voice_scripts` TOCTOU race | `fcntl.flock(LOCK_EX)` + `os.replace()` | `adk_tools.py` (at `src/pitwall/adk_tools.py`) |
| Shared `narrative_agent` across pipelines | 3 separate instances per pipeline | `features/coaching/adk_agents.py` |
| `_qa_histories` memory leak | `_qa_timestamps` TTL + `_qa_cleanup_stale()` | `src/pitwall/__main__.py` |
| No agent observability | `PitwallTracingPlugin` + `agent_traces` DuckDB table | `src/pitwall/features/coaching/adk_agents.py`, `src/pitwall/__main__.py` |
| No KV cache reuse | Persistent sessions per driver + `reset_driver_session()` | `src/pitwall/features/coaching/adk_agents.py`, `src/pitwall/__main__.py` |

---

## Phase 3 — Driver Q&A ✅

| Item | File | Status |
|---|---|---|
| `POST /coach/ask` (multi-turn Q&A) | `src/pitwall/__main__.py` | ✅ shipped |
| `POST /coach/ask/end` (flush to DuckDB) | `src/pitwall/__main__.py` | ✅ shipped |
| `GET /coach/agents` (Vue PWA discovery) | `src/pitwall/__main__.py` | ✅ shipped |
| In-memory `_qa_histories` with 1-hour TTL | `src/pitwall/__main__.py` | ✅ shipped |

---

## Agent telemetry — shipped as part of Phase 2

| Item | Status |
|---|---|
| `agent_traces` table in `get_db()` | ✅ shipped |
| `PitwallTracingPlugin(BasePlugin)` | ✅ shipped |
| `get_pending_traces()` drain function | ✅ shipped |
| `_drain_adk_traces(pitwall_sid)` in bridge | ✅ shipped — called after every `run_adk()` |
| `get_agent_telemetry` tool | ✅ shipped |
| `AgentMetaAgent` (18th agent) | ✅ shipped |

---

## KV cache — shipped as part of Phase 2

| Item | Status |
|---|---|
| `_driver_sessions` persistent session registry | ✅ shipped |
| `_get_or_create_session(user_id)` | ✅ shipped — reuses session, auto-rotates at 50 turns |
| `reset_driver_session(user_id)` | ✅ shipped — exported for bridge |
| `POST /session/start` calls `_reset_adk_session` | ✅ shipped |

---

## Remaining backlog (post-Sonoma)

These were identified in ADR-021 as Tier 1/2 features — not yet implemented.

| Item | Priority | ADR reference |
|---|---|---|
| SSE streaming (`/coach/ask/stream`) | Tier 1 | ADR-021 §SSE |
| ADK state scopes (`user:`, `app:`, `temp:`) | Tier 1 | ADR-021 §State |
| Tracing plugin via `BasePlugin` hooks (verify exact API) | Tier 1 | ADR-021 §Plugin |
| `before_tool_callback` per-agent SQL validation | Tier 2 | ADR-021 §Callbacks |
| `LoopAgent` for Q&A refinement | Tier 2 | ADR-021 §LoopAgent |
| Artifact storage for session exports | Tier 2 | ADR-021 §Artifacts |
| `DatabaseSessionService` backed by DuckDB | Tier 2 | ADR-021 consequence |
| Vue PWA paddock Q&A screen | Tier 1 | sprint-plan.md |

---

## Startup sequence (Termux, Pixel 10)

```bash
# Terminal 1 — E4B model server for ADK paddock agents (legacy `litertlm` backend;
# default is now `openai` → LocalLLM, see ADR-022)
lit pull gemma-4-e4b
lit serve --port 8001

# Terminal 2 — Pitwall bridge (E2B in-process for hot path)
cd ~/pitwall
python3 -m pitwall --coach litert \
    --litert-model ~/storage/shared/Pitwall/models/gemma-4-E2B-it.litertlm
```

Environment variable overrides:

```bash
PITWALL_ADK_OPENAI_URL=localhost:8001    # default (legacy: PITWALL_LITERT_URL)
PITWALL_ADK_OPENAI_MODEL=gemma-4-e4b     # default (legacy: PITWALL_LITERT_MODEL)
```

Legacy names (`PITWALL_LITERT_URL`, `PITWALL_LITERT_MODEL`,
`PITWALL_LITERT_API_KEY`) are still honoured for backward compatibility and
emit a `DeprecationWarning` on first read.
