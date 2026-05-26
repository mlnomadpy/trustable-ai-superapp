# 04 — Shared UI Components

## PageShell.vue (71 lines)
- ⚪ **Clean wrapper** — Good use of slots (`heading`, `default`, `floating`). CyberBackground integration is solid.
- 🔵 **`padding-bottom` may clip HintBar** — `shell-content` has `padding-bottom: clamp(28px, 6vh, 48px)` but HintBar is absolutely positioned. On short viewports, content can overlap the hint bar.
- 🔵 **No scroll support** — `height: 100%` with no `overflow` means pages with more content than viewport height simply clip. Some pages need `overflow-y: auto` on the content area.

## PageHeading.vue (24 lines)
- ⚪ Clean, minimal. Good use of slots for custom heading content.
- 🔵 **Subtitle has same color as title** (`text-silver`) — Low visual hierarchy. Subtitle should be dimmer.

## CoachFloat.vue (45 lines)
- 🟡 **`scale-[0.85]` and `w-[117%]` is a hack** — Scaling down and widening to fit. This means the DialogueBox renders at full size then shrinks, wasting render budget. Better to pass a `compact` prop to DialogueBox.
- 🔵 **No dismiss gesture** — User can't swipe away the coach float. On mobile, it blocks interaction with page content behind it.

## CoachCard.vue (187 lines)
- ⚪ Well-structured component with good state management (focused, locked, selected, portraitOnly).
- 🔵 **`backdrop-filter: blur(4px)`** on `.status-badge` — Performance cost on low-end devices. Consider a solid fallback.

## ParticleBackground.vue (58 lines)
- 🟡 **Always mounted via App.vue** — 8 animated divs on every page. The `float-particle` animation runs 8 instances at `8s infinite`. On the OnTrackHud (which needs max FPS), these are wasteful.
- 🔵 **Fixed positions** — Particles are at hardcoded `top`/`left` percentages. On different aspect ratios, they cluster. Randomize via JS on mount.
- 🔵 **Consider conditional rendering** — Only show on menu/UI pages, not on performance-critical pages like HUD.
