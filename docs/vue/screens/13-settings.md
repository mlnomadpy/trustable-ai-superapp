# 13 — Settings

The garage's tuning bench. Audio sliders, display mode, controls
layout, hardware re-check, driver edit. All persists to the active
save slot.

## Purpose

Verb: **Tune.** Nothing about the driving — this is the dials for the
phone, the controls, the driver's identity.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ SETTINGS                                                   │
│                                                            │
│ ┌─ TAB ─────────────────────────────────────────────────┐ │
│ │ ▶ AUDIO  · DISPLAY · CONTROLS · CAR · DRIVER           │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                            │
│  MASTER          ████████████████░░░░    80 %              │
│  MUSIC           ██████████░░░░░░░░░░    50 %              │
│  SFX             ████████████████████   100 %              │
│  COACH VOICE     ████████████████████   100 %              │
│                                                            │
│  ☑ MUTE ALL                                                │
│  ☐ MUTE COACH VOICE (silence-is-coaching mode)            │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │ T-ROD: "Volume's your call, kid."                  │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  A · ADJUST    ◀ ▶ TAB    B · GARAGE                       │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `idle` | Default | Cursor on first setting in active tab |
| `editing` | A on a slider | Slider shows ◀ ▶ live drag; A or B exits edit |
| `confirming-destructive` | DRIVER → DELETE SAVE | Confirmation dialogue with disappointed coach |

## Tabs

### AUDIO
- Master volume slider (0–100 %)
- Music volume slider
- SFX volume slider
- Coach voice volume slider
- ☐ Mute all
- ☐ Mute coach voice ("silence-is-coaching mode" per `docs/ux.md`)

### DISPLAY
- ☐ Night mode (palette swap to night variant)
- ☐ Reduced motion (per `08-animation-spec.md`)
- ☐ Show FPS counter (debug)
- Scale picker: Auto / 1× / 2× / 3× / 4× / 5×

### CONTROLS
- Keyboard layout: Arrows / WASD / IJKL
- ☐ Swap A/B (left-handed)
- "TEST INPUT" button — opens a virtual gamepad echo for verification

### CAR
- Current car: BMW M3 (E46) — picker to change
- Loaded DBCs: pitwall.dbc + bmw_e46_m3.dbc — list with toggles
- "RUN HARDWARE TEST" → jumps to `15-pit-stall-setup.md`
- "HOW IS MY SCORE CALCULATED?" → opens score formula breakdown modal

### DRIVER
- Driver name (re-enter)
- Avatar slot picker (1–8; locked slots greyed)
- Skill level: BEGINNER / INTERMEDIATE / PRO
- "DELETE SAVE" — destructive; requires double confirmation

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (default T-Rod) | Bottom-right | `idle` (or `wrench_pose` while CAR tab is active, `clipboard_writing` for DRIVER tab) |
| `slider_track` / `slider_handle` | Audio + scale sliders | Static |
| `frame-card` | Section panels | 9-slice |
| `check_v` | Toggle states | Static |

## Vue component

```vue
<!-- pitwall-web/src/views/Settings.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">SETTINGS</h1>
    <TabPicker v-model="tab" :tabs="['AUDIO', 'DISPLAY', 'CONTROLS', 'CAR', 'DRIVER']" />

    <component :is="tabComponent" v-model="save.settings" />

    <DialogueBox v-if="coachQuip"
                 :coach-id="save.preferredCoach"
                 emotion="idle"
                 :text="coachQuip" />

    <HintBar :hints="hints" />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useSaveStore } from '@/stores/save'
const save = useSaveStore()
watch(() => save.settings, () => save.persist(), { deep: true })
</script>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| (none directly) | All settings local |
| `GET /signals/registry?include_can_state=true` | Lazy: when CAR tab opens, refresh DBC list + connection state |

## Audio cues

| Event | Sound |
|---|---|
| Tab switch | `cursor_select` |
| Slider tick | `cursor_move` (fires once per 5 % step, debounced) |
| Toggle flip | `cursor_select` |
| Volume change | applies live (you hear the new mix immediately) |
| DELETE SAVE confirmed | `cancel` (heavy) |

## Input map

| Input | Action |
|---|---|
| ◀ ▶ on tab strip | Switch tab |
| ▲ ▼ | Move within tab |
| A on a slider | Enter edit mode (◀ ▶ adjusts; A or B exits) |
| A on a toggle | Flip |
| A on a button (e.g., RUN HARDWARE TEST) | Trigger |
| B | Back to garage hub |

## Edge cases

- **DELETE SAVE on the last filled slot** — coach delivers full
  farewell; PWA returns to title; IndexedDB slot wiped
- **Avatar slot 8 selected (locked)** — coach: *"Earn that one first."*;
  fall back to current
- **Coach swap during settings (via coach-select shortcut?)** — not
  exposed here; user must visit `05-coach-select.md`
- **Volume changes during active session** — apply immediately; no
  confirmation
- **Reduced motion toggle** — applies immediately; sprite breathing
  pauses on next render
- **Keyboard layout change while in edit mode** — exits edit mode; new
  bindings active immediately

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — entry point (also via
  `Start` quick menu from any screen)
- [`02-onboarding.md`](02-onboarding.md) — initial values came from here
- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — RUN HARDWARE TEST jumps here
- [`07-controls.md`](../07-controls.md) — input config details
- [`06-audio-design.md`](../06-audio-design.md) — volume curves
- [`04-state-architecture.md`](../04-state-architecture.md) — settings persistence schema
