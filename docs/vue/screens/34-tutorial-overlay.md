# 34 — Tutorial Overlay

First-time-user hint layer. Overlays each screen with coach speech
bubbles explaining what to do. **Not a route** — fires once per
screen per save slot.

## Purpose

Verb: **Learn.** Get a new driver oriented without forcing a long
tutorial mode.

## Wireframe (over Garage Hub, first visit)

```
┌────────────────────────────────────────────────────────────┐
│  TAHA · LV.1 · ⚙ T-ROD                          15:32 PT   │
│                                                            │
│   ╔══════════════════╗  ╔══════════════════════╗            │
│   ║   ▶ TRACK         ║  ║   PIT STALL          ║            │
│   ║                   ║  ║                      ║            │
│   ║   GO RACING       ║  ║   CONNECT · TUNE     ║            │
│   ╚════════╤═════════╝  ╚══════════════════════╝            │
│            │                                                │
│   ┌────────▼─────────────────────────────────────┐         │
│   │  ┌──────┐                                    │         │
│   │  │T-ROD │  Tap TRACK to go racing.            │         │
│   │  │encour│  Tap PIT STALL to check the car.    │         │
│   │  └──────┘                                    │         │
│   │                                              │         │
│   │  A · CONTINUE     B · SKIP TUTORIAL          │         │
│   └──────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `triggered` | Save slot's `tutorialsSeen` set lacks the current screen id | Schedule overlay after a 500 ms beat (so the screen mounts cleanly first) |
| `pointing` | Active | Coach speech bubble + arrow pointing at a UI element; everything else dimmed 60% |
| `step-N` | Multi-step tutorial | A advances to next step; up to 3 steps per screen |
| `done` | Last step + A | Mark screen seen in save slot; remove overlay |
| `skipped` | B at any step | Mark all screens seen; coach speaks farewell line |

## Per-screen tutorial scripts

Lives in `pitwall-web/data/tutorials/<screen-id>.md`. Markdown blocks
with anchors:

```yaml
# pitwall-web/data/tutorials/garage-hub.md
- target: tile-track
  emotion: encouraging
  text: "Tap TRACK to go racing."
- target: tile-pit-stall
  emotion: serious
  text: "First time? Tap PIT STALL to check the car connection."
- target: tile-coaches
  emotion: relaxed
  text: "Pick a different coach any time you want."
```

The `target` references a `data-tutorial-id` attribute on the actual
UI element so the overlay arrow knows where to point.

## Special cases

| Screen | Tutorial focus |
|---|---|
| Garage Hub | Where each tile leads (3 steps) |
| Pit Stall Setup | Reading the connection chain (1 step) |
| Pre-Brief | What goals do (2 steps) |
| **On-Track HUD** | **DON'T LOOK AT THE PHONE** — single overlay before HUD goes live; coach `intense`; coach explicitly says: *"Audio is the coaching. Don't read the screen."* |
| Stage Clear | What the score breakdown means (2 steps) |
| Trainer Card | Skill radar interpretation (1 step) |
| Coach Select | What affinity does (1 step) |
| World Map | Locked tracks + how to unlock (1 step) |
| Replay | Scrub gesture + chart cursor (2 steps) |
| Quest Log | Goals vs medals (2 steps) |
| SQL Console | Power-user warning + example queries (1 step) |

Other screens: no tutorial unless explicitly added.

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Speech bubble | Emotion driven by tutorial step's `emotion` field |
| `tutorial_arrow` 4-frame | Pointing at target | Loops at 6 Hz |
| `frame-dialogue` | Around speech bubble | Static |

The on-track HUD tutorial is the most important — coach uses
`intense` (per `../10-coach-emotions.md`) to communicate the gravity
of "don't look at the phone while driving."

## Vue component

```vue
<!-- pitwall-web/src/components/TutorialOverlay.vue -->
<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="active" class="tutorial-overlay">
        <Dim />
        <Spotlight :target="step.target" />
        <ArrowFromBubbleTo :target="step.target" />
        <DialogueBox
          :coach-id="save.preferredCoach"
          :emotion="step.emotion"
          :text="step.text"
          @advance="next"
          @skip="skipAll"
        />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTutorialStore } from '@/stores/tutorial'
const { active, step, next, skipAll } = useTutorialStore()
</script>
```

## Endpoints consumed

None. All tutorial content is shipped with the PWA. Read-status
persists in the save slot's `tutorialsSeen: string[]`.

## Audio cues

| Event | Sound |
|---|---|
| Overlay appears | `transition_wipe` (short) |
| Step advance | `cursor_select` |
| Skip all | `cancel` |
| First-ever entry to on-track HUD tutorial | Coach voice clip plays the warning (pre-rendered) |

## Input map

| Input | Action |
|---|---|
| A | Advance to next step (or finish) |
| B | Skip all tutorials (with confirmation) |
| Tap on speech bubble | Same as A |
| Tap outside bubble | No-op (modal) |
| All other inputs | Disabled while tutorial active |

## Edge cases

- **Player skips tutorials globally then visits Settings** — option to
  re-enable from Settings → "SHOW TUTORIALS"
- **Tutorial would block on-track entry** — fires *before* the HUD
  music starts; coach speaks; player taps to confirm; only then HUD
  goes live. **This is non-skippable on first visit** — it's the
  safety message.
- **Save slot resets / new driver** — every screen's tutorial fires
  again for that driver
- **`prefers-reduced-motion: reduce`** — arrow doesn't loop; text
  appears all at once instead of teletyping

## Related

- [`../03-character-bible.md`](../03-character-bible.md) — coach voice
- [`../10-coach-emotions.md`](../10-coach-emotions.md) — emotion per step
- [`../04-state-architecture.md`](../04-state-architecture.md) — `tutorialsSeen` save-slot field
- [`13-settings.md`](13-settings.md) — re-enable toggle
