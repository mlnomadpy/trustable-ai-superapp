import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTelemetryStore } from '../src/entities/session/model/telemetryStore'

describe('telemetryStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('opens SSE connection', () => {
    const store = useTelemetryStore()
    store.open('test-session')

    expect(store._es).toBeDefined()
  })

  it('closes SSE connection', () => {
    const store = useTelemetryStore()
    store.open('test-session')
    
    const mockClose = store._es?.close

    store.close()

    expect(mockClose).toHaveBeenCalled()
    expect(store._es).toBeNull()
    expect(store.frame).toBeNull()
  })

  it('parses telemetry frame on event', () => {
    const store = useTelemetryStore()
    store.open('test-session')
    
    const addEventListenerMock = vi.mocked(store._es!.addEventListener)
    const handler = addEventListenerMock.mock.calls[0][1] as EventListener

    const mockEvent = {
      data: JSON.stringify({ speed: 100, distance: 50, timestamp: 12345 })
    }
    handler(mockEvent as any)

    expect(store.frame).toEqual({ speed: 100, distance: 50, timestamp: 12345 })
  })

  it('handles invalid json payload', () => {
    const store = useTelemetryStore()
    store.open('test-session')
    
    const addEventListenerMock = vi.mocked(store._es!.addEventListener)
    const handler = addEventListenerMock.mock.calls[0][1] as EventListener

    const mockEvent = {
      data: '{ invalid-json }'
    }

    // Should not throw, should just keep previous state
    store.frame = { speed: 10 } as any
    handler(mockEvent as any)

    expect(store.frame).toEqual({ speed: 10 }) // Did not crash, kept old state
  })

  it('clears frame on error and schedules retry', () => {
    vi.useFakeTimers()
    const store = useTelemetryStore()
    store.open('test-session')
    
    store.frame = { speed: 10 } as any
    store._es!.onerror!(new Event('error'))

    expect(store.frame).toBeNull()
    expect(store._retryCount).toBe(1) // first retry scheduled
    vi.useRealTimers()
  })
})
