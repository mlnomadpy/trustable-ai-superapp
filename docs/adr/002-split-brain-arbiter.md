# ADR-002: Split-Brain Architecture with Message Arbiter

## Status
Accepted

## Origin
Adapted from Pitwall ADR-002. Same arbiter design, paths changed from rules/LLM/geofence to Gemma 4/Gemini 3.0.

## Context
V1 had both hot and warm paths sending audio simultaneously. Conflicting messages confuse the driver and erode trust. Mid-corner audio distracts from driving.

## Decision
All coaching from both paths flows through a message arbiter before reaching the driver.

**Arbiter rules:**
1. P3 (safety): immediate delivery, interrupts everything
2. P2 (technique): delivered on straights only (|gLat| < 0.3G)
3. P1 (strategy): queued behind P2
4. Conflict: same corner from both paths → higher priority wins; same priority → Gemma 4 wins (fresher data)
5. Global cooldown: 3 seconds between messages from different sources
6. Stale expiry: messages > 5 seconds in queue are dropped

**Corner suppression** prevents non-safety messages during cornering. At 130 mph, any distraction in a corner is dangerous.

## Consequences
Positive: No conflicting messages. No mid-corner distraction. Trust is built through consistent, well-timed coaching. Negative: Valid coaching can be dropped (stale expiry) or delayed (corner suppression). Mitigated by the fact that conditions will repeat next lap.
