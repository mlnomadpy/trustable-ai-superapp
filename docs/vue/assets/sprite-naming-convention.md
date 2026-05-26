# Sprite naming convention

How files, frame keys, and animation names are spelled. Strict, because
the `Sprite.vue` component computes paths from these names.

## File names

```
pitwall-web/public/sprites/
└── <category>/
    └── <slug>.png + <slug>.json
```

| Category | Slug examples |
|---|---|
| `coaches/` | `trod`, `bentley`, `drill`, `calm`, `buddy` |
| `drivers/` | `avatars` (one packed sheet for all 8) |
| `ui/` | `frames`, `cursor`, `medals`, `loading_dots`, `usb_can_animation` |
| `tracks/` | `sonoma-map`, `sonoma-corners`, `sonoma-bg` |
| `effects/` | `wipes`, `confetti`, `dust`, `spark`, `sleep_z` |
| `npcs/` | `garage_npcs` (one packed sheet for ambient garage characters) |

Rules:
- All-lowercase filenames
- Hyphens, not underscores, between words
- `.png` for the sheet, `.json` for the frame data
- Both files share the same slug (TexturePacker default)

## Frame keys (inside the .json)

```
<character_id>_<animation>_<frame-index>
```

Examples:

```
trod_idle_0
trod_idle_1
trod_walk_r_0
trod_walk_r_1
trod_walk_r_2
trod_walk_r_3
trod_pushup_down
trod_pushup_up
trod_thumbs_up         (single-frame animations have no _N suffix)
bentley_idle_0
medal_gold_0
medal_silver_0
ui_cursor_arrow_0      (with N for animation-frame variants)
```

Rules:
- All-lowercase
- Underscores between words (different from filenames)
- Animation name is plural-singular consistent — `idle` not `idles`,
  `walk` not `walking`
- Frame-index is zero-based
- Direction qualifier comes before frame index — `walk_r_0`, `walk_l_0`
- Single-frame animations have no `_0` suffix (just `thumbs_up`,
  not `thumbs_up_0`)

## Animation keys (in the JSON's `animations` block)

```
<animation>            (no character prefix — already scoped to the sheet)
```

Examples:

```jsonc
"animations": {
  "idle":      { ... },
  "walk_r":    { ... },
  "walk_l":    { ... },
  "run_r":     { ... },
  "talk":      { ... },
  "thumbsup":  { ... },           // shorthand without underscore
  "victory":   { ... },
  "disappointed": { ... },
  "pushup":    { ... },           // 2-frame: pushup_down + pushup_up
  "sleep":     { ... },
  "kick":      { ... },
  "fight_stance": { ... }
}
```

Rules:
- Match the frame-key prefix (e.g., `walk_r` animation references
  `<char>_walk_r_*` frames)
- The `Sprite.vue` component is called with `animation="idle"`, never
  `animation="trod_idle"` — the sheet name is separate

## Standard animation names (consistent across every character)

These names are required for every coach and driver. Implementations
that don't have a frame for a name should provide an `idle`-equivalent
instead (so the sprite never breaks).

| Name | Frames | FPS | Purpose |
|---|---|---|---|
| `idle` | 2 | 1.5 | Default; gentle breathing |
| `walk_r` / `walk_l` | 4 | 6 | Walking right / left |
| `run_r` / `run_l` | 4 | 8 | Running right / left |
| `talk` | 2 | 6 | Mouth open/closed during dialogue |
| `thumbsup` | 1 | — | Stage clear "great session" |
| `disappointed` | 1 | — | Stage clear "missed goals" |
| `victory` | 2 | 4 | PB unlock celebration |
| `pushup` | 2 | 4 | Easter egg / training scene |
| `sleep` | 3 | 1 | End of day idle |

## Required animations per character class

### Coaches (full set)

T-Rod (full sheet):
- `idle`, `walk_r`, `walk_l`, `run_r`, `talk`, `thumbsup`,
  `disappointed`, `victory`, `pushup`, `sleep`, `kick`, `fight_stance`,
  `point_left`, `point_right`, `clipboard_writing`, `wrench_pose`,
  `holding_gauge`, `coffee_mug`, `bed_lie`, `phone_check`,
  `tablet_review`, `medal_proud`, `trophy_hold`, `arms_crossed`

Other coaches (minimum set):
- `idle`, `walk_r`, `walk_l`, `talk`, `thumbsup`, `disappointed`,
  `victory`, `pushup`

### Drivers (avatars)

- `idle`, `helmet_on`, `victory`, `disappointed`

### UI sprites

- `frames` sheet has named frames not animations (`frame-default`,
  `frame-dialogue`, `frame-card`)
- `cursor` has `arrow` (1 frame) — bouncing is done via CSS transform,
  not extra frames
- `medals` has named frames (`medal_bronze_0`, `medal_silver_0`, …)

## Naming examples (do / don't)

| Do | Don't |
|---|---|
| `trod_idle_0` | `T-Rod_Idle_0` |
| `walk_r` | `walking-right` |
| `thumbsup` | `thumbs-up` (in animation key) |
| `medal_gold_0` | `medal_gold.png` (each medal goes in the packed sheet, not as a separate file) |
| `frame-default` (filename) | `frame_default.png` (filename) |
| `coaches/trod.png` | `coaches/coach_trod.png` |
| `walk_r_0` to `walk_r_3` | `walk_right_frame1`, `walk_right_frame2` |

## Versioning

When a sprite sheet changes (new frames added, palette adjusted), bump
the file name's hash suffix:

```
coaches/trod.<hash>.png
coaches/trod.<hash>.json
```

The build pipeline (Vite) handles this automatically via content hashing
on import. Don't hand-version.

## Lint

A pre-commit hook runs `scripts/lint-sprites.ts` to verify:
- Every `.png` in `sprites/` has a matching `.json`
- Every `.json` has the required keys (`frames`, `animations`, `meta`)
- Every animation referenced in any view exists in some sheet's
  `animations` block (catches typos in template strings)

```bash
pnpm lint:sprites
```

## Related

- [`../02-sprite-sheet-spec.md`](../02-sprite-sheet-spec.md) — frame
  inventory + per-character frame counts
- [`reference-sheet-source.md`](reference-sheet-source.md) — generation
  prompts
