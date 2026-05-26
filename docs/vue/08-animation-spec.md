# 08 — Animation spec

Frame timings, transitions, easings. Every animation in the PWA falls
into one of three categories — sprite frame loops, screen transitions,
or property tweens.

## Three animation categories

### 1. Sprite frame loops (CSS `steps()`)

For per-character looping animations. Implemented as CSS keyframe
animation with `animation-timing-function: steps(N)` so frames advance
discretely, no interpolation.

```css
.sprite-trod-walk {
  animation: trod-walk 0.66s steps(4) infinite;
}
@keyframes trod-walk {
  from { background-position-x: 0;        }
  to   { background-position-x: -256px;   }   /* 4 frames × 64 px */
}
```

| Animation | FPS | Duration / loop | Notes |
|---|---|---|---|
| Idle (breathing) | 1.5 Hz | 1.33 s | 2-frame, gentle |
| Walking | 6 Hz | 0.66 s | 4-frame, mid-pace |
| Running | 8 Hz | 0.50 s | 4-frame, urgent |
| Talking (mouth open/closed) | 6 Hz | 0.33 s | 2-frame; gated to dialogue teletype |
| Push-up | 4 Hz | 0.50 s | 2-frame |
| Kick / fight | 6 Hz | 0.50 s | 4-frame, loops (idle stance optional) |
| Victory (fist pump) | 4 Hz | 0.50 s | 2-frame, plays once |
| Sleep ("Z" floating up) | 1 Hz | 1.00 s | 3-frame, gentle |

Frame rates above are deliberate — slower than 60 Hz to read as
"sprite art" not "video".

### 2. Screen transitions (CSS keyframes + JS orchestration)

Wipes between routes. Detailed in `05-routing-map.md`. Implementation:

```css
.wipe-overlay {
  position: absolute; inset: 0;
  background: var(--ink, #1a1d2e);
  transform: translateX(-100%);
  pointer-events: none;
}
.wipe-overlay.wipe-in-right {
  animation: wipe-in-right 150ms ease-out forwards;
}
@keyframes wipe-in-right {
  from { transform: translateX(-100%); }
  to   { transform: translateX(0);     }
}
```

| Transition | Duration | Easing | Trigger |
|---|---|---|---|
| `wipe-right` | 150 ms | `ease-out` | Forward navigation (A button confirm) |
| `wipe-left` | 150 ms | `ease-out` | Back navigation (B button) |
| `wipe-up` | 200 ms | `ease-in-out` | Entering paddock from on-track |
| `wipe-down` | 200 ms | `ease-in-out` | Entering on-track from paddock |
| `flash-white` | 100 ms | linear | Achievement unlock |
| `fade-to-night` | 1500 ms | `cubic-bezier(0.4, 0, 0.6, 1)` | End of day |

Only `fade-to-night` exceeds 200 ms; everything else is snappy.

### 3. Property tweens (Vue `<Transition>` + small custom utility)

For smaller UI flourishes — cursor flash, score-tick number, dialogue
box slide-up, gauge-bar shrink. We use a tiny utility hook rather than
a heavy library:

```ts
// pitwall-web/src/lib/tween.ts (excerpt)
export function tween(
  from: number, to: number,
  duration: number, easing: (t: number) => number = ease.outCubic,
  onUpdate: (v: number) => void,
): { cancel: () => void } {
  const start = performance.now()
  let raf = 0
  const step = (now: number) => {
    const t = Math.min((now - start) / duration, 1)
    onUpdate(from + (to - from) * easing(t))
    if (t < 1) raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
  return { cancel: () => cancelAnimationFrame(raf) }
}

export const ease = {
  linear:    (t: number) => t,
  outCubic:  (t: number) => 1 - Math.pow(1 - t, 3),
  inOutCubic: (t: number) => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3) / 2,
  outBack:   (t: number) => {
    const c = 1.70158, c3 = c + 1
    return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2)
  },
  outBounce: (t: number) => {
    const n = 7.5625, d = 2.75
    if (t < 1/d) return n*t*t
    if (t < 2/d) { t -= 1.5/d; return n*t*t + 0.75 }
    if (t < 2.5/d) { t -= 2.25/d; return n*t*t + 0.9375 }
    t -= 2.625/d; return n*t*t + 0.984375
  },
}
```

| Element | Animation | Duration | Easing |
|---|---|---|---|
| Cursor on tile change | flash 1 frame ui-coach | 60 ms | linear |
| Cursor on A button | scale 1.0 → 1.2 → 1.0 | 150 ms | `outBack` |
| Score number count-up | 0 → final value | 1.2 s | `outCubic` |
| Dialogue box slide-in (bottom) | translateY 100% → 0 | 200 ms | `outCubic` |
| Achievement toast slide-in | translateX 100% → 0 | 250 ms | `outBack` |
| Achievement toast linger | hold | 2500 ms | — |
| Achievement toast slide-out | translateX 0 → 100% | 200 ms | `inOutCubic` |
| HUD grip-bar shrink | height interpolates to new value | 80 ms | `outCubic` |
| Medal slot-machine ding | scale 0 → 1.2 → 1.0 | 350 ms | `outBack` |
| Lap-best-time pulse | scale 1.0 → 1.05 → 1.0 | 600 ms | `inOutCubic` |
| Map pin pulse | scale 1.0 → 1.1 → 1.0 (loops) | 1000 ms | `inOutCubic` |

## Frame timing reference

A single timing system, used everywhere. All times in milliseconds.

```ts
// pitwall-web/src/lib/timings.ts
export const T = {
  // Cursor
  CURSOR_FLASH:    60,
  CURSOR_BOUNCE:   250,        // Period of the 4 Hz bounce loop = 1000/4
  CURSOR_CONFIRM:  150,

  // Dialogue
  TELETYPE_CHAR:   33,         // ~30 char/sec; max one blip every 30 ms
  DIALOGUE_PAUSE:  300,        // Pause at "." before continuing
  DIALOGUE_FAST:   10,         // Tap-to-fast-forward speed

  // Transitions
  WIPE_FAST:       150,
  WIPE_SLOW:       200,
  FADE_NIGHT:      1500,

  // Score screen
  SCORE_COUNTUP:   1200,
  SCORE_ROW_DELAY: 100,
  MEDAL_DING:      350,

  // HUD
  GRIP_BAR_TWEEN:  80,

  // Achievement
  ACH_SLIDE_IN:    250,
  ACH_LINGER:      2500,
  ACH_SLIDE_OUT:   200,
} as const
```

Single source of truth — no magic numbers in components.

## Reduced motion

When `window.matchMedia('(prefers-reduced-motion: reduce)').matches`:

- Sprite breathing/walking animations pause on the current frame
- Screen wipes shorten to 50 ms (still visible, less jarring)
- Score count-up snaps to final value
- Achievement toast skips slide-in, just appears for 1500 ms
- Cursor stops bouncing
- Map pin stops pulsing

Implementation: a `useReducedMotion()` composable that returns the
matches state and updates on change. Components apply it via class
toggles, not by branching the entire component.

```ts
const reduced = useReducedMotion()

// In template:
<Sprite name="trod" :animation="reduced ? 'idle_static' : 'walk'" />
```

(`idle_static` is a 1-frame variant defined in the sprite sheet for
this case.)

## Animation FPS caps

We don't cap requestAnimationFrame; we cap *what's being updated per
frame*:

- **Sprite frame loops**: capped by `steps()` — they advance at the
  declared FPS regardless of monitor refresh
- **Score count-up + tweens**: tied to `requestAnimationFrame`, so 60 /
  120 / 144 Hz monitors all look smooth
- **HUD updates**: cap at the bridge SSE cue rate (~10 Hz typical) —
  no point updating faster than the data
- **Particle effects (confetti, dust)**: cap at 30 Hz — preserves the
  "old game" feel even on 144 Hz displays

A single `useFrameClock(fps: number)` composable handles the cap:

```ts
export function useFrameClock(fps: number, onTick: () => void) {
  const interval = 1000 / fps
  let last = performance.now()
  let raf = 0
  const loop = (now: number) => {
    if (now - last >= interval) {
      onTick()
      last = now
    }
    raf = requestAnimationFrame(loop)
  }
  onMounted(() => { raf = requestAnimationFrame(loop) })
  onUnmounted(() => cancelAnimationFrame(raf))
}
```

## Frame-perfect Stage Clear sequence

The most choreographed animation in the app. Sequence:

```
t = 0      ms : screen enters, music starts (score_fanfare)
t = 200    ms : "STAGE CLEAR" banner slides down (200 ms outBack)
t = 600    ms : Total score frame appears (instant)
t = 800    ms : Score counts up 0 → final (1200 ms outCubic, ~12 ticks/sec)
t = 2000   ms : Score lands; SFX score_total
t = 2200   ms : Metric row 1 fades in
t = 2300   ms : Metric row 2 fades in
t = 2400   ms : Metric row 3 fades in (etc, 100 ms apart)
t = 2700   ms : Goal results appear together; SFX goal_complete or goal_miss per goal
t = 3200   ms : First medal slides in (if any), 350 ms outBack + medal_award SFX
t = 3700   ms : Second medal (if any)
t = 4200   ms : Third medal (if any)
t = 4700   ms : Coach portrait + dialogue box appear (200 ms slide-up)
t = 4900   ms : Coach line teletypes (~30 char/sec)
t = ~7000  ms : Hint bar appears: "A · CONTINUE · B · HOME"
```

Total animation budget: ~7 s. Skippable with B button at any point —
B jumps straight to the final still frame.

This sequence lives in
`pitwall-web/src/views/StageClear.vue` as one orchestrator function;
each step is a `setTimeout` triggering a state change.

## Don't list

- **No CSS `animation-fill-mode: backwards`** with negative
  delays — confusing.
- **No infinite tweens that adjust DOM layout.** Tweens that change
  layout (height, width) trigger reflow; only color, transform,
  opacity should tween.
- **No `transition: all`.** Always specify the property.
- **No animations during the on-track HUD's high-attention windows.**
  Per `06-audio-design.md`, mid-corner the HUD is mostly static.

## Related

- [`05-routing-map.md`](05-routing-map.md) — wipe directions per route
- [`06-audio-design.md`](06-audio-design.md) — paired audio for each
  visual transition
- [`screens/10-stage-clear.md`](screens/10-stage-clear.md) — the most
  animated screen
