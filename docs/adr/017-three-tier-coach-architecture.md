# ADR-017: Three-Tier Coach Architecture (LLM in paddock, canonical phrases on track)

**Status:** Accepted
**Date:** 2026-04-29

## Context

Until 2026-04-29, `coach_engine.LitertCoach.propose()` was the in-drive
coaching entry point — meant to fire mid-stint, sub-corner, with on-device
LLM-generated rally pace notes. The implementation was correct in shape
(MediaPipe Genai → on-device Gemma 4 E2B), but the *latency* never
matched the use case.

Measured 2026-04-29 on Apple Silicon CPU using `litert-lm` (the actual
runtime that ships, not the desktop-unsupported `mediapipe.tasks.python.genai`):

| Prompt size | First token | Total |
|---|---|---|
| Short cue (~30 tokens out) | ~250 ms | ~470 ms |
| Pre-brief (~200 tokens out) | ~600 ms | **6.7 s** |
| Debrief (~250 tokens out) | ~600 ms | **9–12 s** |

On-Pixel-Tensor-G5 numbers will be similar order of magnitude (Tensor G5's
NPU helps decoding throughput but not first-token; expect 2–4 s for short
cues, 10+ s for long ones). **None of these are useful inside an apex
window, where the corner-entry → corner-exit loop is sub-second.**

We also measured the in-drive cue cadence the existing arbiter is tuned
for: max one cue every 3 s ([ADR-002](002-split-brain-arbiter.md)), which
already implies that in-drive cues should be *short, predictable, and
reliable* — not freshly LLM-generated each time.

## Decision

**Three tiers**, each with the right runtime:

| Tier | When | Latency budget | Runtime |
|---|---|---|---|
| **Pre-brief** | Paddock, pre-session | 2–8 s OK | LiteRT-LM Gemma 4 E2B (`coach_engine.LitertCoach.brief()`) |
| **In-drive** | On-track, mid-stint | < 100 ms | RuleCoach (canonical phrases) + a future pre-rendered audio cache, keyed by `(corner_id, phase, bentley_concept)` |
| **Post-session debrief** | Paddock, post-session | 8–15 s OK | LiteRT-LM Gemma 4 E2B (`coach_engine.LitertCoach.debrief()`) |

Concretely, in `coach_engine.py` (now split across `features/coaching/litert_coach.py` and `features/coaching/rule_coach.py` per PR #30; the `coach_engine` import path is preserved as a shim):

- `LitertCoach.brief()` and `LitertCoach.debrief()` keep their current
  shape — they call `_generate(system_prompt, user_prompt)` which goes
  through `litert_lm.Engine.create_conversation(...).send_message(...)`.
- `LitertCoach.propose()` becomes a one-liner that returns
  `self._fallback.propose(ctx)` — i.e. it forwards every in-drive cue
  to RuleCoach. The LLM is never invoked in-drive, regardless of whether
  the model is loaded.
- `RuleCoach.propose()` stays the canonical-phrase emitter, pulling from
  `TROD_VOICE`, `CORNER_TIPS`, named markers (ADR-011), and the 9 Bentley
  concepts via `match_bentley_concept`.

## Why this is *strictly* better than "LLM mid-drive"

1. **Latency floor is now the right shape.** A driver hears "brake at the
   bridge" 200 ms after the geofence trigger, not 3 s after — and 200 ms
   is bounded by audio-pipeline latency, not LLM token decode.
2. **Predictability is a feature.** The same corner gets the same
   canonical phrase every lap. Drivers learn to anticipate and respond
   to a fixed vocabulary; LLM-generated cues drift in word choice and
   register, which is *worse* coaching.
3. **No coaching during a Doze suspend.** If the bridge process is paged
   out by Android while the LLM is mid-decode, the cue arrives during
   the next corner — which is dangerous. Canonical phrases are a single
   string lookup; they survive suspend.
4. **Pre-rendered audio is plausible.** When the in-drive coach is just
   "look up phrase id, play .mp3", we can render the entire phrase library
   once with a higher-quality TTS (Gemini Flash TTS, ElevenLabs,
   gemini-2.5-flash-tts on Termux) and ship the cache. Latency becomes
   "time to play one .mp3 from disk" ≈ 30 ms.
5. **Quality-on-demand survives.** Drivers who want fresh phrasing get
   it pre-session (via brief) and post-session (via debrief). Those are
   the contemplative phases where 3–8 s isn't a problem.

## What this rules out

- **No LLM call inside any frame-handler hot path.** `coach_engine.propose`,
  `sonic_model.compute_cues`, the CAN reader's `_consume`, the SSE
  emitter's per-cue path: none of them may import or invoke an LLM. Code
  review must catch this.
- **No "just for this one feature" LLM mid-drive.** Future temptations
  ("AI corner classifier", "natural-language pace note variation",
  "personalised coaching adapter") — all paddock-only.
- **No "warm-up the LLM during the out-lap" optimisation.** The model is
  warm at session start (we pre-load it during `make_coach('auto')`).
  Out-lap should be LLM-free; safety cues (P3) only.

## What this enables (next-up work)

- **Pre-rendered phrase library**: render every `(corner, phase, concept)`
  combination through a high-quality TTS once, ship as `.mp3` cache.
  ~50–100 phrases × ~3 s each = ~5 minutes of audio, single-digit MB.
- **GPS+marker association**: in-drive cues already use named markers
  (`next_brake_marker_label`); the phrase-id lookup replaces "{distance}m"
  with "the bridge" / "the bump" / "the K-wall bend" deterministically.
- **Future expansion**: when GPU latency drops (e.g. Tensor G6, MLX
  M-series Metal), revisit. Today's call is right for today's hardware.

## Implementation

Shipped 2026-04-29 alongside this ADR:

- `LitertCoach.propose()` rewritten — line ~819 of `coach_engine.py`,
  delegates to `self._fallback.propose(ctx)`.
- `LitertCoach._infer()` removed (was only called by `propose()`).
- `LitertCoach._generate()` rewritten to use `litert_lm.Engine` instead
  of the desktop-unsupported `mediapipe.tasks.python.genai.inference` API.
- `LitertCoach.brief()` + `debrief()` unchanged in signature; underlying
  `_generate()` swap is transparent.
- `tests/test_coach_engine_litert.py` added — 8 tests, all PASSED on the
  laptop with the actual model loaded; SKIPPED cleanly when the model
  file is absent (CI machines without the 2.4 GB download).
- The `propose()` short-circuit is *itself tested* —
  `test_propose_falls_through_to_rule_per_three_tier_scope` asserts the
  returned message's `reason` never starts with `litert:`.

## Pressure tests

1. **Cold start** — first call after process boot: `brief()` will be
   slower (KV cache warm-up). Acceptable; pre-brief is paddock.
2. **Model file moves between calls** — engine is held open for the
   process lifetime. If the file is deleted mid-process (e.g. user runs
   `litert-lm delete gemma-4-e2b`), the engine survives because libraries
   are mmapped; subsequent brief/debrief should still work until process
   restart.
3. **GPU backend** — ADR-016's CAN ingest fights for CPU; if we move LLM
   to GPU, latency drops further. Today: CPU only.
4. **Multiple coaches at once** — one `LitertCoach` per process. Don't
   instantiate twice (each loads 2.4 GB into RAM); use the singleton
   `make_coach('auto')` pattern in the bridge.
5. **Termux deployment** — same `litert-lm` pip package, same `.litertlm`
   file format, same code path. The Pixel 10's Tensor G5 is currently
   used as CPU only (NPU/TPU integration is litert-lm's roadmap, not
   ours). When NPU lands, brief/debrief get faster for free.

## Consequences

**Positive**
- In-drive coaching is now sub-100ms by construction.
- LLM is reserved for the use cases where its quality earns its latency.
- Code review surface for "is this a hot-path LLM call" is bounded — only
  `LitertCoach.brief()` and `.debrief()` are LLM call sites.
- Cloud Gemini is removed entirely from the bridge ([ADR-017 follow-up:
  `_gemini_insights` deleted, `/score` rewired to local Gemma]).

**Negative**
- The in-drive vocabulary is *fixed*. New phrases require code changes,
  not a prompt tweak. Mitigation: every Bentley concept (9) × every
  marker (16) × every skill level (3) gives 432 phrase slots — plenty.
- The pre-rendered phrase library doesn't exist yet. Until it does,
  in-drive TTS will be runtime-synthesised by the PWA's Web Speech API
  (lower quality, browser-default voice). Acceptable for May 23 demo.

## Related

- [ADR-002 — Split-Brain Architecture with Message Arbiter](002-split-brain-arbiter.md)
  — the in-drive cadence + priority model this builds on.
- [ADR-009 — Graceful Degradation Protocol](009-graceful-degradation.md)
  — RuleCoach is the fallback when LiteRT can't load.
- [ADR-011 — Named-Marker Schema](011-named-marker-schema.md) — the
  phrase keys (the bridge / the bump / the K-wall bend) that anchor
  in-drive cues.
- [ADR-012 — Coach Engine Adapter](012-coach-engine-adapter.md) —
  RuleCoach + LitertCoach interface; this ADR refines what
  LitertCoach.propose() means.
- [ADR-016 — USB-CAN Ingest + Vue PWA Frontend](016-can-bus-ingest-and-frontend-pivot.md)
  — the bridge architecture this coach scoping fits into.
