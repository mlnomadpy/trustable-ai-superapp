import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from '../src/entities/session/model/sessionStore'

describe('sessionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts session and resets metrics', () => {
    const store = useSessionStore()
    
    // Set some dirty state
    store.lapCount = 5
    store.goalsHit = 2
    store.goalsTotal = 3
    
    store.startSession('session-123')
    
    expect(store.activeSessionId).toBe('session-123')
    expect(store.lapCount).toBe(0)
    expect(store.goalsHit).toBe(0)
    expect(store.goalsTotal).toBe(0)
  })

  it('ends session', () => {
    const store = useSessionStore()
    store.startSession('session-123')
    
    store.endSession()
    
    expect(store.activeSessionId).toBeNull()
  })
})
