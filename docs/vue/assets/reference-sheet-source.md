# Reference sheet source + nano-banana cookbook

This is where the "nano-banana generates the rest" promise meets
concrete prompts. The user supplied a complete T-Rod sprite sheet
on 2026-04-29; we use it as the consistency anchor for every other
sprite the project needs.

## The user's reference sheet

A single 13 × 13 grid (~169 frames) showing T-Rod across his full
animation lifecycle. Each cell is approximately 64 × 64 logical pixels
(plus a 2-px gutter). The sheet is committed at
`pitwall-web/public/sprites/coaches/trod-source.png` (raw, unpacked).

Per-row content is documented in
[`02-sprite-sheet-spec.md`](../02-sprite-sheet-spec.md) §
"Reference sheet → frame inventory mapping".

## Style anchor (use as preamble for EVERY prompt)

```
A 2D pixel-art character sprite in the style of a modern indie pixel
RPG (Stardew Valley / Eastward / Pyre era). 30+ shade palette with
smooth dithered shading. Single 1-pixel black outline. No
anti-aliasing in the character itself; only soft dithering inside
shaded regions. Centred composition. Square aspect ratio. White
background, transparent on export. The character is in a neutral lit
racing-paddock environment. No JPEG artefacts. Frame size 64 × 96 pixels
for full body sprites, 96 × 96 for portraits, 64 × 64 for action poses.

Match the proportions and colour grading of the user-supplied T-Rod
sprite sheet — head approximately 1/4 of body height, slim build, no
exaggerated cartoon features.
```

## Coach prompts (4 needed besides T-Rod)

Each coach gets the minimum 14-frame set (idle×2, walk×4, talk×2,
thumbsup, disappointed, victory×2, pushup×2 [easter egg]). Run each
prompt with the same seed for emotion variants to preserve facial
identity.

### Bentley

```
[STYLE ANCHOR]

Coach Bentley: a male British racing instructor in his 50s. Pale skin,
glasses with thin metal frames, receding hairline with greying
temples. Wears a button-down shirt (light blue or beige) under an
unbuttoned cardigan or instructor jacket. Holds a clipboard in his left
hand. Calm, professional posture — body slightly relaxed, weight on
one leg. Pixel art. 64 × 96 px. Neutral expression for idle frames.

Variants:
- "neutral" — relaxed, looking forward
- "encouraging" — slight smile, gesture with open palm
- "disappointed" — frown, clipboard held lower, head slightly down
- "hyped" — wider smile, clipboard raised in approval
```

### Drill Sergeant

```
[STYLE ANCHOR]

Coach Drill Sergeant: a muscular ex-military male in his 40s. Tan
skin, weathered face, intense expression. Buzzcut hair (very short,
brown-grey). Wears a black race-suit top half-unzipped showing a white
undershirt; tribal tattoos visible on neck/arm if visible. Strong,
upright stance. Hands on hips. Pixel art. 64 × 96 px.

Variants:
- "neutral" — stern, arms crossed
- "encouraging" — pointing forcefully at the camera with a raised eyebrow
- "disappointed" — palms-up shrug with a hard frown
- "hyped" — fist pump, mouth open mid-shout
```

### Calm Pro

```
[STYLE ANCHOR]

Coach Calm Pro: a female pro driver in her 30s. East-Asian features,
straight black hair tied back. Wears a fitted red-and-black race suit
zipped to the neck. Holds a helmet under her right arm. Composed,
upright stance with weight balanced. Pixel art. 64 × 96 px.

Variants:
- "neutral" — quiet, slight smile
- "encouraging" — small thumbs-up at hip level, neutral face
- "disappointed" — slight head tilt, soft sigh expression
- "hyped" — eyes brighten, helmet raised slightly
```

### Buddy

```
[STYLE ANCHOR]

Coach Buddy: a friendly male driver in his late 20s. Latin-American
features, scruffy beard, warm brown eyes. Wears a hoodie (charcoal grey
or olive green) under a beanie (knit cap, dark colour). Holds a coffee
cup in his right hand. Casual relaxed stance, weight on one leg, free
hand in pocket. Pixel art. 64 × 96 px.

Variants:
- "neutral" — friendly half-smile
- "encouraging" — open-mouth grin, free hand giving thumbs-up
- "disappointed" — coffee cup lowered, head tilted, soft frown
- "hyped" — coffee cup raised in toast, eyes wide, mouth open
```

## Driver avatar prompts

Eight base avatars. Each needs 5 frames: `idle_0/1`, `helmet_on`,
`victory`, `disappointed`. 64 × 96 px (full body) or 64 × 64 (helmet-on
shot only).

```
Avatar 1 (helmet-up, default racing):
A racing driver in a white-and-orange race suit. Helmet under left
arm. Neutral relaxed pose. Centred composition. Track environment
subtle in the background.

Avatar 2 (casual): same character but in t-shirt + jeans, baseball cap
backwards.

Avatar 3 (full pro): race suit zipped tight, helmet on with visor up
showing eyes.

Avatar 4 (vintage): open-face helmet with goggles pushed up,
old-school leather Nomex suit, vintage racing gloves.

Avatar 5 (female pro): female driver in red-and-white race suit,
helmet under arm.

Avatar 6 (female casual): same character but in t-shirt + leggings,
hair in a ponytail.

Avatar 7 (older instructor): male driver in his 60s, charcoal-grey
race suit, well-worn, greying hair, wise expression.

Avatar 8 (LOCKED — hooded mystery): hooded figure, face fully
shadowed, hoodie up, dark colour palette. Mysterious silhouette.
```

## UI element prompts

```
Logo "PITWALL":
Bold pixel-art word mark "PITWALL" in chunky GBA-era logotype. White +
red-mid (#c93838) + black-line palette. 256 × 64 px. Centred. A vague
checkered-flag motif on the P and final L. Subtitle slot underneath
for "AI Racing Coach".

Frame nine-slice "frame-default":
An 8 × 8 nine-slice frame tile with a single-pixel white outline,
2-pixel ink-deep (#1a1d2e) drop shadow, and clean corners. Tilable
for stretch.

Cursor arrow ▶:
A pixel-art right-facing arrow (▶) at 16 × 16 px. White core with
black-line outline. Single-frame.

Medal sprite (per tier):
Round pixel-art medal at 32 × 32 px, viewed face-on, with a star
embossed in the centre. Generate one per tier:
- bronze (#a06030 / #6e4020 / #d68850 ribbon)
- silver (#a8a4a0 / #6e6c68 / #d8d4c8 ribbon)
- gold (#d3a832 / #8a6c1c / #e8c850 ribbon)
- platinum (#a0c0d0 / #6080a0 / #c8e0f0 ribbon)
- rainbow (multi-hue gradient ribbon, gold core)

START prompt arrow:
Two pixel-art arrows pointing inward at "PRESS START" text:
"▶ PRESS START ◀". GBA-era, 256 × 24 px, white on transparent.
```

## Environment prompts

```
Garage interior background:
A 480 × 320 pixel-art racing-team pit garage interior. Visible: large
rolling toolbox, tire stack in one corner, hanging fluorescent lights,
overhead hoist, BMW M3 E46 silhouette mid-frame (mostly inside
garage). Bottom 1/3 has a cleared "stage" area for the player and
coach sprites to walk around. Side-view, no perspective. Dark blue
concrete floor. Walls in warm grey. Limit palette to ~32 colours
matching the project palette in
docs/vue/01-visual-language.md.

Title-screen background — Sonoma sunset:
A stylized pixel-art Sonoma turn-11 viewpoint at sunset. Distant hills
behind, lit paddock to the right, BMW M3 silhouette mid-corner left.
Wide aspect 480 × 320. GBA-era F-Zero-Maximum-Velocity vibe. Strong
silhouettes, gradient sky from amber (#d8b878) at the horizon to deep
purple-blue (#1a1d3e) at the top.

Sonoma raceway track map (top-down):
A top-down pixel-art rendering of Sonoma Raceway's full 4.06 km lap.
White track outline with red kerb stripes, 11 corners labelled with
small "1"–"11" numerals (m6x11 font). Ground colour: warm dusty brown
(#7a6448). Grass: muted olive-green (#4a7050). Pit lane and
start/finish line marked. 256 × 256 px. Suitable for HUD mini-map at
this size.

World map of California coast (for the world-map screen):
A 480 × 320 pixel-art map of central + northern California coastline.
Stylized — not precise geography. Sonoma raceway pin highlighted (red
+ pulsing); future tracks (Laguna Seca, Thunderhill, Buttonwillow) as
locked silhouette pins. Pacific ocean in the west (sky-noon blue).
Gentle hills in olive-green. Hand-drawn pixel-art feel.
```

## Effect prompts

```
Wipe transition strip:
A 480 × 320 pixel-art "curtain" sprite — black background with a
diagonal pattern that visually reads as a wipe. 4 frames showing the
strip moving from off-screen left to fully covering the canvas.

Confetti burst:
A radial burst of small (4 × 4 px) coloured squares — gold, red, white,
cyan, green — emitting from a central point. 8 frames showing the
particles travelling outward and fading. 64 × 64 px.

Dust puff:
A small grey-tan (#a89878) cloud, 16 × 16 px, 4 frames showing
expansion + fade.

Spark / flash:
A bright white star-shape with radiating lines, 32 × 32 px, 2 frames
(big + medium).

Sleep "Z":
The letter Z in dark blue (#1a1d2e), with 3 frames showing it floating
upward + fading. 16 × 16 px.

Speech-bubble exclamation:
A pixel speech bubble with "!" inside, 24 × 24 px, 2 frames (small
pop + larger settle).
```

## Generation workflow

For each character beyond T-Rod:

1. Run the prompt with consistency-anchor mode enabled (Nano-Banana's
   "Use this character" feature) pointing at the T-Rod source sheet
2. Generate 4 emotion variants with the same seed
3. Manually crop each emotion to the 64 × 96 frame
4. Add to a per-coach .png + .json via TexturePacker
5. Smoke-test by loading via the `Sprite.vue` component
6. Iterate prompt if facial identity drifts

Budget per coach: ~30 minutes of prompt + crop + pack work.

## Quality checklist before committing a generated sheet

- [ ] All 14 frames present (or however many for that character)
- [ ] Single 1-pixel black outline on every frame
- [ ] Same head height across emotion variants
- [ ] Alpha background (no white halo)
- [ ] Palette uses < 50 colours (count via PNG quantizer)
- [ ] All frames same logical size (cropped consistently)
- [ ] Visible at 1 × scale without anti-aliasing
- [ ] Pack via TexturePacker with 2-px padding
- [ ] Produces a `.json` with `animations` block
- [ ] Loads cleanly via `Sprite.vue` at 1 ×, 2 ×, 4 ×, 6 × scales
- [ ] Pose reads at 16 × 16 (the smallest in-game scale we use)

## Sprite naming convention

See [`sprite-naming-convention.md`](sprite-naming-convention.md).

## Don't do

- **No multi-character compositions in one frame.** If T-Rod and
  another character must be on screen, render them as separate sprites
  and compose in CSS.
- **No backgrounds inside character frames.** Backgrounds are their
  own sprites, layered behind characters.
- **No text inside sprite frames.** Text is rendered with the pixel
  fonts; sprites are graphics only.
- **No animation frames longer than 4 in one direction.** If you need
  more, break into multiple animation cycles.

## Related

- [`../02-sprite-sheet-spec.md`](../02-sprite-sheet-spec.md) — frame
  taxonomy
- [`../03-character-bible.md`](../03-character-bible.md) — voice +
  personality (drives emotion choices)
- [`../01-visual-language.md`](../01-visual-language.md) — palette
- [`sprite-naming-convention.md`](sprite-naming-convention.md) — file
  + key naming
