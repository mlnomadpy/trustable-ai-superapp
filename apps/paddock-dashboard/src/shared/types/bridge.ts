/**
 * Bridge API Types
 * Based on docs/api.md
 */

export interface HealthResponse {
  status: 'ok' | string
  version: string
  engine: 'sonic_model' | 'rules'
  coach: 'rule' | 'litert' | null
  driver_level: 'beginner' | 'intermediate' | 'advanced' | null
  track: string | null
  duckdb: boolean
  /** Set when a session is active; null when the bridge is idle. */
  active_session_id: string | null
  timestamp: string
}

export interface AnalyzeRequest {
  session_id: string
  burst_id: number
  avg_speed_kmh: number
  max_combo_g: number
  max_lateral_g?: number
  max_long_g: number
  max_brake_bar: number
  avg_throttle_pct: number
  avg_steering_deg: number
  coast_frames: number
  trail_brake_frames: number
  frame_count: number
  corners_visited: string[]
  distance_m: number
  in_corner: boolean
  past_apex: boolean
}

export interface AnalyzeResponse {
  coaching: string
  pace_note: string
  coach_source: 'rule' | 'litert' | ''
  cues: any[]
  burst_id: number
  source: 'sonic_model' | 'bridge_rules'
}

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

export interface SessionDetailResponse {
  session: SessionSummary
  laps: LapDetail[]
  notes: CoachingNote[]
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
  id?: number
  session_id?: string
  burst_id: number
  distance_m: number
  text: string
  source: string
  recorded_at: string | null
}

export interface ImportRequest {
  vbo_path: string
  driver?: string
  driver_level?: string
  session_id?: string
  note?: string
}

export interface ImportResponse {
  session_id: string
  n_frames: number
  duration_s: number
  distance_m: number
  vbo_source: string
}

export interface StartSessionRequest {
  driver?: string
  driver_level?: string
  track?: string
  car?: string
  note?: string
}

export interface StartSessionResponse {
  started: boolean
  session_id: string
}

export interface EndSessionResponse {
  ended: boolean
  session_id: string
}

export interface LapTimeTableResponse {
  session_id: string
  lap_count: number
  best_lap_s: number
  best_lap_number: number
  laps: {
    lap_number: number
    lap_time_s: number
    delta_to_best_s: number
    is_best: boolean
    sectors: {
      name: string
      time_s: number
      is_best: boolean
    }[]
  }[]
}

export interface PedalBehaviorResponse {
  session_id: string
  frame_count: number
  thresholds: {
    throttle_pct: number
    brake_bar: number
  }
  frame_dt_s: number
  states: {
    [key: string]: {
      frames: number
      pct: number
      time_s: number
    }
  }
}
