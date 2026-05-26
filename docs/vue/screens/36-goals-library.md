# 36 — Goals Library

Sub-screen of `07-pre-brief.md` accessed via "+ CUSTOM GOAL" button.
Lets the driver create their own session goal beyond the
auto-suggested ones.

## Purpose

Verb: **Customize.** Make a goal that fits *this* driver's intention
for *this* session.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ CUSTOM GOAL                                                │
│                                                            │
│  KIND                                                      │
│  ╔═════════════════════╗  ╔═════════════════════╗          │
│  ║ ▶  CORNER FOCUS     ║  ║   LAP TIME          ║          │
│  ╚═════════════════════╝  ╚═════════════════════╝          │
│  ╔═════════════════════╗                                  │
│  ║   TECHNIQUE         ║                                  │
│  ╚═════════════════════╝                                  │
│                                                            │
│  DESCRIPTION                                               │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║ Carry more apex speed at T7_                          ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                                                            │
│  TARGET                                                    │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║   86  km/h    (currently 82 km/h on best lap)        ║  │
│  ║   ◀  ▶  to adjust                                     ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                                                            │
│  ┌──────┐                                                  │
│  │T-ROD │  "Realistic. Let's see if you can hold it."     │
│  │analyz│                                                  │
│  └──────┘                                                  │
│                                                            │
│  A · SAVE GOAL    B · CANCEL    ◆ LIBRARY                  │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `picking-kind` | Mount | Cursor on KIND tiles |
| `editing-description` | A on KIND tile | Character grid for description (max 40 chars) |
| `setting-target` | A on description done | Number stepper with unit picker |
| `validating` | A on target | Check goal is achievable per session capabilities |
| `saving` | Validation OK | Persist to save slot's `goalsHistory`; close back to pre-brief |
| `library` | ◆ pressed | Show list of previously saved custom goals; cursor pick to reuse |

## Validation

Before saving, the goal is checked against current session capabilities:

| Goal kind | Validation |
|---|---|
| `corner_focus` | The corner-aggregate signals (`speed_ms`, `g_lat`) must be in caps; if not, error: "your car doesn't expose enough sensors for this goal" |
| `lap_time` | Just check the target is between 60 s and 300 s and below current PB - 0.1 s |
| `technique` | The required signals for the technique must be in caps; e.g., trail-brake needs `brake_bar` + `g_lat` at ≥ 5 Hz |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Bottom-left, 64×64 | Emotion progression: `analyzing` (editing) → `encouraging` (saved) → `concerned` (validation fails) |
| `frame-card` | Each panel | Static |
| `cursor_arrow` | Active field | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/GoalsLibrary.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">CUSTOM GOAL</h1>

    <KindPicker v-model="kind" />
    <CharGrid v-if="step === 'description'"
              v-model="description" :max="40" />
    <NumberStepper v-if="step === 'target'"
                   v-model="target" :unit="unit" />

    <ValidationFeedback v-if="error"
                        :error="error" />

    <Sprite :sheet="save.preferredCoach"
            :animation="phaseEmotion"
            :variant="'idle'" />
    <p class="font-ui text-body italic">"{{ phaseLine }}"</p>

    <HintBar :hints="hints" />
  </div>
</template>

<script setup lang="ts">
import { useGoalEditor } from '@/lib/goal-editor'
const { kind, description, target, unit, error, phaseEmotion, phaseLine, save: doSave, openLibrary } = useGoalEditor()
</script>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/_live/capabilities` | Validation — does the car expose the required signals? |

Otherwise pure local. Saved goals live on the active save slot.

## Audio cues

| Event | Sound |
|---|---|
| KIND tile cursor | `cursor_move` |
| Character entry | `dialogue_blip` (rate-limited) |
| Number stepper increment | `cursor_move` |
| SAVE | `cursor_select` → return to pre-brief |
| Validation fail | `error_quiet` |
| LIBRARY open | `cursor_select` |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ ◀ ▶ | Move cursor / step number |
| A | Confirm step / advance |
| B | Back one step (or cancel if on KIND) |
| Start | Pause menu |
| ◆ | Open LIBRARY (reuse a saved goal) |

## Library sub-modal

When ◆ is pressed:

```
┌────────────────────────────────────────────────────────────┐
│  ╔══════════════════════════════════════════════════════╗  │
│  ║ SAVED GOALS                            12 saved       ║  │
│  ║ ─────────────────────────────────────────────────    ║  │
│  ║ ▶ Carry more apex speed at T7    used 5 times         ║  │
│  ║   Trail-brake every entry        used 3 times         ║  │
│  ║   Break 1:48                     used 2 times         ║  │
│  ║   …                                                   ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│  A · USE     B · CLOSE                                     │
└────────────────────────────────────────────────────────────┘
```

Cursor on first row; A pre-fills the goal editor with that goal;
B closes the modal.

## Edge cases

- **Empty description** — disallow SAVE; coach line: "Tell me what
  you want to work on."
- **Target outside achievable range** — show inline warning but allow
  save; the player owns the choice
- **Library full (20 saved goals)** — oldest unused is evicted on
  next save
- **Save fails (storage quota)** — error message + offer to clear
  oldest goals

## Related

- [`07-pre-brief.md`](07-pre-brief.md) — parent + entry point
- [`../04-state-architecture.md`](../04-state-architecture.md) —
  `goalsHistory` save-slot field
- [`12-quest-log.md`](12-quest-log.md) — where goals + their results
  live after the session
- [`../10-coach-emotions.md`](../10-coach-emotions.md) — phase emotions
