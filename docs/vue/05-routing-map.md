# 05 — Routing map

Vue Router setup. Every screen is a route; transitions are managed
explicitly (we don't rely on Vue's `<transition>` defaults — pixel-art
wipes need control over duration and direction).

## Routes

```ts
// pitwall-web/src/router.ts (excerpt)
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/',                name: 'title',      component: TitleScreen },
  { path: '/save',            name: 'save',       component: SaveSlot,    meta: { wipe: 'right' } },
  { path: '/onboarding/:step', name: 'onboarding', component: Onboarding,  meta: { wipe: 'right' } },
  { path: '/garage',          name: 'garage',     component: GarageHub,   meta: { wipe: 'right', requiresSave: true } },
  { path: '/garage/trainer',  name: 'trainer',    component: TrainerCard, meta: { wipe: 'right', requiresSave: true } },
  { path: '/garage/coach',    name: 'coach',      component: CoachSelect, meta: { wipe: 'right', requiresSave: true } },
  { path: '/garage/settings', name: 'settings',   component: Settings,    meta: { wipe: 'right', requiresSave: true } },
  { path: '/garage/quests',   name: 'quests',     component: QuestLog,    meta: { wipe: 'right', requiresSave: true } },
  { path: '/world',           name: 'world',      component: WorldMap,    meta: { wipe: 'right', requiresSave: true } },
  { path: '/track/:trackId',  name: 'pre-brief',  component: PreBrief,    meta: { wipe: 'right', requiresSave: true } },
  { path: '/track/:trackId/drive', name: 'drive', component: OnTrackHud,  meta: { wipe: 'down', fullscreen: true, requiresSave: true } },
  { path: '/track/:trackId/cooldown', name: 'cooldown', component: CoolDown, meta: { wipe: 'up', requiresSave: true } },
  { path: '/track/:trackId/clear', name: 'clear', component: StageClear,  meta: { wipe: 'right', requiresSave: true } },
  { path: '/replay/:sessionId', name: 'replay',   component: Replay,      meta: { wipe: 'right', requiresSave: true } },
  { path: '/eod',             name: 'eod',        component: EndOfDay,    meta: { wipe: 'fade-night', requiresSave: true } },

  // Catch-all → title
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
```

## Navigation graph

```mermaid
flowchart TB
  classDef boot   fill:#1a1d2e,stroke:#3d4458,color:#f8f8f0
  classDef garage fill:#2a2f4a,stroke:#3d4458,color:#f8f8f0
  classDef session fill:#5d4a1a,stroke:#8a6e3a,color:#f8f8f0

  T[/]:::boot
  S[/save]:::boot
  O[/onboarding/*]:::boot

  G[/garage]:::garage
  TC[/garage/trainer]:::garage
  CO[/garage/coach]:::garage
  ST[/garage/settings]:::garage
  QL[/garage/quests]:::garage

  W[/world]:::session
  PB[/track/:trackId]:::session
  D[/track/:trackId/drive]:::session
  CD[/track/:trackId/cooldown]:::session
  SC[/track/:trackId/clear]:::session
  R[/replay/:sessionId]:::session
  E[/eod]:::session

  T --> S
  S --> O
  S --> G
  G --> TC
  G --> CO
  G --> ST
  G --> QL
  G --> W
  G --> R
  G --> E
  TC --> G
  CO --> G
  ST --> G
  QL --> G
  W --> PB
  PB --> D
  D --> CD
  CD --> SC
  SC --> G
  SC --> R
  R --> G
  E --> T
```

## Transition rules

Each route's `meta.wipe` declares the visual transition into that
route. Implementation is centralised in `useTransitionStore`:

```ts
// pitwall-web/src/stores/transition.ts
export const useTransitionStore = defineStore('transition', {
  state: () => ({
    direction: null as 'right' | 'left' | 'up' | 'down' | 'fade-night' | null,
    inProgress: false,
  }),
  actions: {
    async play(direction: NonNullable<TransitionDirection>) {
      this.direction  = direction
      this.inProgress = true
      // Trigger the wipe sprite animation; resolve after 150-1500 ms
      await new Promise(resolve => setTimeout(resolve, durationFor(direction)))
      this.inProgress = false
      this.direction  = null
    },
  },
})

router.beforeEach(async (to, from, next) => {
  const trans = useTransitionStore()
  const wipe  = (to.meta.wipe ?? 'right') as TransitionDirection
  await trans.play(wipe)
  next()
})
```

## Guards

### `requiresSave`

Most routes need an active save slot. Routes with `meta.requiresSave: true`
are guarded:

```ts
router.beforeEach((to, from, next) => {
  const save = useSaveStore()
  if (to.meta.requiresSave && save.activeSlotId === null) {
    return next({ name: 'save' })
  }
  next()
})
```

### `fullscreen`

`/track/:trackId/drive` (the on-track HUD) requests `fullscreen` mode
on entry and acquires a `wakeLock`:

```ts
router.beforeEach(async (to, from, next) => {
  if (to.meta.fullscreen) {
    try {
      await document.documentElement.requestFullscreen()
      await navigator.wakeLock?.request('screen')
    } catch { /* user can decline; HUD still works */ }
  }
  if (from.meta.fullscreen && !to.meta.fullscreen) {
    document.exitFullscreen?.()
  }
  next()
})
```

## Deep linking

The PWA is single-page; deep links work for screens that don't depend
on transient state:

| Allowed deep links | Use |
|---|---|
| `/` | Always — title screen |
| `/save` | Always — save-slot select |
| `/garage` | Requires save slot; redirects to `/save` if none |
| `/garage/trainer` | Requires save slot |
| `/garage/coach` | Requires save slot |
| `/garage/settings` | Requires save slot |
| `/world` | Requires save slot |
| `/track/sonoma` | Requires save slot |
| `/replay/<sessionId>` | Requires save slot AND that session belongs to it |

Disallowed deep links (always redirect to `/garage`):
- `/track/<id>/drive` — must come from pre-brief
- `/track/<id>/cooldown` — must come from drive
- `/track/<id>/clear` — must come from cooldown
- `/onboarding/<step>` for step > 1 — must come from save-select

## URL design rationale

We could keep everything as one route with a `?screen=` query param.
We don't, because:

1. Browser back button maps to "B button" cleanly when each screen has
   a real URL.
2. `pitwall-web/screens/<name>.md` doc references map 1:1 to URL paths.
3. Service worker can pre-cache route-specific resources (sprites,
   audio) on first visit to that route.
4. Deep linking from notifications (e.g., "your queued debrief is ready
   → /track/sonoma/clear/<sessionId>") works without state shenanigans.

## Related

- [`04-state-architecture.md`](04-state-architecture.md) — store hydration
- [`08-animation-spec.md`](08-animation-spec.md) — wipe timings + easing
- Each screen doc under `screens/` documents its entry/exit conditions
