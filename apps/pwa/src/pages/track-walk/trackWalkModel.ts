import type { SessionSummary } from '@/entities/session/model/sessionStore'

interface CornerIdLike {
  id: string
}

interface TrackTurnLike {
  id: number
  cx: number
  cy: number
}

interface CornerPinLike {
  id: string
  x: number
  y: number
  turnId: number | null
}

const TRACK_WALK_TURN_IDS: Record<string, { primary: number; aliases: number[] }> = {
  T1: { primary: 5, aliases: [5] },
  T2: { primary: 0, aliases: [0] },
  T3: { primary: 6, aliases: [6, 7] },
  T4: { primary: 1, aliases: [1, 2] },
  T5: { primary: 3, aliases: [3] },
  T6: { primary: 4, aliases: [4] },
  T7: { primary: 8, aliases: [8, 16] },
  T8: { primary: 9, aliases: [9, 10] },
  T9: { primary: 11, aliases: [11, 12] },
  T10: { primary: 13, aliases: [13] },
  T11: { primary: 14, aliases: [14, 15] },
}

export function pickTrackWalkSessionId(
  activeSessionId: string | null,
  sessions: SessionSummary[],
): string | null {
  const withLaps = sessions.find((session) => (session.lap_count ?? 0) > 0)
  const activeSession = activeSessionId
    ? sessions.find((session) => session.session_id === activeSessionId)
    : null

  if (activeSession && (activeSession.lap_count ?? 0) > 0) {
    return activeSessionId
  }

  return withLaps?.session_id ?? activeSessionId ?? null
}

export function buildTurnIdToCornerIndex(
  corners: CornerIdLike[],
): Record<number, number> {
  const mapping: Record<number, number> = {}

  corners.forEach((corner, index) => {
    const config = TRACK_WALK_TURN_IDS[corner.id]
    if (!config) return
    config.aliases.forEach((turnId) => {
      mapping[turnId] = index
    })
  })

  return mapping
}

export function buildTrackWalkCornerPins(
  corners: CornerIdLike[],
  trackTurns: TrackTurnLike[],
): CornerPinLike[] {
  const turnsById = new Map(trackTurns.map((turn) => [turn.id, turn]))

  return corners.map((corner) => {
    const config = TRACK_WALK_TURN_IDS[corner.id]
    const orderedIds = config
      ? [config.primary, ...config.aliases.filter((turnId) => turnId !== config.primary)]
      : []
    const turn = orderedIds
      .map((turnId) => turnsById.get(turnId))
      .find((candidate) => candidate != null)

    return {
      id: corner.id,
      x: turn?.cx ?? 0,
      y: turn?.cy ?? 0,
      turnId: turn?.id ?? null,
    }
  })
}
