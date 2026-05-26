# 26 — Bridge Offline State

Banner overlay + expanded diagnostic. Appears when the bridge becomes
unreachable. **Not a route** — overlays whatever screen is active.

## Purpose

Verb: **Diagnose.** Tell the player *what's wrong* and *what to do
about it* without taking them out of the screen they were on.

## States

| State | Trigger | Behaviour |
|---|---|---|
| `silent` | Bridge healthy or first poll only | Hidden |
| `transient` | One failed `/health` poll | Still hidden — could just be jitter |
| `banner` | 3+ consecutive failed polls (≥ 15 s) | Red banner appears at top of any screen |
| `expanded` | Banner tapped | Full-screen diagnostic with troubleshooting + reconnect |
| `recovering` | `/health` returns 200 again | Banner shows "RECONNECTED" for 1 s, then hides |

## Wireframe — banner state (top of any screen)

```
┌────────────────────────────────────────────────────────────┐
│ ░ BRIDGE OFFLINE — RECONNECTING…       ⚠ tap for details   │░
├────────────────────────────────────────────────────────────┤
│  (parent screen renders normally below)                    │
│                                                            │
│                                                            │
│                                                            │
│  …                                                         │
└────────────────────────────────────────────────────────────┘
```

Red `ui-bad` background, white text, small spinner sprite at the left.
Banner is 16 logical px tall — same as the status bar so it doesn't
shove other content down.

## Wireframe — expanded state

```
┌────────────────────────────────────────────────────────────┐
│ BRIDGE DIAGNOSTIC                                          │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│  ┌──────┐                                                  │
│  │T-ROD │  "Lost the bridge. Let's get you back online."   │
│  │concd │                                                  │
│  └──────┘                                                  │
│                                                            │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║  URL          http://127.0.0.1:8765                  ║  │
│  ║  LAST OK      15 min ago                             ║  │
│  ║  LAST ERROR   ECONNREFUSED                           ║  │
│  ║  RETRIES      18 (every 5 s)                         ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                                                            │
│  TROUBLESHOOTING                                           │
│  ▸ Is the bridge running?                                  │
│      python3 -m src.pitwall                       │
│  ▸ Is `adb reverse tcp:8765 tcp:8765` set up?              │
│  ▸ Is Termux's foreground service alive?                   │
│      sv status pitwall-bridge                              │
│                                                            │
│   A · RETRY NOW    B · BACK    ◆ COPY DIAG                │
└────────────────────────────────────────────────────────────┘
```

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `loading_dots` 6-frame | Banner left | Spins while polling |
| `error_indicator` red | Banner right | Static |
| Coach (`save.preferredCoach`) | Expanded view, top-left | Emotion = `concerned` (per `../10-coach-emotions.md`) |
| `frame-default` 9-slice | Expanded panel | Static |

## Vue component

```vue
<!-- pitwall-web/src/components/BridgeOfflineBanner.vue -->
<template>
  <Teleport to="body">
    <Transition name="slide-down-pixel">
      <div v-if="state === 'banner'" class="bridge-banner">
        <Sprite name="loading_dots" animation="spin" />
        <span class="font-ui text-body">BRIDGE OFFLINE — RECONNECTING…</span>
        <span class="hint">⚠ tap for details</span>
      </div>
    </Transition>
  </Teleport>
  <BridgeDiagnostic v-if="state === 'expanded'" @retry="retry" @close="state='banner'" />
</template>

<script setup lang="ts">
import { useBridgeStore } from '@/stores/bridge'
import { ref, watch } from 'vue'

const bridge = useBridgeStore()
const state = ref<'silent' | 'banner' | 'expanded'>('silent')

watch(() => bridge.consecutiveFailures, (n) => {
  if (n >= 3 && state.value === 'silent') {
    state.value = 'banner'
    audio.playSfx('error_quiet')   // once, not repeated
  } else if (n === 0 && state.value !== 'silent') {
    audio.playSfx('goal_complete')
    setTimeout(() => state.value = 'silent', 1000)
  }
})
</script>
```

## What gets greyed out while offline

| Screen | Behaviour |
|---|---|
| Garage Hub TRACK tile | Greys out, A no-op + tooltip "bridge offline" |
| World Map | Read-only — track pin info from cache; cannot enter pre-brief |
| Pre-Brief | If reached, blocks "CONFIRM" button |
| On-Track HUD | Switches to "ghost cue" mode — sonic_model fallback, no LLM cues |
| Stage Clear | Cached score from save slot; no new debrief |
| Analysis screens | Work from OPFS-cached parquets if available |
| Pit Stall Setup | Chain shows ✗ on every row; the screen is *most useful* in this state |

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /health` | Polled every 5 s by `useBridgeStore`; the trigger for this screen |
| `POST /health/manual-retry` (proposed) | Triggered from RETRY NOW button — forces an immediate poll |

## Audio cues

| Event | Sound |
|---|---|
| First detection (banner appears) | `error_quiet` once |
| Recovery (banner shows "RECONNECTED") | `goal_complete` once |
| Subsequent failed polls | Silent (don't spam) |
| Tap to expand | `cursor_select` |
| RETRY NOW button | `cursor_select` |

## Input map

While banner is shown:

| Input | Action |
|---|---|
| Tap on banner | Expand to full diagnostic |
| Any other input | Pass-through to parent screen |

While expanded:

| Input | Action |
|---|---|
| A | Manual retry (immediate poll) |
| B | Collapse back to banner |
| Start | No-op (don't open pause menu over the diagnostic) |
| ◆ | Copy diagnostic JSON to clipboard |

## Edge cases

- **Bridge is alive but specific endpoint 503s** — banner does NOT
  trigger; this is a per-endpoint problem, surfaced inline by the
  consumer
- **Polling itself raises (network error)** — counts as a failure;
  same logic
- **Bridge offline at app boot** — banner shows on title screen too;
  doesn't block PRESS START since most screens still work
- **Auto-recovery during expanded view** — diagnostic reflows to
  show success; user can still close out
- **Pixel goes to sleep, wakes 30 min later** — the polling resumes
  on `pageshow`; first poll usually succeeds; banner just blinks
  briefly

## Related

- [`../04-state-architecture.md`](../04-state-architecture.md) §
  Bridge state — the polling source
- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — the deepest
  diagnostic; "GO TO PIT STALL" button could link here
- [`08-on-track-hud.md`](08-on-track-hud.md) — ghost-cue fallback
