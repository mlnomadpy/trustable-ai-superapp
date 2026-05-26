# ADR-003: Gemma 4 as Edge LLM on Pixel 10 TPU

## Status
Accepted

## Origin
New for sprint. Replaces Pitwall's hardcoded rules engine (hot path) with an on-device LLM.

## Context
Pitwall's hot path uses a hardcoded `DECISION_MATRIX` — an array of conditions evaluated per frame. This works but has limitations: it can't explain physics, can't adapt language to skill level, and can't reason about context beyond the current frame.

The Pixel 10 has an on-device TPU capable of running Gemma 4 at <50ms inference. This makes it feasible to replace hardcoded rules with an LLM that:
- Evaluates telemetry against pedagogical vectors (Ross Bentley curriculum)
- Generates contextual coaching, not just threshold alerts
- Adapts language to driver skill level (beginner vs pro)
- Understands **why** a technique matters (weight transfer, traction circle), not just **when** to cue it

## Decision
The hot path runs Gemma 4 on the Pixel 10 TPU. Every fused telemetry frame is evaluated by the LLM with matched pedagogical vectors as context.

**Inference budget:** <50ms per frame. At 50Hz, this means the LLM evaluates every frame if inference is fast enough, or every 2nd-3rd frame if needed.

**Pre-filter:** A hard-coded confidence gate runs before the LLM. Frames with all critical signals below threshold are not sent to Gemma 4 (saves TPU cycles). This is the only remaining hardcoded rule — everything else is LLM-driven.

**Fallback:** If the Pixel 10 TPU is overloaded (thermal throttling, background tasks), the system falls back to the Pitwall-style hardcoded decision matrix. The driver gets simpler coaching but never silence.

**Prompt includes:**
- Current frame with confidence metadata
- Matched pedagogical vectors (pre-selected by telemetry trigger conditions)
- Driver skill level
- Last 5 coaching messages (to avoid repetition)
- Corner context (approaching/in/exiting which corner)

## Consequences
Positive: Coaching is richer, more contextual, and adapts to skill level. The system can explain physics, not just issue commands. Negative: LLM inference is less deterministic than rules. Same frame may produce slightly different coaching. Mitigated by consistent prompting and pedagogical vector grounding. Fallback to rules if TPU is unavailable.
