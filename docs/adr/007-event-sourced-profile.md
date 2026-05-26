# ADR-007: Event-Sourced Driver Profile

## Status
Accepted

## Origin
From Pitwall ADR-023, unchanged. The same design works for the sprint.

## Context
The Crew Chief / warm path needs to remember the driver across sessions: what they're good at, where they struggle, how they've improved. Storing a mutable JSON profile that the LLM can write to causes contradictions and hallucination risk.

## Decision
The driver profile is **never written directly** by the LLM. It is computed from an append-only event log of measured facts from DuckDB session aggregations.

**Events** are measured facts: "Turn 3 exit speed avg 65mph, best 70mph, trail brake pct 40%."

**Profile** is computed on demand: linear trends per corner, weakest corner, strongest corner, suggested focus area.

The LLM (LitertCoach / Gemma 4 E2B) reads the computed profile and narrates it in pre-session briefings and post-session debriefs. It interprets but never modifies.

Driver preferences (car, goals, coaching level) are set manually, not by the LLM.

## Consequences
Positive: No hallucination in profile. No contradictions. Deterministic — same events always produce the same profile. Auditable — every assessment traces to a DuckDB query. Negative: Profile lacks "soft" observations. Linear trend analysis is simplistic. Event log grows linearly (mitigated by archiving old events).
