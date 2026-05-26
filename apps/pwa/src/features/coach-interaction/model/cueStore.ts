import { defineStore } from 'pinia'
import { API_BASE } from '@/shared/config/api'

export interface Cue {
  id: string
  text: string
  emotion: string
  timestamp: number
}

function normalizeCue(payload: unknown): Cue | null {
  if (!payload || typeof payload !== 'object') return null

  const raw = payload as Record<string, unknown>
  const text = typeof raw.text === 'string' ? raw.text : ''
  if (!text.trim()) return null

  const idSource = raw.id ?? raw.phrase_id ?? raw.burst_id ?? raw.ts
  const timestamp =
    typeof raw.timestamp === 'number'
      ? raw.timestamp
      : typeof raw.ts === 'number'
        ? raw.ts
        : Date.now()

  return {
    id: idSource == null ? String(timestamp) : String(idSource),
    text,
    emotion: typeof raw.emotion === 'string' && raw.emotion.trim()
      ? raw.emotion
      : 'neutral',
    timestamp,
  }
}

export const useCueStore = defineStore('cue', {
  state: () => ({
    activeCue: null as Cue | null,
    queue: [] as Cue[],
    _es: null as EventSource | null,
    _retryCount: 0,
    _retryTimeout: null as number | null,
    _maxRetries: 10,
    _retryMs: 3000,
  }),
  actions: {
    open(sid: string) {
      this.close()
      this._connect(sid)
    },
    
    consumeNext() {
      if (this.queue.length > 0) {
        this.activeCue = this.queue.shift() || null
      } else {
        this.activeCue = null
      }
    },
    
    clearQueue() {
      this.queue = []
      this.activeCue = null
    },
    
    _connect(sid: string) {
      this._es = new EventSource(`${API_BASE}/cues/stream?session_id=${sid}`)

      const handleCue = (e: MessageEvent) => {
        try {
          const cue = normalizeCue(JSON.parse(e.data))
          if (!cue) return
          this.queue.push(cue)
          this._retryCount = 0 // reset on successful message
        } catch (err) {
          console.error('Failed to parse cue', err)
        }
      }

      // The bridge emits named `cue` SSE events. Keep `onmessage` as a
      // compatibility fallback for older unnamed-message streams.
      this._es.addEventListener('cue', handleCue as EventListener)
      this._es.onmessage = handleCue
      
      this._es.onerror = () => {
        this.activeCue = null
        this._es?.close()
        this._es = null
        
        if (this._retryCount < this._maxRetries) {
          this._retryCount++
          console.warn(`[Cues] Reconnecting (${this._retryCount}/${this._maxRetries})…`)
          this._retryTimeout = window.setTimeout(() => this._connect(sid), this._retryMs)
        } else {
          console.error(`[Cues] Gave up after ${this._maxRetries} retries`)
        }
      }
    },
    
    close() {
      if (this._retryTimeout) clearTimeout(this._retryTimeout)
      this._retryTimeout = null
      this._es?.close()
      this._es = null
      this._retryCount = 0
      this.clearQueue()
    }
  }
})
