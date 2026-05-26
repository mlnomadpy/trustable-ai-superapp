# 05 — Widgets

## StatusBar.vue (184 lines)
- 🟡 **Global `N` key shortcut** — `useKeyboard` handler routes to `/notifications` on any `n`/`N` press. This fires even when user is navigating other pages. Could conflict with keyboard typing on SqlConsole or NameEntry.
- 🟡 **`setInterval` for clock** runs every 1000ms updating a ref — Updates `time` every second but the display only shows `HH:MM`. Wasteful. Update every 60s.
- 🔵 **`coach-badge` class defined but never used** — The template uses `<CyberBadge>` component instead. 30 lines of dead CSS.
- 🔵 **Clip-path on status bar** cuts off content on very narrow screens.

## DialogueBox.vue (~220 lines)
- 🟡 **Typewriter re-implements what `useTypewriter` does** — Should use the composable instead of duplicating the `setInterval` + char-by-char logic.
- 🔵 **No max height** — Long coach text strings can push the dialogue box beyond viewport. Add `max-height` with scroll.

## VirtualGamepad.vue (~180 lines)
- 🔵 **Fixed button sizes** — D-pad and action buttons use fixed px sizes. On tablets, they're too small. On phones, they overlap.
- 🔵 **No visibility toggle** — Always rendered. Should detect if a physical gamepad is connected and hide.

## HintBar.vue
- ⚪ Clean. Shows contextual hints. No issues.

## PauseMenu.vue (265 lines)
- 🟡 **Direct `router.push('/')` on QUIT** — No confirmation dialog. User could accidentally lose progress.
- 🔵 **Resume button doesn't restore audio state** — Music is ducked on pause but `duckMusic(false)` isn't called on resume.

## MedalGrid.vue
- ⚪ Clean grid layout. Good responsive handling.

## SessionGoalsPanel.vue (107 lines)
- ⚪ Clean. Well-scoped for HUD use.

## BridgeOfflineBanner.vue
- ⚪ Simple offline indicator. Works fine.

## UpdateToast.vue (98 lines)
- ⚪ Service worker update detection is solid. Good UX pattern.

## GripBar.vue (widget/hud)
- ⚪ Simple gauge. Clean.

## HUD TrackMap.vue (widget/hud)
- 🟡 **Naming collision** with `shared/ui/core/TrackMap.vue` — Same filename in two different directories. Confusing for imports and search.
