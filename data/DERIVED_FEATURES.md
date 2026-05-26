# Derived Features

Features computed at runtime from raw VBO signals. Not stored in the files.

---

## Unit Conversions

| Feature | Formula | Unit | From |
|---------|---------|------|------|
| `speed_ms` | `velocity / 3.6` | m/s | `velocity` (km/h) |
| `speed_mph` | `velocity * 0.621` | mph | `velocity` (km/h) |
| `lat_decimal` | `DD + MM.MMMMM / 60` | degrees | `lat` (DDMM.MMMMM) |
| `lon_decimal` | `-(DD + MM.MMMMM / 60)` | degrees | `long` (DDMM.MMMMM, West) |

## Spatial Features

| Feature | Formula | Unit | Use |
|---------|---------|------|-----|
| `distance` | Cumulative haversine from lat/lon | meters | Track position, lap detection |
| `curvature` | `d(heading) / d(distance)` | deg/m | Corner detection for auto track mapping |
| `distance_to_corner` | Distance to next corner entry geofence | meters | Feedforward timing for sonic model |
| `corner_name` | Which corner the car is in (or None) | string | Context for coaching rules |
| `lap` | Increment when GPS crosses start/finish | integer | Lap segmentation |
| `lap_time` | Time since last start/finish crossing | seconds | Performance metric |

## Vehicle Dynamics

| Feature | Formula | Unit | Use |
|---------|---------|------|-----|
| `gear` | Lookup from `RPM / (speed_kmh * ratio)` | integer | Shift analysis (CAN gear is broken at 255) |
| `friction_circle_pct` | `ComboAcc / max_session_ComboAcc * 100` | % | Grip utilization for coaching and sonic model |
| `brake_pct` | `Brake_Pressure / max_session_Brake_Pressure * 100` | % | Normalized 0-100 for rules |
| `yaw_rate` | `d(heading) / dt` | deg/s | Oversteer/understeer detection |
| `expected_yaw` | `f(speed, steering_angle, wheelbase)` | deg/s | Compare to actual yaw for over/understeer |

## Driving Phase Labels

| Feature | Condition | Use |
|---------|-----------|-----|
| `is_braking` | `Brake_Pressure > 5` | Phase classification |
| `is_trail_braking` | `Brake_Pressure > 3 AND abs(gLat) > 0.4` | Trail brake detection — highest-value coaching moment |
| `is_cornering` | `abs(gLat) > 0.4` | Corner detection |
| `is_accelerating` | `Throttle > 50 AND abs(gLat) < 0.3` | Straight-line acceleration |
| `is_coasting` | `Throttle < 10 AND Brake_Pressure < 2` | **Wasted time.** Primary coaching target for beginners. |
| `is_pit` | `speed < 15 km/h for > 10 seconds` | Session segmentation |
| `is_outlap` | First lap after pit, speed building from <30 to >100 | Exclude from lap analysis |
| `is_cooldown` | Last lap before pit, speeds never exceed ~70% of normal | Exclude from lap analysis |

## Smoothness Metrics

| Feature | Formula | Unit | Use |
|---------|---------|------|-----|
| `steering_rate` | `d(Steering_Angle) / dt` | deg/s | High rate = abrupt inputs = rough driver |
| `throttle_rate` | `d(Throttle_Position) / dt` | %/s | Smooth throttle application from apex |
| `brake_rate` | `d(Brake_Pressure) / dt` | bar/s | Smooth initial brake application (squeeze, don't stab) |
| `g_dot_lat` | `d(gLat) / dt` | G/s | Load rate — lower = smoother = more traction (Ross Bentley principle) |
| `g_dot_long` | `d(gLong) / dt` | G/s | Same for longitudinal. Target < 0.5 G/s. |
