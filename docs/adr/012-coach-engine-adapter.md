# ADR-012: Coach Engine Adapter

**Status:** Accepted
**Date:** 2026-04-28 (revised)
**Supersedes itself** — earlier draft included an OpenAI-compatible HTTP coach (`LlamaCppCoach`); the project decision on 2026-04-28 is to **commit to on-device LiteRT inference exclusively**, so that adapter has been removed.

**Superseded in part by:** ADR-017 (LitertCoach.propose() no longer calls the LLM in-drive), ADR-022 (in-process LiteRT deprioritised in favour of OpenAI-compatible HTTP shim).

## Context

The Pitwall pipeline grew two coaching surfaces in parallel:

1. **`sonic_model.compute_cues()`** — rule-driven, emits `AudioCue` objects (continuous tones), used since the v1 prototype and wrapped by `src/pitwall/__main__.py`.
2. **A verbal coach** — short, rally-style pace notes per situation ("brake at the bridge", "trail to the apex"), tunable per driver level (beginner / intermediate / pro), grounded in the Ross Bentley curriculum (PDF + intel doc).

The verbal coach must run **on-device** with no cloud dependency, because cellular service at racetracks is unreliable and per-call API spend doesn't suit a free-tier deployment. The Pixel 10's Tensor TPU is the right hardware target. The deployable artifact is the **LiteRT-LM `.task`** bundle published by Google at `litert-community/gemma-4-E2B-it-litert-lm` on HuggingFace, executed via **MediaPipe Genai** (`mediapipe.tasks.python.genai.inference.LlmInference`). On Android the same `.task` file is reachable from Termux Python — the MediaPipe runtime handles backend selection (XNNPack on CPU, ML Drift on GPU, Tensor TPU when available) without us touching delegate APIs by hand.

## Decision

> Updated 2026-05 (PR #30): the monolithic `coach_engine.py` was split into focused modules — `engine_base.py`, `prompts.py`, `pedagogy.py`, `rule_coach.py`, `litert_coach.py`, `arbiter.py` — all under `src/pitwall/features/coaching/`. The `coach_engine` import path remains as a re-export shim; existing call sites keep working.

`src/pitwall/features/coaching/coach_engine.py` (the back-compat shim, or the split-out modules above) defines two implementations behind one interface:

```python
class CoachEngine:
    name: str
    def propose(self, ctx: CoachContext) -> Optional[CoachingMessage]: ...

class RuleCoach(CoachEngine):    # zero-dep templated, fallback when tflite unavailable
class LitertCoach(CoachEngine):  # LiteRT-LM via MediaPipe Genai, runs Gemma 4 E2B on the Tensor TPU
```

`make_coach(kind="auto"|"litert"|"rule", driver_level=, litert_model_path=)` picks an implementation. `auto` tries `LitertCoach` first; if `mediapipe` isn't installed or the `.task` model file is missing, it falls back to `RuleCoach`. `LitertCoach` itself also falls back per-call when its runtime fails, so calling code can always rely on getting *something* back. `kind="tflite"` is accepted as a deprecated alias.

Three contracts make this work:

1. **`CoachContext`** — a single struct that fully describes the current frame *plus* track context (next corner, marker labels, Bentley concept, driver level). Built by `build_context()` so both coaches consume identical inputs. Marker fields (`next_brake_marker_label`, `next_corner_nickname`, `next_corner_tip`) are populated automatically from the track JSON per [ADR-011](011-named-marker-schema.md).
2. **`CoachArbiter`** — priority + cooldown + corner-suppression gate, mirrors the Kotlin `MessageArbiter` from [ADR-002](002-split-brain-arbiter.md). All coaching proposals flow through one arbiter regardless of which engine produced them.
3. **`build_system_prompt()` + `build_user_prompt()`** — single source of truth for every system instruction sent to the LLM. The frontend never assembles or tunes prompts; that work lives backend-side per [ADR-013](013-frontend-backend-boundary.md). Per-driver-level voice (`beginner` / `intermediate` / `pro`) and per-track lore (Sonoma named landmarks, strategy notes) are composed here.

The bridge wraps a single `_coach` instance + `_arbiter` instance and surfaces them on every `/analyze` response as `pace_note` and `coach_source`. CLI flags: `--coach {auto,tflite,rule,off}`, `--tflite-model`, `--driver-level`.

## Why on-device LiteRT only

- **Tensor TPU access**: LiteRT with NNAPI delegate is the only way to use the Pixel 10's TPU from any process. Speed and battery cost both favour this over CPU inference.
- **Zero cloud dependency**: works at any track regardless of cellular coverage, no API quota, no auth.
- **Single artifact to deploy**: one `.task` file in shared storage, readable by the Python backend (Termux). Per ADR-013 the frontend does not run inference, so we don't need the file to be reachable from Kotlin.
- **Future cloud paths are still possible** without changing the interface — a hypothetical `GeminiCoach` or `VertexCoach` would just be another `CoachEngine` subclass. The decision to commit to LitertCoach is about avoiding *current* complexity, not closing future doors.

## Consequences

**Positive**
- One inference path. Less code, fewer dependencies, simpler `make_coach` factory.
- The same `CoachContext` and arbiter rules apply across `RuleCoach` and `LitertCoach`; behaviour is consistent.
- Hot-path Gemma 4 inference happens in the Python backend on the Tensor TPU; no Kotlin↔Python round-trip needed once `LitertCoach` is loaded.
- Graceful degradation: `auto` mode silently falls back to `RuleCoach` when the model isn't installed yet. Field-test demos work even with no model file.

**Negative**
- Termux dependency on the device for the LLM coach. Mitigation: `RuleCoach` covers the no-Termux case; the verbal coach degrades to templated phrasings, not to nothing.
- LiteRT-LM `.task` schemas vary by model release. Mitigation: MediaPipe Genai's `LlmInference.create_from_options()` abstracts most of this, and the prompt-building and response-parsing live in `LitertCoach._infer()` (~10 lines). Adapting to a new release is a localised edit.
- No remote-LLM fallback for emergency debugging. Acceptable trade-off given the deployment context.

## Related

- [ADR-002 — Split-Brain with Arbiter](002-split-brain-arbiter.md) (the arbiter rules every coach respects)
- [ADR-003 — Gemma 4 Edge LLM](003-gemma-edge.md) (the model this coach runs)
- [ADR-005 — Pedagogical Vector Retrieval](005-pedagogical-vectors.md) (the curriculum every coach is grounded in)
- [ADR-010 — HTTP Bridge as Warm-Path Tier 1](010-http-bridge-warm-path.md) (where the coach is exposed)
- [ADR-011 — Named-Marker Schema](011-named-marker-schema.md) (what the coach voices)
- [ADR-013 — Frontend Visualizes, Backend Reasons](013-frontend-backend-boundary.md) (why the coach + prompts live backend-side)
- [API reference](../api.md)
