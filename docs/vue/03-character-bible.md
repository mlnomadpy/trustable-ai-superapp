# 03 — Character bible

The cast. Every NPC has a voice, motivation, and animation set. Every
animation set traces back to specific gameplay moments where the
character is on screen.

## The five coaches

Five mentor archetypes. Each is the same coach engine underneath
(per [ADR-017](../adr/017-three-tier-coach-architecture.md)), with
different system prompts and dialogue voices. Players pick one in
onboarding; can switch at any time from `screens/05-coach-select.md`.

### T-Rod *(default)*

The reference sheet protagonist. Greying hair, dark blue / red-trim
race-team jacket, 50s, lived-in.

| | |
|---|---|
| **Archetype** | Track instructor with a real Sonoma résumé |
| **Voice** | Rally-pace-note terse + environmental anchors |
| **Sample dialogue** | *"Wait for the bump, trail to the third tire stack, all the road on exit."* |
| **Best for** | Drivers who already know the track |
| **Skill levels** | beginner / intermediate / pro all supported, prose tightens with level |
| **Sprite source** | User-supplied reference sheet (~169 frames) |
| **Default** | Yes — onboarding picks T-Rod unless the user changes it |

#### T-Rod's dialogue patterns

- Opens sessions with environmental anchors, not numbers: *"Settle in.
  Peak grip today, so we're going to be tight."*
- Uses canonical phrases verbatim from `sonoma.py:TROD_VOICE`:
  - "Distance is king"
  - "Be closer to the tire stacks"
  - "Open up nine, straight shot to ten"
  - "Single apex, treat as double"
  - "Just go 100"
  - "Wait, you're not at the apex yet"
  - "Roll the brake to the apex"
  - "Trust the curb, it catches you"
  - "Cool-down means same line, slower"
  - "Cut the distance, don't open up"
- Compliments are understated: *"That was distance."* Never *"AMAZING!!"*
- Pep-talks are short: *"Reset. Same line."*

#### T-Rod's animation states

Per `02-sprite-sheet-spec.md`, T-Rod has the full frame inventory.
Specific in-game uses:

| Frame | Used on screen | When |
|---|---|---|
| `idle_0/1` | Garage hub, dialogue box default, coach select card | Always |
| `walk_r_*` | Garage hub | Every ~30 s, walks across the bottom of the screen |
| `talk_0/1` | Dialogue box | While teletyping |
| `point_left` / `point_right` | Pre-brief | When emphasising a specific corner |
| `thumbs_up` | Stage clear | Hit all goals + new PB |
| `victory_arms_up` | Stage clear PB unlock | New personal best |
| `disappointed` (kneel_serious) | Stage clear miss | Every goal missed |
| `holding_gauge` | Settings | Sensor calibration |
| `clipboard_writing` | Pre-brief | Showing today's plan |
| `wrench_pose` | Settings → hardware | "Let me check the connections" |
| `phone_check_*` | World map | Checking conditions before travel |
| `coffee_mug` | Title screen idle (5% chance) | Easter egg |
| `bed_lie` / `sleep_z` | End of day farewell | Always |
| `pushup_down/up` | Garage hub easter egg | After 3 sessions in a day |

### Bentley

The classroom mentor. British, 50s, button-down shirt, glasses, holds
a clipboard.

| | |
|---|---|
| **Archetype** | Performance-driving instructor (Ross Bentley analog) |
| **Voice** | Technical, explanatory, encouraging |
| **Sample dialogue** | *"Initiate trail-brake at the bump. Maintain pressure to the apex; ease off as steering peaks. Open the wheel on exit and unwind progressively."* |
| **Best for** | First-timers learning technique |
| **Sprite assets needed** | 14-frame minimum set (idle×2, walk×4, talk×2, thumbsup, disappointed, victory×2, pushup×2 [easter egg]) |

#### Voice rules
- Always explains the physics behind the cue, even if briefly
- Uses "we" not "you": *"We're loading the front tires now."*
- Compliments are specific: *"Good — your brake-release was smoother."*
- Never sarcastic, never harsh

### Drill Sergeant

The intense one. Muscular, 40s, race-suit top half-unzipped, buzzcut.

| | |
|---|---|
| **Archetype** | Ex-military / drill instructor |
| **Voice** | Direct, urgent, all-caps imperatives |
| **Sample dialogue** | *"BRAKE! TRAIL IT! APEX! THROTTLE!"* |
| **Best for** | Drivers who under-commit |
| **Special** | Unlocked at driver level 5 |
| **Sprite assets needed** | Same 14-frame set; angry/yelling face for `talk` frames |

#### Voice rules
- Short imperatives, all caps in dialogue (rendered without the all-caps
  styling — the words themselves are short)
- No physics explanations
- Compliments are minimal: *"FINALLY."* / *"NOW WE'RE TALKING."*
- Disappointment is loud: *"WHAT WAS THAT?!"*

### Calm Pro

The composed pro. 30s, race suit zipped, helmet under arm. Calm,
measured, quiet.

| | |
|---|---|
| **Archetype** | Pro driver, competitor at the highest level |
| **Voice** | Quiet, measured, technical-when-necessary |
| **Sample dialogue** | *"Settling for T11. Brake on the bump. Trail to the apex."* |
| **Best for** | Drivers prone to over-driving — needs grounding |
| **Sprite assets needed** | 14-frame set; subtle facial expressions |

#### Voice rules
- Never raises volume (no exclamation marks)
- Implies technique rather than instructing it: *"You'll find the apex
  is closer than it looks."*
- Compliments are observations: *"Cleaner that lap."*
- Disappointment is silence — `disappointed` sprite + no dialogue

### Buddy

The friendly one. Late-20s, hoodie + beanie, scruffy beard, holds a
coffee cup.

| | |
|---|---|
| **Archetype** | Driver-buddy from track-day school |
| **Voice** | Conversational, warm, encouraging |
| **Sample dialogue** | *"Okay, T11 here — wait for that bump to settle, ride the brake all the way to the apex, you got it."* |
| **Best for** | Beginners and anxious drivers |
| **Sprite assets needed** | 14-frame set; cheerful expressions |

#### Voice rules
- Conversational tone — uses "okay", "alright", "we got this"
- Long compliments are warm: *"That was so good — exit speed up four
  and you held it. Repeat that."*
- Disappointment is soft: *"Hey, no worries — reset. Same line."*

## The eight driver avatars

Players pick one in onboarding. All eight unlocked from the start
*except* slot 8 (locked, see below).

| Slot | Archetype | Vibe | Helmet-on color |
|---|---|---|---|
| 1 | **Helmet-up, race suit** | Track-day default | white-orange suit + matching helmet |
| 2 | **Casual, cap backwards** | Weekend warrior | t-shirt + jeans |
| 3 | **Race suit zipped, helmet on, visor up** | Pro look | black-and-blue suit |
| 4 | **Open-face helmet + retro gloves** | Vintage | classic Nomex suit, leather gloves |
| 5 | **Female driver, race suit, helmet under arm** | Pro female | red-and-white suit |
| 6 | **Female driver, casual, ponytail** | Weekend warrior, female | t-shirt + leggings |
| 7 | **Older driver, greyed hair, instructor look** | Mentor archetype | charcoal suit, well-worn |
| 8 | **Hooded mystery driver** ⛔ LOCKED | Late-game unlock | hoodie up, face shadowed |

### Avatar 8 unlock condition

Driver level 20 + 1 personal best at every Sonoma corner. Pure
aspirational unlock — gives the late-game progression a visible carrot.

### Avatar animations (per slot)

Same five-frame minimum as `02-sprite-sheet-spec.md`:
- `idle_0/1` — 2-frame breathing on the trainer card
- `helmet_on` — used on the HUD top-status
- `victory` — fist pump, stage clear PB
- `disappointed` — head down, stage clear all-goals-missed

## NPCs in the garage hub

Beyond the player's chosen coach, the garage hub has ambient NPCs that
make the space feel inhabited. None of them have dialogue or gameplay
function — they're set dressing.

| NPC | Sprite | Behaviour |
|---|---|---|
| **Pit crew member** | `crew_walk` 4-frame cycle, generic | Walks back and forth across the bottom of the garage every ~45 s |
| **Mechanic** | `mechanic_idle` 2-frame, generic | Stands by the toolbox, occasionally hands moving |
| **Tire stack** | `tires_static` 1-frame | Decoration |
| **Hanging fluorescent light** | `lamp_idle` 2-frame, slight flicker at 0.5 Hz | Decoration |

These NPCs share one packed sheet, `garage_npcs.png`, which is generated
once and never updated.

## The mentor's daily greeting rotation

When the player enters the garage hub, the chosen coach speaks one of
~10 rotating greetings. Different per coach. T-Rod's set:

```
"Welcome back, kid. Today we drive."
"Good to see you. Engine's warm."
"Suit up. We've got work."
"How are the tires? Let's go."
"Late start. Fine — we'll work fast."
"Sun's out. Time to drive."
"Same as yesterday — distance is king."
"You ready? Track's clear."
"Let's see what you remembered."
"Coffee's on. Then we drive."
```

Greeting picks weighted by:
- Time of day (morning vs evening rotates)
- Previous session result (good → upbeat, bad → reset-style)
- Weather phase via `GET /track/weather?hour_local=…`
- Days since last session (>3 → "haven't seen you in a while")

All ten phrases per coach are pre-rendered TTS clips per
[`06-audio-design.md`](06-audio-design.md), so the greeting is instant
with no LLM call.

## Voice generation pipeline

For each coach, generate a high-quality TTS clip per canonical phrase
(~50 phrases per coach) using:

```bash
# Pseudo-command — actual implementation in pitwall-web/scripts/voice-bake.ts
voice-bake --coach trod \
           --voice "experienced-instructor-american-male-50s" \
           --phrases data/voices/trod-phrases.json \
           --out pitwall-web/public/audio/coaches/trod/
```

Voices we'd target (TTS-vendor-agnostic; recommendation):

| Coach | Voice character | TTS engine |
|---|---|---|
| T-Rod | American male, 50s, gravelly | gemini-2.5-flash-tts (or whatever ships best on Termux) |
| Bentley | British male, 50s, warm | same |
| Drill | American male, 40s, intense | same |
| Calm | Asian-American female, 30s, calm | same |
| Buddy | Latin-American male, 28, friendly | same |

50 phrases × 5 coaches = 250 clips. Each ~2-3 s. Cached on the device.

## Coach affinity (game mechanic)

Each session adds points to the active coach's affinity meter. Affinity
levels unlock cosmetic perks (alt portrait, new dialogue greetings) — no
gameplay-affecting unlocks. Pure flavour.

| Affinity level | Sessions to reach | Unlocks |
|---|---|---|
| 1 — Stranger | start | base 10 greetings |
| 2 — Acquainted | 5 sessions | +5 greetings, daily-rotation widens |
| 3 — Trusted | 15 sessions | unlock alt portrait variant |
| 4 — Tight | 50 sessions | unlock seasonal greetings (rain, dawn, etc.) |
| 5 — Family | 100 sessions | T-Rod's "kid" → uses driver's actual name |

Computed client-side from save slot's session count with that coach
selected. Persists across saves on the same device.

## Coach emotions (Gemma-controlled)

Each coach renders 12 distinct emotions, played as a 2-frame breathing
loop + a 2-frame talking variant. The active emotion is decided by
the LLM when it generates text, or by a static lookup for canonical
phrases. Full taxonomy in [`10-coach-emotions.md`](10-coach-emotions.md).

The 12 emotions: `neutral`, `thinking`, `analyzing`, `encouraging`,
`proud`, `excited`, `serious`, `concerned`, `disappointed`, `intense`,
`relaxed`, `tired`.

Per-coach the *expression* of each emotion differs — Bentley's
`disappointed` is a slight head-tilt + lowered clipboard; Drill
Sergeant's is a hard frown + crossed arms. But the mapping
emotion → coaching context stays identical across coaches.

## What coach swaps look like

When the player opens `screens/05-coach-select.md` and picks a different
coach:

1. Old coach speaks one farewell line (rotates through ~3)
2. Wipe transition
3. New coach speaks one greeting line (rotates through ~10)
4. Player returns to garage hub

Affinity is per-coach and persistent — switching back later picks up
where you left off, with the same affinity level, same unlocked
greetings.

## Related

- [`02-sprite-sheet-spec.md`](02-sprite-sheet-spec.md) — frame inventory
- [`05-coach-select.md`](screens/05-coach-select.md) — the picker screen
- [`06-audio-design.md`](06-audio-design.md) — voice generation pipeline
- [ADR-017 — Three-tier coach architecture](../adr/017-three-tier-coach-architecture.md)
  — coaches share one engine, differ in prompt/voice
