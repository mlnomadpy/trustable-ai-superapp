# 25 — Loading Screen

The bridge between cold-boot and the title screen. Visible briefly
(target < 1.5 s) while sprite packs hydrate, fonts load, IndexedDB
connects.

## Purpose

Verb: **Wait.** Communicate "the app is starting" with minimum cognitive
load.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                ▓▓▓▓▓▓▓▓ ▓▓▓▓▓▓▓▓                            │
│                  PITWALL                                   │
│                ▓▓▓▓▓▓▓▓ ▓▓▓▓▓▓▓▓                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│            ████████████████░░░░░░░░░░░░░░░░░               │
│                  loading sprites…                          │
│                                                            │
│                                                            │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

Plain. Black background. PITWALL logo at center, smaller than title
screen (192×48 vs the title's 256×64). Progress bar below at 1/3
height. Status text under the bar.

## States

| State | Trigger | Behaviour |
|---|---|---|
| `boot` | App mount | Show static logo + "loading…" text |
| `progress` | Each load step completes | Bar advances + status text updates |
| `done` | All loads complete | Transition to title; total elapsed must be ≥ 600 ms (so the bar is visible even on fast machines) |
| `error` | Any load fails | Replace bar with red-mid `error_quiet` indicator + "TAP TO RETRY" |

## Load steps tracked

```ts
const steps = [
  { id: 'fonts',       weight: 5,  label: 'loading fonts…' },
  { id: 'sprites',     weight: 60, label: 'loading sprites…' },
  { id: 'audio',       weight: 20, label: 'loading sounds…' },
  { id: 'save-slots',  weight: 5,  label: 'reading save data…' },
  { id: 'bridge-ping', weight: 10, label: 'pinging bridge…' },
]
// Bar = sum of completed weights / 100
```

The bar is *honest*: it reflects actual progress, not a fake
animation.

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `logo_pitwall_small` | Center | Static |
| `progress_bar_filled` 1-frame | Bottom 1/3 | Width interpolates as steps complete |
| Cursor | Hidden | — |
| Coach | **Absent** (intentional — minimum cognitive load on the loading screen) | — |

## Vue component

```vue
<!-- pitwall-web/src/views/LoadingScreen.vue -->
<template>
  <div class="viewport boot">
    <Sprite name="logo_pitwall_small" />
    <div class="progress">
      <div class="bar-fg" :style="{ width: `${progress}%` }" />
    </div>
    <p class="font-ui text-body">{{ statusText }}</p>
    <button v-if="error" @click="retry" class="retry">
      ▼ TAP TO RETRY
    </button>
  </div>
</template>

<script setup lang="ts">
import { useBootProgress } from '@/lib/boot'
const { progress, statusText, error, retry } = useBootProgress()
</script>
```

## Endpoints consumed

| Endpoint | Step | Use |
|---|---|---|
| `GET /health` | `bridge-ping` | One-shot warm-up; non-blocking — failure proceeds to title with offline indicator |

## Audio cues

| Event | Sound |
|---|---|
| Mount | **No music**, no SFX (intentional) |
| Each step complete | No SFX (silent progress) |
| Done → transitioning | `boot_chime` plays *after* this screen, on title mount |
| Error | `error_quiet` |

Silence is itself a design choice. The loading screen is purely
functional; the title screen is where the brand begins to speak.

## Input map

| Input | Action |
|---|---|
| Tap on retry button (error state only) | Restart all failed steps |
| Any other input | No-op |

## Edge cases

- **All loads finish in under 600 ms** — artificially hold for the
  remainder so the player perceives a "the app booted" beat
- **Sprite pack 404** — `error` state with retry button + offline
  indicator hint
- **IndexedDB blocked (private browsing on iOS)** — proceed with
  in-memory fallback; show non-blocking warning on next screen
- **Service worker first install** — surface a small "pre-caching for
  offline use…" status text after main load is done; bar fills past
  100% in this case (cosmetic — show as a 2nd-pass)

## Related

- [`00-title.md`](00-title.md) — destination on success
- [`../09-tech-stack.md`](../09-tech-stack.md) § Performance budgets
  — < 1.5 s cold start target
- [`../06-audio-design.md`](../06-audio-design.md) — `boot_chime` plays
  on title, not here
