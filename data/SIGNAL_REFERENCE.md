# Signal Reference

Every signal in the VBO files: what it measures, what units, what range, and how to use it for coaching.

---

## GPS Signals (Racelogic VBOX)

| VBO Column | Name | Unit | Range | Description | Coaching Use | Confidence |
|-----------|------|------|-------|-------------|-------------|-----------|
| `sats` | Satellite Count | count | 0–140 | GPS satellites tracked. >60 = good fix. Values >20 encode quality flags. | Confidence indicator for GPS signals. | — |
| `time` | GPS Time of Day | seconds | 163920–185937 | Seconds since midnight UTC. Wraps at 86400. | Primary timestamp. 10Hz exact. | — |
| `lat` | Latitude | DDMM.MMMMM | 2289–2372 | Racelogic format. Convert: `DD + MM.MMMMM / 60`. | Track position, geofencing, lap detection. | 0.95 |
| `long` | Longitude | DDMM.MMMMM | 7339–7347 | Same format. West = negative in decimal degrees. | See latitude. | 0.95 |
| `velocity` | Ground Speed | km/h | 0–198 | GPS-derived. Not affected by wheel spin. | Primary speed for brake points, corner speed, lap estimation. | 0.95 |
| `heading` | Track Heading | degrees | 0–360 | Direction of travel. 0=N, 90=E, 180=S, 270=W. | Corner detection (curvature = d(heading)/d(distance)). | 0.95 |
| `height` | Altitude | meters | 8–93 | GPS altitude above sea level. Sonoma has 55m delta. | Gradient analysis, crest/dip detection. | 0.80 |
| `vert-vel` | Vertical Velocity | m/s | -3.1 to +5.2 | Rate of altitude change. +climbing, -descending. | Crest (pos→neg) and compression (neg→pos) detection. | 0.70 |

## IMU Signals (Racelogic internal accelerometer)

| VBO Column | Name | Unit | Range | Description | Coaching Use | Confidence |
|-----------|------|------|-------|-------------|-------------|-----------|
| `Indicated_Lateral_Acceleration` | Lateral G | G | -1.81 to +1.63 | Perpendicular to travel. +right turn, -left turn. | **Core coaching signal.** Cornering intensity, friction circle, over/understeer. | 0.95 |
| `Indicated_Longitudinal_Acceleration` | Longitudinal G | G | -1.66 to +0.21 | Along travel direction. -braking, +accelerating. | Trail brake detection, braking intensity, throttle smoothness. | 0.95 |
| `ComboAcc` | Combined G | G | 0–2.29 | `sqrt(gLat² + gLong²)`. Total grip utilization. | **Most important metric.** Friction circle %. Low = coasting. High = committed. Over max = sliding. | 0.95 |

## CAN Bus Signals — Driver Inputs (OBDLink MX)

| VBO Column | Name | Unit | Range | Description | Coaching Use | Confidence |
|-----------|------|------|-------|-------------|-------------|-----------|
| `Brake_Pressure` | Brake Line Pressure | bar | 0–104 | Hydraulic brake pressure. Real analog, not binary. | **Most valuable CAN signal.** Trail braking analysis. Descending pressure trace = the trail brake. | 0.95 |
| `Brake_Position` | Brake Pedal Position | 0–1 | 0–1.0 | Pedal travel normalized. Complementary to pressure. | Pedal technique (position ≠ force). | 0.95 |
| `Throttle_Position` | Throttle Pedal | % | 0–99 | Pedal position. 0=closed, 99=WOT. | Coasting detection, smoothness, exit speed coaching. | 0.95 |
| `Steering_Angle` | Steering Wheel Angle | degrees | -1024 to +372 | Angle from center. -left, +right. Clip to ±500°. | Line analysis, understeer detection (high steer + low gLat). | 0.90 |

## CAN Bus Signals — Engine (OBDLink MX)

| VBO Column | Name | Unit | Range | Description | Coaching Use | Confidence |
|-----------|------|------|-------|-------------|-------------|-----------|
| `Engine_Speed` | RPM | rev/min | 843–8,582 | Crankshaft speed. Idle ~850, redline ~8,500. | Shift point analysis, gear derivation (RPM/speed ratio). | 0.95 |

## CAN Bus Signals — Health Monitoring (OBDLink MX)

| VBO Column | Name | Unit | Range | Description | Coaching Use | Confidence |
|-----------|------|------|-------|-------------|-------------|-----------|
| `Coolant_Temperature` | Coolant Temp | °C | 68–99 | Engine water temp. Normal 85-95°C. | Overheat warning >95°C. Don't push hard until >80°C. | 0.90 |
| `Oil_Temperature` | Oil Temp | °C | 84–121 | Engine oil temp. Normal 100-120°C. | Don't rev >6K until >90°C. Breakdown risk >130°C. | 0.90 |
| `Oil_Pressure` | Oil Pressure | bar | 0.6–5.85 | Varies with RPM. Higher RPM = higher pressure. | Anomaly: pressure drops at high RPM = pump issue. | 0.85 |
| `Fuel_Level` | Fuel Level | % | 20–46 | Tank percentage. Integer quantized. | Consumption per lap, range prediction, leak detection. | 0.80 |
| `Battery_Voltage` | Battery Voltage | V | 13.1–13.6 | Electrical system. 13-14.4V = normal. | Alternator health. Dropping at high RPM = belt slip. | 0.90 |
| `Water_Press_(Calc)` | Coolant Pressure | PSI | 7.3–34.8 | Computed by VBOX from CAN. | Cooling system health. Sudden drop = leak. | 0.80 |

## Not Usable (Constant or Broken)

| VBO Column | Value | Issue |
|-----------|-------|-------|
| `Air_Fuel_Ratio` | 500 (constant) | Sensor not connected |
| `Clutch_Position` | 255 (constant) | Not mapped or auto transmission |
| `Exhaust_Temperature` | -50 (constant) | EGT sensor not connected |
| `Gear` | 255 (constant) | CAN signal not mapped — derive from RPM/speed |
| `Head_Temperature` | 0.5–2.4 | Mislabeled. Not a real temperature. |
| `Indicated_Vehicle_Speed` | 500 (constant) | OBD speed not configured. Use GPS `velocity`. |
| `Brake_Press_(Calc)` | -3 to 1066 | Inconsistent units. Use `Brake_Pressure` in bar. |

## Redundant (Computed Conversions)

These duplicate other signals in different units. Ignore them.

| VBO Column | Duplicates | Conversion |
|-----------|-----------|-----------|
| `Water_Temp_(Calc)` (°F) | `Coolant_Temperature` (°C) | `F = C * 9/5 + 32` |
| `Oil_Temp_(Calc)` (°F) | `Oil_Temperature` (°C) | `F = C * 9/5 + 32` |
| `Oil_Press_(Calc)` (PSI) | `Oil_Pressure` (bar) | `PSI = bar * 14.504` |

## Metadata Columns

| VBO Column | Name | Unit | Description |
|-----------|------|------|-------------|
| `Tsample` | Sample Period | seconds | Always 0.100 (10Hz). |
| `avifileindex` | Video File Index | integer | Associated video file number. |
| `avitime` | Video Timestamp | milliseconds | Time into the associated .mp4 for video sync. |
