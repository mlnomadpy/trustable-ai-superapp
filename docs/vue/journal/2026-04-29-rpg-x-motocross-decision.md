# 2026-04-29 — RPG × Motocross decision

The user asked us to design the Vue PWA's UX feeling like *"an RPG game
× motocross challenge GBA game"* and shared a 13×13 sprite sheet of
T-Rod (~169 frames showing a full coach lifecycle: walking, running,
mechanical work, pushups, kicks, victory poses, sleeping, even a
stargazing frame). The user closed with *"chose the best UX that feels
like an old game."*

This journal captures the why behind the call we made.

## What the user actually has vs what they said

The phrase "GBA game" pointed us initially toward GBA-strict aesthetic
(F-Zero Maximum Velocity, Mario Kart Super Circuit, 240×160 native
resolution, 4-shade palettes). But the **sprite sheet they shared
isn't GBA**:

- 30+ shades of grey/red/black/skin in the T-Rod sprite alone
- Smooth dithered shading (not 1-bit dithering)
- Modern proportions (head ~1/4 body height, slim build)
- Activities far beyond what a GBA character set ever included
  (mechanical work, push-ups, stargazing, sleep)

That sheet is **modern indie pixel art** — Stardew Valley / Eastward /
Pyre era. Way more visually rich than a pure GBA game would have been.

So the user's words and the user's reference *disagreed*. We went with
the reference, not the words. The aesthetic is "modern indie pixel-art
RPG that *feels* like an old GBA-era racing game in structure." Best of
both.

## The pitch we committed to

> *It's an RPG where the dungeon IS the racetrack.*

References we decided to chase:

| Game | What we take |
|---|---|
| Stardew Valley | Warm, lived-in pixel-art with NPCs; daily rhythm |
| Pokémon Emerald | Trainer card, save slots, Professor-Oak mentor archetype |
| Tony Hawk PSGBA | Career mode with sponsor goals, stat trees |
| Mario Kart Super Circuit | Track-based progression, cup/championship structure |
| Crosscode | Stage-clear celebration, modern pixel-art proportions |
| Motocross Challenge GBA | Real-feel racing on a 2.5D engine; practice/career split |

Crucially **not** F-Zero Maximum Velocity. Too much arcade, not enough
RPG. The driver isn't the camera; the driver is the protagonist.

## What this means concretely

- **Visual reference** = the user's T-Rod sprite sheet (Stardew-era
  proportions + 30+ palette)
- **Resolution** = 480×320 logical (2× GBA) at integer scales
- **Information architecture** = career-mode RPG (save slot → garage
  hub → world map → pre-brief → drive → cool-down → stage clear)
- **Coach** = mentor NPC archetype (Professor Oak), 5 personas,
  affinity meter, NPC-walks-around-the-garage behaviour
- **Progression** = real telemetry-derived levels, medals, evolution
  charts. Nothing fabricated for the game; everything grounded in
  bridge data
- **Audio** = chiptune music + jsfxr SFX + pre-rendered TTS coach voice
- **Architecture-as-game** = the trainer card displays the driver_profile
  endpoint's output directly; the world map drives `/track/<id>/elevation`;
  stage clear is the score formula made tactile

## What we deliberately rejected

- Pure GBA palette — the sprite sheet rules it out
- Anime / manga portraits — visual disjunct with the sprite sheet
- Cinematic 3D intro — too much production cost; pixel art is the
  budget-honest choice
- "Game over" / fail states — the driving is real; bad sessions are
  feedback, not failure
- Microtransactions in any form
- Stamina/energy gating
- Public leaderboards (post-Sonoma decision)
- "Ironic retro" — this is sincere

## What we'll know in 1 week

After scaffold + first 2-3 screens are implemented:

- Whether the modern-indie-pixel-art direction holds at integer scales
  on a real Pixel screen (vs only-pretty-on-laptops)
- Whether the chosen palette has enough range for night-mode +
  high-contrast variants
- Whether `m6x11` body font is readable at 1× scale on a phone — if
  not, fall back to `Pixel Operator`
- Whether the audio + sprite system feels game-shaped at all, or like a
  webapp-with-pixel-art

If those hold → the design philosophy survives the first contact with
implementation, and the screen docs become specifications.

If they don't → revisit, but only after measuring on real hardware.

## Tone note

This whole doc folder reads as a design journal not a dry spec because
that's how the user asked: *"create a vue folder in the docs to
document the journey."* We commit to that framing. The screens will
say what they are, but they'll also be honest about where the
decisions came from. If a future contributor reads `04-trainer-card.md`
and wonders "why a Pokémon-style trainer card?", they should be able
to walk back to this journal and find the reasoning.
