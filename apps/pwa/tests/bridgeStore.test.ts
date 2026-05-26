import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useBridgeStore } from '../src/shared/api/bridgeStore'
import { bridge } from '../src/shared/api/bridge'

describe('bridgeStore and bridge API', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  describe('bridgeStore', () => {
    it('polls health successfully', async () => {
      const store = useBridgeStore()
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok', version: '1.0', can_bridge: true })
      }) as any

      await store.pollHealth()

      expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8765/health')
      expect(store.health).toEqual({ status: 'ok', version: '1.0', can_bridge: true })
      expect(store.healthError).toBeNull()
      expect(store.consecutiveFailures).toBe(0)
    })

    it('handles poll failure', async () => {
      const store = useBridgeStore()
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error')) as any

      await store.pollHealth()

      expect(store.healthError).toContain('Network error')
      expect(store.consecutiveFailures).toBe(1)
    })

    it('toggles mock offline', () => {
      const store = useBridgeStore()
      
      store.toggleMockOffline()
      expect(store.mockOffline).toBe(true)
      expect(store.consecutiveFailures).toBe(3)
      expect(store.healthError).toBe('MOCK_OFFLINE')

      store.toggleMockOffline()
      expect(store.mockOffline).toBe(false)
      expect(store.consecutiveFailures).toBe(0)
      expect(store.healthError).toBeNull()
    })
  })

  describe('bridge API', () => {
    it('performs GET request', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: 'test' })
      }) as any

      const res = await bridge.get('/test-endpoint')
      
      expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8765/test-endpoint')
      expect(res).toEqual({ data: 'test' })
    })

    it('performs POST request', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true })
      }) as any

      const res = await bridge.post('/submit', { id: 1 })
      
      expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8765/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: 1 })
      })
      expect(res).toEqual({ success: true })
    })

    it('throws error on failed GET', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: 'Not Found'
      }) as any

      await expect(bridge.get('/invalid')).rejects.toThrow('Bridge GET /invalid failed: Not Found')
    })
  })
})
