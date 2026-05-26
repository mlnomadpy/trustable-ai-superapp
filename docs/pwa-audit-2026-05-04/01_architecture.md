# 01 — Architecture & Structure

## FSD Compliance

The app follows Feature-Sliced Design loosely. Layer boundaries are mostly respected.

### 🟡 Router (`router/index.ts`)
- **All 30+ routes in one flat array** — No route grouping by feature. Hard to maintain.
- **`requiresSave` guard works** but silently redirects. User gets no feedback on why they bounced.
- **Transition plays before navigation** via `beforeEach` → `await trans.play(wipe)`. This blocks route entry. If `play()` hangs, navigation freezes.
- **No 404 page** — Catch-all just redirects to `/`. User has no idea what happened.
- **No route-level code splitting hints** — All lazy imports use generic `() => import(...)`. No `webpackChunkName` or Vite manual chunk hints for debugging.

### 🟡 App.vue
- **Touch gesture system in root component** — The swipe-to-arrow-key system (`onGlobalTouchStart`/`onGlobalTouchMove`) belongs in a composable like `useTouchNavigation()`, not in App.vue.
- **Magic number threshold** `40` for swipe detection — Should be a named constant.
- **`ParticleBackground` always rendered** — 8 animated DOM elements floating on every page, even pages that don't need them (e.g., OnTrackHud). Should be conditional or page-opt-in.

### 🔵 main.ts
- **`buttons.css` is never imported** — The file exists with `retro-btn` styles but `main.ts` only imports `global.css`. Either import it or delete it.
- **Error handler is good** but only logs to console. Consider sending to a telemetry service or showing a user-facing crash screen.

### ⚪ General Structure
- `shared/ui/core/` has 22 components — Good granularity but the barrel `index.ts` doesn't export `CyberAvatar`, `CyberBackground`, `CyberDataGrid`, `CyberGauge`, `CyberRadarChart`, `CyberSplitView`, or `TrackMap`. Inconsistent.
- `widgets/hud/TrackMap.vue` exists alongside `shared/ui/core/TrackMap.vue` — Confusing duplication. The widget version wraps the core one but the naming is identical.
