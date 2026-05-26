# ADR-018 — Field-readiness blockers + pedagogy tuning (Team 2 review)

**Status:** Accepted — 2026-04-30
**Driver:** Sonoma Raceway field test, 2026-05-23 (~23 days out at acceptance)

## Context

The 2026-04-29 Team 2 architecture review (CONDITIONAL PASS) flagged three
production blockers and four pedagogy gaps. Each is small in isolation but
together they are decisive for whether the May 23 field test produces a
trustable coach or a buggy one. The review also recommended a long-term
framework refactor (decouple `CoachContext`, parameterise the LSTM input
layer, generalise the spatial loop). That refactor is **deferred** until
after Sonoma — touching it mid-deadline burns time we don't have, and the
blockers + pedagogy work is what actually moves the needle for the test.

## Decision

Ship seven changes on the `tests` branch ahead of the cut-off, all with
test coverage (358 passing, +42 over the pre-ADR baseline of 316):

### Field-readiness blockers

1. **LLM friction sink.** New `llm_friction` DuckDB table and a
   module-level `coach_engine.set_friction_logger` hook. Every
   `LitertCoach._generate` call (brief, debrief, fallback, error) emits
   one record carrying prompt/completion length, latency, truncation
   heuristic, and fallback flag. Surfaced via
   `GET /diagnostics/llm_friction` with p50/p95 latency, fallback rate,
   and per-role aggregation. The Pit Stall Setup screen polls this so
   the operator sees Gemma degradation *before* it bites mid-session.

2. **Audio ducker.** The PWA's audio bus grows a fourth layer, "tactical
   tones" (continuous pitch from the sonic model), with its own gain
   node. While TTS is speaking, the tone gain ramps to 12 % over 8 ms
   and back to 60 % over 80 ms. Bridge cue events now carry an
   `expected_tts_ms` hint (~150 ms/word, floor 800 ms) so the duck
   window matches the spoken phrase exactly. Specced in
   `docs/vue/06-audio-design.md` rule #4.

3. **Kalman dead-reckoning for distance.** New `tools/dead_reckoning.py`
   runs a 1D Kalman filter on `[distance, speed]` driven by CAN speed
   (50–100 Hz) and IMU `g_long`, with 10 Hz GPS as the absolute fix.
   `can_reader._consume` writes the *filtered* `distance_m` to the
   wide table and preserves the raw GPS reading in the tall store as
   `gps_distance_m` for diagnostic comparison. At 130 mph this closes
   the 5.8 m / 100 ms GPS gap that would otherwise blur marker-based
   coaching. Disable per-reader via `dead_reckon=False`.

### Pedagogy tuning (intermediate / Time-Trial driver)

4. **Nothing-time penalty.** Corner grade dimension weights now include
   `s_nothing` at 15 % (linear drop from 1.0 → 0.0 across 0 → 1.5 s of
   dead pedal time). Time-loss attribution multipliers for
   `coast_in_corner` and `nothing_time` raised so a 1 s gap claims ~60 %
   of the delta instead of 40 %. New `mid_corner_coasting` `@coach_rule`
   capability declaration covers in-drive cueing.

5. **Brake-release prompts.** Base + pre-brief system prompts coach the
   *shape* of the brake release ("roll the brake to the apex", "taper,
   don't drop", "longer trail to load the front") instead of static
   markers. The pre-brief explicitly forbids brake-marker prescriptions
   so the model doesn't fall back on "brake at the 100 board."

6. **Slip-angle oscillation rule.** New
   `analytics.slip_oscillation_events()` flags ≥4 friction-band crossings
   inside a 3 s window — the intermediate-driver pattern of overshooting
   the limit and reining it back. Wired into the session bundle as
   `slip_oscillations`; user prompt surfaces the count to the LLM;
   `slip_angle_oscillation` `@coach_rule` registered for in-drive use.

7. **Highlight-reel debrief opener.** Post-session system prompt now
   demands the model OPEN with a validated positive moment (best corner,
   tagged positive highlight, or pace progression) before any critique.
   The user-prompt builder pre-extracts the best-scoring corner and the
   first positive highlight into a `HIGHLIGHT REEL` section so the model
   has something concrete to lead with even on a rough session.

## Consequences

**Positive.** All three field-test blockers from the review are closed
and observable. The coach now teaches transitions (the actual
intermediate-driver gap) instead of locations (which the driver already
knows). Friction and slip telemetry give the post-session debrief
something to talk about beyond apex speed.

**Negative.** The corner grade weights changed — historical scores
written before this ADR aren't directly comparable. The
dead-reckoner introduces ~5 ms of per-frame Kalman work; cheap on a
Pixel 10 but enough to break two CAN pipeline tests that relied on race
timing (fixed in the same commit by using realistic monotonic
timestamps + a force-flush before assertions).

**Deferred.** The framework-extensibility recommendations from the
review (generic `StateContext`, parameterised LSTM I/O, 3D spatial
support) are post-Sonoma work. Don't start them before May 23.
