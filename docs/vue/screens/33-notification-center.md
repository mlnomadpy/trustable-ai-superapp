# 33 — Notification Center

Inbox of pending alerts: queued debriefs ready, medals earned,
sessions ready to upload, etc. Reached by tapping the ✉ pulse in the
status bar.

## Purpose

Verb: **Sort.** Single place for all asynchronous events that have
fired but the player hasn't yet acted on.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ NOTIFICATIONS                              4 new           │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ ▶ ⭕ DEBRIEF READY                          2 min ago  ║   │
│ ║      session-20260423-1004 · Tap to read              ║   │
│ ║                                                       ║   │
│ ║   ⭐ NEW MEDAL · TRAIL BRAKE APPRENTICE   12 min ago    ║   │
│ ║      Tap to view in Quest Log                         ║   │
│ ║                                                       ║   │
│ ║   ⚠️ HARDWARE WARNING                       1 hr ago   ║   │
│ ║      TPMS data rate dropped — replace battery?        ║   │
│ ║                                                       ║   │
│ ║   📈 EVOLUTION SNAPSHOT READY              3 hr ago    ║   │
│ ║      Last 5 sessions analysed · Tap to view           ║   │
│ ║                                                       ║   │
│ ║   ✓ SESSION SAVED                          5 hr ago   ║   │
│ ║      session-20260423-0904 · 18 laps · in DuckDB      ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│  A · OPEN     B · BACK     ◆ MARK ALL READ                 │
└────────────────────────────────────────────────────────────┘
```

Each row: status icon (⭕ unread / ⭐ achievement / ⚠️ warning / 📈
analysis / ✓ archive), title, sub-text, timestamp.

## States

| State | Behaviour |
|---|---|
| `idle` | Cursor on first unread row |
| `archive` | Player pressed ◆ MARK ALL READ; visual fade-to-grey on each |
| `empty` | Zero notifications: coach idle + "No new notifications. Drive a session to fill this up." |

## Notification kinds

| Kind | Icon | Source | Action on A |
|---|---|---|---|
| `debrief-ready` | ⭕ | Bridge: queued cloud or local debrief done | Open `10-stage-clear.md` for that session |
| `medal-earned` | ⭐ | Save store mutation | Open `12-quest-log.md` medal detail |
| `level-up` | 🎉 | Save store mutation | Open `04-trainer-card.md` |
| `affinity-tier` | ❤️ | Save store mutation | Open `05-coach-select.md` |
| `track-unlock` | 🗺️ | Save store mutation | Open `06-world-map.md` |
| `hardware-warning` | ⚠️ | Bridge: capability rate-drop alert | Open `15-pit-stall-setup.md` |
| `evolution-ready` | 📈 | Bridge: 5-session window passed | Open `21-driver-evolution.md` |
| `session-saved` | ✓ | Stage clear completion | (no action; just confirmation) |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Top-right corner, 32×32 | Emotion = `analyzing` (per `../10-coach-emotions.md`) |
| Status icons | Per row, 16×16 | Static |
| Cursor | Active row | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/NotificationCenter.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">NOTIFICATIONS</h1>
    <p class="text-body">{{ unreadCount }} new</p>

    <NotificationList :items="items" :focus="cursor"
                      @select="open" />

    <EmptyState v-if="!items.length"
                :coach="save.preferredCoach"
                emotion="relaxed"
                text="No new notifications. Drive a session to fill this up." />

    <HintBar :hints="['A · OPEN', 'B · BACK', '◆ MARK ALL READ']" />
  </div>
</template>

<script setup lang="ts">
import { useNotificationsStore } from '@/stores/notifications'
const { items, unreadCount, markAllRead, markRead, navigateTo } = useNotificationsStore()
</script>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| SSE `/notifications` (proposed) | Bridge surfaces queued events as they happen |
| `GET /notifications?since=<ISO>` (proposed) | Backfill on page load |

Save-store-driven notifications (medals, level-up, affinity tier) are
local — no bridge call needed.

## Audio cues

| Event | Sound |
|---|---|
| Open notification center | `cursor_select` |
| Cursor row | `cursor_move` |
| A on a row | `cursor_select` → wipe to destination |
| MARK ALL READ | `cancel` (soft thud — like sweeping crumbs off the table) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Cursor between rows |
| A | Open the focused notification's destination + mark read |
| B | Back to garage hub |
| Start | Pause menu |
| ◆ | Mark all as read |

## Edge cases

- **Bridge offline** — local notifications still show; bridge-sourced
  ones wait until reconnect
- **Empty state on first launch** — coach line: *"You haven't earned
  anything yet. Let's go drive."*
- **Notification list > 50** — paginate (20 per page); old read ones
  auto-evict after 30 days
- **Evolution snapshot ready but driver only has 4 sessions** —
  notification doesn't fire (the threshold is 5 per ADR-015 §
  evolution endpoint)

## Related

- Status bar `✉` indicator pulses while `unreadCount > 0`
- [`12-quest-log.md`](12-quest-log.md), [`04-trainer-card.md`](04-trainer-card.md), [`10-stage-clear.md`](10-stage-clear.md), [`15-pit-stall-setup.md`](15-pit-stall-setup.md), [`21-driver-evolution.md`](21-driver-evolution.md), [`06-world-map.md`](06-world-map.md), [`05-coach-select.md`](05-coach-select.md) — possible destinations
