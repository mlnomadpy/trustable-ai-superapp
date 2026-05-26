# Pitwall PWA — Implementation State

**Status:** Shipped
**Path:** `src/pwa/`
**Audience:** Anyone touching the Vue PWA. The earlier GBA / pixel-art
spec in this file has been retired — the shipped app is a cyberpunk-
themed cockpit tool, not a Pokemon clone. The trust UX principles
documented in [`docs/ux.md`](ux.md) still apply.

---

## Stack

| Layer | Pick | Notes |
|---|---|---|
| Framework | Vue 3.5 + `<script setup>` + Vite | |
| State | Pinia 3 | One store per FSD entity |
| Styling | Tailwind 4 (`@tailwindcss/vite`) | Design tokens via CSS variables; `src/app/styles/` |
| Routing | Vue Router 4 | History mode; `requiresSave`, `wipe`, `performance`, `allowPause` meta |
| PWA | Workbox via `vite-plugin-pwa` | Manifest in `vite.config.ts`; icons in `public/icons/` |
| Charts | Chart.js 4 + `chartjs-plugin-zoom` | Wrapped by `shared/ui/charts/CyberLineChart.vue` |
| SQL analytics | `@duckdb/duckdb-wasm` | Worker bundled same-origin (no jsdelivr CORS) |
| Maps | Leaflet 1.9 | Lazy-loaded; Analysis Hall + Track Atlas |
| Voice | Web Speech API (STT + TTS) | `shared/lib/voice.ts` wrapper, graceful no-op when absent |

---

## FSD layout

```
src/pwa/src/
├── app/             ← App.vue, router/, styles/, main.ts
├── pages/           ← 27 page routes, lazy-loaded (title is eager)
├── widgets/         ← composite UI (HUD bits, install prompt, pause, dialogue …)
├── features/        ← coach-interaction, audio-playback, …
├── entities/        ← analysis, session, coach, lap-time, quest, save, leaderboard
└── shared/          ← api/, lib/, ui/{core,charts}, types/
```

`shared/ui/core/` is the design system entry point — every page imports
its building blocks from there. See [Design tokens](#design-tokens)
below.

---

## Design tokens

The cyberpunk skin is a small, opinionated component set. All cockpit
chrome composes from these:

| Token | Purpose |
|---|---|
| `CyberPanel` | Bordered panel with optional animated edge |
| `CyberTile` | Big tappable tile for hub grids |
| `CyberSplitView` | Two-pane page layout (list ↔ detail) |
| `CyberTabs` | Tab strip (used by 9 pages, see below) |
| `CyberCheckbox` | Touch-friendly checkbox |
| `CyberButton` | Primary / secondary / danger button variants |
| `CyberConfirmDialog` | Y/N destructive-action confirm |
| `CyberModal` | Generic modal shell |
| `CyberKeyboard` | On-screen keyboard for name entry / search |
| `Frame` | 9-slice border frame (legacy from the pixel skin, still used) |
| `CyberDataGrid`, `CyberMedal`, `CyberRadarChart`, `CyberGauge`, … | Analytics primitives |

Component count in `shared/ui/core/`: **~36 components**. Charts
(`shared/ui/charts/`) and HUD widgets (`widgets/hud/`) layer on top.

---

## Pages

27 page directories under `src/pwa/src/pages/`, with 33 routes in
`src/pwa/src/app/router/index.ts` (the `/` title is eager; everything
else lazy):

```
/                       Title
/save                   Save slot select
/onboarding/:step       Onboarding wizard
/garage                 Garage hub
/garage/setup           Car setup
/garage/trainer         Trainer card
/garage/coach           Coach select
/garage/coach/bios      Coach bios
/garage/pit-stall       Pit stall (paddock dashboard)
/garage/pit-stall/hardware  Hardware detail
/pit-stall/live         Live pit wall
/garage/quests          Quest log
/garage/sponsors        Sponsor contracts
/garage/analysis        Analysis Hall (tabbed)        ← see docs/analysis-hall.md
/analysis/lap-times     Lap times hall
/analysis/compare       Comparison view
/analysis/corners       Corner mastery
/analysis/straights     Straights & speed
/analysis/track         Track walk
/analysis/atlas         Track atlas
/analysis/evolution     Driver evolution
/analysis/pedals        Pedal profile
/analysis/ghosts        Ghost manager
/analysis/replay        Telemetry replay
/analysis/sql           SQL console
/briefing               Pre-brief
/hud                    On-track HUD                  ← see docs/on-track-hud.md
/stage-clear            Stage clear (post-session)
/calibration            Calibration
/notifications          Notification center
/settings               Settings
/end-of-day             End of day
/leaderboard            Global leaderboard
```

---

## Pages newly tabbed (Pixel 10 landscape)

The `CyberTabs` widget is the standard navigation pattern inside
content-dense pages. The following pages now use it:

```
src/pwa/src/pages/settings/Settings.vue
src/pwa/src/pages/garage-hub/CarSetup.vue
src/pwa/src/pages/calibration/Calibration.vue
src/pwa/src/pages/hardware-detail/HardwareDetail.vue
src/pwa/src/pages/pit-stall/PitStall.vue
src/pwa/src/pages/pit-stall/LivePitWall.vue
src/pwa/src/pages/quest-log/QuestLog.vue
src/pwa/src/pages/quest-log/ui/CoachCodexMode.vue
src/pwa/src/pages/end-of-day/EndOfDay.vue
src/pwa/src/pages/pre-brief/PreBrief.vue
src/pwa/src/pages/trainer-card/TrainerCard.vue
src/pwa/src/pages/analysis-hub/AnalysisHub.vue
```

Each binds `1-9` keys to tab indices and routes `←/→` arrows to
in-page cycling per [`docs/ux.md`](ux.md)'s unified key contract.

---

## Bridge integration

Single typed client at `src/pwa/src/shared/api/bridge.ts` plus a
`bridgeStore` for `/health` polling. The PWA never talks to BLE / USB
/ DuckDB-server directly — everything routes through the bridge.

About **35 unique HTTP endpoints** are currently consumed by the PWA
across stores and pages (out of ~71 declared via `@bp.route` on the
backend). Notable wires:

- `/health`, `/sessions`, `/session/<sid>`, `/session/<sid>/laps`
- `/session/<sid>/lap_time_table`, `/session/<sid>/ideal_lap`
- `/session/<sid>/scorecard`, `/session/<sid>/highlights`,
  `/session/<sid>/incidents`, `/session/<sid>/eob`
- `/session/<sid>/pedal_behavior`, `/session/<sid>/friction_circle`,
  `/session/<sid>/hustle_map`, `/session/<sid>/corners`,
  `/session/<sid>/sector_times`, `/session/<sid>/capabilities`,
  `/session/<sid>/stats`
- `/session/start`, `/session/<sid>/end`
- `/session/replay/start`, `/session/replay/stop`,
  `/session/replay/status`
- `/coach/brief`, `/coach/debrief`, `/coach/ask`, `/coach/ask/end`,
  `/coach/agents`, `/coach/traces`, `/coach/concepts`
- `/driver/<id>/profile`, `/driver/<id>/evolution`
- `/track/markers`, `/track/danger_zones`,
  `/track/<id>/elevation`, `/track/weather`
- `/medals`, `/insights`, `/notifications`
- `/diagnostics/can`, `/diagnostics/llm_friction`

SSE channels:

- `/cues/stream?session_id=<sid>` — coaching cues
- `/telemetry/stream?session_id=<sid>` — frames

Both go through `shared/lib/useReconnectingSSE.ts` so a transient
bridge drop reconnects without surfacing a banner mid-session
(ADR-009).

---

## No-fake-fallback sweep

A deliberate sweep removed every "looks-real" placeholder across the
PWA:

| Surface | Fake removed |
|---|---|
| `entities/quest/model/medalStore.ts` | `_generateProgressMedals` — now an honest empty state |
| `entities/session/model/telemetryStore.ts` | `startSimulation()` (Math.sin/cos shim) deleted |
| `pages/garage-hub/CarSetup.vue` | Wired to real `/cars` endpoint |
| `pages/track-atlas/TrackAtlas.vue` | Wired to `/track/markers`, `/track/danger_zones`, `/track/<id>/elevation`, `/track/weather` |
| `pages/lap-times-hall/LapTimesHall.vue` | Type drift against the real `LapTime` shape fixed |
| `pages/stage-clear/StageClear.vue` | Real `/session/<sid>/scorecard` + `/coach/debrief` |
| `pages/driver-evolution/DriverEvolution.vue` | Fake median fallback dropped |
| `pages/trainer-card/TrainerCard.vue` | Wired to `/driver/<id>/profile` |
| `pages/pre-brief/PreBrief.vue` | Preflight pills bound to real `/health.can.connected` + `frames_total` |
| `pages/pit-stall/ui/LiveCarState.vue` | Coaches panel from real `/coach/agents` + `/session/<sid>/capabilities` |
| `pages/garage-hub/GarageHub.vue` | Tile counts from real stores |
| Many smaller pages | Type drift, hardcoded counts, fake graphs removed |

If the bridge can't answer, the surface degrades to a labelled empty
state ("DATA UNAVAILABLE — bridge offline?") instead of pretending.

---

## Globally mounted

In `App.vue`:

- `BridgeOfflineBanner` — slim banner when `/health` polling fails
- `PauseMenu` — toggled by `P` on routes with `meta.allowPause`
- `CoachSpeaksModal` — coach-driven dialogue interrupts
- `UpdateToast` — service-worker update prompt
- `TransitionWipe` — route-change wipe overlay
- `DiagnosticBar` — LLM-friction tile (real `/diagnostics/llm_friction`)
- `FullscreenToggle` — persists choice via
  `localStorage.fullscreenPreferred`
- `InstallPrompt` — captures `beforeinstallprompt`, sticky bottom
  banner, 7-day dismiss cooldown; mounted at the top level so any page
  can install. Icons + manifest in `vite.config.ts` and
  `public/icons/{icon,icon-maskable}-{192,512}.png` plus
  `apple-touch-icon-180.png`.
- `ParticleBackground` — disabled on `meta.performance` routes (HUD)

A persistent **portrait-warning** overlay appears on portrait viewports
— the app is landscape-only on phone (Pixel 10 ≈ 2424×1080 px).

---

## SSE reconnect-aware

`shared/lib/useReconnectingSSE.ts` is the canonical SSE wrapper. It
holds the EventSource handle, retries with exponential backoff on
`onerror`, and exposes a single `close()` for the page to call in
`onUnmounted`. Stores (`cueStore`, `telemetryStore`,
`notificationStore`) own a single connection scoped to the active
`sid` and re-open on `sid` flips.

---

## ADR-022 compliance

ADR-022 mandates that pages render real data or an honest empty
state, never invented data. The sweep above brought every page into
compliance; the one remaining caveat is `/coach/ask` returning 503
when ADK isn't installed on the bridge — see [Voice loop](#voice-loop).

---

## Voice loop

`shared/lib/voice.ts` wraps the Web Speech API (SpeechSynthesis + the
prefix-aware SpeechRecognition). `useVoiceConversation`
(`entities/coach/model/useVoiceConversation.ts`) composes the
listen → /coach/ask → speak loop. `CoachVoiceButton`
(`widgets/coach-voice-button/CoachVoiceButton.vue`) is the FAB used
by `AskCoachMode` (Quest Log) and now by the On-Track HUD (bottom-
right, hotkey `M`).

On the phone, `/coach/ask` returns **503** when ADK isn't installed
yet — the voice button surfaces the error and the loop stays silent
until the backend is wired or an alternative path is added.

---

## Related docs

- [`docs/ux.md`](ux.md) — UX principles + unified key contract
- [`docs/analysis-hall.md`](analysis-hall.md) — Analysis Hall design
- [`docs/on-track-hud.md`](on-track-hud.md) — On-Track HUD design
- [`docs/api.md`](api.md) — bridge endpoint reference
- [`docs/adr/`](adr/) — architectural decisions (013 frontend/backend
  boundary, 015 telemetry sink, 016 USB-CAN + PWA pivot, 022 honest
  empty states)
