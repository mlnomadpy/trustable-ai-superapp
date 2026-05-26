# ADR-023 — On-Device Voice (ONNX) for TTS + STT

**Status:** Proposed
**Date:** 2026-05-23
**Relates to:** [ADR-013](013-frontend-backend-boundary.md), [ADR-017](017-three-tier-coach-architecture.md), [ADR-018](018-field-readiness-blockers-and-pedagogy-tuning.md), [ADR-022](022-openai-compatible-backend-selector.md)

---

## Context

ADR-017 made the on-device mandate binding for the LLM stack; ADR-022
completed it for the LLM server. The voice layer — TTS for the coach's
spoken output and STT for the driver's push-to-talk Q&A — is the last
component that still depends on whatever the user's browser ships.

Today the PWA implements voice through `src/pwa/src/shared/lib/voice.ts`,
a thin wrapper over the **Web Speech API**:

- `SpeechSynthesis` for TTS — voice quality and presence vary by OS
  build. iOS Safari's en-GB voices are flat; some Android WebViews
  ship no en-GB voice at all and silently fall back to en-US, which
  contradicts the en-GB coaching character we want.
- `SpeechRecognition` for STT — **Chromium-only in practice**. Firefox
  desktop has no implementation. Safari's `webkit`-prefixed variant on
  iOS 17+ works but ships transcripts to Apple servers in most regions,
  which is not on-device.

In the field deployment this matters. The driver's phone (Pixel 10 in
the Termux harness) runs Chromium, so Web Speech STT *does* work today —
but its quality on engine-noise / helmet-muffled input is poor, and on
the codriver's laptop in the paddock (where post-session debriefs and
"ask the coach a question" flows live) Firefox / Safari users get zero
STT.

The pre-rendered MP3 set described in `docs/vue/06-audio-design.md`
(~250 clips per coach, generated offline via Gemini 2.5 Flash TTS) covers
the **hot phrases** the canonical-phrase tier emits on track. It does
**not** cover:

- long-tail LLM-generated replies from the paddock Q&A endpoint
  (`/coach/ask`),
- ad-hoc debrief narration that wasn't anticipated at MP3-render time,
- any STT path at all.

For both of those, the PWA currently falls back to `SpeechSynthesis` /
`SpeechRecognition` — which means the on-device mandate of ADR-017 leaks
to whatever cloud the browser vendor happens to use.

---

## Decision

**Adopt ONNX-runtime-web with a fixed model pair for on-device voice**,
gated behind a backend selector in `voice.ts`. Web Speech remains as the
zero-dependency fallback for browsers that can't run the WASM workload
(or until the model has finished downloading on first launch).

### Picks

| Role          | Model                            | Size  | Why                                                                 |
| ------------- | -------------------------------- | ----- | ------------------------------------------------------------------- |
| TTS           | **Piper en-GB-medium (`alba` or `northern_english_male`)** | ~25 MB | Matches the `pickCoachingVoice()` en-GB-male preference; ~50ms first-byte on a desktop CPU; ONNX-native; permissive license |
| STT (primary) | **sherpa-onnx streaming Zipformer (`en` small)**           | ~30 MB | True streaming (partial transcripts during speech); designed for short utterances; runs on `onnxruntime-web` WASM-SIMD |
| STT (fallback) | **Whisper-tiny-en (Xenova ONNX)** | ~40 MB | Non-streaming but battle-tested; used only if sherpa-onnx fails to initialize (e.g. no SIMD) |

Total cold-start budget: **~55 MB** (Piper + sherpa-onnx). Whisper-tiny
is downloaded on demand, not at first launch.

### Architecture

```
src/pwa/src/shared/lib/voice/
  index.ts            ← public API (unchanged surface: voice.speak, voice.listen)
  backend.ts          ← Backend interface { speak, listen, canSpeak, canListen, kind }
  backend-webspeech.ts ← current implementation, lifted from voice.ts
  backend-onnx.ts     ← new: dispatches to worker
  onnx.worker.ts      ← new: hosts onnxruntime-web + Piper/sherpa-onnx
  models.ts           ← model URLs, OPFS cache, progress events
```

Public API surface (`voice.speak`, `voice.listen`, `voice.canSpeak`,
`voice.canListen`) does **not change**. Callers in `useVoiceConversation`,
`AskCoachMode`, and the audio store keep working without edits.

### Selection logic

```
backend = 'web-speech'                     // default for first paint
if capability_probe_passes:
    backend = 'onnx'                       // upgrade once models are ready
```

Capability probe (cheap, runs at app boot):

1. `crossOriginIsolated === true` (required for WASM threads).
2. `WebAssembly.Memory` with `shared: true` succeeds.
3. OPFS available (`navigator.storage.getDirectory`).
4. User hasn't opted out (`pitwall.voice.backend = 'web-speech'` in settings).

If any check fails → stay on Web Speech, log to the diagnostics panel.

### Model storage

Models live in **OPFS**, not the HTTP cache. iOS Safari evicts the HTTP
cache aggressively (historically ~50 MB cap); OPFS is exempt from that
quota policy and persists across PWA re-installs. The fetch path is:

```
1. Check OPFS for {piper-en-gb.onnx, sherpa-zipformer-en/*}
2. If missing → fetch from /assets/voice-models/ with progress events
   surfaced as a Pinia store (audio store gains downloadProgress).
3. Write to OPFS, hash-verify against manifest.json.
4. Instantiate ort.InferenceSession in the worker.
```

The PWA build ships **only the manifest**; the models are fetched once
on first launch (or pre-bundled in the Termux deployment by the build
script).

### Hot-phrase fast path is unchanged

The pre-rendered MP3 set documented in `docs/vue/06-audio-design.md`
remains the *fastest* path for canonical phrases on-track. ONNX TTS only
serves the long-tail (LLM replies, debrief narration). Order of
preference for any speak call:

1. Pre-rendered MP3 if the phrase has a hash hit.
2. ONNX Piper if the backend is `onnx` and models are loaded.
3. Web Speech `SpeechSynthesis` fallback.

### Audio-ducker contract

`estimate_tts_ms()` in `src/pitwall/features/coaching/cue_renderer.py`
becomes more accurate, not less — Piper's duration is deterministic
given the text. We update the estimator to use Piper's reported duration
when the cue's `voice_backend === 'onnx'`, falling back to the existing
150 ms/word heuristic otherwise.

---

## Consequences

### Positive

- **Cross-browser STT.** Firefox and Safari users get the same Q&A path
  as Chromium users.
- **On-device guarantee restored.** No transcript or synthesized phrase
  ever leaves the device — completes the ADR-017 mandate at the voice
  layer.
- **Voice character consistency.** Piper produces the same en-GB voice
  on every device; no more "iOS Safari sounds wrong" reports.
- **Lower latency once warm.** ONNX TTS first-byte is faster than Web
  Speech on Android in our preliminary tests (Web Speech buffers the
  whole utterance before speaking; Piper streams).
- **Offline-capable.** In-car / weak-signal scenarios stop degrading
  voice quality.

### Negative

- **55 MB first-load cost.** Mitigated by OPFS persistence, progress UI,
  and pre-bundling in the Termux deployment.
- **iOS Safari is the risk surface.** WASM threads require
  cross-origin-isolation headers (COOP/COEP) which the current static
  PWA host doesn't send. We'll need to either configure the host or
  serve from a service worker that injects the headers.
- **Worker plumbing + model asset pipeline** are new infrastructure. The
  build needs a step that places `voice-models/*` under `dist/assets/`
  and emits a hashed manifest.
- **`onnxruntime-web` adds ~3 MB to the JS bundle** (the runtime, not
  the models). Tree-shake aggressively; only the WASM + SIMD execution
  provider is needed.
- **Two STT engines to maintain.** sherpa-onnx primary, Whisper-tiny
  fallback — both have to track upstream ONNX format changes.

### Neutral

- ADR-018's audio-ducker contract is unchanged; only the backing
  duration source becomes more precise.
- The pre-rendered MP3 set keeps its role as the fastest path; nothing
  about ADR-014's Sonoma-hardcoded coach content changes.

---

## Migration plan

1. **PR 1 — refactor.** Lift current `voice.ts` into
   `backend-webspeech.ts` behind the new `Backend` interface. No
   behaviour change. Public API untouched. Ship.
2. **PR 2 — ONNX TTS only.** Add `backend-onnx.ts` + worker. Piper
   en-GB-medium. Behind feature flag `pitwall.voice.tts = 'onnx'`,
   default off. OPFS storage, progress UI, hot-phrase MP3 fast path
   wired. Dogfood on Pixel 10.
3. **PR 3 — ONNX STT.** Add sherpa-onnx streaming Zipformer. Same flag
   `pitwall.voice.stt = 'onnx'`, default off. Ship to Firefox/Safari
   users as the *only* working STT.
4. **PR 4 — flip defaults.** Once both have soaked one track day,
   capability probe upgrades to `onnx` automatically. Web Speech
   remains as the cold-start and degraded-runtime fallback.
5. **PR 5 — Termux pre-bundle.** Add models to the Termux deployment
   script so the first launch on a fresh Pixel 10 doesn't have to
   download 55 MB over a track-day hotspot.

---

## Open questions

- **iOS Safari COOP/COEP.** Do we ship cross-origin-isolation headers
  from the PWA host (preferred) or work around it with a
  service-worker-injection trick? Decision deferred to PR 2.
- **Piper voice choice.** `alba` is en-GB female; `northern_english_male`
  matches the en-GB-male coaching character today. Sample both with
  drivers before PR 2 lands.
- **Whisper-base vs whisper-tiny fallback.** Tiny is 40 MB and accurate
  enough for short commands; base is 75 MB and better on noisy input.
  Default to tiny; revisit if engine-noise WER is unacceptable.
- **Coach voice cloning.** Out of scope for this ADR — Piper supports
  voice cloning given 30 minutes of clean audio, but that's a Sprint+1
  conversation.

---

## Why not the alternatives

- **Keep Web Speech.** Loses the on-device guarantee on STT (Safari
  ships transcripts to Apple), loses Firefox STT entirely, voice
  character drifts across OSes. Rejected.
- **transformers.js / Whisper-only for STT.** Non-streaming, larger
  models for comparable accuracy on short utterances, no TTS story.
  Worse fit than sherpa-onnx for the racing Q&A use case.
- **Kokoro-82M for TTS.** Higher quality, but ~80 MB and slower
  first-byte. Revisit if Piper quality is rejected by drivers.
- **Server-side TTS via the coach bridge.** Would require the bridge to
  ship audio over WebSocket / SSE; adds latency, ties voice quality to
  the bridge's audio pipeline, and Termux has no GPU for fast TTS.
- **Pre-render every possible LLM reply.** Combinatorial; the long tail
  is exactly the case the LLM exists to handle.
