import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

// ── Types ────────────────────────────────────────────────────────────────────

export interface Quest {
  id: string
  title: string
  desc: string
  progress: number
  target: number
  xp: number
  completed: boolean
}

export interface Insight {
  id: string
  rank: number
  title: string
  detail: string
  corners: string[]
  metric_label: string
  metric_value: string
  effort: number
  est_gain_s: number
  evidence_bursts: number
}

interface InsightsResponse {
  insights: Insight[]
  session_bursts: number
  generated_at: string
}

// ── Store ────────────────────────────────────────────────────────────────────
//
// NO FAKE FALLBACKS. If `/insights` returns no items, `daily` stays empty and
// the UI must render an honest "NO ACTIVE QUESTS" state. If the bridge call
// fails, `error` is set and the UI must render an honest error state.
//
// Weekly quests have no backing endpoint on the bridge (no `/insights` weekly
// projection) — `weekly` is intentionally always `[]`. Do NOT add hardcoded
// weekly quests; surface the empty state honestly instead.

export const useQuestStore = defineStore('quest', {
  state: () => ({
    daily: [] as Quest[],
    // No /insights weekly endpoint exists — leave empty until backend ships one.
    weekly: [] as Quest[],
    insights: [] as Insight[],
    isLoading: false,
    error: null as string | null,
  }),

  actions: {
    /**
     * Fetch quests: maps `/insights` items to Quest-shaped daily goals.
     * On error, sets `error` and leaves `daily` as `[]` — no synthesis.
     */
    async fetchQuests() {
      this.isLoading = true
      this.error = null

      try {
        const res = await bridge.get<InsightsResponse>('/insights')
        const items = Array.isArray(res?.insights) ? res.insights : []

        this.daily = items.map((insight) => ({
          id: insight.id,
          title: insight.title.toUpperCase(),
          desc: insight.detail,
          progress: 0,
          target: 1,
          xp: Math.round(insight.est_gain_s * 100),
          completed: false,
        }))

        this.insights = items
        // `weekly` intentionally untouched — backend does not project weekly
        // quests from /insights. If/when it does, map them here.
      } catch (e: any) {
        // Honest failure — surface the error, do NOT synthesize quests.
        this.error = e?.message ?? String(e)
        this.daily = []
        this.insights = []
        console.warn('[questStore] fetchQuests failed:', this.error)
      } finally {
        this.isLoading = false
      }
    },
  }
})
