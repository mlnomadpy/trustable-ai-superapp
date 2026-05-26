# 17 — Lap Times Hall

The lap-by-lap audit. Best lap, ideal lap, distribution box-plot,
sector splits — all four lap-time endpoints surfaced as one screen.

## Purpose

Verb: **Audit your laps.** Where did time go? What's possible? How
consistent was I?

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ LAP TIMES HALL  · session 2026-04-29-1503  ◀ ▶              │
│                                                            │
│  ╔═ HEADLINE ═════════════════════════════════════════╗    │
│  ║  BEST LAP  1:46.8     IDEAL  1:46.4     GAIN  0.4s ║    │
│  ╚═══════════════════════════════════════════════════╝    │
│                                                            │
│  ┌─ LAP TABLE ──────────┐    ┌─ DISTRIBUTION (Tukey) ─┐   │
│  │ # · TOTAL · S1·S2·S3 ·Δ│   │                        │   │
│  │ 1 1:48.2 33.1 38.4 36.7 │   │     ╓─────╖           │   │
│  │ 2 1:47.5 32.9 38.2 36.4 │   │  ───╫─────╫───        │   │
│  │ 3 1:46.8 32.4 38.1 36.3 │←★ │     ╙─────╜           │   │
│  │ 4 1:48.0 33.0 38.5 36.5 │   │   ●  outlier         │   │
│  │ 5 1:47.3 32.8 38.2 36.3 │   │                        │   │
│  │ 6 1:50.1 34.2 39.0 36.9 │○  │   median 1:47.5         │   │
│  │ 7 1:47.0 32.5 38.0 36.5 │   │   stddev 0.6s          │   │
│  │ 8 1:46.9 32.6 38.0 36.3 │   │                        │   │
│  └──────────────────────┘    └────────────────────────┘   │
│                                                            │
│  ◐ T-ROD: "You ALMOST strung the perfect three sectors —   │
│     T11's exit cost you 0.3."                              │
│                                                            │
│  A · OPEN REPLAY    ◀ ▶ MOVE    B · BACK                   │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch all 4 endpoints in parallel; show skeleton |
| `loaded` | All four 200 OK | Render headline + table + box-plot |
| `row-focused` | Cursor on a lap row | Distribution chart highlights that lap as a dot |
| `replay` | A pressed | Wipe to `/replay/<sid>?lap=<n>` |
| `session-switching` | Sidebar/picker change | Reload everything |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `frame-card` | Headline + table + chart panels | 9-slice |
| `box_plot_glyphs` | Distribution chart | Static SVG-style pixel art |
| Cursor | On the lap row | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/LapTimesHall.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <SessionPicker v-model="sid" />

    <Frame frame-type="card" class="headline">
      <Stat label="BEST"  :value="formatLap(table.best_lap_s)" />
      <Stat label="IDEAL" :value="formatLap(ideal.ideal_lap_s)" />
      <Stat label="GAIN"  :value="formatDelta(ideal.gain_potential_s)" />
    </Frame>

    <div class="grid grid-cols-[2fr_1fr]">
      <LapTable :laps="table.laps" :focus="cursor"
                @select="openReplay" />
      <BoxPlot :stats="distribution"
               :highlight-lap="cursor" />
    </div>

    <DialogueBox v-if="coachLine"
                 :coach-id="save.preferredCoach"
                 emotion="thumbsup"
                 :text="coachLine" />

    <HintBar :hints="['A · OPEN REPLAY', '◀ ▶ MOVE', 'B · BACK']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/<sid>/lap_time_table` | Headline `best_lap_s` + per-lap rows |
| `GET /session/<sid>/lap_time_distribution` | Box-plot stats (q1, median, q3, whiskers, outliers, stddev) |
| `GET /session/<sid>/ideal_lap` | Headline `ideal_lap_s` + `gain_potential_s` |
| `GET /session/<sid>/sector_times` | Sector columns S1/S2/S3 in the table (joined with lap_time_table) |

The "session-switching" sidebar is populated via the global session
list (loaded once in `useSaveStore`); switching reloads only the four
endpoints above.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Cursor moves between rows | `cursor_move` |
| Cursor lands on best-lap row | `pb_unlock` (one-shot per visit) |
| A on a lap row | `cursor_select` → wipe to replay |
| Outlier dot focus (advanced) | `error_quiet` (it's an outlier — the lap that doesn't fit) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move cursor between lap rows |
| ◀ ▶ | Switch session in sidebar |
| A | Open replay for selected lap |
| B | Back to analysis hub |
| ◆ Start | Quick menu (open SQL panel for ad-hoc queries) |

## Edge cases

- **Session has < 1 complete lap** (400 from any endpoint) — screen
  shows "NO COMPLETE LAPS — drive a full lap first"
- **All laps have same time** (impossible-but-edge-case) — distribution
  collapses to a single line; coach line: *"Robotic. Try varying lines."*
- **Best lap == ideal lap** — gain shows "0.0s — IDEAL ACHIEVED"; coach
  pulses thumbs-up
- **Outlier dot click** — opens the outlier lap in replay; coach explains
  what was unusual (lap > Q3 + 1.5 IQR)
- **Bridge offline** — fall back to DuckDB-Wasm + cached Parquet for
  this session; same UI, slower if Parquet isn't cached

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — entry point
- [`11-replay.md`](11-replay.md) — destination per lap row
- [`18-corner-mastery.md`](18-corner-mastery.md) — sibling tab
- [Bridge `lap_time_table`](../../api.md#get-sessionsidlap_time_table)
