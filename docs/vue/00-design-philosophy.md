# 00 — Design philosophy

## The pitch

> It's an RPG where the dungeon IS the racetrack.

That's the design north star. Every feature, every screen, every sprite
asks: *if this were a Pokémon-shaped racing RPG running on a
late-GBA / early-DS-era handheld, how would it feel?* If it would feel
clunky, the answer is wrong, regardless of what the underlying telemetry
says.

## Reference points (and what we take from each)

| Reference | What we take | What we leave |
|---|---|---|
| **Stardew Valley** (ConcernedApe, 2016) | Warm, lived-in pixel art with NPC mentors. Daily rhythm — start in the farmhouse, do the day, end at home. The pit garage is the farmhouse. | The farming sim. We don't have crops to grow. |
| **Pokémon Emerald / Black-White** (Game Freak, 2004 / 2010) | Trainer card, save slot system, dialogue-box pacing, Professor Oak as the mentor archetype, region map with locations as quest hubs, Pokédex-style coach progression. | Random encounters, type matchups. |
| **Tony Hawk's Pro Skater 2 GBA** (Vicarious Visions, 2002) | Career-mode structure: pick a level → see goals → run the level → score screen → unlock next level. Stat-based progression: skill trees, sponsors, gear unlocks. | Half-pipe combos. |
| **Mario Kart Super Circuit** (Intelligent Systems, 2001) | Cup → track → result loop. Track icons on the world map. Bronze / silver / gold trophy system. | The karts themselves. |
| **Motocross Challenge GBA** (Black Lantern Studios, 2007) | Real-feel racing on a GBA-era 2.5D engine. Practice / Career / Time Trial mode split. | Gas-pedal physics. |
| **Crosscode** (Radical Fish Games, 2018) | Modern indie pixel art proportions, smooth combat-loop UI, isometric world feel. The "Stage Clear" celebration. | Combat puzzle dungeons. |
| **Eastward** (Pixpil, 2021) | Cinematic dialogue framing with portrait sprites. Quiet moments between action. | The plot. |

If a reviewer asks *"is this trying to be GBA F-Zero?"* — no. F-Zero
Maximum Velocity is a fast arcade racer. We're an RPG with racing as
the verb.

## Three principles overriding everything

These come straight from `docs/ux.md` but get re-stated here because
they're load-bearing for the game wrapper too.

### 1. The driving is the real thing

The game is the wrapper, not the substance. Every animation, every
score-screen flourish, every coach reaction is *grounded in real
telemetry data from the bridge*. We never invent a stat for the game
that the analytics don't actually compute. If the dashboard says
`apex_speed_kmh = 86`, the score screen shows `86 km/h apex`, and the
coach's `hyped` sprite plays only because it's a real personal best.

### 2. Silence is coaching

The arbiter holds 78% of generated cues. The pixel-art wrapper holds
even more — quiet stretches between dialogue boxes, calm garage music
during the in-between. **Don't fill space.** Don't surface a tutorial
during a hot lap. Don't pop achievement toasts mid-corner. The game's
patience IS the trust UX from `docs/ux.md` made tangible.

### 3. Every visible decision must trace to a real one

If a UI element implies a choice ("equip this coach"), there is a real
coach-engine config behind it. If an icon says "T7 entry needs work,"
real `corner_aggregates.apex_speed_kmh` data flagged it. The game can
*frame* analytics; it cannot *fabricate* them. This is what makes
"trustable" tangible — pull any thread, hit the bridge endpoint
underneath.

## The verb

Every screen has one verb the player should feel they're doing.

| Screen | Verb |
|---|---|
| Title | Begin |
| Save select | Identify |
| Onboarding | Set up |
| Garage hub | Choose where to go |
| Trainer card | Reflect |
| Coach select | Recruit |
| World map | Travel |
| Pre-brief | Set intentions |
| On-track HUD | Drive |
| Cool-down | Process |
| Stage clear | Celebrate / Learn |
| Replay | Re-live |
| Quest log | Plan |
| Settings | Tune |
| End of day | Wind down |

If a screen doesn't have a clear verb, it's a wrong screen. Combine it
with another or cut it.

## What we explicitly *don't* do

- **No XP grinding.** Sessions reward genuine improvement; you can't
  hammer the home page for points. Levels come from real driving time,
  not menu-tapping.
- **No fail states.** "Game over" doesn't exist. Bad sessions are
  feedback, not failure. The coach is disappointed, not punishing.
- **No microtransactions.** No premium currency. No premium coaches.
  No premium tracks. If we ship to a public app store post-Sonoma, this
  rule stays.
- **No stamina meter / energy gating.** You can drive as much as the car
  + tires + insurance allow. The app never tells you to come back later.
- **No leaderboards (yet).** Multiplayer is post-Sonoma. The driver
  competes with their own past self via `/driver/<id>/evolution`.
- **No "social share" before May 23.** No outbound share button until
  we've decided what privacy posture means. See
  [`docs/ux.md` § Data privacy & residency](../ux.md).

## What "feels like an old game" specifically means

The user said *"choose the best UX that feels like an old game."* Here's
the precise reading we're committing to:

- **Integer-scaled pixel art** at viewport scale (`image-rendering:
  pixelated`). No anti-aliasing, no fractional scales. A 64×64 sprite is
  64×64, 128×128, 192×192 — never 96×96.
- **Three pixel-grade fonts only**: a chunky title font (Press Start 2P
  or DePixel Schmal), a clean body font (m6x11 / Pixel Operator), a
  7-segment digital readout (DSEG7) for lap timers.
- **Sub-100ms response on every input.** Old games never lagged. The
  D-pad-style nav must feel like cursor-on-rails.
- **Audio that punctuates.** Every confirm has a chime, every cancel has
  a thud, every level-up has a fanfare. Silence is OK; absence-of-feedback
  is not.
- **Save slots, not auto-cloud.** The user picks a slot like they're
  inserting a cartridge. Save slots persist locally (IndexedDB). No
  cloud account, no email login.
- **Title screen on every cold boot.** PRESS START. Not "skip to home."
  The title screen is a beat that says *you've entered a game now*.
- **Dialogue boxes with teletype.** Coach text appears one character
  at a time at ~30 char/sec. Tap-to-skip. This is non-negotiable; it's
  the single biggest contributor to the "old game" feeling.
- **No hamburger menus.** Navigation is via a D-pad metaphor — tile
  grids you cursor across, never lists you scroll.
- **Modal everything.** The screen you're on is the only screen.
  Settings is a screen, not a panel. Inventory is a screen, not a panel.

## What it definitely does NOT mean

- **Not "GBA-resolution-locked."** 240×160 native is too small for
  modern phone screens; we use 480×320 (2× GBA) as the design grid.
- **Not "monochrome 4-color palette."** The user's reference sprite
  sheet uses 30+ colours with smooth shading. We match THAT range, not
  the original GBA's 32k.
- **Not "limited to 4 sprites on screen."** Modern hardware. We can
  render the whole garage with NPCs walking around. Don't be tempted
  to artificially cap.
- **Not "ironic retro."** This is sincere. The pixel art is the actual
  product, not a meme.

## Aesthetic anchor: the user's sprite sheet

[`assets/reference-sheet-source.md`](assets/reference-sheet-source.md)
documents what the user supplied. The single most important data point
from that sheet is the **palette** — 30+ shades of grey/red/black/skin
with smooth dithered transitions. That's the aesthetic. Stardew-Valley
proportions, late-Game-Boy-Advance era racing-RPG framing, real telemetry
underneath.

Match the palette. Match the proportions. Frame the gameplay loop like
a Pokémon trainer's daily rhythm. Get out of the way and let the
driving be the substance.

## Decision log

Things we considered and rejected.

| Considered | Rejected because |
|---|---|
| Pure F-Zero Maximum Velocity aesthetic (240×160, 4-color tunnels) | Too small for modern phones; signals retro-as-gimmick rather than substance |
| Anime / manga portraits | Doesn't match the user's reference sheet; would feel disjointed |
| Real photo of the driver in the trainer card | Privacy nightmare; breaks the visual style |
| 3D Mario-Kart-style intro cinematic | Too much production cost; pixel art is the budget-honest choice |
| Always-on coach voiceover | Violates "silence is coaching" |
| First-person POV on the title screen | We don't have driving footage; pixel art the title art |
| "Pay-to-skip" coach unlocks | Violates the no-microtransactions principle |

## Related

- [`01-visual-language.md`](01-visual-language.md) — palette + typography
- [`02-sprite-sheet-spec.md`](02-sprite-sheet-spec.md) — frame inventory
- [`03-character-bible.md`](03-character-bible.md) — the cast
- [`screens/00-title.md`](screens/00-title.md) — first screen; the rest live alongside it under `screens/`
- [ADR-013 — Frontend visualises, backend reasons](../adr/013-frontend-backend-boundary.md)
