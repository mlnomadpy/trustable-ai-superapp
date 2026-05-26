/**
 * Bridge API Client
 * Wraps native fetch calls to the Python HTTP backend.
 * All stores should use this instead of raw fetch().
 */

import { API_BASE } from '@/shared/config/api'
import type * as Types from '@/shared/types/bridge'

export interface ApiError {
  message: string
}

// ── /cars — real per-car YAML inventory ─────────────────────────────────────
export interface CarChannel {
  name: string
  frame_id: string
  rate_hz: number | null
  role: string
}
export interface CarConfig {
  id: string
  path: string
  loaded: boolean
  error?: string
  make?: string
  model?: string
  chassis?: string
  year?: number | null
  engine?: string
  notes?: string
  dash_logger?: {
    make: string
    model: string
    protocol: string
    total_frames: number | null
    total_channels: number | null
  }
  can_bus?: {
    name: string
    bitrate_bps: number | null
    frame_format: string
    id_width: number | null
  }
  frame_count?: number
  channel_count?: number
  channels?: CarChannel[]
}
export interface CarsResponse {
  cars: CarConfig[]
  loaded_id: string
  loaded_path?: string
  cars_dir: string
  error?: string
}

export const bridge = {
  async getHealth(): Promise<Types.HealthResponse> {
    return this.get<Types.HealthResponse>('/health')
  },

  async getCars(): Promise<CarsResponse> {
    return this.get<CarsResponse>('/cars')
  },

  async analyze(data: Types.AnalyzeRequest): Promise<Types.AnalyzeResponse> {
    return this.post<Types.AnalyzeResponse>('/analyze', data)
  },

  async getSessions(limit = 50, activeOnly = false): Promise<{ sessions: Types.SessionSummary[]; count: number }> {
    return this.get<{ sessions: Types.SessionSummary[]; count: number }>(`/sessions?limit=${limit}&active_only=${activeOnly}`)
  },

  async getSession(sid: string): Promise<Types.SessionDetailResponse> {
    return this.get<Types.SessionDetailResponse>(`/session/${sid}`)
  },

  async startSession(data: Types.StartSessionRequest): Promise<Types.StartSessionResponse> {
    return this.post<Types.StartSessionResponse>('/session/start', data)
  },

  async endSession(sid: string): Promise<Types.EndSessionResponse> {
    return this.post<Types.EndSessionResponse>(`/session/${sid}/end`, {})
  },

  async get<T = unknown>(endpoint: string): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`)
    if (!res.ok) throw new Error(`Bridge GET ${endpoint} failed: ${res.statusText}`)
    return res.json() as Promise<T>
  },
  
  async getBuffer(endpoint: string): Promise<Uint8Array> {
    const res = await fetch(`${API_BASE}${endpoint}`)
    if (!res.ok) throw new Error(`Bridge GET ${endpoint} failed: ${res.statusText}`)
    return new Uint8Array(await res.arrayBuffer())
  },
  
  async getRaw(endpoint: string): Promise<Response> {
    const res = await fetch(`${API_BASE}${endpoint}`)
    if (!res.ok) throw new Error(`Bridge GET ${endpoint} failed: ${res.statusText}`)
    return res
  },
  
  async post<T = unknown>(endpoint: string, body: unknown): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!res.ok) throw new Error(`Bridge POST ${endpoint} failed: ${res.statusText}`)
    return res.json() as Promise<T>
  }
}

