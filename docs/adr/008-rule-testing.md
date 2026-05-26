# ADR-008: Pedagogical Vector Regression Testing

## Status
Accepted

## Origin
Adapted from Pitwall ADR-027. Same testing framework, applied to pedagogical vectors instead of hardcoded rules.

## Context
Pedagogical vectors are the coaching system's most safety-sensitive component. A vector that fires incorrectly can deliver wrong advice at 130 mph. Vectors must be tested before deployment.

## Decision
Every pedagogical vector includes embedded test cases:

1. **Unit tests:** Does the vector trigger on known inputs? Does it NOT trigger when it shouldn't?
2. **Confidence gate tests:** Does the vector stay silent when signal confidence is below threshold?
3. **Reference session tests:** Replay AJ's Gold Standard lap — does the vector fire the expected number of times at the expected corners?
4. **Conflict tests:** Can two conflicting vectors fire on the same frame?

Test cases are embedded in the vector JSON. The test suite runs:
- On every vector DB update
- Before each track session (pre-flight check)
- Against the Gold Standard reference lap as regression baseline

**Vectors that fail tests are disabled**, not deployed. The system logs which vectors are active and which are disabled due to test failures.

## Consequences
Positive: No untested coaching reaches the driver. Gold Standard provides a known-good regression baseline. Confidence gating is verified, not just declared. Negative: Every new vector requires test cases. Reference session data must be maintained. Test suite adds ~5 seconds to startup.
