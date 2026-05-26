# ADR-013: Frontend Visualizes, Backend Reasons

**Status:** Accepted
**Date:** 2026-04-28

## Context

Two parallel runtime stacks have grown side-by-side:

- **Python backend** in `src/pitwall/features/` + `src/pitwall/__main__.py` — sensor fusion, sonic model, coach engine, pedagogical vectors, LLM clients, arbiter, DuckDB.
- **Flutter / Kotlin frontend** in `flutter/` — Pixel 10 app with on-track HUD, paddock review screen, sensor Bluetooth I/O, audio output, **and a parallel reimplementation of sensor fusion, sonic model, message arbiter, and pedagogical vectors in Kotlin**.

The duplication was useful during the merge to validate the architecture in two languages, but it creates drift risk: a coaching change has to land twice, and Bentley pedagogy / system prompts live in two places. As coaching gets richer (markers, named pace notes, LLM-grounded prompts) the cost grows.

The product team's directive on 2026-04-28 is unambiguous: **the frontend owns visualization only; all coaching logic, LLM calls, and system instructions live in the backend**.

## Decision

**Frontend (`flutter/`) responsibilities — and only these:**
- Sensor I/O over Bluetooth and USB (Racelogic Mini via BT, USB-CAN adapter via USB, Pixel Earbuds pairing) — the radios and ports are physically on the device.
- Local audio output (TTS playback of `pace_note`, tone synthesis from `cues`).
- Screen rendering: on-track Signal Light HUD, paddock dashboard, session-management UI.
- Session lifecycle UI: START / STOP / RECORD / REVIEW buttons that call the backend.
- VBO file picker / replay UX (the file lives on the device; the parsing logic does not).

**Backend (`src/pitwall/features/` + `src/pitwall/__main__.py`) responsibilities:**
- Sensor fusion (Kalman / Butterworth / complementary filters, confidence annotation).
- Track loader, marker resolution, corner geometry.
- Sonic model (rule-based + LSTM-driven `compute_cues`).
- Coach engine (`RuleCoach` + `LitertCoach` running Gemma 4 E2B via MediaPipe Genai), system prompts, pedagogical vectors.
- Hot-path LLM orchestration (decides *when* to fire Gemma; if running, owns the system prompt). The TPU inference call itself may still execute in Kotlin via LiteRT for latency, but the prompt + decision come from the backend.
- Arbiter (priority, cooldown, corner suppression).
- Persistence (DuckDB sessions / laps / coaching_notes / telemetry frames).

**The seam** is the existing HTTP API on `127.0.0.1:8765` ([ADR-010](010-http-bridge-warm-path.md)). Every coaching decision flows through it. Existing Kotlin re-implementations of backend logic are **deprecated** — kept temporarily for the May 23 field test as a fallback if the bridge is unreachable, then removed.

## Concrete migration list

| Currently in `flutter/` | Disposition |
|---|---|
| `audio/AudioEngine.kt` | **Keep** — frontend (audio rendering) |
| `data/{TelemetryFrame,TrackMap,AudioCue}.kt` | **Keep** — frontend data classes for deserialization from the API |
| `fusion/{SensorFusion,Filters}.kt` | **Move** — backend owns sensor fusion; frontend should send raw frames to `POST /fuse` (new endpoint) and consume the fused output |
| `hotpath/GemmaEngine.kt` | **Deprecate fully** — Python in Termux can reach the Tensor TPU via MediaPipe Genai's LiteRT-LM runtime, so the backend executes Gemma 4 E2B inference itself (`LitertCoach`). Kept only as a fallback through the May 23 field test, then removed. |
| `hotpath/SonicModel.kt` | **Deprecate** — duplicates Python `sonic_model`; replace with `cues` from `/analyze` |
| `hotpath/PedagogicalVectors.kt` | **Deprecate** — duplicates `coach_engine.match_bentley_concept` |
| `arbiter/MessageArbiter.kt` | **Refactor** — arbiter logic moves backend-side; Kotlin keeps a thin "render this message now" gate (cooldown is enforced by the bridge) |
| `pipeline/AntigravityPipeline.kt` | **Deprecated** — telemetry persistence is handled by DuckDB in the bridge. Removed post field-test. |
| `service/{PitwallService,ReplayService}.kt` | **Keep** — Android foreground service is a frontend concern (battery, lifecycle) |
| `lib/screens/*.dart` | **Keep** — visualization only |
| `lib/platform/pitwall_channel.dart` | **Keep** — MethodChannel into Kotlin services |

## Backend additions implied by this decision

| New endpoint | Replaces | Notes |
|---|---|---|
| `POST /fuse` | `SensorFusion.kt` | Accept raw Racelogic + USB-CAN frames; return confidence-annotated `TelemetryFrame` |
| ~~`POST /hotpath/prompt`~~ | (no longer needed) | Originally proposed when Kotlin was going to execute Gemma inference. With `LitertCoach` running in the backend the round-trip is eliminated. |
| `POST /arbiter/submit` + `GET /arbiter/next` | `MessageArbiter.kt` | Long-poll or websocket; one queue, owned by Python |
| `GET /coach/concepts` | `PedagogicalVectors.kt` | Static introspection — what concepts can fire today |
| `GET /track/markers` | `TrackMap.kt` marker fields | Replaces baked-in marker data on the Flutter side |

These are placeholders — none are implemented yet. They land as the migration proceeds.

## Consequences

**Positive**
- Single source of truth for coaching, system prompts, pedagogy. Bentley curriculum updates are one PR, not two.
- Easier A/B testing of coaches (RuleCoach vs LitertCoach vs any future engine) — all gated by `--coach` on the bridge, no Flutter rebuild.
- The bridge's session/laps/coaching_notes tables become the canonical session record. Replay / leaderboard / scoring all read from there.
- Frontend builds get smaller; debugging gets simpler (one place to look when coaching misbehaves).

**Negative**
- **Latency**: every hot-path decision is a localhost round-trip. Mitigation: localhost is < 5 ms, dwarfed by inference (~30 ms Gemma TPU). Acceptable.
- **Bridge becomes a single point of failure on-device.** Mitigation: existing 3-tier fallback (bridge → Gemini → mock) plus future Kotlin "render-only" replay of last-known coaching. If the bridge dies mid-lap the driver hears the last fired pace note finish, then silence — better than a crash.
- **Migration cost**: Vijay's PR-1 Kotlin code partially gets deprecated. Mitigation: phased — keep duplicate code through May 23 field test as a fallback, remove after sprint wrap.
- **Termux dependency on the device** for full coaching. Mitigation: the field-test setup already requires Termux; for Pixel-only-no-Termux installs the Flutter app falls through to a mock coach. There is no cloud LLM tier per [ADR-012](012-coach-engine-adapter.md).

## Related

- [ADR-002 — Split-Brain with Arbiter](002-split-brain-arbiter.md) — arbiter still split-brain (hot LiteRT + warm bridge), but state lives backend-side now
- [ADR-003 — Gemma 4 Edge LLM](003-gemma-edge.md) — execution stays on TPU; orchestration moves to backend
- [ADR-006 — Sensor Fusion](006-sensor-fusion.md) — implementation moves Kotlin→Python
- [ADR-010 — HTTP Bridge as Warm-Path Tier 1](010-http-bridge-warm-path.md) — the seam
- [ADR-012 — Coach Engine Adapter](012-coach-engine-adapter.md) — the LLM-agnostic interface this ADR makes mandatory rather than optional
