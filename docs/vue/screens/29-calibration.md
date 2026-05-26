# 29 — Calibration

10-second still-car telemetry read. Verifies sensors agree before
the driver pulls out. Reached either from onboarding step 7 or from
Settings → "RECALIBRATE."

## Purpose

Verb: **Verify.** Confirm GPS, IMU, and pedal sensors are zeroed and
agreeing while the car is stationary, before any session.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ CALIBRATION                              7 / 10  s          │
│                                                            │
│              ╔═══════════════════════╗                     │
│              ║       ▒▒▒▒▒▒▒▒        ║                     │
│              ║      ▓▓ CAR ▓▓        ║                     │
│              ║      stationary       ║                     │
│              ║                       ║                     │
│              ╚═══════════════════════╝                     │
│                                                            │
│  GPS LOCK                                                  │
│  ████████████████████████████████░░░░░░░░  ✓               │
│                                                            │
│  IMU NOISE FLOOR                                           │
│  ████████████████████████████████████████  ✓               │
│                                                            │
│  RPM ZERO BASELINE                                         │
│  ████████████████████████████████████████  ✓               │
│                                                            │
│  BRAKE / THROTTLE ZERO                                     │
│  ████████████████████████░░░░░░░░░░░░░░░░  …               │
│                                                            │
│                                                            │
│  ┌──────┐                                                  │
│  │T-ROD │  "Hold tight. Checking the basics."              │
│  │analyz│                                                  │
│  └──────┘                                                  │
│                                                            │
│  B · CANCEL                                                │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `intro` | Mount | Coach speaks `analyzing` line: "Hold tight. Checking the basics." |
| `recording` | After intro | 10 s timer; bars fill as samples accumulate |
| `evaluating` | 10 s done | Each bar locks ✓ or ✗ |
| `success` | All ✓ | Coach `encouraging` + level_up SFX + "CALIBRATED" stamp |
| `failure` | Any ✗ | Coach `concerned` + per-bar error explanation + retry button |

## Calibration thresholds

| Sensor | Pass criterion |
|---|---|
| GPS | Position stable < 1 m drift over 10 s; ≥ 8 sats |
| IMU | All 6 axes std-dev < 0.05 m/s² (lat/long/up) and < 0.5°/s (roll/pitch/yaw) |
| RPM | Reading 700-900 (idle range) for at least 8 of 10 s |
| Brake/throttle | Both within 1 % of zero for full 10 s |

If any sensor's signal isn't in the session capabilities (e.g., car
doesn't expose RPM via OBD), that bar is skipped — we can't
calibrate what isn't there.

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Car silhouette | Top-center, 96×64 | Static (intentionally — it's not moving) |
| Progress bars | Center | Width interpolates as samples gather |
| Coach (`save.preferredCoach`) | Bottom-left, 64×64 | Emotion progression: `analyzing` (recording) → `encouraging` (success) OR `concerned` (failure) per `../10-coach-emotions.md` |
| `check_v` / `x_v` | After each bar | Static |

## Vue component

```vue
<!-- pitwall-web/src/views/Calibration.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">CALIBRATION</h1>
    <p class="font-ui text-body">{{ remainingS }} / 10 s</p>

    <Sprite name="car_stationary" />

    <ProgressBar :label="'GPS LOCK'" :pct="bars.gps" :status="status.gps" />
    <ProgressBar :label="'IMU NOISE FLOOR'" :pct="bars.imu" :status="status.imu" />
    <ProgressBar :label="'RPM ZERO BASELINE'" :pct="bars.rpm" :status="status.rpm" />
    <ProgressBar :label="'BRAKE / THROTTLE ZERO'" :pct="bars.pedals" :status="status.pedals" />

    <CoachSpeaksModal embedded
                      :coach-id="save.preferredCoach"
                      :emotion="phaseEmotion"
                      :text="phaseText" />

    <HintBar :hints="hints" />
  </div>
</template>

<script setup lang="ts">
import { useCalibration } from '@/lib/calibration'
const { bars, status, remainingS, phaseEmotion, phaseText, retry, cancel } = useCalibration()
</script>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `POST /session/_cal/frames` | 10 s × 10 Hz = 100 frames of stationary telemetry |
| `GET /session/_cal/capabilities` | Determines which bars to render |
| `POST /session/_cal/end` (proposed) | Tears down the temp session |

The `_cal` session id is reserved; cleanup happens on screen exit so
multiple calibrations don't pile up.

## Audio cues

| Event | Sound |
|---|---|
| Mount | Coach voice clip plays (TTS pre-rendered) |
| Bar fills 100% | `goal_complete` quietly |
| All bars ✓ | `level_up` |
| Any bar ✗ | `error_quiet` |

## Input map

| Input | Action |
|---|---|
| Any | No-op while recording — let the data accumulate |
| B | Cancel (returns to caller — settings or onboarding) |
| A | (success state only) DONE → returns to caller |
| A | (failure state) RETRY |

## Edge cases

- **Bridge offline mid-calibration** — abort with banner, no save
- **Driver moves the car during recording** — IMU exceeds noise
  threshold; fail explicitly with reason
- **Repeated failures (3 retries)** — coach suggests "go to PIT STALL
  and check the connection chain"
- **Car off (no RPM)** — skip RPM bar; succeed if GPS+IMU+pedals OK
- **First-ever calibration vs recalibration** — same flow; the result
  is timestamped on the save slot for diagnostic purposes

## Related

- [`02-onboarding.md`](02-onboarding.md) — first calibration is step 7
- [`13-settings.md`](13-settings.md) — RECALIBRATE button lives here
- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — connection-chain
  diagnostic, often the next step after a failed cal
- [`../10-coach-emotions.md`](../10-coach-emotions.md) — phase emotions
