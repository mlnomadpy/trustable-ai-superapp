import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'
import { useSessionStore } from '@/entities/session/model/sessionStore'

// ── Types matching GET /session/:sid/lap_time_table response ─────────────────

export interface SectorTime {
  name: string
  time_s: number
  is_best: boolean
}

export interface LapTime {
  lap_number: number
  lap_time_s: number
  delta_to_best_s: number
  is_best: boolean
  sectors: SectorTime[]
}

interface LapTimeTableResponse {
  session_id: string
  lap_count: number
  best_lap_s: number
  best_lap_number: number
  laps: LapTime[]
}

/** Shape of /session/<sid>/ideal_lap (bp_analysis.session_ideal_lap). */
export interface IdealLapResponse {
  session_id: string
  ideal_lap_s: number
  best_actual_lap_s: number
  gain_potential_s: number
  best_sectors: { name: string; time_s: number; from_lap: number }[]
}

/** Shape of /session/<sid>/lap_time_distribution (bp_analysis). */
export interface LapTimeDistributionResponse {
  session_id: string
  min_s: number
  q1_s: number
  median_s: number
  q3_s: number
  max_s: number
  outliers: { lap_number: number; lap_time_s: number }[]
  mean_s: number
  stddev_s: number
}

// ── Store ────────────────────────────────────────────────────────────────────

export const useLapTimeStore = defineStore('lapTime', {
  state: () => ({
    laps: [] as LapTime[],
    bestLapS: null as number | null,
    bestLapNumber: null as number | null,
    isLoading: false,
    error: null as string | null,

    // Server-computed ideal lap (sum of best per-sector times) and the
    // distribution box-plot stats. Both are optional — pages should fall
    // back to client-side approximations when these are null.
    ideal: null as IdealLapResponse | null,
    idealLoading: false,
    idealError: null as string | null,

    distribution: null as LapTimeDistributionResponse | null,
    distributionLoading: false,
    distributionError: null as string | null,
  }),

  getters: {
    /** Best lap formatted as M:SS.mmm */
    bestFormatted: (state) => {
      if (!state.bestLapS) return '--:--.---'
      const mins = Math.floor(state.bestLapS / 60)
      const secs = (state.bestLapS % 60).toFixed(3)
      return `${mins}:${secs.padStart(6, '0')}`
    },
    /** Laps sorted fastest-first */
    sortedByTime: (state) => [...state.laps].sort((a, b) => a.lap_time_s - b.lap_time_s),
    /** Lap count */
    count: (state) => state.laps.length,
  },

  actions: {
    /**
     * Fetch lap times from the backend.
     * Uses the active session from sessionStore if no sid provided.
     */
    async fetchLapTimes(sid?: string) {
      const sessionStore = useSessionStore()
      const sessionId = sid ?? sessionStore.activeSessionId
      if (!sessionId) {
        this.error = 'No active session'
        return
      }

      this.isLoading = true
      this.error = null

      try {
        const res = await bridge.get<LapTimeTableResponse>(`/session/${sessionId}/lap_time_table`)
        this.laps = res.laps
        this.bestLapS = res.best_lap_s
        this.bestLapNumber = res.best_lap_number
      } catch (e: any) {
        this.error = e.message ?? String(e)
        console.warn('[lapTimeStore] fetchLapTimes failed:', e)
        // Keep existing data on error (graceful degradation)
      } finally {
        this.isLoading = false
      }
    },

    /**
     * Theoretical fastest lap from server-computed best-per-sector data.
     * Returns null on 4xx (e.g. no sector data for the session). Pages
     * should fall back to client-side min(sector) computation in that case.
     */
    async fetchIdealLap(sid?: string) {
      const sessionStore = useSessionStore()
      const sessionId = sid ?? sessionStore.activeSessionId
      if (!sessionId) {
        this.idealError = 'No active session'
        return
      }
      this.idealLoading = true
      this.idealError = null
      try {
        this.ideal = await bridge.get<IdealLapResponse>(
          `/session/${sessionId}/ideal_lap`,
        )
      } catch (e: any) {
        this.idealError = e?.message ?? String(e)
        this.ideal = null
      } finally {
        this.idealLoading = false
      }
    },

    /** Lap-time distribution (box plot inputs + outliers). */
    async fetchDistribution(sid?: string) {
      const sessionStore = useSessionStore()
      const sessionId = sid ?? sessionStore.activeSessionId
      if (!sessionId) {
        this.distributionError = 'No active session'
        return
      }
      this.distributionLoading = true
      this.distributionError = null
      try {
        this.distribution = await bridge.get<LapTimeDistributionResponse>(
          `/session/${sessionId}/lap_time_distribution`,
        )
      } catch (e: any) {
        this.distributionError = e?.message ?? String(e)
        this.distribution = null
      } finally {
        this.distributionLoading = false
      }
    },

    /** Clear lap data (e.g., on session change). */
    clear() {
      this.laps = []
      this.bestLapS = null
      this.bestLapNumber = null
      this.error = null
      this.ideal = null
      this.idealError = null
      this.distribution = null
      this.distributionError = null
    },
  }
})
