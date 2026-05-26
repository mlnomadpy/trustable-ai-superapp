/**
 * agentTraceStore — Pinia store for the ADK agent-trace HUD panel.
 *
 * Talks to:
 *   GET /coach/agents              → list of registered coaching agents
 *   GET /coach/traces?since_ts=... → recent agent_traces rows
 *
 * Hard contract: NO MOCKS, NO FAKE TRACES. If the bridge says
 * `available:false` we surface that honestly; the HUD renders an
 * "UNAVAILABLE" badge instead of inventing data.
 */
import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

export interface AgentTrace {
  trace_id: string
  pitwall_sid: string
  agent_name: string
  event_type: string  // 'agent' | 'tool' | 'route' | …
  detail: string
  latency_ms: number | null
  success: boolean
  ts: string          // ISO datetime from the bridge
}

export interface AgentDescriptor {
  name: string
  role?: string
  [k: string]: unknown
}

interface TracesResponse {
  available: boolean
  reason?: string
  traces: AgentTrace[]
  count: number
}

interface AgentsResponse {
  available: boolean
  reason?: string
  agents: AgentDescriptor[]
}

export const useAgentTraceStore = defineStore('agentTrace', {
  state: () => ({
    traces: [] as AgentTrace[],
    agents: [] as AgentDescriptor[],
    lastTs: null as string | null,
    loading: false,
    error: null as string | null,
    available: true,
    reason: null as string | null,
    agentsLoaded: false,
  }),

  getters: {
    /** Total events held client-side (post-merge). */
    eventCount: (state) => state.traces.length,
    /** Quick lookup of agents-that-actually-fired. */
    firedAgentNames: (state) => Array.from(new Set(state.traces.map(t => t.agent_name))),
  },

  actions: {
    /** Load the registry of agents the bridge knows about. Safe to call repeatedly. */
    async fetchAgents() {
      try {
        const res = await bridge.get<AgentsResponse>('/coach/agents')
        this.agents = Array.isArray(res.agents) ? res.agents : []
        this.agentsLoaded = true
        if (res.available === false) {
          this.available = false
          this.reason = res.reason ?? 'ADK not available'
        }
      } catch (e) {
        const msg = (e as Error)?.message ?? String(e)
        this.error = msg
        // Don't flip `available` — /coach/agents may have transiently
        // failed while /coach/traces is fine.
      }
    },

    /**
     * Incremental poll. Pass `sessionId` to filter; pass `since_ts` to
     * receive only newer-than rows (defaults to `lastTs`).
     */
    async pollTraces(opts: { sessionId?: string; since_ts?: string; limit?: number } = {}) {
      const params = new URLSearchParams()
      const sid = opts.sessionId?.trim()
      if (sid) params.set('session_id', sid)
      const since = opts.since_ts ?? this.lastTs
      if (since) params.set('since_ts', since)
      params.set('limit', String(opts.limit ?? 200))

      this.loading = true
      try {
        const res = await bridge.get<TracesResponse>(`/coach/traces?${params.toString()}`)
        this.available = res.available !== false
        this.reason = res.reason ?? null
        if (!this.available) {
          // Honest empty state — do not synthesize.
          this.error = null
          return
        }

        const incoming = Array.isArray(res.traces) ? res.traces : []
        if (incoming.length > 0) {
          // Server returns newest-first. Merge them on top, dedupe by
          // (trace_id, agent_name, ts).
          const seen = new Set(this.traces.map(t => `${t.trace_id}|${t.agent_name}|${t.ts}`))
          const fresh = incoming.filter(t => !seen.has(`${t.trace_id}|${t.agent_name}|${t.ts}`))
          this.traces = [...fresh, ...this.traces].slice(0, 500)
          // Track the newest ts we've ever seen so the next poll is incremental.
          const newest = incoming[0]?.ts
          if (newest && (!this.lastTs || newest > this.lastTs)) {
            this.lastTs = newest
          }
        }
        this.error = null
      } catch (e) {
        this.error = (e as Error)?.message ?? String(e)
      } finally {
        this.loading = false
      }
    },

    /** Drop all client-side state (e.g., on session change). */
    clear() {
      this.traces = []
      this.lastTs = null
      this.error = null
      this.available = true
      this.reason = null
    },
  },
})
