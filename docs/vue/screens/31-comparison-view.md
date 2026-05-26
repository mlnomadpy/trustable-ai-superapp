# 31 — Comparison View

Side-by-side analysis of two driving sessions. Reached from
`17-lap-times-hall.md` "COMPARE" button.

## Purpose

Verb: **Compare.** Where exactly is one lap (or session) faster than
another? Best vs second-best, today vs last week, self vs another
driver.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ COMPARE                                                    │
│                                                            │
│  LEFT     ▼ [ session-20260423 · LAP 7  · 1:46.8 ]          │
│  RIGHT    ▼ [ session-20260415 · LAP 5  · 1:48.2 ]          │
│                                                            │
│  DELTA total       -1.4 s   ──── L FASTER                   │
│                                                            │
│  ╔════ SPEED ═══════════════════════════════════════════╗  │
│  ║   ▁▂▃▄▅▆▆▆▇▇▇▆▆▅▄▃▂▁           L                    ║  │
│  ║   ▁▂▃▄▄▄▅▅▅▅▆▆▆▅▅▄▃▂▁          R                    ║  │
│  ║   T1                                            T11   ║  │
│  ╚═══════════════════════════════════════════════════════╝  │
│                                                            │
│  ╔════ BRAKE ═══════════════════════════════════════════╗  │
│  ║   __▁__▂___▁__▃___▁_▂           L                    ║  │
│  ║   __▁_▂__▃___▁__▃▂__▁           R                    ║  │
│  ╚═══════════════════════════════════════════════════════╝  │
│                                                            │
│  ╔════ G-LAT ═══════════════════════════════════════════╗  │
│  ║                                                       ║  │
│  ╚═══════════════════════════════════════════════════════╝  │
│                                                            │
│  TOP 3 DELTA SECTIONS                                       │
│   • T7 entry (1620-1820 m)   +0.6 s on L                   │
│   • T11 exit (4080-100 m)    +0.4 s on L                   │
│   • Carousel (1294-1540 m)   +0.3 s on L                   │
│                                                            │
│ A · OPEN REPLAY  B · BACK    ◀ ▶ SCRUB                     │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `selecting` | Mount or dropdown click | Pickers active; charts blank |
| `loading` | Both selections set | Fetch + cache both parquets |
| `displaying` | Data ready | Charts render with shared lap_distance x-axis |
| `scrubbing` | ◀ ▶ on charts | Cursor sweeps across; left + right deltas update |

## Use cases

| Compare | Source |
|---|---|
| Best vs second-best (same session) | Auto-suggested when entering from `17-lap-times-hall.md` |
| Best of last week vs best of this week | Auto-suggested if ≥ 2 weeks of data |
| Self vs another driver (same track) | Multi-driver households; uses `/driver/<id>/evolution` cross-reference |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Top-right, 48×48 | Emotion = `analyzing` per `../10-coach-emotions.md` |
| Cursor on chart | Vertical line | Bouncing 1 px |
| Pixel chart fills | Per metric | Static; `vue-chartjs` themed pixel-art per `../09-tech-stack.md` |

## Vue component

```vue
<!-- pitwall-web/src/views/ComparisonView.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">COMPARE</h1>

    <SessionPicker label="LEFT"  v-model="leftSel"  />
    <SessionPicker label="RIGHT" v-model="rightSel" />

    <DeltaSummary :delta="totalDelta" />

    <DualChart label="SPEED"   :left="left.speed"   :right="right.speed"   :cursor="cursorM" />
    <DualChart label="BRAKE"   :left="left.brake"   :right="right.brake"   :cursor="cursorM" />
    <DualChart label="G-LAT"   :left="left.glat"    :right="right.glat"    :cursor="cursorM" />

    <DeltaSections :sections="topDeltas" />

    <Sprite :sheet="save.preferredCoach" animation="analyzing" />
    <HintBar :hints="hints" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /sessions?driver=<name>&track=sonoma` | Populate session pickers |
| `GET /session/<a>/lap_time_table` | Lap pickers within each session |
| `GET /session/<a>/sync?t_from=&t_to=` | Telemetry for left lap |
| `GET /session/<b>/sync?t_from=&t_to=` | Telemetry for right lap |
| `GET /session/<x>/export.parquet?table=telemetry` | Cache for DuckDB-Wasm if user opens SQL console |

## Audio cues

| Event | Sound |
|---|---|
| Picker change | `cursor_move` |
| Both selected, charts populate | `cursor_select` |
| Scrub cursor | `cursor_move` (rate-limited to 5 Hz) |
| OPEN REPLAY | `cursor_select` → wipe to `11-replay.md` |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move between pickers / charts |
| ◀ ▶ | Scrub the chart cursor |
| A | OPEN REPLAY of focused lap (whichever side has the cursor) |
| B | Back to Lap Times Hall |
| Start | Pause menu |

## Edge cases

- **Only one session in saved data** — show single-side comparison
  ("best vs second-best" within that session)
- **Lap selections have different lap_distance lengths** — align by
  percentage, not absolute distance
- **One session has tall-store signals the other doesn't** — only show
  metrics both have; surface a note about missing fields
- **Network slow loading parquets** — partial render; chart fills as
  data arrives

## Related

- [`17-lap-times-hall.md`](17-lap-times-hall.md) — parent + entry point
- [`11-replay.md`](11-replay.md) — destination on A
- [`30-sql-console-fullscreen.md`](30-sql-console-fullscreen.md) — power-user version
- [`../04-state-architecture.md`](../04-state-architecture.md) — DuckDB-Wasm + OPFS
