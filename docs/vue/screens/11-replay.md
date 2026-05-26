# 11 — Replay

The "watch what I just did" screen. Video × telemetry side-by-side
with a shared scrubber. Per-lap selection. Coach annotations dotted
along the timeline.

> **Status:** design only. Video sync (the bridge byte-range MP4
> serving + simulator `--video` flag) is the deferred follow-up to
> [ADR-016](../../adr/016-can-bus-ingest-and-frontend-pivot.md). This
> screen documents the design; implementation lands when the video
> path lands.

## Purpose

Verb: **Re-live.** Watch a lap with telemetry overlaid. Scrub anywhere
in either to seek both. Coach lines from that lap appear with timestamps.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ REPLAY · LAP  ◀ 3 ▶ · 1:46.8 PB                            │
│                                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │ ╔════════════════════════════════════════════════╗ │    │
│  │ ║                                                ║ │    │
│  │ ║         VIDEO  PANEL                           ║ │    │
│  │ ║         <video src="/video/...">              ║ │    │
│  │ ║         480 × 270 (pixel-art frame)            ║ │    │
│  │ ║                                                ║ │    │
│  │ ╚════════════════════════════════════════════════╝ │    │
│  └────────────────────────────────────────────────────┘    │
│                                                            │
│ ─── SPEED ───                                              │
│  ▲     ╱╲                                                  │
│  │    ╱  ╲     ╱╲                                          │
│  │   ╱    ╲   ╱  ╲   ▼ scrubber (drives video.currentTime)│
│  │__/______╲_/____╲___________________________________     │
│                                                            │
│ ─── BRAKE ───                                              │
│ ─── G-LAT ───                                              │
│                                                            │
│ ─── COACH NOTES ───                                        │
│   T1 · 0:08 · "carry throttle through"                     │
│   T7 · 0:42 · "you braked 15m early"                       │
│   T11 · 1:38 · "wait for the bump"                         │
│                                                            │
│  A · PLAY/PAUSE   ◀▶ SCRUB   ◆ SQL    B · BACK             │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading-laps` | Mount | Fetch `lap_time_table` to populate selector |
| `loading-data` | Lap selected | Fetch `sync` for the lap window + lap's coaching notes |
| `paused` | Default | Video paused at start of lap; scrubber at 0 |
| `playing` | A pressed | Video plays at 1× rate; charts cursor + scrubber move in sync |
| `scrubbing` | ◀▶ held / dragged | Video seeks; charts snap |
| `sql` | ◆ Start | Monaco modal opens with DuckDB-Wasm + this lap's frames |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `frame-card` | Video frame | 9-slice with thicker outline |
| `scrubber_handle` | Below charts | 1-frame; tracks pointer |
| `note_pin` | Coach notes timeline | Static dots on the timeline |
| Cursor | Hidden — interaction is timeline drag |

## Vue component

```vue
<!-- pitwall-web/src/views/Replay.vue -->
<template>
  <div class="viewport replay">
    <StatusBar />
    <h1 class="font-title text-title">
      REPLAY · LAP <LapPicker v-model="lapNumber" :max="lapCount" /> · {{ lapTimeStr }}
    </h1>

    <Frame frame-type="card" class="video-frame">
      <video ref="videoEl"
             :src="videoUrl"
             @timeupdate="onVideoTime"
             playsinline />
    </Frame>

    <PixelChart series="speed" :data="syncData" :cursor-t="cursorT" />
    <PixelChart series="brake" :data="syncData" :cursor-t="cursorT" />
    <PixelChart series="g_lat" :data="syncData" :cursor-t="cursorT" />

    <Scrubber v-model="cursorT" :t-from="lap.t_start" :t-to="lap.t_end" />

    <CoachNoteList :notes="coachNotes" :cursor-t="cursorT" @jump="seek" />

    <SqlModal v-if="sqlOpen" :sid="sid" :lap="lapNumber" @close="sqlOpen = false" />

    <HintBar :hints="['A · PLAY/PAUSE', '◀▶ SCRUB', '◆ SQL', 'B · BACK']" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
const videoEl  = ref<HTMLVideoElement | null>(null)
const cursorT  = ref(0)
const videoUrl = computed(() =>
  `/video/${encodeURIComponent(syncData.value?.[0]?.file_path ?? '')}`)

function onVideoTime() {
  if (videoEl.value) cursorT.value = videoEl.value.currentTime + lap.value.t_start
}
function seek(t: number) {
  cursorT.value = t
  if (videoEl.value) videoEl.value.currentTime = t - lap.value.t_start
}
</script>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| `GET /session/<sid>/lap_time_table` | Mount; populates the lap picker |
| `GET /session/<sid>/sync?t_from=&t_to=&names=speed_ms,brake_bar,g_lat` | On lap change; joined telemetry rows for the lap |
| `GET /video/<relpath>` | On lap change; HTML5 `<video>` fetches with byte-range (deferred bridge work) |
| `GET /session/<sid>/clips` | On mount; surface highlight cuts in the lap picker |

The `coachNotes` come from `coaching_notes` joined into `/sync`'s
response; the bridge bundles them when `?include_notes=true`.

## Audio cues

| Event | Sound |
|---|---|
| Mount | quiet; no music swap |
| Lap picker change | `cursor_select` |
| Note pin tap | `cursor_move` + (post-MVP) play the cached coach phrase audio |
| Play/pause | `cursor_select` |

The video has its own audio track (engine sound + dashcam ambient);
plays at 100 %; music ducks while video plays.

## Input map

| Input | Action |
|---|---|
| ◀ ▶ | Move scrubber in 1 % increments (or change lap when picker focused) |
| ▲ ▼ | Move focus between widget zones |
| A | Play / Pause |
| ◆ Start | Open SQL modal |
| B | Back to garage hub or to Stage Clear (depends on entry) |

## Edge cases

- **No video file present** for this session — video panel shows "NO
  VIDEO RECORDED FOR THIS SESSION"; charts and notes still work fine
- **Bridge byte-range MP4 not yet shipped** — video panel shows "VIDEO
  PATH PENDING"; replay still informative via charts
- **Lap selector has only 1 lap** — picker disabled; arrow keys are
  no-op
- **Scrubber dragged outside lap window** — clamps to bounds
- **Video aspect ratio doesn't match the pixel-art frame** — `object-fit:
  contain`; pixel-art frame stays the right size
- **Multiple notes within < 200 ms** — pins overlap visually; tooltip on
  any one shows all collided notes

## Related

- [ADR-016](../../adr/016-can-bus-ingest-and-frontend-pivot.md) — video
  sync deferral
- [`10-stage-clear.md`](10-stage-clear.md) — entry on "WATCH BEST LAP"
  (post-MVP)
- [`16-analysis-hub.md`](16-analysis-hub.md) — alt entry point
- [`17-lap-times-hall.md`](17-lap-times-hall.md) — tap-row → here
- [Bridge `/session/<sid>/sync`](../../api.md)
