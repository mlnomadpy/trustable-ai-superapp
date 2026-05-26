# 09 — Cool-Down

The lap after the last hot lap. Coach goes silent except for
corner-score chimes; the driver hears the result of every corner one
chime at a time.

## Purpose

Verb: **Process.** The transition from "driving hard" to "thinking
about it." No new advice; just summary chimes.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│  COOL DOWN                                                 │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│   ┌──────┐         CORNER SCORES                           │
│   │      │   T1   ●●●●○   GOOD                             │
│   │ T-ROD│   T2   ●●●●●   PERFECT                          │
│   │ thumb│   T3   ●●○○○   LOST 0.3s                        │
│   │  up  │   T4   ●●●●○   GOOD                             │
│   └──────┘   T5   ●●●●●   PERFECT                          │
│              T6   ●●●○○   OK                               │
│              T7   ●○○○○   LOST 0.5s                        │
│              T8   ●●●●○   GOOD                             │
│              T9   ●●●●●   PERFECT                          │
│              T10  ●●●●●   PERFECT                          │
│              T11  ●●●●○   GOOD                             │
│                                                            │
│         LAP 3 · 1:47.2 · -0.4s PB                          │
│                                                            │
│  → STAGE CLEAR ON TRACK STOP                               │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `revealing` | Mount | Reveal one corner row every ~600 ms with `corner_apex` chime |
| `complete` | All 11 corners revealed | Coach reaction sprite reflects overall lap; lap result line appears |
| `awaiting-stop` | Bridge in cool-down state | Wait for transition to Paddock; auto-route to `/track/sonoma/clear` |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach sprite (left) | 96×96 | Reaction picked from band: `thumbs_up` (great), `idle` (mid), `disappointed` (poor) |
| `score_dot_filled` / `score_dot_empty` | Per corner row | 1 frame each; row fills left-to-right with 60 ms stagger |
| `frame-card` | Whole panel | 9-slice |

Status bar **hidden** (continues HUD-style minimal mode).

## Vue component

```vue
<!-- pitwall-web/src/views/CoolDown.vue -->
<template>
  <div class="viewport cool-down">
    <h1 class="font-title text-title">COOL DOWN</h1>

    <CoachReaction :coach-id="save.preferredCoach" :emotion="lapBand" />

    <ol class="corner-list">
      <CornerScoreRow v-for="(c, i) in corners" :key="c.id"
                      :corner="c"
                      :revealed="i < revealedIndex" />
    </ol>

    <LapResultLine v-if="revealedIndex >= corners.length"
                   :lap="lap" :pb="pbDelta" />

    <p class="text-small text-ui-text-300">
      → STAGE CLEAR ON TRACK STOP
    </p>
  </div>
</template>

<script setup lang="ts">
import { useCueStore } from '@/stores/cue'
const cues = useCueStore()

cues.onCue((cue) => {
  if (cue.type === 'corner_score') {
    corners[cue.corner_idx] = { ...cue, revealed: true }
    audio.playSfx('corner_apex')
  }
  if (cue.type === 'session_state' && cue.value === 'paddock') {
    router.push({ name: 'clear', params: { trackId: 'sonoma' } })
  }
})
</script>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| SSE `/cues/stream?session_id=<sid>` | Continues from HUD; bridge tags new cues with `type: 'corner_score'` |

The bridge generates these `corner_score` cues at the cool-down
state-transition. Frontend doesn't compute the scores; bridge does.

## Audio cues

| Event | Sound |
|---|---|
| Mount | swap to `cooldown_loop` (lower energy) |
| Each corner score row reveals | `corner_apex` (50 ms chirp) |
| Last corner reveals | `score_total` (positive chord) |
| New PB on this lap | `pb_unlock` (6-note fanfare) — overrides `score_total` |
| Coach reaction frame | optional pre-rendered MP3 e.g. *"That was distance"* (T-Rod) — only on great laps |

## Input map

| Input | Action |
|---|---|
| All inputs | No-op (auto-routes when bridge hits Paddock state) |
| B | Skip ahead to Stage Clear (advanced; defaults to disabled to honor cool-down) |

## Edge cases

- **Bridge SSE drops** — show last cached corners; coach line:
  *"Connection's gone. Pull in safe."*
- **Driver pulls in immediately** (no cool-down lap) — corners revealed
  fast (one every 100 ms); auto-route still fires
- **Lap not actually a hot lap** (e.g., bailed mid-corner) — corners
  show ●○○○○ for the corners they didn't complete; coach `idle`
- **`prefers-reduced-motion`** — corners reveal all at once instead of
  staggered

## Related

- [`08-on-track-hud.md`](08-on-track-hud.md) — entry point
- [`10-stage-clear.md`](10-stage-clear.md) — destination
- [`03-character-bible.md`](../03-character-bible.md) — coach reaction
  matrix
- [`docs/ux.md` § Mode Switching](../../ux.md) — Cool-down phase
