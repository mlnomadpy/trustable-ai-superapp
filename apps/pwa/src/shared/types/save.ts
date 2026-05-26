export type CoachId = 'trod' | 'bentley' | 'drill' | 'calm' | 'buddy'
export type TrackId = 'sonoma' | 'laguna' | 'thunderhill' | 'buttonwillow'

export interface SaveSlot {
  schemaVersion: 1
  id: 1 | 2 | 3
  createdAt: string
  lastPlayedAt: string

  driverName: string
  driverAvatar?: string
  skillLevel: 'beginner' | 'intermediate' | 'pro'
  /**
   * Per-slot car selection. Null until the driver picks one in the
   * Pit Stall — onboarding intentionally does NOT preset a model so
   * the UI never claims the user owns a car they haven't selected.
   * Pages that read `car` must handle the null case explicitly.
   */
  car: string | null
  avatarSlot: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8

  preferredCoach: CoachId
  preferredTrack: TrackId

  level: number
  sessions: SessionSummary[]
  bestLapBySession: Record<string, number>

  coachAffinity: Record<CoachId, number>

  unlockedTracks: TrackId[]
  unlockedAvatars: number[]
  unlockedCoaches: CoachId[]

  medals: { id: string; awardedAt: string; sessionId?: string }[]
  goalsHistory: SessionGoal[]

  settings: SaveSettings

  /**
   * Per-slot coach personalisation set on the CoachBios screen. Optional
   * for back-compat with slots created before this field shipped — the UI
   * hydrates with defaults when missing.
   */
  coachPrefs?: CoachPrefs
}

export interface CoachPrefs {
  verbosity: 'min' | 'std' | 'max'
  focus: 'brake' | 'line' | 'accel'
  tone: 'aggro' | 'supp' | 'clin'
  autoMute: boolean
}

export interface SessionSummary {
  sessionId: string
  startedAt: string
  trackId: string
  bestLapS: number | null
  lapCount: number
  coachId: CoachId
  goalsHit: number
  goalsTotal: number
  totalScore: number
  pbAchieved: boolean
}

export interface SessionGoal {
  id: string
  kind: 'corner_focus' | 'lap_time' | 'technique'
  description: string
  targetValue: number
  achievedAt?: string
  result?: 'hit' | 'partial' | 'miss'
}

export interface SaveSettings {
  audio: {
    masterVolume: number
    musicVolume: number
    sfxVolume: number
    voiceVolume: number
    coachMute: boolean
  }
  display: {
    nightMode: boolean
    reducedMotion: boolean
    showFps: boolean
  }
  controls: {
    keyboardLayout: 'wasd' | 'arrows' | 'igdk'
    swapAB: boolean
  }
  ux: {
    typewriterSpeed: 'off' | 'fast' | 'normal' | 'slow'
    hapticFeedback: boolean
  }
}

