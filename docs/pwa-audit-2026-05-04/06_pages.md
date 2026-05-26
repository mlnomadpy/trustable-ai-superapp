# 06 — Pages Audit

## Common Issues Across ALL Pages

- 🔴 **Hardcoded mock data** — Every single page uses inline dummy arrays/objects instead of fetching from stores or API. This means the app is a visual prototype with zero live data flow.
- 🟡 **No loading states** — Pages render instantly with mock data. When real APIs are connected, users will see empty screens.
- 🟡 **No error handling** — No try/catch around data fetching. No error UI.
- 🔵 **Coach quotes are hardcoded strings** — Should come from a coach dialogue system or content file.

---

## TitleScreen.vue (193 lines)
- ⚪ Clean. Uses CyberBackground with landscape variant. Good entry point.
- 🔵 **No version display** — Show app version for debugging.

## SaveSelect.vue (91 lines)
- 🟡 **Delete slot has no confirmation** — One tap deletes save data permanently.
- 🔵 **Only 3 slots** — Consider unlimited saves stored in IndexedDB.

## OnboardingFlow.vue (181 lines)
- 🟡 **Step routing uses URL param** (`/onboarding/:step`) but step validation is weak — Invalid step values silently render nothing.
- 🔵 **No progress indicator** — User doesn't know how many steps remain.

## GarageHub.vue (224 lines)
- ⚪ Good tile-based layout. Clean keyboard navigation.
- 🔵 **Tiles don't show status indicators** — e.g., "3 new notifications", "calibration needed".

## CoachSelect.vue (237 lines)
- 🟡 **`trySelect` mutates store directly** — `activeSlot.value.preferredCoach = c.id` without calling `save()`. If app crashes before auto-save, preference is lost.
- 🔵 **Coach preview sprite is `scale(1.3)`** — Can overflow container on small screens.

## CoachBios.vue (154 lines)
- ⚪ Clean tabbed layout with coach portraits.

## OnTrackHud.vue (214 lines)
- 🔴 **Critical performance concern** — CRT overlay, ParticleBackground, and CyberBackground all render on the HUD page. This is the one page that needs 60fps for real-time telemetry.
- 🟡 **Telemetry values are mock** — `ref(0)` for speed, RPM, etc. No connection to `telemetryStore`.
- 🔵 **No fullscreen API** — HUD should offer native fullscreen for immersion.

## LivePitWall.vue (153 lines)
- 🟡 **`telemetryStore.open(sid)` called with hardcoded session ID** — Should come from active session.
- 🔵 **TrackMap car position not animated** — `carProgress` updates discretely. Add CSS transition on the car dot.

## PitStall.vue (189 lines)
- ⚪ Good connection status UI with ConnRow components.
- 🔵 **No auto-discovery** — User must know the bridge IP. Consider mDNS/Bonjour discovery.

## AnalysisHub.vue (132 lines)
- ⚪ Clean hub page with menu navigation.

## TelemetryReplay.vue (150 lines)
- 🟡 **No actual replay controls** — Play/pause/scrub UI exists conceptually but no implementation.
- 🔵 **DuckDB query results not rendered** — The page mentions SQL analysis but doesn't display results.

## GhostManager.vue (131 lines)
- 🔵 **No ghost import/export** — Can't share ghost data with friends.

## ComparisonView.vue (188 lines)
- 🟡 **Hardcoded delta values** — `+0.3s`, `-0.1s` everywhere. No computation.

## CornerMastery.vue (177 lines)
- ⚪ Good corner-by-corner breakdown UI.
- 🔵 **No visual corner highlighting on track map** — When selecting a corner, the map should highlight it.

## StraightsAndSpeed.vue (131 lines)
- ⚪ Clean layout matching the corner mastery pattern.

## TrackWalk.vue (216 lines)
- ⚪ Good "walk through corners" UX with slide-up detail panel.
- 🔵 **Corner detail panel has no close button** — Only keyboard `Escape` works. Touch users stuck.

## TrackAtlas.vue (224 lines)
- ⚪ Good track reference page.
- 🔵 **Static content** — Could benefit from interactive SVG corner annotations.

## LapTimesHall.vue (223 lines)
- 🔵 **No sorting** — Can't sort by lap time, date, or session.
- 🔵 **No pagination** — If user has 1000 laps, all render at once.

## DriverEvolution.vue (193 lines)
- 🔵 **Chart is mock data** — The "trend over time" chart is hardcoded points.

## PedalProfile.vue (231 lines)
- ⚪ Good pedal trace visualization concept.
- 🔵 **Canvas not used** — Pedal traces should use `<canvas>` for performance, not SVG paths.

## PreBrief.vue (120 lines)
- ⚪ Good pre-session workflow.
- 🟡 **Goal selection doesn't persist** — Selected goals aren't saved to the store.

## StageClear.vue (260 lines)
- ⚪ Good end-of-session celebration UI with sequenced animations.
- 🔵 **XP bar fills instantly** — Should animate from old value to new value.

## EndOfDay.vue (129 lines)
- ⚪ Clean summary page.

## QuestLog.vue (222 lines)
- ⚪ Good quest/challenge tracking UI.
- 🔵 **No quest completion animation** — Completing a quest should feel rewarding.

## SponsorContracts.vue (158 lines)
- ⚪ Creative sponsor/contract mechanic.

## Settings.vue (358 lines)
- 🟡 **Settings changes don't persist** — Values are local refs. `save()` is never called after mutation.
- 🟡 **`reducedMotion` toggle exists** but doesn't set `prefers-reduced-motion` override. Only the CSS media query works.
- 🔵 **No "Reset to Defaults" button**.

## SqlConsole.vue (254 lines)
- ⚪ Good developer tool. DuckDB integration works.
- 🔵 **No query history** — Previous queries are lost on navigation.
- 🔵 **No syntax highlighting** — Raw textarea input.

## Calibration.vue (145 lines)
- ⚪ Clean calibration workflow.

## NotificationCenter.vue (107 lines)
- ⚪ Simple notification list.
- 🔵 **No mark-all-as-read** button.
- 🔵 **No notification categories/filters**.

## GlobalLeaderboard.vue (93 lines)
- 🟡 **Entirely mock data** with no API connection.
- 🔵 **No pagination or search**.

## TrainerCard.vue (169 lines)
- ⚪ Good player profile card with radar chart and medal grid.
- 🟡 **`Math.random()` for medal unlock state** — Medals randomly appear unlocked/locked on each mount.

## HardwareDetail.vue (259 lines)
- ⚪ Good hardware diagnostics page.
- 🔵 **CAN signal list is static** — Should update in real-time from bridge.
