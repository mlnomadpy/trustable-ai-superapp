import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'

/**
 * A detected lap (or the full-session pseudo-lap at index 0). Shape
 * mirrors the bridge's `/session/<sid>/laps` JSON contract and the
 * lap entries used by docs/telemetry-viewer.html.
 */
export interface Lap {
  name: string
  t_start: number
  t_end: number
  duration_s: number
  distance_m: number
  /** 'all' | 'gps' | 'distance' | 'stint' (etc.) */
  method: string
}

export interface LapsResponse {
  laps: Lap[]
  track_length_m?: number | null
}

export type TabId = 'overview' | 'telemetry' | 'systems' | 'imu' | 'signals' | 'modules'
export const TAB_ORDER: readonly TabId[] = [
  'overview', 'telemetry', 'systems', 'imu', 'signals', 'modules',
] as const

export interface LapFilterSql {
  /** SQL fragment beginning with " AND " (empty when no lap selected). */
  sql: string
  /** Positional params matching the fragment. */
  params: unknown[]
}

export const useAnalysisStore = defineStore('analysis', {
  state: () => ({
    sessionId: null as string | null,
    laps: [] as Lap[],
    trackLengthM: null as number | null,
    /** 0 = full session pseudo-lap; >0 indexes laps[]. */
    selectedLapIndex: 0,
    filterOutliers: true,
    activeTab: 'overview' as TabId,
    loading: false,
    error: null as string | null,
    /** Per-session error specifically for the laps endpoint. */
    lapsError: null as string | null,
  }),

  getters: {
    selectedLap(state): Lap | null {
      if (state.selectedLapIndex <= 0) return null
      return state.laps[state.selectedLapIndex] ?? null
    },
    /**
     * SQL helper that returns a WHERE-AND fragment plus bound params
     * for the active lap window. Pass the timestamp column name (e.g.
     * `timestamp` for the wide table or `ts.t` for the tall store).
     *
     * Returns `{ sql: '', params: [] }` when no lap is selected so
     * callers can safely concatenate.
     */
    lapFilterSql(state) {
      return (col: string): LapFilterSql => {
        const lap = state.selectedLapIndex > 0 ? state.laps[state.selectedLapIndex] : null
        if (!lap) return { sql: '', params: [] }
        return {
          sql: ` AND ${col} BETWEEN ? AND ?`,
          params: [lap.t_start, lap.t_end],
        }
      }
    },
  },

  actions: {
    async loadSession(sid: string) {
      if (!sid) return
      this.loading = true
      this.error = null
      this.lapsError = null
      try {
        const duck = useDuckDBStore()
        await duck.ensureSessionFull(sid)

        // Laps come from the bridge — they're computed server-side off
        // the same data the parquets export. We deliberately keep the
        // failure mode honest: if the bridge can't serve laps we
        // surface the error and degrade to "Full session" only.
        try {
          const res = await bridge.get<LapsResponse>(`/session/${sid}/laps`)
          const trackLen = res.track_length_m ?? null
          const fullSession: Lap = {
            name: 'Full session',
            t_start: res.laps.length ? Math.min(...res.laps.map(l => l.t_start)) : 0,
            t_end: res.laps.length ? Math.max(...res.laps.map(l => l.t_end)) : 0,
            duration_s: res.laps.reduce((a, l) => a + (l.duration_s ?? 0), 0),
            distance_m: res.laps.reduce((a, l) => a + (l.distance_m ?? 0), 0),
            method: 'all',
          }
          this.laps = [fullSession, ...res.laps]
          this.trackLengthM = trackLen
        } catch (e) {
          this.lapsError = e instanceof Error ? e.message : String(e)
          this.laps = []
          this.trackLengthM = null
        }

        this.sessionId = sid
        this.selectedLapIndex = 0
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.loading = false
      }
    },

    setSelectedLap(idx: number) {
      if (idx < 0 || idx >= this.laps.length) return
      this.selectedLapIndex = idx
    },

    cycleLap(delta: number) {
      if (!this.laps.length) return
      const n = this.laps.length
      this.selectedLapIndex = (this.selectedLapIndex + delta + n) % n
    },

    setFilterOutliers(b: boolean) {
      this.filterOutliers = b
    },

    setActiveTab(t: TabId) {
      this.activeTab = t
    },
  },
})
