import { defineStore } from 'pinia'
import { bridge } from '@/shared/api/bridge'

export interface HealthResponse {
  status: string
  version: string
  can_bridge?: boolean              // legacy field, retained for compat
  active_session_id: string | null
  engine?: string
  coach?: string | null
  driver_level?: string | null
  duckdb?: boolean
  // Phase 1.5 / PWA integration: enriched health fields (additive)
  simulator?: {
    running: boolean
    lap_seconds?: number
    speed_x?: number
  }
  can?: {
    connected: boolean
    fps?: number
    frames_total?: number
    frames_unknown?: number
    channel?: string
    bitrate?: number
    last_frame_age_s?: number | null
  }
  litert?: {
    up: boolean
    transport?: string
    http_url?: string
    http_model?: string
  }
}


export const useBridgeStore = defineStore('bridge', {
  state: () => ({
    health: null as HealthResponse | null,
    healthFetchedAt: 0,
    healthError: null as string | null,
    consecutiveFailures: 0,
    isPolling: false,
    _pollIntervalId: null as number | null,
    mockOffline: false // for dev testing
  }),
  actions: {
    async pollHealth() {
      if (this.mockOffline) {
        this.healthError = 'MOCK_OFFLINE'
        this.consecutiveFailures++
        return
      }
      
      try {
        this.health = await bridge.get<HealthResponse>('/health')
        this.healthFetchedAt = Date.now()
        this.healthError = null
        this.consecutiveFailures = 0
      } catch (e) {
        this.healthError = String(e)
        this.consecutiveFailures++
      }
    },
    
    startPolling() {
      if (this.isPolling) return
      this.isPolling = true
      
      // Initial poll
      this.pollHealth()
      
      // Set interval — store ID so it can be stopped
      this._pollIntervalId = window.setInterval(() => {
        this.pollHealth()
      }, 5000)
    },
    
    stopPolling() {
      if (this._pollIntervalId !== null) {
        clearInterval(this._pollIntervalId)
        this._pollIntervalId = null
      }
      this.isPolling = false
    },
    
    toggleMockOffline() {
      this.mockOffline = !this.mockOffline
      if (this.mockOffline) {
        // Immediately bump failures to test banner appearance faster
        this.consecutiveFailures = 3
        this.healthError = 'MOCK_OFFLINE'
      } else {
        // Immediately recover
        this.consecutiveFailures = 0
        this.healthError = null
      }
    }
  }
})
