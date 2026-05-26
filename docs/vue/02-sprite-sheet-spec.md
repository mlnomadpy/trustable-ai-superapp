# 02 — Sprite sheet spec

How sprites are organised, packed, named, and consumed by the Vue PWA.
Plus a row-by-row taxonomy of the user's reference sheet so we know
exactly which frames map to which animations.

## File-system layout

```
pitwall-web/public/sprites/
├── coaches/
│   ├── trod.png                   # packed sheet, 1024 × 1024 max
│   ├── trod.json                  # frame data (TexturePacker JSON)
│   ├── bentley.png + .json
│   ├── drill.png + .json
│   ├── calm.png + .json
│   └── buddy.png + .json
├── drivers/
│   ├── avatars.png                # 8 driver avatars, 4 states each
│   └── avatars.json
├── ui/
│   ├── frames.png                 # 9-slice frames + cursor + arrows
│   ├── frames.json
│   ├── medals.png                 # bronze / silver / gold / platinum / rainbow
│   └── medals.json
├── tracks/
│   ├── sonoma-map.png             # full Sonoma layout for HUD mini-map
│   ├── sonoma-corners.png         # per-corner thumbnails for trainer card
│   ├── sonoma-world-pin.png       # pin sprite for world map
│   └── sonoma-bg.png              # 480×320 paddock backdrop
└── effects/
    ├── wipes.png                  # screen-transition strips
    ├── confetti.png               # stage-clear particles
    └── dust.png                   # tire-smoke / brake-dust particles
```

Total target footprint: **< 800 KB** for the entire sprite library
after PNG optimisation (oxipng / pngcrush). Service-worker caches the
whole pack on first load; subsequent navigations are instant.

## Frame size conventions

| Asset | Native size | Used for |
|---|---|---|
| Coach portrait | 96 × 96 | Coach select cards, trainer card mentor slot |
| Coach mini portrait | 32 × 32 | Status bar coach badge |
| Coach full body | 64 × 96 | Walking around the garage hub |
| Coach action frame | 64 × 64 | Push-ups, kicks, fist pumps in stage-clear scenes |
| Driver avatar | 64 × 64 | Onboarding picker, trainer card avatar slot |
| Driver helmet-on | 32 × 32 | HUD top-status |
| Medal | 32 × 32 | Medal grid, achievement toast |
| Track pin | 24 × 24 | World map tile |
| Cursor arrow | 16 × 16 | Menu cursor |
| HUD icon | 16 × 16 | Brake/throttle/corner glyphs |

Anything smaller than 16×16 is unreadable; anything bigger than 128×128
breaks the visual scale of the rest of the UI.

## Packing rules

Use [TexturePacker](https://www.codeandweb.com/texturepacker) or
[free-tex-packer](https://free-tex-packer.com/). Settings:

```
Algorithm:    MaxRects (Best Short Side Fit)
Trim:         enabled, alpha threshold 1
Padding:      2 px (so neighbouring frames don't bleed at non-integer
              scales; we never use non-integer scales but it's cheap
              insurance)
Format:       PNG-32
Data format:  JSON (Hash) — keys are frame ids
Power of 2:   enabled (helps GPU upload on lower-end devices)
```

## JSON frame schema

Each `.json` file is `{ "frames": { ... }, "meta": { ... } }`. We add a
custom `animations` block that the Vue `Sprite` component consumes
directly — TexturePacker doesn't write this; we add it by hand or via
a small post-processor script:

```jsonc
// trod.json
{
  "frames": {
    "trod_idle_0": {
      "frame": { "x": 0, "y": 0, "w": 64, "h": 96 },
      "rotated": false, "trimmed": true,
      "spriteSourceSize": { "x": 0, "y": 0, "w": 64, "h": 96 },
      "sourceSize": { "w": 64, "h": 96 }
    },
    "trod_idle_1": { /* ... */ },
    "trod_walk_0": { /* ... */ },
    /* ... */
  },
  "animations": {
    "idle":     { "frames": ["trod_idle_0", "trod_idle_1"], "fps": 1.5, "loop": true },
    "walk":     { "frames": ["trod_walk_0", "trod_walk_1", "trod_walk_2", "trod_walk_3"], "fps": 6, "loop": true },
    "run":      { "frames": ["trod_run_0", "trod_run_1", "trod_run_2", "trod_run_3"],     "fps": 8, "loop": true },
    "talk":     { "frames": ["trod_talk_0", "trod_talk_1"], "fps": 6, "loop": true },
    "pushup":   { "frames": ["trod_pushup_down", "trod_pushup_up"], "fps": 4, "loop": true },
    "victory":  { "frames": ["trod_victory_0", "trod_victory_1"], "fps": 4, "loop": false },
    "thumbsup": { "frames": ["trod_thumbsup"], "fps": 1, "loop": false },
    "sleep":    { "frames": ["trod_sleep_0", "trod_sleep_1", "trod_sleep_2"], "fps": 1, "loop": true },
    /* ... */
  },
  "meta": {
    "image": "trod.png",
    "size": { "w": 1024, "h": 1024 },
    "scale": "1"
  }
}
```

## Reference sheet → frame inventory mapping

The user provided a single 13×13 reference sheet
([`assets/reference-sheet-source.md`](assets/reference-sheet-source.md))
showing T-Rod across ~169 frames. Each cell appears to be ~64×64 with
2-px gutters. We extract individual frames and rename them per the
schema below.

The sheet's row-by-row content (left→right, top→bottom):

| Row | Frames in this row | Animation labels |
|---|---|---|
| 1 (idle / stand) | 13 frames showing arm positions: hands at sides, on hips, raised, pointing | `trod_idle_0`, `trod_idle_1`, `trod_pose_handsonhips`, `trod_pose_arms_raised`, `trod_point_left`, `trod_point_right`, … |
| 2 (walking + running) | walk-right cycle (4) + walk-left cycle (4) + run-right cycle (4) | `trod_walk_r_0..3`, `trod_walk_l_0..3`, `trod_run_r_0..3` |
| 3 (climbing ladder) | crouch + ladder ascend cycle (4 frames repeated for shading variants) | `trod_crouch`, `trod_climb_0..3`, `trod_top_of_ladder` |
| 4 (engine mechanic) | engine tinker + standing-with-wrench + pointing | `trod_engine_lean`, `trod_engine_tinker_0..1`, `trod_wrench_pose`, `trod_wrench_point` |
| 5 (tools + posing) | wrench + gauge + cross-armed + pointing variations | `trod_holding_wrench`, `trod_holding_gauge`, `trod_arms_crossed`, `trod_point_l_emphatic`, `trod_point_r_emphatic`, `trod_camera_hold`, `trod_camera_shoot`, `trod_kneel_0..1`, `trod_meditate`, `trod_book_open` |
| 6 (camera + tablet work) | camera + tablet variants + pointing-while-tablet | `trod_camera_eye`, `trod_camera_review`, `trod_tablet_hold`, `trod_tablet_point`, `trod_tablet_thumbs_up`, `trod_tablet_two_handed`, `trod_clipboard_review` |
| 7 (engineering / data) | wrench + gauge + clipboard variants | `trod_gauge_review`, `trod_clipboard_check_0..3`, `trod_signal_pose`, `trod_clipboard_writing` |
| 8 (concept / thumbs up) | engine-icon + thumbs-up variants + tablet pose with notes | `trod_concept_engine`, `trod_thumbs_up`, `trod_inspect_0..3`, `trod_clipboard_notes`, `trod_tablet_writing` |
| 9 (fuel + comms + push-ups) | fuel-cell icon + walkie-talkie + tablet variants + push-up cycle | `trod_fuel_alert`, `trod_walkie_talk`, `trod_tablet_show_0..2`, `trod_pushup_down`, `trod_pushup_up`, `trod_kneel_serious`, `trod_pray_pose` |
| 10 (combat / fitness) | kicking + martial poses + champion-fist variants | `trod_kick_0..3`, `trod_fight_stance_0..2`, `trod_fist_pump_0..1`, `trod_kneel_satisfied` |
| 11 (victory + medal + trophy) | both-arms-up celebration + medal-around-neck + holding-trophy variants | `trod_victory_arms_up`, `trod_medal_proud_0..3`, `trod_trophy_hold_0..1`, `trod_post_win_relax` |
| 12 (relaxation / phone / reading) | sitting / phone / reading book variants | `trod_phone_check_0..2`, `trod_book_read_0..2`, `trod_resting_pose`, `trod_phone_show_0..1`, `trod_book_close` |
| 13 (downtime / sleep) | coffee-mug + bed + sleeping + computer-night-shift + stargazing | `trod_coffee_mug`, `trod_bed_lie`, `trod_sleep_curl`, `trod_sleep_z`, `trod_smug_pose`, `trod_office_panel_0..1`, `trod_stargazing_0..1`, `trod_sleep_z_outdoor` |

(Exact cell coordinates extracted via the post-processor script; this
table is the human-readable contract. The post-processor reads the
sheet, slices on the 64×64 grid, and emits the JSON.)

## Per-coach animation requirements

Every coach has the same minimum animation set:

| Animation | Frames | Required for |
|---|---|---|
| `idle` | 2 | Coach select, garage hub, dialogue box default |
| `walk` | 4 | Garage hub idle wandering |
| `talk` | 2 | Dialogue box during teletype |
| `thumbsup` | 1 | Stage clear "great session" reaction |
| `disappointed` | 1 (or 2) | Stage clear "missed goals" reaction |
| `victory` | 2 | Personal best unlock |
| `pushup` | 2 | Easter egg in garage hub |

**T-Rod gets the full 169-frame inventory** because he's the default
coach and his sprite sheet is what we have. The other four coaches
(Bentley, Drill Sergeant, Calm Pro, Buddy) launch with the **minimum
7-animation set** = ~14 frames each = ~56 frames across four coaches.

## Driver avatar requirements

Eight base avatars, each with four animation states:

| Animation | Frames | Use |
|---|---|---|
| `idle` | 2 | Trainer card portrait |
| `helmet_on` | 1 | HUD top-status |
| `victory` | 1 | Stage clear PB unlock |
| `disappointed` | 1 | Stage clear all-goals-missed |

= 5 frames × 8 avatars = 40 driver frames total.

## Effect sprites

| Sprite | Frames | Use |
|---|---|---|
| Wipe transition | 4 | Screen change (one shared sprite, 480×320) |
| Confetti burst | 8 | Stage clear medal award |
| Dust puff | 4 | World-map cursor movement, garage walks |
| Spark / flash | 2 | Achievement unlock |
| Z (sleep marker) | 3 | Sleeping coach idle |
| Speech-bubble exclamation | 2 | "!" over a corner that cost time |

## Generating the rest with nano-banana

The user has T-Rod. We need:

- 4 other coaches × ~14 frames each = 56 frames
- 8 driver avatars × 5 frames each = 40 frames
- Effect sprites and UI elements

For each, run a nano-banana prompt against a consistency anchor (the
T-Rod base style). Full prompt cookbook in
[`assets/reference-sheet-source.md`](assets/reference-sheet-source.md).
Each character should match T-Rod's:

- 64 × 96 bounding box for full-body
- 1-px black outline (`#0d0d12`)
- 30+ shade palette derived from `01-visual-language.md`
- 3/4 perspective from waist up; full side view for walks; full front
  for portraits

## Vue consumption pattern

The `Sprite` component is the single point of contact for every sprite
in the app:

```vue
<!-- pitwall-web/src/components/Sprite.vue -->
<template>
  <div
    :class="['sprite', `sprite-${name}`, `sprite-${animation}`]"
    :style="style"
    @animationend="onAnimEnd"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSpriteStore } from '@/stores/sprites'

interface Props {
  sheet:     'trod' | 'bentley' | 'drill' | 'calm' | 'buddy' | 'avatars' | 'medals' | …
  animation: string                         // key into sheet.animations
  scale?:    number                         // default: viewport scale
  paused?:   boolean
}
const props = withDefaults(defineProps<Props>(), { scale: 1, paused: false })
const store = useSpriteStore()

const style = computed(() => store.cssFor(props.sheet, props.animation, {
  scale: props.scale, paused: props.paused,
}))
</script>

<style scoped>
.sprite {
  image-rendering: pixelated;
  background-repeat: no-repeat;
  /* width/height/animation set inline via store.cssFor() */
}
</style>
```

The sprite store loads the `.json` files lazily, computes a CSS string
per (sheet, animation) tuple including `background-image`, `width`,
`height`, and a CSS `animation` keyframe stepping through the frames at
the declared FPS.

## Pre-launch checklist

Before any sprite ships:

- [ ] PNG width and height are powers of 2
- [ ] All frames have 2 px padding
- [ ] No frame is larger than 128 × 128
- [ ] Total sheet size < 1024 × 1024
- [ ] Optimised with `oxipng -o 4`
- [ ] Has a paired `.json` with at least the seven core animations
- [ ] Loaded by the `Sprite` component without console errors
- [ ] Renders correctly at 1×, 2×, 4×, 6× scales
- [ ] Background pixels removed (alpha = 0, not the placeholder red)

## Related

- [`01-visual-language.md`](01-visual-language.md) — palette and frame
  system this taxonomy expresses
- [`03-character-bible.md`](03-character-bible.md) — what each coach
  looks and sounds like
- [`08-animation-spec.md`](08-animation-spec.md) — frame timing and
  transitions
- [`assets/reference-sheet-source.md`](assets/reference-sheet-source.md)
  — the canonical source of the T-Rod frame data
