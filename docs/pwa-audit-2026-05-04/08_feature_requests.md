# 08 — Feature Requests & Alternative Approaches

## Missing Features

### High Priority
1. 🟢 **Real data pipeline** — Replace all mock data with actual store/API bindings
2. 🟢 **Auto-save system** — Debounced save on any store mutation (via Pinia plugin)
3. 🟢 **Loading/skeleton states** — Every page needs a loading phase before content appears
4. 🟢 **Error boundaries** — Wrap page content in error catchers with retry UI
5. 🟢 **Confirmation dialogs** — Delete save, quit session, change coach need "are you sure?"

### Medium Priority
6. 🟢 **Keyboard rebinding** — Let users configure controls beyond the 3 presets
7. 🟢 **Data export** — Export lap times, session data as CSV/JSON
8. 🟢 **Session comparison** — Side-by-side telemetry overlay (partially built in ComparisonView)
9. 🟢 **Coach voice preview** — Play sample audio in CoachSelect before committing
10. 🟢 **Undo system** — At least for car setup changes

### Low Priority
11. 🟢 **Theme system** — Dark/darker/OLED/custom color schemes
12. 🟢 **Multi-track support** — Currently everything is Sonoma-only
13. 🟢 **Internationalization (i18n)** — All text is hardcoded English
14. 🟢 **Tutorial/onboarding tooltips** — Guide new users through the UI
15. 🟢 **Offline indicator** — Show when bridge connection is lost (beyond the banner)

---

## Alternative Approaches

### State Management
- **Current**: Raw Pinia stores with manual save calls
- **Alternative**: Use a Pinia plugin that auto-persists to IndexedDB on every mutation. Libraries like `pinia-plugin-persistedstate` do this. Eliminates the "forgot to call save()" class of bugs.

### Keyboard Navigation
- **Current**: Each page registers its own `useKeyboard` handler with raw key checks
- **Alternative**: Centralized input manager with action mapping. Define actions (`navigate_up`, `select`, `cancel`) and let pages subscribe to actions, not keys. Enables gamepad support for free.

### Animation System
- **Current**: CSS keyframes scattered across global.css, component scoped styles, and inline styles
- **Alternative**: Single `animations.css` file imported globally. All keyframe names namespaced (e.g., `pw-fade-in`, `pw-pulse`). Components reference by name only.

### SVG Track Data
- **Current**: 50KB of path strings in `track_paths.ts`, imported synchronously
- **Alternative**: Store SVG paths as `.svg` files in `public/tracks/`. Load on-demand with `fetch()`. Enables adding new tracks without code changes.

### Coach Dialogue
- **Current**: Hardcoded strings in each page component
- **Alternative**: JSON dialogue trees per coach, loaded from `/content/coaches/{id}/lines.json`. Enables localization, A/B testing, and coach personality tuning without code deploys.

### Performance on HUD Page
- **Current**: CRT overlay, particles, background grid all render on HUD
- **Alternative**: HUD page should opt out of all decorative layers. Add a `performance` mode flag to PageShell that strips all non-essential rendering. Use `requestAnimationFrame` for telemetry updates instead of reactive refs.

### Component Styling
- **Current**: Mix of Tailwind utility classes and scoped CSS in the same components
- **Alternative**: Pick one. Either go full Tailwind (remove scoped styles) or go full scoped CSS (remove utility classes from templates). The mix makes it hard to reason about specificity and maintenance.

### Testing
- **Current**: Zero tests
- **Alternative**: At minimum, add Vitest unit tests for stores (saveStore, telemetryStore, duckdbStore) and composables (useKeyboard, useTypewriter, useSequence). Add Playwright E2E tests for critical flows (onboarding, save/load, navigation).
