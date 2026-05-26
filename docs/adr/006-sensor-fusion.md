# ADR-006: Sensor Fusion for Racelogic + OBDLink

## Status
Accepted

## Origin
Adapted from Pitwall ADR-026. Same fusion strategies, simplified for two pro-grade sources.

## Context
Even with professional hardware, fusion adds value:
- Racelogic GPS and OBDLink CAN both report speed — they can disagree
- Racelogic IMU picks up road vibration that corrupts G-force readings
- Between 20Hz GPS fixes, position jumps — dead-reckoning from IMU smooths this

## Decision
Three fusion strategies:

1. **Speed:** Kalman filter. Racelogic GPS weight 0.7, OBDLink CAN wheel speed weight 0.3. Outlier rejection if difference > 10 km/h.

2. **G-forces:** Butterworth 2nd-order low-pass filter at 12Hz on Racelogic IMU data. Removes road vibration while preserving driving dynamics (peak frequency ~5Hz).

3. **Position:** Complementary filter. Racelogic GPS provides absolute position at 20Hz. Between GPS fixes, IMU dead-reckoning fills gaps for smooth 50Hz position output. GPS corrects IMU drift on each fix.

No fusion needed for OBDLink CAN inputs (throttle, brake, steering, RPM) — these are direct sensor readings at 50Hz, ground truth.

## Consequences
Positive: Smooth position for geofence triggering (no stutter). Clean G-forces for friction circle analysis. Robust speed even if one source glitches. Negative: Filter parameters (Butterworth cutoff, Kalman weights) need tuning on-track. Dead-reckoning accumulates ~1m error between 20Hz GPS fixes — acceptable.
