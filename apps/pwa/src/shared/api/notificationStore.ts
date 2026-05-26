import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

/**
 * Notification kinds emitted by the bridge's `emit_notification(...)` helper
 * in `pitwall/features/realtime/bp_realtime.py`. The SSE stream at
 * `/notifications` (and any future JSON aggregator on the same path) uses
 * these `kind` values to fan out async events to the PWA's notification
 * center.
 */
export type NotificationKind =
  | 'debrief-ready'
  | 'medal-earned'
  | 'level-up'
  | 'affinity-tier'
  | 'track-unlock'
  | 'hardware-warning'
  | 'evolution-ready'
  | 'session-saved'

/**
 * Shape of a notification as rendered in the UI. The store maps the
 * bridge's raw event envelope ({ ts, kind, driver, ...fields }) into this
 * UI-friendly form via `_normalize()`.
 *
 * Inferred from bridge source:
 *   `src/pitwall/features/realtime/bp_realtime.py::emit_notification(...)`
 *   which publishes { ts: float, kind: str, driver: str|None, **fields }.
 * The kind-specific `fields` are documented in `screens/33-notification-center.md`
 * (debrief-ready, medal-earned, level-up, affinity-tier, track-unlock,
 *  hardware-warning, evolution-ready, session-saved).
 */
export interface AppNotification {
  id: string
  kind: NotificationKind | string
  title: string
  subText: string
  timestamp: string
  isRead: boolean
  route?: string
}

/**
 * Raw envelope as the bridge publishes it. We don't trust any of these
 * fields — every read is coalesced through `_normalize` with sane fallbacks.
 */
interface BridgeNotificationEvent {
  ts?: number
  kind?: string
  driver?: string | null
  title?: string
  message?: string
  body?: string
  text?: string
  route?: string
  [k: string]: unknown
}

interface NotificationsResponse {
  notifications?: BridgeNotificationEvent[]
}

const POLL_INTERVAL_MS = 30_000

function _fmtTimestamp(ts: number | undefined): string {
  if (!ts || !Number.isFinite(ts)) return ''
  // Bridge timestamps are unix seconds (per `time.time()`).
  const ms = ts < 1e12 ? ts * 1000 : ts
  try {
    const d = new Date(ms)
    return d.toLocaleString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      month: 'short',
      day: '2-digit',
    })
  } catch {
    return ''
  }
}

function _titleForKind(kind: string): string {
  switch (kind) {
    case 'debrief-ready':    return 'DEBRIEF READY'
    case 'medal-earned':     return 'MEDAL EARNED'
    case 'level-up':         return 'LEVEL UP'
    case 'affinity-tier':    return 'AFFINITY TIER'
    case 'track-unlock':     return 'TRACK UNLOCKED'
    case 'hardware-warning': return 'HARDWARE WARNING'
    case 'evolution-ready':  return 'EVOLUTION READY'
    case 'session-saved':    return 'SESSION SAVED'
    default:                 return kind.toUpperCase().replace(/[-_]/g, ' ')
  }
}

function _normalize(ev: BridgeNotificationEvent, idx: number): AppNotification {
  const kind = (ev.kind ?? 'notification') as NotificationKind | string
  const explicitTitle =
    (typeof ev.title === 'string' && ev.title.trim()) ? ev.title.trim() : ''
  const subText =
    (typeof ev.message === 'string' && ev.message.trim()) ? ev.message.trim()
    : (typeof ev.body === 'string' && ev.body.trim()) ? ev.body.trim()
    : (typeof ev.text === 'string' && ev.text.trim()) ? ev.text.trim()
    : ''
  return {
    id: `${ev.ts ?? Date.now()}-${kind}-${idx}`,
    kind,
    title: explicitTitle || _titleForKind(String(kind)),
    subText,
    timestamp: _fmtTimestamp(ev.ts),
    isRead: false,
    route: typeof ev.route === 'string' ? ev.route : undefined,
  }
}

export const useNotificationsStore = defineStore('notifications', {
  state: () => ({
    items: [] as AppNotification[],
    loading: false,
    error: null as string | null,
    _pollTimer: null as number | null,
  }),
  getters: {
    unreadCount: (state) => state.items.filter(i => !i.isRead).length,
  },
  actions: {
    markRead(id: string) {
      const item = this.items.find(i => i.id === id)
      if (item) item.isRead = true
    },
    markAllRead() {
      this.items.forEach(i => { i.isRead = true })
    },
    /**
     * Local-only injection — kept for completeness so other features
     * (e.g. client-side debrief-ready hints) can still push items
     * without a round-trip. The bridge fetch is the source of truth.
     */
    add(notification: Omit<AppNotification, 'id' | 'isRead'>) {
      this.items.unshift({
        ...notification,
        id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        isRead: false,
      })
    },

    async fetch() {
      this.loading = true
      try {
        const res = await bridge.get<NotificationsResponse | BridgeNotificationEvent[]>(
          '/notifications',
        )
        // The bridge contract is `{ notifications: [...] }`; tolerate a
        // bare-array variant in case the route is later normalized.
        const raw: BridgeNotificationEvent[] = Array.isArray(res)
          ? res
          : Array.isArray(res?.notifications) ? res!.notifications! : []

        // Preserve read-state for items we've already seen, by id.
        const previouslyRead = new Set(
          this.items.filter(i => i.isRead).map(i => i.id),
        )
        const fresh = raw.map((ev, i) => _normalize(ev, i))
        for (const item of fresh) {
          if (previouslyRead.has(item.id)) item.isRead = true
        }
        this.items = fresh
        this.error = null
      } catch (e: any) {
        this.error = e?.message ?? String(e)
        // No-fakes policy: do NOT clear items on transient errors; just
        // surface the failure. But if we've never loaded, leave empty.
      } finally {
        this.loading = false
      }
    },

    /** Begin polling `/notifications` every 30s. Idempotent. */
    startPolling() {
      if (this._pollTimer != null) return
      // Fire immediately then schedule.
      void this.fetch()
      this._pollTimer = window.setInterval(() => {
        void this.fetch()
      }, POLL_INTERVAL_MS)
    },

    stopPolling() {
      if (this._pollTimer != null) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
    },
  },
})
