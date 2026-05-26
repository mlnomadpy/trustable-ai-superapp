# Pitwall PWA — Full Audit Summary

**Date**: 2026-05-04  
**Scope**: All `.vue`, `.css`, and `.ts` files in `src/pwa/src/`  
**Files Reviewed**: ~100 files, ~12,000 lines

## Audit Structure

| File | Covers |
|------|--------|
| [01_architecture.md](./01_architecture.md) | FSD structure, routing, state management |
| [02_global_css.md](./02_global_css.md) | global.css, buttons.css, design tokens |
| [03_core_components.md](./03_core_components.md) | All `shared/ui/core/Cyber*.vue` components |
| [04_shared_ui.md](./04_shared_ui.md) | PageShell, CoachFloat, CoachCard, ParticleBackground |
| [05_widgets.md](./05_widgets.md) | StatusBar, DialogueBox, PauseMenu, HintBar, etc. |
| [06_pages.md](./06_pages.md) | All page-level components |
| [07_stores_and_libs.md](./07_stores_and_libs.md) | Pinia stores, composables, utilities |
| [08_feature_requests.md](./08_feature_requests.md) | Missing features and enhancement ideas |

## Top 10 Critical Issues

1. **Hardcoded mock data everywhere** — Nearly every page uses inline dummy data instead of store/API calls
2. **No error boundaries** — Zero `<ErrorBoundary>` or `onErrorCaptured` usage across pages
3. **Duplicate animation keyframes** — `cursor-bounce` defined in 3+ places (global.css, CyberTile, Tile)
4. **CRT overlay always running** — `crt-flicker` animation runs at 0.15s interval even on low-end devices
5. **Missing `glass` variant in CyberPanel** — prop accepts `'glass'` but no CSS rule exists for it
6. **buttons.css never imported** — `retro-btn` classes defined but the file isn't imported in main.ts
7. **No loading states** — Pages mount and show content instantly with no skeleton/loading UX
8. **Accessibility gaps** — No ARIA labels, no focus-visible styles, no screen reader support
9. **ParticleBackground renders on every page** — Always mounted in App.vue, no conditional rendering
10. **`useKeyboard` listeners stack** — Multiple pages register keyboard handlers that could conflict

## Severity Legend

- 🔴 **BUG** — Broken or will break  
- 🟡 **PROBLEM** — Works but is wrong  
- 🔵 **IMPROVEMENT** — Could be better  
- 🟢 **FEATURE** — Missing capability  
- ⚪ **PRACTICE** — Code quality concern
