# pitwall-web — design journey

> **Status: pre-implementation design specification.** The PWA shipped
> under `src/pwa/` per ADR-022. These docs are preserved as design
> history and decision provenance — they are no longer the source of
> truth for what's built. Cross-check against `src/pwa/` before
> treating any claim here as current behaviour.

Everything we've decided about the Vue PWA lives here. Read this README
first, then walk the docs in numerical order. Screens get their own files
under `screens/`. Reference assets, prompts, and the sprite-sheet
inventory are under `assets/`. Strategy + scratch thinking that didn't
fit into a finalised doc is in `journal/`.

## The pitch (one paragraph)

It's an RPG where the dungeon IS the racetrack. Sessions are dungeons.
Lap times are XP. Medals are loot. Goals are quests. T-Rod is Professor
Oak. The visual reference is **modern indie pixel art** — Stardew Valley
proportions and palette range, not pure GBA — running at integer scales
on a 480×320 logical grid. The structural reference is the GBA-era
career-mode racing arcade: cups, world maps, pre-stage briefings,
post-stage score screens, save slots. Everything serious about the
underlying telemetry stays serious; the wrapper is a game.

## Why

Two reasons that look like one:

1. **Lower the activation energy on engaging with analytics.** A driver
   who'd never sit through a Tukey-box-plot of throttle distribution
   *will* sit through "Lap 4 — 86 points · GREAT TRAIL BRAKE · Coach
   approves." Same numbers, different envelope.
2. **Make the trust UX from `docs/ux.md` tangible.** Coaching confidence
   becomes a sprite emotion. Capability gating becomes a "you can't equip
   that coach yet" message. Disabled rules become locked-room icons. The
   abstract gets a face.

## How to read this folder

- **Foundation** (00–03): the design language. Read first.
  - [`00-design-philosophy.md`](00-design-philosophy.md) — the pitch in
    full, with reference games and what we explicitly aren't doing.
  - [`01-visual-language.md`](01-visual-language.md) — palette derived
    from the actual sprite sheet, typography, frame system, transitions.
  - [`02-sprite-sheet-spec.md`](02-sprite-sheet-spec.md) — frame taxonomy,
    row-by-row mapping of the user-supplied reference sheet, what to
    generate next via nano-banana.
  - [`03-character-bible.md`](03-character-bible.md) — T-Rod + 4 other
    coaches + 8 driver avatars; voice, motivation, animation states.
  - [`10-coach-emotions.md`](10-coach-emotions.md) — **Gemma-controlled
    emotion taxonomy** (12 emotions × per-coach sprites). Drives the
    coach avatar animation everywhere the LLM speaks.

- **Systems** (04–09): the engineering shape underneath the art. Read
  before writing components.
  - [`04-state-architecture.md`](04-state-architecture.md) — Pinia
    stores, save-slot schema, IndexedDB + OPFS persistence.
  - [`05-routing-map.md`](05-routing-map.md) — Vue Router routes,
    transitions, deep-link rules.
  - [`06-audio-design.md`](06-audio-design.md) — chiptune track list,
    SFX inventory, TTS pipeline.
  - [`07-controls.md`](07-controls.md) — D-pad-on-touch, keyboard,
    gamepad. Every screen's input map.
  - [`08-animation-spec.md`](08-animation-spec.md) — sprite frame rates,
    screen transitions, easing curves.
  - [`09-tech-stack.md`](09-tech-stack.md) — Vue 3 + Vite + Tailwind +
    DuckDB-Wasm + Howler + service worker. Why each piece, what it
    replaces, what version.
  - [`11-navigation-map.md`](11-navigation-map.md) — **the god mermaid**.
    Full overview + zoomed subgraphs (session loop, hub radial,
    analytics radial, overlays, Coach Speaks Modal usage) + per-screen
    incoming/outgoing reference table. Single source of truth for
    "where does this button go?"

- **Screens** (under `screens/`): one doc per screen. Each one has
  the same six sections — purpose, wireframe, states, sprite usage,
  Vue component breakdown, API endpoints + audio cues. Walk them in
  player-journey order:

  *Boot + identity*
  - [`00-title.md`](screens/00-title.md) · PRESS START
  - [`01-save-select.md`](screens/01-save-select.md) · pick driver slot
  - [`02-onboarding.md`](screens/02-onboarding.md) · new driver wizard

  *Hub + navigation*
  - [`03-garage-hub.md`](screens/03-garage-hub.md) · main menu / overworld
  - [`04-trainer-card.md`](screens/04-trainer-card.md) · stats + medals
  - [`05-coach-select.md`](screens/05-coach-select.md) · pick mentor
  - [`06-world-map.md`](screens/06-world-map.md) · track select
  - [`12-quest-log.md`](screens/12-quest-log.md) · active goals + medals
  - [`13-settings.md`](screens/13-settings.md) · garage settings

  *Session loop*
  - [`15-pit-stall-setup.md`](screens/15-pit-stall-setup.md) · connect car + live state ★
  - [`07-pre-brief.md`](screens/07-pre-brief.md) · goals + weather + briefing
  - [`37-track-walk.md`](screens/37-track-walk.md) · ★★★ interactive Sonoma layout, per-corner coach commentary, historical review
  - [`08-on-track-hud.md`](screens/08-on-track-hud.md) · live driving
  - [`09-cool-down.md`](screens/09-cool-down.md) · per-corner score chimes
  - [`10-stage-clear.md`](screens/10-stage-clear.md) · post-session score

  *Analytics (data dungeons)*
  - [`16-analysis-hub.md`](screens/16-analysis-hub.md) · entry to analytics ★
  - [`17-lap-times-hall.md`](screens/17-lap-times-hall.md) · lap_time_table + distribution + ideal + sectors
  - [`18-corner-mastery.md`](screens/18-corner-mastery.md) · /corners + throttle box + classification + brake/accel
  - [`19-straights-and-speed.md`](screens/19-straights-and-speed.md) · straight_line_speed
  - [`20-track-atlas.md`](screens/20-track-atlas.md) · elevation + markers + danger zones + weather
  - [`21-driver-evolution.md`](screens/21-driver-evolution.md) · evolution + profile
  - [`22-pedal-profile.md`](screens/22-pedal-profile.md) · pedal_behavior

  *Overlays + modals (not full routes)*
  - [`_coach-speaks-modal.md`](screens/_coach-speaks-modal.md) · ★★ canonical "LLM is talking" pattern
  - [`23-pause-quick-menu.md`](screens/23-pause-quick-menu.md) · Start-button menu
  - [`24-achievement-toast.md`](screens/24-achievement-toast.md) · slide-in medal/level-up notice
  - [`25-loading-screen.md`](screens/25-loading-screen.md) · cold-boot bridge to title
  - [`26-bridge-offline.md`](screens/26-bridge-offline.md) · banner + diagnostic when bridge dies
  - [`33-notification-center.md`](screens/33-notification-center.md) · async-event inbox
  - [`34-tutorial-overlay.md`](screens/34-tutorial-overlay.md) · first-time-user hints
  - [`35-daily-streak.md`](screens/35-daily-streak.md) · "DAY N STREAK" celebration

  *Power-user*
  - [`27-hardware-detail.md`](screens/27-hardware-detail.md) · live signal table + DBC inspector
  - [`28-coach-codex.md`](screens/28-coach-codex.md) · Pokédex of phrases heard
  - [`29-calibration.md`](screens/29-calibration.md) · 10 s sensor verification
  - [`30-sql-console-fullscreen.md`](screens/30-sql-console-fullscreen.md) · Monaco + DuckDB-Wasm
  - [`31-comparison-view.md`](screens/31-comparison-view.md) · two-session diff (post-MVP)
  - [`32-live-spectator.md`](screens/32-live-spectator.md) · read-only HUD mirror (post-MVP)
  - [`36-goals-library.md`](screens/36-goals-library.md) · custom goal editor

  *Other*
  - [`11-replay.md`](screens/11-replay.md) · video × telemetry
  - [`14-end-of-day.md`](screens/14-end-of-day.md) · session-stack farewell

  ★ = added 2026-04-29 in response to "we also need a setup screen +
  all analytics that consume the endpoints we have."
  ★★ = canonical pattern that every LLM moment uses.

- **Assets** (under `assets/`): sprite naming convention, reference-sheet
  inventory, nano-banana prompt cookbook.

- **Journal** (under `journal/`): in-flight thinking that didn't fit
  into a finalised doc. Don't reference these from production code.

## What this design *isn't*

- **Not a real game.** No fail states, no XP grinding for grinding's
  sake, no microtransactions. The "game" wrapper exists to make
  analytics digestible.
- **Not GBA-emulated.** We're not building a webGBA — we're using the
  *visual language* of late-GBA / early-DS-era racing RPGs to make a
  modern PWA feel game-shaped.
- **Not blocking the bridge.** All of this is additive to `pitwall`. If
  the PWA never ships, the bridge is still complete and useful.

## Status

Drafted 2026-04-29 (the same day as ADR-016 + ADR-017). Implementation
hasn't started — the `pitwall-web/` repo doesn't exist yet. This folder
is the design artefact that unblocks scaffolding it.

When implementation begins, treat these docs as the contract. Update
them when the contract changes; don't drift quietly.

## Related

- [ADR-013 — Frontend visualises, backend reasons](../adr/013-frontend-backend-boundary.md)
- [ADR-016 — USB-CAN ingest + Vue PWA frontend](../adr/016-can-bus-ingest-and-frontend-pivot.md)
- [ADR-017 — Three-tier coach architecture](../adr/017-three-tier-coach-architecture.md)
- [`docs/ux.md`](../ux.md) — underlying UX principles this builds on
- [`docs/pitwall-web-design.md`](../pitwall-web-design.md) — the original
  GBA-style sketch this folder supersedes (kept for history; this folder
  is the canonical version).
