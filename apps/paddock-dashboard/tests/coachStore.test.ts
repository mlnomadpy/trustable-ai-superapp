import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { bridge } from '../src/shared/api/bridge'
import { useCoachStore } from '../src/entities/coach/model/coachStore'

describe('coachStore debrief normalization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('maps legacy narrative_md and next_focus fields onto the active debrief state', async () => {
    vi.spyOn(bridge, 'post').mockResolvedValue({
      session_id: 'sess-1',
      narrative_md: '# Session debrief\n\nTurn 7 was the big lever.',
      next_focus: ['Turn 7', 'Brake release', 'Exit throttle'],
      emotion: 'serious',
    } as any)

    const store = useCoachStore()
    await store.fetchDebrief({ sessionId: 'sess-1', driverId: 'Driver 1' })

    expect(store.debrief?.narrative).toBe('# Session debrief\n\nTurn 7 was the big lever.')
    expect(store.debrief?.focus).toEqual(['Turn 7', 'Brake release', 'Exit throttle'])
    expect(store.debrief?.emotion).toBe('serious')
  })
})
