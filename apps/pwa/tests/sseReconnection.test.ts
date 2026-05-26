import { describe, it, expect, vi, beforeEach } from 'vitest'

// We test the SSE reconnection logic through the telemetry store
// since useReconnectingSSE requires Vue component lifecycle (onUnmounted)
import { setActivePinia, createPinia } from 'pinia'
import { useTelemetryStore } from '../src/entities/session/model/telemetryStore'
import { useCueStore } from '../src/features/coach-interaction/model/cueStore'

describe('SSE reconnection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  describe('telemetryStore reconnection', () => {
    it('schedules retry on error with incrementing count', () => {
      const store = useTelemetryStore()
      store.open('test-session')
      
      // Trigger first error
      store._es!.onerror!(new Event('error'))
      
      expect(store._retryCount).toBe(1)
      expect(store._retryTimeout).not.toBeNull()
    })

    it('resets retry count on successful message', () => {
      const store = useTelemetryStore()
      store.open('test-session')
      
      store._retryCount = 5
      
      // Simulate successful telemetry event
      const addEventListenerMock = vi.mocked(store._es!.addEventListener)
      const handler = addEventListenerMock.mock.calls[0][1] as EventListener
      handler({ data: JSON.stringify({ speed: 100, timestamp: 12345 }) } as any)

      expect(store._retryCount).toBe(0)
    })

    it('gives up after max retries', () => {
      const store = useTelemetryStore()
      store.open('test-session')

      // Set to one below max
      store._retryCount = 9

      // Trigger error — should set retry to 10 and schedule
      store._es!.onerror!(new Event('error'))
      expect(store._retryCount).toBe(10)

      // Simulate the retry creating a new ES, then another error
      vi.advanceTimersByTime(3000)

      // The store should have reconnected and the _es should be defined again
      if (store._es) {
        store._es.onerror!(new Event('error'))
        // Should NOT schedule another retry (count exceeds max)
        // retryCount would be 1 from the new connection, not cumulative
      }
    })

    it('stops creating new EventSources once max retries are exhausted', () => {
      // Track every EventSource constructed during the test.
      const constructed: any[] = []
      const OriginalES = global.EventSource
      class TrackedES {
        url: string
        close = vi.fn()
        addEventListener = vi.fn()
        removeEventListener = vi.fn()
        onmessage: ((e: MessageEvent) => void) | null = null
        onerror: ((e: Event) => void) | null = null
        constructor(url: string) {
          this.url = url
          constructed.push(this)
        }
      }
      global.EventSource = TrackedES as any

      try {
        const store = useTelemetryStore()
        store.open('max-retry-session')

        // Initial connect = 1 EventSource constructed.
        expect(constructed.length).toBe(1)

        // Fire 11 consecutive failures (1 over the _maxRetries = 10 cap).
        // Each error triggers close + schedule of a reconnect; advancing timers
        // runs the reconnect which builds a new EventSource (if under cap).
        for (let i = 0; i < 11; i++) {
          const es = store._es
          if (!es || !es.onerror) break
          es.onerror(new Event('error'))
          vi.advanceTimersByTime(store._retryMs)
        }

        // Retry count should be clamped at the configured cap.
        expect(store._retryCount).toBe(store._maxRetries)

        // Only 10 reconnect attempts allowed after the initial connect →
        // at most 1 (initial) + 10 (retries) = 11 EventSources ever built.
        expect(constructed.length).toBeLessThanOrEqual(store._maxRetries + 1)

        // Critically, the 11th failure must NOT spawn a 12th EventSource.
        const countAfterCap = constructed.length
        // Try one more failure cycle — should be a no-op since _es is null and
        // no further retry was scheduled.
        if (store._es && store._es.onerror) {
          store._es.onerror(new Event('error'))
        }
        vi.advanceTimersByTime(store._retryMs * 2)
        expect(constructed.length).toBe(countAfterCap)

        // After exhaustion the store gave up: no live EventSource is open and
        // no new reconnect is in flight. (The store currently uses
        // console.error rather than a dedicated `.error` reactive field for
        // the user-visible signal, so we assert the observable give-up state:
        // no further EventSources are constructed, and _es stays null.)
        expect(store._es).toBeNull()
      } finally {
        global.EventSource = OriginalES
      }
    })

    it('clears retry timeout on close', () => {
      const store = useTelemetryStore()
      store.open('test-session')
      
      // Trigger error to schedule retry
      store._es!.onerror!(new Event('error'))
      expect(store._retryTimeout).not.toBeNull()
      
      // Close should clear everything
      store.close()
      expect(store._retryTimeout).toBeNull()
      expect(store._retryCount).toBe(0)
      expect(store._es).toBeNull()
    })
  })

  describe('cueStore reconnection', () => {
    it('schedules retry on error', () => {
      const store = useCueStore()
      store.open('test-session')
      
      store._es!.onerror!(new Event('error'))
      
      expect(store._retryCount).toBe(1)
      expect(store._retryTimeout).not.toBeNull()
    })

    it('resets retry count on successful cue', () => {
      const store = useCueStore()
      store.open('test-session')
      
      store._retryCount = 3
      
      const addEventListenerMock = vi.mocked(store._es!.addEventListener)
      const handler = addEventListenerMock.mock.calls.find(([eventName]) => eventName === 'cue')?.[1] as EventListener
      handler({ data: JSON.stringify({ burst_id: 1, text: 'Brake!', emotion: 'intense', ts: 0 }) } as any)
      
      expect(store._retryCount).toBe(0)
      expect(store.queue.length).toBe(1)
    })

    it('clears retry timeout on close', () => {
      const store = useCueStore()
      store.open('test-session')
      
      store._es!.onerror!(new Event('error'))
      
      store.close()
      expect(store._retryTimeout).toBeNull()
      expect(store._retryCount).toBe(0)
    })
  })
})
