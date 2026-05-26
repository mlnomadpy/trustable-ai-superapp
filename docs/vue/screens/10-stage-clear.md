# 10 — Stage Clear

The most animated screen in the app. The post-session reveal — score
counts up, metrics fade in, medals slot-machine, coach delivers their
verdict. Every great GBA-era racing-RPG had one of these.

## Purpose

Verb: **Celebrate / learn.** Make analytics digestible by wrapping
them in fanfare. Real numbers, real medals; the celebration is genuine
not gamification-bait.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│                  ╔══════════════════╗                      │
│                  ║   STAGE CLEAR !  ║   ← slides down      │
│                  ╚══════════════════╝                      │
│                                                            │
│           ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                    │
│           ░░░  TOTAL SCORE          ░░░                    │
│           ░░░         8420           ░░░  ← counts up      │
│           ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                    │
│                                                            │
│   BEST LAP        1:46.8       -0.4s PB     ← row fade-in  │
│   IDEAL LAP       1:46.4        0.4s gain                  │
│   CONSISTENCY     ★★★★☆        σ=0.6s                      │
│   TRAIL BRAKE %   78%           +5 vs last                 │
│   COAST TIME      8%           ↓4  GOOD                    │
│                                                            │
│  GOALS                                                     │
│   ✓ APEX SPEED T7      82 → 86 km/h                        │
│   ✓ BREAK 1:48         got 1:46.8                          │
│   ✗ TRAIL BRAKE EVERY  4 of 11 entries                     │
│                                                            │
│  ★ NEW MEDALS                                              │
│   ┌────┐  ┌────┐                                           │
│   │ ★  │  │ ★  │   "Trail Brake Apprentice" · "Sub-1:47"   │
│   └────┘  └────┘                                           │
│                                                            │
│   ┌────────────────────────────────────────────────────┐   │
│   │ T-ROD: "Now THAT was distance."                    │   │
│   └────────────────────────────────────────────────────┘   │
│                                                            │
│  A · CONTINUE     B · HOME      ◆ SHARE                    │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch `lap_time_table` + `ideal_lap` + `lap_time_distribution` + `corners` + `/coach/debrief` + `/score` in parallel |
| `playing-sequence` | Data ready | 7 s orchestrated animation per `08-animation-spec.md` § "Frame-perfect Stage Clear sequence" |
| `awaiting-input` | Sequence complete | Hint bar revealed; A or B advances |
| `skipped` | A pressed during sequence | Snap to final still frame |

## Animation timeline

Authoritative sequence — see `08-animation-spec.md`:

```
t = 0      : enter; music score_fanfare; black background
t = 200    : "STAGE CLEAR" banner slides down (200 ms outBack)
t = 600    : Total score frame appears (instant)
t = 800    : Score counts 0 → final (1200 ms outCubic, ~12 ticks/sec, score_tick per 100)
t = 2000   : score_total chord
t = 2200   : Metric row 1 fades in
t = 2300   : Metric row 2 fades in (… 100 ms apart)
t = 2700   : Goal results appear; goal_complete or goal_miss per goal
t = 3200   : First medal slides in (350 ms outBack, medal_award)
t = 3700   : Second medal (if any)
t = 4200   : Third medal (if any)
t = 4700   : Coach portrait + dialogue box slide up (200 ms)
t = 4900   : Coach dialogue teletypes (~30 char/sec)
t = ~7000  : Hint bar reveals
```

B button at any point → snap to final still.

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach sprite (selected) | Bottom-left | Picked by performance band per `03-character-bible.md`: `victory` (PB+all goals), `thumbs_up` (PB or goals), `idle` (improved), `disappointed` (worse) |
| `medal_*` (5 tiers) | "NEW MEDALS" row | 350 ms outBack scale-in per medal |
| `confetti` 8-frame | Behind big SCORE on PB unlock only | One-shot |
| `frame-card` | Score block + metric block + goals block | 9-slice |
| `frame-dialogue` | Coach dialogue at bottom | 9-slice |

## Score formula (transparency)

Per `pitwall-web-design.md` § "Stage clear":

| Component | Weight | Source |
|---|---|---|
| Best-lap delta vs PB | 30 % | `lap_time_table.best_lap_s` |
| Consistency (1 / stddev) | 20 % | `lap_time_distribution.stddev_s` |
| Goal completion | 25 % | session goals |
| Bentley concept hits | 15 % | sum of coach-rule fires |
| Lap count vs target | 10 % | laps detected |

Players can open the formula breakdown via `13-settings.md` →
"How is my score calculated?" — driver agency over the magic.

## Vue component

```vue
<!-- pitwall-web/src/views/StageClear.vue -->
<template>
  <div class="viewport stage-clear">
    <Banner v-if="phase >= 1" text="STAGE CLEAR !" />

    <ScoreBlock v-if="phase >= 2"
                :counted-value="displayedScore"
                :final-value="totalScore" />

    <MetricRow v-for="(m, i) in metrics" :key="m.label"
               :metric="m"
               :visible="phase >= 3 + i" />

    <GoalResults v-if="phase >= 9" :goals="goals" />

    <MedalSlot v-for="(m, i) in newMedals" :key="m.id"
               :medal="m"
               :delay="i * 500" />

    <DialogueBox v-if="phase >= 12"
                 :coach-id="save.preferredCoach"
                 :emotion="performanceBand"
                 :text="debriefText" />

    <HintBar v-if="phase >= 13"
             :hints="['A · CONTINUE', 'B · HOME', '◆ SHARE']" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tween, ease } from '@/lib/tween'
import { T } from '@/lib/timings'

onMounted(async () => {
  // Fetch all bridge data in parallel
  const [table, ideal, dist, corners, debrief, score] = await Promise.all([
    fetch(`/api/session/${sid}/lap_time_table`).then(r => r.json()),
    fetch(`/api/session/${sid}/ideal_lap`).then(r => r.json()),
    fetch(`/api/session/${sid}/lap_time_distribution`).then(r => r.json()),
    fetch(`/api/session/${sid}/corners`).then(r => r.json()),
    fetch(`/api/coach/debrief`, { method: 'POST', body: JSON.stringify({ session_id: sid }) }).then(r => r.json()),
    fetch(`/api/score`, { method: 'POST', body: JSON.stringify({ session_id: sid }) }).then(r => r.json()),
  ])
  // ... orchestrate phases
  audio.playMusic('score_fanfare', { loop: false })
  tween(0, score.score, T.SCORE_COUNTUP, ease.outCubic, v => displayedScore.value = Math.round(v))
})
</script>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/<sid>/lap_time_table` | Best lap, PB delta |
| `GET /session/<sid>/ideal_lap` | Gain potential |
| `GET /session/<sid>/lap_time_distribution` | Consistency stddev → ★ rating |
| `GET /session/<sid>/corners` | Pedal % + per-corner data for the metrics block |
| `GET /session/<sid>/pedal_behavior` | Trail-brake %, coast % |
| `POST /coach/debrief` | LitertCoach.debrief() → narrative + focus list |
| `POST /score` | Local-Gemma 0–100 score + one-sentence why |

All fetched in parallel on mount; sequence waits for the slowest
(typically `/score` or `/coach/debrief` at 6–10 s on Apple Silicon).
While waiting: coach `clipboard_writing` + `coach_thinking` SFX loop.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `score_fanfare` (music, one-shot) |
| Per 100 score ticks | `score_tick` |
| Score lands | `score_total` |
| Each metric row | (silent — too noisy if 5 SFX in 500 ms) |
| Goal hit | `goal_complete` |
| Goal miss | `goal_miss` |
| Each medal slides in | `medal_award` |
| Personal best | `pb_unlock` (overrides `score_total`) |
| Driver level up | `level_up` (after sequence) |

## Input map

| Input | Action |
|---|---|
| A during sequence | Skip to final still |
| A after sequence | Continue to garage hub |
| B | Home (garage hub) |
| ◆ Start | (post-MVP) Share screenshot — disabled in v1 per privacy posture |

## Edge cases

- **No new medals** — medals row hidden; sequence shortens by 1.5 s
- **No PB this session** — confetti suppressed; coach picks `idle` not
  `victory`
- **All goals missed** — coach `disappointed`; debrief leads with
  reset-style language; score formula transparent shows where points
  came from
- **`/score` LLM unavailable (503)** — fall back to a deterministic
  formula on the PWA; coach line uses pre-rendered phrase
- **Driver hit a new level** — extra animation: level-up fanfare AFTER
  coach dialogue, separate banner: "LV. 13 — NEW PERSONAL RECORD"
- **`prefers-reduced-motion`** — sequence collapses to all-at-once
  reveal; SFX still play

## Related

- [`08-animation-spec.md`](../08-animation-spec.md) — full timing table
- [`09-cool-down.md`](09-cool-down.md) — entry point
- [`03-garage-hub.md`](03-garage-hub.md) — destination on continue
- [`11-replay.md`](11-replay.md) — destination on (post-MVP) "WATCH BEST LAP"
- [`17-lap-times-hall.md`](17-lap-times-hall.md) — drill-down
- [Bridge endpoints](../../api.md)
