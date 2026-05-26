# 00 — Title

The first thing the player sees. Sets the tone for everything that
follows.

## Purpose

Verb: **Begin.** Communicate "this is a game" in two seconds, invite the
player to enter.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│             ░░░░░░░░ Sonoma silhouette ░░░░░░              │
│            ░░░░ T11 corner at sunset ░░░░░░░               │
│           ░░░░░ parallax 4-layer ░░░░░░░                   │
│                                                            │
│          ╔══════════════════════════════╗                  │
│          ║                              ║                  │
│          ║         ▓▓▓▓ ▓▓▓▓ ▓▓▓▓        ║                  │
│          ║         PITWALL              ║                  │
│          ║         ▓▓▓▓ ▓▓▓▓ ▓▓▓▓        ║                  │
│          ║                              ║                  │
│          ║       AI RACING COACH         ║                  │
│          ╚══════════════════════════════╝                  │
│                                                            │
│                                                            │
│                ▶ PRESS  START ◀                            │
│                  (blink @ 2 Hz)                            │
│                                                            │
│                                                            │
│              © 2026  Sonoma Edition                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `boot` | First mount | Logo wipes in (300 ms); chime fanfare plays once |
| `idle` | After boot | "PRESS START" blinks at 2 Hz; parallax background scrolls slowly; T-Rod walks across foreground every ~30 s |
| `pressed` | A or Start button | Logo flashes white once; wipe-right transition to save-select |

## Sprite usage

| Sprite | Where | Frame |
|---|---|---|
| `logo_pitwall_256x64` | Centre | 1 frame, static |
| `start_arrows_animated` | Below logo | 2 frames at 2 Hz (the ▶ ◀ arrows blink with text) |
| `trod` | Bottom of screen, occasionally | `walk_r` cycle, 4 frames @ 6 Hz |
| `bg_sonoma_t11_dusk` | Background | 4 layers each panning at 0.5×, 1×, 2×, 4× cursor-y position |
| Cursor | Hidden on this screen | — |

## Vue component

```vue
<!-- pitwall-web/src/views/TitleScreen.vue -->
<template>
  <div class="viewport">
    <ParallaxBg :layers="['sky', 'hills-far', 'hills-near', 'kerb']"/>

    <Sprite name="logo_pitwall" class="title-logo"/>
    <p class="font-title text-title-lg text-ui-text-300">AI RACING COACH</p>

    <div v-if="!pressed" class="press-start">
      <span class="font-title blink">▶ PRESS  START ◀</span>
    </div>

    <Sprite v-if="showWanderer"
            name="trod" animation="walk_r"
            class="absolute bottom-12 left-0"
            :style="{ transform: `translateX(${wandererX}px)` }"/>

    <p class="copyright">© 2026  Sonoma Edition</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { audio } from '@/lib/audio'
import { useRouter } from 'vue-router'
import { useTransitionStore } from '@/stores/transition'
const router = useRouter(), trans = useTransitionStore()
const pressed = ref(false), showWanderer = ref(false), wandererX = ref(-100)

onMounted(() => {
  audio.playSfx('boot_chime')
  audio.playMusic('title_loop')
  setTimeout(() => { showWanderer.value = true; animateWanderer() }, 5000)
})

function animateWanderer() {
  // T-Rod walks left to right over 8 s, then disappears for 30 s
  /* … requestAnimationFrame loop … */
}

function start() {
  if (pressed.value) return
  pressed.value = true
  audio.playSfx('cursor_select')
  setTimeout(() => router.push({ name: 'save' }), 200)
}

// Bind A + Start to start()
</script>
```

## Endpoints consumed

None. Title screen runs entirely client-side. (Optional: `GET /health`
in the background to warn if the bridge is offline before the player
gets to a screen that needs it.)

## Audio cues

| Event | Sound |
|---|---|
| Mount | `boot_chime` (one-shot) + `title_loop` (music starts) |
| START pressed | `cursor_select` |
| Music ducks during transition | yes, 200 ms fade |

## Input map

| Input | Action |
|---|---|
| A / Start / Z / Enter / Tap anywhere | Start (advance to save-select) |
| Everything else | No-op |

## Edge cases

- **Bridge unreachable on boot** — Title still appears. A small "○"
  indicator appears in the corner; player can press START anyway. The
  save-select / onboarding flow doesn't need the bridge until the
  driver enters the garage hub.
- **`prefers-reduced-motion`** — parallax layers stop scrolling;
  T-Rod doesn't wander; PRESS START doesn't blink (just shows static).
- **Multiple A presses in quick succession** — `pressed` flag debounces;
  only the first triggers the transition.

## Related

- [`01-save-select.md`](01-save-select.md) — next screen
- [`01-visual-language.md`](../01-visual-language.md) — palette, fonts
- [`06-audio-design.md`](../06-audio-design.md) — `boot_chime` and
  `title_loop` specs
