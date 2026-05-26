# 37 — Track Walk

Interactive Sonoma layout, full-screen. Coach standing nearby. All
markers from `data/tracks/sonoma.json` rendered as pins. Tap a corner
to get coached on it; tap a marker to read the lore; review your own
historical performance per corner inline.

The pre-brief moment that *feels like a Pokémon town map*.

## Purpose

Verb: **Walk the track.** Before the driver pulls out, let them
explore Sonoma corner by corner — read the marker tips, hear coach
commentary, see their best vs gold-standard apex speeds — without
ever leaving the paddock.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ TRACK WALK · SONOMA RACEWAY                                │
│                                                            │
│   ░░░░░░░░░░ HILLS BACKGROUND ░░░░░░░░░░░                   │
│  ░░                                          ░░             │
│  ░░       ╭─T1──T2─╮                        ░░              │
│  ░░    T11   ▶     T3                       ░░              │
│  ░░      ╲           ╲                      ░░              │
│  ░░       T10        T4                     ░░              │
│  ░░         ╲       ╱  ╲                    ░░              │
│  ░░          T9    T5  T6 ◀ The Carousel    ░░              │
│  ░░           ╲    │   ╱                    ░░              │
│  ░░            T8─T7                        ░░              │
│  ░░              ▲ "the bridge" (T2 brake)  ░░              │
│  ░░                                          ░░             │
│   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              │
│                                                            │
│  ┌──────┐                                                  │
│  │T-ROD │  "Tap any corner to walk through it.             │
│  │relaxd│   Tap a marker for the story."                    │
│  └──────┘                                                  │
│                                                            │
│ A · ENTER CORNER     B · BACK     ◆ TOGGLE LAYERS          │
└────────────────────────────────────────────────────────────┘
```

## Sub-screen — Corner detail (A on a Turn pin)

```
┌────────────────────────────────────────────────────────────┐
│ T7 · "the 300 board"                                       │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│   ╔══════════════════════════════════════════════════════╗ │
│   ║          ░░░░░ T7 entry-apex-exit zoom ░░░░           ║ │
│   ║                                                       ║ │
│   ║         ░░░░░░░░░░ markers visible: ░░░░               ║ │
│   ║          • the 300 board (brake)                      ║ │
│   ║          • the kerb on the inside (apex)              ║ │
│   ║                                                       ║ │
│   ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│  COACH SAYS                                                │
│  ┌──────┐                                                  │
│  │T-ROD │  "Eyes up — late turn-in, late apex; second     │
│  │intens│   apex matters more."                            │
│  └──────┘                                                  │
│                                                            │
│  YOUR BEST AT T7                                           │
│  ╔══════════════════════════════════════════════════════╗  │
│  ║ ENTRY    96 km/h    ─── gold 102 km/h    ▼ -6         ║  │
│  ║ APEX     78 km/h    ─── gold  85 km/h    ▼ -7         ║  │
│  ║ EXIT     94 km/h    ─── gold  98 km/h    ▼ -4         ║  │
│  ║ BRAKE   34 bar      ─── gold  31 bar     ▲ +3          ║  │
│  ║ TIME    4.6 s       ─── gold  4.0 s      ▼ -0.6        ║  │
│  ║                                                       ║  │
│  ║ GRADE   C+   (was D last week — improving!)           ║  │
│  ╚══════════════════════════════════════════════════════╝  │
│                                                            │
│ A · MAKE THIS A SESSION GOAL    B · BACK    ◆ REPLAY      │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch `/track/markers`, `/track/danger_zones`, `/track/sonoma/elevation`, `/session/<latest>/corners`; coach `analyzing` |
| `idle` | Loaded | Cursor on T1 by default; coach `relaxed` walks across the bottom band |
| `corner-detail` | A on a Turn pin | Slide-up sub-modal with the per-corner card |
| `marker-detail` | A on a non-corner marker (e.g. "the bridge") | Coach speaks marker lore (pre-rendered TTS) via `_coach-speaks-modal.md` |
| `layers-menu` | ◆ pressed | Toggle layers: corners only / + markers / + danger zones / + elevation heatmap / + your-best-line trace |

## Layers

The `◆ TOGGLE LAYERS` menu — pixel-art legend toggles the visual layers
on the track:

| Layer | Source | Default |
|---|---|---|
| Corner pins (T1-T11) | hardcoded | always on |
| Named markers (16 of them) | `GET /track/markers` | on |
| Danger zones (3 colored regions) | `GET /track/danger_zones` | off |
| Elevation heatmap | `GET /track/sonoma/elevation` | off |
| Your best line (most recent session) | `GET /session/<sid>/sync` (last best lap, gps lat/lon) | on if available |
| Gold standard line | `data/reference/sonoma_gold_trace.json` | off |

Active layers persist per save slot.

## Per-corner card content

Each card pulls from:

| Field | Source |
|---|---|
| Corner name | `data/tracks/sonoma.json` corners[].name |
| Nickname (e.g. "the Carousel") | `sonoma.py:CORNER_TIPS` keys |
| Markers visible | `track/markers` filtered by corner |
| Coach commentary | `sonoma.py:CORNER_TIPS[corner]` (T-Rod's line) |
| Your best entry/apex/exit speed | `GET /session/<sid>/corners` for the latest session |
| Gold standard | `data/reference/sonoma_gold.json` for that corner |
| Delta (▼/▲) | computed |
| Grade (A-F) | from `sonoma_gold` comparison |
| Trend | comparison to last week's session |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `bg_sonoma_track_topdown` | Background | Static |
| `corner_pin_active` 2-frame | Each Turn 1-11 | Pulses at 1 Hz; brighter when focused |
| `marker_pin_*` (per kind: brake, apex, reference, etc.) | Per marker | Static |
| `danger_zone_overlay` | Per zone | Static red translucent shape (only when layer active) |
| `elevation_heatmap` | Full track | Static (only when layer active) |
| `best_line_trace` | Driver's last best lap | 1-pixel pixel-art line |
| `gold_line_trace` | Gold standard | 1-pixel pixel-art line, dashed |
| Coach (`save.preferredCoach`) | Bottom band, 64×96 | Walks across at `walk_l` 4-frame; emotion `relaxed` (idle) → `intense` (per-corner zoom) |

The corner pin uses **emotion-coded coloring**:
- Green: graded A or B vs gold
- Amber: graded C
- Red: graded D or F
- Grey: never driven yet (no data)

So the player can scan the whole track and see "the corners I'm
weakest at are red." Per `../10-coach-emotions.md`, this is the
visual hook for the coach's `concerned` reaction in the corner card
when the grade is poor.

## Vue component

```vue
<!-- pitwall-web/src/views/TrackWalk.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">TRACK WALK · SONOMA RACEWAY</h1>

    <TrackCanvas
      :track-id="'sonoma'"
      :layers="activeLayers"
      :focus="cursor"
      @select="onSelect"
    />

    <CoachIdleBand
      :coach-id="save.preferredCoach"
      emotion="relaxed"
      :greeting="randomTrackWalkGreeting"
    />

    <CornerDetailCard
      v-if="selectedCorner"
      :corner-id="selectedCorner.id"
      :coach-id="save.preferredCoach"
      :data="cornerData"
      @add-as-goal="addCornerToGoals"
      @open-replay="openReplay"
      @close="selectedCorner = null"
    />

    <LayersMenu v-if="layersOpen" v-model="activeLayers" @close="layersOpen=false" />

    <HintBar :hints="hints" />
  </div>
</template>

<script setup lang="ts">
import { useTrackData } from '@/lib/track'
import { useSessionsStore } from '@/stores/session'

const { markers, dangerZones, elevation, latestSessionCorners, gold } = useTrackData('sonoma')
// …
</script>
```

The `TrackCanvas` component renders the track sprite + overlays
declaratively from the active layer set. Cursor is a bouncing arrow
that snaps between corner pins (D-pad) and free-cursors over markers
when the player presses ◀▶ within a corner zone.

## Endpoints consumed

| Endpoint | When | Use |
|---|---|---|
| `GET /track/markers` | Mount | All Sonoma markers |
| `GET /track/danger_zones` | Mount | 3 danger regions |
| `GET /track/sonoma/elevation?step_m=20` | First time elevation layer is toggled | Color-graded heatmap data |
| `GET /session/<latest-sid>/corners` | Mount | Per-corner aggregates (entry/apex/exit speeds, peak brake, grade) |
| `GET /session/<latest-sid>/sync?names=lat,lon&t_from=<best-lap-start>&t_to=<best-lap-end>` | When best-line layer toggled | The driver's best-lap GPS trace |
| `GET /session/<sid>/lap_time_table` | Once for "your best" sub-card | To find which lap was the best |

All cached in `useDuckDBStore` for offline review.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `worldmap_loop` continues from `06-world-map.md` |
| Cursor hop between pins | `cursor_move` |
| A on corner | `cursor_select` → slide-up corner card |
| A on marker | `cursor_select` → coach voice clip plays the marker lore |
| Coach speaks on marker | pre-rendered TTS `coaches/<id>/marker_<id>.mp3` |
| `MAKE THIS A SESSION GOAL` confirmed | `goal_complete` |
| `OPEN REPLAY` | `cursor_select` → wipe to replay focused on that corner |
| Layer toggled | `cursor_select` (softer) |

## Input map

### Top-level (track view)

| Input | Action |
|---|---|
| ◀ ▶ | Move cursor between adjacent corner pins (T1↔T2, T2↔T3, etc.) |
| ▲ ▼ | Move between corner pins and the closest marker pins |
| A | Open corner detail (if on a Turn) or marker lore (if on a marker) |
| B | Back — to pre-brief if entered from there, garage hub otherwise |
| Start | Pause menu |
| ◆ | Open layers menu |

### Corner detail card

| Input | Action |
|---|---|
| A | Add this corner to session goals (toast: "Goal added — work on T7 entry") |
| B | Close card; return to track view |
| ◆ | Open replay focused on this corner's distance window |

## Where it's reached from

Two entry points:

1. **From Pre-Brief (`07-pre-brief.md`)** — new "WALK THE TRACK" button.
   Driver enters this screen, explores, returns to pre-brief with
   any added goals already populated.
2. **From Track Atlas (`20-track-atlas.md`)** — same screen, but with
   the analytics/elevation layers more prominent (it's the same view;
   just different layer defaults).
3. **From World Map (`06-world-map.md`)** — "STUDY TRACK" sub-button
   on the Sonoma pin info card. Read-only mode (no goal-adding,
   purely informational).

## Edge cases

- **No completed sessions yet** — corner pins are all grey; cards show
  "no historical data yet — let's go drive" with coach `encouraging`
- **Bridge offline** — markers + corner names work from cached track
  JSON; "your best at T7" data falls back to the most recent
  OPFS-cached parquet
- **Tapped marker has no associated TTS clip yet** — coach speaks via
  Web Speech API fallback
- **Corner without gold-standard data** — grade shows as "—"; deltas
  are vs your own session-best, not gold

## Why this screen earns its keep

- **Pre-brief depth** — the original pre-brief was just goal-setting +
  weather. This adds the *exploration* the driver does naturally
  before pulling out (looking at the map, mentally walking the lap).
- **Per-corner coach moments** — every corner has T-Rod's tip from
  `sonoma.py:CORNER_TIPS`. Surfacing them here means the player
  hears them deliberately, not just mid-corner under pressure.
- **Concrete progress visualisation** — "the corner I'm weakest at"
  is a single tap, color-coded. Maps to action ("MAKE THIS A SESSION
  GOAL").
- **Track lore** — the marker schema (ADR-011) finally has a screen
  where the lore matters. *"the bridge"* isn't just a coaching anchor
  — it's a place the player can visit and read about.

## Related

- [`07-pre-brief.md`](07-pre-brief.md) — primary entry point; offers
  WALK THE TRACK button; goals added here propagate back
- [`20-track-atlas.md`](20-track-atlas.md) — alternative entry; same
  view with analytics-heavy default layers
- [`06-world-map.md`](06-world-map.md) — STUDY TRACK button enters
  read-only mode
- [`18-corner-mastery.md`](18-corner-mastery.md) — deeper corner
  analytics (this screen surfaces the headline numbers; corner-mastery
  has the full breakdown)
- [`11-replay.md`](11-replay.md) — destination on ◆ REPLAY
- [`../adr/011-named-marker-schema.md`](../../adr/011-named-marker-schema.md) — marker schema
- [`../03-character-bible.md`](../03-character-bible.md) — coach
  commentary voice
- [`../10-coach-emotions.md`](../10-coach-emotions.md) — emotion-coded
  corner pin coloring
