# 02 — Onboarding

90-second wizard for a new driver. 7 steps. Skippable past the
hardware-pair step if no bridge is connected (driver can configure
later).

## Purpose

Verb: **Set up.** Identity (name, skill, avatar) + preferences (coach,
car) + optional hardware pair.

## Steps

| # | Route | Question | UI |
|---|---|---|---|
| 1 | `/onboarding/1` | Welcome | T-Rod portrait + dialogue: *"Welcome to Pitwall, kid. Let's set you up."* — A advances |
| 2 | `/onboarding/2` | Name? | 6 × 4 character grid (A-Z, period-hyphen-underscore-space, DEL/END), max 12 chars |
| 3 | `/onboarding/3` | Skill? | 3 large tiles: BEGINNER / INTERMEDIATE / PRO; coach reaction sprite per choice |
| 4 | `/onboarding/4` | Coach? | Roster (same as `screens/05-coach-select.md`); default T-Rod |
| 5 | `/onboarding/5` | Car? | List of supported cars; default BMW M3 (E46); shows DBC signal coverage |
| 6 | `/onboarding/6` | Hardware? | Live `GET /health` poll; "INSERT USB-CAN" sprite animation; flips to ✓ when connected |
| 7 | `/onboarding/7` | Calibration | 10-second still-car telemetry read; coach commentary |

## Wireframe (step 2 — name entry)

```
┌────────────────────────────────────────────────────────────┐
│ SET UP YOUR DRIVER · STEP 2 / 7                            │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│              YOUR NAME                                     │
│                                                            │
│              ╔════════════╗                                │
│              ║ TAHA_      ║                                │
│              ╚════════════╝                                │
│                                                            │
│   A B C D E F G                                            │
│   H I J K L M N                                            │
│   O P Q R S T U                                            │
│   V W X Y Z .                                              │
│   _ - SPC DEL END                                          │
│                                                            │
│   ▶ A · INSERT     B · BACK     END · CONFIRM              │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `step-N` | Route param | Render the step's UI |
| `dialogue-blocking` | Coach speaking | Disable advance until A pressed (or teletype done + 500 ms) |
| `validating-name` | A on END | Reject name shorter than 1 char or longer than 12 |
| `hardware-polling` | Step 6 entry | `GET /health` every 1 s; show ✗ → ✓ animation when connected |

## Sprite usage

- T-Rod (or chosen coach): `idle`, `talk`, `point_left/right` (when
  emphasising a choice), `thumbs_up` (when player makes a choice)
- Avatar previews on step 3+: `avatars` sheet
- USB-CAN illustration on step 6: `ui/usb_can_animation` 4-frame plug-in

## Vue component

`pitwall-web/src/views/Onboarding.vue` reads the `:step` route param
and renders the matching child component. State writes to a
`pendingSave` Pinia store that gets committed to IndexedDB at step 7
completion.

## Endpoints consumed

| Step | Endpoint |
|---|---|
| 6 | `GET /health` (polled every 1 s) |
| 7 | `POST /session/<sid>/frames` (10 s of stationary frames) → confirm sensors agree |

## Audio cues

| Event | Sound |
|---|---|
| Step advance | `cursor_select` |
| Step back | `cancel` |
| Hardware connects (✗ → ✓) | `goal_complete` |
| Final step complete | `level_up` (welcome to Pitwall) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ ◀ ▶ | Navigate the step's UI (character grid, tile picker) |
| A | Insert / select / advance |
| B | Backspace (in name entry) or previous step |
| Start | Skip step (only allowed for hardware-pair if no bridge) |

## Edge cases

- **No bridge available at step 6** — show "SKIP & CONFIGURE LATER"
  option; player can still complete onboarding
- **Empty name at end** — disallow advance; coach disappointed line
- **Calibration shows sensor disagreement** (lat fluctuating > 0.1 m
  while stationary) — warn but allow continue
- **Onboarding interrupted (back button mid-flow)** — `pendingSave` is
  preserved; restart from step 1 with prior values pre-filled

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — destination after step 7
- [`05-coach-select.md`](05-coach-select.md) — same UI as step 4
- [`13-settings.md`](13-settings.md) — driver can change any of these
  later from the garage settings
