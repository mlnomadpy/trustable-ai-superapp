# Coaching Engine

Three layers, one arbiter. Phone-shipping state (2026-05-26):

| Layer | What it is | Phone status |
|---|---|---|
| **sonic_model + RuleCoach** | Per-burst rule engine that consumes telemetry, emits `AudioCue` objects, and routes them through `cue_renderer.py`. Hot path, deterministic, no LLM. | **Active.** |
| **LitertCoach** | Gemma-4-E2B via HTTP to LocalLLM (OpenAI-compatible). Drives `brief()` / `debrief()`; `propose()` defers to `RuleCoach`. | **Active** (LocalLLM at `127.0.0.1:8080/v1`). |
| **ADK multi-agent** | 17 specialist agents over Gemma-4 via `google-adk`. Powers `/coach/ask`, `/coach/agents`, `/coach/traces`. | **NOT installed.** `google-adk` has no `android_arm64_v8a` wheels for `cffi`/`cryptography`/`watchdog`/`pydantic-core` and `adb su` exec has broken DNS. 16 MB of pre-staged ADK wheels live at `~/adk-wheels` on the phone for offline install once DNS is back. |

`/coach/agents` and `/coach/ask` return honest `{available: false, reason: "google-adk not installed"}` until the wheels are installed. See [`adk-agent-architecture.md`](adk-agent-architecture.md) for the full ADK design.

---

## Hot path — `sonic_model` + `RuleCoach`

`sonic_model.compute_cues()` consumes telemetry frames and emits `AudioCue`
objects per burst. `cue_renderer.cue_to_sentence()` converts a cue list into
one short coaching sentence; the same module also exposes a fallback rule
engine when `sonic_model` is unavailable. `bp_core.py:/analyze` exposes this
under `engine = "sonic_model"` (or `"rules"`).

No LLM, no network, no per-burst inference. Latency is bounded by the rule
table.

---

## Warm path — `LitertCoach` over LocalLLM

`src/pitwall/features/coaching/litert_coach.py` is the LLM-driven brief/debrief
class. Construction reads:

| Env | Default | Meaning |
|---|---|---|
| `PITWALL_ADK_OPENAI_URL`   | `http://localhost:8099/v1` (desktop) / `http://localhost:8080/v1` (phone, set by `70-start-bridge.sh`) | OpenAI-compatible HTTP base |
| `PITWALL_ADK_OPENAI_MODEL` | `gemma3n-e2b` (desktop) / `gemma-4-e2b` (phone) | model id served by LocalLLM |
| `PITWALL_ADK_OPENAI_API_KEY` | `lit-serve-not-required` / `local` | bearer; LocalLLM accepts anything when auth is off |
| `PITWALL_COMPACT_PROMPTS`  | unset / `1` on phone | shrink system prompts so Gemma-4-E2B fits its context |
| `PITWALL_LLM_MAX_TOKENS`   | 512 | output budget |
| `PITWALL_LITERT_HTTP_TIMEOUT_S` | 30 | request timeout |

Legacy aliases `PITWALL_LITERT_URL` / `PITWALL_LITERT_MODEL` /
`PITWALL_LITERT_API_KEY` are still honoured and emit a `DeprecationWarning`.

### Three methods

| Method | Purpose | LLM? |
|---|---|---|
| `propose(ctx)` | Per-burst — DEPRECATED for LLM use. Forwards to `RuleCoach.propose()`. | No |
| `brief(...)` | Pre-session paddock narrative (~150 words). | Yes |
| `debrief(bundle, ...)` | Post-session debrief (~300 words). | Yes |

### No-fake-fallbacks policy

`_templated_pre_brief` is no longer called from any synthesis path. When the
LLM is offline, returns empty, or fails to parse, `brief()` / `debrief()`
return `("", [], "neutral")` and record one row in `llm_friction` with
`backend`, `role`, `error`, and `fell_back=False`. The PWA renders an honest
"brief unavailable" panel.

### `/coach/brief` exposes the friction reason

`bp_coaching.py:/coach/brief` returns the standard JSON envelope plus an
`error: str | None` field. When `narrative_md == ""`, the endpoint queries
the latest `llm_friction` row for `role='brief'` and surfaces its `error`
column (truncated to 240 chars) so the PWA can show *why*:

```json
{
  "driver_id": "taha",
  "narrative_md": "",
  "focus": [],
  "emotion": "neutral",
  "error": "engine_not_loaded"
}
```

When the LLM is healthy and parsed, `error` is `null`.

---

## Paddock path — ADK (when installed)

The `PITWALL_ADK_BACKEND` selector chooses one of three transports for the
ADK model client. The phone uses `openai` (HTTP → LocalLLM). See
[`adk-agent-architecture.md`](adk-agent-architecture.md) for the agent
catalogue, intent classifier, pipelines, and the `agent_traces` schema.

`/coach/traces?session_id=&limit=&since_ts=` (new) returns recent rows from
the `agent_traces` DuckDB table for HUD visualisation. Always HTTP 200 even
when ADK or DuckDB is absent — the `available` flag tells the caller.

---

## Message Arbiter

All coaching from sonic_model + LitertCoach flows through `arbiter.py`:

- **P3 (safety):** delivered immediately, interrupts queue.
- **P2 (technique):** delivered on straights only (|gLat| < 0.3 G).
- **P1 (strategy):** queued behind P2.
- **Conflict:** higher priority wins; ties go to the hot path (freshest data).
- **Cooldown:** ≥ 3 s between messages.
- **Stale expiry:** drop after 5 s in queue.

---

## What stays unchanged

- `RuleCoach` + `CoachArbiter` semantics.
- The `[EMOTION:x]` tag contract.
- The `conversations` and `llm_friction` DuckDB tables.
- The PWA's `/coach/brief`, `/coach/debrief`, `/analyze` contracts (the
  `error` field is additive).
