# On-Track HUD

**Status:** Shipped
**Owner:** PWA (`src/pwa/`)
**Route:** `/hud` (`meta: { performance: true, allowPause: true }`)

The cockpit screen for Pixel 10 landscape. Minimalist by design — every
element has to survive a peripheral-vision glance at 130 mph. The
redesign collapsed the prior multi-panel layout into a single
foreground numeral (speed) with status chips around the edges.

Honest empty state: until a frame arrives from the SSE telemetry
stream, the speed / grip / friction / distance tiles render as nothing,
not as fake zeros or `—` filler. Minimap and overlays own their own
empty states.

---

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│  REPLAY · <sid>                  LIVE · ESC P T ⇧D            │  ← top strip
│                                                              │
│  Lap 03/08                                          Best     │
│  ████████░░░░ 62%                                  1:46.8    │  ← corner tiles
│                                                              │
│                                                              │
│                       1 4 2                                  │
│                      ─────                                   │  ← centre speed
│                       MPH                                    │
│                                                              │
│                    ┃ GRIP   ┃ SLIP                           │  ← compact grip
│                                                              │
│  ┌──────┐   Friction 67%   Dist 12.40 km        [TRACE]      │
│  │ map  │                                       [MIC FAB]    │  ← bottom strip
│  └──────┘                                                    │
└──────────────────────────────────────────────────────────────┘
```

- **Top strip** — `REPLAY` pill (amber) on the left when
  `/session/replay/status` reports `running: true`; stream chip
  (`LIVE` / `LOST`) and key-hint legend on the right.
- **Lap corner tile (top-left)** — live derived lap number + total +
  per-lap progress bar.
- **Best corner tile (top-right)** — best lap from the lap-time store
  rendered with 1-decimal precision for at-speed readability
  (analytics pages use 3 decimals).
- **Centre speed numeral** — integer MPH, dominant element, white on
  near-black with a soft glow.
- **Compact grip row** — two `GripBar`s side by side just below the
  speed (`GRIP` left, `SLIP` right). Replaces the giant vertical grip
  towers of the earlier HUD.
- **Bottom strip** — minimap (`HudTrackMap`, Sonoma), friction tile,
  distance tile, TRACE toggle button, voice FAB
  (`CoachVoiceButton`, fixed bottom-right).

All tiles use `src/pwa/src/widgets/hud/HudCornerTile.vue` for label /
numeral / unit composition.

---

## Data flow

```
SSE  /cues/stream    ───▶  cueStore         ───▶  CueBand (overlay)
SSE  /telemetry/stream───▶ telemetryStore  ───▶  frame.* (speed, distance, combo_g, …)
poll /session/replay/status (2s) ─▶ replayStatus ─▶ REPLAY pill, WAITING overlay
poll /health (bridgeStore) ─▶ can.connected ─▶ WAITING overlay copy
GET  /session/<sid>/laps   ─▶ track_length_m ─▶ useLapDerivation
GET  /session/<sid>/lap_time_table ─▶ lapTime.bestLapS ─▶ Best tile
```

### Reactive `sid`

The active session id is a **computed** with a priority chain:

```ts
const sid = computed(() =>
  session.activeSessionId
  ?? replayStatus.value.source_session_id
  ?? bridgeStore.health?.active_session_id
  ?? null,
)
```

Earlier versions captured `sid` statically on mount — that broke when
the user opened the HUD before a replay was running and then started
one from the WAITING overlay; the SSE never subscribed because `sid`
was still null. The replay-source fallback closes that loop within
the ~2s replay-status poll cadence instead of waiting for the slower
~5s `/health` poll.

A `watch(sid, …)` re-opens both `cueStore.open(sid)` and
`telemetryStore.open(sid)`, refetches lap times + track length, and
re-anchors lap derivation on every `sid` flip.

### Lap derivation (`useLapDerivation`)

The bridge does not emit `lap_number` on the realtime SSE — it only
computes laps server-side via `/session/<sid>/laps`. For the cockpit
we derive lap + per-lap progress client-side:

```
startDistance ← first observed frame.distance
since         = frame.distance - startDistance
lap_number    = floor(since / track_length_m) + 1
lap_progress  = ((since mod track_length_m) / track_length_m) * 100
```

Reset triggers (`resetLapDerivation()`):

- `sid` flips (different session = different cumulative distance origin)
- `telemetry.firstFrameAt` flips `null → number` (replay restart with
  the same `sid` — a fresh run begins)

Returns `null` until both a frame *and* a `track_length_m` are
available; the template renders "—" in that window so no fake lap 1 is
ever invented.

---

## Overlays

### WAITING-FOR-DATA

Renders when, after a 3 s grace window, no frame has arrived AND
nothing is feeding the bridge (`replayStatus.running === false` AND
`can.connected === false`). One primary action — `START REPLAY` opens
a modal containing `SessionStartPicker`. The CAN action is disabled
(it's hardware). Status chips at the bottom show live CAN + replay
state so the user knows what changed when the overlay clears.

Grace was bumped from 2 s to 3 s so the overlay doesn't flash on the
quick handoff between `POST /session/replay/start` succeeding and the
first SSE event arriving (~300–1500 ms on Pixel 10 over adb).

After 5 s of no frames despite `replayStatus.running === true` or
`can.connected === true`, the HUD logs a `console.error` with the
debug payload so operators can see the silent-SSE failure without
leaving the page.

### REPLAY ACTIVE pill

Amber chip in the top-left. Renders whenever `replayStatus.running`
flips true — including replays kicked off from another tab or from the
bridge CLI. Shows the source session id when the bridge reports one.

### PAUSE

Full-bleed overlay over the HUD. Two large `CyberButton`s — `CANCEL
SESSION` (danger) and `RESUME SESSION` (secondary). Triggered by `P`,
dismissed by `B`/`A`/`Enter`. Cancellation routes through
`CyberConfirmDialog` to avoid one-tap mistakes mid-session; on confirm
calls `session.endSession()` and routes back to `/garage`.

### Agent trace drawer

`src/pwa/src/pages/on-track-hud/AgentTraceDrawer.vue` slides in from
the right. Polls `/coach/traces` (and `/coach/agents` for the
registry) only while open — battery-aware on Pixel 10. Shows ADK
agent fires + latency + success/failure for this session. Toggled by
`T`.

### Debug overlay (`Shift+D`)

Small mono-font box in the top-right showing `sid`, frames received
since mount, latest frame timestamp, age of the last frame, distance,
track length, derived lap + progress %, replay state, CAN state. Age
turns red past 1500 ms. Read-only, sits above the HUD but below pause
/ waiting modals.

### Replay picker modal

`CyberModal` wrapping `SessionStartPicker`. Opens from the WAITING
overlay. Closes on success — the SSE subscribes through the reactive
`sid` once the bridge sets `state.active_session_id` to the source.

---

## Keyboard

```
ESC        router.back()                (owned by App.vue globally)
P          toggle PAUSE overlay         (meta.allowPause = true)
T          toggle agent trace drawer
M          trigger CoachVoiceButton     (skipped during PAUSE)
Shift+D    toggle debug overlay

While PAUSE is up:
  B / ⌫ / A / Enter   resume
  C                   open CANCEL confirm

While CANCEL confirm is up:
  Enter / Y           confirm cancel → /garage
  ESC / B / N / ⌫     dismiss
```

`M` triggers the same handler the voice FAB binds to its tap. Tapping
the phone at speed is hostile — a physical / Bluetooth keyboard or
steering-wheel macro is the intended input on track.

---

## Empty-state policy

- **No mock frames, ever.** The HUD never seeds fake speed / grip /
  friction values. `telemetryStore.startSimulation()` (the Math.sin/cos
  shim) was deleted in the no-fake-fallback sweep.
- **Tiles render only when `telemetry.firstFrameAt != null`** — until
  the SSE delivers a real frame, the speed numeral, grip row, friction
  and distance tiles are simply absent.
- **The minimap renders independently** — it owns its own empty state
  (centerline + no position marker) and is always visible so the user
  can see Sonoma is loaded even without a session.
- **Best lap shows `—`** until `/session/<sid>/lap_time_table`
  resolves. The tile tone is muted in that window and good once a lap
  exists.
- **Derived lap shows `—`** until both a frame AND a `track_length_m`
  are available. The progress bar is hidden in the same window.

---

## Lap derivation algorithm (detail)

```ts
// useLapDerivation(telemetry, trackLengthM)
//
//   on every read:
//     d  = telemetry.frame.distance        ; nullable, finite
//     tl = trackLengthM.value              ; null or > 0
//     if (d == null || !tl) return null    ; honest empty state
//     if (startDistance == null) startDistance = d
//     since = d - startDistance
//     if (!isFinite(since) || since < 0) return 1
//     lap_number   = max(1, floor(since / tl) + 1)
//     lap_progress = ((since mod tl) / tl) * 100   ∈ [0, 100]
//
//   reset() clears startDistance — called on:
//     - sid flip (watch sid)
//     - telemetry.firstFrameAt null → number (replay restart)
```

Anchoring on the first observed frame (not on 0) means the HUD works
identically whether the cockpit was opened during pit-out, mid-session,
or right after a `/session/replay/start`. The composable is also used
by the debug overlay for the live lap + progress readout.

---

## Related files

```
src/pwa/src/pages/on-track-hud/OnTrackHud.vue
src/pwa/src/pages/on-track-hud/AgentTraceDrawer.vue
src/pwa/src/widgets/hud/HudCornerTile.vue
src/pwa/src/widgets/hud/HudTrackMap.vue
src/pwa/src/widgets/hud/GripBar.vue
src/pwa/src/widgets/session-start/SessionStartPicker.vue
src/pwa/src/widgets/coach-voice-button/CoachVoiceButton.vue
src/pwa/src/entities/session/model/useLapDerivation.ts
src/pwa/src/entities/session/model/telemetryStore.ts
src/pwa/src/entities/lap-time/model/lapTimeStore.ts
src/pwa/src/features/coach-interaction/model/cueStore.ts
src/pwa/src/features/coach-interaction/ui/CueBand.vue
src/pwa/src/shared/lib/voice.ts
src/pwa/src/entities/coach/model/useVoiceConversation.ts
```

See also: [`docs/ux.md`](ux.md) (audio-first principles, mode
switching), [`docs/analysis-hall.md`](analysis-hall.md) (paddock
counterpart).
