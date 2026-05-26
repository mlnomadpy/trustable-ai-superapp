import { defineStore } from 'pinia'
import { API_BASE } from '@/shared/config/api'


export interface TelemetryFrame {
  timestamp: number
  distance: number
  speed: number
  g_lat: number
  g_long: number
  combo_g: number
  brake_pressure: number
  throttle: number
  steering: number
  rpm: number
  lat: number
  lon: number
  // ── Optional fields actually present on the bridge SSE payload ──────────
  // The bridge forwards the full AiM/CAN-decoded frame (100+ fields).
  // These are the ones the UI consumes today or is about to. All optional
  // because not every car/track logs every channel.
  lap_number?: number
  gps_lat?: number
  gps_lon?: number
  ecu_speed_mph?: number
  throttle_pct?: number
  brake_bar?: number
  water_temp_f?: number
  oil_press_psi?: number
  oil_temp_f?: number
  fuel_level_gal?: number
  fuel_pressure_psi?: number
  battery_volt?: number
  gear?: number
  gear_position?: number
  tpms_press_avg_psi?: number
  tpms_temp_avg_f?: number
}

// NO FAKE SIMULATION. The previous `startSimulation()` fabricated frames
// from sine/cosine with hardcoded Sonoma GPS — removed. If there's no
// active session, the UI must render an honest "NO SESSION ACTIVE" state.

export const useTelemetryStore = defineStore('telemetry', {
  state: () => ({
    frame: null as TelemetryFrame | null,
    /**
     * Wall-clock epoch (ms) of the *first* frame received since the most
     * recent `open()` call. UIs use this as a "data has arrived" signal —
     * the HUD watches it to dismiss the WAITING-FOR-DATA overlay the
     * moment the SSE delivers its first telemetry tick.
     */
    firstFrameAt: null as number | null,
    _es: null as EventSource | null,
    _retryCount: 0,
    _retryTimeout: null as number | null,
    _maxRetries: 10,
    _retryMs: 3000,
  }),
  actions: {
    open(sid: string) {
      this.close()
      this.firstFrameAt = null
      if (!sid) {
        // Honest no-op — callers must pass a real session id. No magic
        // 'SIM' activator, no fabricated frames.
        return
      }
      this._connect(sid)
    },

    _connect(sid: string) {
      this._es = new EventSource(`${API_BASE}/telemetry/stream?session_id=${sid}`)

      this._es.addEventListener('telemetry', (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data && data.timestamp) {
            this.frame = data as TelemetryFrame
            if (this.firstFrameAt == null) this.firstFrameAt = Date.now()
            this._retryCount = 0 // reset only on valid payload
          }
        } catch (err) {
          console.error('Failed to parse telemetry', err)
        }
      })

      this._es.onerror = () => {
        this.frame = null
        this._es?.close()
        this._es = null

        if (this._retryCount < this._maxRetries) {
          this._retryCount++
          console.warn(`[Telemetry] Reconnecting (${this._retryCount}/${this._maxRetries})…`)
          this._retryTimeout = window.setTimeout(() => this._connect(sid), this._retryMs)
        } else {
          console.error(`[Telemetry] Gave up after ${this._maxRetries} retries`)
        }
      }
    },

    close() {
      if (this._retryTimeout) clearTimeout(this._retryTimeout)
      this._retryTimeout = null
      this._es?.close()
      this._es = null
      this.frame = null
      this.firstFrameAt = null
      this._retryCount = 0
    }
  }
})
