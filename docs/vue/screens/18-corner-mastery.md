# 18 — Corner Mastery

The deep-dive on cornering. Track-map sprite up top with each corner
colour-coded by performance band + grade; tap-to-drill-in panel below;
throttle box-plots and brake/accel bars stacked for context.

## Purpose

Verb: **Master corners.** Where am I leaving time? Which corners are
above grade, which below? What's the recurring weakness?

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ CORNER MASTERY · session 2026-04-29-1503                   │
│                                                            │
│  ╔═ TRACK MAP (each corner colour-coded) ═══════════════╗ │
│  ║  ▒  ◐ T1  ◑ T2  ◓ T3  ◒ T3a  ◐ T4  ◑ T5  ◓ T6        ║ │
│  ║  ▒  ◐ T7  ◑ T8  ◓ T8a  ◒ T9  ◐ T10  ▶◑ T11           ║ │ ← T11 focused
│  ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│  ╔═ T11  CALAMITY CORNER ═══════════════════════════════╗ │
│  ║  ENTRY 88 km/h   APEX 64 km/h   EXIT 95 km/h          ║ │
│  ║  PEAK BRAKE 41 bar   MAX gLat 1.42                    ║ │
│  ║  CORNER TIME 4.2s   GOLD DELTA -0.3s   GRADE B+        ║ │
│  ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ─── THROTTLE % BY CORNER (box-plot per corner) ───         │
│ T1  ╓━━╫━━╖   T7  ╓━━╫━━╖                                 │
│ T2  ╓━╫━━━╖   T8  ╓━━╫━━╖                                 │
│ T3  ╓━━━╫━━╖  T9  ╓━━━╫━╖                                 │
│ T4  ╓━╫━━━╖   T10 ╓━━╫━━╖                                 │
│ T5  ╓━━╫━╖    T11 ╓━━━╫━━╖                                │
│ T6  ╓━━╫━━╖                                               │
│                                                            │
│ ─── BRAKE/ACCEL (per-corner) ───                           │
│ ▼ DECEL  T7  ███  T10 ████  T11 ██                         │
│ ▲ ACCEL  T11 █████ T4  ███   T10 ██                        │
│                                                            │
│  A · DRILL DOWN    ◀▶▲▼ MOVE   B · BACK                    │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch 4 endpoints in parallel; track-map skeleton |
| `corner-focused` | Cursor on corner pin | Drill panel populates with that corner's data |
| `corner-detail` | A pressed | Modal expands with full per-pass data + coach commentary |
| `band-filter` | Tab switch | Filter to low/med/high speed band |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `track_map_sonoma` (with 11 corner pins) | Top | Static; pins coloured by classification (low=red, med=amber, high=green) and outlined by grade (A→A+ gold, B-→D+ silver, F red) |
| `frame-card` | Drill panel + chart panels | 9-slice |
| `box_plot_mini` per corner row | Throttle panel | 1-frame each |
| `bar_red` / `bar_green` | Brake/accel panel | Heights drive from data |

## Vue component

```vue
<!-- pitwall-web/src/views/CornerMastery.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">CORNER MASTERY · {{ sidShort }}</h1>

    <Frame frame-type="card">
      <CornerMap :corners="cornerData" :focus="cursor" :classification="classification" />
    </Frame>

    <CornerDetailPanel :corner="cursorCorner" />

    <ThrottleBoxPanel :data="throttle" />
    <BrakeAccelPanel :data="brakeAccel" />

    <CornerDetailModal v-if="modalOpen" :corner="cursorCorner" @close="modalOpen = false" />

    <HintBar :hints="['A · DRILL DOWN', '◀▶▲▼ MOVE', 'B · BACK']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/<sid>/corners` | Per-corner aggregates: entry/apex/exit speeds, peak brake, max gLat, corner_time, gold delta, grade |
| `GET /session/<sid>/throttle_corner_box` | Box-plot panel per corner |
| `GET /session/<sid>/corner_classification` | Corner pin colour bands (low/med/high speed) |
| `GET /session/<sid>/brake_acceleration` | Decel zones + corner exit accel data |

If `gold_available` is `false` in `/corners` response, grades show
"--" rather than letter grades; coach mentions: *"No gold standard yet
for comparison."*

## Audio cues

| Event | Sound |
|---|---|
| Cursor moves between corners | `cursor_move` |
| A on a corner | `cursor_select` → modal opens |
| Cursor on a grade-A corner | brief sparkle SFX (subtle, 50 ms) |
| Cursor on a grade-F corner | `error_quiet` (one-shot) |

## Input map

| Input | Action |
|---|---|
| ◀ ▶ | Move corner cursor (T1 ↔ T11) |
| ▲ ▼ | Switch focus zone (track map ↔ throttle panel ↔ brake/accel panel) |
| A | Drill into selected corner |
| B | Back to analysis hub |

## Edge cases

- **Bridge `/corners` endpoint reports `n_passes=0` for some corners** —
  those pins are silhouettes; drill panel: "NO PASSES THIS SESSION"
- **No gold standard available** — grades default to "ungraded";
  recommendations rely on session-internal comparisons
- **Driver did 1 lap only** — box-plots collapse to single dots; box
  visualisation hidden; show single-point scatter instead
- **Single corner pin** if the analytics include a virtual T3a or T8a —
  honor whatever the bridge reports; don't assume exactly 11

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — entry point
- [`17-lap-times-hall.md`](17-lap-times-hall.md) — sibling
- [`20-track-atlas.md`](20-track-atlas.md) — track-map shared design
- [Bridge `/session/<sid>/corners`](../../api.md)
