# 09 — Tech stack

The exact libraries, versions, and configuration. Concrete enough that
"npm create" + this doc produces a working scaffold.

## Stack at a glance

| Layer | Pick | Version (as of 2026-04-29) | Why |
|---|---|---|---|
| Framework | Vue 3 (Composition API + `<script setup>`) | 3.5+ | Smaller bundle than React, cleaner template syntax for game-style menus |
| Build | Vite | 6.0+ | Sub-100 ms HMR; out-of-the-box PWA support |
| Language | TypeScript | 5.5+ | Strict mode; `tsconfig.json` extends `@vue/tsconfig` |
| Routing | Vue Router | 4.4+ | Standard; meta fields drive the wipe-direction logic |
| State | Pinia | 2.2+ | First-party Vue store; well-typed; Composition-API-friendly |
| Styling | Tailwind | 4.0+ | Design tokens map cleanly to the GBA palette |
| Persistence | `idb-keyval` | 6.2+ | 200-line wrapper around IndexedDB; no schema headaches |
| SQL Analytics | `@duckdb/duckdb-wasm` | 1.x | Client-side SQL on cached Parquet |
| Charts | `vue-chartjs` + `chart.js` | 5.x + 4.x | Light, retro-themable; one chart engine, not two |
| Audio | Howler.js | 2.2+ | Single Web Audio wrapper; mute/volume/pool |
| Sprite system | Custom — `Sprite.vue` reading TexturePacker JSON | — | No game-engine dependency; ~80 LoC |
| TTS (live fallback) | Web Speech API | native | When pre-rendered MP3 isn't available |
| HTTP client | Native `fetch` | native | No axios/ofetch; the bridge is localhost, no auth, no retry magic needed |
| SSE | Native `EventSource` | native | For the live cue stream |
| PWA | `vite-plugin-pwa` (Workbox) | 0.20+ | Service worker + manifest in 5 lines of config |
| Testing | Vitest | 2.x | Same Vite pipeline; co-located test files |
| Linting | ESLint + `eslint-config-vue-typescript` | latest | Standard Vue 3 + TS lint rules |
| Code formatting | Prettier with the Tailwind plugin | latest | Class sort order matters for diffs |

Total `dependencies` count target: **< 20** runtime packages. The
bundle should be < 600 KB gz before sprite assets.

## Project layout

```
pitwall-web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── index.html
│
├── public/
│   ├── manifest.webmanifest
│   ├── sw.js                            # written by vite-plugin-pwa
│   ├── icons/
│   │   ├── icon-192.png
│   │   └── icon-512.png
│   ├── fonts/
│   │   ├── PressStart2P-Regular.woff2
│   │   ├── m6x11.woff2
│   │   └── DSEG7Classic-Regular.woff2
│   ├── sprites/                          # all packed sheets + JSON
│   ├── audio/                            # SFX + voice clips
│   └── tracks/                           # track-specific backgrounds
│
├── src/
│   ├── main.ts                           # app boot
│   ├── App.vue                           # root w/ <RouterView>
│   ├── router.ts                         # routes per docs/vue/05-routing-map.md
│   │
│   ├── views/                            # one per screen, see screens/*.md
│   │   ├── TitleScreen.vue
│   │   ├── SaveSlot.vue
│   │   ├── Onboarding.vue
│   │   ├── GarageHub.vue
│   │   ├── TrainerCard.vue
│   │   ├── CoachSelect.vue
│   │   ├── WorldMap.vue
│   │   ├── PreBrief.vue
│   │   ├── OnTrackHud.vue
│   │   ├── CoolDown.vue
│   │   ├── StageClear.vue
│   │   ├── Replay.vue
│   │   ├── QuestLog.vue
│   │   ├── Settings.vue
│   │   └── EndOfDay.vue
│   │
│   ├── components/
│   │   ├── Sprite.vue                    # canonical sprite renderer
│   │   ├── Frame.vue                     # 9-slice frame wrapper
│   │   ├── DialogueBox.vue               # teletype text + portrait
│   │   ├── Cursor.vue                    # bouncing arrow
│   │   ├── PixelButton.vue               # tile button
│   │   ├── GripBar.vue                   # HUD left bar
│   │   ├── OverBar.vue                   # HUD right bar
│   │   ├── TrackMap.vue                  # 2D pixel-art track render
│   │   ├── PixelChart.vue                # chart.js wrapper themed pixel
│   │   ├── MedalGrid.vue
│   │   ├── HintBar.vue
│   │   ├── StatusBar.vue
│   │   ├── VirtualGamepad.vue            # touch D-pad overlay
│   │   └── Toast.vue                     # achievement notifications
│   │
│   ├── stores/                           # Pinia, see docs/vue/04-state-architecture.md
│   │   ├── save.ts
│   │   ├── session.ts
│   │   ├── bridge.ts
│   │   ├── duckdb.ts
│   │   ├── audio.ts
│   │   ├── sprites.ts
│   │   ├── dialogue.ts
│   │   ├── coach.ts
│   │   ├── cue.ts
│   │   └── transition.ts
│   │
│   ├── lib/
│   │   ├── bridge.ts                     # typed HTTP client (50 endpoints)
│   │   ├── sse.ts                        # cue stream wrapper
│   │   ├── ble.ts                        # NOT NEEDED (per ADR-016 — CAN+USB)
│   │   ├── tween.ts                      # tween + easing
│   │   ├── timings.ts                    # T constants from docs/vue/08
│   │   ├── teletype.ts                   # dialogue char-by-char
│   │   ├── audio.ts                      # Howler wrapper
│   │   ├── voice.ts                      # TTS pre-render lookup + Web Speech fallback
│   │   ├── reducedMotion.ts              # composable
│   │   ├── viewportScale.ts              # composable
│   │   └── input/
│   │       ├── keyboard.ts
│   │       ├── gamepad.ts
│   │       └── touchpad.ts               # virtual D-pad logic
│   │
│   ├── types/                            # one .ts per domain object
│   │   ├── save.ts
│   │   ├── coach.ts
│   │   ├── session.ts
│   │   ├── bridge.ts                     # types generated from api.md
│   │   └── sprite.ts
│   │
│   └── styles/
│       ├── tokens.css                    # CSS custom properties
│       └── pixel.css                     # image-rendering: pixelated rules
│
├── tests/
│   ├── components/
│   │   ├── Sprite.test.ts
│   │   ├── DialogueBox.test.ts
│   │   └── …
│   ├── stores/
│   │   ├── save.test.ts
│   │   └── …
│   └── lib/
│       └── teletype.test.ts
│
└── scripts/
    ├── voice-bake.ts                      # generate TTS clips per coach
    ├── sfx-bake.ts                        # regenerate SFX from seeds
    ├── bridge-types.ts                    # codegen TS types from api.md
    └── sprite-pack.ts                     # post-process TexturePacker output
```

## `package.json` (excerpt)

```jsonc
{
  "name": "pitwall-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev":     "vite",
    "build":   "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test":    "vitest",
    "lint":    "eslint . --ext .ts,.vue",
    "format":  "prettier --write \"src/**/*.{ts,vue,css}\"",
    "voice":   "tsx scripts/voice-bake.ts",
    "sfx":     "tsx scripts/sfx-bake.ts",
    "types":   "tsx scripts/bridge-types.ts"
  },
  "dependencies": {
    "vue":                "^3.5.0",
    "vue-router":         "^4.4.0",
    "pinia":              "^2.2.0",
    "@duckdb/duckdb-wasm":"^1.29.0",
    "chart.js":           "^4.4.0",
    "vue-chartjs":        "^5.3.0",
    "howler":             "^2.2.4",
    "idb-keyval":         "^6.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue":   "^5.1.0",
    "@vitest/ui":           "^2.0.0",
    "@vue/tsconfig":        "^0.7.0",
    "autoprefixer":         "^10.4.0",
    "eslint":               "^9.10.0",
    "eslint-plugin-vue":    "^9.30.0",
    "prettier":             "^3.4.0",
    "prettier-plugin-tailwindcss": "^0.6.0",
    "tailwindcss":          "^4.0.0",
    "tsx":                  "^4.20.0",
    "typescript":           "^5.5.0",
    "vite":                 "^6.0.0",
    "vite-plugin-pwa":      "^0.20.0",
    "vitest":               "^2.0.0",
    "vue-tsc":              "^2.1.0"
  }
}
```

## `vite.config.ts`

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Pitwall',
        short_name: 'Pitwall',
        description: 'AI Racing Coach',
        theme_color: '#0d0d12',
        background_color: '#0d0d12',
        display: 'fullscreen',
        orientation: 'portrait',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,woff2,mp3,json}'],
        // Pre-cache the active coach's voice pack lazily
        runtimeCaching: [
          {
            urlPattern: /\/audio\/coaches\/.+\.mp3$/,
            handler: 'CacheFirst',
            options: { cacheName: 'coach-voices', expiration: { maxEntries: 300 } },
          },
          {
            urlPattern: /127\.0\.0\.1:8765\/(session|driver|track|coach|markers)/,
            handler: 'NetworkFirst',
            options: { cacheName: 'bridge', networkTimeoutSeconds: 3 },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    // Proxy bridge calls during dev so localhost:8765 isn't a CORS issue
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', rewrite: p => p.replace(/^\/api/, '') },
    },
  },
})
```

## `tailwind.config.ts` (excerpt)

```ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,vue}'],
  theme: {
    extend: {
      colors: {
        // (palette from docs/vue/01-visual-language.md)
        ink:        '#1a1d2e',
        charcoal:   '#2a2f42',
        slate:      '#3d4458',
        silver:     '#6e7686',
        red:        { deep: '#8a2828', mid: '#c93838', light: '#e85858' },
        skin:       { shadow: '#b07658', mid: '#d89878', light: '#ecb898' },
        ui:         { good: '#2aa198', warn: '#b58900', bad: '#dc322f',
                      info: '#4a98c8', quest: '#d3a832', coach: '#c93838' },
        asphalt:    { deep: '#1f2230', mid: '#2c3242', light: '#3d4458' },
      },
      fontFamily: {
        title: ['"Press Start 2P"', 'monospace'],
        ui:    ['"m6x11"', 'monospace'],
        nums:  ['"DSEG7-Classic"', 'monospace'],
      },
      fontSize: {
        'title-lg': ['16px', '20px'],
        'title':    ['12px', '16px'],
        'body':     ['8px',  '10px'],
        'small':    ['6px',  '8px'],
        'num-lg':   ['14px', '18px'],
        'num':      ['10px', '12px'],
      },
    },
  },
  plugins: [],
} satisfies Config
```

## Bridge type generation

The `scripts/bridge-types.ts` script generates TypeScript types for
all 50 bridge endpoints from `docs/api.md`'s example payloads. Run on
demand:

```bash
pnpm types
# → src/types/bridge.ts updated; commit it
```

Strategy: parse the `jsonc` blocks in `api.md`, infer types via
`json-schema-to-typescript`. Manual review on each codegen change.

## Performance budgets

| Metric | Target | Hard limit |
|---|---|---|
| Cold start (Title screen visible) | 1.5 s | 3 s |
| Save-select to Garage Hub | 200 ms | 500 ms |
| Sprite pack load | 300 ms (cached) | 1 s (cold) |
| DuckDB-Wasm load | 800 ms (lazy) | 2 s |
| HUD frame budget | 16 ms | 33 ms |
| Service worker pre-cache | 2 MB | 4 MB |
| Total bundle (gz, no sprites) | 600 KB | 1 MB |

## Don't list

- **No `axios`.** `fetch` is fine; the bridge is localhost.
- **No `lodash`.** Specific functions only via `lodash-es` if absolutely
  needed; we don't add dep weight for `debounce`.
- **No `pixi.js` / Phaser / babylon.** They'd give us animation
  power we don't need. CSS sprite sheets + small custom helpers are
  enough.
- **No `vue-i18n`.** English-only for May 23. Localisation is
  post-Sonoma; the strings are in component templates for now.
- **No `framer-motion`-equivalent.** CSS keyframes + the small `tween()`
  utility cover everything in `08-animation-spec.md`.
- **No `axios` retry / backoff library.** The bridge is local; if it's
  not responding, surface the error visibly.

## Related

- [`04-state-architecture.md`](04-state-architecture.md) — what each
  store does
- [`05-routing-map.md`](05-routing-map.md) — Vue Router config
- [`06-audio-design.md`](06-audio-design.md) — Howler integration
- [`07-controls.md`](07-controls.md) — input subsystems
- [`08-animation-spec.md`](08-animation-spec.md) — animation primitives
