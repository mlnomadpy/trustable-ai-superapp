import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDuckDBStore } from '../src/shared/lib/duckdb/duckdbStore'
import * as duckdb from '@duckdb/duckdb-wasm'

describe('duckdbStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    
    // Default fetch mock arrayBuffer
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      arrayBuffer: async () => new ArrayBuffer(8)
    }) as any
  })

  it('initializes db only once', async () => {
    const store = useDuckDBStore()
    
    await store.init()
    expect(duckdb.selectBundle).toHaveBeenCalled()
    expect(store.db).toBeDefined()
    expect(store.db!.instantiate).toHaveBeenCalled()

    vi.clearAllMocks()

    // Second init should early return
    await store.init()
    expect(duckdb.selectBundle).not.toHaveBeenCalled()
  })

  it('ensures session caches and runs DDL', async () => {
    const store = useDuckDBStore()
    await store.init()

    // Mock registerFileBuffer
    store.db!.registerFileBuffer = vi.fn()

    const mockConn = await store.db!.connect()
    vi.spyOn(mockConn, 'query')
    store.db!.connect = vi.fn().mockResolvedValue(mockConn)
    
    await store.ensureSession('sid-123')

    expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8765/session/sid-123/export.parquet?table=telemetry')
    expect(store.db!.registerFileBuffer).toHaveBeenCalledWith('sid-123.parquet', expect.any(Uint8Array))
    expect(store.cachedSessionIds.has('sid-123')).toBe(true)
    
    expect(mockConn.query).toHaveBeenCalledWith(`CREATE OR REPLACE VIEW telemetry AS SELECT * FROM 'sid-123.parquet'`)
    
    // Ensure OPFS was hit
    expect(navigator.storage.getDirectory).toHaveBeenCalled()
  })

  it('queries database', async () => {
    const store = useDuckDBStore()
    await store.init()

    const mockConn = await store.db!.connect()
    vi.spyOn(mockConn, 'query')
    store.db!.connect = vi.fn().mockResolvedValue(mockConn)

    const result = await store.query('SELECT * FROM telemetry')
    
    expect(result).toBeDefined()
    expect(mockConn.query).toHaveBeenCalledWith('SELECT * FROM telemetry')
  })

  it('throws if query called before init', async () => {
    const store = useDuckDBStore()
    
    await expect(store.query('SELECT 1')).rejects.toThrow('DuckDB not initialized')
  })
})
