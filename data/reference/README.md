# Reference Session Data

Reference CSV files for rule regression testing (ADR-027). These sessions have known, verified coaching rule trigger counts and are used to gate OTA rule deployments.

## Required Files

| File | Description | Status |
|------|-------------|--------|
| `thunderhill_sim_full.csv` | Forza Thunderhill lap, all 93 signals, schema v2 | Needed — record from Forza with full telemetry |
| `thunderhill_coaching_tier.csv` | Real car Thunderhill lap, GPS + IMU + OBD, schema v2 | Needed — record at Coaching tier |
| `thunderhill_timing_tier.csv` | GPS-only Thunderhill lap, schema v2 | Needed — record with GPS only |
| `sensor_dropout_mid_session.csv` | Session where IMU disconnects mid-lap, schema v2 | Needed — simulate by unplugging IMU |
| `rain_session_low_grip.csv` | Wet session with reduced grip levels, schema v2 | Needed — record in rain or from Forza wet settings |

## How to Record

```bash
# Start server with recording enabled
python ingest.py --adapter forza --record --output data/reference/thunderhill_sim_full.csv

# Or for real car
python ingest.py --adapter gps+obd+imu --record --output data/reference/thunderhill_coaching_tier.csv
```

## Schema

All reference files use schema version 2 (confidence-annotated). Columns follow the naming convention:

```
schema_version, timestamp, speed, speed_confidence, speed_source, gLat, gLat_confidence, gLat_source, ...
```

## Updating

When the frame schema changes (new version), re-record all reference files at the new schema version and update the expected trigger counts in rule definitions.
