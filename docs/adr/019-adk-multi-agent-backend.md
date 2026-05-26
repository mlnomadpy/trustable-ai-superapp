# ADR-019 — ADK Multi-Agent Backend

**Status:** Accepted
**Date:** 2026-05-01
**Driver:** Post-Sonoma capability expansion — richer paddock intelligence, cross-session memory, driver Q&A

**Note:** Files referenced in this ADR have moved: tools/pitwall_bridge.py → src/pitwall/__main__.py; tools/adk_agents.py → src/pitwall/features/coaching/adk_agents.py.

**Superseded structurally by:** ADR-020, ADR-021.

## Context

The current coaching backend (`pitwall_bridge.py` + `coach_engine.py`) is a monolith. After the Sonoma field test the architectural ceiling becomes clear:

- `brief()` and `debrief()` are synchronous LLM calls with pre-packed context. The LLM cannot explore the data — it reasons only over what a developer decided to include.
- `llm_friction` stores LLM call *metadata* but never the actual narrative text. There is no way to recall "what did the coach say before my last session."
- There is no multi-turn conversation. The driver cannot ask a follow-up question.
- `driver_level` is a static string. The driver profile (`driver_events`) is computed correctly but never shapes the coaching conversation dynamically.
- The coaching rules (`@coach_rule` decorators) are evaluated by hand-written logic on every frame. An LLM cannot choose which ones to invoke.

Google's Agent Development Kit (ADK) runs fully locally (`pip install google-adk`), provides multi-agent orchestration, tool use, session state, and streaming — primitives the current backend re-implements by hand.

**Model decision:** ADK agents use the **`Gemini` class with a `base_url`** pointing at a local **LiteRT-LM server** (`lit serve`) running **Gemma 4 E4B**. ADK has native LiteRT-LM support — no Ollama or LiteLLM shim required. E4B (4B parameters) is chosen over the hot-path E2B because paddock tasks (pre-brief, debrief, Q&A) have a 2–15 s latency budget and benefit from the larger model's reasoning depth.

```python
from google.adk.agents import Agent
from google.adk.models import Gemini

model = Gemini(
    base_url=os.getenv("PITWALL_LITERT_URL", "localhost:8001"),
    model=os.getenv("PITWALL_LITERT_MODEL", "gemma-4-e4b"),
)
```

Setup (one-time):
```bash
lit pull gemma-4-e4b   # download from Hugging Face via lit CLI
lit serve --port 8001  # start server before launching the bridge
```

**Two runtimes, one ecosystem — never mixed on the hot path:**

| Path | Runtime | Model | How invoked | Latency budget |
|---|---|---|---|---|
| In-drive (hot) | `litert-lm` Engine (in-process) | Gemma 4 E2B | `litert_lm.Engine` direct | < 100 ms |
| Paddock (ADK) | `lit serve` HTTP server | Gemma 4 E4B | `Gemini(base_url=...)` | 2–15 s |

**Constraints:**
- ADK must not touch the hot path. The in-drive coaching loop stays as `RuleCoach` + `CoachArbiter`. ADK is a paddock-only concern.
- `PITWALL_LITERT_URL` and `PITWALL_LITERT_MODEL` are environment variables so the model can be swapped without code changes. *(Renamed in 2026-05 to `PITWALL_ADK_OPENAI_URL` / `PITWALL_ADK_OPENAI_MODEL` — see ADR-022 and the rename note below. The legacy names still work with a `DeprecationWarning`.)*

## Decision

Introduce ADK as the orchestration layer for paddock-mode coaching (tiers 1 and 3 from ADR-017). The Flask bridge keeps its existing HTTP surface — ADK agents are called *from* the bridge endpoints, not instead of them.

### 1. Agent topology

```
CoachOrchestrator (root agent)
├── TelemetryAgent          — reads DuckDB; wraps session_analyzer, corner_grader
├── PedagogyAgent           — reads driver_events; wraps match_bentley_concept
└── NarrativeAgent          — owns LLM calls; writes brief/debrief to conversations table
```

All three are sub-agents of `CoachOrchestrator`. The orchestrator decides which sub-agents to invoke and in what order based on the request type (brief vs debrief vs Q&A).

### 2. DuckDB as a tool

A single `@tool`-decorated function exposes the entire DuckDB schema to any agent that needs it. It is **read-only** — only the bridge writes to DuckDB.

```python
@tool
def query_pitwall_db(sql: str) -> list[dict]:
    """Query pitwall session data (read-only).
    Tables: laps, telemetry, coaching_notes, telemetry_signals,
            sessions, llm_friction, driver_events, conversations."""
    conn = duckdb.connect(DB_PATH, read_only=True)
    return conn.execute(sql).fetchdf().to_dict("records")
```

`TelemetryAgent` and `PedagogyAgent` both receive this tool. `NarrativeAgent` does not — it writes, so it goes through bridge-side helpers, not the read-only tool.

### 3. Conversation persistence

A new `conversations` table stores every paddock-mode turn — brief narratives, debrief narratives, and user Q&A turns — so they are queryable by future agents and visible in the Vue PWA.

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY DEFAULT nextval('conversations_id_seq'),
    session_id   VARCHAR,
    driver_id    VARCHAR,
    role         VARCHAR,   -- 'coach_brief' | 'coach_debrief' | 'user' | 'assistant'
    text         TEXT,
    focus_items  VARCHAR,   -- JSON array of focus points (brief/debrief only)
    emotion      VARCHAR,   -- coach emotion tag if present
    recorded_at  TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversations_session
    ON conversations(session_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_conversations_driver
    ON conversations(driver_id, recorded_at);
```

`brief()` and `debrief()` in `coach_engine.py` write to this table after a successful generation (lines 1131 and 1169). The existing `llm_friction` table is unchanged — it keeps performance metadata; `conversations` keeps content.

### 4. ADK session service

ADK's `InMemorySessionService` is used for single-session Q&A (turn-by-turn context within one paddock interaction). On session end, the full turn history is flushed to the `conversations` table. This means:

- Within a paddock session: ADK holds context in memory (fast, no DB round-trip per turn)
- After the session ends: full history is durable in DuckDB

A persistent `DatabaseSessionService` backed by DuckDB is deferred — the flush-on-end pattern is sufficient for the Sonoma use case.

## Phased rollout

### Phase 1 — DuckDB tool + conversations table (Sonoma-safe, no ADK dependency)
- Add `conversations` table to `get_db()` schema
- Write brief/debrief narratives to `conversations` in `coach_engine.py`
- Add `GET /conversations/<session_id>` endpoint to bridge
- Add `GET /conversations/driver/<driver_id>` endpoint (cross-session history)

No ADK code yet. Ships before the Sonoma field test. Unlocks chat history in the Vue PWA.

### Phase 2 — ADK agents + DuckDB tool (post-Sonoma)
- Install `google-adk`; add `lit pull gemma-4-e4b` + `lit serve --port 8001` to setup instructions
- Implement `TelemetryAgent`, `PedagogyAgent`, `NarrativeAgent`, `CoachOrchestrator` — all backed by `Gemini(base_url="localhost:8001", model="gemma-4-e4b")`
- Wire `CoachOrchestrator` into `/coach/brief` and `/coach/debrief` bridge endpoints
- Implement `query_pitwall_db` tool with read-only DuckDB connection
- Replace manual `build_post_session_user_prompt` bundle packing with agent-driven tool calls
- Tests: mock DuckDB tool and LiteRT-LM endpoint, assert agent calls correct sub-agents for brief vs debrief

### Phase 3 — Driver Q&A endpoint (post-Sonoma)
- New `POST /coach/ask` endpoint: accepts a driver question, session_id context
- `CoachOrchestrator` handles multi-turn with `InMemorySessionService`
- Flush turns to `conversations` on `POST /coach/ask/end`
- Vue PWA paddock screen wires up the Q&A turn model

## Consequences

**Positive**
- The debrief agent can self-direct its queries: "which corners had the highest coast_pct?" rather than receiving a fixed bundle.
- Cross-session questions become natural: "how has my T3 improved over five sessions?" — one SQL query via the tool.
- All coach narratives are durable and browsable from the Vue PWA.
- Future agents (weather-aware, competitor analysis, equipment notes) plug into the same topology without touching the hot path.
- ADK's built-in streaming means the debrief narrative can stream token-by-token to the Vue PWA rather than waiting 8–15 s for the full response.

**Negative / risks**
- ADK adds a Python dependency with Google-authored abstractions. If ADK's API changes, the paddock layer breaks.
- The flush-on-end pattern loses conversation history if the process crashes mid-session. Acceptable for Sonoma; revisit for production.
- Phase 2 requires rewriting `build_post_session_user_prompt` — the existing integration tests for `/coach/debrief` will need updating.

**Unchanged**
- In-drive path: `RuleCoach` + `CoachArbiter` + `SonicModelV2`. ADK never executes on the hot path.
- Flask bridge HTTP surface: all existing endpoints keep their shape and contract.
- Hot-path `litert-lm` runtime: `LitertCoach` keeps its `litert_lm.Engine` in-process calls for < 100 ms in-drive cues. Unaffected by ADK.
- `llm_friction` table: still receives performance records from every LLM call.

## References

- [ADR-012](012-coach-engine-adapter.md) — coach engine adapter pattern
- [ADR-013](013-frontend-backend-boundary.md) — backend owns LLM logic
- [ADR-015](015-universal-telemetry-sink.md) — universal telemetry sink (DuckDB schema owner)
- [ADR-017](017-three-tier-coach-architecture.md) — three-tier latency split (hot/warm/paddock)
- [ADR-018](018-field-readiness-blockers-and-pedagogy-tuning.md) — llm_friction table spec
- [adk-agent-architecture.md](../adk-agent-architecture.md) — full agent topology, tool specs, use case catalogue
