# ADR-001: Confidence-Annotated Telemetry Frame

## Status
Accepted

## Origin
Adapted from Pitwall ADR-001. Same principle, simplified for pro hardware (fewer source-quality variations).

## Context
Even with professional hardware (Racelogic Mini + OBDLink MX), signal confidence varies. Racelogic GPS drops in tunnels or tree cover. OBDLink Bluetooth can disconnect. The coaching engine must know when to trust a signal and when to stay silent.

## Decision
Every signal carries `confidence` (0.0-1.0), `source`, `hz`, and `stale` metadata. Coaching rules (pedagogical vectors) declare minimum confidence per field.

With pro hardware, most signals are 0.95 under normal conditions. Confidence drops when:
- GPS satellite count < 6 (GPS confidence → 0.60)
- Bluetooth drops (CAN signals → stale)
- Racelogic enters a tunnel (GPS → 0.00, IMU maintains 0.95)

Gemma 4 receives confidence in the frame and is instructed not to coach on signals below threshold. A hard-coded pre-filter also blocks low-confidence frames from reaching the LLM to save TPU cycles.

## Consequences
Positive: No false coaching from degraded sensors, even momentarily. Negative: Slight frame overhead (mitigated by in-process data passing, no serialization for hot path).
