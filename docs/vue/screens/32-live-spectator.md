# 32 — Live Spectator

Read-only mirror of the on-track HUD. For a passenger or external
display (laptop on the same Wi-Fi). Reached from Settings → "OPEN
SPECTATOR LINK" which generates a shareable URL.

## Purpose

Verb: **Spectate.** Watch the live driving session from another
device without interfering with it.

## Wireframe

Identical to `08-on-track-hud.md` but with two changes:

```
┌────────────────────────────────────────────────────────────┐
│  LAP 3 / 8     1:47.2  (-0.4s pb)         ░ READ ONLY ░    │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│   ╔════╗                                          ╔════╗   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║▓▓▓▓║         ░░░░░░░░░░░░░░░░░                ║░░░░║   │
│   ║▓▓▓▓║         ░░  TRACK MAP   ░░                ║░░░░║   │
│   ║▓▓▓▓║         ░░░░░ ▶ pos ░░░░░                ║░░░░║   │
│   ║▓▓▓▓║         ░░░░░░░░░░░░░░░░░                ║░░░░║   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ║▓▓▓▓║         T7 ENTRY  82 km/h                ║░░░░║   │
│   ║▓▓▓▓║                                          ║░░░░║   │
│   ╚════╝                                          ╚════╝   │
│   GRIP  87%                                  OVER   0%     │
│                                                            │
│   ░░░░░░░░░░░░░ DASHCAM (optional toggle) ░░░░░░░░░         │
│   ░░░░░░ video panel · live · 720p / 30 fps ░░░░░░░         │
│                                                            │
│ ░ T-ROD: "ROLL THE BRAKE TO THE APEX"                      │
│                                                            │
│ READ ONLY · No input enabled · ░ paired                    │
└────────────────────────────────────────────────────────────┘
```

Differences from primary HUD:
- "READ ONLY" badge top-right
- All input disabled (touch ignored, no D-pad)
- Optional dashcam panel below the HUD
- Bottom hint replaced with "READ ONLY · paired" connection indicator

## Generating a spectator link

From `13-settings.md` → "OPEN SPECTATOR LINK":

1. Settings asks the bridge for a one-time spectator token
   (`POST /spectator/token` returns `{ token, expires_at }`)
2. PWA renders a QR code + short URL
   `http://<pixel-ip>:8765/spectator?token=<t>`
3. Spectator device scans QR → opens the URL → loads the same
   `pitwall-web` build but routes to `/spectator/<sid>` with the token
4. Bridge enforces token: read-only access to `/cues/stream`,
   `/session/<sid>`, `/session/<sid>/sync`. Tokens expire after 4 h
   or when the primary session ends

## States

| State | Trigger | Behaviour |
|---|---|---|
| `pairing` | URL loaded | Validate token; subscribe to SSE; show "PAIRING…" briefly |
| `live` | SSE active | Mirror HUD; updates at native cue rate |
| `disconnected` | SSE drops | Banner: "RECONNECTING…"; auto-retry every 5 s |
| `session-ended` | Bridge sends end-event | Spectator screen freezes on last frame; shows "SESSION ENDED" |
| `token-expired` | 401 from bridge | Friendly error: "Ask the driver to reopen the spectator link." |

## Sprite usage

Same as `08-on-track-hud.md` plus:

| Sprite | Where | Animation |
|---|---|---|
| `read_only_badge` | Top-right, 64×16 | Static |
| Pairing indicator | Bottom-right, 16×16 | 2-frame pulse at 1 Hz |

Coach badge same as HUD — emotion driven by SSE cue.

## Vue component

```vue
<!-- pitwall-web/src/views/LiveSpectator.vue -->
<template>
  <div class="viewport hud-fullscreen spectator">
    <HudTopBar :lap="lap" :time="lapTime" :pb-delta="pbDelta" />
    <ReadOnlyBadge />
    <GripBar :pct="frictionPct" />
    <TrackMap track="sonoma" :pos-m="distanceM" :heading="heading" />
    <NextCornerCard :corner="upcoming" />
    <OverBar :pct="overPct" />
    <CueBand :cue="activeCue" :read-only="true" />
    <DashcamPanel v-if="dashcamEnabled" :stream="dashcamUrl" />
    <ConnectionStatus :state="pairingState" />
  </div>
</template>
```

The CueBand component takes a `read-only` prop — visually identical
but disables tap interactions.

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `POST /spectator/token` (proposed) | Generates a session-scoped read-only token |
| `GET /spectator/<sid>?token=<t>` (proposed) | Validates + opens SSE |
| SSE `/cues/stream?token=<t>` | Live cues, same as primary |
| `GET /session/<sid>/dashcam.m3u8?token=<t>` (proposed) | HLS or WebRTC dashcam stream — DEFERRED past MVP |

## Audio cues

Same as on-track HUD, **muted by default** (spectators usually have
their own audio context or are talking to the driver). Player can
unmute from a small button in the top-right.

## Input map

All inputs **ignored** in spectator mode. The screen is intentionally
non-interactive. The only exception:

| Input | Action |
|---|---|
| Tap top-right mute icon | Toggle audio mute |
| (No other inputs respected) | — |

This is intentional. A passenger fiddling with the spectator screen
must not affect the driver's experience.

## Edge cases

- **Spectator opens link before session starts** — show pairing
  spinner + "WAITING FOR DRIVER" until SSE delivers first cue
- **Driver pauses session** — spectator stays on the last frame +
  shows "PAUSED" badge
- **Spectator network drops** — auto-retry every 5 s; shows
  reconnecting state
- **Token revoked while open** — friendly screen explaining why,
  with "ask for a new link" hint
- **Multiple spectators on the same token** — allowed; bridge
  doesn't restrict to one viewer

## Related

- [`08-on-track-hud.md`](08-on-track-hud.md) — primary HUD this mirrors
- [`13-settings.md`](13-settings.md) — where the spectator link is generated
- DEFERRED to post-Sonoma per design notes — not on the May 23 critical path
