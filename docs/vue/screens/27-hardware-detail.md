# 27 — Hardware Detail

The deeper view reached from `15-pit-stall-setup.md`'s ◆ HARDWARE INFO
button. Shows every CAN signal in the registry with its live value,
mean rate, and DBC origin.

## Purpose

Verb: **Inspect.** Power-user surface for "is signal X actually being
received from the car?"

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ HARDWARE DETAIL                            page 1 of 5      │
│                                                            │
│ ╔═ SIGNALS ══════════════════════════════════════════════╗ │
│ ║  NAME              UNIT  Hz    LAST   GROUP   DBC      ║ │
│ ║ ─────────────────────────────────────────────────────  ║ │
│ ║  ▶ rpm              rpm  10.0  3247  motion  pitwall  ║ │
│ ║    speed_ms         m/s  10.0  13.0  motion  pitwall  ║ │
│ ║    g_lat            g    10.0  0.04  motion  pitwall  ║ │
│ ║    brake_bar        bar  10.0  0.0   driver  pitwall  ║ │
│ ║    throttle_pct     %    10.0  18.0  driver  pitwall  ║ │
│ ║    oil_temp_c       C     2.0  94.0  power   bmw_e46   ║ │
│ ║    coolant_temp_c   C     2.0  88.0  power   bmw_e46   ║ │
│ ║    clutch_pos_pct   %    50.0  0.0   drive   bmw_e46   ║ │
│ ║    tpms_fl_kpa      kPa   1.0  230.5 tires   bmw_e46   ║ │
│ ║    tpms_fr_kpa      kPa   1.0  231.8 tires   bmw_e46   ║ │
│ ║    afr_lambda      ratio  5.0  0.97  power   bmw_e46   ║ │
│ ║    …                                                   ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ╔═ UNKNOWN CAN IDs ══════════════════════════════════════╗ │
│ ║  0x4F1   3 frames/s   (no DBC entry)                  ║ │
│ ║  0x523   1 frame/s    (no DBC entry)                  ║ │
│ ║  0x6A0   8 frames/s   (no DBC entry)                  ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ A · DRILL IN     B · BACK     ◀ ▶ PAGE     ◆ ADD DBC       │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch registry + caps + start live SSE |
| `idle` | Loaded | Cursor on first row; live values tick at 5 Hz |
| `drilling` | A on a signal | Sub-modal with full signal metadata |
| `add-dbc` | ◆ pressed | File picker → uploads to bridge config |

## Drill-in modal (A on a signal)

```
┌────────────────────────────────────────────────────────────┐
│  ╔══════════════════════════════════════════════════════╗  │
│  ║ SIGNAL · oil_temp_c                                  ║  │
│  ║ ─────────────────────────────────────────────────    ║  │
│  ║ UNITS         °C                                     ║  │
│  ║ SEMANTICS     temperature                            ║  │
│  ║ GROUP         powertrain                             ║  │
│  ║ EXPECTED      5.0 Hz                                 ║  │
│  ║ MIN USEFUL    1.0 Hz                                 ║  │
│  ║ DISCOVERY     static_obd2                            ║  │
│  ║ OBD2 PID      0x5C                                   ║  │
│  ║ DBC SOURCE    bmw_e46_m3.dbc                         ║  │
│  ║                                                      ║  │
│  ║ LAST 50 SAMPLES (live histogram, 5 Hz)               ║  │
│  ║ ▁▂▃▄▅▅▆▆▆▇▇▇▇▇▇▆▆▆▆▆▆▆▆▆▆▆▆▆                          ║  │
│  ║ MIN 89.0   AVG 93.5   MAX 96.0  (last 10 s)          ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│  B · CLOSE                                                 │
└────────────────────────────────────────────────────────────┘
```

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Hidden by default; appears when Player taps a row with low confidence | Emotion = `analyzing` per `../10-coach-emotions.md` |
| `frame-default` | Each panel | Static |
| `cursor_arrow` | On focused row | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/HardwareDetail.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">HARDWARE DETAIL</h1>
    <PaginatedTable :rows="signals" :page="page" :focus="cursor"
                    :live-values="liveValues" />
    <UnknownCanIds :ids="unknownIds" />
    <DrillInModal v-if="drilling" :signal="drilling"
                  @close="drilling = null" />
    <HintBar :hints="hints" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Polled at | Use |
|---|---|---|
| `GET /signals/registry?include_can_state=true` | every 2 s | Master signal list + unknown CAN IDs |
| `GET /session/_live/capabilities` | every 5 s | Hz per signal in *this* car right now |
| `GET /session/_live/signals?names=*&rate_hz=5&interp=hold` | continuous | Live values |
| `POST /signals/dbc-upload` (proposed) | on ◆ ADD DBC | Adds a per-car DBC at runtime |

## Audio cues

| Event | Sound |
|---|---|
| Cursor move | `cursor_move` |
| Drill-in | `cursor_select` |
| Close drill-in | `cancel` |
| Page change | `cursor_move` |
| Add DBC succeeds | `goal_complete` |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move cursor between rows |
| ◀ ▶ | Page through (20 rows per page) |
| A | Drill into focused signal |
| B | Back to Pit Stall Setup |
| Start | Pause menu |
| ◆ | Open file picker for DBC upload |

## Edge cases

- **No live session** — show "WAITING FOR CAR FRAMES…" state with
  the loading-dots sprite; signals listed are registry-only with
  Hz=0
- **Signal in DBC but no frames received** — show "—" in the LAST
  column; flag with amber colour
- **Unknown CAN IDs > 20** — paginate the unknown-IDs panel too
- **DBC upload while live session active** — newly-decoded signals
  appear in the table without restart

## Related

- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — parent screen
- [`../adr/015-universal-telemetry-sink.md`](../../adr/015-universal-telemetry-sink.md) — registry semantics
- [`../adr/016-can-bus-ingest-and-frontend-pivot.md`](../../adr/016-can-bus-ingest-and-frontend-pivot.md) — DBC layering
