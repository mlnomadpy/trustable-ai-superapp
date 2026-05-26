# 15 — Pit Stall Setup

The "is the car talking to us?" screen. Pre-flight check before any
session. Surfaces every connection in the chain — bridge process,
USB-CAN adapter, DBC, live signal stream, and the **current state of
the car right now**: RPM, speed, gear, oil temp, coolant, steering,
brake, throttle, all flowing live.

## Purpose

Verb: **Connect.** Verify the entire stack from car ECU to the PWA in
one screen, *before* the driver leaves the paddock.

This is the screen the driver loads up the moment they sit down in the
car, before pulling out. It must be useful **even if everything is
broken** — it tells the driver exactly which link in the chain is the
problem.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ PIT STALL                                                  │
│                                                            │
│ ╔═ CONNECTION CHAIN ═════════════════════════════════════╗ │
│ ║                                                       ║ │
│ ║  ▒▒▒  BRIDGE       127.0.0.1:8765            ✓ ONLINE  ║ │
│ ║       ENGINE       sonic_model + LiteRT-LM            ║ │
│ ║       DUCKDB       enabled · 47 sessions              ║ │
│ ║                                                       ║ │
│ ║  ▒▒▒  USB-CAN      /dev/ttyACM0  CANable Pro          ║ │
│ ║       INTERFACE    slcan @ 500 kbps         ✓ STREAM   ║ │
│ ║       FRAMES/s     422                                ║ │
│ ║                                                       ║ │
│ ║  ▒▒▒  DBC          pitwall.dbc + bmw_e46_m3.dbc       ║ │
│ ║       SIGNALS      29 + 64 = 93 known                 ║ │
│ ║       UNKNOWN IDS  3 (logged, not decoded)            ║ │
│ ║                                                       ║ │
│ ║  ▒▒▒  CAR          BMW M3 (E46)                       ║ │
│ ║       IGNITION     ON                       ✓ READY    ║ │
│ ║                                                       ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ╔═ LIVE CAR STATE ═══════════════════════════════════════╗ │
│ ║   RPM         3 247 │ GEAR     2 │ SPEED    47 km/h    ║ │
│ ║   OIL TEMP     94°C │ COOLANT 88°C │ FUEL    62 %      ║ │
│ ║   THROTTLE    18 %  │ BRAKE    0 bar │ STEER  -3°      ║ │
│ ║   G-LAT       0.0 g │ G-LONG  0.0 g │ COMBO   0.0 g    ║ │
│ ║                                                       ║ │
│ ║   AVAILABLE COACHES                                    ║ │
│ ║   ✓ base_pace_note    ✓ trail_brake_score              ║ │
│ ║   ✓ oil_temp_warning  ✗ clutch_balance (no signal)     ║ │
│ ║   ✓ tpms_drift                                         ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│  A · BACK     B · BACK     ◆ HARDWARE INFO                 │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `polling-bridge` | Mount | `GET /health` every 1 s; ▒▒▒ animates as ▒▒░ ▒░░ ░░░ ░▒▒ ░▒▒ ▒▒▒ during request |
| `bridge-ok` | 200 from /health | ✓ ONLINE marker; advances to USB-CAN check |
| `usb-can-checking` | Bridge OK | `GET /signals/registry?include_can_state=true` — confirms slcan/socketcan interface alive |
| `usb-can-streaming` | Frames received | Frames/s counter starts ticking; subscribe to live SSE for state |
| `dbc-loaded` | Capabilities returned | List loaded DBCs and known signal counts |
| `car-on` | Recent CAN activity | "READY" indicator; live state populates |
| `car-off` | No CAN frames in 3 s | "IGNITION OFF" hint; live state freezes |

The ▒▒▒ before each line is a 6-frame "loading dots" animation that
plays while that step verifies. On failure: turns into ✗.

## Each row in detail

### Bridge row

- Reads `GET /health` every 1 s
- Shows: bind address, engine status (sonic_model / rules), coach
  status (rule / litert), DuckDB enabled flag, total sessions in DB
- Failure: ✗ with "PROCESS NOT REACHABLE — start the bridge with
  `python3 -m src.pitwall`"

### USB-CAN row

- Reads `GET /signals/registry` with a "?include_can_state=true" query
  param (new — see "Bridge additions" below)
- Shows: device path, adapter model (auto-detected via lsusb if
  available), interface (slcan/socketcan/virtual), bitrate, frames/s
- Failure modes:
  - **No device** → ✗ "USB CABLE NOT PLUGGED IN" + sprite of the OBD-II
    plug
  - **Device present but no frames** → ✗ "NO CAN FRAMES — check car ignition"
  - **Frames flowing but bridge not reading** → ✗ "BRIDGE NOT STARTED
    WITH --can-channel FLAG"

### DBC row

- Reads from `GET /signals/registry`
- Shows: loaded DBC files, total signal count, count of unknown CAN
  IDs (frames whose `arbitration_id` isn't in any loaded DBC)
- Tappable: A on this row opens a sub-screen listing every known signal
  + its current value (deferred to v2)

### Car row

- Computed: ignition is ON if any CAN frame received in last 3 s with
  RPM > 0
- Shows: car make/model from save slot's `car` field
- Failure: "IGNITION OFF — turn key to ACC or RUN"

### Live Car State panel

A live readout. Updates at 5 Hz (cap so the UI doesn't jank). Each
field maps to a real signal:

| Field | Source signal | Format |
|---|---|---|
| RPM | `rpm` (wide) | DSEG7, 4 digits |
| GEAR | `gear` (sink) | `-1`=R, `0`=N, `1..7` |
| SPEED | `speed_ms` × 3.6 | DSEG7, "47 km/h" |
| OIL TEMP | `oil_temp_c` | DSEG7, "94°C" — green < 110, amber 110-120, red > 120 |
| COOLANT | `coolant_temp_c` | DSEG7, "88°C" — green < 95, amber 95-105, red > 105 |
| FUEL | `fuel_level_pct` | "62 %" — amber < 25, red < 10 |
| THROTTLE | `throttle_pct` | "18 %" |
| BRAKE | `brake_bar` | "0 bar" |
| STEER | `steering_deg` | "-3°" |
| G-LAT/G-LONG/COMBO | `g_lat` / `g_long` / `combo_g` | "0.0 g" |

If a field's signal is missing from the session capabilities, it shows
`---` instead of a value.

### Available Coaches panel

Reads `GET /session/<sid>/capabilities` (using a placeholder session
created on entry to this screen). Shows each coach rule's status:

- ✓ — required signals present and rate sufficient
- ✗ — listed reason ("no signal", "rate 1 Hz below 5 Hz min")

This is the player-facing surface of ADR-015 Phase 4 capability
gating.

## Sprite usage

| Sprite | Where |
|---|---|
| `ui/loading_dots` 6-frame | Per-row checking animation |
| `ui/check_v` and `ui/x_v` | Status icons |
| `ui/usb_can_animation` | Full-screen sprite when USB unplugged (the "INSERT CABLE" hint) |
| Coach `holding_gauge` (T-Rod row 5) | Idle in the corner of the screen |
| Cursor | Hidden — this screen is read-only |

## Vue component

```vue
<!-- pitwall-web/src/views/PitStallSetup.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">PIT STALL</h1>

    <Frame frame-type="default" class="conn-chain">
      <ConnRow :state="bridgeState"   :title="'BRIDGE'"
               :details="bridgeDetails"  />
      <ConnRow :state="usbCanState"   :title="'USB-CAN'"
               :details="usbCanDetails"  />
      <ConnRow :state="dbcState"      :title="'DBC'"
               :details="dbcDetails"     />
      <ConnRow :state="carState"      :title="'CAR'"
               :details="carDetails"     />
    </Frame>

    <Frame frame-type="card" class="live-state">
      <LiveCarState :state="liveState" />
      <CoachesAvailable :caps="capabilities" />
    </Frame>

    <HintBar :hints="['A · BACK', 'B · BACK', '◆ HARDWARE INFO']" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useBridgeStore } from '@/stores/bridge'

const bridge = useBridgeStore()
const liveState = ref(emptyLiveState())

let healthTimer: number | null = null
let liveTimer:   number | null = null

onMounted(() => {
  // Poll bridge health every 1 s
  healthTimer = window.setInterval(() => bridge.pollHealth(), 1000)
  // Poll live car state every 200 ms (5 Hz cap)
  liveTimer = window.setInterval(pollLive, 200)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
  if (liveTimer) clearInterval(liveTimer)
})

async function pollLive() {
  // Use the synchroniser at native rate, last 1 s only
  const tNow = Date.now() / 1000
  const r = await fetch(
    `/api/session/_live/signals?names=${liveStateSignals.join(',')}` +
    `&t_from=${tNow - 1}&rate_hz=5&interp=hold`
  )
  const data = await r.json()
  liveState.value = mergeLatest(liveState.value, data.rows)
}
</script>
```

## Bridge additions needed

This screen needs two small bridge changes:

1. **`?include_can_state=true` on `/signals/registry`** — adds an
   `interface`, `channel`, `frames_per_second`, `unknown_ids` block to
   the response so the PWA doesn't have to reverse-engineer them.
2. **Synthetic `_live` session** — the bridge should always tag CAN
   frames into a `_live` session_id when no other session is active,
   so the PWA can read live data via the synchroniser without first
   creating a session.

Both are < 30 lines; documented in
[`docs/api.md`](../../api.md) under "Pit Stall Setup support."

## Endpoints consumed

| Endpoint | Polled at | Use |
|---|---|---|
| `GET /health` | 1 s | Bridge online + engine status |
| `GET /signals/registry?include_can_state=true` | on entry + 5 s | USB-CAN + DBC + frames/s |
| `GET /session/_live/signals?names=…&rate_hz=5&interp=hold` | 200 ms | Live car state |
| `GET /session/_live/capabilities` | on entry | Available coaches |

## Audio cues

| Event | Sound |
|---|---|
| Mount | quiet `garage_loop` (no music swap) |
| Bridge ✓ | `goal_complete` |
| USB-CAN ✓ | `goal_complete` |
| Car READY | `level_up` (you can drive now!) |
| Any failure ✗ | `error_quiet` (one-shot, doesn't repeat per row) |

## Input map

| Input | Action |
|---|---|
| A | Back to garage hub (no-op since this is read-only) |
| B | Back to garage hub |
| Start (◆) | Quick menu (with extra "HARDWARE INFO" entry) |

## Edge cases

- **All systems green for the first time** — small celebration: a
  3-second confetti burst over the screen + `level_up` chime + coach
  thumbs-up sprite + "READY TO DRIVE" banner pulses. Only fires once
  per session start.
- **Bridge online but USB-CAN offline** — coach speaks
  `coach_thinking` line: *"Looks like we don't have CAN data yet —
  check the cable."* Pre-rendered MP3, plays once.
- **Car off (ignition not on)** — RPM = 0, no frames; show stationary
  car silhouette sprite to remind driver to turn the key.
- **Player exits and re-enters** — chain re-validates from scratch
  (don't trust stale state).

## Related

- [ADR-015](../../adr/015-universal-telemetry-sink.md) — capability gating
- [ADR-016](../../adr/016-can-bus-ingest-and-frontend-pivot.md) — USB-CAN flow
- [`16-analysis-hub.md`](16-analysis-hub.md) — destination after pit-stall
- [`07-pre-brief.md`](07-pre-brief.md) — what the driver does after this
