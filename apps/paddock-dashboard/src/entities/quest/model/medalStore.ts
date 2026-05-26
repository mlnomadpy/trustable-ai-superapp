// MEDALS BACKEND DOES NOT EXIST YET. This store returns empty + flag.
// Consumer UI must show "DATA UNAVAILABLE" — do NOT add a fallback here.
import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

export interface Medal {
  id: string
  tier: string
  name: string
  desc: string
  unlocked: boolean
}

/**
 * MedalStore — placeholder for the future medal/achievement system.
 *
 * Backend endpoint (`/medals` or `/achievements`) does not exist yet. We
 * attempt the call so the day it ships nothing has to change here; until
 * then `endpointMissing` will be `true` and `medals` will stay `[]`.
 *
 * Consumers MUST render an honest "MEDALS UNAVAILABLE — backend not
 * implemented" state when `endpointMissing` is true, and a real error
 * state when `error` is set. Do not synthesize medals from any other
 * data source.
 */
export const useMedalStore = defineStore('medal', {
  state: () => ({
    medals: [] as Medal[],
    isLoading: false,
    error: null as string | null,
    /** True when the backend returned 404 — the endpoint is not implemented yet. */
    endpointMissing: false,
    _attempted: false,
  }),

  getters: {
    unlockedCount: (state) => state.medals.filter((m) => m.unlocked).length,
    totalCount: (state) => state.medals.length,
    byTier: (state) => (tier: string) =>
      tier === 'ALL' ? state.medals : state.medals.filter((m) => m.tier === tier),
  },

  actions: {
    async fetchMedals() {
      // Avoid hammering the bridge with repeated 404s — one attempt is enough
      // to set `endpointMissing`. Callers can `reset()` to force a retry.
      if (this._attempted) return

      this.isLoading = true
      this.error = null
      this.endpointMissing = false

      try {
        const res = await bridge.get<{ medals?: Medal[] }>('/medals')
        this.medals = Array.isArray(res?.medals) ? res.medals : []
      } catch (e: any) {
        const msg = e?.message ?? String(e)
        // bridge.get throws "Bridge GET /medals failed: Not Found" on 404.
        if (/not found/i.test(msg) || /404/.test(msg)) {
          this.endpointMissing = true
        } else {
          this.error = msg
        }
        this.medals = []
      } finally {
        this._attempted = true
        this.isLoading = false
      }
    },

    /** Reset attempt flag so the next `fetchMedals()` retries the bridge. */
    reset() {
      this.medals = []
      this.error = null
      this.endpointMissing = false
      this._attempted = false
    },
  },
})
