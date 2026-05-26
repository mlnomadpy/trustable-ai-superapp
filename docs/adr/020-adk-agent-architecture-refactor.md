# ADR-020 — ADK Agent Architecture Refactor

**Status:** Accepted
**Date:** 2026-05-01
**Driver:** Post-ADR-019 audit — 7 structural issues identified before any Phase 2 code ships

**Note:** Files referenced in this ADR have moved: tools/pitwall_bridge.py → src/pitwall/__main__.py; tools/adk_agents.py → src/pitwall/features/coaching/adk_agents.py.

## Context

An audit of the ADK system specified in ADR-019 and documented in
`adk-agent-architecture.md` identified seven structural issues that will cause
silent failures or performance regressions once Phase 2 code ships. None of
them are visible from the API surface — the bridge contract is unchanged — but
all of them are cheap to fix now and expensive to fix post-Sonoma when
integration tests and field data have accumulated against the broken shapes.

The seven issues, in order of severity:

1. **`CoachOrchestrator` is an `LlmAgent` with 17 sub-agents.** The LLM must
   parse ~700 words of routing rules at every invocation and then decide which
   agent to call. Empirically, LLM-based orchestration mis-routes between
   semantically similar agents: `MindsetCoachAgent` vs `ProgressTrackerAgent`,
   `GoalSettingAgent` vs `SessionPlannerAgent`. These agents share vocabulary
   and the routing signal degrades as the catalogue grows.

2. **No `ParallelAgent` used.** The debrief pipeline sequences
   `HighlightFinderAgent → TelemetryAgent → PedagogyAgent → NarrativeAgent`.
   The first three agents are data-fetch operations with no dependency on each
   other. Running them sequentially is approximately 3× slower than running
   them concurrently. With a 2–15 s paddock latency budget this is directly
   user-visible.

3. **`NarrativeAgent` receives paraphrased context.** The current design lets
   the LLM orchestrator summarise what Telemetry and Pedagogy agents found and
   pass that summary to NarrativeAgent as a string. Every layer of LLM
   paraphrase is a lossy compression step. `NarrativeAgent` should consume
   structured data from `session.state`, not a natural-language re-telling.

4. **`query_pitwall_db` accepts raw SQL with no `LIMIT` enforcement.** A
   confused LLM can generate `SELECT * FROM telemetry WHERE session_id = ?`
   against a table with millions of rows. The result set blows the context
   window and may exceed the model's token limit entirely. The read-only
   connection prevents writes but does nothing about read volume.

5. **`get_track_variance_map` imports `track_loader` but never uses it.**
   The import is a dead reference. On Termux (the target Pixel 10 runtime)
   `track_loader` will raise `ImportError` at module load time, breaking the
   entire agent module before a single tool call is made.

6. **`VoiceScriptAgent` generates TTS scripts with no write tool.** The agent
   produces corner-by-corner TTS phrases but has no mechanism to persist them.
   Every generated script exists only in the LLM's response text and is lost
   when the conversation turn ends. The audio cache never grows.

7. **Agent descriptions are 150+ words.** ADK uses the `description` field as
   a routing signal for parent agents and for developer tooling. Verbose
   descriptions that include examples and caveats degrade routing precision and
   inflate token usage on every orchestration step.

## Decision

Fix all seven issues in a single refactor pass before any Phase 2 ADK code is
committed to the main branch. The bridge HTTP surface is unchanged. The public
entry point `PitwallOrchestrator.run(prompt)` wraps `asyncio.run()` identically
to the `CoachOrchestrator.run()` it replaces — callers in `pitwall_bridge.py`
need no changes.

### 1. Replace `LlmAgent` orchestrator with a `CustomAgent` (`BaseAgent` subclass)

`PitwallOrchestrator` inherits from `BaseAgent` and implements
`_run_async_impl`. Routing is a Python keyword classifier (`_classify_intent`),
not LLM reasoning. The classifier maps the lowercased query string to one of
15 intent buckets using substring matching, in priority order:

| Keywords matched | Intent / agent invoked |
|---|---|
| `gold`, `aj`, `reference` | `GoldLapAgent` |
| `fog`, `weather`, `rain` | `WeatherAdaptationAgent` |
| `plan`, `practice`, `laps` | `SessionPlannerAgent` |
| `incident`, `moment`, `spike` | `IncidentReviewAgent` |
| `race`, `stint`, `tyre` | `RacePaceAgent` |
| `target`, `goal`, `pb` | `GoalSettingAgent` |
| `consistent`, `variance` | `MentalMapAgent` |
| `audio`, `script`, `tts` | `VoiceScriptAgent` |
| `turn N`, `carousel` (corner names) | `CornerCoachAgent` |
| `vs`, `compare` | `LapComparisonAgent` |
| `progress`, `faster`, `plateau` | `ProgressTrackerAgent` |
| `setup`, `understeer`, `feels` | `SetupAdvisorAgent` |
| `frustrat`, `stuck` | `MindsetCoachAgent` |
| `debrief`, `today`, `highlight` | `DebriefPipeline` |
| *(default)* | `TelemetryAgent` |

Routing is evaluated top-to-bottom; first match wins. Extending the catalogue
is adding a row to a dict and a new `BaseAgent` subclass — no LLM routing
prompt to maintain.

### 2. Pre-built pipelines using `SequentialAgent` + `ParallelAgent`

Two pipelines replace the flat sequential chain:

```python
DebriefPipeline = SequentialAgent(
    name="DebriefPipeline",
    sub_agents=[
        ParallelAgent(
            name="DataGatherPhase",
            sub_agents=[HighlightFinderAgent, TelemetryAgent, PedagogyAgent],
        ),
        NarrativeAgent,
    ],
)

BriefPipeline = SequentialAgent(
    name="BriefPipeline",
    sub_agents=[PedagogyAgent, NarrativeAgent],
)
```

`DataGatherPhase` runs the three data agents concurrently. `NarrativeAgent`
always runs last, after all data is available in `session.state`. Debrief
wall-clock time drops from ~3× sequential to approximately 1× the slowest
data agent.

### 3. `output_key` on each data agent; `NarrativeAgent` reads structured state

Each data agent is given an `output_key`:

```python
HighlightFinderAgent  → output_key="highlights_data"
TelemetryAgent        → output_key="telemetry_data"
PedagogyAgent         → output_key="pedagogy_data"
```

ADK writes each agent's response to `session.state[output_key]`
automatically. `NarrativeAgent`'s instruction uses template variables:

```
Context:
Highlights: {highlights_data}
Telemetry:  {telemetry_data}
Pedagogy:   {pedagogy_data}
```

ADK injects state values before the instruction reaches the LLM. Context
flows as structured data, not LLM paraphrase. `NarrativeAgent` has no
`output_key` — its output is written to `conversations` via the
`write_conversation` tool.

### 4. SQL safety wrapper in `query_pitwall_db`

Two guards are injected before execution:

1. **LIMIT enforcement.** If the SQL string does not contain the word `LIMIT`
   (case-insensitive), the wrapper appends `LIMIT 500` before executing.
   No agent can return more than 500 rows regardless of what the LLM
   generates.

2. **Non-SELECT rejection.** If the normalised query does not begin with
   `SELECT`, the tool returns a structured error dict rather than executing.
   This is defense-in-depth — `read_only=True` at the connection level already
   blocks writes, but an early rejection with a clear error message is faster
   and produces better LLM self-correction than a DuckDB exception traceback.

```python
@tool
def query_pitwall_db(sql: str) -> list[dict]:
    """Query pitwall session data. Read-only. Max 500 rows."""
    normalised = sql.strip().upper()
    if not normalised.startswith("SELECT"):
        return [{"error": "Only SELECT statements are permitted."}]
    if "LIMIT" not in normalised:
        sql = sql.rstrip().rstrip(";") + " LIMIT 500"
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        return conn.execute(sql).fetchdf().to_dict("records")
    finally:
        conn.close()
```

### 5. Remove dead `track_loader` import from `get_track_variance_map`

The import `from tools import track_loader` in `get_track_variance_map` is
deleted. The function never calls anything from that module. On Termux the
import raises `ImportError` at module load time; removing it makes the tool
importable on all target platforms.

### 6. `save_voice_scripts` tool for `VoiceScriptAgent`

A new tool persists TTS phrase sets to disk:

```python
@tool
def save_voice_scripts(corner_name: str, phrases: dict[str, str]) -> str:
    """Write TTS phrases for a corner to the audio cache.

    Args:
        corner_name: Identifier for the corner (e.g. "turn_7", "carousel").
        phrases:     Mapping of phase → phrase, e.g.
                     {"brake": "Brake now", "apex": "Roll to apex"}.
    Returns:
        Absolute path of the written file.
    """
    path = AUDIO_CACHE_DIR / f"{corner_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(phrases, indent=2))
    return str(path)
```

Output path: `tools/audio_cache/<corner_name>.json`. Format:
`{"phase": "TTS phrase", ...}`. `VoiceScriptAgent` receives this tool in its
`tools` list. Scripts generated during a session now persist and are available
to the in-drive rally co-driver path (see Termux plan in project memory).

### 7. Agent descriptions capped at ~30 words

Every agent `description` is rewritten to be keyword-rich and distinctive,
with no examples, no caveats, and no prose. The complete 17-agent description
set is specified in `adk-agent-architecture.md` (updated alongside this ADR).
Routing reliability increases because the signal-to-noise ratio in the
description field improves.

## Consequences

**Positive.**
Routing is now deterministic Python — intent classification cannot degrade as
the agent catalogue grows, and mis-routes between similar agents are
impossible. The debrief pipeline runs data agents concurrently, cutting
wall-clock time by approximately 3×. `NarrativeAgent` receives structured
state rather than paraphrased prose, eliminating lossy summarisation.
No single SQL query can blow the context window. Voice scripts persist across
sessions and are available to the audio cache consumed by the in-drive path.
The dead import that would break Termux module loading is gone.

**Negative / risks.**
`_classify_intent` is a keyword classifier, not semantic understanding. A
novel query that uses none of the registered keywords falls through to
`TelemetryAgent` (the default). This is a safe fallback for the current use
case — most paddock queries are telemetry questions — but may need a
lightweight embedding classifier post-Sonoma if the `/coach/ask` catalogue
expands significantly.

**Unchanged.**
The bridge HTTP surface is identical. `PitwallOrchestrator.run(prompt)` wraps
`asyncio.run(_run_async_impl(...))` and returns the same `{text, emotion}`
dict that `CoachOrchestrator.run()` would have returned. `RuleCoach`,
`CoachArbiter`, and `LitertCoach` are untouched.

## References

- [ADR-017](017-three-tier-coach-architecture.md) — three-tier latency split
- [ADR-019](019-adk-multi-agent-backend.md) — original ADK topology this ADR revises
- [adk-agent-architecture.md](../adk-agent-architecture.md) — full agent topology, tool specs, updated per this ADR
