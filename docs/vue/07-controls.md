# 07 — Controls

Three input modes. All map to a single 6-button virtual gamepad
internally (`Up / Down / Left / Right / A / B` + optional `Start`),
preserving the GBA mental model.

## The virtual gamepad

```
        [ Up ]
[Left][   ][Right]      [B]    [A]
        [Down]              [Start]
```

| Button | Default action |
|---|---|
| `Up / Down / Left / Right` | Move cursor on the active screen's tile grid |
| `A` | Confirm — select the highlighted tile, advance dialogue, etc. |
| `B` | Cancel / Back — return to previous screen, dismiss dialogue |
| `Start` | Open quick-menu (pause / settings) — inactive on title and during transitions |

Every screen must accept all six buttons or document why a subset is OK
(e.g., title only needs Start; on-track HUD ignores most input).

## Input mode 1 — touch (default on phone)

A virtual D-pad overlays the screen on touch devices. Layout:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                  (game viewport)                           │
│                                                            │
│                                                            │
├────────────────────────────────────────────────────────────┤
│   ╔═══╗                                              ╔═══╗ │
│   ║ ▲ ║                                              ║ A ║ │
│   ║◀ ▶║                                          ╔═══╝   ╚═│
│   ║ ▼ ║                                          ║ B ║      │
│   ╚═══╝                                          ╚═══╝      │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

D-pad sits in the bottom-left, A+B in the bottom-right. Both float
over the bottom hint bar (which is the only place they can overlap UI
without confusion).

### Touch implementation

- D-pad is one PNG sprite with four invisible touch zones overlaid
- A and B are separate sprites (so they can flash independently)
- All buttons honour iOS's "long-press selects text" by `user-select:
  none; -webkit-touch-callout: none; touch-action: manipulation`
- Buttons fire on `pointerdown`, not `click`, for sub-50 ms response
- Multi-touch: simultaneous A+B is allowed (no confirmation, no
  re-binding)

### Tap-only mode (auto-detected)

On screens that don't need the D-pad (dialogue boxes, single-tile
prompts), the D-pad fades out and tapping anywhere advances the
dialogue. Detected via `meta.tapOnly: true` on the route or per-screen
override.

## Input mode 2 — keyboard (default on desktop)

| Key | Action | Configurable? |
|---|---|---|
| Arrow Up / Down / Left / Right | D-pad | Yes (Settings → controls layout) |
| W / A / S / D | D-pad alternate | Yes |
| I / J / K / L | D-pad alternate | Yes |
| Z | A | Yes (also Enter, Space) |
| X | B | Yes (also Esc, Backspace) |
| Enter | A | Yes |
| Space | A | Yes |
| Escape | B | Yes |
| Backspace | B | Yes |
| Tab | Start (quick menu) | Yes |
| F | Toggle fullscreen | No |
| M | Mute all | No |

Settings → controls offers three preset layouts:

- **Arrows + Z/X** (default) — old-school
- **WASD + Enter/Esc** — modern PC-game muscle memory
- **IJKL + Z/X** — left-handed

Plus a "swap A/B" toggle for left-handed players who use Z as cancel.

## Input mode 3 — gamepad (auto-detected)

Standard HTML5 Gamepad API. Detected when a gamepad is plugged in
(`gamepadconnected` event); D-pad and A/B buttons map per the standard
mapping:

| Gamepad button | Action |
|---|---|
| D-pad up/down/left/right | D-pad |
| Left stick (with deadzone) | D-pad |
| Button 0 (A on Xbox / X on PlayStation) | A |
| Button 1 (B on Xbox / Circle on PlayStation) | B |
| Button 9 (Start) | Quick menu |

Polled at 60 Hz via `navigator.getGamepads()` in the `requestAnimation
Frame` loop. No external library — the API is small enough.

## Per-screen input map

Each screen doc has an "Input map" section. The standard:

| Action | Default behaviour |
|---|---|
| `D-pad` | Move cursor on the active tile grid |
| `A` | Confirm the highlighted tile |
| `B` | Navigate back per `05-routing-map.md` |
| `Start` | Open quick menu |

Screens that override the standard:

- **Title** — A or Start: enter save-select. D-pad: no effect.
- **Onboarding name entry** — D-pad: move on character grid. A: select.
  B: backspace. Start: confirm name.
- **On-track HUD** — D-pad and A: no effect (driving uses the wheel,
  not the phone). B: pause → quick menu. Touch the screen anywhere:
  dismiss any momentary cue.
- **Dialogue boxes** — A: advance / fast-forward teletype. B: skip the
  whole dialogue (with confirmation if the speaker is mid-paragraph).
  D-pad: ignored.
- **Stage clear** — A: continue counting up. B: skip the count-up
  animation and reveal final score. D-pad: ignored.

## Cursor visibility

The cursor sprite (▶) is visible on every screen *except*:

- Title (no cursor; just blink "PRESS START")
- On-track HUD (no cursor; the driver isn't poking at the phone)
- Stage clear (no cursor during the count-up animation; appears after)
- Dialogue (no cursor; tap-anywhere)

When the cursor IS visible, it bounces 1 px horizontally at 4 Hz on
the active tile (per `01-visual-language.md` § "Animation primitives").

## Accessibility

- **Sticky keys / dwell**: hold any direction for 400 ms to auto-repeat
  at 5 Hz. Auto-repeat resets when the player lifts the key.
- **`prefers-reduced-motion`**: cursor stops bouncing; transitions
  shorten to 50 ms; sprite breathing animations pause.
- **Screen reader**: every cursor-able tile has an `aria-label` with
  the same text as the visible label. The current selection has
  `aria-current="true"`. Dialogue boxes are `role="dialog"` with the
  full text in `aria-live="polite"`.
- **High-contrast mode**: detected via `prefers-contrast: more`. Swaps
  the palette to a 4-colour high-contrast variant (defined in
  `01-visual-language.md` extension), bumps frame outlines from 1 px to
  2 px, disables sprite shading. Players using this mode get the same
  game; less visual fidelity.

## Don't list

- **No swipe gestures.** Old games didn't have them. Tap, D-pad, A, B.
  Confidence in the input model > convenience for touch-first users.
- **No long-press menus.** Same reason. Long-press is reserved for
  potential text-selection in dialogue (future feature).
- **No drag-to-scroll.** All long lists fit on one screen with
  pagination via D-pad. If a list doesn't fit, redesign the screen.
- **No haptic feedback.** Phones in mounts can't feel vibration; phones
  in hands during a session aren't held. Net negative.
- **No mouse hover state.** Hover is a desktop-only concept; the cursor
  is the focus indicator everywhere.

## Related

- [`05-routing-map.md`](05-routing-map.md) — what `B` means per route
- [`13-settings.md`](screens/13-settings.md) — the controls config screen
- [`01-visual-language.md`](01-visual-language.md) — cursor sprite
