# Architecture Decision Records

Decisions for the Pitwall Sprint, adapted from the [Pitwall open-source project](https://github.com/...) with modifications for the Google hardware stack and production requirements.

## Index

| ADR | Title | Status | Origin |
|-----|-------|--------|--------|
| [001](001-confidence-frame.md) | Confidence-Annotated Telemetry Frame | Accepted | From Pitwall, adapted for Racelogic + OBDLink |
| [002](002-split-brain-arbiter.md) | Split-Brain Architecture with Message Arbiter | Accepted | From Pitwall, adapted for Gemma 4 + Gemini 3 |
| [003](003-gemma-edge.md) | Gemma 4 as Edge LLM on Pixel 10 TPU | Accepted | New for sprint (replaces Pitwall's rules engine) |
| [004](004-antigravity-pipeline.md) | Antigravity Store-and-Forward Pipeline | Accepted | New for sprint (replaces Pitwall's SSE streaming) |
| [005](005-pedagogical-vectors.md) | Pedagogical Vector Retrieval from Ross Bentley Curriculum | Accepted | New for sprint (replaces Pitwall's hardcoded rules) |
| [006](006-sensor-fusion.md) | Sensor Fusion for Racelogic + OBDLink | Accepted | From Pitwall ADR-026, adapted for pro hardware |
| [007](007-event-sourced-profile.md) | Event-Sourced Driver Profile | Accepted | From Pitwall ADR-023, unchanged |
| [008](008-rule-testing.md) | Pedagogical Vector Regression Testing | Accepted | From Pitwall ADR-027, adapted for vectors |
| [009](009-graceful-degradation.md) | Graceful Degradation Protocol | Accepted | From Pitwall ADR-028, adapted for single-device |
| [010](010-http-bridge-warm-path.md) | HTTP Bridge as Warm-Path Tier 1 | Accepted | New 2026-04-28 — codifies `src/pitwall/__main__.py` |
| [011](011-named-marker-schema.md) | Named-Marker Schema for Track Coaching | Accepted | New 2026-04-28 — markers, nicknames, coaching tips |
| [012](012-coach-engine-adapter.md) | Coach Engine Adapter (on-device LiteRT-LM) | Accepted | New 2026-04-28 — `RuleCoach` + `LitertCoach` |
| [013](013-frontend-backend-boundary.md) | Frontend Visualizes, Backend Reasons | Accepted | New 2026-04-28 — backend owns LLM logic + system prompts |
| [014](014-sonoma-as-the-product.md) | Sonoma is the Product | Accepted | New 2026-04-28 — three-mode coaching + analysis pipeline + visualisation bundles, all Sonoma-hardcoded |
| [015](015-universal-telemetry-sink.md) | Universal Telemetry Sink + Capability Model | Accepted | New 2026-04-29 — tall signal store + registry + capability-aware coaches/widgets for any car / any data feed |
| [016](016-can-bus-ingest-and-frontend-pivot.md) | USB-CAN Ingest + Vue PWA Frontend | Accepted | New 2026-04-29 — kills BLE + native Flutter app; everything non-presentation goes in pitwall, frontend becomes a Vue PWA |
| [017](017-three-tier-coach-architecture.md) | Three-Tier Coach Architecture (LLM in paddock, canonical phrases on track) | Accepted | New 2026-04-29 — `LitertCoach.propose()` no longer calls the LLM; in-drive becomes RuleCoach + canonical phrases; LLM reserved for `brief()` + `debrief()`; cloud Gemini removed |
| [018](018-field-readiness-blockers-and-pedagogy-tuning.md) | Field-readiness blockers + pedagogy tuning (Team 2 review) | Accepted | New 2026-04-30 — LLM friction sink, audio ducker, Kalman dead-reckoning, transition-focused pedagogy, highlight-reel debrief opener; framework refactor deferred post-Sonoma |
| [019](019-adk-multi-agent-backend.md) | ADK Multi-Agent Paddock Backend | Accepted | New 2026-05-01 — 18-agent ADK topology, 15 SQL-safe tools, conversations + agent_traces tables, `/coach/ask` Q&A endpoint |
| [020](020-adk-agent-architecture-refactor.md) | ADK Agent Architecture Refactor | Accepted | New 2026-05-01 — 7 structural fixes: `PitwallOrchestrator`, `SequentialAgent`/`ParallelAgent` pipelines, `output_key` pattern, SQL safety, `save_voice_scripts` |
| [021](021-adk-second-audit.md) | ADK Second Audit — Runner, Concurrency, Feature Gaps | Accepted | New 2026-05-01 — `Runner` API, race-condition fix, persistent sessions for KV-cache reuse, `PitwallTracingPlugin` + `agent_traces` |
| [022](022-openai-compatible-backend-selector.md) | On-Phone LocalLLM Server (OpenAI-Compatible) | Accepted | New 2026-05-12 — adopts [LocalLLM](https://www.tahabouhsine.com/localllm/) APK as the primary on-device LLM server; `PITWALL_ADK_BACKEND=openai` dials it over `127.0.0.1:8099/v1`. Legacy `engine` (in-process) and `litertlm` (`lit serve`) remain available; same `openai` path also covers Ollama / LM Studio / llama.cpp / vLLM on dev boxes |
| [023](023-on-device-voice-onnx.md) | On-Device Voice (ONNX) for TTS + STT | Proposed | New 2026-05-23 — replaces Web Speech API with `onnxruntime-web` + Piper en-GB TTS + sherpa-onnx streaming Zipformer STT, ~55 MB models cached in OPFS; restores on-device guarantee at the voice layer; pre-rendered MP3 hot-phrase fast path retained |
