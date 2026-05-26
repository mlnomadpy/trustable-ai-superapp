# ADR-004: Antigravity Store-and-Forward Pipeline

## Status
**Superseded** — the Antigravity store-and-forward pattern was replaced by local DuckDB persistence when the project moved to fully on-device inference (see [ADR-012](012-coach-engine-adapter.md), [ADR-017](017-litert-lm-migration.md)). Vertex AI and Gemini 3.0 references below reflect the original sprint design, not the shipped architecture.

## Origin
New for sprint. Replaces Pitwall's SSE + UDP direct streaming with guaranteed delivery.

## Context
Pitwall uses SSE (2Hz JSON) and UDP (50Hz binary) for telemetry distribution. Both are fire-and-forget — if a frame is missed, it's gone. This is acceptable for the hot path (next frame arrives in 20ms) but problematic for the warm path:

- 5G at racetracks is unreliable (coverage gaps, congestion during events)
- A dropped telemetry burst means Gemini 3.0 misses an entire sector of driving data
- The warm path coaching becomes "blind" for 10-30 seconds during a dropout

Antigravity provides a store-and-forward pattern: buffer telemetry locally, send when connectivity is available, guarantee no data loss.

## Decision
Telemetry frames are buffered in a local ring buffer on the Pixel 10. Every 5-10 seconds, the buffer is packed into a burst and sent to Vertex AI via 5G.

**If 5G is available:** Burst is sent immediately. Vertex AI ingests, triggers Gemini 3.0, returns warm path coaching.

**If 5G is unavailable:** Burst is persisted to local storage (Pixel 10 SSD). When 5G returns, all persisted bursts are sent in order. Gemini 3.0 processes them retroactively. Coaching may be late but data is never lost.

**Burst format:** JSON array of confidence-annotated frames with session metadata (driver level, car, track, burst sequence number).

**Ordering guarantee:** Bursts carry sequence numbers. Vertex AI processes in order, even if delivered out of order after a reconnection.

## Consequences
Positive: No telemetry loss. Warm path always has complete data for analysis, even after 5G dropouts. Post-session analysis is complete. Negative: Warm path coaching may arrive late after a 5G dropout (driver has already passed the relevant corner). The hot path (Gemma 4, fully local) is unaffected by connectivity. Store-and-forward adds local storage I/O.
