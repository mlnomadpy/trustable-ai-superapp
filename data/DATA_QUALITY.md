# Data Quality Notes

Known issues, edge cases, and recommendations for working with this dataset.

---

## Signal Issues

### 1. Satellite Count Encoding

The `sats` field shows values like 12, 80, 100, 140 — not all are literal satellite counts. Values >20 likely encode quality flags beyond count. Use `sats > 60` as "good GPS" threshold.

### 2. Steering Angle Wraps

`Steering_Angle` shows -1024° in some files (notably VBOX0173). This is a CAN sensor overflow during parking or very tight maneuvers. **Clip to ±500°** for analysis. Values within ±400° are valid racing steering inputs.

### 3. Gear Always 255

The CAN signal for gear is not mapped in the OBDLink configuration for this car. Derive gear from RPM and speed:

```python
# BMW M3 S54 approximate gear ratios (final drive × gear ratio)
GEAR_RATIOS = {1: 13.17, 2: 8.09, 3: 5.77, 4: 4.52, 5: 3.68, 6: 3.09}

def estimate_gear(rpm, speed_kmh):
    if speed_kmh < 5: return 0  # stationary
    ratio = rpm / (speed_kmh / 3.6 * 60 / (2 * 3.14159 * 0.315))  # 0.315m = tire radius
    # Find closest matching gear ratio
    return min(GEAR_RATIOS.items(), key=lambda x: abs(x[1] - ratio))[0]
```

### 4. Broken Signals (Constant Across All 183 Files)

These signals are not connected or not mapped. **Exclude from all analysis.**

| Signal | Constant Value | Reason |
|--------|---------------|--------|
| `Air_Fuel_Ratio` | 500 | AFR sensor not connected |
| `Clutch_Position` | 255 | Not mapped or auto/DCT transmission |
| `Exhaust_Temperature` | -50 | EGT sensor not connected |
| `Indicated_Vehicle_Speed` | 500 | OBD speed PID not configured |
| `Gear` | 255 | CAN ID not mapped |
| `Head_Temperature` | 0.5–2.4 | Mislabeled — range doesn't match any temperature |

### 5. Missing Signals (Not in CAN Configuration)

These would be valuable but are not available in any file:

| Signal | Why Missing | Impact |
|--------|------------|--------|
| Tire temperature (per corner) | No IR sensors installed | No tire management coaching |
| Individual wheel speeds | ABS CAN IDs not mapped | No tire slip ratio calculation |

---

## Timestamp Issues

### 6. Midnight Wraps

VBOX0196 and potentially others show negative session duration when GPS time-of-day crosses midnight (86400s) during recording.

**Fix:**
```python
if dt < -1000:
    dt += 86400  # add 24 hours
```

### 7. Stale Timestamps in Transit Sessions

127 transit sessions have long gaps (car parked with engine running) where timestamps increment but no driving occurs. **Filter by `velocity > 5 km/h`** to isolate driving-only frames.

---

## Session Quality

### 8. Transit Sessions (70% of Files)

127 of 183 files are transit — pit lane drives, warm-up laps, cool-down laps, transits between sessions. Max gLat < 0.5G.

**Action:** Exclude from coaching model training. Useful as negative examples for:
- Out-lap / in-lap detection
- Pit lane speed limit detection
- "Is the driver racing?" classifier

### 9. Extended Sessions Contain Pit Stops

Files like VBOX0266 (128 min, 22K frames) and VBOX0212 (100 min, 12K frames) contain multiple stints separated by pit stops (speed = 0 for >30 seconds).

**Action:** Segment into individual stints before lap analysis:
```python
def segment_stints(frames, pit_threshold_s=30):
    stints = []
    current_stint = []
    zero_count = 0
    for f in frames:
        if f.speed < 1.0:  # m/s
            zero_count += 1
        else:
            if zero_count > pit_threshold_s * 10:  # 10Hz
                if current_stint:
                    stints.append(current_stint)
                current_stint = []
            zero_count = 0
            current_stint.append(f)
    if current_stint:
        stints.append(current_stint)
    return stints
```

### 10. Brake Pressure Range Varies by Session

Max brake ranges from 60 bar (VBOX0202, lighter braking) to 104 bar (VBOX0318, heaviest). This reflects different driving styles and possibly different brake pads, not sensor differences.

**Action:** Normalize per-session: `brake_pct = pressure / max_session_pressure * 100`.

### 11. Two Low-Intensity Sessions

- **VBOX0162:** max gLat 0.17G, max speed 128 km/h — transit/warmup only
- **VBOX0165:** max gLat 0.38G, max speed 133 km/h — street drive or parade laps

**Action:** Exclude from hot lap analysis entirely.

---

## ML Training Recommendations

### 12. Use Hot Lap Sessions Only

52 sessions, 470K frames, 13.1 hours across 3 primary tracks. This is the training data.

### 13. VBOX0318 is the Gold Standard Candidate

198 km/h top speed, 104 bar max brake, 1.84G max lateral. Fastest and most aggressive session. Extract the best single lap from this file as the Gold Standard reference for coaching comparison.

### 14. Split by Track for Cross-Validation

| Strategy | Train On | Validate On | Tests |
|----------|---------|-------------|-------|
| **Same-track** | 80% of Track 1 laps | 20% of Track 1 laps | Does the model work on Sonoma? |
| **Cross-track** | Track 1 + Track 2 | Track 8 | Does the model generalize? |
| **Leave-one-out** | All tracks except Track 2 | Track 2 | Hardest test — new track, highest speeds |

### 15. Transit Sessions are Negative Examples

A driving phase classifier must label transit frames as "not racing." Any coaching rule that fires during transit is a false positive.

### 16. Normalize Per-Session, Not Globally

Brake pressure, G-forces, and speed ranges vary across sessions (different conditions, tire life, fuel load). Normalize features within each session for models that compare across sessions. For within-session models (lap comparison, corner scoring), use raw values.
