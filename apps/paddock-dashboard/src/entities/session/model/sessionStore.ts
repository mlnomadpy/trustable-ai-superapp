import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

// ── Types matching backend response shapes ──────────────────────────────────

export interface SessionSummary {
  session_id: string
  driver: string
  driver_level: string
  track: string
  car: string
  started_at: string | null
  ended_at: string | null
  note: string
  lap_count: number
  best_lap_s: number | null
}

export interface LapDetail {
  lap_number: number
  lap_time_s: number | null
  best_sector: number | null
  avg_speed_kmh: number | null
  max_combo_g: number | null
  coast_pct: number | null
  recorded_at: string | null
}

export interface CoachingNote {
  burst_id: string
  distance_m: number
  text: string
  source: string
  recorded_at: string | null
}

export interface SessionDetail {
  session: SessionSummary
  laps: LapDetail[]
  notes: CoachingNote[]
  lap_count: number
  best_lap_s: number | null
}

// ── Store ────────────────────────────────────────────────────────────────────

export const useSessionStore = defineStore('session', {
  state: () => ({
    // Active session
    activeSessionId: null as string | null,
    
    // Session list (from GET /sessions)
    sessions: [] as SessionSummary[],
    sessionsLoading: false,
    sessionsError: null as string | null,
    
    // Session detail (from GET /session/:sid)
    detail: null as SessionDetail | null,
    detailLoading: false,
    detailError: null as string | null,
    
    // Derived from detail
    lapCount: 0,
    goalsHit: 0,
    goalsTotal: 0,
  }),

  getters: {
    activeSession: (state) => state.sessions.find(s => s.session_id === state.activeSessionId) ?? null,
    hasActiveSessions: (state) => state.sessions.some(s => !s.ended_at),
    bestLapFormatted: (state) => {
      if (!state.detail?.best_lap_s) return '--:--.---'
      const t = state.detail.best_lap_s
      const mins = Math.floor(t / 60)
      const secs = (t % 60).toFixed(3)
      return `${mins}:${secs.padStart(6, '0')}`
    },
  },

  actions: {
    /** Fetch all sessions from the backend. */
    async fetchSessions(limit = 50) {
      this.sessionsLoading = true
      this.sessionsError = null
      try {
        const res = await bridge.get<{ sessions: SessionSummary[]; count: number }>(`/sessions?limit=${limit}`)
        this.sessions = res.sessions
      } catch (e: any) {
        this.sessionsError = e.message ?? String(e)
        console.warn('[sessionStore] fetchSessions failed:', e)
      } finally {
        this.sessionsLoading = false
      }
    },

    /** Fetch full detail for one session. */
    async fetchDetail(sid: string) {
      this.detailLoading = true
      this.detailError = null
      try {
        const res = await bridge.get<SessionDetail>(`/session/${sid}`)
        this.detail = res
        this.lapCount = res.lap_count
      } catch (e: any) {
        this.detailError = e.message ?? String(e)
        console.warn('[sessionStore] fetchDetail failed:', e)
      } finally {
        this.detailLoading = false
      }
    },

    /** Start a new live session on the backend. */
    async startSession(opts?: { driver?: string; track?: string; car?: string }) {
      try {
        const res = await bridge.post<{ started: boolean; session_id: string }>('/session/start', opts ?? {})
        this.activeSessionId = res.session_id
        this.lapCount = 0
        this.goalsHit = 0
        this.goalsTotal = 0
        // Refresh session list
        await this.fetchSessions()
        return res.session_id
      } catch (e: any) {
        console.error('[sessionStore] startSession failed:', e)
        return null
      }
    },

    /** End the active session. */
    async endSession() {
      if (!this.activeSessionId) return
      try {
        await bridge.post(`/session/${this.activeSessionId}/end`, {})
      } catch (e: any) {
        console.warn('[sessionStore] endSession failed:', e)
      }
      this.activeSessionId = null
      this.detail = null
      // Refresh list to show ended_at
      await this.fetchSessions()
    },

    /** Set active session without starting a new one (e.g., selecting from list). */
    selectSession(sid: string) {
      this.activeSessionId = sid
      this.fetchDetail(sid)
    },
  }
})
