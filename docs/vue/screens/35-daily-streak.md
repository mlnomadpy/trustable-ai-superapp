# 35 — Daily Streak

Cheap one-second screen overlay that fires once per day on first
garage-hub entry. Pure gamification — *"day 5 in a row, keep it
going."*

## Purpose

Verb: **Show off.** Recognise the player for showing up.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│  (Garage Hub at 30 % opacity behind)                       │
│                                                            │
│                                                            │
│             ╔════════════════════════════════╗             │
│             ║                                ║             │
│             ║          DAY 5 STREAK          ║             │
│             ║         ─────────────          ║             │
│             ║                                ║             │
│             ║       KEEP IT GOING            ║             │
│             ║                                ║             │
│             ║   ┌──────┐                     ║             │
│             ║   │T-ROD │                     ║             │
│             ║   │excitd│                     ║             │
│             ║   └──────┘                     ║             │
│             ║   "Five in a row. That's       ║             │
│             ║    distance."                  ║             │
│             ╚════════════════════════════════╝             │
│                                                            │
│  Auto-dismisses in 2.5 s · Tap to continue                 │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `pending` | Garage hub mount, first time today, streak ≥ 2 | Schedule for after garage backdrop has settled (500 ms) |
| `slide-in` | Pending fired | Slide-in from top (250 ms outBack) |
| `lingering` | Slide-in done | Hold 2 500 ms |
| `dismissed` | Auto OR tap | Slide-out (200 ms inOutCubic); store today as streak day |

## Streak calculation

```ts
// pitwall-web/src/lib/streak.ts
function computeStreak(save: SaveSlot, now: Date): number {
  const last = save.lastSessionDate ? new Date(save.lastSessionDate) : null
  if (!last) return 0
  const hoursSince = (now.getTime() - last.getTime()) / 3600_000
  if (hoursSince < 24) return save.dailyStreakCount   // already counted today
  if (hoursSince < 48) return save.dailyStreakCount + 1   // continue streak
  return 1   // streak broken; today is day 1
}
```

Streak field on save slot:

```ts
interface SaveSlot {
  // …
  dailyStreakCount:  number       // current streak length
  lastSessionDate:   string | null
}
```

## Coach reaction by streak length

Driven by [`../10-coach-emotions.md`](../10-coach-emotions.md):

| Streak | Coach emotion | Coach line example |
|---|---|---|
| 2 days | `encouraging` | "Two in a row. Keep showing up." |
| 3 days | `encouraging` | "Three days. You're building something." |
| 5 days | `excited` | "Five in a row. That's distance." |
| 7 days | `proud` | "A whole week. Now we're cooking." |
| 14 days | `proud` | "Two weeks. You're a regular." |
| 30 days | `proud` | "Thirty days. You're family now, kid." |
| 100 days | `proud` (special variant) | "Hundred. I'm impressed." |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Center of card, 64×64 | Emotion per table above |
| `frame-card` | Card background | Static |
| `confetti` | Behind card on milestone days (5, 7, 14, 30, 100) | One-shot |

## Vue component

```vue
<!-- pitwall-web/src/components/DailyStreak.vue -->
<template>
  <Teleport to="body">
    <Transition name="slide-down-pixel">
      <div v-if="visible" class="streak-overlay">
        <Frame frame-type="card">
          <h2 class="font-title text-title">DAY {{ count }} STREAK</h2>
          <p class="font-ui text-body">KEEP IT GOING</p>
          <Sprite :sheet="save.preferredCoach"
                  :animation="emotion"
                  :variant="'idle'" />
          <p class="font-ui text-body italic">"{{ phrase }}"</p>
          <Confetti v-if="milestone" />
        </Frame>
      </div>
    </Transition>
  </Teleport>
</template>
```

## Endpoints consumed

None — pure local state. The streak is computed client-side from the
save slot.

## Audio cues

| Event | Sound |
|---|---|
| Streak overlay appears | `level_up` if milestone, `goal_complete` otherwise |
| Tap to dismiss | `cancel` |
| Auto-dismiss | (no sound) |

## Input map

| Input | Action |
|---|---|
| Tap anywhere | Dismiss + advance to garage hub |
| Any other input | No-op |

## Edge cases

- **Streak breaks (>48 h gap)** — overlay reads "DAY 1 STREAK · WELCOME
  BACK"; coach `relaxed`; no celebration sound, just `cursor_select`
- **Streak day 1** — no overlay (the player just started; nothing to
  celebrate yet)
- **Player visits garage hub twice in same day** — overlay shown only
  on first visit (date-stamped)
- **Save slot's `lastSessionDate` is null** — overlay never fires
  (driver never completed a session)
- **Streak counter accidentally rolls back due to clock change** —
  use UTC midnight rollover, not local; tolerate ±1 h slew

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — parent screen
- [`../04-state-architecture.md`](../04-state-architecture.md) — `dailyStreakCount` field
- [`24-achievement-toast.md`](24-achievement-toast.md) — same animation
  primitive (slide-in + linger)
