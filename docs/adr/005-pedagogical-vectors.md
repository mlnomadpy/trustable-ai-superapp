# ADR-005: Pedagogical Vector Retrieval from Ross Bentley Curriculum

## Status
Accepted

## Origin
New for sprint. Replaces Pitwall's hardcoded DECISION_MATRIX with structured driving curriculum.

## Context
Pitwall's coaching rules are hardcoded threshold checks:

```
TRAIL_BRAKE: brake > 10 AND |gLat| > 0.4 → "Trail brake, load the front."
```

This fires at the right time but doesn't explain why, can't adapt to skill level, and doesn't connect to a coherent curriculum. A beginner hearing "trail brake" doesn't know what that means or why it matters.

Ross Bentley's Speed Secrets curriculum provides a structured, pedagogically sound framework for teaching performance driving. Concepts like weight transfer, traction circle, slip angle, late apex, and vision have specific telemetry signatures that can be detected in real time.

## Decision
Encode Ross Bentley's curriculum as **pedagogical vectors** — structured JSON objects mapping telemetry conditions to driving concepts, with coaching text calibrated per skill level.

Each vector has:
- **Trigger conditions:** telemetry thresholds that activate the vector
- **Confidence requirements:** minimum signal confidence to activate
- **Physics explanation:** the underlying vehicle dynamics concept
- **Coaching by level:** beginner, intermediate, advanced messaging
- **Anti-patterns:** common mistakes detectable from telemetry
- **Gold Standard reference:** what AJ does at this moment

Vectors are matched to incoming frames by the pre-filter. Matched vectors are injected into Gemma 4's prompt as context, enabling the LLM to generate physics-grounded coaching that references the curriculum.

**This is context injection, not RAG.** The vector DB is small (~50 vectors covering the full curriculum). All vectors are loaded at startup. Matching is simple condition evaluation, not embedding similarity search.

## Consequences
Positive: Coaching is grounded in a proven curriculum. Explanations reference real physics. Skill-level adaptation is built into each vector. Anti-patterns catch specific mistakes. Gold Standard provides concrete targets. Negative: Vectors must be curated and tested (ADR-008). The curriculum is opinionated (Ross Bentley's approach, not the only valid approach). Vectors don't cover every possible driving situation — edge cases get generic coaching from the LLM.
