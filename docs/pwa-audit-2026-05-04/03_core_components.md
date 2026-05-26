# 03 — Core Components (`shared/ui/core/`)

## CyberButton.vue (214 lines)
- 🟡 **`.neon-border` is `display: none`** — Dead code. 7 lines of template + potential CSS for a feature that's disabled. Remove or gate behind a prop.
- 🟡 **Fixed `min-width`/`min-height` in px** — `lg` is `240px` min-width. On mobile landscape that's half the screen. Should use `clamp()`.
- 🔵 **No focus-visible style** — Keyboard users can't tell which button is focused.
- 🔵 **`variant` naming mismatch** — `primary` maps to red, `secondary` to teal. Semantically confusing. Consider `danger`/`accent` naming.

## CyberPanel.vue (143 lines)
- 🔴 **`glass` variant has no CSS rule** — Prop accepts `'glass'` but only `.solid` and `.ghost` have styles. Glass panels render with no background.
- 🟡 **Double pseudo-element usage** — `::before` (scanlines) AND `::after` (border) both use `clip-path`. Two extra compositing layers per panel. On pages with 5+ panels, that's 10 extra layers.
- 🔵 **Entry animation always plays** — `panel-fade-up` runs on every panel mount. If a panel is inside a tab that switches, it re-animates. Add a `noAnimation` prop.

## CyberBackground.vue (183 lines)
- 🟡 **`grid-move` animation runs infinitely** — The perspective grid animates at 3s loop forever. No pause on page idle. GPU cost on mobile.
- 🔵 **Only 3 variants** (`grid`, `landscape`, `stars`) — Consider a `none` variant for pages that want the component wrapper but a custom background.
- ⚪ Stars are hardcoded radial gradients — Works but adding/removing stars requires editing 20 lines of CSS.

## CyberKeyboard.vue (149 lines)
- 🟡 **Hardcoded row count** — `cursorY.value = (cursorY.value + 1) % 5` assumes exactly 5 rows. If characters change, this breaks silently.
- 🟡 **No physical keyboard input** — Only d-pad navigation + click. A user can't just type on their keyboard. The `NameEntry` parent doesn't pass physical key presses through.
- 🔵 **No haptic feedback** on mobile — `navigator.vibrate(10)` on key tap would improve feel.

## CyberDataGrid.vue (118 lines)
- 🟡 **Horizontal scroll not indicated** — On narrow screens, columns overflow but there's no visual hint.
- ⚪ **No sorting/filtering** — Fine for now but will be needed for telemetry tables.

## CyberTile.vue (106 lines)
- 🟡 **Duplicate `cursor-bounce` keyframe** — Already defined in `global.css`. Redefined here in scoped style. Browser parses both.
- 🔵 **No disabled state** — `locked` exists but a generic `disabled` (greyed, no pointer events) would be useful.

## CyberRadarChart.vue (119 lines)
- 🔵 **Fixed viewBox `0 0 100 100`** — Labels that extend beyond 100 units get clipped. Add `overflow: visible` to the SVG.
- ⚪ **Hardcoded 5 axes** — The polygon math works for any N but label positioning is tuned for 5.

## CyberTabs.vue (75 lines)
- 🔵 **No keyboard navigation** — Can't use arrow keys to switch tabs. Only click.
- 🔵 **No `aria-role="tablist"`** — Accessibility gap.

## CyberListRow.vue (106 lines)
- ⚪ Clean implementation. No major issues found.

## CyberMenuList.vue (125 lines)
- ⚪ Clean. Keyboard nav works. Good component.

## CyberSplitView.vue (60 lines)
- 🔵 **Mobile stacks vertically** but gives equal height to both panes. The left pane might need `flex: 0 0 auto` on mobile so the right pane gets the remaining space.

## CyberProgress.vue (96 lines)
- ⚪ Clean. Good step-based animation.

## CyberGauge.vue (44 lines)
- ⚪ Clean. Segmented mask is a nice touch.

## CyberBadge, CyberBox, CyberTag, CyberCheckbox, CyberMetricRow, CyberValuePicker, CyberProgressBar
- ⚪ All small, focused, clean. No issues found.

## CyberAvatar.vue (66 lines)
- 🔵 **Only 4 sizes** (`sm`, `md`, `lg`, `xl`) — Consider accepting arbitrary size via a `size` CSS custom property.

## TrackMap.vue (143 lines)
- 🟡 **50KB of SVG path data in track_paths.ts** — This is loaded for every page that imports TrackMap even if the map isn't visible. Consider dynamic import.
- 🔵 **`viewBox="0 0 3000 1440"`** is fixed — The track doesn't scale to fill narrow containers well. Consider adding `preserveAspectRatio="xMidYMid meet"`.

## index.ts (barrel)
- 🟡 **Missing exports** — `CyberAvatar`, `CyberBackground`, `CyberDataGrid`, `CyberGauge`, `CyberRadarChart`, `CyberSplitView`, `TrackMap` are NOT exported. Consumers import them directly, bypassing the barrel. Inconsistent.
