# 11 — Navigation map

The god mermaid. Every screen, every transition, every overlay,
all visualised. Read top-to-bottom: full overview first, then zoomed
subgraphs for the dense parts.

Use this as the quick-reference when wiring `router.ts` or asking
*"where does the B button on screen X take me?"*

## Legend

```mermaid
flowchart LR
  classDef boot     fill:#1a1d2e,stroke:#3d4458,color:#f8f8f0
  classDef hub      fill:#2a2f4a,stroke:#3d4458,color:#f8f8f0
  classDef session  fill:#5d4a1a,stroke:#8a6e3a,color:#f8f8f0
  classDef analytic fill:#1a3a52,stroke:#4a6e8a,color:#f8f8f0
  classDef overlay  fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0
  classDef power    fill:#5d1a3a,stroke:#8a3a5e,color:#f8f8f0
  classDef pattern  fill:#2e5d3a,stroke:#5a8a6e,color:#f8f8f0,stroke-dasharray:5 3

  L1[Boot]:::boot
  L2[Hub + nav]:::hub
  L3[Session loop]:::session
  L4[Analytics]:::analytic
  L5[Power-user]:::power
  L6[Overlay / modal]:::overlay
  L7[Reusable pattern]:::pattern
```

Solid arrow = forward navigation. Dashed = back navigation. Dotted =
auto-transition (state-driven). Arrow labels are the trigger
(`A` button, `B` button, `Start`, or specific event).

## Full overview — every full route

This shows every routed screen (overlays are in a separate diagram
below to keep it legible).

```mermaid
flowchart TD
  classDef boot     fill:#1a1d2e,stroke:#3d4458,color:#f8f8f0
  classDef hub      fill:#2a2f4a,stroke:#3d4458,color:#f8f8f0
  classDef session  fill:#5d4a1a,stroke:#8a6e3a,color:#f8f8f0
  classDef analytic fill:#1a3a52,stroke:#4a6e8a,color:#f8f8f0
  classDef power    fill:#5d1a3a,stroke:#8a3a5e,color:#f8f8f0

  %% Boot path
  S25[25 Loading]:::boot
  S00[00 Title]:::boot
  S01[01 Save Select]:::boot
  S02[02 Onboarding]:::boot

  %% Hub
  S03[03 Garage Hub]:::hub
  S04[04 Trainer Card]:::hub
  S05[05 Coach Select]:::hub
  S06[06 World Map]:::hub
  S12[12 Quest Log]:::hub
  S13[13 Settings]:::hub
  S28[28 Coach Codex]:::hub

  %% Session loop
  S15[15 Pit Stall Setup]:::session
  S07[07 Pre-Brief]:::session
  S37[37 Track Walk]:::session
  S08[08 On-Track HUD]:::session
  S09[09 Cool-Down]:::session
  S10[10 Stage Clear]:::session
  S14[14 End of Day]:::session
  S29[29 Calibration]:::session

  %% Analytics
  S16[16 Analysis Hub]:::analytic
  S17[17 Lap Times Hall]:::analytic
  S18[18 Corner Mastery]:::analytic
  S19[19 Straights & Speed]:::analytic
  S20[20 Track Atlas]:::analytic
  S21[21 Driver Evolution]:::analytic
  S22[22 Pedal Profile]:::analytic
  S11[11 Replay]:::analytic
  S31[31 Comparison View]:::analytic

  %% Power-user
  S27[27 Hardware Detail]:::power
  S30[30 SQL Console]:::power
  S32[32 Live Spectator]:::power
  S36[36 Goals Library]:::power

  %% Boot
  S25 -->|auto, < 1.5 s| S00
  S00 -->|A / Start| S01
  S01 -->|A on filled slot| S03
  S01 -->|A on empty slot| S02
  S02 -->|step 7 done| S03

  %% Hub radial
  S03 -->|TRACK| S06
  S03 -->|PIT STALL| S15
  S03 -->|TRAINER CARD| S04
  S03 -->|COACHES| S05
  S03 -->|QUEST LOG| S12
  S03 -->|SETTINGS / Start| S13
  S03 -->|ANALYSIS| S16

  S04 -->|◆ EVOLUTION| S21
  S05 -->|swap confirmed| S03
  S12 <-->|tab| S28
  S13 -->|RECALIBRATE| S29
  S13 -->|OPEN SPECTATOR| S32

  %% Session loop
  S06 -->|A on Sonoma pin| S07
  S06 -->|STUDY TRACK| S37
  S07 -->|WALK THE TRACK| S37
  S37 -->|B / SAVE GOAL| S07
  S07 -->|+ CUSTOM GOAL| S36
  S36 -->|SAVE| S07
  S07 -->|CONFIRM| S08
  S07 -->|pre-flight ✗| S15
  S08 -->|car stops, t < 90 s| S09
  S09 -->|t > 90 s, paddock| S10
  S10 -->|A · CONTINUE| S03
  S10 -->|A · REPLAY| S11
  S03 -->|Start → END SESSION| S14
  S14 -->|night fade| S00

  %% Pit Stall
  S15 -->|◆ HARDWARE INFO| S27
  S27 -->|B| S15
  S15 -->|chain ✓| S07

  %% Analytics radial
  S16 -->|LAP TIMES HALL| S17
  S16 -->|CORNER MASTERY| S18
  S16 -->|STRAIGHTS & SPEED| S19
  S16 -->|TRACK ATLAS| S20
  S16 -->|DRIVER EVOLUTION| S21
  S16 -->|PEDAL PROFILE| S22
  S16 -->|◆ SQL CONSOLE| S30
  S17 -->|tap a lap| S11
  S17 -->|COMPARE| S31
  S31 -->|A · OPEN REPLAY| S11
  S20 -->|tap corner| S37

  %% Back arrows (representative; B always goes to parent)
  S04 -->|B| S03
  S05 -->|B| S03
  S06 -->|B| S03
  S12 -->|B| S03
  S13 -->|B| S03
  S15 -->|B| S03
  S16 -->|B| S03
  S17 -->|B| S16
  S18 -->|B| S16
  S19 -->|B| S16
  S20 -->|B| S16
  S21 -->|B| S16
  S22 -->|B| S16
  S30 -->|B| S16
  S31 -->|B| S17
  S29 -->|B| S13
  S37 -->|B| S07
  S11 -->|B| S03
```

## Zoom: session loop

The hot path of the app — every track day touches this chain.

```mermaid
flowchart LR
  classDef session fill:#5d4a1a,stroke:#8a6e3a,color:#f8f8f0
  classDef sup     fill:#5d1a3a,stroke:#8a3a5e,color:#f8f8f0
  classDef hub     fill:#2a2f4a,stroke:#3d4458,color:#f8f8f0
  classDef pattern fill:#2e5d3a,stroke:#5a8a6e,color:#f8f8f0,stroke-dasharray:5 3

  H[03 Garage Hub]:::hub
  WM[06 World Map]:::session
  PIT[15 Pit Stall Setup]:::session
  HW[27 Hardware Detail]:::sup
  CAL[29 Calibration]:::sup
  PB[07 Pre-Brief]:::session
  TW[37 Track Walk]:::session
  GL[36 Goals Library]:::sup
  HUD[08 On-Track HUD]:::session
  CD[09 Cool-Down]:::session
  SC[10 Stage Clear]:::session
  RP[11 Replay]:::session
  CSM[_ Coach Speaks Modal]:::pattern

  H --> WM
  H --> PIT
  PIT --> HW
  PIT -->|chain ✓| PB
  WM -->|A on pin| PB
  WM -->|STUDY TRACK| TW
  PB <-->|WALK THE TRACK| TW
  PB -->|+ CUSTOM GOAL| GL
  GL -->|SAVE| PB
  PB -.->|/coach/brief| CSM
  PB -->|CONFIRM| HUD
  HUD -->|car stops < 5mph 30s| CD
  CD -->|cool-down lap done| SC
  SC -.->|/coach/debrief| CSM
  SC -->|A · CONTINUE| H
  SC -->|A · REPLAY| RP
  RP --> H

  CAL -.->|optional| PIT
```

Three places the **Coach Speaks Modal** fires inside this loop —
pre-brief generation, debrief generation, and any LLM-driven moment.
Per [`screens/_coach-speaks-modal.md`](screens/_coach-speaks-modal.md).

## Zoom: hub radial

Garage Hub is the navigation centre. Six tiles + Start menu.

```mermaid
flowchart TB
  classDef hub  fill:#2a2f4a,stroke:#3d4458,color:#f8f8f0
  classDef sup  fill:#5d1a3a,stroke:#8a3a5e,color:#f8f8f0

  H[03 Garage Hub]:::hub
  TC[04 Trainer Card]:::hub
  CS[05 Coach Select]:::hub
  WM[06 World Map]:::hub
  QL[12 Quest Log]:::hub
  ST[13 Settings]:::hub
  AH[16 Analysis Hub]:::hub
  PIT[15 Pit Stall Setup]:::hub
  CC[28 Coach Codex]:::sup
  CAL[29 Calibration]:::sup
  SP[32 Live Spectator]:::sup
  EV[21 Driver Evolution]:::sup

  H --- TC
  H --- CS
  H --- WM
  H --- QL
  H --- ST
  H --- AH
  H --- PIT
  TC -->|◆| EV
  QL <-->|tab| CC
  ST -->|RECALIBRATE| CAL
  ST -->|OPEN SPECTATOR LINK| SP
```

## Zoom: analytics radial

Analysis Hub is a sub-centre — the data dungeon entry.

```mermaid
flowchart TB
  classDef ana fill:#1a3a52,stroke:#4a6e8a,color:#f8f8f0
  classDef sup fill:#5d1a3a,stroke:#8a3a5e,color:#f8f8f0

  AH[16 Analysis Hub]:::ana
  LT[17 Lap Times Hall]:::ana
  CM[18 Corner Mastery]:::ana
  SS[19 Straights & Speed]:::ana
  TA[20 Track Atlas]:::ana
  DE[21 Driver Evolution]:::ana
  PP[22 Pedal Profile]:::ana
  RP[11 Replay]:::ana
  CV[31 Comparison View]:::ana
  SQL[30 SQL Console]:::sup
  TW[37 Track Walk]:::sup

  AH --> LT
  AH --> CM
  AH --> SS
  AH --> TA
  AH --> DE
  AH --> PP
  AH -->|◆| SQL
  LT -->|tap lap| RP
  LT -->|COMPARE| CV
  CV -->|A · REPLAY| RP
  TA -->|tap corner| TW
  CM -->|tap corner| RP
```

## Overlays — where they fire

Overlays don't appear on the routed map because they overlay
*whatever screen is active*. Here's where each one can fire:

```mermaid
flowchart TB
  classDef overlay fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0
  classDef any    fill:#1a3a52,stroke:#4a6e8a,color:#f8f8f0

  ANY[any non-title screen]:::any
  HUD[08 On-Track HUD]:::any
  HUB[03 Garage Hub]:::any

  PM[23 Pause / Quick Menu]:::overlay
  AT[24 Achievement Toast]:::overlay
  BO[26 Bridge Offline]:::overlay
  NC[33 Notification Center]:::overlay
  TU[34 Tutorial Overlay]:::overlay
  DS[35 Daily Streak]:::overlay
  CSM[_ Coach Speaks Modal]:::overlay

  ANY -->|Start button| PM
  ANY -->|medal earned, level-up, etc.| AT
  ANY -->|/health 503 × 3 polls| BO
  ANY -->|✉ status-bar tap| NC
  ANY -->|first visit per screen| TU
  HUB -->|first hub entry today, streak ≥ 2| DS
  ANY -.->|LLM moment| CSM

  AT -->|tap → destination| ANY
  PM -->|RESUME / B| ANY
  PM -->|END SESSION| EOD[14 End of Day]
  PM -->|QUIT TO TITLE| TT[00 Title]
  PM -->|SETTINGS| ST[13 Settings]
  BO -->|tap → diagnostic| BO
  BO -->|recover| ANY
  NC -->|tap a row| DEST[various screens]
  TU -->|A advance| ANY
  DS -->|auto / tap| ANY
  CSM -->|A advance / B skip| ANY
```

The on-track HUD has **special suppression rules** (per
`06-audio-design.md`) — Achievement Toasts and Tutorials defer to the
next safe moment when the player is mid-corner. Pause is the only
overlay that can interrupt.

## Coach Speaks Modal — usage map

Every place the canonical "LLM is talking" pattern fires:

```mermaid
flowchart LR
  classDef pattern fill:#2e5d3a,stroke:#5a8a6e,color:#f8f8f0,stroke-dasharray:5 3
  classDef src     fill:#1a3a52,stroke:#4a6e8a,color:#f8f8f0

  CSM[_ Coach Speaks Modal]:::pattern

  PB[07 Pre-Brief]:::src
  SC[10 Stage Clear]:::src
  PIT[15 Pit Stall Setup]:::src
  CS[05 Coach Select]:::src
  AT[24 Achievement Toast]:::src
  CC[28 Coach Codex]:::src
  TW[37 Track Walk]:::src
  TU[34 Tutorial Overlay]:::src
  CAL[29 Calibration]:::src

  PB -.->|/coach/brief| CSM
  SC -.->|/coach/debrief| CSM
  PIT -.->|connection ✗ commentary| CSM
  CS -.->|coach intro line| CSM
  AT -.->|coach reaction to medal| CSM
  CC -.->|tap heard phrase| CSM
  TW -.->|tap marker → coach lore| CSM
  TU -.->|hint speech bubble| CSM
  CAL -.->|phase transition lines| CSM
```

The modal reads **emotion** from each caller per
[`10-coach-emotions.md`](10-coach-emotions.md). When the LLM is the
source, emotion comes from the response payload. When a canonical
phrase is the source, emotion comes from the static phrase library
tag.

## Per-screen incoming/outgoing reference

Quick-lookup table for *"who reaches screen N, and where does N
go?"*. Useful when implementing the router.

| # | Screen | Reachable from | Forward exits |
|---|---|---|---|
| 00 | Title | (boot, Quit-to-title from anywhere) | A → 01 Save Select |
| 01 | Save Select | 00, log-out | A on filled → 03; A on empty → 02 |
| 02 | Onboarding | 01 | step 7 done → 03 |
| 03 | Garage Hub | 01, 02, 10, 11, 13, 14, 12, all hubs | 6 tiles + Start menu |
| 04 | Trainer Card | 03 (TRAINER CARD), 24 (level-up tap) | ◆ → 21; B → 03 |
| 05 | Coach Select | 03 (COACHES), 24 (affinity tier) | swap → 03 |
| 06 | World Map | 03 (TRACK), 24 (track unlock) | A on Sonoma → 07; STUDY TRACK → 37 |
| 07 | Pre-Brief | 06 (A on pin) | CONFIRM → 08; WALK → 37; CUSTOM → 36 |
| 08 | On-Track HUD | 07 (CONFIRM, pre-flight ✓) | car stops → 09; B → Pause |
| 09 | Cool-Down | 08 (auto when stopped < 90 s) | t > 90 s in paddock → 10 |
| 10 | Stage Clear | 09 | A · CONTINUE → 03; A · REPLAY → 11 |
| 11 | Replay | 10, 17 (tap lap), 31, 18 (tap corner), 33 | B → 03 |
| 12 | Quest Log | 03, 24 (medal tap), 33 | tab → 28; B → 03 |
| 13 | Settings | 03, 23 Pause Menu | RECALIBRATE → 29; SPECTATOR → 32 |
| 14 | End of Day | 03 (Start → END SESSION) | night fade → 00 |
| 15 | Pit Stall Setup | 03 (PIT STALL), 07 (pre-flight ✗), 26 (offline diagnostic) | ◆ → 27; chain ✓ → 07 |
| 16 | Analysis Hub | 03 (ANALYSIS) | 6 tiles + ◆ → 30 |
| 17 | Lap Times Hall | 16 | tap lap → 11; COMPARE → 31; B → 16 |
| 18 | Corner Mastery | 16 | tap corner → 11 (replay); B → 16 |
| 19 | Straights & Speed | 16 | B → 16 |
| 20 | Track Atlas | 16, 06 (alt entry) | tap corner → 37; B → 16 |
| 21 | Driver Evolution | 16, 04 (◆), 33 | B → 16 |
| 22 | Pedal Profile | 16 | B → 16 |
| 23 | Pause / Quick Menu | Start on any screen | RESUME → parent; SETTINGS → 13; END SESSION → 14; QUIT → 00 |
| 24 | Achievement Toast | event-driven | tap → destination per kind |
| 25 | Loading | app boot | auto → 00 |
| 26 | Bridge Offline | event-driven (3+ failed polls) | tap → expanded; recover → silent |
| 27 | Hardware Detail | 15 (◆) | B → 15 |
| 28 | Coach Codex | 12 (tab) | B → 12 |
| 29 | Calibration | 13, 02 (step 7) | B → caller |
| 30 | SQL Console | 16 (◆) | B → 16 |
| 31 | Comparison View | 17 (COMPARE) | A · REPLAY → 11; B → 17 |
| 32 | Live Spectator | 13 (OPEN SPECTATOR LINK), URL | B → 13 |
| 33 | Notification Center | ✉ status-bar tap from any screen | tap row → various |
| 34 | Tutorial Overlay | first visit per screen per save slot | A advance → parent |
| 35 | Daily Streak | first garage entry today, streak ≥ 2 | tap / auto → 03 |
| 36 | Goals Library | 07 (+ CUSTOM GOAL) | SAVE → 07 |
| 37 | Track Walk | 07 (WALK), 06 (STUDY), 20 (tap corner) | A on corner → corner card; B → caller |
| _ | Coach Speaks Modal | 07, 10, 15, 05, 24, 28, 37, 34, 29 | A advance / B skip → caller |

## Keyboard quick-cheat

A second view: which keystrokes do what across the app.

```mermaid
flowchart LR
  classDef key fill:#1a1d2e,stroke:#3d4458,color:#f8f8f0
  classDef act fill:#2a2f4a,stroke:#3d4458,color:#f8f8f0

  KA[Z / Enter / Space]:::key -->|A| Confirm/Advance:::act
  KB[X / Esc / Backspace]:::key -->|B| Back/Cancel:::act
  KS[Tab]:::key -->|Start| Pause:::act
  KD[Arrows / WASD / IJKL]:::key -->|D-pad| Cursor:::act
  KF[F]:::key -->|toggle| Fullscreen:::act
  KM[M]:::key -->|toggle| MuteAll:::act
```

## What this map enables

- **Implementing `router.ts`** — every entry in the Per-screen table
  becomes a route definition; the diagrams show what guards to wire
- **Reviewing UX coherence** — orphan screens, dead-end paths, or
  unreachable branches show up immediately
- **Onboarding new contributors** — one diagram instead of reading
  38 screen docs
- **Spotting transition cycles** — e.g., 07 ↔ 37 is a healthy
  back-and-forth; `pre-brief → on-track → cool-down → stage-clear →
  hub` is the canonical session arc
- **Mermaid renders inside mkdocs-material** out of the box per
  `mkdocs.yml`'s `pymdownx.superfences` config — these diagrams ship
  with the rendered docs

## Don't-do list

- **Don't move overlays into the routed map.** They overlay; they're
  not destinations. Mixing categories makes the map unreadable.
- **Don't add the Coach Speaks Modal as a screen in the router.** It's
  a component that lives over screens. Its usage map (above) is the
  reference.
- **Don't expand the per-screen table inline.** When the count grows
  past 50 screens, split into a sub-page. Today, 38 screens fit on
  one page.

## Related

- [`05-routing-map.md`](05-routing-map.md) — Vue Router specifics for
  every route in the diagrams
- [`07-controls.md`](07-controls.md) — input behaviour referenced in
  diagram labels
- Every screen doc under `screens/` — the destinations cross-linked
  here
