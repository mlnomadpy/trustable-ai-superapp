# 01 — Visual language

The visual contract every screen and component honours. Derived directly
from the user's reference sprite sheet
([`assets/reference-sheet-source.md`](assets/reference-sheet-source.md)).

## Resolution + scaling

| Decision | Value |
|---|---|
| Logical canvas | **480 × 320** |
| Native sprite frame size | **64 × 64** (most NPCs), **128 × 128** (hero portraits), **32 × 32** (icons) |
| Scaling rule | Integer scales only. The PWA picks the largest integer scale that fits the viewport. |
| Render mode | `image-rendering: pixelated` everywhere. No anti-aliasing. No fractional scales. |
| Common viewport scales | Pixel 10 portrait → 4× (1920 × 1280 logical), laptop 1920×1080 → 5× with letterbox |

```css
/* Tailwind component: pixel-perfect viewport */
.viewport {
  width:  var(--base-w, 480px);
  height: var(--base-h, 320px);
  transform-origin: center;
  transform: scale(var(--scale, 4));
  overflow: hidden;
  position: relative;
  image-rendering: pixelated;
}
```

A small `useViewportScale()` composable computes the scale on resize.
See [`09-tech-stack.md`](09-tech-stack.md).

## Palette

Derived by sampling the reference sprite sheet. Not an arbitrary scheme —
these are the colours actually present in T-Rod's sprite, extended for
backgrounds and UI.

### Character palette (from the sheet)

Read off T-Rod's sprite at sub-pixel level:

```
ink           #1a1d2e    deepest shadow on jacket
charcoal      #2a2f42    jacket mid-tone
slate         #3d4458    jacket highlight, pants base
silver        #6e7686    pants highlight, metal accents
hair-shadow   #6e6c68    grey hair shadow
hair-mid      #a8a4a0    grey hair mid
hair-light    #d8d4c8    grey hair highlight
skin-shadow   #b07658    face shadow
skin-mid      #d89878    face mid
skin-light    #ecb898    face highlight
red-deep      #8a2828    jacket trim shadow
red-mid       #c93838    jacket trim mid (also curb red)
red-light     #e85858    jacket trim highlight
white         #f8f8f0    eye whites, "PRESS START" text
black-line    #0d0d12    1-px outline on every sprite
```

### Track environment palette

Extends the character palette into world settings. Tested for
contrast against the character against any background; nothing in
this row should make T-Rod's outline disappear.

```
asphalt-deep  #1f2230    racing surface deep
asphalt-mid   #2c3242    racing surface mid
asphalt-light #3d4458    racing surface highlight
curb-red      #c93838    matches red-mid
curb-white    #f5f5e8    high-contrast curb stripe
grass-shadow  #2e4a36    Sonoma hills shadow
grass-mid     #4a7050    Sonoma hills mid
grass-light   #6b8a5a    Sonoma hills highlight
sky-dawn      #d8b878    sunrise tone
sky-noon      #6e8ec4    daytime
sky-dusk      #c8786a    sunset (title screen)
sky-night     #1a1d3e    night drive
```

### Functional / UI palette

```
ui-good       #2aa198    success / "GREAT TRAIL BRAKE"
ui-warn       #b58900    "needs work"
ui-bad        #dc322f    "danger zone" / "over the limit"
ui-info       #4a98c8    informational dialogue
ui-quest      #d3a832    medal gold / quest yellow
ui-coach      #c93838    coach accent (matches red-mid)
ui-bg-deep    #0d0d12    dialogue-box dark fill
ui-bg-mid     #1a1d2e    panel mid
ui-bg-light   #2a2f4a    panel highlight
ui-text-100   #f8f8f0    body text
ui-text-300   #b8b8a8    secondary text
ui-text-500   #5a5a4a    disabled / footnote
```

### Tailwind config

```ts
// tailwind.config.ts (excerpt)
theme: {
  colors: {
    ink:        '#1a1d2e',
    charcoal:   '#2a2f42',
    slate:      '#3d4458',
    silver:     '#6e7686',
    hair: { shadow: '#6e6c68', mid: '#a8a4a0', light: '#d8d4c8' },
    skin: { shadow: '#b07658', mid: '#d89878', light: '#ecb898' },
    red:  { deep: '#8a2828', mid: '#c93838', light: '#e85858' },
    white:      '#f8f8f0',
    'black-line': '#0d0d12',

    asphalt: { deep: '#1f2230', mid: '#2c3242', light: '#3d4458' },
    curb:    { red: '#c93838', white: '#f5f5e8' },
    grass:   { shadow: '#2e4a36', mid: '#4a7050', light: '#6b8a5a' },
    sky:     { dawn: '#d8b878', noon: '#6e8ec4', dusk: '#c8786a', night: '#1a1d3e' },

    ui: {
      good:  '#2aa198', warn:  '#b58900', bad:   '#dc322f',
      info:  '#4a98c8', quest: '#d3a832', coach: '#c93838',
    },
  },
}
```

## Typography

Three fonts. Each one has a single role; no multi-purpose fonts.

### `Press Start 2P` — titles + START prompts

- Used on: title screen, "STAGE CLEAR" banner, level-up text, medal names
- Maximum 16 characters per line; longer = wrap or shrink
- Always uppercase
- Tight letter-spacing (`tracking-tight`)
- Available via Google Fonts (free, OFL)

### `m6x11` — body, dialogue, menus, table data

- Used on: dialogue boxes (with teletype), menu lists, trainer card
  body, settings, every UI element that isn't a title or a number
- Mixed case OK
- Line-height 1.1 (chunky, not airy)
- Self-host the .ttf (creator: Daniel Linssen, free)

### `DSEG7-Classic` — lap times, speed, RPM, all numeric readouts

- Used on: HUD speed/RPM, lap timer, distance readout, trainer card
  best-lap field
- Right-aligned by default
- Fixed-width — digits don't bounce when value changes
- Self-host (creator: keshikan, OFL)

```css
@font-face {
  font-family: 'm6x11';
  src: url('/fonts/m6x11.woff2') format('woff2');
  font-display: block;       /* never show fallback; pixel font is the brand */
}
@font-face {
  font-family: 'DSEG7-Classic';
  src: url('/fonts/DSEG7Classic-Regular.woff2') format('woff2');
  font-display: block;
}
```

```ts
// tailwind.config.ts (excerpt)
fontFamily: {
  title: ['"Press Start 2P"', 'monospace'],
  ui:    ['"m6x11"', 'monospace'],
  nums:  ['"DSEG7-Classic"', 'monospace'],
}
```

### Type scale

| Class | Use | Size at 1× | At 4× |
|---|---|---|---|
| `text-title-xl` | Title screen "PITWALL" logo | not text — sprite |
| `text-title-lg` | "STAGE CLEAR" banner | 16 px | 64 px |
| `text-title`    | Screen heading ("WORLD MAP") | 12 px | 48 px |
| `text-body`     | Dialogue, menu labels | 8 px | 32 px |
| `text-small`    | Secondary text, hints | 6 px | 24 px |
| `text-num-lg`   | HUD speed (DSEG7) | 14 px | 56 px |
| `text-num`      | Lap times | 10 px | 40 px |

## The 9-slice frame system

Three nine-slice PNG frames cover every container. Implemented as
`border-image` with `image-rendering: pixelated`.

```
frame-default     8×8 corner tile, 1 px white outline + 2 px ink-deep drop shadow
frame-dialogue    12×12 corner, thicker outline, small triangle pointer
frame-card        12×12 corner, double outline, corner notch motif
```

```css
.frame-default {
  border-style: solid;
  border-width: 8px;          /* logical px, scaled by viewport */
  border-image: url('/sprites/ui/frame-default.png') 8 fill / 8px / 0 stretch;
}
```

The frame sprites live in `pitwall-web/public/sprites/ui/`. Generation
prompts are in [`assets/reference-sheet-source.md`](assets/reference-sheet-source.md).

## Animation primitives

Three building blocks every screen composes.

### Sprite frame loops

Per-character animations use a fixed FPS via CSS `animation-timing-function:
steps(N)`. Default frame rates:

| Animation | FPS | Frames |
|---|---|---|
| Idle / breathing | 1.5 Hz | 2 |
| Walking | 6 Hz | 4 |
| Running | 8 Hz | 4 |
| Talking (mouth open/closed) | 6 Hz | 2 |
| Action (push-up, kick, fist pump) | 6 Hz | 2-4 |
| Sleep ("Z" floating up) | 1 Hz | 3 |

### Screen transitions

Screen changes use a 4-frame **horizontal swipe wipe** at 150 ms total.
The wipe sprite is a single 480×320 PNG with a vertical band;
`transform: translateX(-100%)` slides it out.

| Transition | When | Direction | Duration |
|---|---|---|---|
| `wipe-right` | Forward navigation (selecting a tile) | left → right | 150 ms |
| `wipe-left` | Back navigation (B button) | right → left | 150 ms |
| `wipe-up` | Entering paddock from on-track | bottom → top | 200 ms |
| `wipe-down` | Entering on-track from paddock | top → bottom | 200 ms |
| `flash-white` | Achievement unlock | full-screen flash | 100 ms |
| `fade-to-night` | End of day | fade through ink-deep | 1500 ms |

### Cursor behaviours

A pixel arrow (▶, sprite) marks the active selection on any menu.

| Behaviour | Animation |
|---|---|
| Idle on tile | bounce 1 px horizontally at 4 Hz |
| Just moved to a new tile | brief flash (1 frame ui-coach) |
| Confirm pressed | scale 1.0 → 1.2 → 1.0 over 150 ms |

## Layout primitives

Four layout patterns every screen composes from.

### Status bar (always present)

16 px tall strip at the top. Shows: driver name + level (left), coach
badge (centre), real-world clock (right). Fixed across every screen
including the on-track HUD.

```
┌──────────────────────────────────────────────────────────────┐
│ TAHA · LV.12        ⚙ T-ROD                       15:32 PT   │
└──────────────────────────────────────────────────────────────┘
```

### Hint bar (always present)

12 px tall strip at the bottom. Shows context-sensitive button hints.

```
└──────────────────────────────────────────────────────────────┘
│ A · SELECT     B · BACK     ◀ ▶ MOVE                          │
└──────────────────────────────────────────────────────────────┘
```

### Tile grid (menus)

Most menus use a tile grid. Tiles are 9-slice frames with text +
optional small icon sprite. Cursor moves with D-pad metaphor; A
confirms; B backs out.

| Grid | Tile size | Use |
|---|---|---|
| 2 × 2 | 220 × 110 | Garage hub main verbs |
| 3 × 3 | 140 × 80 | Coach select roster |
| 1 × N | 460 × 32 | Save slot list, sessions list |

### Dialogue box (NPC interaction)

160 px tall strip docked to bottom (above hint bar). Shows portrait sprite
on the left + teletyped text on the right. Tapping advances; B skips.

```
┌──────────────────────────────────────────────────────────────┐
│ ┌──────┐  Settle in. We're at Sonoma, peak grip today,         │
│ │T-ROD │  so we're going to be tight. Remember, distance is    │
│ │  + 3 │  king, especially on these sweeps.                    │
│ │frames│                                            ▼ tap to   │
│ └──────┘                                              advance  │
└──────────────────────────────────────────────────────────────┘
```

## Audio cues paired with visuals

Every visual transition has a paired audio cue. The full SFX list is in
[`06-audio-design.md`](06-audio-design.md); these are the visual ↔ audio
pairs every screen needs:

| Visual event | Audio cue |
|---|---|
| Cursor move | `cursor-move` (16 ms tick) |
| A button confirm | `cursor-select` (two-note ding) |
| B button cancel | `cancel` (soft thud) |
| Wipe transition | `transition-wipe` (whoosh) |
| Dialogue char appears | `dialogue-blip` (very soft tick, max once per 30 ms) |
| Score number ticks up | `score-tick` (click per 100 points) |
| Medal awarded | `medal-award` (slot-machine ding-ding-ding) |
| Personal best unlocked | `pb-unlock` (six-note fanfare) |
| Over-grip warning (HUD) | `over-grip` (buzzer) |

## Don't list

- **No drop shadows beyond the 1-px sprite outline.** No CSS
  `box-shadow`. The pixel-perfect frame system gives the depth.
- **No gradients, ever.** All fills are solid. Sky has gradients
  *baked into the sprite*, not CSS.
- **No translucency / alpha blending in UI.** Transparency only for
  sprite cutouts and the wipe transition mask.
- **No emoji in UI strings.** Sprites for icons. The character set is
  predictable and renders identically on every device.
- **No system fonts as fallback.** If the pixel font fails to load, we
  show nothing rather than Arial. (`font-display: block`.)
- **No CSS animations longer than 1500 ms.** Anything longer is a
  multi-step sequence, not a transition; build it as orchestrated
  state changes.

## Related

- [`02-sprite-sheet-spec.md`](02-sprite-sheet-spec.md) — sprite frame
  taxonomy, naming, packing
- [`06-audio-design.md`](06-audio-design.md) — full SFX + music inventory
- [`08-animation-spec.md`](08-animation-spec.md) — easing curves, frame
  timing, screen-transition orchestration
- [`assets/reference-sheet-source.md`](assets/reference-sheet-source.md)
  — the exact source from which the palette was sampled
