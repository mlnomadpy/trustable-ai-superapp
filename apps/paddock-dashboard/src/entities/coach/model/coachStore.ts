import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'
import { API_BASE } from '@/shared/config/api'
import type { CoachId } from '@/shared/types/save'
import { useLoadingStore } from '@/shared/api/loadingStore'

// ── Types matching backend responses ─────────────────────────────────────────

export interface BriefResponse {
  driver_id: string
  date: string
  weather_phase: string
  surface_state: string
  weather_note: string
  weakest_recent_corner: string | null
  biggest_recent_improvement: string | null
  danger_zones_today: string[]
  narrative_md: string
  focus: string[]
  emotion: string
}

export interface DebriefResponse {
  session_id: string
  scorecard?: Record<string, any>
  highlights?: any[]
  narrative?: string
  narrative_md?: string
  narrative_source?: string
  emotion?: string
  focus?: string[]
  next_focus?: string[]
  [key: string]: any
}

export interface AskResponse {
  answer: string
  emotion: string
  qa_key: string
  turn: number
}

export interface ConversationTurn {
  role: 'user' | 'assistant' | 'coach_brief' | 'coach_debrief'
  text: string
  emotion?: string
  recorded_at?: string | null
}

/** Shape of an item in /coach/agents (the AGENT_REGISTRY). */
export interface AgentRegistryEntry {
  name: string
  role: string
  example_questions?: string[]
}

/** Pinia-friendly representation of /conversations/driver/{id}. */
export interface ConversationRow {
  session_id: string
  driver_id: string
  role: 'user' | 'assistant' | 'coach_brief' | 'coach_debrief'
  text: string
  focus_items?: string | null
  emotion?: string | null
  recorded_at: string | null
}

function normalizeFocusItems(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 3)
}

function normalizeDebriefResponse(payload: DebriefResponse): DebriefResponse {
  const narrative =
    typeof payload.narrative === 'string' && payload.narrative.trim()
      ? payload.narrative
      : typeof payload.narrative_md === 'string' && payload.narrative_md.trim()
        ? payload.narrative_md
        : payload.narrative

  const focus = normalizeFocusItems(payload.focus)
  const nextFocus = focus.length > 0 ? focus : normalizeFocusItems(payload.next_focus)

  return {
    ...payload,
    narrative,
    focus: nextFocus,
  }
}

// ── Store ────────────────────────────────────────────────────────────────────

export const useCoachStore = defineStore('coach', {
  state: () => ({
    activeCoach: 'trod' as CoachId,
    concepts: [] as string[],

    // Brief
    brief: null as BriefResponse | null,
    briefLoading: false,
    briefError: null as string | null,

    // Debrief
    debrief: null as DebriefResponse | null,
    debriefLoading: false,
    debriefError: null as string | null,

    // Q&A conversation
    conversation: [] as ConversationTurn[],
    isAsking: false,
    askError: null as string | null,

    // Streaming Q&A
    streamingText: '',
    isStreaming: false,

    // /coach/agents — AGENT_REGISTRY mirror for the intent-picker UI.
    agents: [] as AgentRegistryEntry[],
    agentsLoading: false,
    agentsError: null as string | null,

    // /conversations/driver/{id} — persisted Q&A + brief/debrief history.
    historyTurns: [] as ConversationRow[],
    historyLoading: false,
    historyError: null as string | null,
  }),

  getters: {
    /** Latest coach emotion from any interaction */
    currentEmotion: (state) => {
      if (state.brief?.emotion) return state.brief.emotion
      if (state.debrief?.emotion) return state.debrief.emotion
      const lastCoach = [...state.conversation].reverse().find(t => t.role === 'assistant')
      return lastCoach?.emotion ?? 'neutral'
    },
  },

  actions: {
    setCoach(coachId: CoachId) {
      this.activeCoach = coachId
    },

    // ── Pre-Session Brief ──────────────────────────────────────────────

    async fetchBrief(opts?: {
      driver?: string
      focus?: string[]
      goal?: string
      sessionId?: string
    }) {
      const loading = useLoadingStore()
      this.briefLoading = true
      loading.start('Generating Brief...', 'adk')
      this.briefError = null
      try {
        const params = new URLSearchParams()
        if (opts?.driver) params.set('driver', opts.driver)
        if (opts?.focus?.length) params.set('focus', opts.focus.join(','))
        if (opts?.goal) params.set('goal', opts.goal)
        if (opts?.sessionId) params.set('session_id', opts.sessionId)
        const qs = params.toString()
        this.brief = await bridge.get<BriefResponse>(`/coach/brief${qs ? '?' + qs : ''}`)
      } catch (e: any) {
        this.briefError = e.message ?? String(e)
        console.warn('[coachStore] fetchBrief failed:', e)
      } finally {
        this.briefLoading = false
        loading.stop()
      }
    },

    // ── Post-Session Debrief ───────────────────────────────────────────

    async fetchDebrief(opts: {
      sessionId: string
      driverId?: string
      vboPath?: string
    }) {
      const loading = useLoadingStore()
      this.debriefLoading = true
      loading.start('Analyzing Session...', 'adk')
      this.debriefError = null
      try {
        const response = await bridge.post<DebriefResponse>('/coach/debrief', {
          session_id: opts.sessionId,
          driver_id: opts.driverId ?? '',
          vbo_path: opts.vboPath,
        })
        this.debrief = normalizeDebriefResponse(response)
      } catch (e: any) {
        this.debriefError = e.message ?? String(e)
        console.warn('[coachStore] fetchDebrief failed:', e)
      } finally {
        this.debriefLoading = false
        loading.stop()
      }
    },

    // ── Interactive Q&A ────────────────────────────────────────────────

    async ask(question: string, opts?: {
      driverId?: string
      sessionId?: string
      intent?: string
    }) {
      const loading = useLoadingStore()
      this.isAsking = true
      loading.start('Paddock Thinking...', 'adk')
      this.askError = null
      this.conversation.push({ role: 'user', text: question })

      try {
        const res = await bridge.post<AskResponse & { error?: string }>('/coach/ask', {
          question,
          driver_id: opts?.driverId ?? '',
          session_id: opts?.sessionId ?? '',
          intent: opts?.intent,
        })
        
        if (res.error || !res.answer) {
          this.conversation.push({
            role: 'assistant',
            text: res.error ?? 'Coach is not available right now. Keep driving!',
            emotion: 'neutral',
          })
          this.askError = res.error ?? 'No answer'
          return null
        }
        
        this.conversation.push({
          role: 'assistant',
          text: res.answer,
          emotion: res.emotion,
        })
        return res
      } catch (e: any) {
        this.askError = e.message ?? String(e)
        console.warn('[coachStore] ask failed:', e)
        return null
      } finally {
        this.isAsking = false
        loading.stop()
      }
    },

    /** Streaming Q&A via SSE (typewriter effect) */
    async askStream(question: string, opts?: {
      driverId?: string
      sessionId?: string
      intent?: string
    }) {
      this.isStreaming = true
      this.streamingText = ''
      this.askError = null
      this.conversation.push({ role: 'user', text: question })

      try {
        const res = await fetch(`${API_BASE}/coach/ask/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question,
            driver_id: opts?.driverId ?? '',
            session_id: opts?.sessionId ?? '',
            intent: opts?.intent,
          }),
        })

        if (!res.ok) throw new Error(`Stream failed: ${res.statusText}`)
        const reader = res.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))
              if (data.delta) {
                this.streamingText += data.delta
              }
              if (data.done) {
                this.conversation.push({
                  role: 'assistant',
                  text: data.answer,
                  emotion: data.emotion ?? 'neutral',
                })
              }
            } catch { /* skip malformed lines */ }
          }
        }
      } catch (e: any) {
        this.askError = e.message ?? String(e)
      } finally {
        this.isStreaming = false
      }
    },

    /** Flush Q&A history to backend for persistence */
    async endConversation(driverId: string, sessionId: string) {
      try {
        await bridge.post('/coach/ask/end', {
          driver_id: driverId,
          session_id: sessionId,
        })
      } catch { /* non-critical */ }
      this.conversation = []
    },

    // ── Agent registry (for routing override + question discovery) ───────

    /**
     * Fetch the list of ADK agents the orchestrator can route to. Used by
     * the Q&A UI to surface (a) "what can I ask?" example questions and
     * (b) an intent-override picker for when the regex classifier would
     * misroute. Cached after first call — call again to refresh.
     */
    async fetchAgents() {
      if (this.agents.length > 0) return this.agents
      this.agentsLoading = true
      this.agentsError = null
      try {
        const res = await bridge.get<{ agents: AgentRegistryEntry[] }>('/coach/agents')
        this.agents = Array.isArray(res?.agents) ? res.agents : []
      } catch (e: any) {
        this.agentsError = e?.message ?? String(e)
        this.agents = []
      } finally {
        this.agentsLoading = false
      }
      return this.agents
    },

    // ── Conversation history (multi-session view of past coach turns) ────

    /**
     * Load the persisted brief / debrief / Q&A history for a driver from
     * `/conversations/driver/{driver_id}`. Backend orders by `recorded_at`.
     */
    async fetchHistory(driverId: string, opts?: { limit?: number }) {
      if (!driverId) return []
      this.historyLoading = true
      this.historyError = null
      try {
        const qs = opts?.limit ? `?limit=${opts.limit}` : ''
        const res = await bridge.get<{ history: ConversationRow[] }>(
          `/conversations/driver/${encodeURIComponent(driverId)}${qs}`,
        )
        this.historyTurns = Array.isArray(res?.history) ? res.history : []
      } catch (e: any) {
        this.historyError = e?.message ?? String(e)
        this.historyTurns = []
      } finally {
        this.historyLoading = false
      }
      return this.historyTurns
    },

    /** Clear all coaching state */
    reset() {
      this.brief = null
      this.debrief = null
      this.conversation = []
      this.streamingText = ''
      this.briefError = null
      this.debriefError = null
      this.askError = null
      this.historyTurns = []
      this.historyError = null
    },
  }
})
