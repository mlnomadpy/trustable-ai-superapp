# ADR-026 — Phase-2 ADK Agent Expansion: AiM signal coverage

**Status:** Accepted
**Date:** 2026-05-28
**Relates to:** [ADR-019](019-adk-multi-agent-backend.md), [ADR-020](020-adk-agent-architecture-refactor.md), [ADR-021](021-adk-second-audit.md), [ADR-024](024-localllm-sole-llm-transport.md), [ADR-025](025-warm-path-localllm-only.md)

---

## Context

ADR-019/020/021 shipped a 17-agent ADK paddock backend with 15 SQL-safe
tools. The agent roster was sized for the V1 telemetry envelope — the six
canonical signals (`speed_ms`, `g_lat`, `g_long`, `combo_g`, `brake_bar`,
`throttle_pct`) emitted by the original Racelogic VBO ingest. Every
existing agent reasons from that six-signal slice.

The AiM MXP pipeline (`data/cars/bmw_e46_m3.yaml` + the bridge's tall-sink
`telemetry_signals` table) emits a much richer signal set: four-corner TPMS
(pressure / temperature / alarm bitfield), 4-corner wheel speeds, 3-axis
gyros (yaw / roll / pitch rate), the powertrain stream (oil / water / fuel
pressure, three temp channels), and the safety-flag stream (`abs_fail`,
`dsc_reg`, `mil_chk_eng`, `brake_switch`). Inspection of the staged 2026-05-23
Sonoma recording showed 35+ AiM-canonical signals in `telemetry_signals` —
of which **only one (`combo_g`) is used by the existing agent roster**.

Five signal groups had no agent owner:

| Signal group | Untapped insight |
|---|---|
| TPMS | tire mgmt, cold→hot delta, leak detection |
| 3-axis gyro | measured U/O, weight-transfer rate |
| 4-corner wheel speeds | wheelspin, lockup, diff behaviour |
| Engine health | reliability, stint-limit warnings |
| Status flags | "ABS dropped at lap 4" explaining pace loss |

`SetupAdvisorAgent` came closest — it infers car *balance* from coasting
patterns — but it had no access to the directly measured yaw-rate signal
that would tell it which corners are over- vs. understeering, and no
access to TPMS or input-quality data.

A separate smoke test against the real Sonoma SQLite also surfaced two
pipeline bugs the existing agents couldn't see:

- The YAML `0xFFFF` "no reading" sentinel passes through unfiltered for
  `brake_press_psi → brake_bar`, polluting any aggregate (max brake = 4519
  bar from 0.085 % of frames).
- The YAML §7 sign-convention `verify-on-first-capture` step had not been
  applied to this car — measured yaw and steering are sign-flipped relative
  to the bicycle-model expectation.

---

## Decision

**Phase-2 expansion**: add six new ADK specialists that each own one AiM
signal domain end-to-end, extend six existing agents with the new tools so
they can cross-reference the new findings, expand the brief/debrief
narrative pipelines so the orchestrator (the "god agent") consumes all the
new signal-domain outputs.

### Six new specialist agents

Each owns one signal domain and publishes findings under a named
`output_key` that the narrative templates cite.

| Agent | Signal domain | Output key | Backing tool |
|---|---|---|---|
| `TireManagerAgent` | TPMS pressure/temp/alarms | `tire_data` | `get_tire_thermal_window` |
| `HandlingBalanceAgent` | yaw rate × steering bicycle model | `handling_data` | `get_handling_balance` |
| `EngineHealthAgent` | oil/water/fuel pressure + temps | `engine_health_data` | `get_engine_health_timeline` |
| `TractionAgent` | 4-corner wheel-speed deltas | `traction_data` | `get_traction_events` |
| `InputQualityAgent` | steering/throttle/brake jerk + smoothness | `input_quality_data` | `get_input_smoothness` |
| `SafetyMonitorAgent` | ABS/DSC/MIL/TPMS alarm timeline | `safety_data` | `get_safety_events` |

Agent count: 17 → 23. Tools: 15 → 21.

### Six existing agent extensions

The QA agents that touch per-session questions gain the new tools so they
can cross-reference what the specialists found. Routing is unchanged —
they still own the same intent — but their reasoning is now richer:

- `TelemetryAgent` ← `+get_safety_events`
- `LapComparisonAgent` ← `+get_engine_health_timeline`, `+get_safety_events`
- `CornerCoachAgent` ← `+get_handling_balance`, `+get_traction_events`
- `SetupAdvisorAgent` ← `+get_handling_balance`, `+get_input_smoothness`, `+get_tire_thermal_window`
- `HighlightFinderAgent` ← `+get_input_smoothness`, `+get_tire_thermal_window`
- `WeatherAdaptationAgent` ← `+get_tire_thermal_window`
- `SessionPlannerAgent` ← `+get_tire_thermal_window`
- `IncidentReviewAgent` ← `+get_safety_events`, `+get_traction_events`
- `RacePaceAgent` ← `+get_engine_health_timeline`, `+get_tire_thermal_window`

### Pipeline expansion: god agent reads everything

`DebriefPipeline` grows from 3 → 9 parallel data agents in its
`DebriefDataPhase`:

```
DebriefDataPhase = ParallelAgent(
    HighlightFinderAgentDebrief,        // highlights_data
    TelemetryAgentDebrief,              // telemetry_data
    PedagogyAgentDebrief,               // pedagogy_data
    TireManagerAgentDebrief,            // tire_data       ← NEW
    HandlingBalanceAgentDebrief,        // handling_data   ← NEW
    EngineHealthAgentDebrief,           // engine_health_data ← NEW
    TractionAgentDebrief,               // traction_data   ← NEW
    InputQualityAgentDebrief,           // input_quality_data ← NEW
    SafetyMonitorAgentDebrief,          // safety_data     ← NEW
)
DebriefPipeline = Sequential(DebriefDataPhase, NarrativeAgentDebrief)
```

`BriefPipeline` grows from 1 → 4 parallel data agents — only the domains
that carry from the prior session into today's pre-brief:

```
BriefDataPhase = ParallelAgent(
    PedagogyAgentBrief,                 // pedagogy_data
    TireManagerAgentBrief,              // tire_data       ← NEW
    EngineHealthAgentBrief,             // engine_health_data ← NEW
    SafetyMonitorAgentBrief,            // safety_data     ← NEW
)
BriefPipeline = Sequential(BriefDataPhase, NarrativeAgentBrief)
```

Each pipeline-internal agent is a clone of its public sibling with the
same `output_key` (satisfies ADK's single-parent invariant).

The `_NARRATIVE_TAIL` template now exposes nine output slots:

```
Session highlights:   {highlights_data?}
Telemetry analysis:   {telemetry_data?}
Pedagogy context:     {pedagogy_data?}
Tire window + alarms: {tire_data?}
Handling balance:     {handling_data?}
Engine health:        {engine_health_data?}
Traction events:      {traction_data?}
Input quality:        {input_quality_data?}
Safety events:        {safety_data?}
```

Empty slots collapse to `""` via ADK's `{key?}` optional binding so the
template stays valid when an upstream data agent has nothing to say (e.g. a
clean session with no safety events).

### Intent classifier

Six new intents wired into `_INTENT_TO_AGENT` and the
`PitwallOrchestrator.sub_agents` list:

```python
"tire":           tire_manager_agent,
"handling":       handling_balance_agent,
"engine_health":  engine_health_agent,
"traction":       traction_agent,
"input_quality":  input_quality_agent,
"safety":         safety_monitor_agent,
```

`_INTENT_PATTERNS` reordered so specialty intents win over the broader
`corner` / `weather` / `telemetry` catch-alls. The patterns dropped the
leading `\b` so compound tool-name identifiers like
`get_tire_thermal_window` also classify correctly — `\b` doesn't match
between `_` and a letter (both are word chars), and ADK chat prompts
routinely reference tools by their compound names. `setup` lost the
`understeer / oversteer / balance` keywords — those route to
`HandlingBalanceAgent` now (which *measures* the balance) while
`SetupAdvisorAgent` keeps the inferential coast/oscillation/setup-language
path.

### AiM-pipeline findings baked into the tools

The phase-2 tools encode lessons surfaced by the prior agent runs:

- **Sentinel filtering** — `_signal_aggregate(lo=, hi=)` clamps the `0xFFFF`
  AiM no-reading marker (becomes 4519 bar after `psi_to_bar`, 200 °C on
  the temp channels). Documented in YAML §8; the bridge doesn't apply it,
  so the tools do.
- **Lap-modulo distance attribution** — `distance_m` is cumulative across
  laps in the AiM ingest; tools fold via `% TRACK_LENGTH_M` before
  matching corner bounds.
- **YAML §7 sign-convention warning** — `get_handling_balance` watches the
  per-session counter-steer-event ratio and surfaces a calibration
  warning when > 50 % of samples have opposite-sign steering and yaw
  (indicating the first-capture sign verification hasn't been applied).
- **Engine-health load gating** — oil-pressure-low anomaly only fires when
  `rpm > 3000 AND throttle_pct > 10` so idle low-pressure (cold start,
  in-pit) doesn't generate false "bearing starvation" alarms.

### Tool safety: catch SQL errors

`_q()` now wraps `conn.execute(sql, params)` in try/except and returns
`[{"error": "..."}]` on failure. Without it, an agent-generated `SELECT`
with a syntax error propagates `sqlite3.OperationalError` up through ADK's
`Runner.run_async()` and crashes the parallel TaskGroup of the
DebriefDataPhase — taking out all 9 data agents on the failure of any one.

---

## Consequences

**Positive:**

- Every signal the AiM YAML emits now has an agent that can talk about it.
- The "god agent" (`PitwallOrchestrator`) brief/debrief narratives see
  every signal domain. Drivers can ask "did I improve at T6?" and the
  CornerCoach answer cross-references measured handling balance and
  traction events for T6, not just lap-time grade history.
- Sentinel-aware aggregates correct one of the YAML-pipeline bugs the
  earlier agent runs surfaced (max brake `4519 bar → 90.8 bar` after the
  filter, matching the realistic E46 M3 brake-pressure envelope).
- The `SafetyMonitorAgent` directly answers the "what changed" question
  when pace drops mid-session — previously this needed manual SQL.
- `HandlingBalanceAgent` finally puts the gyros to work and emits the
  measurement engineers want (balance ratio per corner), instead of the
  inferential coast-percent heuristic.

**Negative:**

- 9 parallel data agents per debrief means 9× the LocalLLM token cost per
  paddock debrief call. On gemma4:e4b via Ollama that's ~80 s for the
  whole debrief on this Mac (vs. ~25 s for the V1 3-way phase). On Pixel
  10 production targets — still acceptable for paddock-tier 2–15 s
  budget per agent, fan-out is parallel.
- Bigger surface to keep ADR-aligned. Six new tools to test, six new
  intents to keep classifier-tuned.
- The lap-modulo distance attribution assumes Sonoma — `TRACK_LENGTH_M`
  comes from `pitwall.features.track.sonoma`. Multi-track sessions will
  need a per-session track length lookup; not blocking today.

**Neutral:**

- Phase-2 doesn't change anything about the LocalLLM transport
  (ADR-024/ADR-025), the hot path (ADR-017), or the warm path. Everything
  added is paddock-tier.

---

## Validation

- 18/18 intent-classifier cases pass for the new + old patterns.
- All six new tools run cleanly against the real Sonoma SQLite, returning
  real numbers: 90.8 bar peak brake (sentinel-filtered), 1.81 G peak combo,
  oil pressure 0.77–5.79 bar with 1 load-gated anomaly, 321 wheelspin
  events, 94.1/100 smoothness score, 1 safety event (brake-switch).
- DebriefPipeline executes the 9-way parallel data phase end-to-end and
  produces a narrative citing tire / handling / engine numbers.
- `_q` error wrap prevents agent-generated SQL bugs from killing the
  TaskGroup.

---

## References

- [ADR-019](019-adk-multi-agent-backend.md) — original 18-agent topology
- [ADR-020](020-adk-agent-architecture-refactor.md) — Sequential/Parallel pipeline pattern
- [ADR-021](021-adk-second-audit.md) — `Runner` API + ParallelAgent race fix + KV-cache sessions
- `data/cars/bmw_e46_m3.yaml` — AiM MXP CAN config + sentinel documentation
- `data/formulas/standard.yaml` — formula registry for `psi_to_bar`, `f_to_c`, etc.
- `apps/edge-daemon/pitwall/adk_tools.py` — 21 tools (15 V1 + 6 phase-2)
- `apps/edge-daemon/pitwall/features/coaching/adk_agents.py` — 23 agents + orchestrator + pipelines
