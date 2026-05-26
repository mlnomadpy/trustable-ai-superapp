# 16 — Analysis Hub

The "data dungeon" entry point. From here the driver picks which
analytics deep-dive to enter. Each tile leads to one of six analytics
screens that wrap the bridge's Phase-6 endpoints into game-shaped
reading rooms.

## Purpose

Verb: **Investigate.** Pick which kind of data tonight: laps, corners,
straights, track, evolution, pedals.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ ANALYSIS HALL                                              │
│                                                            │
│  ╔══════════════════╗  ╔══════════════════════╗            │
│  ║ ▶ LAP TIMES HALL  ║  ║   CORNER MASTERY     ║            │
│  ║   24 LAPS THIS    ║  ║   11 CORNERS         ║            │
│  ║   SEASON          ║  ║   GRADED A-F          ║            │
│  ╚══════════════════╝  ╚══════════════════════╝            │
│                                                            │
│  ╔══════════════════╗  ╔══════════════════════╗            │
│  ║   STRAIGHTS &     ║  ║   TRACK ATLAS        ║            │
│  ║   SPEED           ║  ║   ELEVATION ·         ║            │
│  ║   3 STRAIGHTS     ║  ║   MARKERS · ZONES     ║            │
│  ╚══════════════════╝  ╚══════════════════════╝            │
│                                                            │
│  ╔══════════════════╗  ╔══════════════════════╗            │
│  ║   DRIVER          ║  ║   PEDAL PROFILE      ║            │
│  ║   EVOLUTION       ║  ║   THROTTLE · BRAKE   ║            │
│  ║   47 SESSIONS     ║  ║   COAST · TRAIL      ║            │
│  ╚══════════════════╝  ╚══════════════════════╝            │
│                                                            │
│   SQL CONSOLE         (◆ to open Monaco editor)           │
│                                                            │
│  A · ENTER     B · GARAGE                                  │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Behaviour |
|---|---|
| `loading` | Fetch session list + last session id; tile sub-text fills in |
| `idle` | Cursor on LAP TIMES HALL by default |
| `no-data` | Driver has zero completed sessions: tiles greyed; coach line: *"Drive a lap first."* |

## Tiles

Each tile is a hub for related endpoints:

| Tile | Screen | Endpoints surfaced |
|---|---|---|
| LAP TIMES HALL | `screens/17-lap-times-hall.md` | `lap_time_table`, `lap_time_distribution`, `ideal_lap`, `sector_times` |
| CORNER MASTERY | `screens/18-corner-mastery.md` | `session/<sid>/corners`, `throttle_corner_box`, `corner_classification`, `brake_acceleration` |
| STRAIGHTS & SPEED | `screens/19-straights-and-speed.md` | `straight_line_speed` |
| TRACK ATLAS | `screens/20-track-atlas.md` | `track/<id>/elevation`, `track/markers`, `track/danger_zones`, `track/weather` |
| DRIVER EVOLUTION | `screens/21-driver-evolution.md` | `driver/<id>/evolution`, `driver/<id>/profile` |
| PEDAL PROFILE | `screens/22-pedal-profile.md` | `pedal_behavior` |

## Sprite usage

- Each tile has a small icon sprite top-left (~32×32):
  - LAP TIMES → stopwatch icon
  - CORNER MASTERY → curve icon
  - STRAIGHTS → arrow icon
  - TRACK ATLAS → map icon
  - DRIVER EVOLUTION → growth chart
  - PEDAL PROFILE → foot icon
- Coach (`trod`) idle in the bottom-left corner

## Vue component

`pitwall-web/src/views/AnalysisHub.vue` — same tile-grid pattern as
GarageHub. Each tile dispatches to its respective route.

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /sessions?driver=<name>` | Total session count for the LAP TIMES HALL sub-text |
| `GET /session/<latest-sid>/lap_time_table` | Used to populate "24 laps" / "11 corners" stats |

These are loaded on entry to the hub, not in each individual tile, so
sub-screens have data already cached.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Tile A | `cursor_select` → wipe to detail screen |
| Monaco SQL opens | `cursor_select` (stronger) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ ◀ ▶ | Move cursor between tiles |
| A | Enter selected tile |
| B | Back to garage hub |
| ◆ Start | Open Monaco SQL console (modal over hub) |

## SQL Console (◆ Start)

A power-user surface. Loads DuckDB-Wasm + a Monaco editor pre-populated
with helpful queries:

```sql
-- Last session's laps with sector splits
SELECT lap_number, lap_time_s, s1, s2, s3
FROM session_laps('<latest-sid>')
ORDER BY lap_number;

-- Where I lost time at T7 between best and second-best lap
SELECT distance_m,
       speed_best, speed_2nd,
       (speed_2nd - speed_best) * 3.6 AS delta_kmh
FROM compare_laps('<latest-sid>', best_lap, second_lap)
WHERE distance_m BETWEEN 1620 AND 1820;
```

Closes on Esc or B. Results render as a pixel-styled table.

## Edge cases

- **No completed sessions** — every tile greys out; SQL console
  disabled; coach line directs to TRACK
- **DuckDB-Wasm fails to load** — SQL console hidden; tiles still work
  because they hit the bridge directly

## Related

- [`17-lap-times-hall.md`](17-lap-times-hall.md)
- [`18-corner-mastery.md`](18-corner-mastery.md)
- [`19-straights-and-speed.md`](19-straights-and-speed.md)
- [`20-track-atlas.md`](20-track-atlas.md)
- [`21-driver-evolution.md`](21-driver-evolution.md)
- [`22-pedal-profile.md`](22-pedal-profile.md)
