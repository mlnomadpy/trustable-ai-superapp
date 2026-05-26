# 20 — Track Atlas

The "study the track" screen. One Sonoma map, four overlay toggles:
elevation, markers, danger zones, weather. Tap a marker → coach
delivers track lore.

## Purpose

Verb: **Study the track.** Build mental map of the place. The screen
that matters most for a first-time-at-Sonoma driver.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ TRACK ATLAS · SONOMA RACEWAY                               │
│                                                            │
│ ☑ ELEVATION   ☑ MARKERS   ☑ DANGER ZONES                  │
│ ░ WEATHER: peak grip · DRY · 21 °C                          │
│                                                            │
│ ╔═══════════════════════════════════════════════════════╗ │
│ ║                                                       ║ │
│ ║   ░░░░░ Sonoma 11-corner layout ░░░░░░                ║ │
│ ║   colour-coded by elevation                            ║ │
│ ║   ◯ marker pins (16 total)                             ║ │
│ ║   ▒ danger-zone shading (3 zones)                      ║ │
│ ║                                                       ║ │
│ ║   ▶ Selected: "the K-wall bend" (T1 apex)             ║ │
│ ║                                                       ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ╔═ ELEVATION CHART (toggle to show) ══════════════════════╗│
│ ║ ▲                                                      ║│
│ ║ │   ╱╲                              ╱╲                ║│
│ ║ │  ╱  ╲___        ___              ╱  ╲                ║│
│ ║ │_/      ╲_______/   ╲____________╱    ╲___           ║│
│ ║         start                               finish     ║│
│ ╚═══════════════════════════════════════════════════════╝│
│                                                            │
│  ◐ T-ROD: "Apex tight at the K-wall — bumpy on entry."     │
│                                                            │
│  A · TAP MARKER     ◀▶▲▼ MOVE     B · BACK                 │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch elevation + markers + danger-zones + weather |
| `idle` | Loaded | All overlays toggled on; cursor on T1's K-wall marker |
| `marker-detail` | A on a marker | Coach delivers the marker's `transcript_line` per `markers.json` |
| `danger-detail` | A on a danger zone | Coach delivers safety reminder |
| `chart-on` | "ELEVATION CHART" tab | Side panel with pixel-line graph (distance_m on x, altitude_m on y) |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `track_map_sonoma_elevation` | Background | Static; pixels coloured by `altitude_m` from light=high to dark=low |
| `marker_pin` | 16 marker positions | Static; bouncing on cursor focus |
| `danger_zone_overlay` | 3 danger zones | Semi-translucent red shading |
| `frame-card` | Elevation chart side panel | 9-slice |
| Cursor | On focused marker / danger zone | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/TrackAtlas.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">TRACK ATLAS · SONOMA RACEWAY</h1>

    <ToggleStrip v-model:elevation="showElevation"
                 v-model:markers="showMarkers"
                 v-model:danger="showDanger" />

    <WeatherBadge :weather="weather" />

    <Frame frame-type="card" class="map-frame">
      <SonomaMap
        :show-elevation="showElevation"
        :show-markers="showMarkers"
        :show-danger="showDanger"
        :elevation="elevation.samples"
        :markers="markers"
        :danger-zones="dangerZones"
        :focus="cursor"
        @select="openDetail" />
    </Frame>

    <ElevationChart v-if="chartTab" :data="elevation.samples" />

    <DialogueBox v-if="detailText"
                 :coach-id="save.preferredCoach"
                 :emotion="detailEmotion"
                 :text="detailText"
                 @done="detailText = null" />

    <HintBar :hints="['A · TAP MARKER', '◀▶▲▼ MOVE', 'B · BACK']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /track/sonoma/elevation?step_m=20` | Elevation profile + min/max altitude → background colour-coding |
| `GET /track/markers` | 16 named marker pins with positions + transcript lines |
| `GET /track/danger_zones` | 3 zones with severity + descriptions |
| `GET /track/weather?hour_local=<h>` | Current phase indicator |

All four are cached at app boot; this screen consumes them without
re-fetching unless the player presses `◆ Start` to refresh.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Cursor moves to a marker | `cursor_move` |
| A on a marker | `cursor_select` + (post-MVP) per-marker pre-rendered T-Rod voice clip |
| A on a danger zone | `error_quiet` (subdued; it's not a fail, just a reminder) |
| Toggle flip | `cursor_select` |

## Input map

| Input | Action |
|---|---|
| ◀ ▶ ▲ ▼ | Move cursor between markers / danger zones (snap to nearest in direction of press) |
| A | Show selected marker's coach line |
| B | Back to analysis hub |
| ◆ Start | Refresh data from bridge |
| `1` `2` `3` (dev shortcut) | Toggle individual overlays |

## Edge cases

- **Track JSON has no elevation profile** (`elevation_source: "missing"`) —
  ELEVATION toggle disabled with tooltip "no elevation data for this track"
- **Player visits before completing first session** — screen still
  loads (data is track-static, not session-bound); coach line:
  *"Memorise this. You'll thank me later."*
- **Danger zone overlap with marker** — marker takes priority on
  cursor-snap; danger zone selected via dedicated tab
- **Bridge offline** — fully cached; works offline once loaded once

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — entry point
- [`06-world-map.md`](06-world-map.md) — sibling (cross-track view)
- [`07-pre-brief.md`](07-pre-brief.md) — refers to markers + danger zones
- [ADR-011 — Named-marker schema](../../adr/011-named-marker-schema.md)
- [Bridge `/track/<id>/elevation`](../../api.md#get-trackidelevation)
- [`03-character-bible.md`](../03-character-bible.md) — T-Rod's transcript anchors
