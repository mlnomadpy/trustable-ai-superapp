# 24 — Achievement Toast

Slide-in overlay. Fires when the player earns a medal, levels up,
hits a coach-affinity tier, or unlocks a track. **Not a route** —
appears over whatever screen is active.

## Purpose

Verb: **Celebrate.** Acknowledge a win without yanking the player out
of what they're doing.

## Wireframe (slide-in from bottom-right)

```
┌────────────────────────────────────────────────────────────┐
│  (parent screen at 100 % opacity — no dim)                 │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                            ╔════════════════════════════╗  │
│                            ║ ★ MEDAL UNLOCKED            ║  │
│                            ║ ┌──┐ TRAIL BRAKE APPRENTICE ║  │
│                            ║ │★★│ See Quest Log ▶         ║  │
│                            ║ └──┘ ┌──┐ T-ROD              ║  │
│                            ║      │ proud │ "Distance."   ║  │
│                            ║      └──┘                    ║  │
│                            ╚════════════════════════════╝  │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `pending` | Achievement event queued during apex window | Wait for safe moment; do not interrupt mid-corner |
| `slide-in` | Safe moment | Slide-in from right (250 ms outBack) per `08-animation-spec.md` |
| `lingering` | Slide-in done | Hold 2 500 ms |
| `slide-out` | Linger ends OR tap | Slide-out (200 ms inOutCubic) |
| `dismissed` | Slide-out done | Removed from DOM |
| `tapped` | Tap on toast | Dismiss + navigate to detail (Quest Log medal page, Trainer Card level row, etc.) |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Medal sprite (per tier) | Left of toast, 32×32 | Static; medal tier picked from event |
| Coach (`save.preferredCoach`) | Right of toast, 48×48 | Emotion = `proud` (medal), `excited` (level-up), `encouraging` (affinity tier), `intense` (track unlock) |
| `frame-default` 9-slice | Toast background | Static |
| `flash-white` overlay | Spark behind medal during slide-in | 100 ms one-shot |

The coach emotion is the load-bearing detail — it says *"this is the
kind of win this is."* See [`../10-coach-emotions.md`](../10-coach-emotions.md).

## Vue component

```vue
<!-- pitwall-web/src/components/AchievementToast.vue -->
<template>
  <Teleport to="body">
    <TransitionGroup name="toast-slide">
      <div v-for="t in queue" :key="t.id"
           class="toast"
           @click="onTap(t)">
        <Sprite :sheet="'medals'" :animation="t.sprite" />
        <div class="text">
          <p class="font-title text-title">{{ t.title }}</p>
          <p class="font-ui text-body">{{ t.subtitle }}</p>
        </div>
        <Sprite :sheet="t.coachId" :animation="t.coachEmotion" :variant="'idle'" />
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup lang="ts">
import { useAchievementQueue } from '@/stores/achievement'
const { queue, onTap } = useAchievementQueue()
</script>
```

The `useAchievementQueue` store ensures only one toast shows at a time;
events arriving during apex-windows of `08-on-track-hud.md` are
buffered and surfaced during the next safe moment.

## Endpoints consumed

None directly. Events are emitted by:
- `useSaveStore` mutations (medal awarded, level changed)
- SSE `/cues/stream` from the bridge (when bridge detects a milestone)

## Audio cues

| Event type | Sound |
|---|---|
| Medal | `medal_award` (slot-machine ding) |
| Level up | `level_up` (1.8 s rising chime) |
| Coach affinity tier | `goal_complete` |
| Track unlock | `pb_unlock` |

Audio is **suppressed during apex window** of the on-track HUD per
`06-audio-design.md` § rule 5. SFX queues up with the visual.

## Input map

| Input | Action |
|---|---|
| Tap on toast | Dismiss instantly + navigate to detail |
| Any other input | No-op (the toast is non-blocking) |

## Edge cases

- **Multiple achievements at once (rare)** — queue them; show one at
  a time, 200 ms gap between
- **Network drop while toast pending** — toast still shows; the underlying
  data is local
- **Player dismissed via tap mid-slide-in** — finish slide-in, then
  immediately slide-out
- **`prefers-reduced-motion: reduce`** — skip slide-in animation,
  appear for 1 500 ms then disappear

## Related

- [`12-quest-log.md`](12-quest-log.md) — destination on tap (medals)
- [`04-trainer-card.md`](04-trainer-card.md) — destination on tap (level up)
- [`../08-animation-spec.md`](../08-animation-spec.md) — toast timings
- [`../06-audio-design.md`](../06-audio-design.md) — apex-window suppression
