# 14 — End of Day

The wind-down. Player taps Start → "End Session for the Day"; the app
shows today's tally, coach delivers a farewell, fade-to-night, back to
title.

## Purpose

Verb: **Wind down.** Punctuate the day. Sleep button for the brain.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░ NIGHT  SKY ░░░░░░░░░░░░░░░░░░░░░░░░  │
│                                                            │
│                  END  OF  DAY                              │
│                                                            │
│ ╔═ TODAY ══════════════════════════════════════════════╗   │
│ ║   SESSIONS         3                                  ║   │
│ ║   TOTAL LAPS       23                                 ║   │
│ ║   BEST LAP         1:46.8 (NEW PB ✓)                  ║   │
│ ║   MEDALS EARNED    2 ★ ★                              ║   │
│ ║   LEVEL PROGRESS   ████████░░  Lv 12 → 13 (4 to go)   ║   │
│ ╚═══════════════════════════════════════════════════════╝  │
│                                                            │
│            ┌──────┐                                        │
│            │      │                                        │
│            │ T-ROD│   "Same time tomorrow, kid."           │
│            │ bed  │                                        │
│            │ lie  │                                        │
│            └──────┘                                        │
│                                                            │
│           ░ Z ░                                            │
│         ░ Z ░                                              │
│       ░ Z ░                                                │
│                                                            │
│  → fades to night → back to title                          │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `summary` | Mount | Tally appears row-by-row (200 ms each) |
| `farewell` | Summary done | Coach `bed_lie` or `coffee_mug` sprite + farewell dialogue (teletype) |
| `fading-night` | Dialogue done + 1 s pause | 1500 ms fade to ink-deep with `fade-to-night` |
| `gone` | Fade complete | Router → `/` (title) |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `bg_night_paddock` | Background | Static; subtle stargazing ambient (per T-Rod row 13: stargazing frames) |
| Coach `bed_lie` (T-Rod) or alternates | Centre | 1-frame; `Z` floating sprite plays at 1 Hz |
| `Z_floating` | Above sleeping coach | 3-frame at 1 Hz |
| `frame-card` | Tally panel | 9-slice |

## Vue component

```vue
<!-- pitwall-web/src/views/EndOfDay.vue -->
<template>
  <div class="viewport eod">
    <Sprite name="bg_night_paddock" class="absolute inset-0 -z-10" />

    <h1 class="font-title text-title-lg">END  OF  DAY</h1>

    <Frame frame-type="card">
      <SummaryRow v-for="(r, i) in tally" :key="r.label"
                  :label="r.label" :value="r.value"
                  :visible="phase >= 1 + i" />
    </Frame>

    <Sprite name="trod" :animation="sleepingAnim"
            class="coach-lie" v-if="phase >= 6" />
    <Sprite name="z_floating" v-if="phase >= 6" class="z-stack" />

    <DialogueBox v-if="phase >= 7"
                 :coach-id="save.preferredCoach"
                 emotion="idle"
                 :text="farewellText"
                 @done="phase = 8" />

    <FadeOverlay v-if="phase >= 9" />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { audio } from '@/lib/audio'
onMounted(async () => {
  audio.playMusic('eod_loop')
  await save.persist()           // commit the day's stats
  await audio.playVoice(save.preferredCoach, 'farewell_eod')
  setTimeout(() => router.push({ name: 'title' }), T.FADE_NIGHT + 500)
})
</script>
```

## Endpoints consumed

None. EOD reads from local save slot only. Day's stats are computed
client-side from `save.sessions` filtered to today.

## Audio cues

| Event | Sound |
|---|---|
| Mount | swap to `eod_loop` (slow, melancholic) |
| Each summary row reveals | `score_tick` |
| Coach farewell | pre-rendered MP3 `farewell_eod.mp3` per coach |
| Fade-to-night | `night_chime` (5-note descending lullaby) |
| Title screen returns | `title_loop` (per `00-title.md`) |

## Input map

| Input | Action |
|---|---|
| A | Skip ahead (jumps to fade if player presses early) |
| B | Cancel — return to garage hub (no farewell) |
| Other | No-op |

## Edge cases

- **No sessions today** — show "NO SESSIONS TODAY"; coach line:
  *"Tomorrow then."*; still fades to night
- **Driver leveled up today** — extra row: "LV. 12 → 13 ✓"; pulses
  with `level_up` SFX
- **First-time end-of-day** — coach delivers a longer welcome-to-the-
  routine speech (one-shot per save slot)
- **Multiple saves** (driver A finished, driver B starts) — EOD is
  per-slot; switching slot bypasses
- **`prefers-reduced-motion`** — fade-to-night collapses to 200 ms

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — entry point (Start menu →
  "End Session for the Day")
- [`00-title.md`](00-title.md) — destination
- [`08-animation-spec.md`](../08-animation-spec.md) — fade-to-night timing
- [`06-audio-design.md`](../06-audio-design.md) — `eod_loop`, `night_chime`,
  per-coach farewell MP3
- [`03-character-bible.md`](../03-character-bible.md) — T-Rod bed/sleep
  frames (row 13)
