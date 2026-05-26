# 01 — Save Slot Select

Three slots. The driver picks which save to load (or starts a new one).

## Purpose

Verb: **Identify.** "Which driver am I tonight?" Multi-driver households
share a phone; each gets a slot.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ SELECT  SAVE  SLOT                                         │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ ▶ SLOT 1                                             ║   │
│ ║   ┌──┐  TAHA · LV.12 · INTERMEDIATE                   ║   │
│ ║   │██│  BMW M3 (E46) · 47 SESSIONS                    ║   │
│ ║   │██│  ★ BEST 1:46.8 · 14 MEDALS                     ║   │
│ ║   └──┘  LAST PLAYED · YESTERDAY                       ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║   SLOT 2                                             ║   │
│ ║          NEW DRIVER                                  ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║   SLOT 3                                             ║   │
│ ║          NEW DRIVER                                  ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│  ▶ A · LOAD     B · DELETE     ◀ ▶ MOVE                    │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Behaviour |
|---|---|
| `loading` | Hydrate from IndexedDB on mount |
| `idle` | Cursor on first non-empty slot (or slot 1 if all empty) |
| `confirming-delete` | Show "ARE YOU SURE?" dialogue with coach's `disappointed` portrait |

## Sprite usage

- Driver avatar (per-slot): `avatars` sheet, `idle` frame, 64×64
- Cursor: `ui/cursor_arrow`
- Tile frame: `ui/frame-default` 9-slice

## Vue component

```vue
<!-- pitwall-web/src/views/SaveSlot.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">SELECT SAVE SLOT</h1>

    <div class="slot-list">
      <SlotCard v-for="(slot, i) in save.slots" :key="i"
                :slot="slot" :slot-id="(i + 1) as 1 | 2 | 3"
                :focused="cursor === i"
                @select="handleSelect(i + 1)"
                @delete="confirmDelete(i + 1)" />
    </div>

    <DialogueBox v-if="confirming"
                 :coach-id="save.slots[confirming - 1]?.preferredCoach ?? 'trod'"
                 emotion="disappointed"
                 :text="`Delete ${save.slots[confirming - 1]?.driverName}?`"
                 @yes="doDelete" @no="confirming = null" />

    <HintBar :hints="hints" />
  </div>
</template>
```

## Endpoints consumed

None directly. Save data is in IndexedDB; bridge isn't needed until the
driver enters the garage hub.

## Audio cues

| Event | Sound |
|---|---|
| Cursor up/down | `cursor_move` |
| A on filled slot | `cursor_select` → wipe to `/garage` |
| A on empty slot | `cursor_select` → wipe to `/onboarding/1` |
| B on filled slot | `cancel` → confirm-delete dialogue |
| Delete confirmed | `cancel` (heavier) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move cursor between slots |
| A | Load (filled) or create (empty) |
| B | Delete (filled) or back to title (empty + cursor on empty) |
| Start | No-op |

## Edge cases

- **All slots empty** — cursor lands on slot 1; A creates new driver
- **Storage quota exceeded** — show inline "save unavailable" warning;
  read-only mode (can't create new, can load existing)
- **Slot file corrupted** — render as "CORRUPTED · DELETE TO RESTORE"; A
  triggers delete flow

## Related

- [`02-onboarding.md`](02-onboarding.md) — when slot is empty
- [`04-state-architecture.md`](../04-state-architecture.md) — save format
