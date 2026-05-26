# ADR-010: HTTP Bridge as Warm-Path Tier 1

**Status:** Accepted
**Date:** 2026-04-28

## Context

The Flutter Pixel 10 app needs strategic coaching beyond what `GemmaEngine` (hot-path TPU inference) can produce in <50 ms. The original sprint design called for Vertex AI / Gemini 3.0 over 5G, with Antigravity store-and-forward as the transport. In practice:

- Cellular service at racetracks is unreliable.
- Vertex AI round-trip is 1–3 s — usable, but burns API quota.
- The full Python coaching stack (`sonic_model.compute_cues`, `coach_engine`, `track_loader` with markers) lives in `src/pitwall/features/` and is the canonical implementation; reproducing it in Kotlin is a maintenance liability.

`src/pitwall/__main__.py` (introduced 2026-04-28 by VijayVivekanand/android PR #1, extended by this ADR) wraps the Python stack in a Flask HTTP server on `127.0.0.1:8765` and is reachable from the Pixel app via `adb reverse` or a Termux loopback when running on-device.

## Decision

The bridge is the **only warm path**. Per [ADR-012](012-coach-engine-adapter.md), the project committed to on-device coaching exclusively — no cloud LLM tier. The Flutter app calls:

1. **Bridge** at `127.0.0.1:8765/analyze` — full `sonic_model` + `coach_engine` (RuleCoach + LitertCoach), < 50 ms, offline-capable.
2. **Mock** — fixed strings for unit tests and demo fallback if the bridge is unreachable.

`/analyze` returns:
- `coaching` — race-engineer-style summary (existing contract, unchanged).
- `pace_note` — rally-style verbal cue from `coach_engine` (additive, may be empty).
- `coach_source` — engine name (`rule` / `litert` / ``).
- `cues` — serialized `AudioCue` list for HUD rendering.

State is persisted to a single DuckDB file (`tools/pitwall_sessions.duckdb`) with three tables: `sessions`, `laps`, `coaching_notes`.

## Consequences

**Positive**
- One canonical coaching implementation (Python) used by both the dev TUI and the Pixel app — no Kotlin/Python drift on coaching logic.
- Sub-50 ms warm-path latency without cloud dependency, exactly when the driver needs it on track.
- DuckDB persistence gives us session replay + leaderboard storage on-device without a server.
- Coach inference runs in-process via MediaPipe Genai — no extra HTTP hop or model server to maintain.

**Negative**
- Adds a Python runtime requirement on the Pixel device (Termux). Mitigation: Tier 2 + Tier 3 fallbacks make this best-effort, not required.
- Two HTTP hops on the device (Flutter → bridge → coach). Mitigation: localhost loopback + < 5 ms Flask serving cost is dominated by `sonic_model` inference (~30 ms) which we'd pay anyway.
- DuckDB file is single-writer — multi-driver shared leaderboards still need a server eventually.

## Related

- [ADR-002 — Split-Brain with Arbiter](002-split-brain-arbiter.md) (the warm path the bridge serves)
- [ADR-004 — Antigravity Store-and-Forward](004-antigravity-pipeline.md) (the transport that delivers bursts to `/analyze`)
- [ADR-009 — Graceful Degradation](009-graceful-degradation.md) (the 3-tier fallback ladder)
- [ADR-012 — Coach Engine Adapter](012-coach-engine-adapter.md) (the LLM-agnostic interface the bridge exposes)
- [API reference](../api.md)
