# 23 — Pause / Quick Menu

The Start-button overlay. Available on every screen except the title
and during transitions. **Modal**, not a route.

## Purpose

Verb: **Pause.** Give the player a single place to resume, tweak
settings, end the session, or quit.

## Wireframe (overlay over current screen)

```
┌────────────────────────────────────────────────────────────┐
│ (parent screen at 30 % opacity)                            │
│                                                            │
│           ╔══════════════════════════════════╗             │
│           ║          PAUSED                  ║             │
│           ║  ────────────────────────────    ║             │
│           ║                                  ║             │
│           ║   ▶  RESUME                       ║             │
│           ║      SETTINGS                     ║             │
│           ║      END SESSION FOR THE DAY      ║             │
│           ║      QUIT TO TITLE                ║             │
│           ║                                  ║             │
│           ║                                  ║             │
│           ║  ┌──────┐                         ║             │
│           ║  │ T-ROD│   "Take your time."     ║             │
│           ║  │ idle │                         ║             │
│           ║  └──────┘                         ║             │
│           ╚══════════════════════════════════╝             │
│                                                            │
│  A · CONFIRM   B · RESUME   ◆ RESUME                       │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `summoning` | Start pressed on parent screen | Modal slides down (200 ms outBack); music ducks 50% |
| `idle` | Modal up | Cursor on RESUME by default |
| `confirming-quit` | A on QUIT TO TITLE | Coach `disappointed` + "Are you sure? Unsaved laps will stay in the bridge" |
| `confirming-end-day` | A on END SESSION | Wipes to `14-end-of-day.md` |
| `dismissing` | Resume / B / Start | Modal slides up; music un-ducks |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Bottom-left of modal, 64×64 | Emotion = `relaxed` if parent is paddock-side, `concerned` if parent is on-track HUD, `disappointed` during quit-confirmation |
| `frame-card` 9-slice | Modal background | Static |
| `cursor_arrow` | Active item | Bouncing |

Emotion behavior driven by [`../10-coach-emotions.md`](../10-coach-emotions.md):
the menu surfaces a different coach mood depending on context, so
pausing on-track feels different from pausing in the garage.

## Vue component

```vue
<!-- pitwall-web/src/components/PauseMenu.vue -->
<template>
  <Teleport to="body">
    <Transition name="slide-down-pixel">
      <div v-if="visible" class="pause-overlay">
        <Frame frame-type="card">
          <h2 class="font-title text-title">PAUSED</h2>
          <ul class="menu">
            <MenuItem v-for="(item, i) in items" :key="item.id"
                      :focused="cursor === i"
                      :item="item"
                      @select="onSelect(item.id)" />
          </ul>
          <CoachSpeaksModal
            embedded
            :coach-id="save.preferredCoach"
            :emotion="contextualEmotion"
            text="Take your time."
            :voice-id="`pause_${parentRoute}`"
          />
        </Frame>
      </div>
    </Transition>
  </Teleport>
</template>
```

## Endpoints consumed

None directly. END SESSION FOR THE DAY closes any open SSE connections
on transition; that's local cleanup, not a bridge call.

## Audio cues

| Event | Sound |
|---|---|
| Open | `transition_wipe` (short) + music duck 50% over 200 ms |
| Cursor | `cursor_move` |
| RESUME | `cancel` (soft thud) + un-duck |
| QUIT confirmation | `error_quiet` (hesitation tone) |
| END SESSION | `night_chime` → wipe-to-night |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move cursor between items |
| A | Confirm focused item |
| B | Resume (close modal) |
| Start | Resume (close modal) |
| Escape | Resume (close modal) |

## Edge cases

- **Triggered during a transition** — Start button is no-op while
  `useTransitionStore.inProgress`
- **On-track HUD parent + bridge SSE active** — keep SSE alive
  during pause; resume picks up the latest cue without re-subscribing
- **Title screen parent** — Start button is *not* a pause on the title
  screen (it's the "PRESS START" prompt)
- **Already-confirming-quit, B pressed** — back out of confirmation,
  not out of the menu

## Related

- [`07-controls.md`](../07-controls.md) — Start as the trigger
- [`14-end-of-day.md`](14-end-of-day.md) — destination for END SESSION
- [`13-settings.md`](13-settings.md) — destination for SETTINGS
- [`_coach-speaks-modal.md`](_coach-speaks-modal.md) — embedded coach element
