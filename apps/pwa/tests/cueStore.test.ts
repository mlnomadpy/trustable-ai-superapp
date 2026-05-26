import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCueStore } from '../src/features/coach-interaction/model/cueStore'

describe('cueStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('opens SSE connection', () => {
    const store = useCueStore()
    store.open('test-session')

    expect(store._es).toBeDefined()
    expect(store._es?.addEventListener).toHaveBeenCalledWith('cue', expect.any(Function))
  })

  it('closes SSE connection', () => {
    const store = useCueStore()
    store.open('test-session')
    store.activeCue = { id: '1', text: 'Brake hard!', emotion: 'intense', timestamp: 123 }
    store.queue.push({ id: '2', text: 'Turn in!', emotion: 'focused', timestamp: 124 })
    
    const mockClose = store._es?.close

    store.close()

    expect(mockClose).toHaveBeenCalled()
    expect(store._es).toBeNull()
    expect(store.activeCue).toBeNull()
    expect(store.queue).toEqual([])
  })

  it('queues cue on named SSE cue events', () => {
    const store = useCueStore()
    store.open('test-session')

    const listener = vi.mocked(store._es!.addEventListener).mock.calls
      .find(([eventName]) => eventName === 'cue')?.[1] as EventListener

    listener({
      data: JSON.stringify({ burst_id: 7, text: 'Brake hard!', emotion: 'intense', ts: 123 }),
    } as any)

    expect(store.queue.length).toBe(1)
    expect(store.queue[0]).toEqual({ id: '7', text: 'Brake hard!', emotion: 'intense', timestamp: 123 })
  })

  it('supports unnamed SSE messages as a compatibility fallback', () => {
    const store = useCueStore()
    store.open('test-session')

    store._es!.onmessage!({
      data: JSON.stringify({ id: '1', text: 'Brake hard!', emotion: 'intense', timestamp: 123 }),
    } as any)

    expect(store.queue.length).toBe(1)
    expect(store.queue[0]).toEqual({ id: '1', text: 'Brake hard!', emotion: 'intense', timestamp: 123 })
  })

  it('clears activeCue on error and schedules retry', () => {
    vi.useFakeTimers()
    const store = useCueStore()
    store.open('test-session')
    
    store.activeCue = { id: '1', text: 'Brake hard!', emotion: 'intense', timestamp: 123 }
    store._es!.onerror!(new Event('error'))

    expect(store.activeCue).toBeNull()
    expect(store._retryCount).toBe(1) // first retry scheduled
    vi.useRealTimers()
  })
})
