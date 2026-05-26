# 02 — Global CSS & Design Tokens

## global.css (442 lines)

### 🔴 Bugs
- **Duplicate `.fade-*` transitions** — Defined in both `global.css` (L183-190) AND `App.vue` scoped styles (L193-201). The scoped version has `0.3s ease`, the global has `0.15s ease`. Global wins due to specificity, making the App.vue version dead code.

### 🟡 Problems
- **`crt-overlay` in `@layer utilities`** — This is a component class with layout properties (`position: absolute; inset: 0`), not a utility. It should be in a component layer or in App.vue where it's used.
- **Orphaned selectors** — `.page-bg` classes were removed from global.css (moved to CyberBackground) but `.page-content` still references `z-index: 10` assuming a background layer at z-index 0 exists. Fragile coupling.
- **`body .viewport` override** uses `!important` on 5 properties. This is a sledgehammer. If any component needs viewport constraints for a specific reason, it can't override back.
- **Mixed unit systems** — Some values use `clamp()` with `vmin`, others use `vh`/`vw`, others use raw `px`. No documented rationale for when to use which.

### 🔵 Improvements
- **No dark/light mode toggle** — `--color-ink` is always dark. The `nightMode` setting exists in SaveSettings but no CSS custom property switching is implemented.
- **`.glass` utility uses `!important`** on `background` — This will override any component-level background. Remove `!important` or use a more specific selector.
- **Stagger animation classes** (`stagger-1` through `stagger-5`) — Only 5 levels. If a list has 6+ items, the 6th gets no animation. Consider a CSS custom property approach: `animation-delay: calc(var(--stagger-index, 0) * 80ms)`.
- **Color tokens hardcoded in multiple places** — `#c93838` (curb red) appears raw in `.kerb-stripe`, `.heading-rule`, `.kerb-stripe-v`. Should be `var(--color-curb-red)`.

### ⚪ Practices
- **No `@font-face` declarations** — Fonts `Orbitron`, `Rajdhani`, `Share Tech Mono` are referenced but never loaded. They must be loaded via `<link>` in `index.html` (not visible in source). If fonts fail to load, entire UI falls back to `sans-serif`/`monospace` with no visual grace.
- **`@import "tailwindcss"` (v4 style)** is used — Confirm the project is actually on Tailwind v4. If on v3, this import syntax won't work.

---

## buttons.css (155 lines)

### 🔴 Bugs
- **File is never imported** — Not in `main.ts`, not in `global.css`, not in any component. All `.retro-btn` classes are dead code. Either import it in `main.ts` after `global.css`, or delete the file.

### 🟡 Problems
- **Uses `margin-bottom: 10px` / `margin-top: 8px` for 3D effect** — This causes layout shift on `:active`. Surrounding elements jump. Use `transform: translateY()` instead.
- **`clip-path` with hardcoded `8px` corners** — Not responsive. On very small buttons, the 8px cut is proportionally huge.

### 🔵 Improvements
- **`bg-shift` animation** runs `3s linear infinite` on every button's `::after` — Constant GPU compositing for a barely-visible diagonal shift. Consider `animation-play-state: paused` by default, `running` on `:hover`.
