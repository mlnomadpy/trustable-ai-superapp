# 08 — On-Track HUD

The screen the driver glances at at 130 mph. **The most important
screen in the app.** Everything else loses its job if this fails.

## Purpose

Verb: **Drive.** Surface live coaching + grip state without
distracting from driving. Audio is primary; visual is peripheral.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│  LAP 3 / 8     1:47.2  (-0.4s pb)            ●●●●●  AI ON  │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│   ╔════╗                                          ╔════╗   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║▓▓▓▓║         ░░░░░░░░░░░░░░░░░                ║░░░░║   │
│   ║▓▓▓▓║         ░░  TRACK MAP   ░░                ║░░░░║   │
│   ║▓▓▓▓║         ░░░░░ ▶ pos ░░░░░                ║░░░░║   │
│   ║▓▓▓▓║         ░░░░░░░░░░░░░░░░░                ║░░░░║   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║▓▓▓▓║         T7 ENTRY  82 km/h                ║░░░░║   │
│   ║▓▓▓▓║         BRAKE AT THE 4-BOARD             ║░░░░║   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║░░░░║                                          ║░░░░║   │
│   ║░░░░║                                          ║░░░░║   │
│   ╚════╝                                          ╚════╝   │
│   GRIP  87%                                  OVER   0%     │
│                                                            │
│ ░ T-ROD: "ROLL THE BRAKE TO THE APEX"                      │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `entering` | Mount | Wake-lock + fullscreen requested; SSE opens |
| `live` | Telemetry flowing | Bars animate; corner card updates; cue band shows latest cue |
| `apex-window` | Bridge tags frame as `in_corner` | NO non-safety SFX, NO visual transitions; bars and cue band only |
| `cue-active` | New cue arrived | Bottom band teletypes new line over previous (one-line max, never overlap) |
| `over-grip` | Right bar > 50 % | `over_grip` SFX + right bar pulses (1 frame ui-bad) |
| `bridge-offline` | SSE error | Bars dim 50 %; "AI OFF" indicator top-right; sonic_model fallback continues client-side if cached |
| `earbuds-disconnect` | `audiooutputchange` event | Three large glyph cards (BRAKE / THROTTLE / CORNER) replace the cue band |
| `paused` | B button | Pause overlay with confirmation: "PAUSE ON TRACK?" |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `grip_bar_left` 11-frame (10 % steps) | Far left | Drives by `friction_circle_pct` from cues |
| `over_bar_right` 11-frame | Far right | Drives by amount over 100 % |
| `track_map_sonoma` | Centre | Static; ▶ position arrow drives by `lap_distance_m` |
| `cue_band_frame` | Bottom | 9-slice; teletype text inside |
| `glyph_brake/throttle/corner` 32×32 | Earbuds-disconnect mode | Static, low-saturation cards |
| `ai_indicator` 2-frame | Top-right | Pulse when AI ON; dim ✗ when offline |

Status bar **hidden** on this screen — max real estate.

## Vue component

```vue
<!-- pitwall-web/src/views/OnTrackHud.vue -->
<template>
  <div class="viewport hud-fullscreen">
    <HudTopBar :lap="lap" :time="lapTime" :pb-delta="pbDelta" :ai-on="ai.on" />
    <GripBar :pct="frictionPct" />
    <TrackMap track="sonoma" :pos-m="distanceM" :heading="heading" />
    <NextCornerCard :corner="upcoming" />
    <OverBar :pct="overPct" />
    <CueBand v-if="!earbudsOff" :cue="activeCue" />
    <GlyphCards v-else :brake="braking" :throttle="thr" :corner="upcoming" />
    <PauseOverlay v-if="paused" @resume="paused = false" @quit="quit" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useCueStore } from '@/stores/cue'
const cues = useCueStore()
const sid  = useSessionStore().sid

onMounted(async () => {
  document.documentElement.requestFullscreen?.()
  await navigator.wakeLock?.request('screen')
  cues.open(sid)
})
onUnmounted(() => {
  cues.close()
  document.exitFullscreen?.()
})
</script>
```

## Endpoints consumed

| Endpoint | When | Use |
|---|---|---|
| SSE `/cues/stream?session_id=<sid>` | Open on mount | Live coaching cues, friction-circle %, upcoming corner, lap time deltas |
| `POST /sensor/raw` | Bridge-side, not PWA-side | CAN reader posts here; PWA never calls it directly |
| `POST /session/<sid>/frames` | Optional, post-cue ack | Replay-grade frames if PWA buffered any client-side state — minimal use |

The PWA never calls an LLM here. Cues come pre-arbitrated from the
bridge per [ADR-002](../../adr/002-split-brain-arbiter.md) and
[ADR-017](../../adr/017-three-tier-coach-architecture.md).

## Audio cues

| Event | Sound |
|---|---|
| Cue arrives outside apex | pre-rendered MP3 from `/audio/coaches/<id>/<phrase-id>.mp3` |
| Right bar > 50 % | `over_grip` (one-shot, debounced 500 ms) |
| Coast > 5 s | `coast_warning` |
| Apex hit (geofence) | `corner_apex` (50 ms chirp) |
| **Inside apex window** | NO non-safety audio — `over_grip` + `corner_apex` only |
| SSE drops | `error_quiet` once |
| Music | `drive_loop` at low volume (40 % of music volume; ducks to 5 % during cues) |

## Input map

| Input | Action |
|---|---|
| D-pad / A | No-op (driver is driving, not poking) |
| B | Pause overlay |
| Tap anywhere | Dismiss any momentary cue early |
| Start | Pause overlay |

## Edge cases

- **SSE drops mid-stint** — `bridge-offline` state; bars dim; client-side
  sonic_model rules can still fire from cached frame data; auto-reconnect
  every 1 s
- **Earbuds disconnect** — `audiooutputchange` event swaps to glyph
  cards; spoken once: "AUDIO LOST" via Web Speech (because earbuds are
  the only audio path, this fires through the phone speaker)
- **Wake lock denied** by user — toast: "SCREEN MAY DIM"; HUD still
  works
- **Fullscreen denied** — HUD runs in browser chrome; status-bar visible;
  warn once
- **Phone overheats** — frame rate drops to 15 fps; "COOLING" indicator;
  bars and map continue
- **Battery < 15 %** — HUD darkens to AMOLED black; non-essential layers
  (gold-standard overlay, weather) hide
- **GPS lost** (tunnel, garage) — track-map ▶ freezes at last position;
  cue band shows "GPS LOST"

Per [`docs/ux.md` § "Failure modes"](../../ux.md), the principle: ONE
ANNOUNCEMENT, then go quiet.

## Related

- [ADR-002 — Split-brain arbiter](../../adr/002-split-brain-arbiter.md)
- [ADR-017 — Three-tier coach](../../adr/017-three-tier-coach-architecture.md)
- [`07-pre-brief.md`](07-pre-brief.md) — entry point
- [`09-cool-down.md`](09-cool-down.md) — destination
- [`06-audio-design.md`](../06-audio-design.md) — HUD audio rules
- [`docs/ux.md` § Audio + HUD](../../ux.md)
