import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

/**
 * Leaderboard entry shape — the bridge does not yet expose a
 * `/leaderboard` endpoint (multi-driver benchmarking + privacy controls
 * land post-Sonoma). The store is wired against the route anyway, so the
 * moment the bridge ships it, this page Just Works without further PWA
 * changes:
 *
 *   - 404 from the bridge → `endpointMissing = true` (honest empty state)
 *   - other error          → `error = e.message` (red error panel)
 *   - 200                  → `entries` populated from response
 *
 * No fake/mock fallback is synthesised here (no-fakes policy).
 */

export interface LeaderboardEntry {
  rank: number
  initials: string
  car: string
  track: string
  time: string
}

interface LeaderboardResponse {
  entries?: LeaderboardEntry[]
  leaderboard?: LeaderboardEntry[]
}

/**
 * Heuristic: the shared bridge client throws on non-2xx with a message
 * like "Bridge GET /leaderboard failed: Not Found". Treat anything that
 * smells like a missing route as `endpointMissing` so the page can
 * render the "not yet available" state instead of a generic error.
 */
function _looksLike404(msg: string): boolean {
  const m = msg.toLowerCase()
  return m.includes('not found') || m.includes('404')
}

export const useLeaderboardStore = defineStore('leaderboard', {
  state: () => ({
    entries: [] as LeaderboardEntry[],
    isLoading: false,
    /** Last bridge error message (non-404). Null when healthy or missing-route. */
    error: null as string | null,
    /**
     * True when the bridge responded with a 404 for `/leaderboard` — the
     * route simply hasn't been implemented on the backend yet. Distinct
     * from `error` because it isn't a malfunction; it's a known gap.
     */
    endpointMissing: false,
  }),
  actions: {
    async fetchLeaderboard() {
      this.isLoading = true
      try {
        const res = await bridge.get<LeaderboardResponse | LeaderboardEntry[]>(
          '/leaderboard',
        )
        const entries: LeaderboardEntry[] = Array.isArray(res)
          ? res
          : Array.isArray(res?.entries)
            ? res!.entries!
            : Array.isArray(res?.leaderboard)
              ? res!.leaderboard!
              : []
        this.entries = entries
        this.error = null
        this.endpointMissing = false
      } catch (e: any) {
        const msg: string = e?.message ?? String(e)
        if (_looksLike404(msg)) {
          this.endpointMissing = true
          this.error = null
          this.entries = []
        } else {
          this.endpointMissing = false
          this.error = msg
          this.entries = []
        }
      } finally {
        this.isLoading = false
      }
    },
  },
})
