# 19 — Straights & Speed

The "did I commit?" view. Top speed per named straight, with which lap
got it and a trend arrow vs prior session.

## Purpose

Verb: **Hunt top speed.** Find where momentum lives. Did I keep it?

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ STRAIGHTS & SPEED · session 2026-04-29-1503                │
│                                                            │
│ ╔═ SONOMA WITH 3 NAMED STRAIGHTS HIGHLIGHTED ════════════╗ │
│ ║                                                       ║ │
│ ║  ░░░░░ FRONT STRAIGHT ░░░░░  ▲ 198.4 km/h   LAP 7      ║ │
│ ║   ▲ +2.1 km/h vs session-1                            ║ │
│ ║                                                       ║ │
│ ║  ░░ T4 RUN ░░░  ▲ 138.7 km/h   LAP 12                 ║ │
│ ║   ▼ -1.0 km/h vs session-1  (-cost on T3a exit)       ║ │
│ ║                                                       ║ │
│ ║  ░░ T7 → T8a ░░░  ▲ 187.2 km/h   LAP 11               ║ │
│ ║   = 0 km/h flat                                       ║ │
│ ║                                                       ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│  ◐ T-ROD: "T4 Run dropped 1 km/h — that's T3a exit. Tighten │
│     it. Don't open up."                                    │
│                                                            │
│  A · OPEN REPLAY (lap of selected straight)   B · BACK      │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch `straight_line_speed` for current + most-recent prior session |
| `idle` | Loaded | Cursor on first straight; trend arrows + delta visible |
| `replay-launch` | A pressed | Open `/replay/<sid>?lap=<n>` for the lap that produced the top speed |
| `coach-commentary` | Any straight dropped > 5 km/h vs PB | Coach line auto-suggests cause (corner-exit upstream) |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `track_map_sonoma_straights_highlighted` | Background | Static; 3 straights drawn brighter than rest of track |
| `arrow_up_green` / `arrow_down_red` / `arrow_flat` | Per-straight trend | Static |
| `frame-card` | Per-straight badges | 9-slice |
| Cursor | On focused straight | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/StraightsAndSpeed.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">STRAIGHTS &amp; SPEED · {{ sidShort }}</h1>

    <Frame frame-type="card" class="track-map">
      <Sprite name="track_map_sonoma_straights_highlighted" />
      <StraightBadge v-for="s in straights" :key="s.name"
                     :straight="s"
                     :prev-top="prevSession.straights.find(p => p.name === s.name)?.top_speed_kmh"
                     :focused="cursor === s.name" />
    </Frame>

    <DialogueBox v-if="coachLine"
                 :coach-id="save.preferredCoach"
                 :emotion="lossEmotion"
                 :text="coachLine" />

    <HintBar :hints="['A · OPEN REPLAY', 'B · BACK']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/<sid>/straight_line_speed` | Current session per-straight tops |
| `GET /session/<prev-sid>/straight_line_speed` | Last session for trend deltas |
| `GET /session/<sid>/lap_time_table` | To map `from_lap` → lap timings for the replay link |

The "prev session" is the most recent prior session at the same track
for this driver — pulled from `useSaveStore.slots[active].sessions`.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Cursor move | `cursor_move` |
| Trend arrow up (improvement vs prev) | brief sparkle SFX |
| Trend arrow down > 5 km/h | `error_quiet` (one-shot) |
| New session top speed (any straight set this session ≥ all-time best) | `level_up` |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move cursor between straights |
| A | Open replay at the straight (defaults to t-from = halfway through the straight) |
| B | Back to analysis hub |

## Edge cases

- **Endpoint returns `top_speed_kmh: null`** for a straight (no laps
  reached it) — show "NO DATA"; trend hidden
- **First session ever** — no prev session to compare; trend arrows
  hidden; coach line: "First time on this track — these are your
  baselines."
- **Coach commentary heuristic** — when Front Straight drops > 5 km/h,
  blame T11 exit; T4 Run drops, blame T3a; T7→T8a drops, blame T7
  apex. Lookup table in `pitwall-web/src/data/straight-cause-map.ts`.
- **Driver swapped car between sessions** — trend may be misleading;
  show small ⚠ icon next to the trend
- **Bridge offline** — load from DuckDB-Wasm cache; trend uses cached
  prior

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — entry point
- [`11-replay.md`](11-replay.md) — destination
- [Bridge `/straight_line_speed`](../../api.md#get-sessionsidstraight_line_speed)
- `sonoma.STRAIGHTS` constant — the named-straight definitions
