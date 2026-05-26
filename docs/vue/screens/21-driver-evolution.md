# 21 — Driver Evolution

The "see your growth" screen. Multi-session time-series across all
sessions for this driver. Big-picture view; the trainer card drilled
into a story arc.

## Purpose

Verb: **See your growth.** Are you actually getting faster? Where?
What's the macro trend?

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ DRIVER EVOLUTION · TAHA AT SONOMA                          │
│                                                            │
│ ╔═ HERO ═══════════════════════════════════════════════╗   │
│ ║   FIRST 1:50.5  →  LATEST 1:46.8                      ║   │
│ ║   ▼ -3.7 s OVER 47 SESSIONS                           ║   │
│ ║                                                       ║   │
│ ║   ⚡ T11 apex speed: +8.2 km/h since session #1         ║   │
│ ╚═══════════════════════════════════════════════════════╝  │
│                                                            │
│ ─── BEST LAP (purple) · MEDIAN LAP (grey) ───              │
│                                                            │
│  ▲                                                         │
│  │ ░                                                       │
│  │  ░    ░░                                                │
│  │   ░░░░  ░░    ░                                         │
│  │      ░░░░░░░░░░░░░░░░  ─── best                         │
│  │ ─────────────────────  ─── median                       │
│  │__________________________________________               │
│   1    10   20   30   40   47  ← session index             │
│                                                            │
│ ─── SECTOR PBs (3 lines) ───                               │
│                                                            │
│ ╔═ PER-CORNER IMPROVEMENT HEATMAP ══════════════════════╗  │
│ ║      session #1                                #47    ║  │
│ ║ T1   ░░░ ▒▒▒ ▒▒▓ ▒▓▓ ▓▓█  better → ░ to █             ║  │
│ ║ T7   ░░░ ░▒▒ ▒▒▒ ▒▒▓ ▓▓▓                              ║  │
│ ║ T11  ░░▒ ▒▒▒ ▒▒▓ ▒▓▓ ▓▓█  ← biggest gainer            ║  │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│  ◐ T-ROD: "T11's where you found 0.5s. Don't lose it."     │
│                                                            │
│  ◀ ▶ SCRUB SESSION                B · BACK                 │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch evolution + profile in parallel |
| `idle` | Loaded | Hero card + 5-line chart + heatmap; coach commentary auto-generated |
| `< 5 sessions` | 204 from `/evolution` | Placeholder "NEED 5 SESSIONS" with progress bar; coach: *"Keep driving."* |
| `session-scrub` | ◀ ▶ pressed | Highlight specific session in the chart |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `frame-card` | Hero + heatmap panels | 9-slice |
| `chart_pixel_line` | Multi-line chart | Pixel-style; uses chart.js with pixel theme |
| `heatmap_cell_*` | Per-corner heatmap | 5-step gradient ░ ▒ ▓ █ |
| Coach (selected) | Bottom-right | `idle` (or `clipboard_writing` while loading) |

## Vue component

```vue
<!-- pitwall-web/src/views/DriverEvolution.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">DRIVER EVOLUTION · {{ name }} AT SONOMA</h1>

    <Frame frame-type="card" class="hero" v-if="enoughSessions">
      <h2>FIRST {{ firstBest }} → LATEST {{ latestBest }}</h2>
      <p>▼ {{ improvement }} OVER {{ sessionCount }} SESSIONS</p>
      <p v-if="biggestGain">⚡ {{ biggestGain.corner }} apex speed: {{ biggestGain.deltaKmh }} km/h since session #1</p>
    </Frame>

    <Placeholder v-else
                 :sessions-needed="5 - sessionCount" />

    <PixelChart series-set="evolution"
                :data="evolution.evolution"
                :x-key="'session_index'"
                :y-series="['best_lap_s', 'median_lap_s', 'sector_pbs.s1', 'sector_pbs.s2', 'sector_pbs.s3']" />

    <CornerImprovementHeatmap :data="cornerHeatmap" />

    <DialogueBox v-if="coachLine"
                 :coach-id="save.preferredCoach"
                 :emotion="trendEmotion"
                 :text="coachLine" />

    <HintBar :hints="['◀ ▶ SCRUB SESSION', 'B · BACK']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /driver/<id>/evolution?track=sonoma` | Per-session best/median + sector PBs + summary deltas + biggest_corner_gain |
| `GET /driver/<id>/profile` | Skill radar + event-sourced profile data |

The corner-improvement heatmap is computed client-side from the
evolution rows — for each session, look at `corner_aggregates`-like
data in the profile and render as a 5-step heatmap.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Hero card reveals | `score_total` (positive chord, one-shot) |
| Cursor on a chart point | `cursor_move` |
| Heatmap cell focused | `cursor_move` |
| Coach line displays | (no extra SFX; coach voice optional) |

## Input map

| Input | Action |
|---|---|
| ◀ ▶ | Scrub session index in the chart (highlights one session) |
| ▲ ▼ | Switch focus zone (chart ↔ heatmap) |
| A | Open Lap Times Hall for the focused session |
| B | Back to analysis hub |
| ◆ Start | Toggle chart series visibility (best / median / S1 / S2 / S3) |

## Edge cases

- **Evolution endpoint returns 204** (< 5 sessions) — placeholder
  screen with progress bar showing "3 / 5 SESSIONS"; coach line:
  *"Two more sessions and we can read the trend."*
- **Driver has 0 sessions** — endpoint 404; show: *"No sessions yet."*
- **Massive jump in lap time** (e.g., car or driver swap) — chart
  shows a vertical break + small ⚠ icon at the discontinuity
- **Sessions span multiple cars** — colour data points by car (BMW =
  blue, GR86 = orange, etc.); legend in corner
- **`/profile` 404** — radar / event data hidden; chart still works

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — entry point
- [`04-trainer-card.md`](04-trainer-card.md) — sibling (alt evolution view)
- [`17-lap-times-hall.md`](17-lap-times-hall.md) — destination on A
- [Bridge `/driver/<id>/evolution`](../../api.md#get-driveridevolutiontracksonoma)
- [Bridge `/driver/<id>/profile`](../../api.md)
- [ADR-007 — Event-sourced driver profile](../../adr/007-event-sourced-profile.md)
