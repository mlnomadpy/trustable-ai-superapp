# Pitwall Driver Profile Metrics

The Profile Tab in the Paddock evaluates the driver across 5 dynamic skills. Because we do not have full onboard physics simulation telemetry (e.g. steering angle, tire slip, suspension travel), these metrics are derived heuristically from the smartphone's GPS/IMU sensor fusion and the corner segmentation logic.

## 1. Braking Precision (Anti-Coasting)
A precise driver transitions directly from the throttle to the brake pedal and back again. "Coasting" (being off both the throttle and the brake) implies hesitation, lack of commitment, or early braking. 

- **Calculation**: Coasting is measured as the percentage of frames where the driver is neither applying significant throttle nor brakes. The metric assumes that ~30% coasting across a corner is poor.
- **Formula**: `max(0.0, 1.0 - (Average Coast Pct / 30.0))`

## 2. Trail Braking
Trail braking is the technique of keeping a light but decaying pressure on the brake pedal as the car turns into the corner, keeping weight over the front wheels to aid rotation.

- **Calculation**: A frame is considered "trail braking" if the driver is in the **entry phase** (first 33%) of a corner and the brake pressure is > 3%. We measure the percentage of entry frames that include trail braking.
- **Formula**: `min(1.0, (Average Trail Pct) * 2.0 / 100.0)`
  *(Note: A 50% trail braking duration across corner entry yields a 100% score).*

## 3. Corner Entry Speed
Rolling sufficient minimum speed into the corner entry.

- **Calculation**: Compares the driver's observed average speed during the entry phase of the corner to the "gold standard" reference speed for that corner.
- **Formula**: `min(1.0, Average(Observed Entry Speed / Reference Entry Speed))`

## 4. Apex Commitment
Carrying speed through the tightest part of the corner without over-slowing.

- **Calculation**: Compares the driver's observed average speed during the apex phase (middle 33%) of the corner to the reference apex speed.
- **Formula**: `min(1.0, Average(Observed Apex Speed / Reference Apex Speed))`

## 5. Throttle Pickup (Exit Speed)
Getting on the throttle early to maximize speed down the subsequent straight. Good throttle pickup directly correlates to higher exit speeds.

- **Calculation**: Compares the driver's observed average speed during the exit phase (final 33%) of the corner to the reference exit speed.
- **Formula**: `min(1.0, Average(Observed Exit Speed / Reference Exit Speed))`
