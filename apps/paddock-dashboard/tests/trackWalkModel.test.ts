import { describe, expect, it } from 'vitest'
import { buildTrackWalkCornerPins, buildTurnIdToCornerIndex, pickTrackWalkSessionId } from '../src/pages/track-walk/trackWalkModel'

describe('trackWalkModel', () => {
  it('prefers the active session id when it already has laps', () => {
    const sessionId = pickTrackWalkSessionId('live-session', [
      {
        session_id: 'live-session',
        driver: 'Driver',
        driver_level: 'beginner',
        track: 'Sonoma Raceway',
        car: 'BMW M3 (E46)',
        started_at: '2026-05-20T10:00:00Z',
        ended_at: '2026-05-20T10:20:00Z',
        note: '',
        lap_count: 4,
        best_lap_s: 107.2,
      },
    ])

    expect(sessionId).toBe('live-session')
  })

  it('prefers the first session with laps over an active session that has none yet', () => {
    const sessionId = pickTrackWalkSessionId('live-session', [
      {
        session_id: 'live-session',
        driver: 'Driver',
        driver_level: 'beginner',
        track: 'Sonoma Raceway',
        car: 'BMW M3 (E46)',
        started_at: '2026-05-20T10:00:00Z',
        ended_at: null,
        note: '',
        lap_count: 0,
        best_lap_s: null,
      },
      {
        session_id: 'lap-session',
        driver: 'Driver',
        driver_level: 'beginner',
        track: 'Sonoma Raceway',
        car: 'BMW M3 (E46)',
        started_at: '2026-05-21T10:00:00Z',
        ended_at: '2026-05-21T10:20:00Z',
        note: '',
        lap_count: 7,
        best_lap_s: 106.8,
      },
    ])

    expect(sessionId).toBe('lap-session')
  })

  it('falls back to the first session with laps when no active session exists', () => {
    const sessionId = pickTrackWalkSessionId(null, [
      {
        session_id: 'empty-session',
        driver: 'Driver',
        driver_level: 'beginner',
        track: 'Sonoma Raceway',
        car: 'BMW M3 (E46)',
        started_at: '2026-05-20T10:00:00Z',
        ended_at: '2026-05-20T10:20:00Z',
        note: '',
        lap_count: 0,
        best_lap_s: null,
      },
      {
        session_id: 'lap-session',
        driver: 'Driver',
        driver_level: 'beginner',
        track: 'Sonoma Raceway',
        car: 'BMW M3 (E46)',
        started_at: '2026-05-21T10:00:00Z',
        ended_at: '2026-05-21T10:20:00Z',
        note: '',
        lap_count: 7,
        best_lap_s: 106.8,
      },
    ])

    expect(sessionId).toBe('lap-session')
  })

  it('maps aliased Sonoma turn markers to their logical corners', () => {
    const mapping = buildTurnIdToCornerIndex([
      { id: 'T3' },
      { id: 'T8' },
      { id: 'T11' },
    ])

    expect(mapping).toEqual({
      6: 0,
      7: 0,
      9: 1,
      10: 1,
      14: 2,
      15: 2,
    })
  })

  it('builds corner pins from the primary visible Sonoma turn markers', () => {
    const pins = buildTrackWalkCornerPins(
      [
        { id: 'T1' },
        { id: 'T6' },
        { id: 'T10' },
      ],
      [
        { id: 4, cx: 400, cy: 410 },
        { id: 5, cx: 120, cy: 130 },
        { id: 13, cx: 910, cy: 920 },
      ],
    )

    expect(pins).toEqual([
      { id: 'T1', x: 120, y: 130, turnId: 5 },
      { id: 'T6', x: 400, y: 410, turnId: 4 },
      { id: 'T10', x: 910, y: 920, turnId: 13 },
    ])
  })

  it('falls back to an alias turn marker when the primary marker is missing', () => {
    const pins = buildTrackWalkCornerPins(
      [{ id: 'T11' }],
      [{ id: 15, cx: 2220, cy: 530 }],
    )

    expect(pins).toEqual([
      { id: 'T11', x: 2220, y: 530, turnId: 15 },
    ])
  })
})
